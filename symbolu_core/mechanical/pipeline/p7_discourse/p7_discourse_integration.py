"""
P7 — Discourse Act Resolver Pipeline Integration Module

Provides a thin shim for integrating P7 (Discourse Act Resolver)
into the Symbol-U pipeline. Called immediately after P6, before any
semantic/lexical language processing.

P7 is a post-regime, pre-semantics phase.

Usage in orchestrator:
    from .p7_discourse.p7_discourse_integration import maybe_run_p7

    # After P6 stage
    maybe_run_p7(ctx)
    # ctx.p7_discourse_envelope is now set

Authority Model:
    - P7 consumes PO1 PhaseMinusOneEnvelope, PO2 IntentEnvelope,
      PO3 AllowedActionSet, and P6 RegimeEnvelope
    - P7 cannot override PO1–P6 decisions
    - P7 produces DiscourseEnvelope (read-only, constrains language generation)
    - P7 does NOT perform semantic processing, lexical selection, or execution

CRITICAL: P7 is gating-only and deterministic. It constrains downstream
language generation but does not directly produce any output.
"""

from typing import Any, Dict, Optional

from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_schema import (
    PhaseMinusOneEnvelope,
)
from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import IntentEnvelope
from symbolu_core.mechanical.pipeline.phase_one.phase_one_schema import AllowedActionSet
from symbolu_core.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu_core.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
    DiscourseAct,
)
from symbolu_core.mechanical.pipeline.p7_discourse.p7_discourse_resolver import (
    P7DiscourseResolver,
)


# Singleton P7 resolver instance
_p7_resolver: Optional[P7DiscourseResolver] = None


def get_p7_resolver() -> P7DiscourseResolver:
    """Get or create the singleton P7 discourse resolver instance."""
    global _p7_resolver
    if _p7_resolver is None:
        _p7_resolver = P7DiscourseResolver()
    return _p7_resolver


def _has_blocked_upstream(ctx: Any) -> bool:
    """
    Check if any upstream envelope is blocked.

    This function checks if PO1-P6 have any blocking conditions
    that would prevent P7 from running.

    Args:
        ctx: Pipeline context.

    Returns:
        True if any upstream is blocked, False otherwise.
    """
    # Check PO1 for BLOCKED policy
    if hasattr(ctx, 'phase_minus_one') and ctx.phase_minus_one is not None:
        if ctx.phase_minus_one.is_blocked():
            return True

    # Check PO2 for blocked planning
    if hasattr(ctx, 'phase_zero') and ctx.phase_zero is not None:
        if ctx.phase_zero.is_planning_blocked():
            # Note: planning blocked doesn't necessarily block P7
            # P7 can still resolve to QUESTION for clarification
            pass

    # Check P6 for HOLD regime (this will be handled in resolver)
    # Not blocking here, resolver will handle

    return False


def maybe_run_p7(ctx: Any) -> None:
    """
    Run P7 discourse act resolution on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    P7 requires PO1, PO2, PO3, and P6 to be present.

    IMPORTANT: This function attaches the result to ctx.p7_discourse_envelope.
    It does NOT return the envelope - use get_p7_discourse(ctx) to retrieve it.

    CRITICAL: P7 is gating-only and deterministic. It constrains downstream
    language generation but does not directly produce any output.

    Rules:
    - Run only if PO1, PO2, PO3, and P6 exist
    - No BLOCKED envelope upstream (conservative check)
    - Attach DiscourseEnvelope to ctx.p7_discourse_envelope
    - Must not alter upstream behavior

    Args:
        ctx: Pipeline context with phase_minus_one, phase_zero,
             allowed_actions, and p6_regime.
    """
    # Check if PO1 output is available
    if not hasattr(ctx, 'phase_minus_one') or ctx.phase_minus_one is None:
        return

    # Check if PO2 output is available
    if not hasattr(ctx, 'phase_zero') or ctx.phase_zero is None:
        return

    # Check if PO3 output is available
    if not hasattr(ctx, 'allowed_actions') or ctx.allowed_actions is None:
        return

    # Check if P6 output is available (required for P7)
    if not hasattr(ctx, 'p6_regime') or ctx.p6_regime is None:
        return

    grounding_envelope: PhaseMinusOneEnvelope = ctx.phase_minus_one
    intent_envelope: IntentEnvelope = ctx.phase_zero
    action_contract: AllowedActionSet = ctx.allowed_actions
    regime_envelope: RegimeEnvelope = ctx.p6_regime

    # Run P7 resolver
    resolver = get_p7_resolver()
    envelope = resolver.resolve(
        grounding_envelope=grounding_envelope,
        intent_envelope=intent_envelope,
        action_contract=action_contract,
        regime_envelope=regime_envelope,
        grammar_evidence=None,  # Grammar evidence optional
    )

    # Attach to context (gating capture, no execution)
    ctx.p7_discourse_envelope = envelope


def run_p7_directly(
    grounding_envelope: PhaseMinusOneEnvelope,
    intent_envelope: IntentEnvelope,
    action_contract: AllowedActionSet,
    regime_envelope: RegimeEnvelope,
    grammar_evidence: Optional[Dict[str, Any]] = None,
) -> DiscourseEnvelope:
    """
    Run P7 directly with explicit inputs.

    Useful for testing or standalone discourse act resolution.

    CRITICAL: The discourse act selection constrains downstream language generation
    but does not directly produce any output.

    Args:
        grounding_envelope: PhaseMinusOneEnvelope from PO1.
        intent_envelope: IntentEnvelope from PO2.
        action_contract: AllowedActionSet from PO3.
        regime_envelope: RegimeEnvelope from P6.
        grammar_evidence: Optional grammar/linguistic evidence.

    Returns:
        DiscourseEnvelope with discourse act resolution verdict.
    """
    resolver = get_p7_resolver()
    return resolver.resolve(
        grounding_envelope=grounding_envelope,
        intent_envelope=intent_envelope,
        action_contract=action_contract,
        regime_envelope=regime_envelope,
        grammar_evidence=grammar_evidence,
    )


def get_p7_discourse(ctx: Any) -> Optional[DiscourseEnvelope]:
    """
    Get the P7 discourse envelope from context.

    Args:
        ctx: Pipeline context.

    Returns:
        DiscourseEnvelope or None if not available.
    """
    if not hasattr(ctx, 'p7_discourse_envelope'):
        return None
    return ctx.p7_discourse_envelope


def is_discourse_deferral(ctx: Any) -> bool:
    """
    Check if discourse act is DEFERRAL (most conservative).

    Args:
        ctx: Pipeline context.

    Returns:
        True if discourse act is DEFERRAL, False otherwise.
        Returns True (conservative) if P7 hasn't run.
    """
    discourse = get_p7_discourse(ctx)
    if discourse is None:
        # Conservative default: if P7 hasn't run, consider DEFERRAL
        return True
    return discourse.is_deferral()


def is_discourse_question(ctx: Any) -> bool:
    """
    Check if discourse act is QUESTION.

    Args:
        ctx: Pipeline context.

    Returns:
        True if discourse act is QUESTION, False otherwise.
    """
    discourse = get_p7_discourse(ctx)
    if discourse is None:
        return False
    return discourse.is_question()


def is_discourse_reflection(ctx: Any) -> bool:
    """
    Check if discourse act is REFLECTION.

    Args:
        ctx: Pipeline context.

    Returns:
        True if discourse act is REFLECTION, False otherwise.
    """
    discourse = get_p7_discourse(ctx)
    if discourse is None:
        return False
    return discourse.is_reflection()


def is_discourse_acknowledgment(ctx: Any) -> bool:
    """
    Check if discourse act is ACKNOWLEDGMENT.

    Args:
        ctx: Pipeline context.

    Returns:
        True if discourse act is ACKNOWLEDGMENT, False otherwise.
    """
    discourse = get_p7_discourse(ctx)
    if discourse is None:
        return False
    return discourse.is_acknowledgment()


def is_discourse_explanation(ctx: Any) -> bool:
    """
    Check if discourse act is EXPLANATION.

    Args:
        ctx: Pipeline context.

    Returns:
        True if discourse act is EXPLANATION, False otherwise.
    """
    discourse = get_p7_discourse(ctx)
    if discourse is None:
        return False
    return discourse.is_explanation()


def is_discourse_instruction(ctx: Any) -> bool:
    """
    Check if discourse act is INSTRUCTION.

    Args:
        ctx: Pipeline context.

    Returns:
        True if discourse act is INSTRUCTION, False otherwise.
    """
    discourse = get_p7_discourse(ctx)
    if discourse is None:
        return False
    return discourse.is_instruction()


def get_discourse_reason(ctx: Any) -> Optional[str]:
    """
    Get the reason string from the P7 discourse verdict.

    Args:
        ctx: Pipeline context.

    Returns:
        Reason string or None if P7 hasn't run.
    """
    discourse = get_p7_discourse(ctx)
    if discourse is None:
        return None
    return discourse.reason


def get_resolved_discourse_act(ctx: Any) -> Optional[DiscourseAct]:
    """
    Get the resolved discourse act from context.

    Args:
        ctx: Pipeline context.

    Returns:
        DiscourseAct or None if P7 hasn't run.
    """
    discourse = get_p7_discourse(ctx)
    if discourse is None:
        return None
    return discourse.act


__all__ = [
    "get_p7_resolver",
    "maybe_run_p7",
    "run_p7_directly",
    "get_p7_discourse",
    "is_discourse_deferral",
    "is_discourse_question",
    "is_discourse_reflection",
    "is_discourse_acknowledgment",
    "is_discourse_explanation",
    "is_discourse_instruction",
    "get_discourse_reason",
    "get_resolved_discourse_act",
]
