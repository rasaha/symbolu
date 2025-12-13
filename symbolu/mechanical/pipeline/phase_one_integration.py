"""
Phase 1 Pipeline Integration Module

Provides a thin shim for integrating Phase 1 (Intent → Allowed Action Binding)
into the Symbol-U pipeline. Called immediately after Phase 0, before the Planner.

Usage in orchestrator:
    from .phase_one_integration import maybe_run_phase_one

    # After Phase 0 stage
    ctx.allowed_actions = maybe_run_phase_one(ctx)

Authority Model:
    - Phase 1 consumes Phase 0 IntentEnvelope (read-only)
    - Phase 1 cannot override Phase 0 decisions
    - Phase 1 produces AllowedActionSet for Planner consumption
    - Planner may ONLY propose actions from AllowedActionSet
    - PlannerGate remains final authority on action execution
"""

from typing import Any, Optional

from symbolu.mechanical.pipeline.phase_one import (
    PhaseOneResolver,
    AllowedActionSet,
)
from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import IntentEnvelope


# Singleton Phase 1 resolver instance
_phase_one_resolver: Optional[PhaseOneResolver] = None


def get_phase_one_resolver() -> PhaseOneResolver:
    """Get or create the singleton Phase 1 resolver instance."""
    global _phase_one_resolver
    if _phase_one_resolver is None:
        _phase_one_resolver = PhaseOneResolver()
    return _phase_one_resolver


def maybe_run_phase_one(ctx: Any) -> Optional[AllowedActionSet]:
    """
    Run Phase 1 action binding on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    Phase 1 requires Phase 0 output to be present in context.

    Args:
        ctx: Pipeline context with phase_zero envelope.

    Returns:
        AllowedActionSet with the eligible actions for the Planner,
        or None if Phase 0 output is not available.
    """
    # Check if Phase 0 output is available
    if not hasattr(ctx, 'phase_zero') or ctx.phase_zero is None:
        return None

    intent_envelope: IntentEnvelope = ctx.phase_zero

    # Run Phase 1 resolver
    resolver = get_phase_one_resolver()
    return resolver.resolve(intent_envelope)


def run_phase_one_directly(
    intent_envelope: IntentEnvelope,
) -> AllowedActionSet:
    """
    Run Phase 1 directly with explicit IntentEnvelope input.

    Useful for testing or standalone action binding.

    Args:
        intent_envelope: IntentEnvelope from Phase 0.

    Returns:
        AllowedActionSet with eligible actions.
    """
    resolver = get_phase_one_resolver()
    return resolver.resolve(intent_envelope)


def get_allowed_actions(ctx: Any) -> Optional[AllowedActionSet]:
    """
    Get the Phase 1 allowed actions from context.

    Args:
        ctx: Pipeline context.

    Returns:
        AllowedActionSet or None if not available.
    """
    if not hasattr(ctx, 'allowed_actions'):
        return None
    return ctx.allowed_actions


def is_action_allowed(ctx: Any, action: Any) -> bool:
    """
    Check if a specific action is allowed based on Phase 1 resolution.

    Args:
        ctx: Pipeline context.
        action: ActionClass to check.

    Returns:
        True if action is in the allowed set, False otherwise.
    """
    allowed = get_allowed_actions(ctx)
    if allowed is None:
        # Conservative default: if Phase 1 hasn't run, no actions allowed
        return False
    return allowed.is_action_allowed(action)


def get_allowed_action_count(ctx: Any) -> int:
    """
    Get the count of allowed actions from Phase 1.

    Args:
        ctx: Pipeline context.

    Returns:
        Number of allowed actions, or 0 if Phase 1 hasn't run.
    """
    allowed = get_allowed_actions(ctx)
    if allowed is None:
        return 0
    return allowed.count()


__all__ = [
    "get_phase_one_resolver",
    "maybe_run_phase_one",
    "run_phase_one_directly",
    "get_allowed_actions",
    "is_action_allowed",
    "get_allowed_action_count",
]
