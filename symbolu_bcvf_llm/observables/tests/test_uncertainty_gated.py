"""Tests for UncertaintyGatedBCVFPerStepMaxObservable."""

from __future__ import annotations

from typing import List

import numpy as np
import pytest

from symbolu_bcvf_llm.benchmark.dataset import MockBenchmark
from symbolu_bcvf_llm.observables.base import ObservableValue
from symbolu_bcvf_llm.observables.probe import probe_observables_parallel
from symbolu_bcvf_llm.observables.uncertainty_gated import (
    UncertaintyGatedBCVFPerStepMaxObservable,
)
from symbolu_bcvf_llm.sources.mock import MockSource


def _peaked(V: int, top: int, L: int = 5, peak: float = 10.0) -> np.ndarray:
    z = np.full((L, V), -peak, dtype=np.float32)
    z[:, top] = peak
    return z


def _uniform_logits(V: int, L: int = 5) -> np.ndarray:
    return np.zeros((L, V), dtype=np.float32)


def _make_agreeing_peaked_sources(V: int = 8) -> List[MockSource]:
    return [MockSource(lambda p, V=V: _peaked(V, 3), L=5, V=V) for _ in range(3)]


def _make_uniform_sources(V: int = 8) -> List[MockSource]:
    return [MockSource(lambda p, V=V: _uniform_logits(V), L=5, V=V) for _ in range(3)]


# --------------------------------------------------------------------------- #
# Shape / polarity / opt-in
# --------------------------------------------------------------------------- #


def test_returns_observable_value():
    obs = UncertaintyGatedBCVFPerStepMaxObservable()
    v = obs.observe(_make_agreeing_peaked_sources(), [1], [3, 3])
    assert isinstance(v, ObservableValue)
    assert isinstance(v.scalar, float)


def test_polarity_is_suspicion():
    assert UncertaintyGatedBCVFPerStepMaxObservable().higher_means_more_suspicious is True


def test_requires_isolated_sources():
    assert UncertaintyGatedBCVFPerStepMaxObservable().requires_isolated_sources is True


def test_default_threshold_is_one_nat():
    """§0.8 pre-commit: threshold must not be silently tuned."""
    obs = UncertaintyGatedBCVFPerStepMaxObservable()
    v = obs.observe(_make_agreeing_peaked_sources(), [1], [3])
    assert v.metadata["entropy_threshold"] == 1.0


def test_custom_threshold_propagates():
    obs = UncertaintyGatedBCVFPerStepMaxObservable(entropy_threshold=2.5)
    v = obs.observe(_make_agreeing_peaked_sources(), [1], [3])
    assert v.metadata["entropy_threshold"] == 2.5


# --------------------------------------------------------------------------- #
# Metadata structure
# --------------------------------------------------------------------------- #


def test_metadata_keys():
    obs = UncertaintyGatedBCVFPerStepMaxObservable()
    v = obs.observe(_make_agreeing_peaked_sources(), [1], [3, 3, 3])
    for k in (
        "entropy_threshold", "n_steps", "n_uncertain_steps",
        "per_step_costs", "per_step_entropies",
        "max_step_cost_all", "max_step_cost_gated",
    ):
        assert k in v.metadata


def test_metadata_shape_matches_choice_length():
    obs = UncertaintyGatedBCVFPerStepMaxObservable()
    choice = [3, 3, 3, 3]
    v = obs.observe(_make_agreeing_peaked_sources(), [1], choice)
    assert v.metadata["n_steps"] == len(choice)
    assert len(v.metadata["per_step_costs"]) == len(choice)
    assert len(v.metadata["per_step_entropies"]) == len(choice)


# --------------------------------------------------------------------------- #
# Gating behavior
# --------------------------------------------------------------------------- #


def test_peaked_sources_below_threshold_gate_out():
    """Highly-peaked softmax → entropy ≈ 0 → below default tau=1.0 →
    all steps gated out → scalar = 0 regardless of BCVF cost."""
    obs = UncertaintyGatedBCVFPerStepMaxObservable()
    v = obs.observe(_make_agreeing_peaked_sources(V=8), [1], [3, 3, 3])
    assert v.scalar == 0.0
    assert v.metadata["n_uncertain_steps"] == 0
    # All per-step entropies should be near zero
    for ent in v.metadata["per_step_entropies"]:
        assert ent < 0.1


def test_uniform_sources_above_threshold_pass_gate():
    """Uniform distribution over V=8 tokens → entropy = ln(8) ≈ 2.08 nats
    > tau=1.0 → all steps pass gate."""
    obs = UncertaintyGatedBCVFPerStepMaxObservable()
    v = obs.observe(_make_uniform_sources(V=8), [1], [3, 3])
    assert v.metadata["n_uncertain_steps"] == 2
    # BCVF on uniform sources is 0 (no disagreement), so scalar = 0.
    # The point is: all entropies > tau, all steps considered.
    for ent in v.metadata["per_step_entropies"]:
        assert ent > 1.0


def test_threshold_higher_than_max_entropy_returns_zero():
    """Set tau above all possible entropies → no step qualifies → scalar=0."""
    obs = UncertaintyGatedBCVFPerStepMaxObservable(entropy_threshold=100.0)
    v = obs.observe(_make_uniform_sources(V=8), [1], [3, 3])
    assert v.scalar == 0.0
    assert v.metadata["n_uncertain_steps"] == 0


def test_empty_choice_tokens_returns_zero():
    obs = UncertaintyGatedBCVFPerStepMaxObservable()
    v = obs.observe(_make_agreeing_peaked_sources(), [1], [])
    assert v.scalar == 0.0
    assert v.metadata["n_steps"] == 0
    assert v.metadata["per_step_costs"] == []


def test_max_gated_equals_scalar():
    """`max_step_cost_gated` metadata always equals the scalar."""
    obs = UncertaintyGatedBCVFPerStepMaxObservable()
    v = obs.observe(_make_uniform_sources(V=8), [1], [3, 3])
    assert v.metadata["max_step_cost_gated"] == v.scalar


# --------------------------------------------------------------------------- #
# State mutation (commit opt-in)
# --------------------------------------------------------------------------- #


def test_advances_sources_through_commits():
    """For K-token choice, K-1 commits happen between steps."""
    obs = UncertaintyGatedBCVFPerStepMaxObservable()
    srcs = [
        MockSource(lambda p: _peaked(8, 3), L=5, V=8, initial_prefix=[1, 2])
        for _ in range(3)
    ]
    obs.observe(srcs, [1, 2], [3, 3, 3])
    # Started at [1, 2]; after 3-token choice, 2 commits happened.
    for s in srcs:
        assert list(s.committed_prefix) == [1, 2, 3, 3]


def test_probe_harness_isolation_works():
    bench = MockBenchmark(num_questions=3)
    reports = probe_observables_parallel(
        [UncertaintyGatedBCVFPerStepMaxObservable()],
        bench,
        retain_datapoints=True,
    )
    r = reports["uncertainty_gated_bcvf_per_step_max"]
    assert r.n_datapoints == 6  # 3 questions × 2 choices
    for dp in r.datapoints:
        # MockBenchmark produces 3-token choices.
        assert dp.observable_value.metadata["n_steps"] == 3
