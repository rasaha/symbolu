"""Typed physical-safety evidence contract (Phase 2).

An immutable, deterministically-identifiable bundle of physical-safety evidence
for ONE candidate, produced by a real safety-module adapter (see
``autonomous_control_plane/safety_adapters/``). This module is STDLIB-ONLY: it is
the typed contract; the numpy/safety-module integration lives in the adapter
subpackage so the ACP core stays production-independent.

Every value carries units (documented per field), the evaluator source + version,
the world-state version, the candidate identity, an observation timestamp +
freshness, and a validity status. Construction fails loudly on NaN/Inf and
malformed fields; the adapter is responsible for STALE / EVALUATOR_FAILED /
binding failures (which map to fail-closed HARD constraint results).

Field units (all SI unless noted):
  min_obstacle_clearance_m   metres
  time_to_collision_s        seconds
  stopping_distance_m        metres
  available_stopping_margin_m metres
  max_velocity_ratio         fraction of the joint velocity limit (>1 = breach)
  max_accel_ratio            fraction of the joint acceleration limit
  max_jerk_ratio             fraction of the joint jerk limit
  safety_score               [0,1], higher = safer (from ValidationReport)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

from .errors import SchemaValidationError
from .identity import identity, normalize_float

_DOMAIN = "physical_evidence"


class PhysicalValidity(str, Enum):
    VALID = "VALID"                    # evidence computed successfully, fresh
    STALE = "STALE"                    # freshness exceeded the limit
    EVALUATOR_FAILED = "EVALUATOR_FAILED"  # the safety module raised
    MISSING = "MISSING"               # required evidence not available


def _opt_finite(v: Optional[float], field_name: str) -> Optional[float]:
    if v is None:
        return None
    return normalize_float(float(v), field=field_name)


@dataclass(frozen=True)
class PhysicalEvidence:
    """Per-candidate physical-safety evidence from a real evaluator."""
    candidate_identity: str            # binds to the exact candidate
    state_version: str                 # binds to the exact world-state version
    evaluator: str                     # e.g. "TrajectoryValidator"
    evaluator_version: str
    observation_time_s: float
    freshness_s: float                 # age of the underlying observation
    coordinate_frame: str              # "joint" | "world_se2" | "ee"
    validity: PhysicalValidity
    # Booleans (None = not evaluated by this evaluator).
    trajectory_valid: Optional[bool] = None
    is_safe: Optional[bool] = None
    velocity_ok: Optional[bool] = None
    accel_ok: Optional[bool] = None
    jerk_ok: Optional[bool] = None
    workspace_ok: Optional[bool] = None
    collision_free: Optional[bool] = None
    self_collision_free: Optional[bool] = None
    human_proximity_ok: Optional[bool] = None
    kinematic_feasible: Optional[bool] = None
    dynamic_stable: Optional[bool] = None
    actuator_ok: Optional[bool] = None
    map_lane_valid: Optional[bool] = None
    # Numerics (units above; None = not measured).
    safety_score: Optional[float] = None
    min_obstacle_clearance_m: Optional[float] = None
    time_to_collision_s: Optional[float] = None
    stopping_distance_m: Optional[float] = None
    available_stopping_margin_m: Optional[float] = None
    max_velocity_ratio: Optional[float] = None
    max_accel_ratio: Optional[float] = None
    max_jerk_ratio: Optional[float] = None
    limit_violations: Tuple[str, ...] = ()
    # Fields not part of identity (diagnostics).
    note: str = field(default="", metadata={"identity": False})

    def __post_init__(self) -> None:
        if not self.candidate_identity or not self.state_version:
            raise SchemaValidationError("candidate_identity/state_version required")
        if not isinstance(self.validity, PhysicalValidity):
            raise SchemaValidationError("validity must be PhysicalValidity")
        normalize_float(self.observation_time_s, field="observation_time_s")
        normalize_float(self.freshness_s, field="freshness_s")
        if self.freshness_s < 0:
            raise SchemaValidationError("freshness_s must be >= 0")
        for f in ("safety_score", "min_obstacle_clearance_m", "time_to_collision_s",
                  "stopping_distance_m", "available_stopping_margin_m",
                  "max_velocity_ratio", "max_accel_ratio", "max_jerk_ratio"):
            _opt_finite(getattr(self, f), f)  # raises NonFiniteValueError on NaN/Inf
        if not isinstance(self.limit_violations, tuple):
            raise SchemaValidationError("limit_violations must be a tuple")

    @property
    def is_usable(self) -> bool:
        """Evidence may inform admissibility only if VALID (fail-closed else)."""
        return self.validity is PhysicalValidity.VALID

    @property
    def identity(self) -> str:
        return identity(self, domain=_DOMAIN)
