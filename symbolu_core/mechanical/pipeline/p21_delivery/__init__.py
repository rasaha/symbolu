"""
P21 - Delivery Mode Resolver

A governance-only phase that determines HOW output may be delivered.
P21 answers one question: "Is output allowed, and through which delivery channel?"

P21 sits after cognition/governance and before any renderer.
P21 is purely deterministic, read-only, and non-cognitive.
P21 enforces delivery channel permissions only.

Usage:
    from symbolu_core.mechanical.pipeline.p21_delivery import (
        maybe_run_p21,
        DeliveryMode,
        DeliveryModeDecision,
    )

    # In pipeline after P20:
    maybe_run_p21(ctx)

    # Check decision:
    if ctx.p21.delivery_mode == DeliveryMode.TEXT_ONLY:
        # Voice delivery prohibited
        ...

Design Principles:
    - Deterministic: Same inputs → same outputs
    - Read-only: Does not modify context
    - Non-cognitive: No inference, no interpretation
    - Restrictive-only: Can only restrict, never enable
    - Binding: Renderers must respect decision

CRITICAL CONSTRAINTS:
    ❌ Must NOT:
        - Read acoustic units
        - Read vrtti mappings
        - Read Sanskrit data
        - Inspect lexical or semantic content
        - Modify text
        - Infer emotion or intent
        - Override any upstream decision
"""

# Schema exports
from symbolu_core.mechanical.pipeline.p21_delivery.p21_delivery_schema import (
    # Version
    P21_VERSION,
    # Enums
    DeliveryMode,
    # Dataclasses
    DeliveryModeDecision,
    # Exceptions
    DeliveryInvariantViolation,
    # Constants - enforcement tags
    TAG_BLOCKED_BY_UPSTREAM,
    TAG_HOLD_REGIME,
    TAG_ACOUSTIC_SAFETY_RESTRICTION,
    TAG_HIGH_DRIFT_RISK,
    TAG_CONSERVATIVE_DEFAULT,
    TAG_NORMAL_OPERATION,
    # Helper functions
    create_decision,
    create_suppressed_decision,
    create_text_only_decision,
)

# Resolver exports
from symbolu_core.mechanical.pipeline.p21_delivery.p21_delivery_resolver import (
    DeliveryModeResolver,
    access_forbidden_attribute,
    FORBIDDEN_ACOUSTIC_ATTRS,
    FORBIDDEN_LEXICAL_ATTRS,
    FORBIDDEN_SEMANTIC_ATTRS,
    FORBIDDEN_ONTOLOGY_ATTRS,
    ALL_FORBIDDEN_ATTRS,
    OPEN_REGIMES,
)

# Integration exports
from symbolu_core.mechanical.pipeline.p21_delivery.p21_integration import (
    # Singleton
    get_p21_resolver,
    # Integration
    maybe_run_p21,
    run_p21,
    run_p21_directly,
    # Helpers
    is_p21_disabled,
    has_p21_decision,
    get_p21_decision,
    get_delivery_mode,
    is_delivery_allowed,
    allows_voice_delivery,
    allows_text_delivery,
    is_suppressed,
    get_p21_version,
    validate_renderer_compliance,
)


__all__ = [
    # Version
    "P21_VERSION",
    # Enums
    "DeliveryMode",
    # Dataclasses
    "DeliveryModeDecision",
    # Exceptions
    "DeliveryInvariantViolation",
    # Constants - enforcement tags
    "TAG_BLOCKED_BY_UPSTREAM",
    "TAG_HOLD_REGIME",
    "TAG_ACOUSTIC_SAFETY_RESTRICTION",
    "TAG_HIGH_DRIFT_RISK",
    "TAG_CONSERVATIVE_DEFAULT",
    "TAG_NORMAL_OPERATION",
    # Constants - forbidden attributes
    "FORBIDDEN_ACOUSTIC_ATTRS",
    "FORBIDDEN_LEXICAL_ATTRS",
    "FORBIDDEN_SEMANTIC_ATTRS",
    "FORBIDDEN_ONTOLOGY_ATTRS",
    "ALL_FORBIDDEN_ATTRS",
    "OPEN_REGIMES",
    # Resolver
    "DeliveryModeResolver",
    "access_forbidden_attribute",
    # Integration
    "get_p21_resolver",
    "maybe_run_p21",
    "run_p21",
    "run_p21_directly",
    # Helpers
    "is_p21_disabled",
    "has_p21_decision",
    "get_p21_decision",
    "get_delivery_mode",
    "is_delivery_allowed",
    "allows_voice_delivery",
    "allows_text_delivery",
    "is_suppressed",
    "get_p21_version",
    "validate_renderer_compliance",
    # Factory functions
    "create_decision",
    "create_suppressed_decision",
    "create_text_only_decision",
]
