"""§11 tests for the four built-in Ketu observables.

Each observable is probed on a fabricated tiny source triple with
known-target behavior. Verifies:
  - shape and polarity of the ObservableValue
  - metadata structure
  - that state is not mutated
  - handles edge cases (empty choice, identical sources, etc.)
"""

from __future__ import annotations

from typing import List

import numpy as np
import pytest

from symbolu_bcvf_llm.core import BCVFLLMConfig
from symbolu_bcvf_llm.observables.agreement import SourceAgreementObservable
from symbolu_bcvf_llm.observables.base import ObservableValue
from symbolu_bcvf_llm.observables.bcvf import (
    BCVFSourceZeroCostObservable,
    BCVFTotalCostObservable,
)
from symbolu_bcvf_llm.observables.entropy import Source0EntropyObservable
from symbolu_bcvf_llm.sources.mock import MockSource


# --------------------------------------------------------------------------- #
# Test fixtures
# --------------------------------------------------------------------------- #


def _peaked(V: int, top: int, L: int = 5, peak: float = 10.0) -> np.ndarray:
    z = np.full((L, V), -peak, dtype=np.float32)
    z[:, top] = peak
    return z


def _make_agreeing_sources(V: int = 8, L: int = 5, top: int = 3,
                           prefix=None) -> List[MockSource]:
    """Three sources that all produce the same peaked distribution."""
    return [
        MockSource(lambda p: _peaked(V, top, L), L=L, V=V,
                   initial_prefix=list(prefix or []))
        for _ in range(3)
    ]


def _make_disagreeing_sources(V: int = 8, L: int = 5,
                              prefix=None) -> List[MockSource]:
    """Three sources that each peak on a different token."""
    return [
        MockSource(lambda p: _peaked(V, 1, L), L=L, V=V,
                   initial_prefix=list(prefix or [])),
        MockSource(lambda p: _peaked(V, 2, L), L=L, V=V,
                   initial_prefix=list(prefix or [])),
        MockSource(lambda p: _peaked(V, 3, L), L=L, V=V,
                   initial_prefix=list(prefix or [])),
    ]


# --------------------------------------------------------------------------- #
# BCVFTotalCostObservable
# --------------------------------------------------------------------------- #


def test_bcvf_total_cost_returns_float():
    obs = BCVFTotalCostObservable()
    srcs = _make_agreeing_sources()
    v = obs.observe(sources=srcs, prompt_tokens=[1, 2], choice_tokens=[3])
    assert isinstance(v, ObservableValue)
    assert isinstance(v.scalar, float)


def test_bcvf_total_cost_has_per_source():
    obs = BCVFTotalCostObservable()
    srcs = _make_agreeing_sources()
    v = obs.observe(sources=srcs, prompt_tokens=[1, 2], choice_tokens=[3])
    assert v.per_source is not None
    assert v.per_source.shape == (3,)


def test_bcvf_total_cost_metadata_keys():
    obs = BCVFTotalCostObservable()
    v = obs.observe(_make_agreeing_sources(), [1], [2])
    assert "max_acceleration_norm" in v.metadata
    assert "gate_activation_count" in v.metadata
    assert "per_pair_costs" in v.metadata


def test_bcvf_total_cost_agreeing_sources_low():
    """When all three sources produce identical flat-top distributions,
    BCVF total cost should be (near-)zero."""
    obs = BCVFTotalCostObservable()
    v = obs.observe(_make_agreeing_sources(), [1], [2])
    # Constant across time → 2nd-diff = 0 → Huber = 0 → total = 0.
    assert v.scalar == pytest.approx(0.0, abs=1e-10)


def test_bcvf_total_cost_polarity():
    assert BCVFTotalCostObservable().higher_means_more_suspicious is True


def test_bcvf_total_cost_accepts_custom_config():
    cfg = BCVFLLMConfig(gate_threshold=0.5)
    obs = BCVFTotalCostObservable(bcvf_config=cfg)
    v = obs.observe(_make_agreeing_sources(), [1], [2])
    # Higher threshold → gate rarely opens → still zero on agreement.
    assert v.scalar == pytest.approx(0.0, abs=1e-10)


# --------------------------------------------------------------------------- #
# BCVFSourceZeroCostObservable
# --------------------------------------------------------------------------- #


def test_bcvf_source_zero_cost_structure():
    obs = BCVFSourceZeroCostObservable()
    v = obs.observe(_make_agreeing_sources(), [1], [2])
    assert isinstance(v.scalar, float)
    assert v.per_source is not None
    assert v.per_source.shape == (3,)
    assert "total_cost" in v.metadata
    assert "relative_to_total" in v.metadata


def test_bcvf_source_zero_cost_matches_per_source_zero():
    obs = BCVFSourceZeroCostObservable()
    # Make source 0 different to generate non-zero per-source cost.
    srcs = _make_disagreeing_sources()
    v = obs.observe(srcs, [1], [2])
    assert v.scalar == v.per_source[0]


# --------------------------------------------------------------------------- #
# Source0EntropyObservable
# --------------------------------------------------------------------------- #


def test_entropy_peaked_is_low():
    """Sharply-peaked distribution → entropy ≈ 0."""
    obs = Source0EntropyObservable()
    v = obs.observe(_make_agreeing_sources(V=8, top=3), [1], [2])
    # Peaked softmax at peak=10 is essentially one-hot → entropy ≈ 0
    assert v.scalar < 0.1


def test_entropy_uniform_is_high():
    """Uniform distribution on V → entropy = ln(V)."""
    V = 8
    def fn(prefix):
        return np.zeros((5, V), dtype=np.float32)   # softmax → uniform
    srcs = [MockSource(fn, L=5, V=V) for _ in range(3)]
    obs = Source0EntropyObservable()
    v = obs.observe(srcs, [1], [2])
    # ln(8) ≈ 2.079
    assert v.scalar == pytest.approx(np.log(V), rel=1e-3)


def test_entropy_metadata():
    obs = Source0EntropyObservable()
    v = obs.observe(_make_agreeing_sources(V=8, top=3), [1], [2])
    assert v.metadata["vocab_size"] == 8
    assert v.metadata["top1_token"] == 3
    assert 0.0 < v.metadata["top1_prob"] <= 1.0


def test_entropy_polarity():
    assert Source0EntropyObservable().higher_means_more_suspicious is True


# --------------------------------------------------------------------------- #
# SourceAgreementObservable
# --------------------------------------------------------------------------- #


def test_agreement_unanimous_returns_zero():
    """All sources agree on argmax at every l → disagreement = 0."""
    obs = SourceAgreementObservable()
    v = obs.observe(_make_agreeing_sources(), [1], [2])
    assert v.scalar == pytest.approx(0.0)
    assert v.metadata["agreement_fraction"] == pytest.approx(1.0)


def test_agreement_all_different_returns_one():
    """Every source picks a different argmax → disagreement = 1."""
    obs = SourceAgreementObservable()
    srcs = _make_disagreeing_sources()
    v = obs.observe(srcs, [1], [2])
    assert v.scalar == pytest.approx(1.0)
    assert v.metadata["agreement_fraction"] == pytest.approx(0.0)


def test_agreement_polarity():
    assert SourceAgreementObservable().higher_means_more_suspicious is True


def test_agreement_metadata():
    obs = SourceAgreementObservable()
    v = obs.observe(_make_disagreeing_sources(V=8), [1], [2])
    assert v.metadata["L"] == 5
    assert v.metadata["M"] == 3
    assert len(v.metadata["argmax_first_position"]) == 3


# --------------------------------------------------------------------------- #
# Cross-cutting properties
# --------------------------------------------------------------------------- #


def test_no_observable_mutates_sources():
    """All four observables must leave committed-prefix state unchanged."""
    observables = [
        BCVFTotalCostObservable(),
        BCVFSourceZeroCostObservable(),
        Source0EntropyObservable(),
        SourceAgreementObservable(),
    ]
    for obs in observables:
        srcs = _make_agreeing_sources(prefix=[1, 2, 3])
        before = [s.committed_prefix for s in srcs]
        obs.observe(srcs, [1], [4])
        after = [s.committed_prefix for s in srcs]
        assert before == after, (
            f"{obs.name} mutated source state: {before} vs {after}"
        )
