"""Structural completeness result (never a quality score).

Completeness answers "is the assessment structurally finished under the published
contract?" — required criteria present, required evidence bound, observations
valid, required uncertainty present, no prohibited evidence, no unresolved
blocking conflicts. It does NOT consider whether observation values are good or
bad. A fully-supported 1/5 may be COMPLETE; a favourable 5/5 with missing required
evidence is INCOMPLETE or BLOCKED.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .status import CompletenessStatus


@dataclass(frozen=True)
class CompletenessResult:
    status: CompletenessStatus
    required_criteria_total: int = 0
    satisfied_criteria: int = 0
    criteria_with_observations: int = 0
    blocking_conditions: tuple[str, ...] = field(default_factory=tuple)
    has_uncertainty: bool = False
    has_conflicts: bool = False

    @property
    def finalizable(self) -> bool:
        """Advisory finalization is permitted only for a COMPLETE* status."""
        return self.status in (
            CompletenessStatus.COMPLETE,
            CompletenessStatus.COMPLETE_WITH_UNCERTAINTY,
            CompletenessStatus.COMPLETE_WITH_CONFLICTS,
        )