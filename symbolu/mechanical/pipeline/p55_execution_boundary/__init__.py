"""
Phase 55: Execution Authorization Boundary

Phase P55 is the exclusive execution authorization boundary.
No action may proceed without explicit authorization.

P55 determines whether a system action may proceed beyond cognition.
It answers one question only:
    "Is this execution explicitly authorized under bound governance?"

This completes Symbol-U's contract:

    Layer                 Responsibility
    ─────────────────────────────────────────────────
    Cognition (P1–P49)    Compute truth
    Governance Binding    Bind authority (P52–P53)
    Audit (P54)           Record provenance
    P55                   Authorize execution

There is nothing beyond P55 inside Symbol-U.
Anything after P55 is external responsibility.

Usage:
    from symbolu.mechanical.pipeline.p55_execution_boundary import (
        # Main integration
        maybe_run_p55,
        is_execution_authorized,

        # Schema
        ExecutionAuthorizationDecision,
        ExecutionProposalEnvelope,

        # Factory functions
        create_denial_decision,
        create_authorization_decision,
    )

    # In pipeline
    decision = maybe_run_p55(ctx)
    if is_execution_authorized(ctx):
        # Proceed with execution
        pass
"""

# Schema exports
from .p55_schema import (
    # Version
    P55_VERSION,
    # Denial reason codes
    DENIAL_NO_GOVERNANCE,
    DENIAL_GOVERNANCE_NOT_BOUND,
    DENIAL_GOVERNANCE_DECISION_NOT_ALLOW,
    DENIAL_BLOCKING_READINESS_FLAGS,
    DENIAL_NO_AUDIT_RECORD,
    DENIAL_NO_EXECUTION_PROPOSAL,
    DENIAL_EXECUTION_NOT_IN_ALLOWLIST,
    VALID_DENIAL_REASON_CODES,
    # Constants
    EXECUTION_AUTHORIZATION_DECISION_FIELDS,
    EXECUTION_PROPOSAL_ENVELOPE_FIELDS,
    # Dataclasses
    ExecutionProposalEnvelope,
    ExecutionAuthorizationDecision,
    # Factory functions
    create_denial_decision,
    create_authorization_decision,
)

# Authorizer exports
from .p55_authorizer import (
    # Allow-list
    ALLOWED_ACTION_TYPES,
    # Core function
    authorize_execution,
    # Direct entry point
    run_p55_directly,
)

# Integration exports
from .p55_integration import (
    # Pipeline integration
    is_p55_disabled,
    has_p55_authorization,
    get_p55_authorization,
    is_execution_authorized,
    maybe_run_p55,
)


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
    "ALLOWED_ACTION_TYPES",
    # Dataclasses
    "ExecutionProposalEnvelope",
    "ExecutionAuthorizationDecision",
    # Factory functions
    "create_denial_decision",
    "create_authorization_decision",
    # Core function
    "authorize_execution",
    # Direct entry point
    "run_p55_directly",
    # Pipeline integration
    "is_p55_disabled",
    "has_p55_authorization",
    "get_p55_authorization",
    "is_execution_authorized",
    "maybe_run_p55",
]
