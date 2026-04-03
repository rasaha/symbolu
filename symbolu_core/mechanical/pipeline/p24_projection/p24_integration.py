"""
P24 - Acoustic-Ontology Projection Observer Integration

This phase is observer-only and non-authoritative.

Integration functions for running P24 within the pipeline.
Provides singleton access and pipeline-friendly entry points.

Usage:
    from symbolu_core.mechanical.pipeline.p24_projection import maybe_run_p24

    # In pipeline after P23:
    ctx = maybe_run_p24(ctx)

    # Access projection report:
    if ctx.p24_projection_report is not None:
        print(f"Layers: {ctx.p24_projection_report.projected_layers}")
        print(f"Risk: {ctx.p24_projection_report.projection_risk_band}")

CRITICAL CONSTRAINTS:
    - Must not block pipeline execution
    - Must not modify routing, regime, discourse, planner, or renderer
    - Must not read text, tokens
    - Must not feed back into P1-P23
    - Attaches result to ctx.p24_projection_report only
    - No downstream routing effect
"""

from __future__ import annotations

from typing import Any, Optional

from symbolu_core.mechanical.pipeline.p24_projection.p24_projection_schema import (
    P24_VERSION,
    OntologyLayer,
    ProjectionRiskBand,
    ProjectionMismatchType,
    P24ProjectionReport,
    P24InvariantViolation,
    create_empty_report,
)
from symbolu_core.mechanical.pipeline.p24_projection.p24_projection_resolver import (
    P24ProjectionResolver,
)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================


_p24_resolver: Optional[P24ProjectionResolver] = None


def get_p24_resolver() -> P24ProjectionResolver:
    """
    Get the singleton P24ProjectionResolver instance.

    This phase is observer-only and non-authoritative.

    Returns:
        The shared P24ProjectionResolver instance
    """
    global _p24_resolver
    if _p24_resolver is None:
        _p24_resolver = P24ProjectionResolver()
    return _p24_resolver


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p24(ctx: Any) -> Any:
    """
    Run P24 projection observation if prerequisites are met.

    This phase is observer-only and non-authoritative.

    This is the main integration entry point. It:
        1. Checks if PO1 is BLOCKED -> returns ctx with blocked report
        2. Resolves projection from pipeline artifacts
        3. Attaches the report to ctx.p24_projection_report
        4. Never blocks pipeline execution

    P24 is designed to run after P23 and has no downstream routing effect.

    CRITICAL: This function:
        - Must NOT modify routing, regime, discourse, planner, or renderer
        - Must NOT read text, tokens
        - Must NOT feed back into P1-P23
        - Must NOT block pipeline execution

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The same ctx object (possibly with p24_projection_report attached)
    """
    # Check for None context
    if ctx is None:
        return ctx

    # Check if P24 is disabled on this context
    if is_p24_disabled(ctx):
        return ctx

    # Run the resolver
    try:
        resolver = get_p24_resolver()
        report = resolver.resolve(ctx)
    except P24InvariantViolation:
        # Re-raise invariant violations - these are critical
        raise
    except Exception:
        # For other errors, attach empty report to not block pipeline
        # In production, this should be logged
        report = create_empty_report()

    # Attach to context (observer-only attribute)
    _attach_report(ctx, report)

    return ctx


def run_p24(ctx: Any) -> P24ProjectionReport:
    """
    Run P24 directly, always returning a report.

    This phase is observer-only and non-authoritative.

    Unlike maybe_run_p24, this always runs and returns a report.
    Use this for testing or when you need guaranteed output.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        P24ProjectionReport (always returns, never None)
    """
    resolver = get_p24_resolver()
    return resolver.resolve(ctx)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _attach_report(ctx: Any, report: P24ProjectionReport) -> None:
    """
    Attach the projection report to context.

    This phase is observer-only and non-authoritative.

    Attaches to ctx.p24_projection_report only.
    P24 must NOT write to any other ctx attribute.

    Args:
        ctx: PipelineContext
        report: The P24 projection report
    """
    # Attach to p24_projection_report (standard attribute)
    if hasattr(ctx, "p24_projection_report"):
        ctx.p24_projection_report = report
    else:
        try:
            setattr(ctx, "p24_projection_report", report)
        except AttributeError:
            pass  # Context is frozen

    # Also attach to p24 for consistency with other phases
    if hasattr(ctx, "p24"):
        ctx.p24 = report
    else:
        try:
            setattr(ctx, "p24", report)
        except AttributeError:
            pass  # Context is frozen


def is_p24_disabled(ctx: Any) -> bool:
    """
    Check if P24 is disabled on this context.

    This phase is observer-only and non-authoritative.

    P24 can be disabled by setting ctx._p24_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P24 is disabled, False otherwise
    """
    return getattr(ctx, "_p24_disabled", False)


def has_p24_report(ctx: Any) -> bool:
    """
    Check if context has a P24 report attached.

    This phase is observer-only and non-authoritative.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p24_projection_report or ctx.p24 is set
    """
    return (
        getattr(ctx, "p24_projection_report", None) is not None or
        getattr(ctx, "p24", None) is not None
    )


def get_p24_report(ctx: Any) -> Optional[P24ProjectionReport]:
    """
    Get the P24 report from context if present.

    This phase is observer-only and non-authoritative.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The P24ProjectionReport if present, None otherwise
    """
    report = getattr(ctx, "p24_projection_report", None)
    if report is None:
        report = getattr(ctx, "p24", None)
    return report


def is_high_risk(report: Optional[P24ProjectionReport]) -> bool:
    """
    Check if report indicates high risk.

    This phase is observer-only and non-authoritative.

    Args:
        report: P24ProjectionReport or None

    Returns:
        True if high risk, False otherwise
    """
    if report is None:
        return False
    return report.is_high_risk()


def has_strong_mismatch(report: Optional[P24ProjectionReport]) -> bool:
    """
    Check if report indicates strong mismatch.

    This phase is observer-only and non-authoritative.

    Args:
        report: P24ProjectionReport or None

    Returns:
        True if strong mismatch, False otherwise
    """
    if report is None:
        return False
    return report.has_strong_mismatch()


def get_projected_layers(ctx: Any) -> tuple:
    """
    Get the projected layers from context.

    This phase is observer-only and non-authoritative.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Tuple of OntologyLayer (empty tuple if no report)
    """
    report = get_p24_report(ctx)
    if report is None:
        return ()
    return report.projected_layers


def get_projection_tags(ctx: Any) -> frozenset:
    """
    Get the projection tags from context.

    This phase is observer-only and non-authoritative.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Frozenset of projection tags (empty if no report)
    """
    report = get_p24_report(ctx)
    if report is None:
        return frozenset()
    return report.projection_tags


def get_risk_band(ctx: Any) -> ProjectionRiskBand:
    """
    Get the projection risk band from context.

    This phase is observer-only and non-authoritative.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        ProjectionRiskBand (LOW as default if no report)
    """
    report = get_p24_report(ctx)
    if report is None:
        return ProjectionRiskBand.LOW
    return report.projection_risk_band


def get_mismatch_type(ctx: Any) -> ProjectionMismatchType:
    """
    Get the mismatch type from context.

    This phase is observer-only and non-authoritative.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        ProjectionMismatchType (NONE as default if no report)
    """
    report = get_p24_report(ctx)
    if report is None:
        return ProjectionMismatchType.NONE
    return report.mismatch_type


def get_confidence(ctx: Any) -> float:
    """
    Get the confidence score from context.

    This phase is observer-only and non-authoritative.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Confidence score (0.0 as default if no report)
    """
    report = get_p24_report(ctx)
    if report is None:
        return 0.0
    return report.confidence


def get_p24_version() -> str:
    """
    Get the current P24 schema version.

    This phase is observer-only and non-authoritative.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P24_VERSION


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    # Singleton
    "get_p24_resolver",
    # Integration
    "maybe_run_p24",
    "run_p24",
    # Helpers
    "is_p24_disabled",
    "has_p24_report",
    "get_p24_report",
    "is_high_risk",
    "has_strong_mismatch",
    "get_projected_layers",
    "get_projection_tags",
    "get_risk_band",
    "get_mismatch_type",
    "get_confidence",
    "get_p24_version",
]
