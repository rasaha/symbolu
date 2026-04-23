"""Tests for CoherenceAnchoredBCVFObservable — stability × alignment."""

from __future__ import annotations

from typing import List

import numpy as np
import pytest

from symbolu_bcvf_llm.benchmark.dataset import MockBenchmark
from symbolu_bcvf_llm.observables.base import ObservableValue
from symbolu_bcvf_llm.observables.coherence import (
    CoherenceAnchoredBCVFObservable,
    CoherenceAnchoredBCVFPerStepObservable,
)
from symbolu_bcvf_llm.observables.probe import probe_observables_parallel
from symbolu_bcvf_llm.sources.mock import MockSource


def _peaked(V: int, top: int, L: int = 5, peak: float = 10.0) -> np.ndarray:
    z = np.full((L, V), -peak, dtype=np.float32)
    z[:, top] = peak
    return z


def _make_agreeing_sources(
    V: int = 8, L: int = 5, top: int = 3,
) -> List[MockSource]:
    return [
        MockSource(lambda p, V=V, top=top, L=L: _peaked(V, top, L), L=L, V=V)
        for _ in range(3)
    ]


def _make_disagreeing_sources(V: int = 8, L: int = 5) -> List[MockSource]:
    return [
        MockSource(lambda p, V=V, L=L: _peaked(V, 1, L), L=L, V=V),
        MockSource(lambda p, V=V, L=L: _peaked(V, 2, L), L=L, V=V),
        MockSource(lambda p, V=V, L=L: _peaked(V, 3, L), L=L, V=V),
    ]


# --------------------------------------------------------------------------- #
# Basic shape + polarity
# --------------------------------------------------------------------------- #


def test_returns_scalar_float():
    obs = CoherenceAnchoredBCVFObservable()
    v = obs.observe(_make_agreeing_sources(), [1, 2], [3])
    assert isinstance(v, ObservableValue)
    assert isinstance(v.scalar, float)


def test_polarity_is_trust():
    assert CoherenceAnchoredBCVFObservable().higher_means_more_suspicious is False


def test_metadata_keys():
    obs = CoherenceAnchoredBCVFObservable()
    v = obs.observe(_make_agreeing_sources(), [1], [3])
    for k in ("stability", "alignment", "bcvf_total_cost", "first_token"):
        assert k in v.metadata


# --------------------------------------------------------------------------- #
# Stability component (via BCVF cost)
# --------------------------------------------------------------------------- #


def test_agreeing_sources_give_stability_1():
    """All sources identical → BCVF total_cost = 0 → stability = 1."""
    obs = CoherenceAnchoredBCVFObservable()
    v = obs.observe(_make_agreeing_sources(top=3), [1], [3])
    assert v.metadata["stability"] == pytest.approx(1.0, abs=1e-10)
    # bcvf cost should be near-zero in agreement case
    assert v.metadata["bcvf_total_cost"] == pytest.approx(0.0, abs=1e-10)


# --------------------------------------------------------------------------- #
# Alignment component (P(first_token | prompt) from source 0)
# --------------------------------------------------------------------------- #


def test_alignment_high_when_choice_matches_peak():
    """When source 0 peaks on token 3 and choice is [3], alignment ≈ 1."""
    obs = CoherenceAnchoredBCVFObservable()
    v = obs.observe(_make_agreeing_sources(V=8, top=3), [1], [3])
    # Peak of 10 on token 3 → softmax ≈ 1.0 on that token
    assert v.metadata["alignment"] > 0.9


def test_alignment_low_when_choice_is_not_model_preferred():
    """Source 0 peaks on token 3 but choice is [5] → alignment near 0."""
    obs = CoherenceAnchoredBCVFObservable()
    v = obs.observe(_make_agreeing_sources(V=8, top=3), [1], [5])
    assert v.metadata["alignment"] < 0.01


def test_alignment_defaults_to_1_for_empty_choice():
    obs = CoherenceAnchoredBCVFObservable()
    v = obs.observe(_make_agreeing_sources(), [1], [])
    assert v.metadata["alignment"] == 1.0
    assert v.metadata["first_token"] == -1


# --------------------------------------------------------------------------- #
# Combined scalar = stability × alignment
# --------------------------------------------------------------------------- #


def test_scalar_equals_stability_times_alignment():
    """The product identity must hold exactly (up to float rounding)."""
    obs = CoherenceAnchoredBCVFObservable()
    v = obs.observe(_make_agreeing_sources(V=8, top=3), [1], [3])
    expected = v.metadata["stability"] * v.metadata["alignment"]
    assert v.scalar == pytest.approx(expected, abs=1e-10)


def test_scalar_low_when_alignment_low():
    """Stability high but alignment low → combined scalar low."""
    obs = CoherenceAnchoredBCVFObservable()
    v = obs.observe(_make_agreeing_sources(V=8, top=3), [1], [5])
    # stability ≈ 1 (sources agree), alignment ≈ 0 (wrong token) → scalar ≈ 0
    assert v.scalar < 0.01
    assert v.metadata["stability"] > 0.99
    assert v.metadata["alignment"] < 0.01


# --------------------------------------------------------------------------- #
# No state mutation
# --------------------------------------------------------------------------- #


def test_does_not_mutate_source_state():
    obs = CoherenceAnchoredBCVFObservable()
    srcs = [
        MockSource(lambda p: _peaked(8, 3), L=5, V=8, initial_prefix=[1, 2, 3])
        for _ in range(3)
    ]
    before = [s.committed_prefix for s in srcs]
    obs.observe(srcs, [1, 2], [3])
    after = [s.committed_prefix for s in srcs]
    assert before == after


# --------------------------------------------------------------------------- #
# CoherenceAnchoredBCVFPerStepObservable
# --------------------------------------------------------------------------- #


def test_per_step_returns_scalar_float():
    obs = CoherenceAnchoredBCVFPerStepObservable()
    v = obs.observe(_make_agreeing_sources(), [1, 2], [3, 3, 3])
    assert isinstance(v, ObservableValue)
    assert isinstance(v.scalar, float)


def test_per_step_polarity_is_trust():
    obs = CoherenceAnchoredBCVFPerStepObservable()
    assert obs.higher_means_more_suspicious is False


def test_per_step_requires_isolated_sources():
    obs = CoherenceAnchoredBCVFPerStepObservable()
    assert obs.requires_isolated_sources is True


def test_per_step_metadata_shape():
    obs = CoherenceAnchoredBCVFPerStepObservable()
    choice = [3, 3, 3]
    v = obs.observe(_make_agreeing_sources(), [1], choice)
    for k in ("stability", "alignment", "max_step_bcvf",
              "geo_mean_log_prob", "n_steps",
              "per_step_costs", "per_step_source_0_costs"):
        assert k in v.metadata
    assert v.metadata["n_steps"] == len(choice)
    assert len(v.metadata["per_step_costs"]) == len(choice)


def test_per_step_agreeing_sources_stability_is_one():
    obs = CoherenceAnchoredBCVFPerStepObservable()
    v = obs.observe(_make_agreeing_sources(), [1], [3, 3, 3])
    assert v.metadata["max_step_bcvf"] == pytest.approx(0.0, abs=1e-10)
    assert v.metadata["stability"] == pytest.approx(1.0, abs=1e-10)


def test_per_step_alignment_high_when_choices_match_peak():
    """Source 0 peaks on token 3 at every position; choice = [3, 3, 3].
    Every step's P(token=3) ≈ 1, so geo_mean ≈ 1, alignment ≈ 1."""
    obs = CoherenceAnchoredBCVFPerStepObservable()
    v = obs.observe(_make_agreeing_sources(V=8, top=3), [1], [3, 3, 3])
    assert v.metadata["alignment"] > 0.9


def test_per_step_alignment_low_when_choices_diverge_from_peak():
    """Source 0 peaks on token 3; choice = [5, 5, 5] → P(5) ≈ 0 at every
    step → geo_mean ≈ 0 → alignment ≈ 0."""
    obs = CoherenceAnchoredBCVFPerStepObservable()
    v = obs.observe(_make_agreeing_sources(V=8, top=3), [1], [5, 5, 5])
    assert v.metadata["alignment"] < 1e-5


def test_per_step_empty_choice_returns_pure_stability():
    obs = CoherenceAnchoredBCVFPerStepObservable()
    v = obs.observe(_make_agreeing_sources(), [1], [])
    # Fallback: alignment = 1, scalar = stability
    assert v.metadata["n_steps"] == 0
    assert v.metadata["alignment"] == 1.0
    assert v.scalar == v.metadata["stability"]


def test_per_step_scalar_equals_stability_times_alignment():
    obs = CoherenceAnchoredBCVFPerStepObservable()
    v = obs.observe(_make_agreeing_sources(V=8, top=3), [1], [3, 3, 3])
    expected = v.metadata["stability"] * v.metadata["alignment"]
    assert v.scalar == pytest.approx(expected, abs=1e-10)


def test_per_step_advances_source_state_through_commits():
    """For K-token choice, the observable commits K-1 tokens between
    steps (one commit after each step except the last)."""
    obs = CoherenceAnchoredBCVFPerStepObservable()
    srcs = [
        MockSource(lambda p: _peaked(8, 3), L=5, V=8, initial_prefix=[1, 2])
        for _ in range(3)
    ]
    choice = [3, 3, 3]
    obs.observe(srcs, [1, 2], choice)
    # Each source started with prefix [1, 2]. After 3-token choice:
    # K-1 = 2 commits happen (after step 0 and step 1). Last step
    # doesn't commit.
    for s in srcs:
        assert list(s.committed_prefix) == [1, 2, 3, 3]


def test_per_step_integrates_with_probe_harness_isolation():
    """End-to-end via probe_observables_parallel. Each (Q, C) gets a
    fresh source triple per the requires_isolated_sources flag."""
    bench = MockBenchmark(num_questions=3)
    reports = probe_observables_parallel(
        [CoherenceAnchoredBCVFPerStepObservable()],
        bench,
        retain_datapoints=True,
    )
    r = reports["coherence_anchored_bcvf_per_step"]
    assert r.n_datapoints == 6  # 3 questions × 2 choices
    for dp in r.datapoints:
        # MockBenchmark produces 3-token choices.
        assert dp.observable_value.metadata["n_steps"] == 3
