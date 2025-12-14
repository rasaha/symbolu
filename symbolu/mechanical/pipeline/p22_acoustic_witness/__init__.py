"""
P22 - Acoustic-Vrtti Witness Extractor

This phase is witness-only and has zero authority over cognition or delivery.

P22 observes acoustic motion signatures of the user's input without influencing
meaning, intent, regime, discourse, or semantics. It exists to:
    - Acknowledge how sound moves, not what it means
    - Preserve acoustic truth without authority
    - Allow later delivery layers to optionally soften or neutralize expression

Usage:
    from symbolu.mechanical.pipeline.p22_acoustic_witness import (
        maybe_run_p22,
        MotionPrimitive,
        MotionBalance,
        P22AcousticVrittiWitness,
    )

    # In pipeline after P21:
    maybe_run_p22(ctx)

    # Check witness:
    if ctx.p22_acoustic_witness.dominant_motion == MotionPrimitive.FRICTION:
        # High friction detected in input
        ...

Design Principles:
    - Deterministic: Same inputs -> same outputs
    - Read-only: Does not modify context
    - Witness-only: Observes without influencing
    - Post-P21: Operates after delivery barrier
    - No authority: Cannot gate, block, or route

CRITICAL CONSTRAINTS:
    P22 MUST NOT:
        - Infer intent
        - Infer emotion
        - Infer meaning
        - Modify regime, discourse, semantics, or lexicon
        - Feed data back into P1-P21
        - Gate, block, or allow anything
        - Change system behavior

    P22 MUST:
        - Be deterministic
        - Be read-only
        - Be witness-only
        - Operate after P21
        - Never touch delivery decisions
"""

# Schema exports
from symbolu.mechanical.pipeline.p22_acoustic_witness.p22_schema import (
    # Version
    P22_VERSION,
    # Enums
    MotionPrimitive,
    MotionBalance,
    # Dataclasses
    P22AcousticVrittiWitness,
    # Exceptions
    P22InvariantViolation,
    # Factory functions
    create_empty_witness,
)

# Resolver exports
from symbolu.mechanical.pipeline.p22_acoustic_witness.p22_resolver import (
    AcousticVrittiWitnessResolver,
    resolve_acoustic_witness,
    VRITTI_TO_MOTION,
    FORBIDDEN_INTENT_ATTRS,
    FORBIDDEN_REGIME_ATTRS,
    FORBIDDEN_DISCOURSE_ATTRS,
    FORBIDDEN_SEMANTIC_ATTRS,
    FORBIDDEN_LEXICAL_ATTRS,
    FORBIDDEN_SAFETY_ATTRS,
    FORBIDDEN_PERSONA_ATTRS,
    ALL_FORBIDDEN_ATTRS,
)

# Integration exports
from symbolu.mechanical.pipeline.p22_acoustic_witness.p22_integration import (
    # Singleton
    get_p22_resolver,
    # Integration
    maybe_run_p22,
    run_p22,
    run_p22_directly,
    # Helpers
    is_p22_disabled,
    has_p22_witness,
    get_p22_witness,
    get_acoustic_signature,
    get_dominant_motion,
    get_motion_balance,
    get_pressure_band,
    get_vritti_vector,
    get_p22_version,
)


__all__ = [
    # Version
    "P22_VERSION",
    # Enums
    "MotionPrimitive",
    "MotionBalance",
    # Dataclasses
    "P22AcousticVrittiWitness",
    # Exceptions
    "P22InvariantViolation",
    # Factory functions
    "create_empty_witness",
    # Resolver
    "AcousticVrittiWitnessResolver",
    "resolve_acoustic_witness",
    # Constants - vritti mapping
    "VRITTI_TO_MOTION",
    # Constants - forbidden attributes
    "FORBIDDEN_INTENT_ATTRS",
    "FORBIDDEN_REGIME_ATTRS",
    "FORBIDDEN_DISCOURSE_ATTRS",
    "FORBIDDEN_SEMANTIC_ATTRS",
    "FORBIDDEN_LEXICAL_ATTRS",
    "FORBIDDEN_SAFETY_ATTRS",
    "FORBIDDEN_PERSONA_ATTRS",
    "ALL_FORBIDDEN_ATTRS",
    # Integration
    "get_p22_resolver",
    "maybe_run_p22",
    "run_p22",
    "run_p22_directly",
    # Helpers
    "is_p22_disabled",
    "has_p22_witness",
    "get_p22_witness",
    "get_acoustic_signature",
    "get_dominant_motion",
    "get_motion_balance",
    "get_pressure_band",
    "get_vritti_vector",
    "get_p22_version",
]
