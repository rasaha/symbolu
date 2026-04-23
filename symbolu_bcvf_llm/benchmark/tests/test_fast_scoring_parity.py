"""§6.2 Phase 2 parity tests: the batched fast-scoring path must
produce log-probs identical (within fp tolerance) to the per-token
lookahead/commit slow path.

This is the load-bearing guarantee: if fast and slow disagree, the
Phase 2 speedup is not safe to use because it changes the §1.10
verdict semantics.
"""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_bcvf_llm.benchmark.scoring import (
    _has_batched_scoring,
    score_choice_blend,
    score_choice_blend_batched,
    score_choice_vanilla,
    score_choice_vanilla_batched,
)
from symbolu_bcvf_llm.sources.base import BatchedScoringSource
from symbolu_bcvf_llm.sources.mock import MockSource


def _make_source(V=8, L=5, peak_top=2, seed=0):
    """Produces peaked logits on a prefix-dependent token so commits
    change future output — exercises the teacher-forcing state."""
    def fn(prefix):
        rng = np.random.default_rng(seed=seed + (sum(prefix) if prefix else 0))
        z = rng.normal(size=(L, V)).astype(np.float32)
        # Add a bias toward `peak_top + prefix_len % V` so tokens matter.
        bias_idx = (peak_top + (len(prefix) if prefix else 0)) % V
        z[:, bias_idx] += 5.0
        return z
    return MockSource(fn, L=L, V=V, initial_prefix=[1])


def test_mock_source_implements_batched_protocol():
    s = _make_source()
    assert isinstance(s, BatchedScoringSource)
    assert _has_batched_scoring(s)


def test_score_teacher_forced_shape_and_sum_to_one():
    s = _make_source(V=8)
    probs = s.score_teacher_forced([3, 5, 1])
    assert probs.shape == (3, 8)
    row_sums = probs.sum(axis=-1)
    # MockSource's fallback path reads fp32 probs from lookahead() and
    # upcasts — rounding gives Σp = 1 ± ~1e-7. HuggingFaceSource's native
    # batched path computes in fp64 and is tighter (~1e-15) but we set
    # a shared tolerance that both pass.
    np.testing.assert_allclose(row_sums, 1.0, rtol=0, atol=1e-5)


def test_score_teacher_forced_does_not_mutate_source_state():
    s = _make_source()
    before = s.committed_prefix
    s.score_teacher_forced([2, 3, 1])
    after = s.committed_prefix
    assert before == after


def test_vanilla_fast_matches_slow():
    """For the same source, fast-vanilla == slow-vanilla (within fp tolerance)."""
    V, L = 8, 5
    target = [3, 5, 1, 2]

    # Two identical source triples (same fn, same initial state).
    srcs_slow = [_make_source(V=V, L=L, seed=7) for _ in range(3)]
    srcs_fast = [_make_source(V=V, L=L, seed=7) for _ in range(3)]

    slow_score = score_choice_vanilla(srcs_slow, target)
    fast_score = score_choice_vanilla_batched(srcs_fast, target)

    assert abs(slow_score - fast_score) < 1e-10, (
        f"fast-vanilla diverged from slow-vanilla: "
        f"fast={fast_score} slow={slow_score}"
    )


def test_blend_fast_matches_slow():
    """Conventional-blend fast path must match slow within fp tolerance."""
    V, L = 8, 5
    target = [3, 5, 1, 2]

    srcs_slow = [_make_source(V=V, L=L, seed=i) for i in range(3)]
    srcs_fast = [_make_source(V=V, L=L, seed=i) for i in range(3)]

    slow_score = score_choice_blend(srcs_slow, target)
    fast_score = score_choice_blend_batched(srcs_fast, target)

    assert abs(slow_score - fast_score) < 1e-10, (
        f"fast-blend diverged from slow-blend: "
        f"fast={fast_score} slow={slow_score}"
    )


def test_vanilla_batched_rejects_non_batched_source():
    """Calling the fast path on a source without the batched protocol
    should raise TypeError with a clear message."""

    class DumbSource:
        # Satisfies Source protocol but NOT BatchedScoringSource.
        L = 5
        vocab_size = 8
        eos_token_id = None

        def lookahead(self):
            return (np.zeros((5, 8), dtype=np.float32),
                    np.ones(5, dtype=bool))

        def commit(self, token_id):
            pass

    dumb = DumbSource()
    # Confirm it's NOT batched-scoring-capable.
    assert not _has_batched_scoring(dumb)

    with pytest.raises(TypeError, match="score_teacher_forced"):
        score_choice_vanilla_batched([dumb], [1, 2])


def test_empty_target_tokens_returns_zero_score():
    """Edge case: K=0 empty target should give log P = 0 (empty sum)."""
    srcs = [_make_source() for _ in range(3)]
    assert score_choice_vanilla_batched(srcs, []) == 0.0
    srcs2 = [_make_source() for _ in range(3)]
    assert score_choice_blend_batched(srcs2, []) == 0.0


def test_fast_scoring_runs_harness_end_to_end_on_mock_benchmark():
    """Regression: harness with fast_scoring=True works end-to-end
    against MockBenchmark. Should match fast_scoring=False outcomes
    for determinism-sensitive assertions (same predictions)."""
    from symbolu_bcvf_llm.benchmark.dataset import MockBenchmark
    from symbolu_bcvf_llm.benchmark.harness import run_benchmark

    bench_fast = MockBenchmark(num_questions=6, seed=0)
    bench_slow = MockBenchmark(num_questions=6, seed=0)

    bundle_fast = run_benchmark(bench_fast, fast_scoring=True)
    bundle_slow = run_benchmark(bench_slow, fast_scoring=False)

    for decoder in ("vanilla", "conventional_blend", "bcvf_trust"):
        r_fast = bundle_fast.results[decoder]
        r_slow = bundle_slow.results[decoder]
        np.testing.assert_array_equal(
            r_fast.per_question_predicted,
            r_slow.per_question_predicted,
            err_msg=f"fast and slow disagree on predictions for {decoder}",
        )
        assert r_fast.accuracy == r_slow.accuracy


def test_fast_scoring_bundle_metadata_records_setting():
    from symbolu_bcvf_llm.benchmark.dataset import MockBenchmark
    from symbolu_bcvf_llm.benchmark.harness import run_benchmark

    bench = MockBenchmark(num_questions=3)
    bundle = run_benchmark(bench, fast_scoring=True)
    for r in bundle.results.values():
        assert r.metadata.get("fast_scoring") is True
    bundle2 = run_benchmark(bench, fast_scoring=False)
    for r in bundle2.results.values():
        assert r.metadata.get("fast_scoring") is False
