"""
PO1 — Observer–Observed Grounding Pipeline Integration Module
(Implemented as phase_minus_one for backward compatibility)

Provides a thin shim for integrating PO1 (Observer-Observed Grounding)
into the Symbol-U pipeline. Called at the earliest safe entry point before
any semantic processing.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Usage in orchestrator:
    from .phase_minus_one_integration import maybe_run_phase_minus_one

    # After MLCR stage (earliest safe point)
    ctx.phase_minus_one = maybe_run_phase_minus_one(ctx)

Authority Model:
    - PO1 establishes grounding constraints
    - Authority flows downward (constraints are binding on downstream stages)
    - Information flows upward (violations reported but not overridden)
"""

from typing import Any, Optional

from symbolu.mechanical.pipeline.grounding import (
    PhaseMinusOnePipeline,
    PhaseMinusOneEnvelope,
)

# Singleton PO1 pipeline instance
_phase_minus_one_pipeline: Optional[PhaseMinusOnePipeline] = None


def get_phase_minus_one_pipeline() -> PhaseMinusOnePipeline:
    """Get or create the singleton PO1 pipeline instance."""
    global _phase_minus_one_pipeline
    if _phase_minus_one_pipeline is None:
        _phase_minus_one_pipeline = PhaseMinusOnePipeline()
    return _phase_minus_one_pipeline


def maybe_run_phase_minus_one(ctx: Any) -> Optional[PhaseMinusOneEnvelope]:
    """
    Run PO1 grounding analysis on the request text.

    This is the main integration function to call from the pipeline orchestrator.
    PO1 always runs as it provides essential grounding constraints.

    Args:
        ctx: Pipeline context with request.

    Returns:
        PhaseMinusOneEnvelope with grounding analysis.
    """
    # Check if we have a request
    if not hasattr(ctx, 'request') or ctx.request is None:
        return None

    # Get the request text
    text = ctx.request.text if hasattr(ctx.request, 'text') else None
    if not text or not text.strip():
        return None

    # Run PO1 pipeline
    pipeline = get_phase_minus_one_pipeline()
    return pipeline.run(text)


def run_phase_minus_one_directly(text: str) -> PhaseMinusOneEnvelope:
    """
    Run PO1 directly with explicit text input.

    Useful for testing or standalone grounding analysis.

    Args:
        text: The text to analyze.

    Returns:
        PhaseMinusOneEnvelope with grounding analysis.
    """
    pipeline = get_phase_minus_one_pipeline()
    return pipeline.run(text)


def is_pipeline_blocked(ctx: Any) -> bool:
    """
    Check if pipeline is blocked due to PO1 grounding.

    Args:
        ctx: Pipeline context.

    Returns:
        True if pipeline should be blocked (requires clarification).
    """
    if not hasattr(ctx, 'phase_minus_one') or ctx.phase_minus_one is None:
        return False
    return ctx.phase_minus_one.is_blocked()


def get_grounding_envelope(ctx: Any) -> Optional[PhaseMinusOneEnvelope]:
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


__all__ = [
    "get_phase_minus_one_pipeline",
    "maybe_run_phase_minus_one",
    "run_phase_minus_one_directly",
    "is_pipeline_blocked",
    "get_grounding_envelope",
]
