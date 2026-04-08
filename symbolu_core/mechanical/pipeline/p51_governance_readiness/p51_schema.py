"""
Phase 51: Governance Readiness Envelope Schema

Phase 51 summarizes structural readiness for governance without exercising
governance authority.

P51 answers only one question:
    "Is this pipeline output structurally ready to be handed to a future
    governance layer?"

P51 does NOT:
    - Enforce policy
    - Modify behavior
    - Block actions
    - Override any prior phase
    - Predict outcomes

P51 ONLY summarizes whether upstream phases are:
    - Complete
    - Coherent
    - Explainable
    - Non-contradictory

P51 is diagnostic only.

INPUTS (Read-Only):
    Phase 51 MAY read:
        - UnifiedCognitiveSnapshot (P20)
        - DeliveryModeDecision (P21)
        - Observer outputs (P22-P49)
        - CoherenceState (Phase 10/12)
        - Drift / entropy summaries (P18, P19)
        - Phase trace metadata

    Phase 51 MUST NOT read:
        - Raw user input
        - Lexical content
        - Semantic content
        - Acoustic content
        - Any future governance configuration

INVARIANTS:
    INV-P51-1: P51 MUST NOT modify any upstream data
    INV-P51-2: P51 MUST NOT introduce new classifications or decisions
    INV-P51-3: P51 MUST NOT block or gate output
    INV-P51-4: P51 MUST NOT depend on future governance logic
    INV-P51-5: When P51 is removed, system behavior is bitwise identical
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Tuple

# Version identifier for this phase
P51_VERSION = "1.0.0"

# Readiness level classifications
ReadinessLevel = Literal["READY", "CONDITIONAL", "NOT_READY"]

# Valid readiness levels (for validation)
VALID_READINESS_LEVELS = frozenset({"READY", "CONDITIONAL", "NOT_READY"})

# Hard drift threshold for governance readiness
DRIFT_SAFETY_THRESHOLD = 0.85

# Mandatory phase envelopes that must be present for READY status
MANDATORY_PHASES = frozenset({
    "p6_regime",
    "p7_discourse_envelope",
    "phase_20_snapshot",
    "p21_delivery_mode",
})


@dataclass(frozen=True)
class GovernanceReadinessEnvelope:
    """
    Immutable governance readiness envelope.

    This is the output of Phase 51. It summarizes whether the pipeline
    output is structurally ready for a future governance layer without
    exercising any governance authority itself.

    P51 is a bridge, not a gate.
    It observes whether the system is governable, not whether it should act.

    Invariants:
        - ready must match readiness_level == "READY"
        - readiness_level must be in VALID_READINESS_LEVELS
        - blocking_factors must be tuple
        - advisory_notes must be tuple
        - supporting_evidence must be Mapping
        - observer_only must be True (enforced)
    """

    # Core outputs (all required)
    ready: bool
    readiness_level: ReadinessLevel
    blocking_factors: Tuple[str, ...]
    advisory_notes: Tuple[str, ...]
    supporting_evidence: Mapping[str, Any]
    observer_only: Literal[True]

    # Metadata
    version: str = P51_VERSION
    architectural_phase: str = "P51"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # INV-P51-2: observer_only must be True
        if self.observer_only is not True:
            raise ValueError("observer_only must be True (P51 is diagnostic only)")

        # Validate readiness_level
        if self.readiness_level not in VALID_READINESS_LEVELS:
            raise ValueError(
                f"Invalid readiness_level: {self.readiness_level}. "
                f"Must be one of {sorted(VALID_READINESS_LEVELS)}"
            )

        # Validate ready matches readiness_level
        expected_ready = self.readiness_level == "READY"
        if self.ready != expected_ready:
            raise ValueError(
                f"ready={self.ready} does not match readiness_level="
                f"'{self.readiness_level}'. Expected ready={expected_ready}"
            )

        # Ensure blocking_factors is tuple
        if not isinstance(self.blocking_factors, tuple):
            object.__setattr__(
                self, "blocking_factors",
                tuple(self.blocking_factors)
            )

        # Ensure advisory_notes is tuple
        if not isinstance(self.advisory_notes, tuple):
            object.__setattr__(
                self, "advisory_notes",
                tuple(self.advisory_notes)
            )

        # Validate READY has no blocking factors
        if self.readiness_level == "READY" and len(self.blocking_factors) > 0:
            raise ValueError(
                "READY status cannot have blocking_factors. "
                f"Found: {self.blocking_factors}"
            )

        # Validate NOT_READY has blocking factors
        if self.readiness_level == "NOT_READY" and len(self.blocking_factors) == 0:
            raise ValueError(
                "NOT_READY status must have at least one blocking_factor"
            )

    def to_dict(self) -> dict:
        """Serialize to dictionary for observability."""
        return {
            "ready": self.ready,
            "readiness_level": self.readiness_level,
            "blocking_factors": list(self.blocking_factors),
            "advisory_notes": list(self.advisory_notes),
            "supporting_evidence": dict(self.supporting_evidence),
            "observer_only": self.observer_only,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
        }

    def has_blocking_factors(self) -> bool:
        """Check if any blocking factors exist."""
        return len(self.blocking_factors) > 0

    def has_advisory_notes(self) -> bool:
        """Check if any advisory notes exist."""
        return len(self.advisory_notes) > 0

    def blocking_factor_count(self) -> int:
        """Return the number of blocking factors."""
        return len(self.blocking_factors)

    def advisory_note_count(self) -> int:
        """Return the number of advisory notes."""
        return len(self.advisory_notes)

    def is_ready(self) -> bool:
        """Check if readiness level is READY."""
        return self.readiness_level == "READY"

    def is_conditional(self) -> bool:
        """Check if readiness level is CONDITIONAL."""
        return self.readiness_level == "CONDITIONAL"

    def is_not_ready(self) -> bool:
        """Check if readiness level is NOT_READY."""
        return self.readiness_level == "NOT_READY"


def create_governance_readiness_envelope(
    readiness_level: ReadinessLevel,
    blocking_factors: Tuple[str, ...] = (),
    advisory_notes: Tuple[str, ...] = (),
    supporting_evidence: Mapping[str, Any] | None = None,
) -> GovernanceReadinessEnvelope:
    """
    Factory function to create GovernanceReadinessEnvelope safely.

    Always sets observer_only=True (enforced by design).
    Automatically derives ready from readiness_level.

    INV-P51-2: Observer-only enforced.
    INV-P51-3: No gating - this is diagnostic only.

    Args:
        readiness_level: "READY", "CONDITIONAL", or "NOT_READY"
        blocking_factors: Tuple of blocking factor descriptions
        advisory_notes: Tuple of advisory note strings
        supporting_evidence: Optional mapping of evidence

    Returns:
        GovernanceReadinessEnvelope
    """
    return GovernanceReadinessEnvelope(
        ready=readiness_level == "READY",
        readiness_level=readiness_level,
        blocking_factors=tuple(blocking_factors),
        advisory_notes=tuple(advisory_notes),
        supporting_evidence=supporting_evidence or {},
        observer_only=True,
    )


# Public exports
__all__ = [
    # Version
    "P51_VERSION",
    # Type Aliases
    "ReadinessLevel",
    # Constants
    "VALID_READINESS_LEVELS",
    "DRIFT_SAFETY_THRESHOLD",
    "MANDATORY_PHASES",
    # Dataclasses
    "GovernanceReadinessEnvelope",
    # Factory
    "create_governance_readiness_envelope",
]
