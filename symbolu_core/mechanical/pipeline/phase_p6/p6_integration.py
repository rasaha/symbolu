"""
P6 — Regime Selection & Operational Mode Gate Pipeline Integration Module

Provides a thin shim for integrating P6 (Regime Selection Gate)
into the Symbol-U pipeline. Called immediately after PO5, before any
acoustic/symbolic language processing.

P6 is the first post-governance, pre-language phase.

Usage in orchestrator:
    from .phase_p6.p6_integration import maybe_run_p6

    # After PO5 stage
    maybe_run_p6(ctx)
    # ctx.p6_regime is now set

Authority Model:
    - P6 consumes PO2 IntentEnvelope, PO5 ExecutionEligibilityEnvelope,
      PO1 OverallPolicy, and Phase-41 coherence regime
    - P6 cannot override PO1–PO5 decisions
    - P6 produces RegimeEnvelope (read-only, constrains language generation)
    - P6 does NOT perform semantic processing, lexical selection, or execution

CRITICAL: P6 is gating-only and deterministic. It constrains downstream
language generation but does not directly produce any output.
"""

from typing import Any, Optional

from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import IntentEnvelope
from symbolu_core.mechanical.pipeline.phase_po5.po5_schema import ExecutionEligibilityEnvelope
from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_schema import OverallPolicy
from symbolu_core.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu_core.mechanical.pipeline.phase_p6.p6_regime_gate import P6RegimeGate


# Singleton P6 gate instance
_p6_gate: Optional[P6RegimeGate] = None


def get_p6_gate() -> P6RegimeGate:
    """Get or create the singleton P6 regime gate instance."""
    global _p6_gate
    if _p6_gate is None:
        _p6_gate = P6RegimeGate()
    return _p6_gate


def _get_coherence_regime(ctx: Any) -> str:
    """
    Extract coherence regime from context (Phase-41 output).

    This function reads the already-computed coherence regime from
    the coherence state. It does NOT recompute the regime.

    Args:
        ctx: Pipeline context.

    Returns:
        Coherence regime band string (e.g., "stable", "mixed", "volatile").
        Returns "unknown" if coherence state is not available.
    """
    # Try to get coherence regime from coherence_state
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        # Phase-41 stores the regime band in current_regime_band
        regime_band = getattr(ctx.coherence_state, 'current_regime_band', None)
        if regime_band:
            return regime_band

    # Fallback to "unknown" if no coherence data available
    return "unknown"


def maybe_run_p6(ctx: Any) -> None:
    """
    Run P6 regime selection on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    P6 requires PO5 (po5_execution_eligibility) to be present.

    IMPORTANT: This function attaches the result to ctx.p6_regime.
    It does NOT return the envelope - use get_p6_regime(ctx) to retrieve it.

    CRITICAL: P6 is gating-only and deterministic. It constrains downstream
    language generation but does not directly produce any output.

    Rules:
    - Run only if PO5 execution eligibility exists
    - Pull coherence regime from existing Phase-41 output (do not recompute)
    - Attach RegimeEnvelope to ctx.p6_regime
    - Must not alter downstream behavior yet

    Args:
        ctx: Pipeline context with phase_zero, po5_execution_eligibility,
             phase_minus_one, and optionally coherence_state.
    """
    # Check if PO2 output is available
    if not hasattr(ctx, 'phase_zero') or ctx.phase_zero is None:
        return

    # Check if PO5 output is available (required for P6)
    if not hasattr(ctx, 'po5_execution_eligibility') or ctx.po5_execution_eligibility is None:
        return

    # Check if PO1 output is available
    if not hasattr(ctx, 'phase_minus_one') or ctx.phase_minus_one is None:
        return

    intent_envelope: IntentEnvelope = ctx.phase_zero
    execution: ExecutionEligibilityEnvelope = ctx.po5_execution_eligibility
    overall_policy: OverallPolicy = ctx.phase_minus_one.overall_policy

    # Get coherence regime from Phase-41 (do not recompute)
    coherence_regime = _get_coherence_regime(ctx)

    # Run P6 gate
    gate = get_p6_gate()
    envelope = gate.select(intent_envelope, execution, coherence_regime, overall_policy)

    # Attach to context (gating capture, no execution)
    ctx.p6_regime = envelope


def run_p6_directly(
    intent_envelope: IntentEnvelope,
    execution: ExecutionEligibilityEnvelope,
    coherence_regime: str,
    overall_policy: OverallPolicy,
) -> RegimeEnvelope:
    """
    Run P6 directly with explicit inputs.

    Useful for testing or standalone regime selection.

    CRITICAL: The regime selection constrains downstream language generation
    but does not directly produce any output.

    Args:
        intent_envelope: IntentEnvelope from PO2.
        execution: ExecutionEligibilityEnvelope from PO5.
        coherence_regime: Coherence regime band from Phase-41.
        overall_policy: OverallPolicy from PO1.

    Returns:
        RegimeEnvelope with regime selection verdict.
    """
    gate = get_p6_gate()
    return gate.select(intent_envelope, execution, coherence_regime, overall_policy)


def get_p6_regime(ctx: Any) -> Optional[RegimeEnvelope]:
    """
    Get the P6 regime envelope from context.

    Args:
        ctx: Pipeline context.

    Returns:
        RegimeEnvelope or None if not available.
    """
    if not hasattr(ctx, 'p6_regime'):
        return None
    return ctx.p6_regime


def is_regime_hold(ctx: Any) -> bool:
    """
    Check if regime is HOLD (most conservative).

    Args:
        ctx: Pipeline context.

    Returns:
        True if regime is HOLD, False otherwise.
        Returns True (conservative) if P6 hasn't run.
    """
    regime = get_p6_regime(ctx)
    if regime is None:
        # Conservative default: if P6 hasn't run, consider HOLD
        return True
    return regime.is_hold()


def is_regime_stabilize(ctx: Any) -> bool:
    """
    Check if regime is STABILIZE.

    Args:
        ctx: Pipeline context.

    Returns:
        True if regime is STABILIZE, False otherwise.
    """
    regime = get_p6_regime(ctx)
    if regime is None:
        return False
    return regime.is_stabilize()


def is_regime_reflect(ctx: Any) -> bool:
    """
    Check if regime is REFLECT.

    Args:
        ctx: Pipeline context.

    Returns:
        True if regime is REFLECT, False otherwise.
    """
    regime = get_p6_regime(ctx)
    if regime is None:
        return False
    return regime.is_reflect()


def is_regime_inform(ctx: Any) -> bool:
    """
    Check if regime is INFORM.

    Args:
        ctx: Pipeline context.

    Returns:
        True if regime is INFORM, False otherwise.
    """
    regime = get_p6_regime(ctx)
    if regime is None:
        return False
    return regime.is_inform()


def is_regime_clarify(ctx: Any) -> bool:
    """
    Check if regime is CLARIFY.

    Args:
        ctx: Pipeline context.

    Returns:
        True if regime is CLARIFY, False otherwise.
    """
    regime = get_p6_regime(ctx)
    if regime is None:
        return False
    return regime.is_clarify()


def is_regime_de_escalate(ctx: Any) -> bool:
    """
    Check if regime is DE_ESCALATE.

    Args:
        ctx: Pipeline context.

    Returns:
        True if regime is DE_ESCALATE, False otherwise.
    """
    regime = get_p6_regime(ctx)
    if regime is None:
        return False
    return regime.is_de_escalate()


def get_regime_reason(ctx: Any) -> Optional[str]:
    """
    Get the reason string from the P6 regime verdict.

    Args:
        ctx: Pipeline context.

    Returns:
        Reason string or None if P6 hasn't run.
    """
    regime = get_p6_regime(ctx)
    if regime is None:
        return None
    return regime.reason


def get_selected_regime(ctx: Any) -> Optional[OperationalRegime]:
    """
    Get the selected operational regime from context.

    Args:
        ctx: Pipeline context.

    Returns:
        OperationalRegime or None if P6 hasn't run.
    """
    regime = get_p6_regime(ctx)
    if regime is None:
        return None
    return regime.regime


__all__ = [
    "get_p6_gate",
    "maybe_run_p6",
    "run_p6_directly",
    "get_p6_regime",
    "is_regime_hold",
    "is_regime_stabilize",
    "is_regime_reflect",
    "is_regime_inform",
    "is_regime_clarify",
    "is_regime_de_escalate",
    "get_regime_reason",
    "get_selected_regime",
]
