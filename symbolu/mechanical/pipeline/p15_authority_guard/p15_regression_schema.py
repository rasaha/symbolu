"""
P15 Regression Guard — Schema Definitions

Immutable snapshot structures for capturing P15 authority state
and recording violations when phases ≥ 16 attempt unauthorized modifications.

These dataclasses are FROZEN to guarantee immutability.
No field may be modified after construction.

Design Principles:
- Immutable (frozen dataclasses)
- Deterministic (no random/time-dependent fields in core structures)
- Complete (captures all authority-bearing decisions from PO1–P15)
- Serializable (supports logging/audit)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Literal


# ============================================================================
# VIOLATION TYPE ENUM
# ============================================================================


class ViolationType(str, Enum):
    """
    Classification of P15 regression violations.

    Each violation type represents a specific category of unauthorized
    modification attempted by a phase ≥ 16.

    INTENT_OVERRIDE: Attempt to change the intent classification
    REGIME_ESCALATION: Attempt to change or escalate the operational regime
    DISCOURSE_MUTATION: Attempt to modify the discourse act
    POSTURE_MUTATION: Attempt to change the response posture
    ACTION_EXPANSION: Attempt to expand the allowed action set
    BLOCKED_UNBLOCK: Attempt to unblock a blocked state
    AUTHORITY_REINTRODUCTION: Attempt to introduce new authority signals
    """
    INTENT_OVERRIDE = "INTENT_OVERRIDE"
    REGIME_ESCALATION = "REGIME_ESCALATION"
    DISCOURSE_MUTATION = "DISCOURSE_MUTATION"
    POSTURE_MUTATION = "POSTURE_MUTATION"
    ACTION_EXPANSION = "ACTION_EXPANSION"
    BLOCKED_UNBLOCK = "BLOCKED_UNBLOCK"
    AUTHORITY_REINTRODUCTION = "AUTHORITY_REINTRODUCTION"


# ============================================================================
# IMMUTABLE SNAPSHOT
# ============================================================================


@dataclass(frozen=True)
class P15AuthoritySnapshot:
    """
    Immutable snapshot of all authority-bearing decisions from PO1–P15.

    This snapshot is captured ONCE immediately after P15 completes.
    It serves as the reference against which all subsequent phases
    are validated. Any deviation from this snapshot is a violation.

    Fields:
        intent: IntentType value as string (from PO2)
        regime: OperationalRegime value as string (from P6)
        discourse_act: DiscourseAct value as string (from P7)
        response_posture: ResponsePosture value as string (from PO2)
        interaction_mode: InteractionMode value as string (from P15)
        allowed_actions: Frozen set of allowed action class strings (from PO3)
        blocked: Whether the pipeline is in blocked state
        grounding_mode: ObservationMode value as string (from PO1)

    Invariants:
        - All fields are immutable (frozen dataclass)
        - allowed_actions is a frozenset (cannot be expanded)
        - blocked is a boolean (cannot transition True → False)
    """
    intent: str
    regime: str
    discourse_act: str
    response_posture: str
    interaction_mode: str
    allowed_actions: FrozenSet[str]
    blocked: bool
    grounding_mode: str = ""

    # Metadata for audit/tracing (does not affect validation)
    snapshot_version: str = "1.0.0"
    captured_at_phase: int = 15

    def __post_init__(self) -> None:
        """Validate snapshot invariants at construction time."""
        # Validate string fields are non-empty
        if not self.intent:
            raise ValueError("P15AuthoritySnapshot.intent cannot be empty")
        if not self.regime:
            raise ValueError("P15AuthoritySnapshot.regime cannot be empty")
        if not self.discourse_act:
            raise ValueError("P15AuthoritySnapshot.discourse_act cannot be empty")
        if not self.response_posture:
            raise ValueError("P15AuthoritySnapshot.response_posture cannot be empty")
        if not self.interaction_mode:
            raise ValueError("P15AuthoritySnapshot.interaction_mode cannot be empty")

        # Validate allowed_actions is a frozenset
        if not isinstance(self.allowed_actions, frozenset):
            raise ValueError(
                f"P15AuthoritySnapshot.allowed_actions must be a frozenset, "
                f"got {type(self.allowed_actions).__name__}"
            )

        # Validate blocked is a boolean
        if not isinstance(self.blocked, bool):
            raise ValueError(
                f"P15AuthoritySnapshot.blocked must be a bool, "
                f"got {type(self.blocked).__name__}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/audit."""
        return {
            "intent": self.intent,
            "regime": self.regime,
            "discourse_act": self.discourse_act,
            "response_posture": self.response_posture,
            "interaction_mode": self.interaction_mode,
            "allowed_actions": sorted(self.allowed_actions),
            "blocked": self.blocked,
            "grounding_mode": self.grounding_mode,
            "snapshot_version": self.snapshot_version,
            "captured_at_phase": self.captured_at_phase,
        }


# ============================================================================
# VIOLATION RECORD
# ============================================================================


@dataclass(frozen=True)
class P15RegressionViolation:
    """
    Immutable record of a single P15 regression violation.

    Each violation captures:
    - Which phase attempted the violation
    - Which field was violated
    - What value was expected (from snapshot)
    - What value was observed (current state)
    - The type of violation

    This is an audit record, not a correction mechanism.
    Violations are collected and then raised as an exception.
    """
    phase: int
    field: str
    expected: Any
    observed: Any
    violation_type: ViolationType
    reason: str = ""

    def __post_init__(self) -> None:
        """Validate violation record invariants."""
        # Phase must be >= 16
        if self.phase < 16:
            raise ValueError(
                f"P15RegressionViolation.phase must be >= 16, got {self.phase}"
            )

        # Field must be non-empty
        if not self.field:
            raise ValueError("P15RegressionViolation.field cannot be empty")

        # Violation type must be valid
        if not isinstance(self.violation_type, ViolationType):
            raise ValueError(
                f"P15RegressionViolation.violation_type must be ViolationType, "
                f"got {type(self.violation_type).__name__}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/audit."""
        return {
            "phase": self.phase,
            "field": self.field,
            "expected": _serialize_value(self.expected),
            "observed": _serialize_value(self.observed),
            "violation_type": self.violation_type.value,
            "reason": self.reason,
        }


# ============================================================================
# EXCEPTION CLASS
# ============================================================================


class P15RegressionViolationError(Exception):
    """
    Exception raised when one or more P15 regression violations are detected.

    This exception is DETERMINISTIC and NON-BYPASSABLE.
    It cannot be caught and ignored without explicit intent.

    The exception contains all violations detected, allowing for
    complete audit of what went wrong.
    """

    def __init__(
        self,
        violations: List[P15RegressionViolation],
        phase: int,
        message: str = "",
    ) -> None:
        """
        Initialize the violation error.

        Args:
            violations: List of all detected violations
            phase: The phase number that triggered the violation
            message: Optional additional message
        """
        self.violations = violations
        self.phase = phase

        # Build comprehensive error message
        violation_summaries = []
        for v in violations:
            violation_summaries.append(
                f"  - {v.violation_type.value}: field='{v.field}', "
                f"expected={_serialize_value(v.expected)}, "
                f"observed={_serialize_value(v.observed)}"
            )

        full_message = (
            f"P15 Regression Guard: {len(violations)} violation(s) detected "
            f"at phase {phase}.\n"
            f"Phases >= 16 may NOT modify authority decisions from PO1-P15.\n"
            f"Violations:\n" + "\n".join(violation_summaries)
        )

        if message:
            full_message = f"{message}\n{full_message}"

        super().__init__(full_message)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/audit."""
        return {
            "error_type": "P15RegressionViolationError",
            "phase": self.phase,
            "violation_count": len(self.violations),
            "violations": [v.to_dict() for v in self.violations],
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _serialize_value(value: Any) -> Any:
    """
    Serialize a value for logging/audit purposes.

    Handles frozensets, enums, and other special types.
    """
    if isinstance(value, frozenset):
        return sorted(value)
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    "ViolationType",
    "P15AuthoritySnapshot",
    "P15RegressionViolation",
    "P15RegressionViolationError",
]
