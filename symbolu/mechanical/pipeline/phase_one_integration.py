"""
PO3 — Intent → Allowed Action Contract Pipeline Integration Module
(Implemented as phase_one for backward compatibility)

Provides a thin shim for integrating PO3 (Intent → Allowed Action Contract)
into the Symbol-U pipeline. Called immediately after PO2, before the Planner.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Usage in orchestrator:
    from .phase_one_integration import maybe_run_phase_one

    # After PO2 stage
    ctx.allowed_actions = maybe_run_phase_one(ctx)

Authority Model:
    - PO3 consumes PO2 IntentEnvelope (read-only)
    - PO3 cannot override PO2 decisions
    - PO3 produces AllowedActionSet for Planner consumption
    - Planner may ONLY propose actions from AllowedActionSet
    - PlannerGate remains final authority on action execution
"""

from typing import Any, Optional

from symbolu.mechanical.pipeline.phase_one import (
    PhaseOneResolver,
    AllowedActionSet,
)
from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import IntentEnvelope


# Singleton PO3 resolver instance
_phase_one_resolver: Optional[PhaseOneResolver] = None


def get_phase_one_resolver() -> PhaseOneResolver:
    """Get or create the singleton PO3 resolver instance."""
    global _phase_one_resolver
    if _phase_one_resolver is None:
        _phase_one_resolver = PhaseOneResolver()
    return _phase_one_resolver


def maybe_run_phase_one(ctx: Any) -> Optional[AllowedActionSet]:
    """
    Run PO3 action binding on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    PO3 requires PO2 output to be present in context.

    Args:
        ctx: Pipeline context with phase_zero envelope.

    Returns:
        AllowedActionSet with the eligible actions for the Planner,
        or None if PO2 output is not available.
    """
    # Check if PO2 output is available
    if not hasattr(ctx, 'phase_zero') or ctx.phase_zero is None:
        return None

    intent_envelope: IntentEnvelope = ctx.phase_zero

    # Run PO3 resolver
    resolver = get_phase_one_resolver()
    return resolver.resolve(intent_envelope)


def run_phase_one_directly(
    intent_envelope: IntentEnvelope,
) -> AllowedActionSet:
    """
    Run PO3 directly with explicit IntentEnvelope input.

    Useful for testing or standalone action binding.

    Args:
        intent_envelope: IntentEnvelope from PO2.

    Returns:
        AllowedActionSet with eligible actions.
    """
    resolver = get_phase_one_resolver()
    return resolver.resolve(intent_envelope)


def get_allowed_actions(ctx: Any) -> Optional[AllowedActionSet]:
    """
    Get the PO3 allowed actions from context.

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
    Check if a specific action is allowed based on PO3 resolution.

    Args:
        ctx: Pipeline context.
        action: ActionClass to check.

    Returns:
        True if action is in the allowed set, False otherwise.
    """
    allowed = get_allowed_actions(ctx)
    if allowed is None:
        # Conservative default: if PO3 hasn't run, no actions allowed
        return False
    return allowed.is_action_allowed(action)


def get_allowed_action_count(ctx: Any) -> int:
    """
    Get the count of allowed actions from PO3.

    Args:
        ctx: Pipeline context.

    Returns:
        Number of allowed actions, or 0 if PO3 hasn't run.
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
