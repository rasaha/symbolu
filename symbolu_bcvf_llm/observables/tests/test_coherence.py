"""Tests for CoherenceAnchoredBCVFObservable — stability × alignment."""

from __future__ import annotations

from typing import List

import numpy as np
import pytest

from symbolu_bcvf_llm.observables.base import ObservableValue
from symbolu_bcvf_llm.observables.coherence import (
    CoherenceAnchoredBCVFObservable,
)
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
