"""
Phase 55: Execution Authorization Boundary Schema

Phase P55 is the exclusive execution authorization boundary.
No action may proceed without explicit authorization.

P55 determines whether a system action may proceed beyond cognition.
It answers one question only:
    "Is this execution explicitly authorized under bound governance?"

P55 DOES:
    - Confirm governance is present
    - Confirm governance binding is valid
    - Confirm requested execution is explicitly allowed
    - Confirm no blocking readiness flags exist
    - Confirm audit record exists
    - Emit authorization decision

P55 does NOT:
    - Interpret meaning
    - Infer intent
    - Decide what action to take
    - Generate language
    - Alter cognition
    - Execute actions
    - Call external systems
    - Trigger side effects
    - Log explanations
    - Handle retries
    - Perform policy interpretation

P55 only says YES or NO.

INPUTS (Read-Only):
    Phase 55 MAY read:
        - GovernanceBindingEnvelope (from P53)
        - GovernanceReadinessEnvelope (from P51)
        - ComplianceAuditRecord (from P54)
        - ExecutionProposalEnvelope (explicit, pre-declared action intent)
        - Execution context metadata

    Phase 55 MUST NOT read:
        - Raw user input
        - Semantic meaning
        - Acoustic data
        - Ontology inference
        - LLM output
        - Observer metrics (P22-P49)

OUTPUTS:
    - ExecutionAuthorizationDecision: Authorization YES or NO

INVARIANTS:
    INV-P55-1: Execution is DENIED by default unless explicitly authorized
    INV-P55-2: No cognition phase can override P55
    INV-P55-3: No observer phase can influence P55
    INV-P55-4: Authorization requires governance provenance
    INV-P55-5: P55 must be deterministic and replayable
    INV-P55-6: P55 must be removable without altering cognition
"""

from dataclasses import dataclass
from typing import Optional, Tuple


# Version identifier for this phase
P55_VERSION = "1.0.0"

# Denial reason codes (no natural language explanations)
DENIAL_NO_GOVERNANCE = "DENIAL_NO_GOVERNANCE"
DENIAL_GOVERNANCE_NOT_BOUND = "DENIAL_GOVERNANCE_NOT_BOUND"
DENIAL_GOVERNANCE_DECISION_NOT_ALLOW = "DENIAL_GOVERNANCE_DECISION_NOT_ALLOW"
DENIAL_BLOCKING_READINESS_FLAGS = "DENIAL_BLOCKING_READINESS_FLAGS"
DENIAL_NO_AUDIT_RECORD = "DENIAL_NO_AUDIT_RECORD"
DENIAL_NO_EXECUTION_PROPOSAL = "DENIAL_NO_EXECUTION_PROPOSAL"
DENIAL_EXECUTION_NOT_IN_ALLOWLIST = "DENIAL_EXECUTION_NOT_IN_ALLOWLIST"

# All valid denial reason codes
VALID_DENIAL_REASON_CODES = frozenset({
    DENIAL_NO_GOVERNANCE,
    DENIAL_GOVERNANCE_NOT_BOUND,
    DENIAL_GOVERNANCE_DECISION_NOT_ALLOW,
    DENIAL_BLOCKING_READINESS_FLAGS,
    DENIAL_NO_AUDIT_RECORD,
    DENIAL_NO_EXECUTION_PROPOSAL,
    DENIAL_EXECUTION_NOT_IN_ALLOWLIST,
})

# Allowed fields in ExecutionAuthorizationDecision (for structural validation)
EXECUTION_AUTHORIZATION_DECISION_FIELDS = frozenset({
    "authorized",
    "authority_id",
    "denial_reason_code",
    "audit_record_id",
    "version",
    "architectural_phase",
})

# Allowed fields in ExecutionProposalEnvelope (for structural validation)
EXECUTION_PROPOSAL_ENVELOPE_FIELDS = frozenset({
    "action_id",
    "action_type",
    "target_scope",
    "version",
    "architectural_phase",
})


@dataclass(frozen=True)
class ExecutionProposalEnvelope:
    """
    Immutable execution proposal envelope.

    This represents a pre-declared action intent that P55 will authorize or deny.
    It contains only structural metadata about the proposed action, not semantic
    content or interpretation.

    P55 reads this to determine if the action is in the allow-list.
    P55 does NOT interpret the meaning of the action.

    Invariants:
        - action_id must be non-empty string (unique identifier)
        - action_type must be non-empty string (structural classification)
        - target_scope must be tuple of strings (affected areas)
    """

    # Core identity fields
    action_id: str
    action_type: str
    target_scope: Tuple[str, ...]

    # Metadata
    version: str = P55_VERSION
    architectural_phase: str = "P55"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # Validate action_id is non-empty
        if not self.action_id or not isinstance(self.action_id, str):
            raise ValueError("action_id must be a non-empty string")

        # Validate action_type is non-empty
        if not self.action_type or not isinstance(self.action_type, str):
            raise ValueError("action_type must be a non-empty string")

        # Ensure target_scope is tuple
        if not isinstance(self.target_scope, tuple):
            object.__setattr__(
                self, "target_scope",
                tuple(self.target_scope)
            )

    def to_dict(self) -> dict:
        """Serialize to dictionary for observability."""
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target_scope": list(self.target_scope),
            "version": self.version,
            "architectural_phase": self.architectural_phase,
        }


@dataclass(frozen=True)
class ExecutionAuthorizationDecision:
    """
    Immutable execution authorization decision.

    This is the output of Phase 55. It contains a binary YES/NO decision
    with no natural language explanations.

    P55 creates this decision.
    P55 only says YES or NO.

    Invariants:
        - authorized: False by default (INV-P55-1)
        - authority_id: Verbatim from P53 (None if denied)
        - denial_reason_code: Explicit code if denied (None if authorized)
        - audit_record_id: Reference to P54 audit record (required)
    """

    # Core decision
    authorized: bool

    # Authority provenance (from P53, None if denied)
    authority_id: Optional[str]

    # Denial reason code (None if authorized)
    denial_reason_code: Optional[str]

    # Audit record reference (from P54)
    audit_record_id: str

    # Metadata
    version: str = P55_VERSION
    architectural_phase: str = "P55"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # Validate audit_record_id is non-empty
        if not self.audit_record_id or not isinstance(self.audit_record_id, str):
            raise ValueError("audit_record_id must be a non-empty string")

        # If denied, denial_reason_code must be set and valid
        if not self.authorized:
            if self.denial_reason_code is None:
                raise ValueError(
                    "authorized=False requires denial_reason_code to be set"
                )
            if self.denial_reason_code not in VALID_DENIAL_REASON_CODES:
                raise ValueError(
                    f"Invalid denial_reason_code: {self.denial_reason_code}. "
                    f"Must be one of {sorted(VALID_DENIAL_REASON_CODES)}"
                )
            # authority_id should be None when denied
            if self.authority_id is not None:
                raise ValueError(
                    "authorized=False should have authority_id=None"
                )
        else:
            # If authorized, denial_reason_code must be None
            if self.denial_reason_code is not None:
                raise ValueError(
                    "authorized=True requires denial_reason_code to be None"
                )
            # authority_id must be set when authorized
            if self.authority_id is None:
                raise ValueError(
                    "authorized=True requires authority_id to be set"
                )

    def to_dict(self) -> dict:
        """Serialize to dictionary for observability."""
        return {
            "authorized": self.authorized,
            "authority_id": self.authority_id,
            "denial_reason_code": self.denial_reason_code,
            "audit_record_id": self.audit_record_id,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
        }


def create_denial_decision(
    denial_reason_code: str,
    audit_record_id: str,
) -> ExecutionAuthorizationDecision:
    """
    Factory function to create a denial decision.

    This is the DEFAULT outcome (INV-P55-1).

    Args:
        denial_reason_code: One of VALID_DENIAL_REASON_CODES
        audit_record_id: Reference to P54 audit record

    Returns:
        ExecutionAuthorizationDecision with authorized=False
    """
    return ExecutionAuthorizationDecision(
        authorized=False,
        authority_id=None,
        denial_reason_code=denial_reason_code,
        audit_record_id=audit_record_id,
    )


def create_authorization_decision(
    authority_id: str,
    audit_record_id: str,
) -> ExecutionAuthorizationDecision:
    """
    Factory function to create an authorization decision.

    This is the EXCEPTIONAL outcome - only when all conditions are met.

    Args:
        authority_id: Authority provenance from P53
        audit_record_id: Reference to P54 audit record

    Returns:
        ExecutionAuthorizationDecision with authorized=True
    """
    return ExecutionAuthorizationDecision(
        authorized=True,
        authority_id=authority_id,
        denial_reason_code=None,
        audit_record_id=audit_record_id,
    )


# Public exports
__all__ = [
    # Version
    "P55_VERSION",
    # Denial reason codes
    "DENIAL_NO_GOVERNANCE",
    "DENIAL_GOVERNANCE_NOT_BOUND",
    "DENIAL_GOVERNANCE_DECISION_NOT_ALLOW",
    "DENIAL_BLOCKING_READINESS_FLAGS",
    "DENIAL_NO_AUDIT_RECORD",
    "DENIAL_NO_EXECUTION_PROPOSAL",
    "DENIAL_EXECUTION_NOT_IN_ALLOWLIST",
    "VALID_DENIAL_REASON_CODES",
    # Constants
    "EXECUTION_AUTHORIZATION_DECISION_FIELDS",
    "EXECUTION_PROPOSAL_ENVELOPE_FIELDS",
    # Dataclasses
    "ExecutionProposalEnvelope",
    "ExecutionAuthorizationDecision",
    # Factory functions
    "create_denial_decision",
    "create_authorization_decision",
]
