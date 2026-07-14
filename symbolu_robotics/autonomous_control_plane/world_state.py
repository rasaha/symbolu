"""CanonicalWorldState envelope.

An immutable, deterministically-identifiable snapshot of the state ACP decides
on. The ``version`` property is the content identity: any material change to the
snapshot yields a new version, which is what commit-time revalidation checks
against (see ``authorization.py``).

Standard-library only. No numpy / ROS / hardware dependency (Phase-0 core rule).
The schema is intentionally NOT claimed complete for every robotics domain;
``extensions`` is the explicit, identity-bearing extension point.
"""
from __future__ import annotations

import types
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Mapping

from .errors import SchemaValidationError
from .identity import identity, normalize_float

_DOMAIN = "world_state"


class OperatingMode(str, Enum):
    """Coarse operating mode the decision is conditioned on."""
    AUTONOMOUS = "AUTONOMOUS"
    DEGRADED = "DEGRADED"
    MANUAL = "MANUAL"
    MAINTENANCE = "MAINTENANCE"


@dataclass(frozen=True)
class Pose:
    """6-DoF pose. SE(2) users set z/roll/pitch to 0.0."""
    x: float
    y: float
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

    def __post_init__(self) -> None:
        for f in ("x", "y", "z", "roll", "pitch", "yaw"):
            normalize_float(getattr(self, f), field=f"Pose.{f}")


@dataclass(frozen=True)
class Velocity:
    """Body-frame velocity summary."""
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    yaw_rate: float = 0.0

    def __post_init__(self) -> None:
        for f in ("vx", "vy", "vz", "yaw_rate"):
            normalize_float(getattr(self, f), field=f"Velocity.{f}")

    @property
    def speed(self) -> float:
        return (self.vx * self.vx + self.vy * self.vy + self.vz * self.vz) ** 0.5


@dataclass(frozen=True)
class FreshnessSummary:
    """Deterministic freshness rollup over the input sources/predictors."""
    worst_case_age_s: float
    n_fresh: int
    n_stale: int
    all_within_budget: bool

    def __post_init__(self) -> None:
        normalize_float(self.worst_case_age_s, field="FreshnessSummary.worst_case_age_s")
        if self.worst_case_age_s < 0:
            raise SchemaValidationError("worst_case_age_s must be >= 0")
        if self.n_fresh < 0 or self.n_stale < 0:
            raise SchemaValidationError("n_fresh / n_stale must be >= 0")


@dataclass(frozen=True)
class CanonicalWorldState:
    """Immutable snapshot ACP decides on. ``version`` == content identity."""
    tick: int                       # monotonic sequence id
    observation_time_s: float       # monotonic observation timestamp (seconds)
    pose: Pose
    velocity: Velocity
    environment_version: str        # map / environment model version tag
    mission_id: str                 # active mission identifier
    freshness: FreshnessSummary
    operating_mode: OperatingMode
    # Explicit, identity-bearing extension point for domain-specific fields.
    extensions: Mapping[str, str] = field(default_factory=dict)
    # Free-text label: NOT part of identity (does not change the version).
    label: str = field(default="", metadata={"identity": False})

    def __post_init__(self) -> None:
        if self.tick < 0:
            raise SchemaValidationError("tick must be >= 0")
        normalize_float(self.observation_time_s,
                        field="CanonicalWorldState.observation_time_s")
        if not self.mission_id:
            raise SchemaValidationError("mission_id must be non-empty")
        if not isinstance(self.operating_mode, OperatingMode):
            raise SchemaValidationError("operating_mode must be OperatingMode")
        # Freeze extensions into a read-only mapping with validated str keys/values.
        ext = dict(self.extensions)
        for k, v in ext.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise SchemaValidationError(
                    "extensions keys and values must be str (domain-neutral, "
                    "identity-stable); use a typed subclass for richer data")
        object.__setattr__(self, "extensions", types.MappingProxyType(ext))

    @property
    def version(self) -> str:
        """Content identity of this snapshot (the state-version/hash)."""
        return identity(self, domain=_DOMAIN)
