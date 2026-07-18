"""ConstraintResult envelope + constraint classification.

A ``ConstraintResult`` is the deterministic outcome of evaluating one constraint
against one candidate. HARD constraints are non-compensatory: a single failed
HARD result makes a candidate inadmissible regardless of any soft objective or
advisory feature (enforced in ``action_selection.py``).

Standard-library only.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import SchemaValidationError
from .identity import normalize_float

_COMPARATORS = frozenset({"<", "<=", ">", ">=", "==", "!=", "bool"})


class ConstraintKind(str, Enum):
    HARD = "HARD"   # non-compensatory; failure => inadmissible
    SOFT = "SOFT"   # objective/preference; never gates admissibility


@dataclass(frozen=True)
class ConstraintResult:
    """Deterministic result of evaluating one constraint on one candidate."""
    constraint_id: str
    kind: ConstraintKind
    passed: bool
    observed_value: float
    required_bound: float
    comparator: str            # one of _COMPARATORS
    reason_code: str           # dispositive reason code (e.g. COLLISION_MARGIN)
    evidence_ref: str          # world-state version / predictor identity it used

    def __post_init__(self) -> None:
        if not self.constraint_id:
            raise SchemaValidationError("constraint_id must be non-empty")
        if not isinstance(self.kind, ConstraintKind):
            raise SchemaValidationError("kind must be ConstraintKind")
        normalize_float(self.observed_value, field="ConstraintResult.observed_value")
        normalize_float(self.required_bound, field="ConstraintResult.required_bound")
        if self.comparator not in _COMPARATORS:
            raise SchemaValidationError(
                f"comparator must be one of {sorted(_COMPARATORS)}")
        if not self.reason_code:
            raise SchemaValidationError("reason_code must be non-empty")

    @property
    def is_hard(self) -> bool:
        return self.kind is ConstraintKind.HARD

    @property
    def blocks_admissibility(self) -> bool:
        """A failed HARD constraint blocks admissibility; soft never does."""
        return self.is_hard and not self.passed


class NoConfiguredConstraintsEvaluator:
    """Reference HardConstraintEvaluator with NO constraints configured.

    Returns an empty result set for every candidate. Composed with the selector
    this proves the fail-closed path: no hard evidence => not admissible =>
    ``NO_SAFE_ACTION`` (never a permissive default). It never authorizes.
    """

    safety_critical = True

    def evaluate(self, candidate, world_state) -> tuple:  # -> Tuple[ConstraintResult,...]
        return ()
