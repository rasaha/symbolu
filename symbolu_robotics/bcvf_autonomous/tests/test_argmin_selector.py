"""Integration tests for the non-MPPI reference adapter (§6.3).

Verifies that the TrustWeightComputer works correctly when consumed
by a planner that is NOT MPPI — i.e., the §6.3 extraction is
genuinely planner-agnostic. These tests replay three invariants that
the §6.3 acceptance criteria require:

(a) Planner works with BCVF disabled (lambda_c=0) — adapter is not
    MPPI-coupled through the trust computer.
(b) Trust weights are a valid simplex (non-negative, rows sum to 1).
(c) Lemma 1 invariance preserved: constant and linear-drift
    predictor inputs produce uniform weights (trust computer returns
    ~zero per_source_cost, softmin outputs uniform simplex).
"""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.core import BCVFConfig, CostOrder
from symbolu_robotics.bcvf_autonomous.integrations.argmin_selector import (
    ArgminSelectorPlanner,
)
from symbolu_robotics.bcvf_autonomous.mppi_planner import (
    MPPIConfig,
    PerfCostConfig,
)
from symbolu_robotics.bcvf_autonomous.predictors import create_predictor_set
from symbolu_robotics.bcvf_autonomous.simulator import make_straight_road


def _small_mppi(**overrides) -> MPPIConfig:
    cfg = MPPIConfig(
        num_rollouts=32,
        horizon=20,
        dt=0.1,
        temperature=5.0,
        noise_std=np.array([0.5, 0.1]),
        lambda_c=1.0,
        bcvf_config=BCVFConfig(
            gate_threshold=0.2,
            gate_beta=100.0,
            huber_delta=0.5,
            lever_arm=2.5,
            weight_matrix=np.ones(3),
            dt=0.1,
        ),
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _make_planner(mppi_cfg=None):
    predictors = create_predictor_set(seed=0)
    road = make_straight_road(length=200.0)
    planner = ArgminSelectorPlanner(
        mppi_cfg or _small_mppi(),
        PerfCostConfig(),
        predictors,
        road,
        [],
    )
    planner.set_seed(42)
    return planner


# --- (a) planner works with BCVF disabled ---


def test_argmin_runs_with_bcvf_disabled() -> None:
    """lambda_c=0 → trust computer returns uniform weights → adapter
    still produces a valid control output."""
    planner = _make_planner(mppi_cfg=_small_mppi(lambda_c=0.0))
    result = planner.plan()
    assert result.first_control.shape == (2,)
    assert np.isfinite(result.first_control).all()
    assert result.bcvf_cost == 0.0  # kernel not invoked at lambda_c=0
    assert 0 <= result.selected_rollout_idx < 32


def test_argmin_runs_with_bcvf_enabled() -> None:
    """lambda_c=1 → trust computer runs full pipeline → adapter still
    produces a valid control output."""
    planner = _make_planner()
    result = planner.plan()
    assert result.first_control.shape == (2,)
    assert np.isfinite(result.first_control).all()
    assert result.bcvf_cost >= 0.0


# --- (b) weights invariant preserved via the full pipeline ---


def test_argmin_trust_weights_valid_simplex() -> None:
    """After a plan step, the underlying trust computer's last output
    must satisfy rows-sum-to-1 (within fp tolerance) and non-negativity.
    We inspect via a second compute() call with a known input."""
    planner = _make_planner()
    planner.plan()  # prime the EMA
    # Directly exercise the computer with the same inputs a plan step
    # would produce: uniform trajectories across K, M.
    rng = np.random.default_rng(7)
    trajs = rng.normal(scale=0.3, size=(8, 4, 20, 3)).astype(np.float64)
    result = planner._trust_computer.compute(trajs)
    assert result.weights.shape == (8, 4)
    np.testing.assert_allclose(result.weights.sum(axis=1), 1.0, atol=1e-10)
    assert (result.weights >= -1e-12).all()


# --- (c) Lemma 1 preserved under the adapter ---


def test_argmin_lemma1_constant_bias_uniform_weights() -> None:
    """Constant bias between predictors → per_source_cost ≈ 0 →
    trust weights uniform (regardless of which planner consumes them)."""
    planner = _make_planner()
    # Synthesize trajectories with a constant offset between predictors.
    K, M, H = 4, 4, 20
    base = np.zeros((K, H, 3), dtype=np.float64)
    trajs = np.zeros((K, M, H, 3), dtype=np.float64)
    for m in range(M):
        trajs[:, m, :, :] = base + np.array([m * 0.5, 0.0, 0.0])
    result = planner._trust_computer.compute(trajs)
    # Under constant bias, SECOND-order BCVF is exactly zero, so the
    # softmin degenerates to uniform.
    np.testing.assert_allclose(
        result.weights, np.full((K, M), 1.0 / M), atol=1e-10,
    )


def test_argmin_lemma1_linear_drift_uniform_weights() -> None:
    """Linear drift between predictors → per_source_cost ≈ 0 →
    trust weights uniform."""
    planner = _make_planner()
    K, M, H = 4, 4, 20
    ks = np.arange(H, dtype=np.float64)
    trajs = np.zeros((K, M, H, 3), dtype=np.float64)
    for m in range(M):
        # Each predictor drifts at its own constant rate.
        trajs[:, m, :, 0] = m * 0.1 * ks  # linear in time, constant velocity
    result = planner._trust_computer.compute(trajs)
    np.testing.assert_allclose(
        result.weights, np.full((K, M), 1.0 / M), atol=1e-10,
    )


# --- end-to-end: adapter works with the autonomy-validated V1 config ---


def test_argmin_with_v1_config() -> None:
    """Full V1 consumer pattern (EMA + deadband + non-anchor) works
    through the non-MPPI adapter."""
    mppi_cfg = MPPIConfig(
        num_rollouts=32,
        horizon=20,
        dt=0.1,
        temperature=5.0,
        noise_std=np.array([0.5, 0.1]),
        lambda_c=1.0,
        bcvf_config=BCVFConfig(
            gate_threshold=0.05,
            gate_beta=400.0,
            huber_delta=0.5,
            lever_arm=2.5,
            weight_matrix=np.ones(3),
            use_anchor_pairing=False,
            dt=0.1,
            cost_order=CostOrder.SECOND,
        ),
    )
    planner = ArgminSelectorPlanner(
        mppi_cfg,
        PerfCostConfig(),
        create_predictor_set(seed=0),
        make_straight_road(length=200.0),
        [],
    )
    planner.set_seed(42)
    planner.set_ema_alpha(0.05)
    planner.set_deadband_k_sigma(2.0)
    for _ in range(5):
        result = planner.plan()
        assert np.isfinite(result.first_control).all()


def test_argmin_reset_clears_trust_state() -> None:
    """planner.reset() must clear the underlying trust-computer state."""
    planner = _make_planner()
    planner.set_ema_alpha(0.05)
    planner.plan()  # initialize EMA
    assert planner._trust_computer._ema_mean is not None
    planner.reset()
    assert planner._trust_computer._ema_mean is None
