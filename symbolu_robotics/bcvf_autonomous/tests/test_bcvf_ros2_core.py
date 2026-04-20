"""Tests for §6.4 ROS 2 bridge core (framework-agnostic).

The ``BCVFTrustBridge`` is pure Python — no ``rclpy`` dependency.
These tests verify the message <-> tensor plumbing and the pass-
through to ``TrustWeightComputer`` without needing a ROS 2 install.
"""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.core import BCVFConfig, CostOrder
from symbolu_robotics.bcvf_ros2.core import (
    BCVFTrustBridge,
    BCVFTrustBridgeConfig,
)
from symbolu_robotics.bcvf_ros2.messages import (
    PredictedTrajectories,
    TrustDistribution,
)


def _default_bridge_config(**overrides) -> BCVFTrustBridgeConfig:
    cfg = BCVFTrustBridgeConfig(
        bcvf_config=BCVFConfig(
            lambda_c=1.0,
            gate_threshold=0.05,
            gate_beta=400.0,
            huber_delta=0.5,
            use_anchor_pairing=False,
            dt=0.1,
            cost_order=CostOrder.SECOND,
        ),
        ema_alpha=0.05,
        deadband_k_sigma=2.0,
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _make_msg(K: int = 2, M: int = 3, H: int = 20, seed: int = 42) -> PredictedTrajectories:
    rng = np.random.default_rng(seed)
    trajectories = rng.normal(scale=0.3, size=(K, M, H, 3)).astype(np.float64)
    return PredictedTrajectories(
        stamp=1.0,
        frame_id="map",
        predictor_names=[f"M{i+1}" for i in range(M)],
        trajectories=trajectories,
    )


# --- message validation ---


def test_predicted_trajectories_rejects_bad_shape() -> None:
    with pytest.raises(ValueError):
        PredictedTrajectories(
            stamp=0.0,
            frame_id="map",
            predictor_names=["M1", "M2"],
            trajectories=np.zeros((2, 2, 20)),  # wrong ndim
        )


def test_predicted_trajectories_rejects_name_mismatch() -> None:
    with pytest.raises(ValueError):
        PredictedTrajectories(
            stamp=0.0,
            frame_id="map",
            predictor_names=["M1", "M2"],  # only 2 names
            trajectories=np.zeros((1, 3, 20, 3)),  # but 3 predictors
        )


def test_trust_distribution_validates_weights_shape() -> None:
    with pytest.raises(ValueError):
        TrustDistribution(
            stamp=0.0,
            frame_id="map",
            predictor_names=["M1", "M2", "M3"],
            weights=np.zeros((2, 2)),  # M mismatch with names (3)
            bcvf_total=np.zeros(2),
        )


# --- bridge step ---


def test_bridge_step_returns_trust_distribution() -> None:
    bridge = BCVFTrustBridge(_default_bridge_config())
    msg = _make_msg(K=2, M=3, H=20)
    out = bridge.step(msg)
    assert isinstance(out, TrustDistribution)
    assert out.stamp == msg.stamp
    assert out.frame_id == msg.frame_id
    assert out.predictor_names == msg.predictor_names
    assert out.weights.shape == (2, 3)
    assert out.bcvf_total.shape == (2,)


def test_bridge_step_weights_form_valid_simplex() -> None:
    bridge = BCVFTrustBridge(_default_bridge_config())
    msg = _make_msg(K=4, M=4, H=20)
    out = bridge.step(msg)
    np.testing.assert_allclose(out.weights.sum(axis=1), 1.0, atol=1e-10)
    assert (out.weights >= -1e-12).all()


def test_bridge_step_passes_through_predictor_names() -> None:
    """A quirky predictor name list (non-Mi) must round-trip unchanged."""
    bridge = BCVFTrustBridge(_default_bridge_config())
    msg = _make_msg(K=2, M=3, H=20)
    msg.predictor_names = ["hdmap", "kalman", "learned"]
    out = bridge.step(msg)
    assert out.predictor_names == ["hdmap", "kalman", "learned"]


def test_bridge_reset_clears_state() -> None:
    bridge = BCVFTrustBridge(_default_bridge_config())
    bridge.step(_make_msg())  # initialize EMA
    assert bridge.trust_computer._ema_mean is not None
    bridge.reset()
    assert bridge.trust_computer._ema_mean is None


def test_bridge_lambda_c_zero_returns_uniform_weights() -> None:
    """lambda_c=0 short-circuits to uniform weights — core invariant
    propagates through the ROS 2 bridge."""
    cfg = _default_bridge_config()
    cfg.bcvf_config = BCVFConfig(
        lambda_c=0.0,
        gate_threshold=0.05,
        gate_beta=400.0,
        huber_delta=0.5,
        use_anchor_pairing=False,
        dt=0.1,
        cost_order=CostOrder.SECOND,
    )
    bridge = BCVFTrustBridge(cfg)
    msg = _make_msg(K=2, M=4, H=20)
    out = bridge.step(msg)
    np.testing.assert_allclose(out.weights, np.full((2, 4), 0.25), atol=1e-12)
    np.testing.assert_allclose(out.bcvf_total, 0.0, atol=1e-12)


def test_bridge_propagates_lemma1_invariance() -> None:
    """Constant-bias predictors → BCVF cost ≈ 0 → uniform weights,
    even through the ROS 2 bridge."""
    bridge = BCVFTrustBridge(_default_bridge_config())
    K, M, H = 2, 4, 20
    # All predictors identical shape + constant offset between them
    traj = np.zeros((K, M, H, 3), dtype=np.float64)
    for m in range(M):
        traj[:, m, :, 0] = m * 0.5  # constant x-offset
    msg = PredictedTrajectories(
        stamp=0.0,
        frame_id="map",
        predictor_names=[f"M{i+1}" for i in range(M)],
        trajectories=traj,
    )
    out = bridge.step(msg)
    np.testing.assert_allclose(out.weights, np.full((K, M), 1.0 / M), atol=1e-10)


def test_bridge_exclusion_enabled_via_config() -> None:
    """Turning on exclusion via config wires through the bridge."""
    cfg = _default_bridge_config(exclusion_enabled=True)
    bridge = BCVFTrustBridge(cfg)
    assert bridge.trust_computer._exclusion_enabled is True


def test_bridge_sequential_steps_update_ema() -> None:
    """Step 0 initializes EMA; step 1 produces non-zero residual."""
    bridge = BCVFTrustBridge(_default_bridge_config())
    out0 = bridge.step(_make_msg(seed=7))
    # After step 0, EMA mean should be initialized.
    assert bridge.trust_computer._ema_mean is not None
    mean_before = bridge.trust_computer._ema_mean.copy()
    # Step 1 with a different seed should update EMA.
    bridge.step(_make_msg(seed=9))
    mean_after = bridge.trust_computer._ema_mean
    # EMA changed (not bit-identical)
    assert not np.array_equal(mean_before, mean_after)


# --- ros2_shim import-time safety ---


def test_ros2_shim_imports_without_rclpy() -> None:
    """The ros2_shim module must be importable in a non-ROS
    environment. rclpy is deferred to call time via _require_rclpy."""
    import symbolu_robotics.bcvf_ros2.ros2_shim as shim
    assert hasattr(shim, "build_bcvf_trust_node")
    assert hasattr(shim, "_require_rclpy")


def test_ros2_shim_raises_clear_error_without_rclpy() -> None:
    """If rclpy isn't installed, the shim raises a clear ImportError."""
    from symbolu_robotics.bcvf_ros2 import ros2_shim
    try:
        import rclpy  # noqa: F401
        # rclpy IS installed — skip this test
        pytest.skip("rclpy is installed in this environment")
    except ImportError:
        pass
    with pytest.raises(ImportError) as excinfo:
        ros2_shim._require_rclpy()
    assert "rclpy" in str(excinfo.value)
    assert "BCVFTrustBridge" in str(excinfo.value)  # points to usable fallback
