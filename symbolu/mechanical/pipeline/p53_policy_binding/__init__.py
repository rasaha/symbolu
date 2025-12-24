"""
Phase 53: External Policy Binding Layer

Phase 53 binds external governance decisions into the pipeline without
interpretation or enforcement.

P53 is the first phase allowed to bind to authority, but must not execute it.

P53 answers exactly one question:
    "If an external governance system exists, how is its decision injected
    without contaminating cognition?"

P53 is a plug, not a judge.

Architectural Positioning:
    - P52 defines how governance may speak (contract)
    - P53 defines where governance attaches (binding)
    - P54 will define how it is audited
    - P55 will define how execution is blocked or allowed

Usage:
    from symbolu.mechanical.pipeline.p53_policy_binding import (
        maybe_run_p53,
        GovernanceBindingEnvelope,
    )

    # In pipeline after P52:
    envelope = maybe_run_p53(ctx)

    # Access binding status:
    if envelope.bound:
        print(f"Decision: {envelope.decision}")
        print(f"Authority: {envelope.authority_id}")
    else:
        print("No governance bound")

INVARIANTS:
    INV-P53-1: P53 MUST NOT modify cognition, regime, discourse, or delivery
    INV-P53-2: P53 MUST NOT reinterpret governance decisions
    INV-P53-3: P53 MUST NOT introduce fallback logic if governance is absent
    INV-P53-4: P53 MUST NOT assume authority correctness
    INV-P53-5: P53 MUST remain removable without changing cognitive outputs
"""

from .p53_schema import (
    # Version
    P53_VERSION,
    # Type Aliases
    GovernanceDecision,
    # Constants
    VALID_GOVERNANCE_DECISIONS,
    GOVERNANCE_BINDING_FIELDS,
    # Dataclasses
    GovernanceBindingEnvelope,
    # Factory functions
    create_unbound_envelope,
)

from .p53_binder import (
    # Exceptions
    GovernanceResponseValidationError,
    # Validation
    validate_governance_response_structure,
    # Core binding
    bind_governance_response,
    # Direct entry point
    run_p53_directly,
)

from .p53_integration import (
    # Integration
    maybe_run_p53,
    # Helpers
    is_p53_disabled,
    has_p53_binding,
    get_p53_binding,
    is_governance_bound,
    get_governance_decision,
    get_p53_version,
)


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
    # Exceptions
    "GovernanceResponseValidationError",
    # Validation
    "validate_governance_response_structure",
    # Core binding
    "bind_governance_response",
    # Direct entry point
    "run_p53_directly",
    # Integration
    "maybe_run_p53",
    # Helpers
    "is_p53_disabled",
    "has_p53_binding",
    "get_p53_binding",
    "is_governance_bound",
    "get_governance_decision",
    "get_p53_version",
]
