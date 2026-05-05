"""Tests for the framework-agnostic ``BCVFNodeBehaviour``.

The node behaviour is the integration-contract layer that wraps
:class:`BCVFTrustBridge` with rate-limiting, deadline-awareness,
and safety-state-machine composition. These tests pin the §3 / §5
contracts of ``ROS2_DDS_SBOM_DESIGN.md`` without requiring rclpy.

Coverage:

* Initial tick before any predictor publishes returns ``None``.
* Tick after every predictor publishes returns a typed
  :class:`ConsensusOutputMessage` with the right shapes.
* Per-predictor deadline tracking marks predictors with no
  recent message as deadline-violated.
* Stale-on-resume protection — a deadline-violated predictor
  needs one fresh post-tick message to clear.
* The safety-state-machine state is included in every output
  with the documented ASIL classification.
* ``reset()`` clears bridge state, state-machine state, and
  predictor buffers.
* Config validation rejects empty or duplicate predictor names,
  non-positive rates, and non-positive deadlines.
* Unknown-predictor messages are silently dropped (DDS topic
  routing should already filter; defensive guard pinned).
"""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.core import BCVFConfig, CostOrder
from symbolu_robotics.bcvf_autonomous.safety_state import SafetyState
from symbolu_robotics.bcvf_ros2 import (
    BCVFNode,
    BCVFNodeBehaviour,
    BCVFNodeConfig,
    BCVFTrustBridgeConfig,
    ConsensusOutputMessage,
    PredictorTrajectoryMessage,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _bridge_config() -> BCVFTrustBridgeConfig:
    return BCVFTrustBridgeConfig(
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


def _node_config(**overrides) -> BCVFNodeConfig:
    base = BCVFNodeConfig(
        bridge_config=_bridge_config(),
        predictor_names=("M1", "M2", "M3"),
        publish_rate_hz=100.0,
        predictor_deadline_ms=100,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def _make_msg(name: str, K: int = 2, H: int = 5, stamp: float = 1.0) -> PredictorTrajectoryMessage:
    return PredictorTrajectoryMessage(
        stamp=stamp,
        frame_id="map",
        predictor_name=name,
        horizon=H,
        num_rollouts=K,
        poses=np.zeros((K, H, 3), dtype=np.float64),
    )


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance_ms(self, ms: float) -> None:
        self.now += ms / 1000.0


# --------------------------------------------------------------------------- #
# Initial state — no predictor data
# --------------------------------------------------------------------------- #


def test_first_tick_with_no_predictor_data_returns_none():
    """No predictor has published yet → there's nothing to
    publish. The rclpy adapter would skip publication."""
    node = BCVFNode(_node_config(), clock=_FakeClock())
    out = node.tick()
    assert out is None
    assert node.n_ticks == 1
    assert node.n_published == 0


def test_initial_safety_state_is_normal():
    node = BCVFNode(_node_config(), clock=_FakeClock())
    assert node.safety_state == SafetyState.NORMAL


# --------------------------------------------------------------------------- #
# Happy-path tick
# --------------------------------------------------------------------------- #


def test_tick_after_inputs_returns_consensus_message():
    clock = _FakeClock()
    node = BCVFNode(_node_config(), clock=clock)
    for name in ("M1", "M2", "M3"):
        node.on_predictor_trajectory(_make_msg(name))
    clock.advance_ms(5.0)
    out = node.tick()
    assert isinstance(out, ConsensusOutputMessage)
    assert out.predictor_names == ["M1", "M2", "M3"]
    assert out.trust_weights.shape == (2, 3)
    assert out.bcvf_total.shape == (2,)
    assert out.num_rollouts == 2


def test_consensus_output_includes_safety_state():
    clock = _FakeClock()
    node = BCVFNode(_node_config(), clock=clock)
    for name in ("M1", "M2", "M3"):
        node.on_predictor_trajectory(_make_msg(name))
    clock.advance_ms(5.0)
    out = node.tick()
    assert out is not None
    assert out.safety_state == SafetyState.NORMAL
    assert out.safety_state_asil_class == 0


def test_trust_weights_form_valid_simplex():
    clock = _FakeClock()
    node = BCVFNode(_node_config(), clock=clock)
    rng = np.random.default_rng(42)
    for name in ("M1", "M2", "M3"):
        msg = _make_msg(name)
        msg.poses[:] = rng.normal(scale=0.3, size=msg.poses.shape)
        node.on_predictor_trajectory(msg)
    clock.advance_ms(5.0)
    out = node.tick()
    assert out is not None
    assert np.all(out.trust_weights >= 0)
    row_sums = out.trust_weights.sum(axis=1)
    assert np.allclose(row_sums, 1.0, atol=1e-9)


# --------------------------------------------------------------------------- #
# Per-predictor deadline tracking
# --------------------------------------------------------------------------- #


def test_predictor_with_no_message_is_deadline_violated():
    """Initial state: no predictor has ever published →
    every predictor is deadline-violated."""
    node = BCVFNode(_node_config(), clock=_FakeClock())
    node.tick()
    assert set(node.deadline_violations) == {"M1", "M2", "M3"}


def test_stale_predictor_is_deadline_violated():
    clock = _FakeClock()
    cfg = _node_config(predictor_deadline_ms=50)
    node = BCVFNode(cfg, clock=clock)
    for name in ("M1", "M2", "M3"):
        node.on_predictor_trajectory(_make_msg(name))
    # First tick — everyone fresh.
    clock.advance_ms(10.0)
    node.tick()
    assert node.deadline_violations == ()
    # Now M3 stops publishing. M1 + M2 keep publishing.
    clock.advance_ms(60.0)  # > 50 ms deadline
    node.on_predictor_trajectory(_make_msg("M1"))
    node.on_predictor_trajectory(_make_msg("M2"))
    node.tick()
    assert "M3" in node.deadline_violations
    assert "M1" not in node.deadline_violations


def test_deadline_violated_predictor_marked_excluded_in_output():
    clock = _FakeClock()
    cfg = _node_config(predictor_deadline_ms=50)
    node = BCVFNode(cfg, clock=clock)
    for name in ("M1", "M2", "M3"):
        node.on_predictor_trajectory(_make_msg(name))
    clock.advance_ms(10.0)
    node.tick()
    # M3 stops publishing.
    clock.advance_ms(60.0)
    node.on_predictor_trajectory(_make_msg("M1"))
    node.on_predictor_trajectory(_make_msg("M2"))
    out = node.tick()
    assert out is not None
    assert out.is_excluded is not None
    # M3 is the third predictor (index 2).
    assert bool(out.is_excluded[2]) is True
    # M1 + M2 are not deadline-excluded.
    assert bool(out.is_excluded[0]) is False
    assert bool(out.is_excluded[1]) is False


def test_stale_on_resume_protection():
    """A deadline-violated predictor needs one fresh post-tick
    message to clear the violation. A single late-then-fresh
    arrival doesn't bounce the status mid-tick.
    """
    clock = _FakeClock()
    cfg = _node_config(predictor_deadline_ms=50)
    node = BCVFNode(cfg, clock=clock)
    for name in ("M1", "M2", "M3"):
        node.on_predictor_trajectory(_make_msg(name))
    clock.advance_ms(10.0)
    node.tick()
    # M3 goes stale.
    clock.advance_ms(60.0)
    node.on_predictor_trajectory(_make_msg("M1"))
    node.on_predictor_trajectory(_make_msg("M2"))
    node.tick()
    assert "M3" in node.deadline_violations
    # M3 publishes a fresh message — but the violation only
    # clears at the NEXT tick, not on the message arrival.
    clock.advance_ms(5.0)
    node.on_predictor_trajectory(_make_msg("M3"))
    # Tick again — the new message is fresh, so on this tick the
    # deadline-violated flag clears.
    node.tick()
    assert "M3" not in node.deadline_violations


# --------------------------------------------------------------------------- #
# reset()
# --------------------------------------------------------------------------- #


def test_reset_clears_bridge_state_and_buffers():
    clock = _FakeClock()
    node = BCVFNode(_node_config(), clock=clock)
    for name in ("M1", "M2", "M3"):
        node.on_predictor_trajectory(_make_msg(name))
    clock.advance_ms(5.0)
    node.tick()
    assert node.last_output is not None
    node.reset()
    assert node.last_output is None
    assert node.n_ticks == 0
    assert node.n_published == 0
    assert node.safety_state == SafetyState.NORMAL


# --------------------------------------------------------------------------- #
# Config validation
# --------------------------------------------------------------------------- #


def test_node_config_rejects_empty_predictor_names():
    with pytest.raises(ValueError, match="predictor_names"):
        BCVFNodeConfig(
            bridge_config=_bridge_config(), predictor_names=()
        )


def test_node_config_rejects_duplicate_predictor_names():
    with pytest.raises(ValueError, match="unique"):
        BCVFNodeConfig(
            bridge_config=_bridge_config(),
            predictor_names=("M1", "M2", "M1"),
        )


def test_node_config_rejects_non_positive_publish_rate():
    with pytest.raises(ValueError, match="publish_rate_hz"):
        BCVFNodeConfig(
            bridge_config=_bridge_config(),
            predictor_names=("M1",),
            publish_rate_hz=0,
        )


def test_node_config_rejects_non_positive_deadline():
    with pytest.raises(ValueError, match="predictor_deadline_ms"):
        BCVFNodeConfig(
            bridge_config=_bridge_config(),
            predictor_names=("M1",),
            predictor_deadline_ms=-1,
        )


# --------------------------------------------------------------------------- #
# Defensive: unknown predictor messages
# --------------------------------------------------------------------------- #


def test_unknown_predictor_message_is_silently_dropped():
    """DDS topic routing should already filter, but defensive:
    an extra subscription doesn't crash the node."""
    node = BCVFNode(_node_config(), clock=_FakeClock())
    node.on_predictor_trajectory(_make_msg("UNKNOWN_M5"))
    # No side-effect — buffers should still be empty for known
    # predictors.
    assert set(node.deadline_violations) == set()  # before tick, never validated
    node.tick()
    # Every known predictor is still deadline-violated (no
    # fresh data for any of them).
    assert set(node.deadline_violations) == {"M1", "M2", "M3"}


# --------------------------------------------------------------------------- #
# Public name alias
# --------------------------------------------------------------------------- #


def test_bcvfnode_aliases_bcvfnodebehaviour():
    """The public-doc / roadmap name is ``BCVFNode`` — for now it
    aliases the framework-agnostic ``BCVFNodeBehaviour``. When
    the rclpy-bound subclass lands (gated on §6.4 colcon-build
    work), this alias may be replaced."""
    assert BCVFNode is BCVFNodeBehaviour


# --------------------------------------------------------------------------- #
# Predictor-trajectory message validation
# --------------------------------------------------------------------------- #


def test_predictor_trajectory_message_rejects_bad_shape():
    with pytest.raises(ValueError, match="poses"):
        PredictorTrajectoryMessage(
            stamp=1.0, frame_id="map",
            predictor_name="M1",
            horizon=5, num_rollouts=2,
            poses=np.zeros((10, 3)),  # wrong rank
        )


def test_predictor_trajectory_message_rejects_inconsistent_dims():
    with pytest.raises(ValueError, match="num_rollouts"):
        PredictorTrajectoryMessage(
            stamp=1.0, frame_id="map",
            predictor_name="M1",
            horizon=5, num_rollouts=3,  # mismatches poses.shape[0]
            poses=np.zeros((2, 5, 3)),
        )


def test_predictor_trajectory_message_rejects_empty_name():
    with pytest.raises(ValueError, match="predictor_name"):
        PredictorTrajectoryMessage(
            stamp=1.0, frame_id="map",
            predictor_name="",
            horizon=5, num_rollouts=2,
            poses=np.zeros((2, 5, 3)),
        )


# --------------------------------------------------------------------------- #
# Audit-fix regression pins (post-v0.7.x critical-audit pass)
# --------------------------------------------------------------------------- #
#
# Each test below pins a contract the original implementation
# violated. A future refactor that reverts the fix re-fails the
# suite.


def test_audit_fix_shape_mismatched_predictor_is_excluded_not_zero_padded():
    """Audit Finding 1: a predictor publishing a (K, H) shape
    different from the canonical tensor shape used to be
    silently zero-padded — fabricating pose data the predictor
    never produced. Now: the predictor is rejected for the tick
    and surfaces in is_excluded.
    """
    clock = _FakeClock()
    node = BCVFNode(_node_config(), clock=clock)
    # M1, M3 publish canonical (K=2, H=5) — sets the canonical shape.
    node.on_predictor_trajectory(_make_msg("M1", K=2, H=5))
    node.on_predictor_trajectory(_make_msg("M3", K=2, H=5))
    # M2 publishes a different shape (K=2, H=3 — three steps
    # short of the canonical horizon). Used to silently
    # zero-pad steps 3, 4. Now: M2 is shape-rejected for the tick.
    node.on_predictor_trajectory(
        PredictorTrajectoryMessage(
            stamp=1.0, frame_id="map",
            predictor_name="M2",
            horizon=3, num_rollouts=2,
            poses=np.ones((2, 3, 3), dtype=np.float64),
        )
    )
    clock.advance_ms(5.0)
    out = node.tick()
    assert out is not None
    assert out.is_excluded is not None
    # M2 (index 1) must be excluded for the tick.
    assert bool(out.is_excluded[1]) is True
    # M1 + M3 are not.
    assert bool(out.is_excluded[0]) is False
    assert bool(out.is_excluded[2]) is False


def test_audit_fix_clock_backwards_does_not_clear_deadline_violations():
    """Audit Finding 2: a clock that steps backwards (sim-time
    reset, NTP step at boot, container suspend/resume) used to
    silently clear every deadline-violated flag in one tick.
    Now: a future-stamped last_arrival is treated as a violation.
    """
    clock = _FakeClock()
    cfg = _node_config(predictor_deadline_ms=50)
    node = BCVFNode(cfg, clock=clock)
    # Publish at t=1.5s.
    clock.now = 1.5
    for name in ("M1", "M2", "M3"):
        node.on_predictor_trajectory(_make_msg(name))
    # First tick at t=1.51s — everyone fresh.
    clock.now = 1.51
    node.tick()
    assert node.deadline_violations == ()
    # Now mark them stale by advancing the clock (so deadline
    # would normally fire). Tick at t=1.7s (200 ms later, > 50 ms
    # deadline).
    clock.now = 1.7
    node.tick()
    assert set(node.deadline_violations) == {"M1", "M2", "M3"}
    # Now step the clock backwards to t=0.99s — earlier than every
    # last_arrival timestamp. Used to clear all violations.
    clock.now = 0.99
    node.tick()
    assert set(node.deadline_violations) == {"M1", "M2", "M3"}, (
        "clock-backwards silently cleared deadline violations — "
        "the audit-fix Finding 2 regression should keep them set"
    )


def test_audit_fix_state_machine_reaches_fault_via_node_path():
    """Audit Finding 3: the BCVFNode used to feed
    consec_suspect=zeros to the state machine, so NORMAL →
    DEGRADED could never fire from this surface. Now:
    consec_suspect is the per-predictor count of consecutive
    excluded ticks.

    This test drives multiple predictors into deadline-violated
    state and confirms the safety_state escalates beyond NORMAL.
    """
    clock = _FakeClock()
    cfg = BCVFNodeConfig(
        bridge_config=_bridge_config(),
        predictor_names=("M1", "M2", "M3"),
        publish_rate_hz=100.0,
        predictor_deadline_ms=50,
        # Tune state machine for a fast test: small window, low
        # threshold so 2-of-N excluded ticks transition.
        state_machine_config=__import__(
            "symbolu_robotics.bcvf_autonomous.safety_state",
            fromlist=["SafetyStateMachineConfig"],
        ).SafetyStateMachineConfig(
            rolling_window_ticks=20,
            near_veto_consec_floor=2,
            near_veto_rate_threshold=0.50,
        ),
    )
    node = BCVFNode(cfg, clock=clock)
    # Publish M1 only — M2 + M3 never publish.
    for _ in range(30):
        node.on_predictor_trajectory(_make_msg("M1"))
        clock.advance_ms(5.0)
        node.tick()
    # M2 + M3 have been deadline-violated every tick, so their
    # consec_suspect counters should be ≥ 2 every tick. The state
    # machine's near-veto rate should now exceed 0.50.
    out = node.last_output
    assert out is not None
    # M2, M3 excluded; safety_state should have escalated past NORMAL.
    assert out.safety_state != SafetyState.NORMAL, (
        "BCVFNode → state machine signal path is broken — "
        "deadline-driven exclusions should drive an escalation"
    )


def test_audit_fix_predictor_names_ordering_is_canonical():
    """Audit Finding 8 (coverage gap): publishing in arrival
    order should NOT scramble the M-axis in the bridge tensor;
    canonical ordering comes from config.predictor_names.
    """
    clock = _FakeClock()
    node = BCVFNode(_node_config(), clock=clock)
    # Publish in reverse order: M3, M1, M2.
    node.on_predictor_trajectory(_make_msg("M3"))
    node.on_predictor_trajectory(_make_msg("M1"))
    node.on_predictor_trajectory(_make_msg("M2"))
    clock.advance_ms(5.0)
    out = node.tick()
    assert out is not None
    # ConsensusOutput predictor_names must follow config order,
    # not arrival order.
    assert out.predictor_names == ["M1", "M2", "M3"]
