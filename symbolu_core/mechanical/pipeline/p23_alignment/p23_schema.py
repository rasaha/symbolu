"""
P23 - Inner-Outer Alignment Observer Schema Definitions

This phase is observer-only and non-authoritative.

P23 observes whether the internal acoustic pressure (from P22) is aligned with
the externally allowed interaction mode (from P6 + P7). It exists to:
    - Report alignment or tension between acoustic motion and regime/discourse
    - Provide descriptive tags for observation purposes only
    - Never influence routing, delivery, or behavior

P23 MUST NOT:
    - Decide what to say
    - Decide how to say it
    - Gate or block output
    - Infer emotion or intent
    - Modify regime, discourse, or any upstream state
    - Feed data back into P1-P22
    - Cause any behavior change

P23 MUST:
    - Be deterministic
    - Be read-only
    - Be observer-only
    - Operate after P22
    - Never touch delivery decisions

CRITICAL ARCHITECTURAL INVARIANT:
    P23 is purely observational. It witnesses alignment without authority.
    The alignment report is immutable and has no downstream effect on routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


# ============================================================================
# VERSION CONSTANT
# ============================================================================


P23_VERSION = "1.0.0"


# ============================================================================
# ENUMS - Alignment State Classification (LOCKED)
# ============================================================================


class AlignmentState(str, Enum):
    """
    Classification of alignment between internal acoustic pressure and
    external interaction mode constraints.

    This phase is observer-only and non-authoritative.

    These are pure alignment descriptors based on rule-based comparison.
    No emotional labels. No intent inference. No semantic interpretation.

    Attributes:
        ALIGNED: Internal pressure is within or below allowed limit
        NEUTRAL: Internal pressure exactly matches allowed limit
        TENSION: Internal pressure exceeds allowed limit by one band
        CONTRADICTION: Internal pressure exceeds allowed limit by two or more bands
    """
    ALIGNED = "aligned"
    NEUTRAL = "neutral"
    TENSION = "tension"
    CONTRADICTION = "contradiction"


# ============================================================================
# DATACLASSES - Alignment Report (IMMUTABLE)
# ============================================================================


@dataclass(frozen=True)
class P23AlignmentReport:
    """
    Immutable alignment report observing inner-outer tension.

    This phase is observer-only and non-authoritative.

    This dataclass captures the observed alignment state between acoustic
    pressure (from P22) and regime/discourse constraints (from P6/P7).
    It contains no interpretation, intent inference, or emotional content.

    Invariants:
        - All fields are read-only (frozen dataclass)
        - observer_only is always True
        - No semantic, intent, or emotion fields
        - Values are deterministic given same input
        - tension_score is clamped to [0.0, 1.0]
        - alignment_tags contains only descriptive strings

    Attributes (Observation):
        alignment_state: Classification of alignment (ALIGNED/NEUTRAL/TENSION/CONTRADICTION)
        tension_score: Rule-based tension magnitude in [0.0, 1.0]
        alignment_tags: Descriptive tags for observation (frozenset)

    Attributes (Metadata):
        observer_only: Always True - enforces observer-only semantics
        architectural_phase: Identifier for this phase ("P23")
        version: P23 version string for provenance
    """

    # === Observation ===
    alignment_state: AlignmentState
    tension_score: float
    alignment_tags: frozenset

    # === Metadata ===
    observer_only: bool = True
    architectural_phase: str = "P23"
    version: str = P23_VERSION

    def __post_init__(self) -> None:
        """
        Validate P23AlignmentReport invariants.

        This phase is observer-only and non-authoritative.
        """
        # Validate observer_only is True
        if not self.observer_only:
            raise ValueError(
                "P23AlignmentReport.observer_only must be True"
            )

        # Validate alignment_state is AlignmentState
        if not isinstance(self.alignment_state, AlignmentState):
            raise ValueError(
                f"P23AlignmentReport.alignment_state must be AlignmentState, "
                f"got {type(self.alignment_state).__name__}"
            )

        # Validate tension_score is in [0.0, 1.0]
        if not isinstance(self.tension_score, (int, float)):
            raise ValueError(
                f"P23AlignmentReport.tension_score must be float, "
                f"got {type(self.tension_score).__name__}"
            )
        if not (0.0 <= self.tension_score <= 1.0):
            raise ValueError(
                f"P23AlignmentReport.tension_score must be in [0.0, 1.0], "
                f"got {self.tension_score}"
            )

        # Validate alignment_tags is frozenset
        if not isinstance(self.alignment_tags, frozenset):
            raise ValueError(
                f"P23AlignmentReport.alignment_tags must be frozenset, "
                f"got {type(self.alignment_tags).__name__}"
            )

        # Validate all tags are strings
        for tag in self.alignment_tags:
            if not isinstance(tag, str):
                raise ValueError(
                    f"P23AlignmentReport.alignment_tags must contain only strings, "
                    f"found {type(tag).__name__}"
                )

    def is_aligned(self) -> bool:
        """Check if alignment state indicates alignment."""
        return self.alignment_state == AlignmentState.ALIGNED

    def is_neutral(self) -> bool:
        """Check if alignment state indicates neutral."""
        return self.alignment_state == AlignmentState.NEUTRAL

    def is_tension(self) -> bool:
        """Check if alignment state indicates tension."""
        return self.alignment_state == AlignmentState.TENSION

    def is_contradiction(self) -> bool:
        """Check if alignment state indicates contradiction."""
        return self.alignment_state == AlignmentState.CONTRADICTION

    def has_tag(self, tag: str) -> bool:
        """Check if a specific tag is present."""
        return tag in self.alignment_tags

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to dictionary for logging/tracing.

        This phase is observer-only and non-authoritative.
        """
        return {
            # Observation
            "alignment_state": self.alignment_state.value,
            "tension_score": self.tension_score,
            "alignment_tags": sorted(self.alignment_tags),
            # Metadata
            "observer_only": self.observer_only,
            "architectural_phase": self.architectural_phase,
            "version": self.version,
        }


# ============================================================================
# EXCEPTIONS
# ============================================================================


class P23InvariantViolation(Exception):
    """
    Exception raised when P23 invariants are violated.

    This phase is observer-only and non-authoritative.

    This is raised when:
        - P23 attempts to read forbidden data (text, tokens, semantics, intent, etc.)
        - P23 attempts to write to ctx outside p23_*
        - P23 output is used for gating or policy
        - Non-determinism is detected
    """

    def __init__(self, message: str, violation_type: str = "UNKNOWN") -> None:
        """
        Initialize the violation exception.

        Args:
            message: Human-readable description of the violation
            violation_type: Category of violation (FORBIDDEN_ACCESS, WRITE_ATTEMPT, etc.)
        """
        super().__init__(message)
        self.violation_type = violation_type
        self.message = message

    def __str__(self) -> str:
        return f"[P23:{self.violation_type}] {self.message}"


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================


def create_aligned_report(
    tension_score: float = 0.0,
    tags: frozenset = None,
) -> P23AlignmentReport:
    """
    Create an ALIGNED alignment report.

    This phase is observer-only and non-authoritative.

    Args:
        tension_score: Tension score (should be low for aligned)
        tags: Optional alignment tags

    Returns:
        P23AlignmentReport with ALIGNED state
    """
    return P23AlignmentReport(
        alignment_state=AlignmentState.ALIGNED,
        tension_score=max(0.0, min(1.0, tension_score)),
        alignment_tags=tags if tags is not None else frozenset(),
    )


def create_neutral_report(
    tension_score: float = 0.25,
    tags: frozenset = None,
) -> P23AlignmentReport:
    """
    Create a NEUTRAL alignment report.

    This phase is observer-only and non-authoritative.

    Args:
        tension_score: Tension score
        tags: Optional alignment tags

    Returns:
        P23AlignmentReport with NEUTRAL state
    """
    return P23AlignmentReport(
        alignment_state=AlignmentState.NEUTRAL,
        tension_score=max(0.0, min(1.0, tension_score)),
        alignment_tags=tags if tags is not None else frozenset(),
    )


def create_tension_report(
    tension_score: float = 0.5,
    tags: frozenset = None,
) -> P23AlignmentReport:
    """
    Create a TENSION alignment report.

    This phase is observer-only and non-authoritative.

    Args:
        tension_score: Tension score (should be moderate for tension)
        tags: Optional alignment tags

    Returns:
        P23AlignmentReport with TENSION state
    """
    return P23AlignmentReport(
        alignment_state=AlignmentState.TENSION,
        tension_score=max(0.0, min(1.0, tension_score)),
        alignment_tags=tags if tags is not None else frozenset(),
    )


def create_contradiction_report(
    tension_score: float = 1.0,
    tags: frozenset = None,
) -> P23AlignmentReport:
    """
    Create a CONTRADICTION alignment report.

    This phase is observer-only and non-authoritative.

    Args:
        tension_score: Tension score (should be high for contradiction)
        tags: Optional alignment tags

    Returns:
        P23AlignmentReport with CONTRADICTION state
    """
    return P23AlignmentReport(
        alignment_state=AlignmentState.CONTRADICTION,
        tension_score=max(0.0, min(1.0, tension_score)),
        alignment_tags=tags if tags is not None else frozenset(),
    )


def create_empty_report() -> P23AlignmentReport:
    """
    Create an empty/neutral alignment report.

    This phase is observer-only and non-authoritative.

    Used when PO1 is blocked or P22 is not available.

    Returns:
        P23AlignmentReport with NEUTRAL state and no tags
    """
    return P23AlignmentReport(
        alignment_state=AlignmentState.NEUTRAL,
        tension_score=0.0,
        alignment_tags=frozenset(),
    )


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    # Version
    "P23_VERSION",
    # Enums
    "AlignmentState",
    # Dataclasses
    "P23AlignmentReport",
    # Exceptions
    "P23InvariantViolation",
    # Factory functions
    "create_aligned_report",
    "create_neutral_report",
    "create_tension_report",
    "create_contradiction_report",
    "create_empty_report",
]
