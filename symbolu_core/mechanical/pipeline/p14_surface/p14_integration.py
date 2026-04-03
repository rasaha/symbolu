"""
P14 - Expression Surface Realizer Pipeline Integration Module

Provides a thin shim for integrating P14 (Expression Surface Realizer)
into the Symbol-U pipeline. Called immediately after P13, before any
downstream rendering or text generation.

P14 produces a SurfacePlan, not text. It is CONSTRAINED by P13.

Usage in orchestrator:
    from .p14_surface.p14_integration import maybe_run_p14

    # After P13 stage
    maybe_run_p14(ctx)
    # ctx.p14_surface is now set (or deferral plan if insufficient data)

Authority Model:
    - P14 consumes PO1, PO2, P6, P7, P8, P9, P13 outputs (read-only)
    - P14 cannot mutate any upstream output
    - P14 cannot override P13 safety constraints
    - P14 produces SurfacePlan (read-only)
    - P14 failure forces deferral plan

CRITICAL: P14 produces a SurfacePlan, not text.
Downstream renderers consume the SurfacePlan.

ARCHITECTURAL PRINCIPLE:
    P14 produces a SurfacePlan, not text.
    P14 is constrained by P13.
    P14 is pre-acoustic and pre-renderer.
"""

from typing import Any, List, Optional, Tuple

from symbolu_core.mechanical.pipeline.p14_surface.p14_surface_schema import (
    SurfaceStyle,
    PunctuationPolicy,
    HedgePolicy,
    LengthPolicy,
    PersonaSignalPolicy,
    SurfacePlan,
    get_deferral_plan,
)
from symbolu_core.mechanical.pipeline.p14_surface.p14_surface_realizer import (
    P14SurfaceRealizer,
)


# Singleton P14 realizer instance
_p14_realizer: Optional[P14SurfaceRealizer] = None


def get_p14_realizer() -> P14SurfaceRealizer:
    """Get or create the singleton P14 surface realizer instance."""
    global _p14_realizer
    if _p14_realizer is None:
        _p14_realizer = P14SurfaceRealizer()
    return _p14_realizer


def maybe_run_p14(ctx: Any) -> Any:
    """
    Run P14 expression surface realization on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    P14 requires P13 to have run for safety synchronization, but will produce
    a deferral plan if upstream phases are missing.

    IMPORTANT: This function attaches the result to ctx.p14_surface.
    It returns the context unchanged (for chaining).

    CRITICAL: P14 produces a SurfacePlan, not text.
    The plan constrains downstream rendering.

    Rules:
    - If ctx.p14_surface already exists -> return ctx unchanged
    - If P13 is not available -> attach deferral plan
    - On any error -> attach deferral plan
    - Attach SurfacePlan to ctx.p14_surface

    Args:
        ctx: Pipeline context with phase outputs.

    Returns:
        The same context object (for chaining).
    """
    # Rule 1: If P14 already ran, don't run again
    if hasattr(ctx, 'p14_surface') and ctx.p14_surface is not None:
        return ctx

    # Run P14 realizer
    try:
        realizer = get_p14_realizer()
        plan = realizer.realize(ctx)

        # Attach to context
        if plan is not None:
            ctx.p14_surface = plan
        else:
            # Should not happen (realizer returns deferral on missing upstream)
            # but defensive: attach deferral plan
            ctx.p14_surface = get_deferral_plan()
    except Exception:
        # Fail-closed: on any error, attach deferral plan
        ctx.p14_surface = get_deferral_plan()

    return ctx


def run_p14_directly(ctx: Any) -> Optional[SurfacePlan]:
    """
    Run P14 directly with explicit context.

    Useful for testing or standalone surface plan computation.

    CRITICAL: The plan is NOT attached to context.
    Downstream phases should consume the returned plan.

    Args:
        ctx: Pipeline context with phase outputs.

    Returns:
        SurfacePlan with surface policies.
    """
    realizer = get_p14_realizer()
    return realizer.realize(ctx)


def get_p14_surface_plan(ctx: Any) -> Optional[SurfacePlan]:
    """
    Get the P14 surface plan from context.

    Args:
        ctx: Pipeline context.

    Returns:
        SurfacePlan or None if not available.
    """
    if not hasattr(ctx, 'p14_surface'):
        return None
    return ctx.p14_surface


# ============================================================================
# STYLE ACCESSORS
# ============================================================================


def get_style(ctx: Any) -> SurfaceStyle:
    """
    Get the surface style from the plan.

    Args:
        ctx: Pipeline context.

    Returns:
        SurfaceStyle (defaults to DEFERRAL_MINIMAL if not available).
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        return SurfaceStyle.DEFERRAL_MINIMAL  # Conservative default
    return plan.style


def is_minimal(ctx: Any) -> bool:
    """
    Check if style is MINIMAL.

    Args:
        ctx: Pipeline context.

    Returns:
        True if MINIMAL, False otherwise.
    """
    return get_style(ctx) == SurfaceStyle.MINIMAL


def is_deferral(ctx: Any) -> bool:
    """
    Check if style is DEFERRAL_MINIMAL.

    Args:
        ctx: Pipeline context.

    Returns:
        True if DEFERRAL_MINIMAL, False otherwise.
        Returns True if P14 hasn't run (conservative default).
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        return True  # Conservative: deferral if no plan
    return plan.is_deferral()


def is_gentle(ctx: Any) -> bool:
    """
    Check if style is GENTLE.

    Args:
        ctx: Pipeline context.

    Returns:
        True if GENTLE, False otherwise.
    """
    return get_style(ctx) == SurfaceStyle.GENTLE


def is_neutral(ctx: Any) -> bool:
    """
    Check if style is NEUTRAL.

    Args:
        ctx: Pipeline context.

    Returns:
        True if NEUTRAL, False otherwise.
    """
    return get_style(ctx) == SurfaceStyle.NEUTRAL


def is_formal(ctx: Any) -> bool:
    """
    Check if style is FORMAL.

    Args:
        ctx: Pipeline context.

    Returns:
        True if FORMAL, False otherwise.
    """
    return get_style(ctx) == SurfaceStyle.FORMAL


# ============================================================================
# PUNCTUATION ACCESSORS
# ============================================================================


def get_punctuation_policy(ctx: Any) -> PunctuationPolicy:
    """
    Get the punctuation policy from the plan.

    Args:
        ctx: Pipeline context.

    Returns:
        PunctuationPolicy (defaults to BASIC_PERIODS if not available).
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        return PunctuationPolicy.BASIC_PERIODS  # Conservative default
    return plan.punctuation


def allows_exclamation(ctx: Any) -> bool:
    """
    Check if exclamation marks are allowed.

    Args:
        ctx: Pipeline context.

    Returns:
        True if allowed, False otherwise.
        Returns False if P14 hasn't run (conservative).
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        return False
    return plan.allows_exclamation()


def allows_ellipsis(ctx: Any) -> bool:
    """
    Check if ellipsis is allowed.

    Args:
        ctx: Pipeline context.

    Returns:
        True if allowed, False otherwise.
        Returns False if P14 hasn't run (conservative).
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        return False
    return plan.allows_ellipsis()


# ============================================================================
# HEDGING ACCESSORS
# ============================================================================


def get_hedge_policy(ctx: Any) -> HedgePolicy:
    """
    Get the hedging policy from the plan.

    Args:
        ctx: Pipeline context.

    Returns:
        HedgePolicy (defaults to NONE if not available).
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        return HedgePolicy.NONE
    return plan.hedging


def requires_hedging(ctx: Any) -> bool:
    """
    Check if hedging is required.

    Args:
        ctx: Pipeline context.

    Returns:
        True if required, False otherwise.
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        return False
    return plan.requires_hedging()


# ============================================================================
# LENGTH ACCESSORS
# ============================================================================


def get_length_policy(ctx: Any) -> LengthPolicy:
    """
    Get the length policy from the plan.

    Args:
        ctx: Pipeline context.

    Returns:
        LengthPolicy (defaults to ONE_SENTENCE if not available).
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        return LengthPolicy.ONE_SENTENCE  # Conservative default
    return plan.length


def allows_bullets(ctx: Any) -> bool:
    """
    Check if bullet lists are allowed.

    Args:
        ctx: Pipeline context.

    Returns:
        True if allowed, False otherwise.
        Returns False if P14 hasn't run (conservative).
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        return False
    return plan.allows_bullets()


def get_max_sentences(ctx: Any) -> int:
    """
    Get the maximum allowed sentences.

    Args:
        ctx: Pipeline context.

    Returns:
        Maximum sentences (defaults to 1 if not available).
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        return 1  # Conservative default
    return plan.get_max_sentences()


# ============================================================================
# PERSONA SIGNAL ACCESSORS
# ============================================================================


def get_persona_signals(ctx: Any) -> PersonaSignalPolicy:
    """
    Get the persona signals policy from the plan.

    Args:
        ctx: Pipeline context.

    Returns:
        PersonaSignalPolicy (defaults to NONE if not available).
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        return PersonaSignalPolicy.NONE
    return plan.persona_signals


def requires_question(ctx: Any) -> bool:
    """
    Check if output must be a question.

    Args:
        ctx: Pipeline context.

    Returns:
        True if question required, False otherwise.
        Returns True if P14 hasn't run (conservative for deferral).
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        return True  # Conservative: require question
    return plan.requires_question


# ============================================================================
# CONNECTOR ACCESSORS
# ============================================================================


def get_allowed_connectors(ctx: Any) -> Tuple[str, ...]:
    """
    Get the allowed connectors from the plan.

    Args:
        ctx: Pipeline context.

    Returns:
        Tuple of allowed connector strings (empty if not available).
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        return ()
    return plan.allowed_connectors


def has_connector(ctx: Any, connector: str) -> bool:
    """
    Check if a connector is in the allowed list.

    Args:
        ctx: Pipeline context.
        connector: The connector to check.

    Returns:
        True if allowed, False otherwise.
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        return False
    return plan.has_connector(connector)


# ============================================================================
# FORBIDDEN TOKEN ACCESSORS
# ============================================================================


def get_forbidden_tokens(ctx: Any) -> Tuple[str, ...]:
    """
    Get the forbidden tokens from the plan.

    Args:
        ctx: Pipeline context.

    Returns:
        Tuple of forbidden token strings.
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        from symbolu_core.mechanical.pipeline.p14_surface.p14_surface_schema import DEFAULT_FORBIDDEN_TOKENS
        return DEFAULT_FORBIDDEN_TOKENS
    return plan.forbidden_tokens


def is_forbidden(ctx: Any, token: str) -> bool:
    """
    Check if a token is forbidden.

    Args:
        ctx: Pipeline context.
        token: The token to check.

    Returns:
        True if forbidden, False otherwise.
    """
    plan = get_p14_surface_plan(ctx)
    if plan is None:
        # Conservative check against defaults
        from symbolu_core.mechanical.pipeline.p14_surface.p14_surface_schema import DEFAULT_FORBIDDEN_TOKENS
        token_lower = token.lower()
        for forbidden in DEFAULT_FORBIDDEN_TOKENS:
            if forbidden.lower() in token_lower:
                return True
        return False
    return plan.is_forbidden(token)


__all__ = [
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
