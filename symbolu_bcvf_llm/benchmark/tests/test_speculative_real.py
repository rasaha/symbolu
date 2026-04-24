"""§12.3 SpeculativeDecodingBenchmark — unit tests for the
acceptance-math primitives and prompt-text routing.

Tests the pure-NumPy bits and the class-construction mocking path.
Real-model loading is deferred to runpod — not exercised in CI.
"""

from __future__ import annotations

from unittest import mock

import numpy as np
import pytest

from symbolu_bcvf_llm.benchmark.speculative import (
    SpeculativeDecodingBenchmark,
    _stable_softmax,
)


# --------------------------------------------------------------------------- #
# _stable_softmax
# --------------------------------------------------------------------------- #


def test_stable_softmax_sums_to_one():
    x = np.array([[1.0, 2.0, 3.0], [0.0, -1.0, -2.0]])
    p = _stable_softmax(x, axis=-1)
    assert np.allclose(p.sum(axis=-1), 1.0)


def test_stable_softmax_handles_large_values():
    """No overflow when inputs are very large."""
    x = np.array([[1000.0, 1000.1, 999.9]])
    p = _stable_softmax(x, axis=-1)
    assert np.all(np.isfinite(p))
    assert np.allclose(p.sum(), 1.0)


def test_stable_softmax_monotone_preserved():
    x = np.array([1.0, 2.0, 3.0])
    p = _stable_softmax(x, axis=-1)
    assert p[0] < p[1] < p[2]


# --------------------------------------------------------------------------- #
# _compute_expected_accepted
# --------------------------------------------------------------------------- #


def _make_fake_bench_for_math_test(
    target_probs_seq, draft_probs_seq, vocab_size=8,
):
    """Build a SpeculativeDecodingBenchmark via __new__ + wire enough
    internals for _compute_expected_accepted to run. The target+draft
    forward passes are mocked to return the given probability
    sequences."""
    bench = SpeculativeDecodingBenchmark.__new__(SpeculativeDecodingBenchmark)
    bench._target_model = mock.Mock()
    bench._draft_model = mock.Mock()
    bench._target_tokenizer = mock.Mock()

    def fake_encode(text, add_special_tokens=True):
        # Simple: prompt tokenizes to [1, 2, 3] regardless of text
        return [1, 2, 3]

    bench._target_tokenizer.encode = fake_encode
    bench.vocab_size = vocab_size
    bench.eos_token_id = None

    class _FakeTorchTensor:
        """Minimal stand-in for torch.Tensor just for this test."""
        def __init__(self, logits):
            self._logits = np.asarray(logits)
        # When the code does t_out.logits[0, i:j, :].float().cpu().numpy(),
        # we need to support that chain.
        @property
        def logits(self):
            return _FakeLogits(self._logits)

    class _FakeLogits:
        def __init__(self, arr):
            self._arr = arr
        def __getitem__(self, key):
            return _FakeSubTensor(self._arr[key])

    class _FakeSubTensor:
        def __init__(self, arr):
            self._arr = np.asarray(arr)
        def float(self):
            return self
        def cpu(self):
            return self
        def numpy(self):
            return self._arr

    # Make forward calls return pre-computed logits such that
    # softmax(logits) == the desired probability sequence.
    def logits_from_probs(probs_seq):
        """Convert (K, V) probs into (1, prompt+K, V) fake logits.
        Logits are log-probs padded with a prefix for the prompt."""
        K, V = probs_seq.shape
        prompt_len = 3
        total_len = prompt_len + K
        logits = np.zeros((1, total_len, V), dtype=np.float64)
        # Positions prompt_len - 1 .. prompt_len - 1 + K predict the
        # candidate tokens; fill those with log(probs).
        for i in range(K):
            pos = prompt_len - 1 + i
            logits[0, pos, :] = np.log(probs_seq[i] + 1e-30)
        return logits

    target_logits = logits_from_probs(np.asarray(target_probs_seq))
    draft_logits = logits_from_probs(np.asarray(draft_probs_seq))

    bench._target_model.side_effect = lambda x: _FakeTorchTensor(target_logits)
    bench._draft_model.side_effect = lambda x: _FakeTorchTensor(draft_logits)

    # Mock next(model.parameters()).device to avoid touching torch.
    bench._target_model.parameters = lambda: iter([mock.Mock(device="cpu")])
    bench._draft_model.parameters = lambda: iter([mock.Mock(device="cpu")])
    return bench


def test_expected_accepted_when_target_matches_draft():
    """If target and draft have identical distributions, alpha = 1
    at every position, so E[accepted] = K (full draft length)."""
    pytest.importorskip("torch")
    V = 8
    K = 3
    probs = np.tile([0.5, 0.3, 0.1, 0.05, 0.03, 0.01, 0.005, 0.005], (K, 1))
    bench = _make_fake_bench_for_math_test(probs, probs, vocab_size=V)
    # Teacher-force candidate [0, 0, 0] — tokens all in-vocab
    candidate = np.array([0, 0, 0])
    e = bench._compute_expected_accepted("prompt text", candidate)
    assert e == pytest.approx(float(K), abs=1e-9)


def test_expected_accepted_when_draft_confidently_wrong():
    """Draft puts all mass on a token target rejects → alpha ≈ 0
    on first position → E[accepted] ≈ 0."""
    pytest.importorskip("torch")
    V = 8
    K = 3
    target_probs = np.tile([0.9, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.04],
                           (K, 1))
    draft_probs = np.tile([0.01, 0.9, 0.01, 0.01, 0.01, 0.01, 0.01, 0.04],
                          (K, 1))
    bench = _make_fake_bench_for_math_test(
        target_probs, draft_probs, vocab_size=V,
    )
    # Candidate picks the draft's preferred token (1), which the
    # target mostly rejects.
    candidate = np.array([1, 1, 1])
    e = bench._compute_expected_accepted("prompt text", candidate)
    # alpha_0 = min(1, 0.01 / 0.9) ≈ 0.011
    # Subsequent alphas are also ~0.011 but weighted by product.
    # E ≈ 0.011 + 0.011 * 0.011 + ... ≈ 0.011
    assert e < 0.1


def test_expected_accepted_partial_match():
    """Target has prob 0.4 on candidate token, draft has prob 0.5.
    alpha = min(1, 0.4/0.5) = 0.8.
    K=2: E = 0.8 + 0.8 * 0.8 = 1.44."""
    pytest.importorskip("torch")
    V = 4
    target = np.array([
        [0.4, 0.3, 0.2, 0.1],
        [0.4, 0.3, 0.2, 0.1],
    ])
    draft = np.array([
        [0.5, 0.2, 0.2, 0.1],
        [0.5, 0.2, 0.2, 0.1],
    ])
    bench = _make_fake_bench_for_math_test(target, draft, vocab_size=V)
    candidate = np.array([0, 0])
    e = bench._compute_expected_accepted("prompt text", candidate)
    assert e == pytest.approx(0.8 + 0.64, rel=1e-6)


# --------------------------------------------------------------------------- #
# _extract_prompt_text — schema routing
# --------------------------------------------------------------------------- #


def test_extract_prompt_text_halueval_schema():
    """HaluEval-QA rows have `question` → formats as Q/A prompt."""
    bench = SpeculativeDecodingBenchmark.__new__(SpeculativeDecodingBenchmark)
    row = {"question": "What is 2+2?", "right_answer": "4"}
    text = bench._extract_prompt_text(row)
    assert "What is 2+2?" in text
    assert text.startswith("Q: ")
    assert text.endswith("A:")


def test_extract_prompt_text_generic_prompt():
    bench = SpeculativeDecodingBenchmark.__new__(SpeculativeDecodingBenchmark)
    row = {"prompt": "Custom prompt string."}
    text = bench._extract_prompt_text(row)
    assert text == "Custom prompt string."


def test_extract_prompt_text_unknown_schema_raises():
    bench = SpeculativeDecodingBenchmark.__new__(SpeculativeDecodingBenchmark)
    with pytest.raises(KeyError, match="no recognized prompt field"):
        bench._extract_prompt_text({"foo": "bar", "baz": 42})
