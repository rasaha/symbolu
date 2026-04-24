"""§12.5 cross-layer observable tests.

Validates:
  - The 2nd-difference math primitive is correct on known inputs.
  - LayerInstabilityObservable produces a scalar from a per-step
    MockLayerSource walk.
  - CoherenceAnchoredLayerBCVFObservable computes stability × alignment
    with the SCC product identity.
  - Observables require source 0 to expose layer_lookahead.
  - Probe harness isolation works end-to-end.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pytest

from symbolu_bcvf_llm.observables.base import ObservableValue
from symbolu_bcvf_llm.observables.layer import (
    CoherenceAnchoredLayerBCVFObservable,
    LayerInstabilityObservable,
    _layer_2nd_diff_norm,
)
from symbolu_bcvf_llm.observables.probe import probe_observables_parallel
from symbolu_bcvf_llm.sources.mock import MockLayerSource, MockSource


# --------------------------------------------------------------------------- #
# _layer_2nd_diff_norm math
# --------------------------------------------------------------------------- #


def test_2nd_diff_zero_for_constant_layers():
    """All layers identical → 2nd-diff is zero vector at every interior layer."""
    V = 8
    probs = np.tile([1.0 / V] * V, (5, 1))  # (5, V) uniform
    assert _layer_2nd_diff_norm(probs) == pytest.approx(0.0, abs=1e-10)


def test_2nd_diff_zero_for_linear_layers():
    """Linear interpolation across layers → 2nd-diff = 0."""
    V = 4
    probs = np.stack([
        np.array([1.0, 0.0, 0.0, 0.0]),
        np.array([0.75, 0.25, 0.0, 0.0]),
        np.array([0.5, 0.5, 0.0, 0.0]),
        np.array([0.25, 0.75, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0, 0.0]),
    ], axis=0)
    assert _layer_2nd_diff_norm(probs) == pytest.approx(0.0, abs=1e-10)


def test_2nd_diff_positive_for_jitter():
    """Alternating distributions across layers → large 2nd-diff."""
    V = 4
    a = np.array([1.0, 0.0, 0.0, 0.0])
    b = np.array([0.0, 1.0, 0.0, 0.0])
    probs = np.stack([a, b, a, b, a], axis=0)
    assert _layer_2nd_diff_norm(probs) > 1.0


def test_2nd_diff_requires_at_least_3_layers():
    V = 4
    probs = np.zeros((2, V))
    assert _layer_2nd_diff_norm(probs) == 0.0


def test_2nd_diff_rejects_1d_input():
    with pytest.raises(ValueError, match="N_layers"):
        _layer_2nd_diff_norm(np.zeros(10))


# --------------------------------------------------------------------------- #
# MockLayerSource plumbing
# --------------------------------------------------------------------------- #


def _peaked_logits(V, top, L, peak=10.0):
    z = np.full((L, V), -peak, dtype=np.float32)
    z[:, top] = peak
    return z


def _varied_layer_fn(prefix, n_layers, V):
    """Synthetic: each layer peaks on a different token."""
    z = np.full((n_layers, V), -5.0, dtype=np.float32)
    for l in range(n_layers):
        z[l, l % V] = 5.0
    return z


def _constant_layer_fn(prefix, n_layers, V):
    """All layers peak on the same token."""
    z = np.full((n_layers, V), -5.0, dtype=np.float32)
    z[:, 2] = 5.0
    return z


def test_mock_layer_source_returns_correct_shape():
    src = MockLayerSource(
        lambda p: _peaked_logits(8, 3, 5),
        L=5, V=8, n_layers=6,
    )
    out = src.layer_lookahead()
    assert out.shape == (6, 8)


def test_mock_layer_source_rows_are_probability_distributions():
    src = MockLayerSource(
        lambda p: _peaked_logits(8, 3, 5),
        L=5, V=8, n_layers=6,
    )
    out = src.layer_lookahead()
    for row in out:
        assert row.min() >= 0
        assert row.sum() == pytest.approx(1.0, abs=1e-6)


def test_mock_layer_source_default_is_constant_across_layers():
    """Without a layer_logits_fn, the default broadcasts the regular
    lookahead's position-0 logits — so all layers are identical."""
    src = MockLayerSource(
        lambda p: _peaked_logits(8, 3, 5),
        L=5, V=8, n_layers=6,
    )
    out = src.layer_lookahead()
    for l in range(1, 6):
        np.testing.assert_allclose(out[0], out[l])


def test_mock_layer_source_rejects_few_layers():
    with pytest.raises(ValueError, match="n_layers"):
        MockLayerSource(lambda p: _peaked_logits(8, 3, 5), L=5, V=8, n_layers=2)


# --------------------------------------------------------------------------- #
# LayerInstabilityObservable
# --------------------------------------------------------------------------- #


def _make_varied_layer_sources() -> List[MockSource]:
    """Two MockLayerSources: layer trajectories vary across layers."""
    return [
        MockLayerSource(
            lambda p: _peaked_logits(8, 3, 5),
            L=5, V=8, n_layers=6, layer_logits_fn=_varied_layer_fn,
        ),
        MockLayerSource(
            lambda p: _peaked_logits(8, 3, 5),
            L=5, V=8, n_layers=6, layer_logits_fn=_varied_layer_fn,
        ),
    ]


def _make_constant_layer_sources() -> List[MockSource]:
    """Two MockLayerSources with no cross-layer variation."""
    return [
        MockLayerSource(
            lambda p: _peaked_logits(8, 3, 5),
            L=5, V=8, n_layers=6, layer_logits_fn=_constant_layer_fn,
        ),
        MockLayerSource(
            lambda p: _peaked_logits(8, 3, 5),
            L=5, V=8, n_layers=6, layer_logits_fn=_constant_layer_fn,
        ),
    ]


def test_layer_instability_is_zero_for_constant_layers():
    obs = LayerInstabilityObservable()
    v = obs.observe(_make_constant_layer_sources(), [1], [3, 3])
    assert v.scalar == pytest.approx(0.0, abs=1e-10)


def test_layer_instability_positive_for_varied_layers():
    obs = LayerInstabilityObservable()
    v = obs.observe(_make_varied_layer_sources(), [1], [3, 3])
    assert v.scalar > 0.0


def test_layer_instability_polarity_is_suspicion():
    assert LayerInstabilityObservable().higher_means_more_suspicious is True


def test_layer_instability_requires_isolated_sources():
    assert LayerInstabilityObservable().requires_isolated_sources is True


def test_layer_instability_metadata_shape():
    obs = LayerInstabilityObservable()
    v = obs.observe(_make_varied_layer_sources(), [1], [3, 3, 3])
    assert v.metadata["n_steps"] == 3
    assert v.metadata["n_layers"] == 6
    assert len(v.metadata["per_step_instabilities"]) == 3
    assert v.metadata["mean_instability"] >= 0.0
    assert 0 <= v.metadata["argmax_step"] < 3


def test_layer_instability_degrades_gracefully_on_non_layer_source():
    """When source 0 lacks layer_lookahead, the observable emits
    zero with an `unsupported=True` metadata flag rather than
    crashing. Keeps probe runs alive on benchmarks that don't
    expose per-layer hidden states."""
    obs = LayerInstabilityObservable()
    plain = [
        MockSource(lambda p: _peaked_logits(8, 3, 5), L=5, V=8) for _ in range(2)
    ]
    v = obs.observe(plain, [1], [3])
    assert v.scalar == 0.0
    assert v.metadata.get("unsupported") is True
    assert "layer_lookahead" in v.metadata["reason"]


def test_layer_instability_empty_choice_returns_zero():
    obs = LayerInstabilityObservable()
    v = obs.observe(_make_varied_layer_sources(), [1], [])
    assert v.scalar == 0.0
    assert v.metadata["n_steps"] == 0


# --------------------------------------------------------------------------- #
# CoherenceAnchoredLayerBCVFObservable
# --------------------------------------------------------------------------- #


def test_coherence_layer_polarity_is_trust():
    obs = CoherenceAnchoredLayerBCVFObservable()
    assert obs.higher_means_more_suspicious is False


def test_coherence_layer_requires_isolated_sources():
    obs = CoherenceAnchoredLayerBCVFObservable()
    assert obs.requires_isolated_sources is True


def test_coherence_layer_product_identity():
    """scalar = stability × alignment (±ε)."""
    obs = CoherenceAnchoredLayerBCVFObservable()
    v = obs.observe(_make_varied_layer_sources(), [1], [3, 3])
    expected = v.metadata["stability"] * v.metadata["alignment"]
    assert v.scalar == pytest.approx(expected, abs=1e-10)


def test_coherence_layer_stability_is_one_for_constant_layers():
    """No cross-layer variation → max_layer_instability = 0 → stability = 1."""
    obs = CoherenceAnchoredLayerBCVFObservable()
    v = obs.observe(_make_constant_layer_sources(), [1], [3, 3])
    assert v.metadata["max_layer_instability"] == pytest.approx(0.0, abs=1e-10)
    assert v.metadata["stability"] == pytest.approx(1.0, abs=1e-10)


def test_coherence_layer_alignment_high_when_choice_matches_peak():
    """Source 0 peaks on token 3 at position 0; choice = [3, 3] → P(3) ≈ 1."""
    obs = CoherenceAnchoredLayerBCVFObservable()
    v = obs.observe(_make_constant_layer_sources(), [1], [3, 3])
    assert v.metadata["alignment"] > 0.99


def test_coherence_layer_alignment_low_when_choice_diverges():
    """Choice tokens that source 0 assigns near-zero probability → alignment ≈ 0."""
    obs = CoherenceAnchoredLayerBCVFObservable()
    v = obs.observe(_make_constant_layer_sources(), [1], [5, 5])
    assert v.metadata["alignment"] < 1e-5


def test_coherence_layer_metadata_keys():
    obs = CoherenceAnchoredLayerBCVFObservable()
    v = obs.observe(_make_varied_layer_sources(), [1], [3, 3, 3])
    for k in (
        "stability", "alignment", "max_layer_instability",
        "mean_layer_instability", "per_step_instabilities",
        "geo_mean_log_prob", "n_steps",
    ):
        assert k in v.metadata


# --------------------------------------------------------------------------- #
# Probe-harness integration
# --------------------------------------------------------------------------- #


class _MockLayerBench:
    """Minimal benchmark producing 2-choice questions with
    MockLayerSources. Inline class — not worth a full class in the
    benchmark module for this test."""

    name = "mock_layer"

    def __init__(self, num_questions: int = 4):
        from symbolu_bcvf_llm.benchmark.dataset import Question
        self._qs: List[Question] = []
        self.num_questions = num_questions
        for q_idx in range(num_questions):
            correct_token = 3
            wrong_token = 5
            self._qs.append(Question(
                prompt_tokens=[0, 1, q_idx],
                choices=["correct", "wrong"],
                choice_tokens=[
                    [correct_token, correct_token, correct_token],
                    [wrong_token, wrong_token, wrong_token],
                ],
                correct_index=0,
                metadata={"question_id": q_idx},
            ))

    @property
    def questions(self):
        return tuple(self._qs)

    def make_sources(self, question):
        return [
            MockLayerSource(
                lambda p: _peaked_logits(8, 3, 5),
                L=5, V=8, n_layers=6,
                layer_logits_fn=_varied_layer_fn,
            ),
            MockLayerSource(
                lambda p: _peaked_logits(8, 3, 5),
                L=5, V=8, n_layers=6,
                layer_logits_fn=_varied_layer_fn,
            ),
        ]


def test_probe_harness_runs_layer_observables_end_to_end():
    bench = _MockLayerBench(num_questions=4)
    reports = probe_observables_parallel(
        [LayerInstabilityObservable(), CoherenceAnchoredLayerBCVFObservable()],
        bench,
        retain_datapoints=True,
    )
    for name in (
        "layer_instability_max", "coherence_anchored_layer_bcvf_per_step",
    ):
        r = reports[name]
        assert r.n_datapoints == 8  # 4 questions × 2 choices
        for dp in r.datapoints:
            assert dp.observable_value.metadata["n_steps"] == 3
