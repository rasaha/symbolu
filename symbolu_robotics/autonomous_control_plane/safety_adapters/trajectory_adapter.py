"""Real TrajectoryValidator -> ACP physical-evidence adapter (Phase 2).

Wraps the repository's REAL ``symbolu_robotics.safety.trajectory_validator``
(deterministic joint-space validator; velocity/accel/jerk/workspace/collision/
self-collision/human checks with the module's own thresholds) and maps its
``ValidationReport`` to a typed ``PhysicalEvidence`` bundle + per-category HARD
``ConstraintResult``s. No formulas are re-implemented; the real validator does
the work. Every result binds the exact candidate identity + world-state version.

Fail-closed:
  * stale evidence (freshness > max_stale_s) -> validity STALE + a failing HARD
    ``STALE_PHYSICAL_EVIDENCE`` result (never EXECUTE);
  * validator raises -> validity EVALUATOR_FAILED + a failing HARD
    ``EVALUATOR_FAILED`` result;
  * missing trajectory -> validity MISSING + failing HARD ``MISSING_TRAJECTORY``.

Determinism: the validator's only clock use is ``validation_time_ms`` (report
metadata); it never enters the evidence identity or any ConstraintResult, so the
mapped output is a deterministic function of (trajectory, obstacles, human).
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import numpy as np

from symbolu_robotics.safety.trajectory_validator import (
    TrajectoryPoint, TrajectoryValidator, TrajectoryValidatorConfig)

from ..constraints import ConstraintKind, ConstraintResult
from ..envelopes import CanonicalActionCandidate
from ..physical_evidence import PhysicalEvidence, PhysicalValidity

_EVALUATOR = "TrajectoryValidator"
_EVALUATOR_VERSION = "symbolu_robotics.safety.trajectory_validator@v1"
# Immediate-collision threshold the validator itself uses to invalidate a point.
_TTC_FLOOR_S = 0.1


def _has(violations: Sequence[str], keyword: str) -> bool:
    return any(keyword in v.lower() for v in violations)


def _hard(cid: str, passed: bool, observed: float, bound: float, comparator: str,
          reason: str, evidence_ref: str) -> ConstraintResult:
    return ConstraintResult(
        constraint_id=cid, kind=ConstraintKind.HARD, passed=passed,
        observed_value=observed, required_bound=bound, comparator=comparator,
        reason_code=reason, evidence_ref=evidence_ref)


class TrajectoryValidatorAdapter:
    """Real physical-safety evaluator for a joint-trajectory candidate."""

    evaluator = _EVALUATOR
    evaluator_version = _EVALUATOR_VERSION
    safety_critical = True

    def __init__(self, config: Optional[TrajectoryValidatorConfig] = None,
                 max_stale_s: float = 0.2):
        self._validator = TrajectoryValidator(config)
        self._max_stale_s = max_stale_s

    def _fail_closed(self, candidate, world_version, now_s, freshness_s,
                     validity: PhysicalValidity, reason: str):
        ev_ref = f"{_EVALUATOR}|{world_version}|{candidate.identity}"
        ev = PhysicalEvidence(
            candidate_identity=candidate.identity, state_version=world_version,
            evaluator=_EVALUATOR, evaluator_version=_EVALUATOR_VERSION,
            observation_time_s=now_s, freshness_s=freshness_s,
            coordinate_frame="joint", validity=validity, note=reason)
        cr = _hard(reason, passed=False, observed=0.0, bound=1.0,
                   comparator="bool", reason=reason, evidence_ref=ev_ref)
        return ev, (cr,)

    def evaluate(
        self, *,
        candidate: CanonicalActionCandidate,
        trajectory_points: List[TrajectoryPoint],
        obstacles: Optional[List[Tuple[np.ndarray, float]]] = None,
        human_position: Optional[np.ndarray] = None,
        human_velocity: Optional[np.ndarray] = None,
        world_version: str,
        now_s: float,
        observation_time_s: float,
        freshness_s: float,
    ) -> Tuple[PhysicalEvidence, Tuple[ConstraintResult, ...]]:
        # 1. Stale / missing gates (fail closed).
        if freshness_s > self._max_stale_s:
            return self._fail_closed(candidate, world_version, now_s, freshness_s,
                                     PhysicalValidity.STALE, "STALE_PHYSICAL_EVIDENCE")
        if not trajectory_points:
            return self._fail_closed(candidate, world_version, now_s, freshness_s,
                                     PhysicalValidity.MISSING, "MISSING_TRAJECTORY")

        # 2. Call the REAL validator (fail closed on any exception).
        try:
            self._validator.set_obstacles(list(obstacles or []))
            self._validator.set_human_state(human_position, human_velocity)
            report = self._validator.validate(trajectory_points)
        except Exception:  # noqa: BLE001 - safety module failure => fail closed
            return self._fail_closed(candidate, world_version, now_s, freshness_s,
                                     PhysicalValidity.EVALUATOR_FAILED,
                                     "EVALUATOR_FAILED")

        viol = report.limit_violations
        ev_ref = f"{_EVALUATOR}|{world_version}|{candidate.identity}"

        # 3. Categorize collision predictions by type.
        collision_ttc = [c.time_to_collision for c in report.collision_predictions
                         if "self" not in str(c.collision_type).lower()
                         and "human" not in str(c.collision_type).lower()]
        self_col = any("self" in str(c.collision_type).lower()
                       for c in report.collision_predictions)
        human_hi = any("human" in str(c.collision_type).lower() and c.severity > 0.8
                       for c in report.collision_predictions)
        min_ttc = min(collision_ttc) if collision_ttc else None
        collision_free = not any(t < _TTC_FLOOR_S for t in collision_ttc)

        pos_ok = not _has(viol, "position")
        vel_ok = not _has(viol, "velocity")
        acc_ok = not _has(viol, "acceleration")
        jerk_ok = not _has(viol, "jerk")
        ws_ok = not _has(viol, "workspace")

        # 4. Build typed physical evidence.
        ev = PhysicalEvidence(
            candidate_identity=candidate.identity, state_version=world_version,
            evaluator=_EVALUATOR, evaluator_version=_EVALUATOR_VERSION,
            observation_time_s=observation_time_s, freshness_s=freshness_s,
            coordinate_frame="joint", validity=PhysicalValidity.VALID,
            trajectory_valid=report.is_safe, is_safe=report.is_safe,
            velocity_ok=vel_ok, accel_ok=acc_ok, jerk_ok=jerk_ok,
            workspace_ok=ws_ok, collision_free=collision_free,
            self_collision_free=not self_col, human_proximity_ok=not human_hi,
            safety_score=float(report.safety_score),
            time_to_collision_s=(None if min_ttc is None else float(min_ttc)),
            limit_violations=tuple(viol))

        # 5. Emit per-category HARD constraints (granular explainability).
        results = [
            _hard("POSITION_LIMIT", pos_ok, 1.0 if pos_ok else 0.0, 1.0, "bool",
                  "POSITION_LIMIT" if pos_ok else "POSITION_LIMIT_VIOLATION", ev_ref),
            _hard("VELOCITY_LIMIT", vel_ok, 1.0 if vel_ok else 0.0, 1.0, "bool",
                  "VELOCITY_LIMIT" if vel_ok else "VELOCITY_LIMIT_VIOLATION", ev_ref),
            _hard("ACCEL_LIMIT", acc_ok, 1.0 if acc_ok else 0.0, 1.0, "bool",
                  "ACCEL_LIMIT" if acc_ok else "ACCEL_LIMIT_VIOLATION", ev_ref),
            _hard("JERK_LIMIT", jerk_ok, 1.0 if jerk_ok else 0.0, 1.0, "bool",
                  "JERK_LIMIT" if jerk_ok else "JERK_LIMIT_VIOLATION", ev_ref),
            _hard("WORKSPACE", ws_ok, 1.0 if ws_ok else 0.0, 1.0, "bool",
                  "WORKSPACE" if ws_ok else "WORKSPACE_VIOLATION", ev_ref),
            _hard("COLLISION_CLEARANCE", collision_free,
                  (min_ttc if min_ttc is not None else 999.0), _TTC_FLOOR_S, ">=",
                  "COLLISION_CLEARANCE" if collision_free else "COLLISION_PREDICTED",
                  ev_ref),
            _hard("SELF_COLLISION", not self_col, 0.0 if self_col else 1.0, 1.0,
                  "bool", "SELF_COLLISION" if not self_col else "SELF_COLLISION_PREDICTED",
                  ev_ref),
            _hard("HUMAN_PROXIMITY", not human_hi, 0.0 if human_hi else 1.0, 1.0,
                  "bool", "HUMAN_PROXIMITY" if not human_hi else "HUMAN_PROXIMITY_VIOLATION",
                  ev_ref),
        ]
        return ev, tuple(results)
