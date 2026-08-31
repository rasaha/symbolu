"""Operating constraints — hard, non-compensatory limits (distinct from preferences).

Hard operating limits are represented SEPARATELY from optimization preferences (which live
in :mod:`.policy`). A hard constraint is *non-compensatory*: a cheaper or otherwise
higher-scoring candidate can NEVER overcome a quota, safety, validity, or policy violation.
Phase 3 filters candidates against these constraints BEFORE any weighted scoring runs, so an
infeasible candidate is removed from consideration rather than out-scored.

Fields (repository-appropriate equivalents of the required concepts):
  * ``min_capacity`` / ``max_capacity`` — absolute floor/ceiling for the primary resource.
  * ``allowed_step`` — permitted change increment (e.g. scale by multiples of 1 or 2).
  * ``regional_quota`` — a hard provider/regional capacity ceiling (>= max_capacity check).
  * ``cooldown_seconds`` + ``last_change_at`` — minimum change interval / cooldown.
  * ``forecast_validity_seconds`` — how long a forecast is considered current.
  * ``protect_slo`` / ``protect_error_budget`` — reliability protections that forbid
    scale-down while the state shows an active SLO/error-budget breach.
  * ``dependency_capacity_ceiling`` — a supplied max on a named downstream resource.
  * ``prohibited_actions`` — action kinds that are unavailable/forbidden right now.
  * ``max_cost_increase_minor`` — maximum permitted absolute cost increase (minor units).
  * ``safety_margin_fraction`` — optional operator-defined coverage margin on the forecast.

Every threshold is explicit, finite, validated, and bound (via :meth:`digest`) into the
recommendation evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple

from ..canonical.serialization import content_digest

OPERATING_CONSTRAINTS_SCHEMA_VERSION = "capacity-operating-constraints-1"


class ConstraintError(ValueError):
    """Raised when an operating-constraint set is malformed (fail closed)."""


class ConstraintViolationKind(str, Enum):
    """Typed reasons a candidate fails hard-constraint filtering (non-compensatory)."""

    BELOW_MIN_CAPACITY = "below_min_capacity"
    ABOVE_MAX_CAPACITY = "above_max_capacity"
    INVALID_STEP = "invalid_step"
    QUOTA_EXCEEDED = "quota_exceeded"
    COOLDOWN_ACTIVE = "cooldown_active"
    SLO_PROTECTED = "slo_protected"
    ERROR_BUDGET_PROTECTED = "error_budget_protected"
    DEPENDENCY_CEILING_EXCEEDED = "dependency_ceiling_exceeded"
    PROHIBITED_ACTION = "prohibited_action"
    MAX_COST_INCREASE_EXCEEDED = "max_cost_increase_exceeded"


def _finite_number(name: str, v: Any, *, allow_none: bool = False) -> None:
    if v is None:
        if allow_none:
            return
        raise ConstraintError(f"{name} is required")
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ConstraintError(f"{name} must be a finite number")


@dataclass(frozen=True)
class OperatingConstraints:
    """Immutable set of hard operating limits for one recommendation decision."""

    min_capacity: int
    max_capacity: int
    allowed_step: int = 1
    regional_quota: Optional[int] = None
    cooldown_seconds: float = 0.0
    last_change_at: Optional["datetime"] = None  # type: ignore[name-defined]
    forecast_validity_seconds: Optional[float] = None
    protect_slo: bool = False
    protect_error_budget: bool = False
    dependency_capacity_ceiling: Mapping[str, int] = field(default_factory=dict)
    prohibited_actions: Tuple[str, ...] = ()
    max_cost_increase_minor: Optional[int] = None
    safety_margin_fraction: float = 0.0
    schema_version: str = OPERATING_CONSTRAINTS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        from datetime import datetime  # local import; no module-level datetime dependency
        for name in ("min_capacity", "max_capacity", "allowed_step"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise ConstraintError(f"{name} must be an int")
        if self.min_capacity < 0:
            raise ConstraintError("min_capacity must be >= 0")
        if self.max_capacity < self.min_capacity:
            raise ConstraintError("max_capacity must be >= min_capacity")
        if self.allowed_step < 1:
            raise ConstraintError("allowed_step must be >= 1")
        if self.regional_quota is not None:
            if isinstance(self.regional_quota, bool) or not isinstance(self.regional_quota, int) or self.regional_quota < 0:
                raise ConstraintError("regional_quota must be an int >= 0 or None")
        _finite_number("cooldown_seconds", self.cooldown_seconds)
        if self.cooldown_seconds < 0:
            raise ConstraintError("cooldown_seconds must be >= 0")
        if self.last_change_at is not None and not isinstance(self.last_change_at, datetime):
            raise ConstraintError("last_change_at must be a datetime or None")
        if self.forecast_validity_seconds is not None:
            _finite_number("forecast_validity_seconds", self.forecast_validity_seconds)
            if self.forecast_validity_seconds <= 0:
                raise ConstraintError("forecast_validity_seconds must be > 0 or None")
        for name in ("protect_slo", "protect_error_budget"):
            if not isinstance(getattr(self, name), bool):
                raise ConstraintError(f"{name} must be a bool")
        if not isinstance(self.dependency_capacity_ceiling, Mapping):
            raise ConstraintError("dependency_capacity_ceiling must be a mapping")
        for k, v in self.dependency_capacity_ceiling.items():
            if not isinstance(k, str) or k == "":
                raise ConstraintError("dependency_capacity_ceiling keys must be non-empty strings")
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ConstraintError("dependency_capacity_ceiling values must be ints >= 0")
        object.__setattr__(self, "dependency_capacity_ceiling", dict(self.dependency_capacity_ceiling))
        if not isinstance(self.prohibited_actions, tuple):
            object.__setattr__(self, "prohibited_actions", tuple(self.prohibited_actions))
        for a in self.prohibited_actions:
            if not isinstance(a, str) or a == "":
                raise ConstraintError("prohibited_actions must be non-empty strings")
        if self.max_cost_increase_minor is not None:
            if isinstance(self.max_cost_increase_minor, bool) or not isinstance(self.max_cost_increase_minor, int) or self.max_cost_increase_minor < 0:
                raise ConstraintError("max_cost_increase_minor must be an int >= 0 or None")
        _finite_number("safety_margin_fraction", self.safety_margin_fraction)
        if not (0.0 <= self.safety_margin_fraction <= 1.0):
            raise ConstraintError("safety_margin_fraction must be in [0, 1]")
        # NOTE: a regional_quota below min_capacity is NOT a construction error — it is a
        # genuine misconfiguration the recommendation pipeline detects at decision time and
        # reports as a typed QUOTA_CONFLICT abstention (fail closed), rather than silently
        # producing an impossible feasible region here.

    def effective_ceiling(self) -> int:
        """The binding capacity ceiling: min(max_capacity, regional_quota)."""
        if self.regional_quota is None:
            return self.max_capacity
        return min(self.max_capacity, self.regional_quota)

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "min_capacity": self.min_capacity,
            "max_capacity": self.max_capacity,
            "allowed_step": self.allowed_step,
            "regional_quota": self.regional_quota,
            "cooldown_seconds": self.cooldown_seconds,
            "last_change_at": self.last_change_at,
            "forecast_validity_seconds": self.forecast_validity_seconds,
            "protect_slo": self.protect_slo,
            "protect_error_budget": self.protect_error_budget,
            "dependency_capacity_ceiling": dict(self.dependency_capacity_ceiling),
            "prohibited_actions": list(self.prohibited_actions),
            "max_cost_increase_minor": self.max_cost_increase_minor,
            "safety_margin_fraction": self.safety_margin_fraction,
        }

    def digest(self) -> str:
        return content_digest("capacity_operating_constraints", self.schema_version,
                              self.to_canonical_dict())

    @classmethod
    def from_dict(cls, data: Any) -> "OperatingConstraints":
        if not isinstance(data, Mapping):
            raise ConstraintError("constraints must be a mapping")
        known = {
            "schema_version", "min_capacity", "max_capacity", "allowed_step", "regional_quota",
            "cooldown_seconds", "last_change_at", "forecast_validity_seconds", "protect_slo",
            "protect_error_budget", "dependency_capacity_ceiling", "prohibited_actions",
            "max_cost_increase_minor", "safety_margin_fraction",
        }
        unknown = set(data) - known
        if unknown:
            raise ConstraintError(f"unknown constraint field(s): {sorted(unknown)}")
        for req in ("min_capacity", "max_capacity"):
            if req not in data:
                raise ConstraintError(f"constraints require '{req}'")
        return cls(
            min_capacity=data["min_capacity"],
            max_capacity=data["max_capacity"],
            allowed_step=data.get("allowed_step", 1),
            regional_quota=data.get("regional_quota"),
            cooldown_seconds=data.get("cooldown_seconds", 0.0),
            last_change_at=data.get("last_change_at"),
            forecast_validity_seconds=data.get("forecast_validity_seconds"),
            protect_slo=data.get("protect_slo", False),
            protect_error_budget=data.get("protect_error_budget", False),
            dependency_capacity_ceiling=data.get("dependency_capacity_ceiling") or {},
            prohibited_actions=tuple(data.get("prohibited_actions") or ()),
            max_cost_increase_minor=data.get("max_cost_increase_minor"),
            safety_margin_fraction=data.get("safety_margin_fraction", 0.0),
            schema_version=data.get("schema_version", OPERATING_CONSTRAINTS_SCHEMA_VERSION),
        )


__all__ = [
    "OPERATING_CONSTRAINTS_SCHEMA_VERSION",
    "ConstraintError",
    "ConstraintViolationKind",
    "OperatingConstraints",
]
