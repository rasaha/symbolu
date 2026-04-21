"""§2.8.9–§2.8.10: pair-level tests for _enumerate_pairs and _pair_cost."""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_bcvf_llm.core import (
    BCVFLLMConfig,
    CostOrder,
    _enumerate_pairs,
    _pair_cost,
)


def test_enumerate_pairs_all_pairs_m3():
    assert _enumerate_pairs(3, False, 0) == [(1, 0), (2, 0), (2, 1)]


def test_enumerate_pairs_anchor_m3():
    assert _enumerate_pairs(3, True, 0) == [(1, 0), (2, 0)]


def test_enumerate_pairs_m2_anchor_equals_all_pairs():
    assert _enumerate_pairs(2, True, 0) == _enumerate_pairs(2, False, 0) == [(1, 0)]


def test_enumerate_pairs_m3_all_sources_covered_twice():
    pairs = _enumerate_pairs(3, False, 0)
    counts = {s: 0 for s in range(3)}
    for (i, j) in pairs:
        counts[i] += 1
        counts[j] += 1
    assert all(c == 2 for c in counts.values())


def _accelerating_pair(L=5, V=10, seed=42):
    rng = np.random.default_rng(seed=seed)
    eta = rng.random(size=(V,)) + 0.5
    ls = np.arange(L, dtype=np.float64).reshape(L, 1)
    p_i = 0.5 * eta * (ls ** 2)
    p_j = np.zeros((L, V), dtype=np.float64)
    return p_i, p_j


def test_pair_cost_no_mask_matches_unmasked_sum():
    cfg = BCVFLLMConfig()
    p_i, p_j = _accelerating_pair()
    cost_none, _, _ = _pair_cost(p_i, p_j, cfg, valid_mask=None)
    mask = np.ones(p_i.shape[0] - 2, dtype=bool)
    cost_ones, _, _ = _pair_cost(p_i, p_j, cfg, valid_mask=mask)
    assert cost_none == pytest.approx(cost_ones, rel=0, abs=1e-12)


def test_pair_cost_all_invalid_returns_zero():
    cfg = BCVFLLMConfig()
    p_i, p_j = _accelerating_pair()
    mask = np.zeros(p_i.shape[0] - 2, dtype=bool)
    cost, _, acts = _pair_cost(p_i, p_j, cfg, valid_mask=mask)
    assert cost == 0.0
    assert acts == 0


def test_pair_cost_constant_bias_zero():
    cfg = BCVFLLMConfig()
    L, V = 5, 10
    rng = np.random.default_rng(seed=42)
    base = rng.random(size=(L, V))
    alpha = rng.random(size=(V,))
    p_i = base + alpha
    p_j = base
    cost, _, _ = _pair_cost(p_i, p_j, cfg, valid_mask=None)
    assert cost == pytest.approx(0.0, abs=1e-10)


def test_pair_cost_linear_drift_zero():
    cfg = BCVFLLMConfig()
    L, V = 5, 10
    rng = np.random.default_rng(seed=42)
    base = rng.random(size=(L, V))
    alpha = rng.random(size=(V,))
    gamma = rng.random(size=(V,))
    ls = np.arange(L, dtype=np.float64).reshape(L, 1)
    # e = p_i - p_j = alpha + gamma*l
    p_i = base + alpha + gamma * ls
    p_j = base
    cost, _, _ = _pair_cost(p_i, p_j, cfg, valid_mask=None)
    assert cost < 1e-10


def test_pair_cost_quadratic_positive():
    cfg = BCVFLLMConfig()
    p_i, p_j = _accelerating_pair()
    cost, _, acts = _pair_cost(p_i, p_j, cfg, valid_mask=None)
    assert cost > 0.0
    assert acts > 0


def test_pair_cost_eos_single_source_truncation():
    cfg = BCVFLLMConfig()
    # SECOND order with L=5 ⇒ stencil centers l* ∈ [1, 2, 3].
    # Source i truncates at l=1 (valid = [T, T, F, F, F]).
    # Stencil mask requires i[l-1] & i[l] & i[l+1] for each l*.
    # Here _pair_cost takes a (L-2,) stencil mask directly.
    p_i, p_j = _accelerating_pair()
    stencil_mask = np.array([False, False, False], dtype=bool)
    cost, _, acts = _pair_cost(p_i, p_j, cfg, valid_mask=stencil_mask)
    assert cost == 0.0
    assert acts == 0
    # Non-truncated sanity: full stencil mask reproduces unmasked behavior
    full_mask = np.ones(3, dtype=bool)
    cost2, _, _ = _pair_cost(p_i, p_j, cfg, valid_mask=full_mask)
    cost_free, _, _ = _pair_cost(p_i, p_j, cfg, valid_mask=None)
    assert cost2 == pytest.approx(cost_free, abs=1e-12)


def test_pair_cost_max_signal_unmasked():
    cfg = BCVFLLMConfig()
    p_i, p_j = _accelerating_pair()
    mask_zero = np.zeros(3, dtype=bool)
    _, max_signal_masked, _ = _pair_cost(p_i, p_j, cfg, valid_mask=mask_zero)
    _, max_signal_free, _ = _pair_cost(p_i, p_j, cfg, valid_mask=None)
    assert max_signal_masked == pytest.approx(max_signal_free, abs=1e-12)
    assert max_signal_free > 0.0


def test_pair_cost_activations_counts_valid_only():
    cfg = BCVFLLMConfig()
    p_i, p_j = _accelerating_pair()
    # All positions valid ⇒ activations > 0 for accelerating input.
    _, _, acts_full = _pair_cost(
        p_i, p_j, cfg, valid_mask=np.ones(3, dtype=bool)
    )
    # All positions invalid ⇒ activations == 0 regardless of gate.
    _, _, acts_empty = _pair_cost(
        p_i, p_j, cfg, valid_mask=np.zeros(3, dtype=bool)
    )
    assert acts_full > 0
    assert acts_empty == 0
