"""
P9 - Lexical Selection Pipeline Integration Module

Provides a thin shim for integrating P9 (Lexical Selection Engine)
into the Symbol-U pipeline. Called immediately after P8, before any
acoustic/prosody processing.

P9 is a post-semantic, pre-acoustic phase.

Usage in orchestrator:
    from .p9_lexical.p9_integration import maybe_run_p9

    # After P8 stage
    maybe_run_p9(ctx)
    # ctx.lexical_frame is now set

Authority Model:
    - P9 consumes P8 SemanticFrame, P7 DiscourseEnvelope, P6 RegimeEnvelope
    - P9 cannot override P1-P8 decisions
    - P9 produces LexicalFrame (read-only, constrains acoustic generation)
    - P9 does NOT perform syntax construction, word ordering, or acoustic modulation

CRITICAL: P9 is gating-only and deterministic. It constrains downstream
acoustic generation but does not directly produce any output.
"""

from typing import Any, Dict, Optional

from symbolu_core.mechanical.pipeline.p8_semantics.p8_semantic_schema import (
    SemanticFrame,
    SemanticSlot,
)
from symbolu_core.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
)
from symbolu_core.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu_core.mechanical.pipeline.p9_lexical.p9_lexical_schema import LexicalFrame
from symbolu_core.mechanical.pipeline.p9_lexical.p9_lexical_resolver import P9LexicalResolver


# Singleton P9 resolver instance
_p9_resolver: Optional[P9LexicalResolver] = None


def get_p9_resolver() -> P9LexicalResolver:
    """Get or create the singleton P9 lexical resolver instance."""
    global _p9_resolver
    if _p9_resolver is None:
        _p9_resolver = P9LexicalResolver()
    return _p9_resolver


def is_lexicalization_allowed(ctx: Any) -> bool:
    """
    Check if lexicalization is allowed for this context.

    Lexicalization is NOT allowed if:
    - P8 SemanticFrame is not present
    - SemanticFrame is not allowed
    - Regime is HOLD (but P9 will still run and return empty frame)

    Args:
        ctx: Pipeline context.

    Returns:
        True if lexicalization is allowed, False otherwise.
    """
    # Check if P8 output is available
    if not hasattr(ctx, 'semantic_frame') or ctx.semantic_frame is None:
        return False

    # Check if semantic frame is allowed
    semantic_frame: SemanticFrame = ctx.semantic_frame
    if not semantic_frame.allowed:
        return False

    return True


def maybe_run_p9(ctx: Any) -> None:
    """
    Run P9 lexical selection on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    P9 requires P8, P7, and P6 to be present.

    IMPORTANT: This function attaches the result to ctx.lexical_frame.
    It does NOT return the frame - use get_p9_lexical_frame(ctx) to retrieve it.

    CRITICAL: P9 is gating-only and deterministic. It constrains downstream
    acoustic generation but does not directly produce any output.

    Rules:
    - Run only if P8, P7, and P6 exist
    - Attach LexicalFrame to ctx.lexical_frame
    - Must not alter upstream behavior

    Args:
        ctx: Pipeline context with semantic_frame, p7_discourse_envelope,
             and p6_regime.
    """
    # Check if P8 output is available
    if not hasattr(ctx, 'semantic_frame') or ctx.semantic_frame is None:
        return

    # Check if P7 output is available (required for P9)
    if not hasattr(ctx, 'p7_discourse_envelope') or ctx.p7_discourse_envelope is None:
        return

    # Check if P6 output is available (required for P9)
    if not hasattr(ctx, 'p6_regime') or ctx.p6_regime is None:
        return

    semantic_frame: SemanticFrame = ctx.semantic_frame
    discourse_envelope: DiscourseEnvelope = ctx.p7_discourse_envelope
    regime_envelope: RegimeEnvelope = ctx.p6_regime

    # Run P9 resolver
    resolver = get_p9_resolver()
    frame = resolver.resolve(
        semantic_frame=semantic_frame,
        discourse_envelope=discourse_envelope,
        regime_envelope=regime_envelope,
    )

    # Attach to context (gating capture, no execution)
    ctx.lexical_frame = frame


def run_p9_directly(
    semantic_frame: SemanticFrame,
    discourse_envelope: DiscourseEnvelope,
    regime_envelope: RegimeEnvelope,
) -> LexicalFrame:
    """
    Run P9 directly with explicit inputs.

    Useful for testing or standalone lexical selection.

    CRITICAL: The lexical frame constrains downstream acoustic generation
    but does not directly produce any output.

    Args:
        semantic_frame: SemanticFrame from P8.
        discourse_envelope: DiscourseEnvelope from P7.
        regime_envelope: RegimeEnvelope from P6.

    Returns:
        LexicalFrame with lexical selection verdict.
    """
    resolver = get_p9_resolver()
    return resolver.resolve(
        semantic_frame=semantic_frame,
        discourse_envelope=discourse_envelope,
        regime_envelope=regime_envelope,
    )


def get_p9_lexical_frame(ctx: Any) -> Optional[LexicalFrame]:
    """
    Get the P9 lexical frame from context.

    Args:
        ctx: Pipeline context.

    Returns:
        LexicalFrame or None if not available.
    """
    if not hasattr(ctx, 'lexical_frame'):
        return None
    return ctx.lexical_frame


def is_lexical_frame_allowed(ctx: Any) -> bool:
    """
    Check if lexical frame is allowed.

    Args:
        ctx: Pipeline context.

    Returns:
        True if lexical frame is allowed, False otherwise.
        Returns False (conservative) if P9 hasn't run.
    """
    frame = get_p9_lexical_frame(ctx)
    if frame is None:
        # Conservative default: if P9 hasn't run, consider not allowed
        return False
    return frame.allowed


def is_lexical_frame_empty(ctx: Any) -> bool:
    """
    Check if lexical frame is empty (no selections).

    Args:
        ctx: Pipeline context.

    Returns:
        True if frame is empty, False otherwise.
        Returns True (conservative) if P9 hasn't run.
    """
    frame = get_p9_lexical_frame(ctx)
    if frame is None:
        # Conservative default: if P9 hasn't run, consider empty
        return True
    return frame.is_empty()


def get_lexical_frame_reason(ctx: Any) -> Optional[str]:
    """
    Get the reason string from the P9 lexical frame verdict.

    Args:
        ctx: Pipeline context.

    Returns:
        Reason string or None if P9 hasn't run.
    """
    frame = get_p9_lexical_frame(ctx)
    if frame is None:
        return None
    return frame.reason


def get_lexical_selection(ctx: Any, slot: SemanticSlot) -> Optional[str]:
    """
    Get a specific lexical selection from the frame.

    Args:
        ctx: Pipeline context.
        slot: The SemanticSlot to retrieve.

    Returns:
        Lexical selection string or None if not present/selected.
    """
    frame = get_p9_lexical_frame(ctx)
    if frame is None:
        return None
    return frame.get_selection(slot)


def has_lexical_selection(ctx: Any, slot: SemanticSlot) -> bool:
    """
    Check if a slot has a lexical selection in the frame.

    Args:
        ctx: Pipeline context.
        slot: The SemanticSlot to check.

    Returns:
        True if slot has a selection, False otherwise.
    """
    frame = get_p9_lexical_frame(ctx)
    if frame is None:
        return False
    return frame.has_slot(slot)


def get_all_lexical_selections(ctx: Any) -> Dict[SemanticSlot, str]:
    """
    Get all lexical selections from the frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Dictionary of selections or empty dict if P9 hasn't run.
    """
    frame = get_p9_lexical_frame(ctx)
    if frame is None:
        return {}
    return frame.get_all_selections()


def get_lexical_selection_count(ctx: Any) -> int:
    """
    Get the number of lexical selections in the frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Number of selections or 0 if P9 hasn't run.
    """
    frame = get_p9_lexical_frame(ctx)
    if frame is None:
        return 0
    return frame.count()


def get_source_discourse_act(ctx: Any) -> Optional[str]:
    """
    Get the source discourse act from the lexical frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Discourse act string or None if P9 hasn't run.
    """
    frame = get_p9_lexical_frame(ctx)
    if frame is None:
        return None
    return frame.source_discourse_act


def get_source_regime(ctx: Any) -> Optional[str]:
    """
    Get the source regime from the lexical frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Regime string or None if P9 hasn't run.
    """
    frame = get_p9_lexical_frame(ctx)
    if frame is None:
        return None
    return frame.source_regime


__all__ = [
    "get_p9_resolver",
    "is_lexicalization_allowed",
    "maybe_run_p9",
    "run_p9_directly",
    "get_p9_lexical_frame",
    "is_lexical_frame_allowed",
    "is_lexical_frame_empty",
    "get_lexical_frame_reason",
    "get_lexical_selection",
    "has_lexical_selection",
    "get_all_lexical_selections",
    "get_lexical_selection_count",
    "get_source_discourse_act",
    "get_source_regime",
]
