"""
Phase 55: Execution Authorization Boundary - Pipeline Integration

This module provides pipeline integration for P55.

P55 is the exclusive execution authorization boundary.
No action may proceed without explicit authorization.

Integration pattern matches P51-P54:
    - maybe_run_p55(): Main integration entry point
    - is_p55_disabled(): Check if P55 is disabled
    - has_p55_authorization(): Check if P55 result exists
    - get_p55_authorization(): Get P55 result if it exists
    - _extract_*(): Context extraction functions
    - _attach_*(): Context attachment functions

INV-P55-6: P55 must be removable without altering cognition.
"""

from typing import Any, FrozenSet, Optional

from .p55_schema import (
    ExecutionAuthorizationDecision,
    ExecutionProposalEnvelope,
)
from .p55_authorizer import (
    authorize_execution,
    ALLOWED_ACTION_TYPES,
)


# ============================================================================
# CONTEXT EXTRACTION
# ============================================================================


def _extract_governance_binding(ctx: Any) -> Optional[Any]:
    """
    Extract GovernanceBindingEnvelope from context.

    P55 MAY read: GovernanceBindingEnvelope (from P53)

    Returns None if not present (does not error).
    """
    return getattr(ctx, "p53_policy_binding", None)


def _extract_governance_readiness(ctx: Any) -> Optional[Any]:
    """
    Extract GovernanceReadinessEnvelope from context.

    P55 MAY read: GovernanceReadinessEnvelope (from P51)

    Returns None if not present (does not error).
    """
    return getattr(ctx, "p51_governance_readiness", None)


def _extract_audit_record(ctx: Any) -> Optional[Any]:
    """
    Extract ComplianceAuditRecord from context.

    P55 MAY read: ComplianceAuditRecord (from P54)

    Returns None if not present (does not error).
    """
    return getattr(ctx, "p54_audit_record", None)


def _extract_execution_proposal(ctx: Any) -> Optional[ExecutionProposalEnvelope]:
    """
    Extract ExecutionProposalEnvelope from context.

    P55 MAY read: ExecutionProposalEnvelope (explicit, pre-declared action intent)

    Returns None if not present (does not error).
    """
    return getattr(ctx, "p55_execution_proposal", None)


def _extract_allowed_action_types(ctx: Any) -> Optional[FrozenSet[str]]:
    """
    Extract allowed action types override from context.

    Returns None to use default ALLOWED_ACTION_TYPES.
    """
    return getattr(ctx, "p55_allowed_action_types", None)


# ============================================================================
# CONTEXT ATTACHMENT
# ============================================================================


def _attach_authorization_decision(
    ctx: Any,
    decision: ExecutionAuthorizationDecision,
) -> None:
    """
    Attach ExecutionAuthorizationDecision to context.

    The decision is attached to ctx.p55_execution_authorization.
    """
    ctx.p55_execution_authorization = decision


# ============================================================================
# PIPELINE INTEGRATION
# ============================================================================


def is_p55_disabled(ctx: Any) -> bool:
    """
    Check if P55 is disabled for this context.

    P55 can be disabled via ctx._p55_disabled = True.

    Returns:
        True if P55 is disabled, False otherwise.
    """
    return getattr(ctx, "_p55_disabled", False)


def has_p55_authorization(ctx: Any) -> bool:
    """
    Check if P55 authorization decision exists in context.

    Returns:
        True if p55_execution_authorization is present, False otherwise.
    """
    auth = getattr(ctx, "p55_execution_authorization", None)
    return auth is not None


def get_p55_authorization(ctx: Any) -> Optional[ExecutionAuthorizationDecision]:
    """
    Get P55 authorization decision from context if it exists.

    Returns:
        ExecutionAuthorizationDecision if present, None otherwise.
    """
    return getattr(ctx, "p55_execution_authorization", None)


def is_execution_authorized(ctx: Any) -> bool:
    """
    Check if execution is authorized based on P55 decision.

    Returns:
        True if authorized, False otherwise (including when no decision exists).
    """
    auth = get_p55_authorization(ctx)
    if auth is None:
        return False
    return auth.authorized


def maybe_run_p55(ctx: Any) -> Optional[ExecutionAuthorizationDecision]:
    """
    Main integration entry point for P55.

    This function:
        1. Checks if P55 is disabled
        2. Extracts inputs from context
        3. Runs authorization computation
        4. Attaches result to context
        5. Returns authorization decision

    INV-P55-1: Returns denial by default (no authorization leaks)
    INV-P55-6: When disabled, returns None without side effects

    Args:
        ctx: Pipeline context object

    Returns:
        ExecutionAuthorizationDecision if P55 runs, None if disabled
    """
    # Check if disabled
    if is_p55_disabled(ctx):
        return None

    # Extract inputs from context
    governance_binding = _extract_governance_binding(ctx)
    governance_readiness = _extract_governance_readiness(ctx)
    audit_record = _extract_audit_record(ctx)
    execution_proposal = _extract_execution_proposal(ctx)
    allowed_action_types = _extract_allowed_action_types(ctx)

    # Run authorization
    decision = authorize_execution(
        governance_binding=governance_binding,
        governance_readiness=governance_readiness,
        audit_record=audit_record,
        execution_proposal=execution_proposal,
        allowed_action_types=allowed_action_types,
    )

    # Attach to context
    _attach_authorization_decision(ctx, decision)

    return decision


# Public exports
__all__ = [
    # Context extraction
    "_extract_governance_binding",
    "_extract_governance_readiness",
    "_extract_audit_record",
    "_extract_execution_proposal",
    "_extract_allowed_action_types",
    # Context attachment
    "_attach_authorization_decision",
    # Pipeline integration
    "is_p55_disabled",
    "has_p55_authorization",
    "get_p55_authorization",
    "is_execution_authorized",
    "maybe_run_p55",
]
