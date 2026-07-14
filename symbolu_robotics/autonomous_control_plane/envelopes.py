"""CanonicalActionCandidate envelope + ActionDecision outcomes.

A candidate carries a *reference* to its trajectory/command (not the heavy array)
plus the deterministic scalar features admissibility and selection need. It binds
``origin_state_version`` so a candidate generated against a stale world can be
detected. ``ActionDecision`` is a closed set of explicit outcomes — there is no
probabilistic "allow score."

Standard-library only.
"""
from __future__ import annotations

import types
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .errors import SchemaValidationError
from .identity import identity, normalize_float

_DOMAIN = "action_candidate"


class ActionType(str, Enum):
    MOVE = "MOVE"
    STOP = "STOP"
    HOLD = "HOLD"
    MANIPULATE = "MANIPULATE"
    YIELD = "YIELD"
    CUSTOM = "CUSTOM"


class ActionDecision(str, Enum):
    """Closed set of decision outcomes. No probabilistic allow-score exists."""
    EXECUTE = "EXECUTE"
    EXECUTE_WITH_CONSTRAINTS = "EXECUTE_WITH_CONSTRAINTS"
    REPLAN = "REPLAN"
    REQUEST_MORE_OBSERVATION = "REQUEST_MORE_OBSERVATION"
    DEGRADE_MODE = "DEGRADE_MODE"
    SAFE_STOP = "SAFE_STOP"
    NO_SAFE_ACTION = "NO_SAFE_ACTION"


@dataclass(frozen=True)
class CanonicalActionCandidate:
    """Immutable, deterministically-identifiable action candidate."""
    candidate_id: str                  # stable id within a tick
    action_type: ActionType
    trajectory_ref: str                # reference/id to the trajectory or command
    target: str                        # target reference (pose id / goal id / "")
    expected_duration_s: float
    max_speed: float
    max_accel: float
    stopping_margin_s: float           # time-to-stop / escape margin
    collision_margin_m: float
    stability_margin: float
    goal_progress: float               # [0, 1]
    energy_estimate: float
    origin_state_version: str          # world-state version it was generated on
    metadata: Mapping[str, str] = field(default_factory=dict)
    # Free-text provenance: NOT part of identity.
    provenance: str = field(default="", metadata={"identity": False})

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise SchemaValidationError("candidate_id must be non-empty")
        if not isinstance(self.action_type, ActionType):
            raise SchemaValidationError("action_type must be ActionType")
        if not self.origin_state_version:
            raise SchemaValidationError("origin_state_version must be non-empty")
        for f in ("expected_duration_s", "max_speed", "max_accel",
                  "stopping_margin_s", "collision_margin_m", "stability_margin",
                  "goal_progress", "energy_estimate"):
            normalize_float(getattr(self, f), field=f"CanonicalActionCandidate.{f}")
        if self.expected_duration_s < 0 or self.max_speed < 0 or self.max_accel < 0:
            raise SchemaValidationError("duration/speed/accel must be >= 0")
        if not (0.0 <= self.goal_progress <= 1.0):
            raise SchemaValidationError("goal_progress must be in [0, 1]")
        meta = dict(self.metadata)
        for k, v in meta.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise SchemaValidationError("metadata keys/values must be str")
        object.__setattr__(self, "metadata", types.MappingProxyType(meta))

    @property
    def identity(self) -> str:
        return identity(self, domain=_DOMAIN)
