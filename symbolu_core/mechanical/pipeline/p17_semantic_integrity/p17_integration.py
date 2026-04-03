"""
P17 - Semantic Integrity Monitor Integration

Integration functions for running P17 within the pipeline.
Provides singleton access and pipeline-friendly entry points.

Usage:
    from symbolu_core.mechanical.pipeline.p17_semantic_integrity import maybe_run_p17

    # In pipeline after P9:
    maybe_run_p17(ctx)

    # Access report:
    if ctx.p17 is not None:
        print(f"Integrity score: {ctx.p17.integrity_score}")
"""

from __future__ import annotations

from typing import Any, Optional

from symbolu_core.mechanical.pipeline.p17_semantic_integrity.p17_schema import (
    P17IntegrityReport,
    P17_VERSION,
)
from symbolu_core.mechanical.pipeline.p17_semantic_integrity.p17_resolver import (
    P17SemanticIntegrityMonitor,
)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_p17_monitor: Optional[P17SemanticIntegrityMonitor] = None


def get_p17_monitor() -> P17SemanticIntegrityMonitor:
    """
    Get the singleton P17SemanticIntegrityMonitor instance.

    Returns:
        The shared P17SemanticIntegrityMonitor instance
    """
    global _p17_monitor
    if _p17_monitor is None:
        _p17_monitor = P17SemanticIntegrityMonitor()
    return _p17_monitor


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p17(ctx: Any) -> Optional[P17IntegrityReport]:
    """
    Run P17 semantic integrity monitor if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P17 should run (at least some upstream artifacts present)
    2. Runs the integrity monitor
    3. Attaches the report to ctx.p17

    P17 is designed to run after P9 (lexical selection) and before
    any downstream rendering or DHA phases.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The P17IntegrityReport if run, None if skipped
    """
    # Check if P17 is disabled on this context
    if is_p17_disabled(ctx):
        return None

    # P17 can run even with minimal inputs (will report INSUFFICIENT_EVIDENCE)
    # The only case we skip is if ctx has no relevant attributes at all
    has_any_input = (
        hasattr(ctx, "phase_minus_one") or
        hasattr(ctx, "p6_regime") or
        hasattr(ctx, "p7_discourse_envelope") or
        hasattr(ctx, "semantic_frame") or
        hasattr(ctx, "lexical_frame")
    )

    if not has_any_input:
        # Context has none of the expected attributes, skip P17
        return None

    # Run the monitor
    monitor = get_p17_monitor()
    report = monitor.run(ctx)

    # Attach to context
    if hasattr(ctx, "p17"):
        ctx.p17 = report
    else:
        # Context doesn't have p17 attribute, try to set it anyway
        try:
            setattr(ctx, "p17", report)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass

    return report


def run_p17_directly(
    po1: Optional[Any] = None,
    p6: Optional[Any] = None,
    p7: Optional[Any] = None,
    p8: Optional[Any] = None,
    p9: Optional[Any] = None,
) -> P17IntegrityReport:
    """
    Run P17 directly with explicit inputs (for testing).

    This bypasses the context extraction and allows direct testing
    of the integrity monitor with mock objects.

    Args:
        po1: PO1 grounding envelope (optional)
        p6: P6 regime envelope (optional)
        p7: P7 discourse envelope (optional)
        p8: P8 semantic frame (optional)
        p9: P9 lexical frame (optional)

    Returns:
        P17IntegrityReport with analysis results
    """
    # Create a simple namespace to hold the inputs
    class MockContext:
        pass

    ctx = MockContext()
    ctx.phase_minus_one = po1
    ctx.p6_regime = p6
    ctx.p7_discourse_envelope = p7
    ctx.semantic_frame = p8
    ctx.lexical_frame = p9

    monitor = get_p17_monitor()
    return monitor.run(ctx)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p17_disabled(ctx: Any) -> bool:
    """
    Check if P17 is disabled on this context.

    P17 can be disabled by setting ctx._p17_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P17 is disabled, False otherwise
    """
    return getattr(ctx, "_p17_disabled", False)


def has_p17_report(ctx: Any) -> bool:
    """
    Check if context has a P17 report attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p17 is set and not None
    """
    return getattr(ctx, "p17", None) is not None


def get_p17_report(ctx: Any) -> Optional[P17IntegrityReport]:
    """
    Get the P17 report from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The P17IntegrityReport if present, None otherwise
    """
    return getattr(ctx, "p17", None)


def is_integrity_clean(ctx: Any) -> bool:
    """
    Check if context has clean integrity (no HIGH severity issues).

    Convenience function for downstream gating decisions.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P17 report is_clean, False otherwise (including if no report)
    """
    report = get_p17_report(ctx)
    if report is None:
        return False
    return report.is_clean


def get_integrity_score(ctx: Any) -> float:
    """
    Get the integrity score from context.

    Convenience function for downstream gating decisions.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Integrity score in [0.0, 1.0], or 0.0 if no report
    """
    report = get_p17_report(ctx)
    if report is None:
        return 0.0
    return report.integrity_score


def get_p17_version() -> str:
    """
    Get the current P17 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P17_VERSION


# Public exports
__all__ = [
    # Singleton
    "get_p17_monitor",
    # Integration
    "maybe_run_p17",
    "run_p17_directly",
    # Helpers
    "is_p17_disabled",
    "has_p17_report",
    "get_p17_report",
    "is_integrity_clean",
    "get_integrity_score",
    "get_p17_version",
]
