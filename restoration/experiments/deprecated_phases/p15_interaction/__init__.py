"""
P15 — Interaction Mode Resolver

P15 is a deterministic, non-semantic, non-acoustic layer that determines
how interactive the system may be when delivering the already-realized expression.

P15 determines interaction posture only:
- Never alters wording, acoustics, or meaning
- Never introduces reasoning or explanation
- Never overrides HOLD/BLOCKED states

InteractionMode enum:
- READ_ONLY: Most conservative - presents information with no interaction
- ACK_ONLY: Simple acknowledgment only
- SUPPORTIVE: Gentle, non-directive support
- CLARIFYING: May ask clarifying questions
- INFORMATIVE: May provide informational content

Resolution Rules (strict, ordered):
1. If ctx.is_blocked → ACK_ONLY
2. If regime == HOLD → READ_ONLY
3. If discourse == DEFERRAL → ACK_ONLY
4. If discourse == QUESTION → CLARIFYING
5. If reflexive + regime in {DE_ESCALATE, STABILIZE} → SUPPORTIVE
6. If detached + discourse == EXPLANATION → INFORMATIVE
7. Fallback → READ_ONLY

Usage:
    from symbolu.mechanical.pipeline.p15_interaction import maybe_run_p15

    # After P14 stage
    maybe_run_p15(ctx)
    # ctx.interaction_directive is now set

CRITICAL: P15 produces an InteractionDirective, not content.
P15 cannot alter wording, acoustics, or meaning.
"""

# Schema exports
from symbolu.mechanical.pipeline.p15_interaction.p15_interaction_schema import (
    # Enums
    InteractionMode,
    # Dataclasses
    InteractionDirective,
    # Constants
    P15_VERSION,
    # Helper functions
    get_read_only_directive,
    get_ack_only_directive,
)

# Resolver exports
from symbolu.mechanical.pipeline.p15_interaction.p15_interaction_resolver import (
    # Classes
    P15InteractionResolver,
    # Standalone functions
    resolve_interaction_mode,
    # Constants - regime sets
    SUPPORTIVE_REGIMES,
    HOLD_REGIMES,
    DEFERRAL_DISCOURSE_ACTS,
    QUESTION_DISCOURSE_ACTS,
    EXPLANATION_DISCOURSE_ACTS,
    REFLEXIVE_GROUNDING_MODES,
    DETACHED_GROUNDING_MODES,
)

# Integration exports
from symbolu.mechanical.pipeline.p15_interaction.p15_integration import (
    # Core functions
    get_p15_resolver,
    maybe_run_p15,
    run_p15_directly,
    get_interaction_directive,
    # Mode accessors
    get_mode,
    is_read_only,
    is_ack_only,
    is_supportive,
    is_clarifying,
    is_informative,
    # Capability accessors
    allows_questions,
    allows_information,
    allows_support,
    is_blocked,
)


__all__ = [
    # Schema - Enums
    "InteractionMode",
    # Schema - Dataclasses
    "InteractionDirective",
    # Schema - Constants
    "P15_VERSION",
    # Schema - Helper functions
    "get_read_only_directive",
    "get_ack_only_directive",
    # Resolver - Classes
    "P15InteractionResolver",
    # Resolver - Standalone functions
    "resolve_interaction_mode",
    # Resolver - Constants
    "SUPPORTIVE_REGIMES",
    "HOLD_REGIMES",
    "DEFERRAL_DISCOURSE_ACTS",
    "QUESTION_DISCOURSE_ACTS",
    "EXPLANATION_DISCOURSE_ACTS",
    "REFLEXIVE_GROUNDING_MODES",
    "DETACHED_GROUNDING_MODES",
    # Integration - Core functions
    "get_p15_resolver",
    "maybe_run_p15",
    "run_p15_directly",
    "get_interaction_directive",
    # Integration - Mode accessors
    "get_mode",
    "is_read_only",
    "is_ack_only",
    "is_supportive",
    "is_clarifying",
    "is_informative",
    # Integration - Capability accessors
    "allows_questions",
    "allows_information",
    "allows_support",
    "is_blocked",
]
