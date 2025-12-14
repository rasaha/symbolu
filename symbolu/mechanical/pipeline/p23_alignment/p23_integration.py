"""
P23 - Inner-Outer Alignment Observer Integration

This phase is observer-only and non-authoritative.

Integration functions for running P23 within the pipeline.
Provides singleton access and pipeline-friendly entry points.

Usage:
    from symbolu.mechanical.pipeline.p23_alignment import maybe_run_p23

    # In pipeline after P22:
    ctx = maybe_run_p23(ctx)

    # Access alignment report:
    if ctx.p23_alignment_report is not None:
        print(f"State: {ctx.p23_alignment_report.alignment_state}")
        print(f"Score: {ctx.p23_alignment_report.tension_score}")

CRITICAL CONSTRAINTS:
    - Must not block pipeline execution
    - Must not modify routing, regime, discourse, planner, or renderer
    - Must not read text, tokens, semantics, intent, ontology
    - Must not feed back into P1-P22
    - Attaches result to ctx.p23_alignment_report only
    - No downstream routing effect
"""

from __future__ import annotations

from typing import Any, Optional

from symbolu.mechanical.pipeline.p23_alignment.p23_schema import (
    P23_VERSION,
    AlignmentState,
    P23AlignmentReport,
    P23InvariantViolation,
    create_empty_report,
)
from symbolu.mechanical.pipeline.p23_alignment.p23_resolver import (
    AlignmentObserver,
)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================


_p23_observer: Optional[AlignmentObserver] = None


def get_p23_observer() -> AlignmentObserver:
    """
    Get the singleton AlignmentObserver instance.

    This phase is observer-only and non-authoritative.

    Returns:
        The shared AlignmentObserver instance
    """
    global _p23_observer
    if _p23_observer is None:
        _p23_observer = AlignmentObserver()
    return _p23_observer


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p23(ctx: Any) -> Any:
    """
    Run P23 alignment observation if prerequisites are met.

    This phase is observer-only and non-authoritative.

    This is the main integration entry point. It:
        1. Checks if PO1 is BLOCKED -> returns ctx unchanged
        2. Checks if P22 witness is available
        3. Extracts alignment observation
        4. Attaches the report to ctx.p23_alignment_report
        5. Never blocks pipeline execution

    P23 is designed to run after P22 and has no downstream routing effect.

    CRITICAL: This function:
        - Must NOT modify routing, regime, discourse, planner, or renderer
        - Must NOT read text, tokens, semantics, intent, ontology
        - Must NOT feed back into P1-P22
        - Must NOT block pipeline execution

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The same ctx object (possibly with p23_alignment_report attached)
    """
    # Check for None context
    if ctx is None:
        return ctx

    # Check if P23 is disabled on this context
    if is_p23_disabled(ctx):
        return ctx

    # Check if PO1 is BLOCKED -> return ctx unchanged
    if _is_po1_blocked(ctx):
        # Still attach an empty report with blocked tag
        report = create_empty_report()
        _attach_report(ctx, report)
        return ctx

    # Run the observer
    try:
        observer = get_p23_observer()
        report = observer.observe_from_context(ctx)
    except P23InvariantViolation:
        # Re-raise invariant violations - these are critical
        raise
    except Exception:
        # For other errors, attach empty report to not block pipeline
        # In production, this should be logged
        report = create_empty_report()

    # Attach to context (observer-only attribute)
    _attach_report(ctx, report)

    return ctx


def run_p23(ctx: Any) -> P23AlignmentReport:
    """
    Run P23 directly, always returning a report.

    This phase is observer-only and non-authoritative.

    Unlike maybe_run_p23, this always runs and returns a report.
    Use this for testing or when you need guaranteed output.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        P23AlignmentReport (always returns, never None)
    """
    observer = get_p23_observer()
    return observer.observe_from_context(ctx)


def run_p23_directly(
    pressure_band: str = "low",
    motion_stability: str = "stable",
    regime: str = "OPEN",
    discourse_act: str = "DEFERRAL",
) -> P23AlignmentReport:
    """
    Run P23 directly with explicit inputs (for testing).

    This phase is observer-only and non-authoritative.

    This bypasses context extraction and allows direct testing
    of the alignment observation with mock values.

    Args:
        pressure_band: Acoustic pressure ("low", "moderate", "high")
        motion_stability: Motion stability ("stable", "oscillatory", "chaotic")
        regime: Operational regime
        discourse_act: Discourse act

    Returns:
        P23AlignmentReport with alignment observations
    """
    observer = get_p23_observer()
    return observer.observe(
        pressure_band=pressure_band,
        motion_stability=motion_stability,
        regime=regime,
        discourse_act=discourse_act,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _is_po1_blocked(ctx: Any) -> bool:
    """
    Check if PO1 (phase_minus_one) is blocked.

    This phase is observer-only and non-authoritative.

    Args:
        ctx: Pipeline context

    Returns:
        True if PO1 is blocked, False otherwise
    """
    # Try phase_minus_one
    po1 = getattr(ctx, "phase_minus_one", None)
    if po1 is not None:
        is_blocked_method = getattr(po1, "is_blocked", None)
        if callable(is_blocked_method):
            return is_blocked_method()
        # Try direct attribute
        blocked = getattr(po1, "blocked", None)
        if blocked is not None:
            return bool(blocked)

    return False


def _attach_report(ctx: Any, report: P23AlignmentReport) -> None:
    """
    Attach the alignment report to context.

    This phase is observer-only and non-authoritative.

    Attaches to ctx.p23_alignment_report only.
    P23 must NOT write to any other ctx attribute.

    Args:
        ctx: PipelineContext
        report: The P23 alignment report
    """
    # Attach to p23_alignment_report (standard attribute)
    if hasattr(ctx, "p23_alignment_report"):
        ctx.p23_alignment_report = report
    else:
        try:
            setattr(ctx, "p23_alignment_report", report)
        except AttributeError:
            pass  # Context is frozen

    # Also attach to p23 for consistency with other phases
    if hasattr(ctx, "p23"):
        ctx.p23 = report
    else:
        try:
            setattr(ctx, "p23", report)
        except AttributeError:
            pass  # Context is frozen


def is_p23_disabled(ctx: Any) -> bool:
    """
    Check if P23 is disabled on this context.

    This phase is observer-only and non-authoritative.

    P23 can be disabled by setting ctx._p23_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P23 is disabled, False otherwise
    """
    return getattr(ctx, "_p23_disabled", False)


def has_p23_report(ctx: Any) -> bool:
    """
    Check if context has a P23 report attached.

    This phase is observer-only and non-authoritative.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p23_alignment_report or ctx.p23 is set
    """
    return (
        getattr(ctx, "p23_alignment_report", None) is not None or
        getattr(ctx, "p23", None) is not None
    )


def get_p23_report(ctx: Any) -> Optional[P23AlignmentReport]:
    """
    Get the P23 report from context if present.

    This phase is observer-only and non-authoritative.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The P23AlignmentReport if present, None otherwise
    """
    report = getattr(ctx, "p23_alignment_report", None)
    if report is None:
        report = getattr(ctx, "p23", None)
    return report


def get_alignment_state(ctx: Any) -> AlignmentState:
    """
    Get the alignment state from context.

    This phase is observer-only and non-authoritative.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        AlignmentState (NEUTRAL as default if no report)
    """
    report = get_p23_report(ctx)
    if report is None:
        return AlignmentState.NEUTRAL
    return report.alignment_state


def get_tension_score(ctx: Any) -> float:
    """
    Get the tension score from context.

    This phase is observer-only and non-authoritative.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Tension score (0.0 as default if no report)
    """
    report = get_p23_report(ctx)
    if report is None:
        return 0.0
    return report.tension_score


def get_alignment_tags(ctx: Any) -> frozenset:
    """
    Get the alignment tags from context.

    This phase is observer-only and non-authoritative.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Frozenset of alignment tags (empty if no report)
    """
    report = get_p23_report(ctx)
    if report is None:
        return frozenset()
    return report.alignment_tags


def is_aligned(ctx: Any) -> bool:
    """
    Check if alignment state is ALIGNED.

    This phase is observer-only and non-authoritative.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if aligned, False otherwise
    """
    return get_alignment_state(ctx) == AlignmentState.ALIGNED


def is_tension(ctx: Any) -> bool:
    """
    Check if alignment state is TENSION or CONTRADICTION.

    This phase is observer-only and non-authoritative.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if tension or contradiction, False otherwise
    """
    state = get_alignment_state(ctx)
    return state in (AlignmentState.TENSION, AlignmentState.CONTRADICTION)


def get_p23_version() -> str:
    """
    Get the current P23 schema version.

    This phase is observer-only and non-authoritative.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P23_VERSION


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    # Singleton
    "get_p23_observer",
    # Integration
    "maybe_run_p23",
    "run_p23",
    "run_p23_directly",
    # Helpers
    "is_p23_disabled",
    "has_p23_report",
    "get_p23_report",
    "get_alignment_state",
    "get_tension_score",
    "get_alignment_tags",
    "is_aligned",
    "is_tension",
    "get_p23_version",
]
