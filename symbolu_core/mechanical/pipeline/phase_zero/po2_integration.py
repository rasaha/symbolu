"""
PO2 — Intent Envelope & Response Posture Pipeline Integration Module

Provides a thin shim for integrating PO2 (Intent Envelope & Response Posture)
into the Symbol-U pipeline. Called immediately after PO1, before PO3.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Usage in orchestrator:
    from .phase_zero.po2_integration import maybe_run_po2

    # After PO1 stage
    maybe_run_po2(ctx)
    # ctx.phase_zero is now set

Authority Model:
    - PO2 consumes PO1 PhaseMinusOneEnvelope (read-only)
    - PO2 cannot override PO1 decisions (BLOCKED stays BLOCKED)
    - PO2 produces IntentEnvelope for PO3 action binding
"""

from typing import Any, Optional

from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_schema import PhaseMinusOneEnvelope
from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import IntentEnvelope, IntentType, ResponsePosture
from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_resolver import PhaseZeroResolver


# Singleton PO2 resolver instance
_po2_resolver: Optional[PhaseZeroResolver] = None


def get_po2_resolver() -> PhaseZeroResolver:
    """Get or create the singleton PO2 resolver instance."""
    global _po2_resolver
    if _po2_resolver is None:
        _po2_resolver = PhaseZeroResolver()
    return _po2_resolver


def maybe_run_po2(ctx: Any) -> None:
    """
    Run PO2 intent envelope resolution on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    PO2 requires PO1 (phase_minus_one) to be present.

    IMPORTANT: This function attaches the result to ctx.phase_zero.
    It does NOT return the envelope - use get_po2_envelope(ctx) to retrieve it.

    Rules:
    - Run only if PO1 (phase_minus_one) completed
    - Attach IntentEnvelope to ctx.phase_zero
    - Must respect PO1 constraints (BLOCKED → CLARIFY intent)

    Args:
        ctx: Pipeline context with phase_minus_one.
    """
    # Check if PO1 output is available
    if not hasattr(ctx, 'phase_minus_one') or ctx.phase_minus_one is None:
        return

    po1_envelope: PhaseMinusOneEnvelope = ctx.phase_minus_one

    # Run PO2 resolver
    resolver = get_po2_resolver()
    envelope = resolver.resolve(po1_envelope)

    # Attach to context
    ctx.phase_zero = envelope


def run_po2_directly(po1_envelope: PhaseMinusOneEnvelope) -> IntentEnvelope:
    """
    Run PO2 directly with explicit inputs.

    Useful for testing or standalone intent resolution.

    Args:
        po1_envelope: PhaseMinusOneEnvelope from PO1.

    Returns:
        IntentEnvelope with intent and response posture.
    """
    resolver = get_po2_resolver()
    return resolver.resolve(po1_envelope)


def get_po2_envelope(ctx: Any) -> Optional[IntentEnvelope]:
    """
    Get the PO2 intent envelope from context.

    Args:
        ctx: Pipeline context.

    Returns:
        IntentEnvelope or None if not available.
    """
    if not hasattr(ctx, 'phase_zero'):
        return None
    return ctx.phase_zero


def get_intent_type(ctx: Any) -> Optional[IntentType]:
    """
    Get the intent type from PO2.

    Args:
        ctx: Pipeline context.

    Returns:
        IntentType or None if PO2 hasn't run.
    """
    envelope = get_po2_envelope(ctx)
    if envelope is None:
        return None
    return envelope.intent_type


def get_response_posture(ctx: Any) -> Optional[ResponsePosture]:
    """
    Get the response posture from PO2.

    Args:
        ctx: Pipeline context.

    Returns:
        ResponsePosture or None if PO2 hasn't run.
    """
    envelope = get_po2_envelope(ctx)
    if envelope is None:
        return None
    return envelope.response_posture


def is_planning_blocked(ctx: Any) -> bool:
    """
    Check if planning is blocked by PO2.

    Args:
        ctx: Pipeline context.

    Returns:
        True if planning is blocked, False otherwise.
        Returns True (conservative) if PO2 hasn't run.
    """
    envelope = get_po2_envelope(ctx)
    if envelope is None:
        return True
    return envelope.is_planning_blocked()


def requires_clarification(ctx: Any) -> bool:
    """
    Check if PO2 requires clarification before proceeding.

    Args:
        ctx: Pipeline context.

    Returns:
        True if clarification required, False otherwise.
    """
    envelope = get_po2_envelope(ctx)
    if envelope is None:
        return True
    return envelope.requires_clarification()


__all__ = [
    "get_po2_resolver",
    "maybe_run_po2",
    "run_po2_directly",
    "get_po2_envelope",
    "get_intent_type",
    "get_response_posture",
    "is_planning_blocked",
    "requires_clarification",
]
