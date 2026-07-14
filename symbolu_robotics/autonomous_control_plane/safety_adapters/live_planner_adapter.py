"""Production-shaped planner-output -> TrajectoryPoint adapter (Phase 3 §2).

Translates the REAL deliberative planner's output (a ``Plan`` whose actions are
``ActuatorCommand``s) into the existing ``TrajectoryPoint`` representation the
Phase-2 ``TrajectoryValidatorAdapter`` consumes — WITHOUT fabricating physical
values. A constant-velocity ``ActuatorCommand`` is rolled forward
deterministically (the literal meaning of "apply velocity v for duration T"); no
missing physical value is interpolated or inferred.

Fails closed (§2) on: missing trajectory, malformed dimensions, unit ambiguity /
inconsistent joint ordering (wrong joint count), NaN/Inf, unsupported command
type (no joint velocities), and candidate/state identity mismatch. On any of
these it returns a non-SUPPORTED status; the shadow hook then records a
fail-closed outcome and never EXECUTEs.

Imports numpy + the real safety modules — lives in the adapter subpackage, not
the ACP core.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

import numpy as np

from symbolu_robotics.safety.trajectory_validator import TrajectoryPoint

from ..envelopes import ActionType, CanonicalActionCandidate
from .candidate_bridge import velocity_command_to_trajectory

_EXPECTED_JOINTS = 6  # manipulator DoF the TrajectoryValidator is configured for


class LivePathStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    MISSING_TRAJECTORY = "MISSING_TRAJECTORY"
    UNSUPPORTED_COMMAND = "UNSUPPORTED_COMMAND"
    DIMENSION_MISMATCH = "DIMENSION_MISMATCH"
    NONFINITE = "NONFINITE"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"


@dataclass(frozen=True)
class LivePathResult:
    status: LivePathStatus
    candidate: Optional[CanonicalActionCandidate]
    trajectory_points: Optional[List[TrajectoryPoint]]
    reason: str
    planner_provenance: str
    coordinate_frame: str = "joint"
    n_joints: int = _EXPECTED_JOINTS


def _first_actuator_command(plan) -> Optional[object]:
    actions = getattr(plan, "actions", None)
    if not actions:
        return None
    return actions[0]


def plan_to_trajectory_candidate(
    *,
    action_id: str,
    plan,
    world_version: str,
    q0: np.ndarray,
    dt: float = 0.1,
    steps: int = 5,
    planner_provenance: str,
    expected_state_version: Optional[str] = None,
) -> LivePathResult:
    """Map a real ``Plan`` to an ACP candidate + joint trajectory (fail-closed)."""
    # Identity binding: candidate must be evaluated against the state it was
    # planned on. A caller-supplied expected_state_version guards A-vs-B mixups.
    if expected_state_version is not None and expected_state_version != world_version:
        return LivePathResult(LivePathStatus.IDENTITY_MISMATCH, None, None,
                              "world-state identity mismatch", planner_provenance)

    cmd = _first_actuator_command(plan)
    if cmd is None:
        return LivePathResult(LivePathStatus.MISSING_TRAJECTORY, None, None,
                              "plan has no actions", planner_provenance)

    # Emergency stop / explicit stop -> a zero-velocity (inherently safe) traj.
    emergency = bool(getattr(cmd, "emergency_stop", False))
    vel = getattr(cmd, "target_velocities", None)

    if emergency and vel is None:
        vel = np.zeros(_EXPECTED_JOINTS)
    if vel is None:
        # e.g. a gripper (grasp/release) command: no joint trajectory exists ->
        # unsupported for physical trajectory validation (do NOT fabricate one).
        return LivePathResult(LivePathStatus.UNSUPPORTED_COMMAND, None, None,
                              "command has no joint target_velocities "
                              "(non-locomotion / gripper command)", planner_provenance)

    vel = np.asarray(vel, dtype=np.float64)
    q0 = np.asarray(q0, dtype=np.float64)
    if vel.ndim != 1 or vel.shape[0] != _EXPECTED_JOINTS or q0.shape[0] != _EXPECTED_JOINTS:
        return LivePathResult(LivePathStatus.DIMENSION_MISMATCH, None, None,
                              f"expected {_EXPECTED_JOINTS}-joint command/state, got "
                              f"vel{tuple(vel.shape)} q0{tuple(q0.shape)}",
                              planner_provenance)
    if not (np.all(np.isfinite(vel)) and np.all(np.isfinite(q0))):
        return LivePathResult(LivePathStatus.NONFINITE, None, None,
                              "NaN/Inf in command or initial state", planner_provenance)

    trajectory = velocity_command_to_trajectory(q0, vel, dt=dt, steps=steps)
    candidate = CanonicalActionCandidate(
        candidate_id=action_id, action_type=ActionType.MANIPULATE,
        trajectory_ref=f"{action_id}:live", target="", expected_duration_s=dt * steps,
        max_speed=0.0, max_accel=0.0, stopping_margin_s=0.0, collision_margin_m=0.0,
        stability_margin=0.0, goal_progress=0.5, energy_estimate=0.0,
        origin_state_version=world_version,
        metadata={"planner_provenance": planner_provenance,
                  "coordinate_frame": "joint", "n_joints": str(_EXPECTED_JOINTS)})
    return LivePathResult(LivePathStatus.SUPPORTED, candidate, trajectory,
                          "ok", planner_provenance)
