"""
PO4 — Planner Proposal Envelope Pipeline Integration Module

Provides a thin shim for integrating PO4 (Planner Proposal Envelope)
into the Symbol-U pipeline. Called immediately after PO3, before any
planner execution.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Usage in orchestrator:
    from .phase_po4.po4_integration import maybe_run_po4

    # After PO3 stage (with proposed actions available)
    maybe_run_po4(ctx, proposed_actions)
    # ctx.po4_proposal is now set

Authority Model:
    - PO4 consumes PO2 IntentEnvelope and PO3 AllowedActionSet (read-only)
    - PO4 cannot override PO1–PO3 decisions
    - PO4 produces PlannerProposalEnvelope for governance review
    - PO4 does NOT enable or trigger any execution
"""

from typing import Any, List, Optional

from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import IntentEnvelope
from symbolu_core.mechanical.pipeline.phase_one.phase_one_schema import AllowedActionSet
from symbolu_core.mechanical.pipeline.governance.planner_gate import ActionClass
from symbolu_core.mechanical.pipeline.phase_po4.po4_schema import PlannerProposalEnvelope
from symbolu_core.mechanical.pipeline.phase_po4.po4_resolver import PO4Resolver


# Singleton PO4 resolver instance
_po4_resolver: Optional[PO4Resolver] = None


def get_po4_resolver() -> PO4Resolver:
    """Get or create the singleton PO4 resolver instance."""
    global _po4_resolver
    if _po4_resolver is None:
        _po4_resolver = PO4Resolver()
    return _po4_resolver


def maybe_run_po4(
    ctx: Any,
    proposed_actions: Optional[List[ActionClass]] = None,
) -> None:
    """
    Run PO4 proposal envelope generation on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    PO4 requires both PO2 (phase_zero) and PO3 (allowed_actions) to be present.

    IMPORTANT: This function attaches the result to ctx.po4_proposal.
    It does NOT return the envelope - use get_po4_proposal(ctx) to retrieve it.

    Rules:
    - Run only if PO3 (allowed_actions) completed
    - Attach PlannerProposalEnvelope to ctx.po4_proposal
    - Must not affect downstream behavior (governance only)

    Args:
        ctx: Pipeline context with phase_zero and allowed_actions.
        proposed_actions: Optional list of actions the planner proposes.
            If None, an empty proposal is validated.
    """
    # Check if PO2 output is available
    if not hasattr(ctx, 'phase_zero') or ctx.phase_zero is None:
        return

    # Check if PO3 output is available
    if not hasattr(ctx, 'allowed_actions') or ctx.allowed_actions is None:
        return

    intent_envelope: IntentEnvelope = ctx.phase_zero
    allowed_action_set: AllowedActionSet = ctx.allowed_actions

    # Default to empty proposal if none provided
    if proposed_actions is None:
        proposed_actions = []

    # Run PO4 resolver
    resolver = get_po4_resolver()
    envelope = resolver.resolve(intent_envelope, allowed_action_set, proposed_actions)

    # Attach to context (governance capture, no execution)
    ctx.po4_proposal = envelope


def run_po4_directly(
    intent_envelope: IntentEnvelope,
    allowed_action_set: AllowedActionSet,
    proposed_actions: List[ActionClass],
) -> PlannerProposalEnvelope:
    """
    Run PO4 directly with explicit inputs.

    Useful for testing or standalone proposal validation.

    Args:
        intent_envelope: IntentEnvelope from PO2.
        allowed_action_set: AllowedActionSet from PO3.
        proposed_actions: Actions the planner proposes.

    Returns:
        PlannerProposalEnvelope with validation result.
    """
    resolver = get_po4_resolver()
    return resolver.resolve(intent_envelope, allowed_action_set, proposed_actions)


def get_po4_proposal(ctx: Any) -> Optional[PlannerProposalEnvelope]:
    """
    Get the PO4 proposal envelope from context.

    Args:
        ctx: Pipeline context.

    Returns:
        PlannerProposalEnvelope or None if not available.
    """
    if not hasattr(ctx, 'po4_proposal'):
        return None
    return ctx.po4_proposal


def is_proposal_valid(ctx: Any) -> bool:
    """
    Check if the PO4 proposal is fully valid.

    Args:
        ctx: Pipeline context.

    Returns:
        True if proposal status is VALID, False otherwise.
    """
    proposal = get_po4_proposal(ctx)
    if proposal is None:
        return False
    return proposal.is_valid()


def is_proposal_blocked(ctx: Any) -> bool:
    """
    Check if the PO4 proposal is blocked.

    Args:
        ctx: Pipeline context.

    Returns:
        True if proposal status is BLOCKED, False otherwise.
    """
    proposal = get_po4_proposal(ctx)
    if proposal is None:
        # Conservative default: if PO4 hasn't run, consider blocked
        return True
    return proposal.is_blocked()


def get_allowed_proposed_actions(ctx: Any) -> List[ActionClass]:
    """
    Get the list of allowed proposed actions from PO4.

    Args:
        ctx: Pipeline context.

    Returns:
        List of allowed actions, or empty list if PO4 hasn't run.
    """
    proposal = get_po4_proposal(ctx)
    if proposal is None:
        return []
    return list(proposal.allowed_actions)


def get_rejected_proposed_actions(ctx: Any) -> List[ActionClass]:
    """
    Get the list of rejected proposed actions from PO4.

    Args:
        ctx: Pipeline context.

    Returns:
        List of rejected actions, or empty list if PO4 hasn't run.
    """
    proposal = get_po4_proposal(ctx)
    if proposal is None:
        return []
    return list(proposal.rejected_actions.keys())


__all__ = [
    "get_po4_resolver",
    "maybe_run_po4",
    "run_po4_directly",
    "get_po4_proposal",
    "is_proposal_valid",
    "is_proposal_blocked",
    "get_allowed_proposed_actions",
    "get_rejected_proposed_actions",
]
