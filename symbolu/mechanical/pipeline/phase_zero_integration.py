"""
Phase 0 Pipeline Integration Module

Provides a thin shim for integrating Phase 0 (Intent Envelope & Act-Type Selection)
into the Symbol-U pipeline. Called immediately after Phase −1, before the Planner.

Usage in orchestrator:
    from .phase_zero_integration import maybe_run_phase_zero

    # After Phase −1 stage
    ctx.phase_zero = maybe_run_phase_zero(ctx)

Authority Model:
    - Phase 0 consumes Phase −1 constraints (read-only)
    - Phase 0 cannot override Phase −1 BLOCKED status
    - Phase 0 produces IntentEnvelope for Planner consumption
    - Authority flows downward (constraints binding on downstream stages)
"""

from typing import Any, Optional

from symbolu.mechanical.pipeline.phase_zero import (
    PhaseZeroResolver,
    IntentEnvelope,
)
from symbolu.mechanical.pipeline.grounding.phase_minus_one_schema import (
    PhaseMinusOneEnvelope,
)


# Singleton Phase 0 resolver instance
_phase_zero_resolver: Optional[PhaseZeroResolver] = None


def get_phase_zero_resolver() -> PhaseZeroResolver:
    """Get or create the singleton Phase 0 resolver instance."""
    global _phase_zero_resolver
    if _phase_zero_resolver is None:
        _phase_zero_resolver = PhaseZeroResolver()
    return _phase_zero_resolver


def maybe_run_phase_zero(ctx: Any) -> Optional[IntentEnvelope]:
    """
    Run Phase 0 intent resolution on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    Phase 0 requires Phase −1 output to be present in context.

    Args:
        ctx: Pipeline context with phase_minus_one envelope.

    Returns:
        IntentEnvelope with determined intent type and response posture,
        or None if Phase −1 output is not available.
    """
    # Check if Phase −1 output is available
    if not hasattr(ctx, 'phase_minus_one') or ctx.phase_minus_one is None:
        return None

    phase_minus_one: PhaseMinusOneEnvelope = ctx.phase_minus_one

    # Run Phase 0 resolver
    resolver = get_phase_zero_resolver()
    return resolver.resolve(phase_minus_one)


def run_phase_zero_directly(
    phase_minus_one: PhaseMinusOneEnvelope,
) -> IntentEnvelope:
    """
    Run Phase 0 directly with explicit Phase −1 envelope input.

    Useful for testing or standalone intent resolution.

    Args:
        phase_minus_one: PhaseMinusOneEnvelope from Phase −1.

    Returns:
        IntentEnvelope with intent type and response posture.
    """
    resolver = get_phase_zero_resolver()
    return resolver.resolve(phase_minus_one)


def is_planning_allowed(ctx: Any) -> bool:
    """
    Check if planning is allowed based on Phase 0 resolution.

    Args:
        ctx: Pipeline context.

    Returns:
        True if planning may proceed, False if blocked.
    """
    if not hasattr(ctx, 'phase_zero') or ctx.phase_zero is None:
        # Conservative default: if Phase 0 hasn't run, block planning
        return False
    return ctx.phase_zero.planning_allowed


def get_intent_envelope(ctx: Any) -> Optional[IntentEnvelope]:
    """
    Get the Phase 0 intent envelope from context.

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
