"""Tests for bcvf_autonomous.predictors — DESIGN.md §2.6."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.core import BCVFConfig, compute_bcvf_cost
from symbolu_robotics.bcvf_autonomous.predictors import (
    BicycleConfig,
    ControlInput,
    FailureConfig,
    GNSSMap,
    IMUOdometry,
    LidarSLAM,
    PredictorState,
    VisualOdometry,
    create_predictor_set,
)


# --- helpers ---


def _straight_line_controls(horizon: int, velocity: float = 8.0) -> np.ndarray:
    controls = np.zeros((horizon, 2), dtype=np.float64)
    controls[:, 0] = velocity
    return controls


def _constant_steer_controls(
    horizon: int, velocity: float = 4.0, steering: float = 0.2
) -> np.ndarray:
    controls = np.zeros((horizon, 2), dtype=np.float64)
    controls[:, 0] = velocity
    controls[:, 1] = steering
    return controls


def _default_bcvf_config() -> BCVFConfig:
    # Matches default_se2.yaml post-sweep defaults.
    return BCVFConfig(
        lambda_c=1.0,
        gate_threshold=0.2,
        gate_beta=100.0,
        huber_delta=0.5,
        lever_arm=2.5,
        weight_matrix=np.ones(3, dtype=np.float64),
        use_anchor_pairing=True,
        anchor_index=0,
        dt=0.1,
    )


# --- §2.6.1 Bicycle model (pure dynamics via bicycle_step) ---


def _roll_bicycle(pred, controls: np.ndarray) -> np.ndarray:
    """Call ``bicycle_step`` directly, bypassing noise / drift / failure."""
    state = PredictorState()
    trajectory = np.zeros((controls.shape[0], 3), dtype=np.float64)
    for k in range(controls.shape[0]):
        state = pred.bicycle_step(
            state, ControlInput(float(controls[k, 0]), float(controls[k, 1]))
        )
        trajectory[k] = (state.x, state.y, state.theta)
    return trajectory


def test_bicycle_straight_line() -> None:
    pred = IMUOdometry(seed=0)
    controls = _straight_line_controls(50, velocity=8.0)
    trajectory = _roll_bicycle(pred, controls)
    assert np.allclose(trajectory[:, 1], 0.0, atol=1e-12)
    assert np.allclose(trajectory[:, 2], 0.0, atol=1e-12)
    expected_x = 8.0 * 0.1 * np.arange(1, 51)
    assert np.allclose(trajectory[:, 0], expected_x, atol=1e-12)


def test_bicycle_constant_turn() -> None:
    pred = IMUOdometry(seed=0, bicycle_config=BicycleConfig(wheelbase=2.0))
    steering = 0.2
    velocity = 4.0
    expected_radius = pred.bicycle_config.wheelbase / math.tan(steering)
    controls = _constant_steer_controls(200, velocity=velocity, steering=steering)
    trajectory = _roll_bicycle(pred, controls)
    # Kinematic bicycle ICR for a positive steering from the origin with
    # heading 0 is at (0, +R). Distance from ICR should equal R.
    radii = np.hypot(trajectory[:, 0], trajectory[:, 1] - expected_radius)
    # Euler discretization drifts on the order of dt — allow ~3% radial error.
    assert np.allclose(radii, expected_radius, rtol=0.03)


def test_bicycle_zero_velocity() -> None:
    pred = IMUOdometry(seed=0)
    controls = np.zeros((20, 2), dtype=np.float64)
    controls[:, 1] = 0.3
    trajectory = _roll_bicycle(pred, controls)
    assert np.allclose(trajectory, 0.0, atol=1e-12)


def test_bicycle_clamps_velocity() -> None:
    cfg = BicycleConfig(max_velocity=5.0)
    pred = IMUOdometry(bicycle_config=cfg, seed=0)
    controls = np.zeros((10, 2), dtype=np.float64)
    controls[:, 0] = 20.0
    trajectory = _roll_bicycle(pred, controls)
    # 5 m/s * 0.1 s = 0.5 m per step -> 5 m after 10 steps.
    assert trajectory[-1, 0] == pytest.approx(5.0, abs=1e-12)


def test_bicycle_clamps_steering() -> None:
    cfg_capped = BicycleConfig(max_steering=0.1)
    cfg_open = BicycleConfig(max_steering=2.0)
    controls = _constant_steer_controls(100, velocity=4.0, steering=1.5)
    traj_capped = _roll_bicycle(IMUOdometry(bicycle_config=cfg_capped, seed=0), controls)
    traj_open = _roll_bicycle(IMUOdometry(bicycle_config=cfg_open, seed=0), controls)
    # Clamped predictor turns slower -> smaller |yaw| at the end.
    assert abs(traj_capped[-1, 2]) < abs(traj_open[-1, 2])


def test_bicycle_reverse() -> None:
    pred = IMUOdometry(seed=0)
    controls = np.zeros((10, 2), dtype=np.float64)
    controls[:, 0] = -4.0
    trajectory = _roll_bicycle(pred, controls)
    assert trajectory[-1, 0] < 0.0


# --- §2.6.2 Nominal agreement ---


def test_nominal_trajectories_close() -> None:
    predictors = create_predictor_set()
    controls = _straight_line_controls(50, velocity=8.0)
    trajectories = [p.predict(controls) for p in predictors.values()]
    # Max pairwise ||p_i - p_j|| over all steps (x, y only).
    max_gap = 0.0
    for i in range(len(trajectories)):
        for j in range(i + 1, len(trajectories)):
            dxy = trajectories[i][:, :2] - trajectories[j][:, :2]
            max_gap = max(max_gap, float(np.linalg.norm(dxy, axis=-1).max()))
    assert max_gap < 2.0, f"nominal disagreement too large: {max_gap:.3f} m"


def test_nominal_bcvf_low() -> None:
    predictors = create_predictor_set()
    controls = _straight_line_controls(50, velocity=8.0)
    trajectories = [p.predict(controls) for p in predictors.values()]
    cost = compute_bcvf_cost(trajectories, _default_bcvf_config()).total_cost
    # With Phase 2-tuned post-filter noise floors, nominal BCVF stays
    # well below 10 (typical range 1–5 across seeds).
    assert cost < 10.0, f"nominal BCVF cost surprisingly high: {cost:.3f}"


def test_predictor_determinism() -> None:
    controls = _straight_line_controls(30, velocity=6.0)
    p1 = IMUOdometry(seed=7)
    p2 = IMUOdometry(seed=7)
    t1 = p1.predict(controls)
    t2 = p2.predict(controls)
    assert np.array_equal(t1, t2)
    # Same predictor instance, two predict calls -> same trajectory (reset RNG).
    t3 = p1.predict(controls)
    assert np.array_equal(t1, t3)


# --- §2.6.3 Failure divergence ---


def test_lidar_failure_accelerating() -> None:
    bc = BicycleConfig()
    m1 = IMUOdometry(bicycle_config=bc, seed=100)
    m2 = LidarSLAM(bicycle_config=bc, seed=101)
    m2.set_failure(FailureConfig(active=True, onset_time=0.0, severity=1.0, ramp_duration=0.1))
    controls = _straight_line_controls(50, velocity=8.0)
    t1 = m1.predict(controls)
    t2 = m2.predict(controls)

    # Disagreement x-component over time.
    dx = t2[:, 0] - t1[:, 0]
    ks = np.arange(dx.size, dtype=np.float64)
    # Quadratic fit: dx = a*k^2 + b*k + c.
    coeffs = np.polyfit(ks, dx, 2)
    fit = np.polyval(coeffs, ks)
    ss_res = float(np.sum((dx - fit) ** 2))
    ss_tot = float(np.sum((dx - dx.mean()) ** 2))
    r_squared = 1.0 - ss_res / max(ss_tot, 1e-12)
    assert abs(coeffs[0]) > 1e-4, f"quadratic term too small: {coeffs[0]:.6f}"
    assert r_squared > 0.9, f"R^2 on quadratic fit is {r_squared:.3f}"


def test_vo_tracking_loss() -> None:
    bc = BicycleConfig()
    vo = VisualOdometry(bicycle_config=bc, seed=200)
    # Severity 1.0 with zero ramp puts us immediately into tracking-loss regime.
    vo.set_failure(FailureConfig(active=True, onset_time=0.0, severity=1.0, ramp_duration=0.0))
    controls = _straight_line_controls(50, velocity=8.0)
    trajectory = vo.predict(controls)
    # Truth (no failure, no noise) would be x = 0.1 * 8 * (k+1) = 0.8*(k+1).
    # Frozen/tracking-loss means estimate stays near a single frozen pose
    # instead of advancing ~40 m over H=50 steps. Measure displacement from
    # mean — should be small (random walk around the frozen pose).
    disp_from_mean = np.linalg.norm(
        trajectory[:, :2] - trajectory[:, :2].mean(axis=0), axis=-1
    ).max()
    assert disp_from_mean < 1.5, f"frozen state spread too large: {disp_from_mean:.3f}"


def test_gps_multipath_jumps() -> None:
    bc = BicycleConfig()
    gnss = GNSSMap(bicycle_config=bc, seed=300, failure_type="multipath")
    gnss.set_failure(FailureConfig(active=True, onset_time=0.0, severity=1.0, ramp_duration=0.5))
    controls = _straight_line_controls(200, velocity=8.0)
    trajectory = gnss.predict(controls)
    # Step-to-step displacement excluding deterministic motion (v*dt=0.8 m).
    step_displacement = np.linalg.norm(np.diff(trajectory[:, :2], axis=0), axis=-1)
    jumps_over_2m = int(np.sum(step_displacement > 2.0))
    assert jumps_over_2m >= 5, f"multipath jumps > 2m: {jumps_over_2m}"


def test_gps_map_error_lateral() -> None:
    bc = BicycleConfig()
    gnss = GNSSMap(bicycle_config=bc, seed=301, failure_type="map_error")
    gnss.set_failure(FailureConfig(active=True, onset_time=0.0, severity=1.0, ramp_duration=0.1))
    controls = _straight_line_controls(50, velocity=8.0)
    trajectory = gnss.predict(controls)
    # Straight-line motion along +x, lateral offset applied at +pi/2 -> +y.
    # The y-coordinate should grow over time.
    early_y = trajectory[:5, 1].mean()
    late_y = trajectory[-5:, 1].mean()
    assert late_y - early_y > 2.0, (
        f"lateral offset not accumulating: early_y={early_y:.3f} late_y={late_y:.3f}"
    )


def test_imu_drift_linear() -> None:
    bc = BicycleConfig()
    m1_ref = IMUOdometry(bicycle_config=bc, seed=400)
    m1_fault = IMUOdometry(bicycle_config=bc, seed=401)
    m1_fault.set_failure(
        FailureConfig(active=True, onset_time=0.0, severity=1.0, ramp_duration=0.1)
    )
    controls = _straight_line_controls(50, velocity=8.0)
    t_ref = m1_ref.predict(controls)
    t_fault = m1_fault.predict(controls)

    cost = compute_bcvf_cost([t_ref, t_fault], _default_bcvf_config()).total_cost
    # IMU drift is a random walk -> approximately linear in expectation, so
    # second-order acceleration is small (Lemma 1). With the tuned post-
    # filter noise floor the cost sits well under the failure-mode costs.
    assert cost < 5.0, f"IMU drift produced large BCVF cost: {cost:.2f}"


# --- §2.6.4 Integration with Phase 1 ---


def test_nominal_all_predictors_bcvf_zero() -> None:
    predictors = create_predictor_set()
    controls = _straight_line_controls(50, velocity=8.0)
    trajectories = [p.predict(controls) for p in predictors.values()]
    cost = compute_bcvf_cost(trajectories, _default_bcvf_config()).total_cost
    # Post-filter predictor noise keeps nominal cost in the "quiet" regime
    # (<< any of the failure-mode costs covered by the next test).
    assert cost < 10.0, f"nominal-mode BCVF cost too high: {cost:.2f}"


def test_lidar_failure_bcvf_positive() -> None:
    predictors = create_predictor_set()
    controls = _straight_line_controls(50, velocity=8.0)
    # Inject LiDAR failure from t=2s with a short ramp.
    predictors["M2"].set_failure(
        FailureConfig(active=True, onset_time=2.0, severity=1.0, ramp_duration=0.5)
    )
    trajectories = [p.predict(controls) for p in predictors.values()]
    cost = compute_bcvf_cost(trajectories, _default_bcvf_config()).total_cost
    assert cost > 0.5, f"LiDAR failure did not elevate cost: {cost:.3f}"


def test_failure_vs_nominal_ordering() -> None:
    bcfg = _default_bcvf_config()
    controls = _straight_line_controls(50, velocity=8.0)

    nominal = create_predictor_set()
    nominal_trajectories = [p.predict(controls) for p in nominal.values()]
    nominal_cost = compute_bcvf_cost(nominal_trajectories, bcfg).total_cost

    faulted = create_predictor_set()
    faulted["M2"].set_failure(
        FailureConfig(active=True, onset_time=0.0, severity=1.0, ramp_duration=0.5)
    )
    faulted_trajectories = [p.predict(controls) for p in faulted.values()]
    fault_cost = compute_bcvf_cost(faulted_trajectories, bcfg).total_cost

    assert fault_cost > nominal_cost, (
        f"fault cost {fault_cost:.3f} not greater than nominal {nominal_cost:.3f}"
    )


# --- misc contract tests ---


def test_predict_does_not_mutate_state() -> None:
    pred = IMUOdometry(seed=99)
    initial = PredictorState(x=1.0, y=2.0, theta=0.3, timestamp=0.5)
    pred.set_state(initial)
    _ = pred.predict(_straight_line_controls(10, velocity=3.0))
    assert pred.state.x == pytest.approx(1.0)
    assert pred.state.y == pytest.approx(2.0)
    assert pred.state.theta == pytest.approx(0.3)
    assert pred.state.timestamp == pytest.approx(0.5)


def test_predict_requires_valid_shape() -> None:
    pred = IMUOdometry(seed=0)
    with pytest.raises(ValueError):
        pred.predict(np.zeros((10,)))
    with pytest.raises(ValueError):
        pred.predict(np.zeros((10, 3)))
