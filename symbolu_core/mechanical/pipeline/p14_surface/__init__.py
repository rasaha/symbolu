"""
P14 - Expression Surface Realizer

P14 is the first "surface shaping" phase in the Symbol-U pipeline.
It converts upstream frames (PO1-P13 + P9 lexical) into a SurfacePlan:
a deterministic, safe, minimally expressive plan for how an output
should look as text.

Key Characteristics:
- Deterministic: No LLM calls, no probabilistic behavior
- Conservative: Stricter behavior when uncertain
- Authority-Respecting: Cannot override PO1-P13 constraints
- Sound-Agnostic: Pre-acoustic and pre-renderer
- Strict Allow-List: Only connectors from curated pools

P14 Controls:
- Text-level expressiveness (punctuation, sentence shape, hedges, brevity)
- Surface styling (MINIMAL, NEUTRAL, GENTLE, FORMAL, DEFERRAL_MINIMAL)
- Persona signals (SAFE_ACK, SAFE_REFLECT, SAFE_CLARIFY)
- Forbidden tokens (avoid certainty markers, diagnostic language)

P14 Does NOT:
- Generate free-form paragraphs or final text
- Change semantic intent
- Invent content
- Require phonemes, TTS, or audio
- Call LLMs or use ML models

Authority Flow:
    PO1 -> PO2 -> ... -> P13 -> P14 -> (Renderers)

Usage:
    from symbolu_core.mechanical.pipeline.p14_surface import (
        maybe_run_p14,
        get_p14_surface_plan,
        SurfacePlan,
        SurfaceStyle,
    )

    # In pipeline orchestrator
    maybe_run_p14(ctx)

    # Access plan
    plan = get_p14_surface_plan(ctx)
    if plan.is_deferral():
        # Handle deferral mode
        pass
"""

# Schema exports
from symbolu_core.mechanical.pipeline.p14_surface.p14_surface_schema import (
    # Enums
    SurfaceStyle,
    PunctuationPolicy,
    HedgePolicy,
    LengthPolicy,
    PersonaSignalPolicy,
    # Dataclasses
    SurfacePlan,
    # Constants - connector pools
    DEFERRAL_CONNECTORS,
    REFLECT_CONNECTORS,
    ACK_CONNECTORS,
    CLARIFY_CONNECTORS,
    NEVER_ALLOWED_CONNECTORS,
    # Constants - forbidden tokens
    DEFAULT_FORBIDDEN_TOKENS,
    RELATIONAL_FORBIDDEN_TOKENS,
    # Constants - hedge words
    LIGHT_HEDGE_WORDS,
    REQUIRED_HEDGE_WORDS,
    # Constants - version
    P14_VERSION,
    # Helper functions
    get_deferral_plan,
    build_forbidden_tokens,
)

# Realizer exports
from symbolu_core.mechanical.pipeline.p14_surface.p14_surface_realizer import (
    # Constants
    DEFERRAL_REGIMES,
    CAREFUL_REGIMES,
    INFORM_REGIMES,
    REFLECTION_DISCOURSE_ACTS,
    ACK_DISCOURSE_ACTS,
    QUESTION_DISCOURSE_ACTS,
    EXPLANATION_DISCOURSE_ACTS,
    RELATIONAL_GROUNDING_MODES,
    AUTHORITY_RESTRICTED_MODES,
    # Resolution functions
    resolve_style,
    resolve_punctuation,
    resolve_hedging,
    resolve_length,
    resolve_persona_signals,
    resolve_allowed_connectors,
    resolve_requires_question,
    # Realizer class
    P14SurfaceRealizer,
)

# Integration exports
from symbolu_core.mechanical.pipeline.p14_surface.p14_integration import (
    # Core functions
    get_p14_realizer,
    maybe_run_p14,
    run_p14_directly,
    get_p14_surface_plan,
    # Style accessors
    get_style,
    is_minimal,
    is_deferral,
    is_gentle,
    is_neutral,
    is_formal,
    # Punctuation accessors
    get_punctuation_policy,
    allows_exclamation,
    allows_ellipsis,
    # Hedging accessors
    get_hedge_policy,
    requires_hedging,
    # Length accessors
    get_length_policy,
    allows_bullets,
    get_max_sentences,
    # Persona signal accessors
    get_persona_signals,
    requires_question,
    # Connector accessors
    get_allowed_connectors,
    has_connector,
    # Forbidden token accessors
    get_forbidden_tokens,
    is_forbidden,
)


__all__ = [
    # === Schema Exports ===
    # Enums
    "SurfaceStyle",
    "PunctuationPolicy",
    "HedgePolicy",
    "LengthPolicy",
    "PersonaSignalPolicy",
    # Dataclasses
    "SurfacePlan",
    # Constants - connector pools
    "DEFERRAL_CONNECTORS",
    "REFLECT_CONNECTORS",
    "ACK_CONNECTORS",
    "CLARIFY_CONNECTORS",
    "NEVER_ALLOWED_CONNECTORS",
    # Constants - forbidden tokens
    "DEFAULT_FORBIDDEN_TOKENS",
    "RELATIONAL_FORBIDDEN_TOKENS",
    # Constants - hedge words
    "LIGHT_HEDGE_WORDS",
    "REQUIRED_HEDGE_WORDS",
    # Constants - version
    "P14_VERSION",
    # Helper functions
    "get_deferral_plan",
    "build_forbidden_tokens",
    # === Realizer Exports ===
    # Constants
    "DEFERRAL_REGIMES",
    "CAREFUL_REGIMES",
    "INFORM_REGIMES",
    "REFLECTION_DISCOURSE_ACTS",
    "ACK_DISCOURSE_ACTS",
    "QUESTION_DISCOURSE_ACTS",
    "EXPLANATION_DISCOURSE_ACTS",
    "RELATIONAL_GROUNDING_MODES",
    "AUTHORITY_RESTRICTED_MODES",
    # Resolution functions
    "resolve_style",
    "resolve_punctuation",
    "resolve_hedging",
    "resolve_length",
    "resolve_persona_signals",
    "resolve_allowed_connectors",
    "resolve_requires_question",
    # Realizer class
    "P14SurfaceRealizer",
    # === Integration Exports ===
    # Core functions
    "get_p14_realizer",
    "maybe_run_p14",
    "run_p14_directly",
    "get_p14_surface_plan",
    # Style accessors
    "get_style",
    "is_minimal",
    "is_deferral",
    "is_gentle",
    "is_neutral",
    "is_formal",
    # Punctuation accessors
    "get_punctuation_policy",
    "allows_exclamation",
    "allows_ellipsis",
    # Hedging accessors
    "get_hedge_policy",
    "requires_hedging",
    # Length accessors
    "get_length_policy",
    "allows_bullets",
    "get_max_sentences",
    # Persona signal accessors
    "get_persona_signals",
    "requires_question",
    # Connector accessors
    "get_allowed_connectors",
    "has_connector",
    # Forbidden token accessors
    "get_forbidden_tokens",
    "is_forbidden",
]
