"""
PO2 — Intent Envelope & Response Posture Pipeline Integration Module
(Implemented as phase_zero for backward compatibility)

Provides a thin shim for integrating PO2 (Intent Envelope & Response Posture)
into the Symbol-U pipeline. Called immediately after PO1, before the Planner.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Usage in orchestrator:
    from .phase_zero_integration import maybe_run_phase_zero

    # After PO1 stage
    ctx.phase_zero = maybe_run_phase_zero(ctx)

Authority Model:
    - PO2 consumes PO1 constraints (read-only)
    - PO2 cannot override PO1 BLOCKED status
    - PO2 produces IntentEnvelope for Planner consumption
    - Authority flows downward (constraints binding on downstream stages)
"""

from typing import Any, Optional

from symbolu_core.mechanical.pipeline.phase_zero import (
    PhaseZeroResolver,
    IntentEnvelope,
)
from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_schema import (
    PhaseMinusOneEnvelope,
)


# Singleton PO2 resolver instance
_phase_zero_resolver: Optional[PhaseZeroResolver] = None


def get_phase_zero_resolver() -> PhaseZeroResolver:
    """Get or create the singleton PO2 resolver instance."""
    global _phase_zero_resolver
    if _phase_zero_resolver is None:
        _phase_zero_resolver = PhaseZeroResolver()
    return _phase_zero_resolver


def maybe_run_phase_zero(ctx: Any) -> Optional[IntentEnvelope]:
    """
    Run PO2 intent resolution on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    PO2 requires PO1 output to be present in context.

    Args:
        ctx: Pipeline context with phase_minus_one envelope.

    Returns:
        IntentEnvelope with determined intent type and response posture,
        or None if PO1 output is not available.
    """
    # Check if PO1 output is available
    if not hasattr(ctx, 'phase_minus_one') or ctx.phase_minus_one is None:
        return None

    phase_minus_one: PhaseMinusOneEnvelope = ctx.phase_minus_one

    # Run PO2 resolver
    resolver = get_phase_zero_resolver()
    return resolver.resolve(phase_minus_one)


def run_phase_zero_directly(
    phase_minus_one: PhaseMinusOneEnvelope,
) -> IntentEnvelope:
    """
    Run PO2 directly with explicit PO1 envelope input.

    Useful for testing or standalone intent resolution.

    Args:
        phase_minus_one: PhaseMinusOneEnvelope from PO1.

    Returns:
        IntentEnvelope with intent type and response posture.
    """
    resolver = get_phase_zero_resolver()
    return resolver.resolve(phase_minus_one)


def is_planning_allowed(ctx: Any) -> bool:
    """
    Check if planning is allowed based on PO2 resolution.

    Args:
        ctx: Pipeline context.

    Returns:
        True if planning may proceed, False if blocked.
    """
    if not hasattr(ctx, 'phase_zero') or ctx.phase_zero is None:
        # Conservative default: if PO2 hasn't run, block planning
        return False
    return ctx.phase_zero.planning_allowed


def get_intent_envelope(ctx: Any) -> Optional[IntentEnvelope]:
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


__all__ = [
    "get_phase_zero_resolver",
    "maybe_run_phase_zero",
    "run_phase_zero_directly",
    "is_planning_allowed",
    "get_intent_envelope",
]
