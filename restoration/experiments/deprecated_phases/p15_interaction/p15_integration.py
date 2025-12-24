"""
P15 - Interaction Mode Resolver Pipeline Integration Module

Provides a thin shim for integrating P15 (Interaction Mode Resolver)
into the Symbol-U pipeline. Called immediately after P14, before any
downstream delivery or rendering.

P15 produces an InteractionDirective, not content. It is CONSTRAINED
by P13 and P14 and cannot modify their outputs.

Usage in orchestrator:
    from .p15_interaction.p15_integration import maybe_run_p15

    # After P14 stage
    maybe_run_p15(ctx)
    # ctx.interaction_directive is now set (or read_only if insufficient data)

Authority Model:
    - P15 consumes P6, P7, PO1 outputs (read-only)
    - P15 cannot mutate any upstream output
    - P15 cannot override P13 or P14 constraints
    - P15 produces InteractionDirective (read-only)
    - P15 failure forces READ_ONLY directive

CRITICAL: P15 determines interaction posture only.
P15 cannot alter wording, acoustics, or meaning.

ARCHITECTURAL PRINCIPLE:
    P15 produces an InteractionDirective, not content.
    P15 is constrained by P13 and P14.
    P15 is pre-delivery and post-surface.
"""

from typing import Any, Optional

from symbolu.mechanical.pipeline.p15_interaction.p15_interaction_schema import (
    InteractionMode,
    InteractionDirective,
    get_read_only_directive,
    get_ack_only_directive,
)
from symbolu.mechanical.pipeline.p15_interaction.p15_interaction_resolver import (
    P15InteractionResolver,
)


# Singleton P15 resolver instance
_p15_resolver: Optional[P15InteractionResolver] = None


def get_p15_resolver() -> P15InteractionResolver:
    """Get or create the singleton P15 interaction resolver instance."""
    global _p15_resolver
    if _p15_resolver is None:
        _p15_resolver = P15InteractionResolver()
    return _p15_resolver


def maybe_run_p15(ctx: Any) -> Any:
    """
    Run P15 interaction mode resolution on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    P15 requires P6/P7 to have run for mode determination, but will produce
    a READ_ONLY directive if upstream phases are missing.

    IMPORTANT: This function attaches the result to ctx.interaction_directive.
    It returns the context unchanged (for chaining).

    CRITICAL: P15 produces an InteractionDirective, not content.
    The directive constrains downstream delivery.

    Rules:
    - If ctx.interaction_directive already exists -> return ctx unchanged
    - If P6/P7 are not available -> attach READ_ONLY directive
    - On any error -> attach READ_ONLY directive
    - Attach InteractionDirective to ctx.interaction_directive

    Args:
        ctx: Pipeline context with phase outputs.

    Returns:
        The same context object (for chaining).
    """
    # Rule 1: If P15 already ran, don't run again
    if hasattr(ctx, 'interaction_directive') and ctx.interaction_directive is not None:
        return ctx

    # Run P15 resolver
    try:
        resolver = get_p15_resolver()
        directive = resolver.resolve(ctx)

        # Attach to context
        if directive is not None:
            ctx.interaction_directive = directive
        else:
            # Should not happen (resolver returns fallback on missing upstream)
            # but defensive: attach read_only directive
            ctx.interaction_directive = get_read_only_directive()
    except Exception:
        # Fail-closed: on any error, attach read_only directive
        ctx.interaction_directive = get_read_only_directive()

    return ctx


def run_p15_directly(ctx: Any) -> Optional[InteractionDirective]:
    """
    Run P15 directly with explicit context.

    Useful for testing or standalone interaction mode computation.

    CRITICAL: The directive is NOT attached to context.
    Downstream phases should consume the returned directive.

    Args:
        ctx: Pipeline context with phase outputs.

    Returns:
        InteractionDirective with interaction mode.
    """
    resolver = get_p15_resolver()
    return resolver.resolve(ctx)


def get_interaction_directive(ctx: Any) -> Optional[InteractionDirective]:
    """
    Get the P15 interaction directive from context.

    Args:
        ctx: Pipeline context.

    Returns:
        InteractionDirective or None if not available.
    """
    if not hasattr(ctx, 'interaction_directive'):
        return None
    return ctx.interaction_directive


# ============================================================================
# MODE ACCESSORS
# ============================================================================


def get_mode(ctx: Any) -> InteractionMode:
    """
    Get the interaction mode from the directive.

    Args:
        ctx: Pipeline context.

    Returns:
        InteractionMode (defaults to READ_ONLY if not available).
    """
    directive = get_interaction_directive(ctx)
    if directive is None:
        return InteractionMode.READ_ONLY  # Conservative default
    return directive.mode


def is_read_only(ctx: Any) -> bool:
    """
    Check if mode is READ_ONLY.

    Args:
        ctx: Pipeline context.

    Returns:
        True if READ_ONLY, False otherwise.
        Returns True if P15 hasn't run (conservative default).
    """
    directive = get_interaction_directive(ctx)
    if directive is None:
        return True  # Conservative: read_only if no directive
    return directive.is_read_only()


def is_ack_only(ctx: Any) -> bool:
    """
    Check if mode is ACK_ONLY.

    Args:
        ctx: Pipeline context.

    Returns:
        True if ACK_ONLY, False otherwise.
    """
    directive = get_interaction_directive(ctx)
    if directive is None:
        return False
    return directive.is_ack_only()


def is_supportive(ctx: Any) -> bool:
    """
    Check if mode is SUPPORTIVE.

    Args:
        ctx: Pipeline context.

    Returns:
        True if SUPPORTIVE, False otherwise.
    """
    directive = get_interaction_directive(ctx)
    if directive is None:
        return False
    return directive.is_supportive()


def is_clarifying(ctx: Any) -> bool:
    """
    Check if mode is CLARIFYING.

    Args:
        ctx: Pipeline context.

    Returns:
        True if CLARIFYING, False otherwise.
    """
    directive = get_interaction_directive(ctx)
    if directive is None:
        return False
    return directive.is_clarifying()


def is_informative(ctx: Any) -> bool:
    """
    Check if mode is INFORMATIVE.

    Args:
        ctx: Pipeline context.

    Returns:
        True if INFORMATIVE, False otherwise.
    """
    directive = get_interaction_directive(ctx)
    if directive is None:
        return False
    return directive.is_informative()


# ============================================================================
# CAPABILITY ACCESSORS
# ============================================================================


def allows_questions(ctx: Any) -> bool:
    """
    Check if questions are allowed in this mode.

    Args:
        ctx: Pipeline context.

    Returns:
        True if questions allowed, False otherwise.
        Returns False if P15 hasn't run (conservative).
    """
    directive = get_interaction_directive(ctx)
    if directive is None:
        return False
    return directive.allows_questions()


def allows_information(ctx: Any) -> bool:
    """
    Check if informational content is allowed in this mode.

    Args:
        ctx: Pipeline context.

    Returns:
        True if information allowed, False otherwise.
        Returns False if P15 hasn't run (conservative).
    """
    directive = get_interaction_directive(ctx)
    if directive is None:
        return False
    return directive.allows_information()


def allows_support(ctx: Any) -> bool:
    """
    Check if supportive content is allowed in this mode.

    Args:
        ctx: Pipeline context.

    Returns:
        True if support allowed, False otherwise.
        Returns False if P15 hasn't run (conservative).
    """
    directive = get_interaction_directive(ctx)
    if directive is None:
        return False
    return directive.allows_support()


def is_blocked(ctx: Any) -> bool:
    """
    Check if interaction is blocked.

    Args:
        ctx: Pipeline context.

    Returns:
        True if blocked, False otherwise.
        Returns False if P15 hasn't run.
    """
    directive = get_interaction_directive(ctx)
    if directive is None:
        return False
    return directive.blocked


__all__ = [
    # Core functions
    "get_p15_resolver",
    "maybe_run_p15",
    "run_p15_directly",
    "get_interaction_directive",
    # Mode accessors
    "get_mode",
    "is_read_only",
    "is_ack_only",
    "is_supportive",
    "is_clarifying",
    "is_informative",
    # Capability accessors
    "allows_questions",
    "allows_information",
    "allows_support",
    "is_blocked",
]
