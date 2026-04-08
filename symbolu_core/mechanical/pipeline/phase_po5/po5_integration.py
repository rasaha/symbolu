"""
PO5 — Planner Execution Gate Pipeline Integration Module

Provides a thin shim for integrating PO5 (Planner Execution Gate)
into the Symbol-U pipeline. Called immediately after PO4, before any
acoustic/symbolic processing or agent systems.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Usage in orchestrator:
    from .phase_po5.po5_integration import maybe_run_po5

    # After PO4 stage
    maybe_run_po5(ctx)
    # ctx.po5_execution_eligibility is now set

Authority Model:
    - PO5 consumes PO2 IntentEnvelope, PO4 PlannerProposalEnvelope, PO1 OverallPolicy
    - PO5 cannot override PO1–PO4 decisions
    - PO5 produces ExecutionEligibilityEnvelope (read-only, non-actuating)
    - PO5 does NOT enable, trigger, or schedule any execution

CRITICAL: PO5 is non-actuating. The ELIGIBLE status is informational only.
No execution system exists in the Symbol-U architecture at this phase.
"""

from typing import Any, Optional

from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import IntentEnvelope
from symbolu_core.mechanical.pipeline.phase_po4.po4_schema import PlannerProposalEnvelope
from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_schema import OverallPolicy
from symbolu_core.mechanical.pipeline.phase_po5.po5_schema import ExecutionEligibilityEnvelope
from symbolu_core.mechanical.pipeline.phase_po5.po5_gate import PO5ExecutionGate


# Singleton PO5 gate instance
_po5_gate: Optional[PO5ExecutionGate] = None


def get_po5_gate() -> PO5ExecutionGate:
    """Get or create the singleton PO5 execution gate instance."""
    global _po5_gate
    if _po5_gate is None:
        _po5_gate = PO5ExecutionGate()
    return _po5_gate


def maybe_run_po5(ctx: Any) -> None:
    """
    Run PO5 execution eligibility evaluation on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    PO5 requires PO2 (phase_zero), PO4 (po4_proposal), and PO1 (phase_minus_one)
    to be present.

    IMPORTANT: This function attaches the result to ctx.po5_execution_eligibility.
    It does NOT return the envelope - use get_po5_eligibility(ctx) to retrieve it.

    CRITICAL: PO5 is non-actuating. It produces a read-only eligibility verdict
    and does NOT trigger any execution.

    Rules:
    - Run only if PO4 (po4_proposal) completed
    - Attach ExecutionEligibilityEnvelope to ctx.po5_execution_eligibility
    - Must not affect downstream behavior (governance only)
    - Must not trigger any execution

    Args:
        ctx: Pipeline context with phase_zero, po4_proposal, and phase_minus_one.
    """
    # Check if PO2 output is available
    if not hasattr(ctx, 'phase_zero') or ctx.phase_zero is None:
        return

    # Check if PO4 output is available (required for PO5)
    if not hasattr(ctx, 'po4_proposal') or ctx.po4_proposal is None:
        return

    # Check if PO1 output is available
    if not hasattr(ctx, 'phase_minus_one') or ctx.phase_minus_one is None:
        return

    intent_envelope: IntentEnvelope = ctx.phase_zero
    proposal: PlannerProposalEnvelope = ctx.po4_proposal
    overall_policy: OverallPolicy = ctx.phase_minus_one.overall_policy

    # Run PO5 gate
    gate = get_po5_gate()
    envelope = gate.evaluate(intent_envelope, proposal, overall_policy)

    # Attach to context (governance capture, no execution)
    ctx.po5_execution_eligibility = envelope


def run_po5_directly(
    intent_envelope: IntentEnvelope,
    proposal: PlannerProposalEnvelope,
    overall_policy: OverallPolicy,
) -> ExecutionEligibilityEnvelope:
    """
    Run PO5 directly with explicit inputs.

    Useful for testing or standalone eligibility evaluation.

    CRITICAL: The ELIGIBLE status is informational only.
    No executor exists in the architecture.

    Args:
        intent_envelope: IntentEnvelope from PO2.
        proposal: PlannerProposalEnvelope from PO4.
        overall_policy: OverallPolicy from PO1.

    Returns:
        ExecutionEligibilityEnvelope with eligibility verdict.
    """
    gate = get_po5_gate()
    return gate.evaluate(intent_envelope, proposal, overall_policy)


def get_po5_eligibility(ctx: Any) -> Optional[ExecutionEligibilityEnvelope]:
    """
    Get the PO5 execution eligibility envelope from context.

    Args:
        ctx: Pipeline context.

    Returns:
        ExecutionEligibilityEnvelope or None if not available.
    """
    if not hasattr(ctx, 'po5_execution_eligibility'):
        return None
    return ctx.po5_execution_eligibility


def is_execution_prohibited(ctx: Any) -> bool:
    """
    Check if execution is prohibited by PO5.

    Args:
        ctx: Pipeline context.

    Returns:
        True if execution is prohibited, False otherwise.
        Returns True (conservative) if PO5 hasn't run.
    """
    eligibility = get_po5_eligibility(ctx)
    if eligibility is None:
        # Conservative default: if PO5 hasn't run, consider prohibited
        return True
    return eligibility.is_prohibited()


def is_execution_deferred(ctx: Any) -> bool:
    """
    Check if execution eligibility is deferred by PO5.

    Args:
        ctx: Pipeline context.

    Returns:
        True if execution is deferred, False otherwise.
    """
    eligibility = get_po5_eligibility(ctx)
    if eligibility is None:
        return False
    return eligibility.is_deferred()


def is_execution_eligible(ctx: Any) -> bool:
    """
    Check if execution would be conceptually eligible.

    CRITICAL: ELIGIBLE is informational only. No executor exists.
    This function does NOT enable or trigger any execution.

    Args:
        ctx: Pipeline context.

    Returns:
        True if conceptually eligible, False otherwise.
    """
    eligibility = get_po5_eligibility(ctx)
    if eligibility is None:
        return False
    return eligibility.is_eligible()


def get_eligibility_reason(ctx: Any) -> Optional[str]:
    """
    Get the reason string from the PO5 eligibility verdict.

    Args:
        ctx: Pipeline context.

    Returns:
        Reason string or None if PO5 hasn't run.
    """
    eligibility = get_po5_eligibility(ctx)
    if eligibility is None:
        return None
    return eligibility.reason


__all__ = [
    "get_po5_gate",
    "maybe_run_po5",
    "run_po5_directly",
    "get_po5_eligibility",
    "is_execution_prohibited",
    "is_execution_deferred",
    "is_execution_eligible",
    "get_eligibility_reason",
]
