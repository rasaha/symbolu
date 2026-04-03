"""
PO1 — Observer-Observed Grounding Pipeline Integration Module

Provides a thin shim for integrating PO1 (Observer-Observed Grounding)
into the Symbol-U pipeline. Called as the first governance stage before
any semantic or discourse processing.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Usage in orchestrator:
    from .grounding.po1_integration import maybe_run_po1

    # First stage in pipeline
    maybe_run_po1(ctx)
    # ctx.phase_minus_one is now set

Authority Model:
    - PO1 establishes grounding constraints
    - Authority flows downward (constraints are binding)
    - PO1 output feeds into PO2 (Intent Envelope)
"""

from typing import Any, Optional

from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_pipeline import PhaseMinusOnePipeline
from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_schema import PhaseMinusOneEnvelope, OverallPolicy
from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_session import SessionContext


# Singleton PO1 pipeline instance
_po1_pipeline: Optional[PhaseMinusOnePipeline] = None


def get_po1_pipeline() -> PhaseMinusOnePipeline:
    """Get or create the singleton PO1 pipeline instance."""
    global _po1_pipeline
    if _po1_pipeline is None:
        _po1_pipeline = PhaseMinusOnePipeline()
    return _po1_pipeline


def maybe_run_po1(ctx: Any) -> None:
    """
    Run PO1 grounding analysis on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    PO1 is the first governance stage and has no upstream dependencies.

    IMPORTANT: This function attaches the result to ctx.phase_minus_one.
    It does NOT return the envelope - use get_po1_envelope(ctx) to retrieve it.

    Rules:
    - Run on every request (no skip conditions)
    - Attach PhaseMinusOneEnvelope to ctx.phase_minus_one
    - Subsequent stages must respect grounding constraints

    Args:
        ctx: Pipeline context with request.
    """
    if not hasattr(ctx, 'request') or ctx.request is None:
        return

    text = ctx.request.text
    if not text:
        return

    pipeline = get_po1_pipeline()

    # Check if session context is available
    session = _get_or_create_session(ctx)

    if session:
        envelope = pipeline.run_with_session(text, session)
    else:
        envelope = pipeline.run(text)

    # Attach to context
    ctx.phase_minus_one = envelope


def _get_or_create_session(ctx: Any) -> Optional[SessionContext]:
    """
    Get existing session context or create new one if session tracking enabled.

    Session context is created if:
    - session_id is present in request metadata
    - A session store is available in context

    Args:
        ctx: Pipeline context.

    Returns:
        SessionContext or None if session tracking not enabled.
    """
    # Check if session context already exists
    if hasattr(ctx, 'po1_session') and ctx.po1_session is not None:
        return ctx.po1_session

    # Check if session tracking is enabled via metadata
    if hasattr(ctx, 'request') and ctx.request.metadata:
        session_id = ctx.request.metadata.get('session_id')
        if session_id:
            # Create new session context for this session
            session = SessionContext.create()
            ctx.po1_session = session
            return session

    return None


def run_po1_directly(text: str, session: Optional[SessionContext] = None) -> PhaseMinusOneEnvelope:
    """
    Run PO1 directly with explicit inputs.

    Useful for testing or standalone grounding analysis.

    Args:
        text: Input text to analyze.
        session: Optional session context for multi-turn awareness.

    Returns:
        PhaseMinusOneEnvelope with grounding analysis.
    """
    pipeline = get_po1_pipeline()
    if session:
        return pipeline.run_with_session(text, session)
    return pipeline.run(text)


def get_po1_envelope(ctx: Any) -> Optional[PhaseMinusOneEnvelope]:
    """
    Get the PO1 grounding envelope from context.

    Args:
        ctx: Pipeline context.

    Returns:
        PhaseMinusOneEnvelope or None if not available.
    """
    if not hasattr(ctx, 'phase_minus_one'):
        return None
    return ctx.phase_minus_one


def is_grounding_blocked(ctx: Any) -> bool:
    """
    Check if grounding analysis resulted in BLOCKED policy.

    Args:
        ctx: Pipeline context.

    Returns:
        True if grounding is blocked, False otherwise.
        Returns True (conservative) if PO1 hasn't run.
    """
    envelope = get_po1_envelope(ctx)
    if envelope is None:
        return True
    return envelope.overall_policy == OverallPolicy.BLOCKED


def is_multi_context(ctx: Any) -> bool:
    """
    Check if grounding analysis found multiple contexts.

    Args:
        ctx: Pipeline context.

    Returns:
        True if multi-context detected, False otherwise.
    """
    envelope = get_po1_envelope(ctx)
    if envelope is None:
        return False
    return envelope.overall_policy == OverallPolicy.MULTI_CONTEXT


def get_overall_policy(ctx: Any) -> Optional[OverallPolicy]:
    """
    Get the overall grounding policy from PO1.

    Args:
        ctx: Pipeline context.

    Returns:
        OverallPolicy or None if PO1 hasn't run.
    """
    envelope = get_po1_envelope(ctx)
    if envelope is None:
        return None
    return envelope.overall_policy


__all__ = [
    "get_po1_pipeline",
    "maybe_run_po1",
    "run_po1_directly",
    "get_po1_envelope",
    "is_grounding_blocked",
    "is_multi_context",
    "get_overall_policy",
]
