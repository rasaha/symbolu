"""Tests for per-step trust diagnostics (TrustShapedEpisodeRecord)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous import (
    BCVFConfig,
    RolloutAggregation,
    TrustDiagnosticsRecorder,
    TrustShapedEpisodeRecord,
    TrustStepRecord,
)
from symbolu_robotics.bcvf_autonomous.trust import TrustWeightResult


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #


def _make_result(
    K: int = 5, M: int = 4, with_ema: bool = False
) -> TrustWeightResult:
    rng = np.random.default_rng(0)
    weights = rng.dirichlet(np.ones(M), size=K)
    per_pred_cost = rng.uniform(0.1, 1.0, size=(K, M))
    bcvf_total = per_pred_cost.sum(axis=1) * 0.5
    return TrustWeightResult(
        weights=weights,
        bcvf_total=bcvf_total,
        per_pred_cost=per_pred_cost,
        ema_mean=(per_pred_cost.mean(axis=0) if with_ema else None),
        ema_std=(per_pred_cost.std(axis=0) if with_ema else None),
        deadband_active_count=0,
        is_excluded=None,
    )


# --------------------------------------------------------------------------- #
# TrustDiagnosticsRecorder
# --------------------------------------------------------------------------- #


def test_recorder_mean_aggregation_shape():
    rec = TrustDiagnosticsRecorder(M=4)
    for _ in range(3):
        rec.record(_make_result(K=5, M=4))
    record = rec.finalize()
    assert isinstance(record, TrustShapedEpisodeRecord)
    assert record.n_steps == 3
    assert record.M == 4
    assert record.per_step_weights.shape == (3, 4)
    assert record.per_step_costs.shape == (3, 4)
    assert record.per_step_bcvf_total.shape == (3,)


def test_recorder_mean_matches_axis_zero_mean():
    rec = TrustDiagnosticsRecorder(M=4, aggregation=RolloutAggregation.MEAN)
    result = _make_result(K=5, M=4)
    record = rec.record(result)
    np.testing.assert_allclose(
        record.weights, result.weights.mean(axis=0), atol=1e-12
    )
    np.testing.assert_allclose(
        record.per_predictor_cost, result.per_pred_cost.mean(axis=0), atol=1e-12
    )


def test_recorder_argmin_total_picks_low_cost_rollout():
    rec = TrustDiagnosticsRecorder(
        M=4, aggregation=RolloutAggregation.ARGMIN_TOTAL
    )
    weights = np.array(
        [[0.25, 0.25, 0.25, 0.25],
         [1.00, 0.00, 0.00, 0.00],
         [0.50, 0.50, 0.00, 0.00]]
    )
    per_pred = np.array(
        [[1.0, 1.0, 1.0, 1.0],   # total 4.0
         [0.1, 0.1, 0.1, 0.1],   # total 0.4 — minimum
         [0.5, 0.5, 0.5, 0.5]]   # total 2.0
    )
    result = TrustWeightResult(
        weights=weights,
        bcvf_total=per_pred.sum(axis=1),
        per_pred_cost=per_pred,
        ema_mean=None,
        ema_std=None,
        deadband_active_count=0,
        is_excluded=None,
    )
    record = rec.record(result)
    np.testing.assert_allclose(record.weights, weights[1])
    np.testing.assert_allclose(record.per_predictor_cost, per_pred[1])


def test_recorder_residual_only_when_ema_present():
    rec = TrustDiagnosticsRecorder(M=4)
    no_ema = _make_result(M=4, with_ema=False)
    record = rec.record(no_ema)
    assert record.residual is None

    rec2 = TrustDiagnosticsRecorder(M=4)
    with_ema = _make_result(M=4, with_ema=True)
    record2 = rec2.record(with_ema)
    assert record2.residual is not None
    np.testing.assert_allclose(
        record2.residual,
        with_ema.per_pred_cost.mean(axis=0) - with_ema.ema_mean,
        atol=1e-12,
    )


def test_recorder_reset_clears_state():
    rec = TrustDiagnosticsRecorder(M=4)
    rec.record(_make_result())
    rec.record(_make_result())
    assert rec.n_steps == 2
    rec.reset()
    assert rec.n_steps == 0
    record = rec.finalize()
    assert record.n_steps == 0
    assert record.per_step_weights.shape == (0, 4)


def test_recorder_finalize_zero_steps():
    rec = TrustDiagnosticsRecorder(M=3)
    record = rec.finalize()
    assert record.n_steps == 0
    assert record.per_step_weights.shape == (0, 3)
    assert record.per_step_bcvf_total.shape == (0,)


def test_recorder_validates_weight_shape():
    rec = TrustDiagnosticsRecorder(M=4)
    bad = TrustWeightResult(
        weights=np.zeros((5, 3)),
        bcvf_total=np.zeros(5),
        per_pred_cost=np.zeros((5, 3)),
        ema_mean=None,
        ema_std=None,
        deadband_active_count=0,
        is_excluded=None,
    )
    with pytest.raises(ValueError):
        rec.record(bad)


# --------------------------------------------------------------------------- #
# Exclusion / deadband recording
# --------------------------------------------------------------------------- #


def test_recorder_captures_exclusion_state():
    rec = TrustDiagnosticsRecorder(M=4)
    excluded = np.array([False, True, False, False])
    result = TrustWeightResult(
        weights=np.full((3, 4), 0.25),
        bcvf_total=np.zeros(3),
        per_pred_cost=np.zeros((3, 4)),
        ema_mean=None,
        ema_std=None,
        deadband_active_count=0,
        is_excluded=excluded,
    )
    record = rec.record(result)
    assert record.is_excluded is not None
    np.testing.assert_array_equal(record.is_excluded, excluded)


def test_recorder_marks_deadband_fired_when_majority_in_deadband():
    rec = TrustDiagnosticsRecorder(M=4)
    K = 10
    # 6 of 10 in deadband ⇒ majority ⇒ fired.
    result = TrustWeightResult(
        weights=np.full((K, 4), 0.25),
        bcvf_total=np.zeros(K),
        per_pred_cost=np.zeros((K, 4)),
        ema_mean=None,
        ema_std=None,
        deadband_active_count=6,
        is_excluded=None,
    )
    record = rec.record(result)
    assert record.deadband_active_count == 6
    assert record.deadband_fired is True


# --------------------------------------------------------------------------- #
# Episode record serialization
# --------------------------------------------------------------------------- #


def test_episode_record_to_dict_round_trips_json():
    rec = TrustDiagnosticsRecorder(M=4)
    for _ in range(3):
        rec.record(_make_result(with_ema=True))
    record = rec.finalize()
    payload = record.to_dict()
    encoded = json.dumps(payload)
    decoded = json.loads(encoded)
    assert decoded["n_steps"] == 3
    assert decoded["M"] == 4
    assert len(decoded["per_step_weights"]) == 3
    assert len(decoded["per_step_weights"][0]) == 4


# --------------------------------------------------------------------------- #
# Integration with MPPIPlanner
# --------------------------------------------------------------------------- #


def test_planner_diagnostics_records_per_tick():
    """Smoke test: enable diagnostics on the planner, run a few plan() calls,
    confirm the episode record stacks per tick."""
    from symbolu_robotics.bcvf_autonomous import (
        MPPIConfig,
        MPPIPlanner,
        PerfCostConfig,
        create_predictor_set,
        make_straight_road,
    )

    predictors = create_predictor_set(seed=0)
    road = make_straight_road(length=200.0)
    mppi = MPPIConfig(num_rollouts=64, horizon=10)
    planner = MPPIPlanner(mppi, PerfCostConfig(), predictors, road, [])
    planner.set_seed(0)
    planner.set_trust_diagnostics_enabled(True)

    for _ in range(3):
        planner.plan()

    record = planner.get_trust_diagnostics()
    assert record is not None
    assert record.n_steps == 3
    assert record.M == len(predictors)
    assert record.per_step_weights.shape == (3, len(predictors))


def test_planner_diagnostics_disabled_returns_none():
    from symbolu_robotics.bcvf_autonomous import (
        MPPIConfig,
        MPPIPlanner,
        PerfCostConfig,
        create_predictor_set,
        make_straight_road,
    )

    predictors = create_predictor_set(seed=0)
    road = make_straight_road(length=200.0)
    planner = MPPIPlanner(
        MPPIConfig(num_rollouts=16, horizon=8),
        PerfCostConfig(),
        predictors,
        road,
        [],
    )
    assert planner.get_trust_diagnostics() is None


# --------------------------------------------------------------------------- #
# Pre-update EMA exact-residual tests
# --------------------------------------------------------------------------- #


def test_pre_update_ema_residual_is_exact():
    """The recorder's residual must equal cost - pre_update_ema, the
    value the trust shaper used to drive the deadband / softmin.
    Before the fix the recorder used the post-update EMA, which is
    off by one ema_alpha step."""
    from symbolu_robotics.bcvf_autonomous import BCVFConfig
    from symbolu_robotics.bcvf_autonomous.trust import TrustWeightComputer

    bcvf_config = BCVFConfig(lambda_c=1.0)
    computer = TrustWeightComputer(bcvf_config)
    computer.set_ema_alpha(0.1)
    rec = TrustDiagnosticsRecorder(M=3)

    H = 10
    K = 4
    ks = np.arange(H, dtype=np.float64)

    def make_trajs(accel: float) -> np.ndarray:
        base = np.zeros((H, 3), dtype=np.float64)
        base[:, 0] = ks * 0.5
        trajs = np.broadcast_to(base[None, None, :, :], (K, 3, H, 3)).copy()
        trajs[:, 1, :, 1] += 0.5 * accel * ks * ks
        return trajs

    # Two ticks with *different* per-predictor costs — required for the
    # EMA to actually move between snapshots. With identical trajectories
    # tick-to-tick the cold-start EMA pins to the first observation and
    # subsequent updates are no-ops, leaving pre-update == post-update.
    accels = [0.05, 0.20]
    for tick, accel in enumerate(accels):
        result = computer.compute(make_trajs(accel))
        record = rec.record(result)
        if tick > 0:
            assert result.ema_mean_pre_update is not None
            expected_residual = (
                result.per_pred_cost.mean(axis=0)
                - result.ema_mean_pre_update
            )
            np.testing.assert_allclose(
                record.residual, expected_residual, atol=1e-12
            )
            # Confirm post-update EMA differs from pre-update.
            assert not np.allclose(
                result.ema_mean, result.ema_mean_pre_update
            )


# --------------------------------------------------------------------------- #
# End-to-end Runner integration with JSON dump
# --------------------------------------------------------------------------- #


def test_runner_emits_trust_diagnostics_json(tmp_path):
    """Full Runner.run() with trust_diagnostics_path set must produce
    a JSON artifact whose shape matches the in-memory record."""
    import json
    from symbolu_robotics.bcvf_autonomous import (
        BCVFConfig,
        MPPIConfig,
        PerfCostConfig,
        Runner,
        SimConfig,
    )
    from symbolu_robotics.bcvf_autonomous.runner import RunConfig
    from symbolu_robotics.bcvf_autonomous.simulator import (
        make_straight_road,
    )

    diag_path = tmp_path / "trust_diag.json"
    cfg = RunConfig(
        sim=SimConfig(
            dt=0.1,
            max_steps=8,
            road=make_straight_road(length=100.0),
            obstacles=[],
            seed=11,
        ),
        mppi=MPPIConfig(num_rollouts=64, horizon=10, dt=0.1),
        perf=PerfCostConfig(),
        bcvf=BCVFConfig(lambda_c=1.0, dt=0.1),
        seed=11,
        ema_alpha=0.1,
        trust_diagnostics_enabled=True,
        trust_diagnostics_path=str(diag_path),
        trust_diagnostics_aggregation="mean",
    )

    runner = Runner(cfg)
    result = runner.run()
    assert result.total_steps > 0

    # Compare in-memory record to JSON-on-disk record.
    in_memory = runner.trust_diagnostics()
    assert in_memory is not None
    assert in_memory.n_steps > 0

    assert diag_path.exists()
    with open(diag_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    assert payload["seed"] == 11
    diag = payload["diagnostics"]
    assert diag["n_steps"] == in_memory.n_steps
    assert diag["M"] == in_memory.M
    assert len(diag["per_step_weights"]) == in_memory.n_steps
    assert len(diag["per_step_weights"][0]) == in_memory.M
    # Per-step rows sum to 1 (trust weights normalize).
    for row in diag["per_step_weights"]:
        assert abs(sum(row) - 1.0) < 1e-9


def test_runner_diagnostics_aggregation_argmin_total(tmp_path):
    """Argmin-total aggregation must produce a record across a real
    Runner episode, not just synthetic TrustWeightResult fixtures."""
    from symbolu_robotics.bcvf_autonomous import (
        BCVFConfig,
        MPPIConfig,
        PerfCostConfig,
        Runner,
        SimConfig,
    )
    from symbolu_robotics.bcvf_autonomous.runner import RunConfig
    from symbolu_robotics.bcvf_autonomous.simulator import (
        make_straight_road,
    )

    cfg = RunConfig(
        sim=SimConfig(
            dt=0.1, max_steps=6,
            road=make_straight_road(length=100.0),
            obstacles=[], seed=3,
        ),
        mppi=MPPIConfig(num_rollouts=32, horizon=8, dt=0.1),
        perf=PerfCostConfig(),
        bcvf=BCVFConfig(lambda_c=1.0, dt=0.1),
        seed=3,
        trust_diagnostics_enabled=True,
        trust_diagnostics_aggregation="argmin_total",
    )
    runner = Runner(cfg)
    runner.run()
    diag = runner.trust_diagnostics()
    assert diag is not None
    assert diag.n_steps > 0
    assert diag.aggregation.value == "argmin_total"


def test_runner_rejects_unknown_aggregation():
    from symbolu_robotics.bcvf_autonomous import (
        BCVFConfig,
        MPPIConfig,
        PerfCostConfig,
        Runner,
        SimConfig,
    )
    from symbolu_robotics.bcvf_autonomous.runner import RunConfig
    from symbolu_robotics.bcvf_autonomous.simulator import (
        make_straight_road,
    )

    cfg = RunConfig(
        sim=SimConfig(
            dt=0.1, max_steps=4,
            road=make_straight_road(length=50.0),
            obstacles=[], seed=0,
        ),
        mppi=MPPIConfig(num_rollouts=8, horizon=5, dt=0.1),
        perf=PerfCostConfig(),
        bcvf=BCVFConfig(lambda_c=1.0, dt=0.1),
        seed=0,
        trust_diagnostics_enabled=True,
        trust_diagnostics_aggregation="not_a_real_mode",
    )
    with pytest.raises(ValueError):
        Runner(cfg).run()
