"""
P8 - Semantic Slot Resolution Pipeline Integration Module

Provides a thin shim for integrating P8 (Semantic Slot Resolver)
into the Symbol-U pipeline. Called immediately after P7, before any
lexical/word-level language processing.

P8 is a post-discourse, pre-lexical phase.

Usage in orchestrator:
    from .p8_semantics.p8_semantic_integration import maybe_run_p8

    # After P7 stage
    maybe_run_p8(ctx)
    # ctx.semantic_frame is now set

Authority Model:
    - P8 consumes PO1 PhaseMinusOneEnvelope, PO2 IntentEnvelope,
      P6 RegimeEnvelope, and P7 DiscourseEnvelope
    - P8 cannot override PO1-P7 decisions
    - P8 produces SemanticFrame (read-only, constrains lexical generation)
    - P8 does NOT perform lexical selection, word choice, or syntax

CRITICAL: P8 is gating-only and deterministic. It constrains downstream
lexical generation but does not directly produce any output.
"""

from typing import Any, Dict, Optional

from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_schema import (
    PhaseMinusOneEnvelope,
)
from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import IntentEnvelope
from symbolu_core.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu_core.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
    DiscourseAct,
)
from symbolu_core.mechanical.pipeline.p8_semantics.p8_semantic_schema import (
    SemanticFrame,
    SemanticSlot,
)
from symbolu_core.mechanical.pipeline.p8_semantics.p8_semantic_resolver import (
    P8SemanticResolver,
)


# Singleton P8 resolver instance
_p8_resolver: Optional[P8SemanticResolver] = None


def get_p8_resolver() -> P8SemanticResolver:
    """Get or create the singleton P8 semantic resolver instance."""
    global _p8_resolver
    if _p8_resolver is None:
        _p8_resolver = P8SemanticResolver()
    return _p8_resolver


def _has_blocked_upstream(ctx: Any) -> bool:
    """
    Check if any upstream envelope is blocked.

    This function checks if PO1-P7 have any blocking conditions
    that would prevent P8 from running.

    Args:
        ctx: Pipeline context.

    Returns:
        True if any upstream is blocked, False otherwise.
    """
    # Check PO1 for BLOCKED policy
    if hasattr(ctx, 'phase_minus_one') and ctx.phase_minus_one is not None:
        if ctx.phase_minus_one.is_blocked():
            return True

    # Check P6 for HOLD regime - P8 can still run but will produce DEFERRAL frame
    # Not blocking here, resolver will handle

    # Check P7 for DEFERRAL - P8 can still run with DEFERRAL act
    # Not blocking here, resolver will handle

    return False


def maybe_run_p8(ctx: Any) -> None:
    """
    Run P8 semantic slot resolution on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    P8 requires PO1, PO2, P6, and P7 to be present.

    IMPORTANT: This function attaches the result to ctx.semantic_frame.
    It does NOT return the frame - use get_p8_semantic_frame(ctx) to retrieve it.

    CRITICAL: P8 is gating-only and deterministic. It constrains downstream
    lexical generation but does not directly produce any output.

    Rules:
    - Run only if PO1, PO2, P6, and P7 exist
    - Regime is not BLOCKED (conservative check)
    - Attach SemanticFrame to ctx.semantic_frame
    - Must not alter upstream behavior

    Args:
        ctx: Pipeline context with phase_minus_one, phase_zero,
             p6_regime, and p7_discourse_envelope.
    """
    # Check if PO1 output is available
    if not hasattr(ctx, 'phase_minus_one') or ctx.phase_minus_one is None:
        return

    # Check if PO2 output is available
    if not hasattr(ctx, 'phase_zero') or ctx.phase_zero is None:
        return

    # Check if P6 output is available (required for P8)
    if not hasattr(ctx, 'p6_regime') or ctx.p6_regime is None:
        return

    # Check if P7 output is available (required for P8)
    if not hasattr(ctx, 'p7_discourse_envelope') or ctx.p7_discourse_envelope is None:
        return

    grounding_envelope: PhaseMinusOneEnvelope = ctx.phase_minus_one
    intent_envelope: IntentEnvelope = ctx.phase_zero
    regime_envelope: RegimeEnvelope = ctx.p6_regime
    discourse_envelope: DiscourseEnvelope = ctx.p7_discourse_envelope

    # Run P8 resolver
    resolver = get_p8_resolver()
    frame = resolver.resolve(
        grounding_envelope=grounding_envelope,
        intent_envelope=intent_envelope,
        regime_envelope=regime_envelope,
        discourse_envelope=discourse_envelope,
        grammar_evidence=None,  # Grammar evidence optional
    )

    # Attach to context (gating capture, no execution)
    ctx.semantic_frame = frame


def run_p8_directly(
    grounding_envelope: PhaseMinusOneEnvelope,
    intent_envelope: IntentEnvelope,
    regime_envelope: RegimeEnvelope,
    discourse_envelope: DiscourseEnvelope,
    grammar_evidence: Optional[Dict[str, Any]] = None,
) -> SemanticFrame:
    """
    Run P8 directly with explicit inputs.

    Useful for testing or standalone semantic slot resolution.

    CRITICAL: The semantic frame constrains downstream lexical generation
    but does not directly produce any output.

    Args:
        grounding_envelope: PhaseMinusOneEnvelope from PO1.
        intent_envelope: IntentEnvelope from PO2.
        regime_envelope: RegimeEnvelope from P6.
        discourse_envelope: DiscourseEnvelope from P7.
        grammar_evidence: Optional grammar/linguistic evidence.

    Returns:
        SemanticFrame with semantic slot resolution verdict.
    """
    resolver = get_p8_resolver()
    return resolver.resolve(
        grounding_envelope=grounding_envelope,
        intent_envelope=intent_envelope,
        regime_envelope=regime_envelope,
        discourse_envelope=discourse_envelope,
        grammar_evidence=grammar_evidence,
    )


def get_p8_semantic_frame(ctx: Any) -> Optional[SemanticFrame]:
    """
    Get the P8 semantic frame from context.

    Args:
        ctx: Pipeline context.

    Returns:
        SemanticFrame or None if not available.
    """
    if not hasattr(ctx, 'semantic_frame'):
        return None
    return ctx.semantic_frame


def is_semantic_frame_allowed(ctx: Any) -> bool:
    """
    Check if semantic frame is allowed.

    Args:
        ctx: Pipeline context.

    Returns:
        True if semantic frame is allowed, False otherwise.
        Returns False (conservative) if P8 hasn't run.
    """
    frame = get_p8_semantic_frame(ctx)
    if frame is None:
        # Conservative default: if P8 hasn't run, consider not allowed
        return False
    return frame.allowed


def is_deferral_frame(ctx: Any) -> bool:
    """
    Check if semantic frame is a DEFERRAL frame.

    Args:
        ctx: Pipeline context.

    Returns:
        True if frame is DEFERRAL, False otherwise.
        Returns True (conservative) if P8 hasn't run.
    """
    frame = get_p8_semantic_frame(ctx)
    if frame is None:
        # Conservative default: if P8 hasn't run, consider DEFERRAL
        return True
    return frame.is_deferral_frame()


def get_semantic_frame_reason(ctx: Any) -> Optional[str]:
    """
    Get the reason string from the P8 semantic frame verdict.

    Args:
        ctx: Pipeline context.

    Returns:
        Reason string or None if P8 hasn't run.
    """
    frame = get_p8_semantic_frame(ctx)
    if frame is None:
        return None
    return frame.reason


def get_slot_value(ctx: Any, slot: SemanticSlot) -> Optional[str]:
    """
    Get a specific slot value from the semantic frame.

    Args:
        ctx: Pipeline context.
        slot: The SemanticSlot to retrieve.

    Returns:
        Slot value string or None if not present/populated.
    """
    frame = get_p8_semantic_frame(ctx)
    if frame is None:
        return None
    return frame.get_slot_value(slot)


def has_slot(ctx: Any, slot: SemanticSlot) -> bool:
    """
    Check if a slot exists in the semantic frame.

    Args:
        ctx: Pipeline context.
        slot: The SemanticSlot to check.

    Returns:
        True if slot exists (may be None), False otherwise.
    """
    frame = get_p8_semantic_frame(ctx)
    if frame is None:
        return False
    return frame.has_slot(slot)


def get_populated_slots(ctx: Any) -> Dict[SemanticSlot, str]:
    """
    Get all populated (non-None) slots from the semantic frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Dictionary of populated slots or empty dict if P8 hasn't run.
    """
    frame = get_p8_semantic_frame(ctx)
    if frame is None:
        return {}
    return frame.get_populated_slots()


def get_discourse_act_from_frame(ctx: Any) -> Optional[DiscourseAct]:
    """
    Get the discourse act from the semantic frame.

    Args:
        ctx: Pipeline context.

    Returns:
        DiscourseAct or None if P8 hasn't run.
    """
    frame = get_p8_semantic_frame(ctx)
    if frame is None:
        return None
    return frame.discourse_act


__all__ = [
    "get_p8_resolver",
    "maybe_run_p8",
    "run_p8_directly",
    "get_p8_semantic_frame",
    "is_semantic_frame_allowed",
    "is_deferral_frame",
    "get_semantic_frame_reason",
    "get_slot_value",
    "has_slot",
    "get_populated_slots",
    "get_discourse_act_from_frame",
]
