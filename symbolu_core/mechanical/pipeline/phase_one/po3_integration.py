"""
PO3 — Intent → Allowed Action Contract Pipeline Integration Module

Provides a thin shim for integrating PO3 (Intent → Allowed Action Contract)
into the Symbol-U pipeline. Called immediately after PO2, before PO4.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Usage in orchestrator:
    from .phase_one.po3_integration import maybe_run_po3

    # After PO2 stage
    maybe_run_po3(ctx)
    # ctx.allowed_actions is now set

Authority Model:
    - PO3 consumes PO2 IntentEnvelope (read-only)
    - PO3 cannot override PO1–PO2 decisions
    - PO3 produces AllowedActionSet that constrains planner proposals
    - PO3 does NOT enable or trigger any execution
"""

from typing import Any, FrozenSet, Optional

from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import IntentEnvelope
from symbolu_core.mechanical.pipeline.phase_one.phase_one_schema import AllowedActionSet
from symbolu_core.mechanical.pipeline.phase_one.phase_one_resolver import PhaseOneResolver
from symbolu_core.mechanical.pipeline.governance.planner_gate import ActionClass


# Singleton PO3 resolver instance
_po3_resolver: Optional[PhaseOneResolver] = None


def get_po3_resolver() -> PhaseOneResolver:
    """Get or create the singleton PO3 resolver instance."""
    global _po3_resolver
    if _po3_resolver is None:
        _po3_resolver = PhaseOneResolver()
    return _po3_resolver


def maybe_run_po3(ctx: Any) -> None:
    """
    Run PO3 action binding on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    PO3 requires PO2 (phase_zero) to be present.

    IMPORTANT: This function attaches the result to ctx.allowed_actions.
    It does NOT return the action set - use get_po3_action_set(ctx) to retrieve it.

    Rules:
    - Run only if PO2 (phase_zero) completed
    - Attach AllowedActionSet to ctx.allowed_actions
    - Must respect PO2 intent (action set derived from intent)

    Args:
        ctx: Pipeline context with phase_zero.
    """
    # Check if PO2 output is available
    if not hasattr(ctx, 'phase_zero') or ctx.phase_zero is None:
        return

    intent_envelope: IntentEnvelope = ctx.phase_zero

    # Run PO3 resolver
    resolver = get_po3_resolver()
    action_set = resolver.resolve(intent_envelope)

    # Attach to context
    ctx.allowed_actions = action_set


def run_po3_directly(intent_envelope: IntentEnvelope) -> AllowedActionSet:
    """
    Run PO3 directly with explicit inputs.

    Useful for testing or standalone action binding.

    Args:
        intent_envelope: IntentEnvelope from PO2.

    Returns:
        AllowedActionSet with eligible actions.
    """
    resolver = get_po3_resolver()
    return resolver.resolve(intent_envelope)


def get_po3_action_set(ctx: Any) -> Optional[AllowedActionSet]:
    """
    Get the PO3 allowed action set from context.

    Args:
        ctx: Pipeline context.

    Returns:
        AllowedActionSet or None if not available.
    """
    if not hasattr(ctx, 'allowed_actions'):
        return None
    return ctx.allowed_actions


def get_allowed_actions(ctx: Any) -> FrozenSet[ActionClass]:
    """
    Get the set of allowed actions from PO3.

    Args:
        ctx: Pipeline context.

    Returns:
        FrozenSet of allowed ActionClass values, or empty set if PO3 hasn't run.
    """
    action_set = get_po3_action_set(ctx)
    if action_set is None:
        return frozenset()
    return action_set.allowed_actions


def is_action_allowed(ctx: Any, action: ActionClass) -> bool:
    """
    Check if a specific action is allowed by PO3.

    Args:
        ctx: Pipeline context.
        action: ActionClass to check.

    Returns:
        True if action is allowed, False otherwise.
        Returns False (conservative) if PO3 hasn't run.
    """
    action_set = get_po3_action_set(ctx)
    if action_set is None:
        return False
    return action_set.is_action_allowed(action)


def is_action_set_empty(ctx: Any) -> bool:
    """
    Check if the allowed action set is empty (ABSTAIN intent).

    Args:
        ctx: Pipeline context.

    Returns:
        True if action set is empty, False otherwise.
        Returns True (conservative) if PO3 hasn't run.
    """
    action_set = get_po3_action_set(ctx)
    if action_set is None:
        return True
    return action_set.is_empty()


def get_action_count(ctx: Any) -> int:
    """
    Get the count of allowed actions.

    Args:
        ctx: Pipeline context.

    Returns:
        Number of allowed actions, or 0 if PO3 hasn't run.
    """
    action_set = get_po3_action_set(ctx)
    if action_set is None:
        return 0
    return action_set.count()


__all__ = [
    "get_po3_resolver",
    "maybe_run_po3",
    "run_po3_directly",
    "get_po3_action_set",
    "get_allowed_actions",
    "is_action_allowed",
    "is_action_set_empty",
    "get_action_count",
]
