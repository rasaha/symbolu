"""§2.8.11–§2.8.12: scalar + batched entry point tests."""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_bcvf_llm.core import (
    BCVFLLMConfig,
    BCVFLLMResult,
    compute_bcvf_cost,
    compute_bcvf_cost_batch,
)


def _accelerating_source(L=5, V=10, eta=None, seed=42):
    rng = np.random.default_rng(seed=seed)
    if eta is None:
        eta = rng.random(size=(V,)) + 0.5
    ls = np.arange(L, dtype=np.float64).reshape(L, 1)
    return 0.5 * eta * (ls ** 2)


def _flat_source(L=5, V=10, seed=42):
    rng = np.random.default_rng(seed=seed)
    return np.broadcast_to(rng.random(size=(V,)), (L, V)).astype(np.float64).copy()


def test_bcvflllmresult_fields():
    cfg = BCVFLLMConfig()
    sources = [_flat_source(seed=s) for s in (1, 2, 3)]
    r = compute_bcvf_cost(sources, cfg)
    assert isinstance(r, BCVFLLMResult)
    assert isinstance(r.total_cost, float)
    assert isinstance(r.per_pair_costs, dict)
    assert isinstance(r.per_source_costs, dict)
    assert isinstance(r.max_acceleration_norm, float)
    assert isinstance(r.gate_activation_count, int)


def test_compute_bcvf_cost_scalar_shape_validation():
    cfg = BCVFLLMConfig()
    # M < 2
    with pytest.raises(ValueError):
        compute_bcvf_cost([np.zeros((5, 10))], cfg)
    # L < 3
    with pytest.raises(ValueError):
        compute_bcvf_cost(
            [np.zeros((2, 10)), np.zeros((2, 10)), np.zeros((2, 10))], cfg
        )
    # vocab mismatch
    with pytest.raises(ValueError):
        compute_bcvf_cost(
            [np.zeros((5, 10)), np.zeros((5, 20)), np.zeros((5, 10))], cfg
        )
    # ndim != 2
    with pytest.raises(ValueError):
        compute_bcvf_cost(
            [np.zeros((5, 10, 2)), np.zeros((5, 10, 2)), np.zeros((5, 10, 2))],
            cfg,
        )
    # lookahead mismatch
    with pytest.raises(ValueError):
        compute_bcvf_cost(
            [np.zeros((5, 10)), np.zeros((6, 10)), np.zeros((5, 10))], cfg
        )


def test_compute_bcvf_cost_scalar_nan_guard():
    cfg = BCVFLLMConfig()
    bad = _flat_source()
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        compute_bcvf_cost([bad, _flat_source(seed=2), _flat_source(seed=3)], cfg)


def test_compute_bcvf_cost_scalar_m3_all_pairs_enumeration():
    cfg = BCVFLLMConfig()
    r = compute_bcvf_cost(
        [_flat_source(seed=s) for s in (1, 2, 3)], cfg
    )
    assert set(r.per_pair_costs.keys()) == {(1, 0), (2, 0), (2, 1)}


def test_compute_bcvf_cost_scalar_per_source_sums_to_double_total():
    cfg = BCVFLLMConfig()
    sources = [_accelerating_source(eta=np.linspace(0.3, 0.7, 10), seed=i)
               for i in (1, 2, 3)]
    # Make sources slightly different so pair costs are non-zero.
    sources[1] = sources[1] * 0.7
    sources[2] = sources[2] * 1.3
    r = compute_bcvf_cost(sources, cfg)
    total_from_per_source = sum(r.per_source_costs.values())
    assert total_from_per_source == pytest.approx(
        2.0 * r.total_cost, rel=0, abs=1e-10
    )


def test_compute_bcvf_cost_scalar_outlier_discrimination_2_to_1():
    cfg = BCVFLLMConfig()
    L, V = 5, 20
    eta = np.linspace(0.5, 1.0, V)
    # Source 0 is the outlier with quadratic acceleration; sources 1 and 2
    # are identical flat sequences.
    outlier = _accelerating_source(L=L, V=V, eta=eta)
    flat = np.zeros((L, V), dtype=np.float64)
    r = compute_bcvf_cost([outlier, flat, flat.copy()], cfg)
    s0 = r.per_source_costs[0]
    s1 = r.per_source_costs[1]
    s2 = r.per_source_costs[2]
    assert s0 > 0
    ratio_1 = s0 / s1
    ratio_2 = s0 / s2
    assert 1.8 <= ratio_1 <= 2.2
    assert 1.8 <= ratio_2 <= 2.2


def test_compute_bcvf_cost_scalar_eos_valid_masks_propagated():
    cfg = BCVFLLMConfig()
    L, V = 5, 10
    outlier = _accelerating_source(L=L, V=V, eta=np.linspace(0.5, 1.0, V))
    flat = np.zeros((L, V), dtype=np.float64)
    # Source 0 truncates at l=1: valid = [T, T, F, F, F]
    # Sources 1 and 2 fully valid.
    vm0 = np.array([True, True, False, False, False], dtype=bool)
    vm12 = np.ones(L, dtype=bool)
    r = compute_bcvf_cost([outlier, flat, flat.copy()], cfg,
                          valid_masks=[vm0, vm12, vm12])
    # All stencil centers l* ∈ {1,2,3}. For pair (1,0):
    # mi[:-2] & mi[1:-1] & mi[2:] = [T,T,F]&[T,F,F]&[F,F,F] = [F,F,F].
    # Same for pair (2,0). Pair (2,1) is fully valid but sources 1==2 ⇒ cost=0.
    assert r.per_pair_costs[(1, 0)] == pytest.approx(0.0, abs=1e-12)
    assert r.per_pair_costs[(2, 0)] == pytest.approx(0.0, abs=1e-12)
    assert r.per_pair_costs[(2, 1)] == pytest.approx(0.0, abs=1e-12)


def test_compute_bcvf_cost_batch_matches_scalar_elementwise():
    cfg = BCVFLLMConfig()
    T, M, L, V = 3, 3, 5, 10
    rng = np.random.default_rng(seed=42)
    batch = rng.random(size=(T, M, L, V))
    total, _ = compute_bcvf_cost_batch(batch, cfg, return_per_source=True)
    for t in range(T):
        sources = [batch[t, m, :, :] for m in range(M)]
        r = compute_bcvf_cost(sources, cfg)
        assert total[t] == pytest.approx(r.total_cost, rel=0, abs=1e-10)


def test_compute_bcvf_cost_batch_per_source_shape():
    cfg = BCVFLLMConfig()
    T, M, L, V = 4, 3, 5, 8
    rng = np.random.default_rng(seed=42)
    batch = rng.random(size=(T, M, L, V))
    total, per_source = compute_bcvf_cost_batch(
        batch, cfg, return_per_source=True
    )
    assert total.shape == (T,)
    assert per_source.shape == (T, M)


def test_compute_bcvf_cost_batch_valid_masks_propagate():
    cfg = BCVFLLMConfig()
    T, M, L, V = 2, 3, 5, 6
    rng = np.random.default_rng(seed=42)
    batch = rng.random(size=(T, M, L, V))
    # t=0: source 0 truncates at l=1; t=1: all valid.
    vm = np.ones((T, M, L), dtype=bool)
    vm[0, 0, 2:] = False
    total_masked, _ = compute_bcvf_cost_batch(
        batch, cfg, valid_masks_batch=vm, return_per_source=True
    )
    # Compare to scalar with matching valid_masks lists.
    sources_t0 = [batch[0, m, :, :] for m in range(M)]
    masks_t0 = [vm[0, m, :] for m in range(M)]
    r0 = compute_bcvf_cost(sources_t0, cfg, valid_masks=masks_t0)
    assert total_masked[0] == pytest.approx(r0.total_cost, rel=0, abs=1e-10)

    sources_t1 = [batch[1, m, :, :] for m in range(M)]
    r1 = compute_bcvf_cost(sources_t1, cfg)
    assert total_masked[1] == pytest.approx(r1.total_cost, rel=0, abs=1e-10)
