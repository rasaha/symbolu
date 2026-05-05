"""``BCVFNodeBehaviour`` — framework-agnostic node behaviour.

The behaviour is the public-facing piece of the ROS 2 / DDS
integration contract. It wraps :class:`BCVFTrustBridge` with:

* per-predictor input buffers + arrival timestamps,
* a publish-rate-limited tick that produces one
  :class:`ConsensusOutputMessage` per call,
* per-predictor deadline tracking — a predictor whose latest
  message is older than ``predictor_deadline_ms`` is marked
  excluded for the next tick,
* composition with :class:`SafetyStateMachine` so the published
  consensus carries the system-level safety posture,
* stale-on-resume protection — a deadline-violated predictor
  needs one fresh tick to clear before its exclusion bit drops.

The class is deliberately framework-agnostic: it accepts a
``clock`` callable (``time.monotonic`` by default) and emits
``ConsensusOutputMessage`` dataclasses that the rclpy adapter
converts to real ROS 2 messages at the boundary. The class is
testable without ROS 2 installed.

See ``ROS2_DDS_SBOM_DESIGN.md`` §3.3 + §5 for the full design.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from ..bcvf_autonomous.safety_state import (
    SafetyState,
    SafetyStateMachine,
    SafetyStateMachineConfig,
    TickView,
)
from .core import BCVFTrustBridge, BCVFTrustBridgeConfig
from .messages import PredictedTrajectories, TrustDistribution


# --------------------------------------------------------------------------- #
# Per-predictor input message
# --------------------------------------------------------------------------- #


@dataclass
class PredictorTrajectoryMessage:
    """Framework-agnostic equivalent of ``PredictorTrajectory.msg``.

    One message per predictor per planning step. The rclpy
    adapter converts between this dataclass and the real
    ROS 2 message at the bus boundary. See
    ``ROS2_DDS_SBOM_DESIGN.md`` §3.1.
    """

    stamp: float                      # nanoseconds since epoch
    frame_id: str
    predictor_name: str
    horizon: int
    num_rollouts: int
    poses: np.ndarray                 # (K, H, 3) SE(2) x/y/θ

    def __post_init__(self) -> None:
        if self.poses.ndim != 3 or self.poses.shape[-1] != 3:
            raise ValueError(
                f"poses must be (K, H, 3); got {self.poses.shape}"
            )
        if self.poses.shape[0] != self.num_rollouts:
            raise ValueError(
                f"poses.shape[0]={self.poses.shape[0]} mismatches "
                f"num_rollouts={self.num_rollouts}"
            )
        if self.poses.shape[1] != self.horizon:
            raise ValueError(
                f"poses.shape[1]={self.poses.shape[1]} mismatches "
                f"horizon={self.horizon}"
            )
        if not self.predictor_name:
            raise ValueError("predictor_name must be a non-empty string")


# --------------------------------------------------------------------------- #
# Consensus output message
# --------------------------------------------------------------------------- #


@dataclass
class ConsensusOutputMessage:
    """Framework-agnostic equivalent of ``ConsensusOutput.msg``.

    Published by the node behaviour at ``publish_rate_hz``. Carries
    the BCVF trust distribution + the safety-state-machine state
    for one planning step. See ``ROS2_DDS_SBOM_DESIGN.md`` §3.2.
    """

    stamp: float
    frame_id: str
    predictor_names: List[str]
    trust_weights: np.ndarray          # (K, M)
    num_rollouts: int
    bcvf_total: np.ndarray             # (K,)
    ema_mean: Optional[np.ndarray]     # (M,) or None
    ema_std: Optional[np.ndarray]      # (M,) or None
    deadband_active_count: int
    is_excluded: Optional[np.ndarray]  # (M,) bool or None
    safety_state: SafetyState
    safety_state_asil_class: int       # 0 (N/A), 2 (ASIL-B), 4 (ASIL-D)


# --------------------------------------------------------------------------- #
# Node config
# --------------------------------------------------------------------------- #


@dataclass
class BCVFNodeConfig:
    """Configuration for :class:`BCVFNodeBehaviour`.

    ``bridge_config`` is required (the trust-shaping engine).
    The remaining knobs control the timing discipline.
    """

    bridge_config: BCVFTrustBridgeConfig
    #: One predictor topic per name. Order is the canonical
    #: predictor ordering used by the bridge tensor.
    predictor_names: Tuple[str, ...] = ()
    #: Rate at which the node publishes ``ConsensusOutputMessage``.
    #: Default 100 Hz matches the DDS QoS deadline of 10 ms.
    publish_rate_hz: float = 100.0
    #: A predictor is deadline-violated if no fresh message has
    #: arrived within this many milliseconds.
    predictor_deadline_ms: int = 100
    #: State-machine config; ``None`` uses the default
    #: ``SafetyStateMachineConfig()``.
    state_machine_config: Optional[SafetyStateMachineConfig] = None
    #: Frame in which the consensus is published. Mirrors the
    #: input frame_id by default; override if the consensus is
    #: re-projected to a vehicle-fixed frame.
    output_frame_id: str = "map"

    def __post_init__(self) -> None:
        if not self.predictor_names:
            raise ValueError(
                "predictor_names must be non-empty — the node needs "
                "at least one predictor topic to subscribe to"
            )
        if len(set(self.predictor_names)) != len(self.predictor_names):
            raise ValueError(
                f"predictor_names must be unique; "
                f"got {self.predictor_names}"
            )
        if self.publish_rate_hz <= 0:
            raise ValueError(
                f"publish_rate_hz must be positive; "
                f"got {self.publish_rate_hz}"
            )
        if self.predictor_deadline_ms <= 0:
            raise ValueError(
                f"predictor_deadline_ms must be positive; "
                f"got {self.predictor_deadline_ms}"
            )


# --------------------------------------------------------------------------- #
# ASIL classification helper
# --------------------------------------------------------------------------- #


def _asil_class_for(state: SafetyState) -> int:
    """Map a SafetyState to the per-state ASIL classification.

    NORMAL = 0 (N/A — not in a safety-relevant transition).
    DEGRADED = 2 (ASIL-B — warning class).
    FAULT / FAILSAFE = 4 (ASIL-D — safety-critical).
    """
    if state == SafetyState.NORMAL:
        return 0
    if state == SafetyState.DEGRADED:
        return 2
    if state in (SafetyState.FAULT, SafetyState.FAILSAFE):
        return 4
    return 0  # defensive: unreachable for the four-state enum


# --------------------------------------------------------------------------- #
# BCVFNodeBehaviour
# --------------------------------------------------------------------------- #


@dataclass
class _PredictorBuffer:
    """Per-predictor buffer: the latest message + arrival time
    + suspicion counters."""

    last_message: Optional[PredictorTrajectoryMessage] = None
    last_arrival: Optional[float] = None
    deadline_violated: bool = False
    #: Audit-fix Finding 3: consecutive ticks the predictor has
    #: been "suspect" (deadline-violated OR bridge-excluded OR
    #: shape-rejected). Mirrors the per-predictor
    #: ``consec_suspect`` counter that
    #: ``TrustWeightComputer`` tracks internally for exclusion;
    #: surfaces here so the safety state machine has a real
    #: near-veto signal to fire NORMAL → DEGRADED on through
    #: the BCVFNode path.
    consec_suspect: int = 0


class BCVFNodeBehaviour:
    """Framework-agnostic BCVF ROS 2 node behaviour.

    The class is the testable core of :class:`BCVFNode` (the
    rclpy-bound class lives in :mod:`ros2_shim`). Inputs:

    * :meth:`on_predictor_trajectory` — call per inbound
      :class:`PredictorTrajectoryMessage`.
    * :meth:`tick` — call at ``publish_rate_hz`` (rclpy timer
      drives this in production; tests pass a fake clock).

    Outputs:

    * Each :meth:`tick` returns one
      :class:`ConsensusOutputMessage` (or ``None`` if no
      predictor has published yet — the node has nothing to
      publish until at least one predictor's input arrives).

    The class enforces three invariants from
    ``ROS2_DDS_SBOM_DESIGN.md`` §5:

    1. **Bounded publish rate.** Output is per-tick, regardless
       of input rate. The caller (rclpy timer or test driver) is
       responsible for calling :meth:`tick` at the configured
       cadence.
    2. **Per-predictor deadline.** A predictor whose last
       message is older than ``predictor_deadline_ms`` is
       deadline-violated; its column appears in
       ``is_excluded`` of the output, and the safety state
       machine sees the exclusion via the same path live data
       would take.
    3. **Stale-on-resume protection.** A deadline-violated
       predictor needs one fresh message AFTER the latest tick
       to clear the violation — single transient ticks don't
       bounce the deadline status.
    """

    def __init__(
        self,
        config: BCVFNodeConfig,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._clock = clock
        self._bridge = BCVFTrustBridge(config.bridge_config)
        sm_cfg = (
            config.state_machine_config
            if config.state_machine_config is not None
            else SafetyStateMachineConfig()
        )
        self._safety_state_machine = SafetyStateMachine(sm_cfg)
        # Initialise one buffer per predictor in declaration order.
        # Reading buffers in declaration order is what fixes the
        # canonical M-axis ordering of the bridge tensor.
        self._buffers: Dict[str, _PredictorBuffer] = {
            name: _PredictorBuffer() for name in config.predictor_names
        }
        # Track the last tick's published message for diagnostics.
        self._last_output: Optional[ConsensusOutputMessage] = None
        self._n_ticks: int = 0
        self._n_published: int = 0

    # ----- public properties ----- #

    @property
    def config(self) -> BCVFNodeConfig:
        return self._config

    @property
    def safety_state(self) -> SafetyState:
        return self._safety_state_machine.state

    @property
    def safety_state_machine(self) -> SafetyStateMachine:
        return self._safety_state_machine

    @property
    def deadline_violations(self) -> Tuple[str, ...]:
        """Tuple of predictor names currently flagged as
        deadline-violated. Empty if every predictor is fresh."""
        return tuple(
            name
            for name, buf in self._buffers.items()
            if buf.deadline_violated
        )

    @property
    def n_ticks(self) -> int:
        return self._n_ticks

    @property
    def n_published(self) -> int:
        """Count of ticks that produced a published output (i.e.
        ticks where at least one predictor had an input)."""
        return self._n_published

    @property
    def last_output(self) -> Optional[ConsensusOutputMessage]:
        return self._last_output

    # ----- input ----- #

    def on_predictor_trajectory(
        self, msg: PredictorTrajectoryMessage
    ) -> None:
        """Buffer one inbound predictor message.

        A message for an unknown predictor name (not in the
        config's ``predictor_names``) is silently dropped — the
        DDS layer's topic-routing should already filter, but
        defensive: an extra subscription doesn't crash the node.
        """
        buf = self._buffers.get(msg.predictor_name)
        if buf is None:
            return
        buf.last_message = msg
        buf.last_arrival = self._clock()
        # Do NOT clear deadline_violated yet — stale-on-resume
        # protection (§5 invariant 3): the violation clears at
        # the next tick, not on the message arrival, so a single
        # late-then-fresh message doesn't bounce status.

    # ----- tick ----- #

    def tick(self) -> Optional[ConsensusOutputMessage]:
        """Run one publishing cycle. Returns the output message
        (or ``None`` if no predictor has published yet)."""
        self._n_ticks += 1
        now = self._clock()
        # Update per-predictor deadline status. A predictor is
        # deadline-violated if:
        #   * it has never published, OR
        #   * its latest arrival is older than the deadline, OR
        #   * its latest arrival is in the FUTURE relative to
        #     ``now`` (audit-fix Finding 2: a clock that steps
        #     backwards — ROS sim-time reset, NTP step at boot,
        #     container suspend/resume, GPS time sync — would
        #     otherwise silently clear every deadline violation).
        deadline_s = self._config.predictor_deadline_ms / 1000.0
        for buf in self._buffers.values():
            if buf.last_arrival is None:
                buf.deadline_violated = True
                continue
            stale_for_s = now - buf.last_arrival
            if stale_for_s < 0 or stale_for_s > deadline_s:
                buf.deadline_violated = True
            else:
                # Fresh: clears the violation on the next tick
                # boundary (stale-on-resume). The buffer's data
                # is fresh enough to use this tick.
                buf.deadline_violated = False

        # If no predictor has any message yet, there's nothing to
        # publish. (The rclpy adapter will skip publication on a
        # None return.)
        if not any(buf.last_message is not None for buf in self._buffers.values()):
            return None

        # Build the (K, M, H, 3) tensor from the latest per-
        # predictor messages. We take the canonical M-axis
        # ordering from the config's ``predictor_names`` tuple.
        # Predictors with no message yet OR deadline-violated
        # contribute zero-pose stubs and are exclusion-flagged
        # downstream; the bridge sees them as "present but
        # producing degenerate output", which the trust shaper
        # already handles as "high BCVF cost → low weight".
        predictor_names = list(self._config.predictor_names)
        # Determine canonical (K, H) from any message — first
        # buffer with a fresh message defines the shape.
        sample = next(
            (
                buf.last_message
                for buf in self._buffers.values()
                if buf.last_message is not None
            ),
            None,
        )
        assert sample is not None  # guarded by the early return above
        K = sample.num_rollouts
        H = sample.horizon
        M = len(predictor_names)
        trajectories = np.zeros((K, M, H, 3), dtype=np.float64)
        # Per-predictor exclusion mask. A predictor is excluded
        # for THIS tick if any of:
        #   * never published / deadline-violated
        #   * shape-rejected (audit-fix Finding 1: refuse to
        #     fabricate poses for rollouts the predictor never
        #     produced — silently zero-padding mismatched (K, H)
        #     used to route fake near-vehicle predictions into
        #     consensus).
        deadline_excluded = np.zeros(M, dtype=bool)
        shape_rejected = np.zeros(M, dtype=bool)
        for m, name in enumerate(predictor_names):
            buf = self._buffers[name]
            if buf.last_message is None or buf.deadline_violated:
                deadline_excluded[m] = True
                continue
            poses = buf.last_message.poses
            if poses.shape != (K, H, 3):
                # Shape doesn't match the canonical (K, H, 3) the
                # consensus tensor expects. Reject the predictor
                # for this tick rather than silently zero-padding
                # — padding fabricates pose data the predictor
                # never produced + the kernel sees the zero rows
                # as "good" trajectories the predictor agrees
                # with, which is a real consensus-injection
                # vulnerability.
                shape_rejected[m] = True
                continue
            trajectories[:, m, :, :] = poses

        # Run the bridge over the canonical tensor.
        bridge_input = PredictedTrajectories(
            stamp=sample.stamp,
            frame_id=sample.frame_id,
            predictor_names=predictor_names,
            trajectories=trajectories,
        )
        trust_msg: TrustDistribution = self._bridge.step(bridge_input)

        # Combine the bridge's exclusion bits with the deadline-
        # exclusion mask AND the shape-rejected mask: a predictor
        # is excluded if ANY of the three is true.
        bridge_excl = trust_msg.is_excluded
        if bridge_excl is not None:
            combined_excluded = np.logical_or.reduce(
                [bridge_excl.astype(bool), deadline_excluded, shape_rejected]
            )
        else:
            combined_excluded = np.logical_or(
                deadline_excluded, shape_rejected
            )

        # Audit-fix Finding 3: surface a real near-veto signal to
        # the safety state machine. Per-predictor consec_suspect
        # counts consecutive ticks the predictor was "suspect"
        # (excluded by ANY mechanism — bridge, deadline, shape).
        # Resets to 0 the tick the predictor is fresh + accepted
        # by the bridge. This gives the state machine the
        # near-veto signal it needs to fire NORMAL → DEGRADED
        # via the BCVFNode path; without it the state machine
        # was structurally unable to escalate (NORMAL only).
        for m, name in enumerate(predictor_names):
            buf = self._buffers[name]
            if combined_excluded[m]:
                buf.consec_suspect += 1
            else:
                buf.consec_suspect = 0
        consec_suspect = np.array(
            [self._buffers[n].consec_suspect for n in predictor_names],
            dtype=np.int64,
        )
        # Use the largest BCVF total across rollouts — the state
        # machine works on a single-tick scalar.
        bcvf_scalar = float(np.max(trust_msg.bcvf_total))
        tick_view = TickView(
            bcvf_total=bcvf_scalar,
            is_excluded=combined_excluded,
            consec_suspect=consec_suspect,
            M=M,
        )
        self._safety_state_machine.observe(tick_view)
        sm_state = self._safety_state_machine.state

        out = ConsensusOutputMessage(
            stamp=sample.stamp,
            frame_id=self._config.output_frame_id,
            predictor_names=predictor_names,
            trust_weights=trust_msg.weights,
            num_rollouts=K,
            bcvf_total=trust_msg.bcvf_total,
            ema_mean=trust_msg.ema_mean,
            ema_std=trust_msg.ema_std,
            deadband_active_count=int(trust_msg.deadband_active_count),
            is_excluded=combined_excluded,
            safety_state=sm_state,
            safety_state_asil_class=_asil_class_for(sm_state),
        )
        self._last_output = out
        self._n_published += 1
        return out

    # ----- diagnostic / ops ----- #

    def reset(self) -> None:
        """Clear per-episode state on the bridge (EMA, exclusion
        counters) AND reset the safety state machine. The state
        machine reset uses the manual-reset path through
        FAULT/FAILSAFE; from NORMAL/DEGRADED it just re-creates
        the machine fresh."""
        self._bridge.reset()
        # Reset the state machine by replacing it. The transition
        # log of the old machine is implicitly discarded; a
        # production deployment that wants to retain the audit
        # trail across resets must persist the log externally
        # before calling reset().
        sm_cfg = (
            self._config.state_machine_config
            if self._config.state_machine_config is not None
            else SafetyStateMachineConfig()
        )
        self._safety_state_machine = SafetyStateMachine(sm_cfg)
        for buf in self._buffers.values():
            buf.last_message = None
            buf.last_arrival = None
            buf.deadline_violated = False
            buf.consec_suspect = 0
        self._last_output = None
        self._n_ticks = 0
        self._n_published = 0


# --------------------------------------------------------------------------- #
# Public BCVFNode alias (the §3 / roadmap / public-doc name)
# --------------------------------------------------------------------------- #


#: Public name. The roadmap + design doc use ``BCVFNode``; the
#: framework-agnostic class is named ``BCVFNodeBehaviour`` to
#: distinguish it from a future rclpy-bound subclass. Until the
#: rclpy-bound subclass exists (gated on §6.4 colcon-build
#: execution work), ``BCVFNode`` aliases the behaviour class.
BCVFNode = BCVFNodeBehaviour
