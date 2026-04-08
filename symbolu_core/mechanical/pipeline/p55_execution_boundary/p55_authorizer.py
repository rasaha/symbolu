"""
Phase 55: Execution Authorization Boundary - Core Authorizer

This module implements the core authorization logic for P55.

P55 is the exclusive execution authorization boundary.
No action may proceed without explicit authorization.

Authorization Logic:
    1. Confirms governance is present (P53.bound == True)
    2. Confirms governance binding is valid (P53.decision == "ALLOW")
    3. Confirms requested execution is explicitly allowed (in allow-list)
    4. Confirms no blocking readiness flags exist (P51.blocking_factors empty)
    5. Confirms audit record exists (P54 present)
    6. Emits authorization decision

NO imports from:
    - LLMs
    - Renderers
    - Acoustic modules
    - Observers

NO heuristics.
NO probabilistic logic.
"""

from typing import Any, FrozenSet, Optional, Protocol, Tuple, runtime_checkable

from .p55_schema import (
    ExecutionAuthorizationDecision,
    ExecutionProposalEnvelope,
    create_authorization_decision,
    create_denial_decision,
    DENIAL_NO_GOVERNANCE,
    DENIAL_GOVERNANCE_NOT_BOUND,
    DENIAL_GOVERNANCE_DECISION_NOT_ALLOW,
    DENIAL_BLOCKING_READINESS_FLAGS,
    DENIAL_NO_AUDIT_RECORD,
    DENIAL_NO_EXECUTION_PROPOSAL,
    DENIAL_EXECUTION_NOT_IN_ALLOWLIST,
)


# ============================================================================
# PROTOCOLS FOR INPUT TYPES (to avoid importing from upstream phases)
# ============================================================================


@runtime_checkable
class GovernanceBindingEnvelopeProtocol(Protocol):
    """Protocol for GovernanceBindingEnvelope (P53)."""
    bound: bool
    decision: Optional[str]
    authority_id: Optional[str]


@runtime_checkable
class GovernanceReadinessEnvelopeProtocol(Protocol):
    """Protocol for GovernanceReadinessEnvelope (P51)."""
    ready: bool
    blocking_factors: Tuple[str, ...]


@runtime_checkable
class ComplianceAuditRecordProtocol(Protocol):
    """Protocol for ComplianceAuditRecord (P54)."""
    execution_id: str


# ============================================================================
# ALLOW-LIST FOR EXECUTION TYPES
# ============================================================================

# Explicit allow-list of action types that may be authorized
# No action type outside this list can ever be authorized
ALLOWED_ACTION_TYPES: FrozenSet[str] = frozenset({
    "DELIVERY_TEXT",
    "DELIVERY_VOICE",
    "DELIVERY_MULTIMODAL",
    "STATE_TRANSITION",
    "CONTEXT_UPDATE",
})


# ============================================================================
# CORE AUTHORIZATION FUNCTION
# ============================================================================


def authorize_execution(
    governance_binding: Optional[GovernanceBindingEnvelopeProtocol],
    governance_readiness: Optional[GovernanceReadinessEnvelopeProtocol],
    audit_record: Optional[ComplianceAuditRecordProtocol],
    execution_proposal: Optional[ExecutionProposalEnvelope],
    allowed_action_types: Optional[FrozenSet[str]] = None,
) -> ExecutionAuthorizationDecision:
    """
    Core authorization function for P55.

    This function implements the authorization logic:
        1. Confirms governance is present
        2. Confirms governance binding is valid
        3. Confirms requested execution is explicitly allowed
        4. Confirms no blocking readiness flags exist
        5. Confirms audit record exists
        6. Emits authorization decision

    INV-P55-1: Execution is DENIED by default.
    INV-P55-4: Authorization requires governance provenance.
    INV-P55-5: Deterministic and replayable.

    Args:
        governance_binding: GovernanceBindingEnvelope from P53 (required)
        governance_readiness: GovernanceReadinessEnvelope from P51 (required)
        audit_record: ComplianceAuditRecord from P54 (required)
        execution_proposal: ExecutionProposalEnvelope (required)
        allowed_action_types: Optional override for allowed action types

    Returns:
        ExecutionAuthorizationDecision with authorized=True or False
    """
    # Use provided allow-list or default
    action_allow_list = allowed_action_types or ALLOWED_ACTION_TYPES

    # Generate audit record ID (required for all decisions)
    audit_record_id = _get_audit_record_id(audit_record)

    # Step 1: Check audit record exists
    if audit_record is None:
        return create_denial_decision(
            denial_reason_code=DENIAL_NO_AUDIT_RECORD,
            audit_record_id="MISSING_AUDIT_RECORD",
        )

    # Step 2: Check execution proposal exists
    if execution_proposal is None:
        return create_denial_decision(
            denial_reason_code=DENIAL_NO_EXECUTION_PROPOSAL,
            audit_record_id=audit_record_id,
        )

    # Step 3: Check governance is present
    if governance_binding is None:
        return create_denial_decision(
            denial_reason_code=DENIAL_NO_GOVERNANCE,
            audit_record_id=audit_record_id,
        )

    # Step 4: Check governance is bound
    if not governance_binding.bound:
        return create_denial_decision(
            denial_reason_code=DENIAL_GOVERNANCE_NOT_BOUND,
            audit_record_id=audit_record_id,
        )

    # Step 5: Check governance decision is ALLOW
    if governance_binding.decision != "ALLOW":
        return create_denial_decision(
            denial_reason_code=DENIAL_GOVERNANCE_DECISION_NOT_ALLOW,
            audit_record_id=audit_record_id,
        )

    # Step 6: Check no blocking readiness flags exist
    if governance_readiness is not None:
        if len(governance_readiness.blocking_factors) > 0:
            return create_denial_decision(
                denial_reason_code=DENIAL_BLOCKING_READINESS_FLAGS,
                audit_record_id=audit_record_id,
            )

    # Step 7: Check execution is in allow-list
    if execution_proposal.action_type not in action_allow_list:
        return create_denial_decision(
            denial_reason_code=DENIAL_EXECUTION_NOT_IN_ALLOWLIST,
            audit_record_id=audit_record_id,
        )

    # All checks passed - AUTHORIZE
    return create_authorization_decision(
        authority_id=governance_binding.authority_id or "GOVERNANCE_AUTHORITY",
        audit_record_id=audit_record_id,
    )


def _get_audit_record_id(
    audit_record: Optional[ComplianceAuditRecordProtocol],
) -> str:
    """Extract audit record ID from P54 record."""
    if audit_record is None:
        return "MISSING_AUDIT_RECORD"
    return getattr(audit_record, "execution_id", "UNKNOWN_AUDIT_RECORD")


# ============================================================================
# DIRECT ENTRY POINT (for testing)
# ============================================================================


def run_p55_directly(
    governance_binding: Optional[Any],
    governance_readiness: Optional[Any],
    audit_record: Optional[Any],
    execution_proposal: Optional[ExecutionProposalEnvelope],
    allowed_action_types: Optional[FrozenSet[str]] = None,
) -> ExecutionAuthorizationDecision:
    """
    Direct entry point for running P55 authorization.

    This is used for testing and direct invocation outside the pipeline.

    Args:
        governance_binding: P53 GovernanceBindingEnvelope (or compatible)
        governance_readiness: P51 GovernanceReadinessEnvelope (or compatible)
        audit_record: P54 ComplianceAuditRecord (or compatible)
        execution_proposal: ExecutionProposalEnvelope
        allowed_action_types: Optional override for allowed action types

    Returns:
        ExecutionAuthorizationDecision
    """
    return authorize_execution(
        governance_binding=governance_binding,
        governance_readiness=governance_readiness,
        audit_record=audit_record,
        execution_proposal=execution_proposal,
        allowed_action_types=allowed_action_types,
    )


# Public exports
__all__ = [
    # Allow-list
    "ALLOWED_ACTION_TYPES",
    # Core function
    "authorize_execution",
    # Direct entry point
    "run_p55_directly",
]
