"""
Phase 53: External Policy Binding Layer Schema

Phase 53 binds external governance decisions into the pipeline without
interpretation or enforcement.

P53 answers exactly one question:
    "If an external governance system exists, how is its decision injected
    without contaminating cognition?"

P53 is a plug, not a judge.

P53 DOES:
    - Accept a GovernanceResponse (from P52 contract)
    - Validate its structure
    - Record it immutably
    - Mark binding status

P53 does NOT:
    - Interpret decisions
    - Act on decisions
    - Modify cognition
    - Evaluate policy
    - Enforce rules
    - Provide defaults

INPUTS (Read-Only):
    Phase 53 MAY read:
        - GovernanceRequest (from P52)
        - GovernanceResponse (external, optional)
        - Phase trace metadata
        - Pipeline execution ID

    Phase 53 MUST NOT read:
        - Raw user input
        - Semantic frames
        - Acoustic signals
        - Intent or regime logic
        - Any cognitive formulas

OUTPUTS:
    - GovernanceBindingEnvelope: Immutable binding record

INVARIANTS:
    INV-P53-1: P53 MUST NOT modify cognition, regime, discourse, or delivery
    INV-P53-2: P53 MUST NOT reinterpret governance decisions
    INV-P53-3: P53 MUST NOT introduce fallback logic if governance is absent
    INV-P53-4: P53 MUST NOT assume authority correctness
    INV-P53-5: P53 MUST remain removable without changing cognitive outputs
"""

from dataclasses import dataclass
from typing import Literal, Optional, Tuple


# Version identifier for this phase
P53_VERSION = "1.0.0"

# Valid governance decisions (imported from P52 contract)
GovernanceDecision = Literal["ALLOW", "DENY", "DEFER"]

# Valid governance decision values (for validation)
VALID_GOVERNANCE_DECISIONS = frozenset({"ALLOW", "DENY", "DEFER"})

# Allowed fields in GovernanceBindingEnvelope (for structural validation)
GOVERNANCE_BINDING_FIELDS = frozenset({
    "bound",
    "decision",
    "rationale_codes",
    "audit_reference",
    "authority_id",
    "version",
    "architectural_phase",
})


@dataclass(frozen=True)
class GovernanceBindingEnvelope:
    """
    Immutable governance binding envelope.

    This records whether an external governance decision has been bound
    to this pipeline execution. It stores the decision verbatim without
    interpretation or modification.

    P53 creates this envelope.
    P53 does NOT interpret the decision.
    P53 does NOT act on the decision.

    Invariants:
        - bound: True if GovernanceResponse was present and valid
        - decision: Verbatim copy from GovernanceResponse (None if unbound)
        - rationale_codes: Verbatim copy from GovernanceResponse (empty if unbound)
        - audit_reference: Verbatim copy from GovernanceResponse (None if unbound)
        - authority_id: Opaque string identifier (no parsing, no validation)
    """

    # Binding status
    bound: bool

    # Verbatim governance decision (None if not bound)
    decision: Optional[GovernanceDecision]

    # Verbatim rationale codes (empty tuple if not bound)
    rationale_codes: Tuple[str, ...]

    # Verbatim audit reference (None if not bound or not provided)
    audit_reference: Optional[str]

    # Opaque authority identifier (no parsing)
    authority_id: Optional[str]

    # Metadata
    version: str = P53_VERSION
    architectural_phase: str = "P53"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # Validate decision if bound
        if self.bound:
            if self.decision is None:
                raise ValueError(
                    "bound=True requires decision to be set"
                )
            if self.decision not in VALID_GOVERNANCE_DECISIONS:
                raise ValueError(
                    f"Invalid decision: {self.decision}. "
                    f"Must be one of {sorted(VALID_GOVERNANCE_DECISIONS)}"
                )
        else:
            # If not bound, decision must be None
            if self.decision is not None:
                raise ValueError(
                    "bound=False requires decision to be None"
                )

        # Ensure rationale_codes is tuple
        if not isinstance(self.rationale_codes, tuple):
            object.__setattr__(
                self, "rationale_codes",
                tuple(self.rationale_codes)
            )

        # authority_id is opaque - no validation beyond type
        # It can be None, empty string, or any string value

    def to_dict(self) -> dict:
        """Serialize to dictionary for observability."""
        return {
            "bound": self.bound,
            "decision": self.decision,
            "rationale_codes": list(self.rationale_codes),
            "audit_reference": self.audit_reference,
            "authority_id": self.authority_id,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
        }


def create_unbound_envelope() -> GovernanceBindingEnvelope:
    """
    Create an unbound envelope when no governance response exists.

    This is the ONLY way to create an unbound envelope.
    No fallback logic. No defaults. Just absence recording.
    """
    return GovernanceBindingEnvelope(
        bound=False,
        decision=None,
        rationale_codes=(),
        audit_reference=None,
        authority_id=None,
    )


# Public exports
__all__ = [
    # Version
    "P53_VERSION",
    # Type Aliases
    "GovernanceDecision",
    # Constants
    "VALID_GOVERNANCE_DECISIONS",
    "GOVERNANCE_BINDING_FIELDS",
    # Dataclasses
    "GovernanceBindingEnvelope",
    # Factory functions
    "create_unbound_envelope",
]
