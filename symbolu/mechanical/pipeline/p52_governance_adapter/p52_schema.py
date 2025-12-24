"""
Phase 52: Governance Adapter Interface Schema

Phase 52 defines the structural interface between Symbol-U cognition and
external governance systems. It contains no governance logic.

P52 is a pure contract definition — nothing more.

Think of P52 as an electrical socket — not the appliance.

P52 answers exactly one question:
    "If an external governance engine existed, what data would it receive,
    and what shape must its response have?"

P52 does NOT:
    - Enforce policy
    - Evaluate rules
    - Block execution
    - Modify outputs
    - Interpret meaning
    - Contain logic

INPUTS (Read-Only):
    Phase 52 MAY read:
        - GovernanceReadinessEnvelope (P51)
        - UnifiedCognitiveSnapshot (P20)
        - Phase trace metadata (IDs, timestamps)
        - Delivery metadata (P21 result)

    Phase 52 MUST NOT read:
        - Raw user input
        - Lexical or semantic content
        - Acoustic data
        - Any policy configuration
        - Any runtime execution state

OUTPUTS:
    - GovernanceRequest: Structural data for external governance
    - GovernanceResponse: Contract interface (never instantiated in P52)

INVARIANTS:
    INV-P52-1: P52 MUST NOT execute or simulate governance
    INV-P52-2: P52 MUST NOT modify or reinterpret upstream data
    INV-P52-3: P52 MUST NOT introduce branching or gating
    INV-P52-4: P52 MUST NOT require GovernanceResponse to exist
    INV-P52-5: When P52 is removed, system behavior is bitwise identical
"""

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional, Tuple


# Version identifier for this phase
P52_VERSION = "1.0.0"

# Valid governance decision types (for contract definition)
GovernanceDecision = Literal["ALLOW", "DENY", "DEFER"]

# Valid governance decision values (for validation)
VALID_GOVERNANCE_DECISIONS = frozenset({"ALLOW", "DENY", "DEFER"})

# Readiness level type (mirrored from P51 for interface clarity)
ReadinessLevel = Literal["READY", "CONDITIONAL", "NOT_READY"]

# Valid readiness levels (for validation)
VALID_READINESS_LEVELS = frozenset({"READY", "CONDITIONAL", "NOT_READY"})

# Allowed fields in GovernanceRequest (for structural validation)
GOVERNANCE_REQUEST_FIELDS = frozenset({
    "snapshot_id",
    "readiness_level",
    "blocking_factors",
    "advisory_notes",
    "cognitive_summary",
    "trace_hash",
    "version",
    "architectural_phase",
})

# Allowed fields in GovernanceResponse (for structural validation)
GOVERNANCE_RESPONSE_FIELDS = frozenset({
    "decision",
    "rationale_codes",
    "audit_reference",
})


@dataclass(frozen=True)
class GovernanceRequest:
    """
    Immutable governance request envelope.

    This is the structural data that would be sent to an external governance
    engine if one existed. It contains only structural metadata — no free text,
    no semantics, no probabilities.

    P52 assembles this from upstream phase outputs.
    P52 stores it in PipelineContext.
    P52 does NOT send it anywhere.
    P52 does NOT expect a response.

    Invariants:
        - snapshot_id must be non-empty string
        - readiness_level must be in VALID_READINESS_LEVELS
        - blocking_factors must be tuple
        - advisory_notes must be tuple
        - cognitive_summary must be Mapping (structural metadata only)
        - trace_hash must be non-empty string
    """

    # Core fields (all required)
    snapshot_id: str
    readiness_level: ReadinessLevel
    blocking_factors: Tuple[str, ...]
    advisory_notes: Tuple[str, ...]
    cognitive_summary: Mapping[str, Any]
    trace_hash: str

    # Metadata
    version: str = P52_VERSION
    architectural_phase: str = "P52"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # Validate snapshot_id is non-empty
        if not self.snapshot_id or not isinstance(self.snapshot_id, str):
            raise ValueError("snapshot_id must be a non-empty string")

        # Validate readiness_level
        if self.readiness_level not in VALID_READINESS_LEVELS:
            raise ValueError(
                f"Invalid readiness_level: {self.readiness_level}. "
                f"Must be one of {sorted(VALID_READINESS_LEVELS)}"
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

        # Validate cognitive_summary is Mapping
        if not isinstance(self.cognitive_summary, Mapping):
            raise TypeError(
                f"cognitive_summary must be Mapping, "
                f"got {type(self.cognitive_summary).__name__}"
            )

        # Validate trace_hash is non-empty
        if not self.trace_hash or not isinstance(self.trace_hash, str):
            raise ValueError("trace_hash must be a non-empty string")

    def to_dict(self) -> dict:
        """Serialize to dictionary for observability."""
        return {
            "snapshot_id": self.snapshot_id,
            "readiness_level": self.readiness_level,
            "blocking_factors": list(self.blocking_factors),
            "advisory_notes": list(self.advisory_notes),
            "cognitive_summary": dict(self.cognitive_summary),
            "trace_hash": self.trace_hash,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
        }


@dataclass(frozen=True)
class GovernanceResponse:
    """
    Immutable governance response contract.

    IMPORTANT: This is NOT produced in P52.
    It exists only as a contract definition.
    No defaults. No logic.

    This defines the shape that a response from an external governance
    engine MUST have. P52 does not create, populate, or process instances
    of this class. It is a pure interface specification.

    Future governance engines must return data matching this shape.

    Fields:
        decision: "ALLOW", "DENY", or "DEFER"
        rationale_codes: Tuple of code strings explaining the decision
        audit_reference: Optional reference ID for audit trail
    """

    decision: GovernanceDecision
    rationale_codes: Tuple[str, ...]
    audit_reference: Optional[str]

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # Validate decision
        if self.decision not in VALID_GOVERNANCE_DECISIONS:
            raise ValueError(
                f"Invalid decision: {self.decision}. "
                f"Must be one of {sorted(VALID_GOVERNANCE_DECISIONS)}"
            )

        # Ensure rationale_codes is tuple
        if not isinstance(self.rationale_codes, tuple):
            object.__setattr__(
                self, "rationale_codes",
                tuple(self.rationale_codes)
            )

    def to_dict(self) -> dict:
        """Serialize to dictionary for observability."""
        return {
            "decision": self.decision,
            "rationale_codes": list(self.rationale_codes),
            "audit_reference": self.audit_reference,
        }


# Public exports
__all__ = [
    # Version
    "P52_VERSION",
    # Type Aliases
    "GovernanceDecision",
    "ReadinessLevel",
    # Constants
    "VALID_GOVERNANCE_DECISIONS",
    "VALID_READINESS_LEVELS",
    "GOVERNANCE_REQUEST_FIELDS",
    "GOVERNANCE_RESPONSE_FIELDS",
    # Dataclasses
    "GovernanceRequest",
    "GovernanceResponse",
]
