"""Tests for bcvf_autonomous.runner — DESIGN.md §3C.9."""

from __future__ import annotations

import json

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.core import CostOrder
from symbolu_robotics.bcvf_autonomous.predictors import FailureConfig
from symbolu_robotics.bcvf_autonomous.runner import (
    RunConfig,
    Runner,
    benchmark_planner,
    load_config,
)
from symbolu_robotics.bcvf_autonomous.simulator import Obstacle

# All runner tests use a compact config to keep tests fast.


def _quick_config() -> RunConfig:
    cfg = load_config(
        overrides={
            "mppi.rollouts": 64,
            "mppi.horizon": 20,
            "mppi.noise_std": [2.0, 0.2],
            "mppi.velocity_bounds": [0.5, 8.0],
            "environment.max_steps": 20,
        }
    )
    return cfg


# --- §3C.9.1 integration tests ---


def test_full_episode_completes() -> None:
    cfg = _quick_config()
    result = Runner(cfg).run()
    assert result.total_steps == cfg.sim.max_steps
    assert not result.collision


def test_episode_with_collision_terminates() -> None:
    cfg = load_config(
        overrides={
            "mppi.rollouts": 32,
            "mppi.horizon": 10,
            "mppi.noise_std": [0.1, 0.05],           # very little steering exploration
            "mppi.velocity_bounds": [4.0, 8.0],       # force forward motion
            "mppi.steering_bounds": [-0.05, 0.05],    # can't escape obstacle laterally
            "mppi.lambda_c": 0.0,                     # baseline, no BCVF avoidance
            "environment.max_steps": 40,
            "environment.obstacles": [{"x": 8.0, "y": 0.0, "radius": 2.0}],
            "perf.collision_weight": 0.0,             # no soft-avoid penalty
        }
    )
    result = Runner(cfg).run()
    assert result.collision, (
        f"expected baseline planner to collide; total_steps={result.total_steps}"
    )
    assert result.collision_step is not None


def test_config_loading() -> None:
    cfg = load_config()
    # default gate_threshold from default_se2.yaml post-sweep
    assert cfg.bcvf.gate_threshold == pytest.approx(0.2)
    assert cfg.bcvf.gate_beta == pytest.approx(100.0)
    assert cfg.bcvf.cost_order == CostOrder.SECOND
    assert cfg.sim.max_steps == 200
    assert cfg.sim.road.centerline.shape[1] == 2


def test_config_overrides() -> None:
    cfg = load_config(overrides={"bcvf.lambda_c": 5.0})
    assert cfg.bcvf.lambda_c == pytest.approx(5.0)
    assert cfg.bcvf.gate_threshold == pytest.approx(0.2)  # unchanged


def test_config_dot_path_nested() -> None:
    cfg = load_config(overrides={"mppi.noise_std": [2.0, 0.3]})
    assert cfg.mppi.noise_std.tolist() == [2.0, 0.3]


def test_config_cost_order_override() -> None:
    cfg = load_config(overrides={"cost_order": "ZEROTH"})
    assert cfg.bcvf.cost_order == CostOrder.ZEROTH


def test_episode_diagnostics_shapes() -> None:
    cfg = _quick_config()
    diag = Runner(cfg).diagnostics()
    T = diag.total_steps
    assert diag.ground_truth_trajectory.shape == (T, 3)
    assert diag.applied_controls.shape == (T, 2)
    assert diag.bcvf_costs.shape == (T,)
    assert diag.perf_costs.shape == (T,)
    assert diag.total_costs.shape == (T,)
    for name, traj in diag.predictor_trajectories.items():
        assert traj.shape == (T, 3)


def test_diagnostics_serializable() -> None:
    cfg = _quick_config()
    diag = Runner(cfg).diagnostics()
    blob = json.dumps(diag.to_dict())
    back = json.loads(blob)
    assert back["total_steps"] == diag.total_steps
    assert isinstance(back["ground_truth_trajectory"], list)


def test_deterministic_episodes() -> None:
    cfg = _quick_config()
    a = Runner(cfg).run()
    b = Runner(cfg).run()
    # Trajectories should match element-wise.
    a_gt = np.array(
        [[s.ground_truth.x, s.ground_truth.y, s.ground_truth.theta] for s in a.history]
    )
    b_gt = np.array(
        [[s.ground_truth.x, s.ground_truth.y, s.ground_truth.theta] for s in b.history]
    )
    assert np.allclose(a_gt, b_gt)


def test_failure_onset_timing() -> None:
    cfg = load_config(
        overrides={
            "mppi.rollouts": 32,
            "mppi.horizon": 10,
            "mppi.noise_std": [1.0, 0.1],
            "mppi.velocity_bounds": [0.5, 5.0],
            "environment.max_steps": 30,
        }
    )
    # Inject LiDAR failure at t=2.0 s (step 20 for dt=0.1).
    cfg.failures["M2"] = FailureConfig(
        active=True, onset_time=2.0, severity=1.0, ramp_duration=0.1
    )
    result = Runner(cfg).run()

    bcvf_series = np.array([s.bcvf_cost for s in result.history[1:]])
    # Before step 20 (t < 2s), BCVF should be low; after, elevated.
    pre = bcvf_series[:19]
    post = bcvf_series[19:]
    assert pre.mean() < post.mean(), (
        f"pre-onset mean {pre.mean():.3f} not less than post {post.mean():.3f}"
    )


# --- §3C.9.2 timing benchmark (fast sanity check only) ---


def test_benchmark_planner_returns_structured_stats() -> None:
    """Structural check: benchmark_planner populates the expected stats.

    Wall-clock budgets (DESIGN §3C.9.2: p99 < 5ms reduced, < 20ms full)
    are reserved for the slow-marked tests below. Option A rollouts are a
    Python loop over K; Option B (batch bicycle) is the escalation path
    when the slow tests fail their budgets on a given host.
    """
    cfg = load_config(
        overrides={"mppi.rollouts": 16, "mppi.horizon": 10}
    )
    stats = benchmark_planner(cfg, num_cycles=5)
    for key in ("mean_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms", "within_budget"):
        assert key in stats, f"missing stat: {key}"
    assert stats["mean_ms"] > 0.0
    assert stats["p99_ms"] >= stats["p50_ms"]


@pytest.mark.slow
def test_planner_timing_reduced_budget() -> None:
    """DESIGN §3C.9.2 fast sanity (K=200, H=30): p99 < 5 ms."""
    cfg = load_config(overrides={"mppi.rollouts": 200, "mppi.horizon": 30})
    stats = benchmark_planner(cfg, num_cycles=20)
    assert stats["p99_ms"] < 5.0, stats


@pytest.mark.slow
def test_planner_timing_budget() -> None:
    """DESIGN §3C.9.2 full budget (K=1000, H=50): p99 < 20 ms."""
    cfg = load_config()
    stats = benchmark_planner(cfg, num_cycles=30)
    assert stats["p99_ms"] < 20.0, stats
