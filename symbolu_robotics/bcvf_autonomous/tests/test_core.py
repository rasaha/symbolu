"""Tests for bcvf_autonomous.core — DESIGN.md Sections 1.3.2 and 1.3.3.

Also covers the Phase 1 acceptance-criteria timing assertion
(K=1000, H=50, M=4 anchor-mode batch cost < 50 ms).
"""

from __future__ import annotations

import time
from typing import List

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.core import (
    BCVFConfig,
    compute_bcvf_cost,
    compute_bcvf_cost_batch,
    compute_disagreement,
    compute_disagreement_acceleration,
    pseudo_huber,
    smooth_gate,
)


def _constant_trajectory(pose: np.ndarray, horizon: int) -> np.ndarray:
    return np.tile(pose.astype(np.float64), (horizon, 1))


def _default_config(**overrides) -> BCVFConfig:
    cfg = BCVFConfig(weight_matrix=np.ones(3, dtype=np.float64))
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


# --- Lemma 1 and linearity invariants ---


def test_constant_bias_zero_cost() -> None:
    horizon = 20
    traj_i = _constant_trajectory(np.array([1.0, 0.0, 0.0]), horizon)
    traj_j = _constant_trajectory(np.array([0.5, 0.0, 0.0]), horizon)
    cfg = _default_config()
    result = compute_bcvf_cost([traj_i, traj_j], cfg)
    assert result.total_cost == pytest.approx(0.0, abs=1e-10)


def test_linear_drift_zero_cost() -> None:
    horizon = 20
    ks = np.arange(horizon, dtype=np.float64)
    traj_i = np.stack([ks * 0.0, np.zeros(horizon), np.zeros(horizon)], axis=-1)
    # Linearly growing offset -> constant velocity -> zero acceleration.
    traj_j = np.stack([ks * 0.1, np.zeros(horizon), np.zeros(horizon)], axis=-1)
    cfg = _default_config()
    result = compute_bcvf_cost([traj_i, traj_j], cfg)
    assert result.total_cost == pytest.approx(0.0, abs=1e-9)


def test_accelerating_divergence_nonzero() -> None:
    horizon = 20
    ks = np.arange(horizon, dtype=np.float64)
    traj_i = np.zeros((horizon, 3), dtype=np.float64)
    traj_j = np.stack([0.05 * ks * ks, np.zeros(horizon), np.zeros(horizon)], axis=-1)
    cfg = _default_config()
    result = compute_bcvf_cost([traj_i, traj_j], cfg)
    assert result.total_cost > 0.0


# --- Gate behaviour ---


def test_gate_below_threshold() -> None:
    # Small disagreement well below T=0.1 even under quadratic growth.
    horizon = 20
    ks = np.arange(horizon, dtype=np.float64)
    # Peak disagreement at k=H-1: 0.00005 * 361 ~= 0.018 << 0.1.
    traj_i = np.zeros((horizon, 3), dtype=np.float64)
    traj_j = np.stack(
        [0.00005 * ks * ks, np.zeros(horizon), np.zeros(horizon)], axis=-1
    )
    cfg = _default_config()
    result = compute_bcvf_cost([traj_i, traj_j], cfg)
    assert result.total_cost < 1e-3


def test_gate_above_threshold() -> None:
    horizon = 20
    ks = np.arange(horizon, dtype=np.float64)
    traj_i = np.zeros((horizon, 3), dtype=np.float64)
    traj_j = np.stack(
        [0.05 * ks * ks, np.zeros(horizon), np.zeros(horizon)], axis=-1
    )
    cfg = _default_config()
    result = compute_bcvf_cost([traj_i, traj_j], cfg)
    assert result.total_cost > 0.0
    assert result.gate_activation_count > 0


# --- Pseudo-Huber properties ---


def test_huber_quadratic_near_zero() -> None:
    r = np.array([1e-3, 2e-3, 5e-3])
    delta = 0.5
    vals = pseudo_huber(r, delta)
    expected_quadratic = 0.5 * r ** 2
    assert np.allclose(vals, expected_quadratic, rtol=1e-3, atol=1e-8)


def test_huber_linear_large_r() -> None:
    delta = 0.5
    r = np.array([50.0, 100.0, 500.0])
    vals = pseudo_huber(r, delta)
    expected_linear = delta * r - delta ** 2
    assert np.allclose(vals, expected_linear, rtol=1e-2)


# --- Pairing modes ---


def _make_trajectories(num_models: int, horizon: int) -> List[np.ndarray]:
    rng = np.random.default_rng(seed=12345)
    base = rng.normal(size=(horizon, 3)) * 0.1
    trajectories = []
    for m in range(num_models):
        offset = rng.normal(size=(horizon, 3)) * 0.05
        trajectories.append((base + offset).astype(np.float64))
    return trajectories


def test_anchor_vs_all_pairs_consistent() -> None:
    trajectories = _make_trajectories(num_models=2, horizon=20)
    anchor = compute_bcvf_cost(trajectories, _default_config(use_anchor_pairing=True))
    all_pairs = compute_bcvf_cost(
        trajectories, _default_config(use_anchor_pairing=False)
    )
    assert anchor.total_cost == pytest.approx(all_pairs.total_cost, rel=1e-12, abs=1e-12)


def test_anchor_fewer_pairs() -> None:
    trajectories = _make_trajectories(num_models=4, horizon=20)
    anchor = compute_bcvf_cost(trajectories, _default_config(use_anchor_pairing=True))
    all_pairs = compute_bcvf_cost(
        trajectories, _default_config(use_anchor_pairing=False)
    )
    assert len(anchor.per_pair_costs) == 3
    assert len(all_pairs.per_pair_costs) == 6


def test_perfect_agreement_zero_cost() -> None:
    horizon = 20
    traj = np.linspace(0.0, 1.0, horizon * 3).reshape(horizon, 3).astype(np.float64)
    trajectories = [traj.copy() for _ in range(4)]
    result = compute_bcvf_cost(trajectories, _default_config())
    assert result.total_cost == pytest.approx(0.0, abs=1e-10)


def test_batch_matches_sequential() -> None:
    horizon = 20
    num_models = 4
    rng = np.random.default_rng(seed=2026)
    rollouts = []
    for _ in range(8):
        traj_set = [
            rng.normal(scale=0.2, size=(horizon, 3)).astype(np.float64)
            for _ in range(num_models)
        ]
        rollouts.append(traj_set)
    cfg = _default_config()
    batch_costs = compute_bcvf_cost_batch(rollouts, cfg)
    sequential = np.array([compute_bcvf_cost(r, cfg).total_cost for r in rollouts])
    assert np.allclose(batch_costs, sequential, rtol=1e-10, atol=1e-12)


def test_cost_positive_semidefinite() -> None:
    rng = np.random.default_rng(seed=1)
    cfg = _default_config()
    for _ in range(100):
        horizon = 20
        trajectories = [
            rng.normal(scale=0.5, size=(horizon, 3)).astype(np.float64)
            for _ in range(3)
        ]
        cost = compute_bcvf_cost(trajectories, cfg).total_cost
        assert cost >= 0.0


def test_off_by_one_alignment() -> None:
    horizon = 10
    traj_i = np.zeros((horizon, 3), dtype=np.float64)
    traj_j = np.stack(
        [
            np.linspace(0.0, 1.0, horizon),
            np.zeros(horizon),
            np.zeros(horizon),
        ],
        axis=-1,
    ).astype(np.float64)
    e = compute_disagreement(traj_i, traj_j, lever_arm=2.5)
    a = compute_disagreement_acceleration(e, dt=0.1)
    gate = smooth_gate(e[1:-1], 0.1, 200.0, np.ones(3, dtype=np.float64))
    assert a.shape[0] == horizon - 2
    assert gate.shape[0] == horizon - 2


# --- Section 1.3.3: specific numerical test cases ---


def test_case_A_stationary_constant_offset() -> None:
    horizon = 10
    traj_i = _constant_trajectory(np.array([1.0, 0.0, 0.0]), horizon)
    traj_j = _constant_trajectory(np.array([0.5, 0.0, 0.0]), horizon)
    e = compute_disagreement(traj_i, traj_j, lever_arm=2.5)
    assert np.allclose(e, np.tile([0.5, 0.0, 0.0], (horizon, 1)), atol=1e-12)
    a = compute_disagreement_acceleration(e, dt=0.1)
    assert np.allclose(a, 0.0, atol=1e-10)
    cost = compute_bcvf_cost([traj_i, traj_j], _default_config()).total_cost
    assert cost == pytest.approx(0.0, abs=1e-10)


def test_case_B_sudden_jump() -> None:
    horizon = 10
    traj_i = np.zeros((horizon, 3), dtype=np.float64)
    jump = np.zeros((horizon, 3), dtype=np.float64)
    jump[5:, 0] = 1.0
    result = compute_bcvf_cost([traj_i, jump], _default_config())
    e = compute_disagreement(traj_i, jump, lever_arm=2.5)
    a = compute_disagreement_acceleration(e, dt=0.1)
    # Second difference stencil: nonzero entries around the jump index 5.
    nonzero_indices = np.nonzero(np.linalg.norm(a, axis=-1) > 1e-9)[0]
    assert set(nonzero_indices.tolist()).issubset({3, 4, 5})
    assert result.total_cost > 0.0


def test_case_C_quadratic_divergence_scales() -> None:
    horizon = 10
    ks = np.arange(horizon, dtype=np.float64)
    traj_i = np.zeros((horizon, 3), dtype=np.float64)
    traj_j_small = np.stack(
        [0.01 * ks * ks, np.zeros(horizon), np.zeros(horizon)], axis=-1
    )
    traj_j_large = np.stack(
        [0.02 * ks * ks, np.zeros(horizon), np.zeros(horizon)], axis=-1
    )
    cfg = _default_config()
    cost_small = compute_bcvf_cost([traj_i, traj_j_small], cfg).total_cost
    cost_large = compute_bcvf_cost([traj_i, traj_j_large], cfg).total_cost
    assert cost_large >= 2.0 * cost_small
    assert cost_small > 0.0


# --- Success gate from Section 1.6 ---


def test_success_gate_monotonic_under_acceleration() -> None:
    horizon = 20
    ks = np.arange(horizon, dtype=np.float64)
    traj_i = np.zeros((horizon, 3), dtype=np.float64)
    cfg = _default_config()

    def cost_for(coeff: float) -> float:
        traj_j = np.stack(
            [coeff * ks * ks, np.zeros(horizon), np.zeros(horizon)], axis=-1
        )
        return compute_bcvf_cost([traj_i, traj_j], cfg).total_cost

    c1 = cost_for(0.02)
    c2 = cost_for(0.04)
    assert c2 >= 2.0 * c1


def test_success_gate_no_wrap_discontinuity() -> None:
    horizon = 20
    ks = np.arange(horizon, dtype=np.float64)
    # Heading sweep across +/- pi boundary.
    thetas = np.pi - 0.01 + 0.001 * ks
    traj_i = np.stack([np.zeros(horizon), np.zeros(horizon), thetas], axis=-1)
    traj_j = np.stack([np.zeros(horizon), np.zeros(horizon), np.zeros(horizon)], axis=-1)
    cfg = _default_config()
    result = compute_bcvf_cost([traj_i, traj_j], cfg)
    assert np.isfinite(result.total_cost)


# --- Timing assertion from Section 1.5 ---


def test_batch_timing_under_50ms() -> None:
    k_batch = 1000
    horizon = 50
    num_models = 4
    rng = np.random.default_rng(seed=7)
    rollouts = rng.normal(
        scale=0.5, size=(k_batch, num_models, horizon, 3)
    ).astype(np.float64)
    rollouts_list = [[rollouts[k, m] for m in range(num_models)] for k in range(k_batch)]
    cfg = _default_config()

    # Warm-up to exclude one-time NumPy overhead.
    compute_bcvf_cost_batch(rollouts_list[:4], cfg)

    start = time.perf_counter()
    costs = compute_bcvf_cost_batch(rollouts_list, cfg)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert costs.shape == (k_batch,)
    # Acceptance criterion from DESIGN.md Section 1.5.
    assert elapsed_ms < 50.0, f"batch cost took {elapsed_ms:.2f} ms (budget 50 ms)"
