"""
P18 - Temporal Entropy Differential Integration

Integration functions for running P18 within the pipeline.
Provides singleton access and pipeline-friendly entry points.

Usage:
    from symbolu_core.mechanical.pipeline.p18_temporal_entropy import maybe_run_p18

    # In pipeline after P17:
    maybe_run_p18(ctx)

    # Access report:
    if ctx.p18 is not None:
        print(f"Entropy now: {ctx.p18.entropy_now}")
        print(f"Trend: {ctx.p18.trend.value}")
"""

from __future__ import annotations

from typing import Any, Optional

from symbolu_core.mechanical.pipeline.p18_temporal_entropy.p18_schema import (
    EntropyTrend,
    P18TemporalEntropyReport,
    VolatilityBand,
    P18_VERSION,
)
from symbolu_core.mechanical.pipeline.p18_temporal_entropy.p18_resolver import (
    P18TemporalEntropyDifferential,
)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_p18_resolver: Optional[P18TemporalEntropyDifferential] = None


def get_p18_resolver() -> P18TemporalEntropyDifferential:
    """
    Get the singleton P18TemporalEntropyDifferential instance.

    Returns:
        The shared P18TemporalEntropyDifferential instance
    """
    global _p18_resolver
    if _p18_resolver is None:
        _p18_resolver = P18TemporalEntropyDifferential()
    return _p18_resolver


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p18(ctx: Any) -> Optional[P18TemporalEntropyReport]:
    """
    Run P18 temporal entropy differential if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P18 should run
    2. Runs the entropy differential computation
    3. Attaches the report to ctx.p18
    4. Updates coherence_state history if available

    P18 is designed to run after P17 and after coherence computation.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The P18TemporalEntropyReport if run, None if skipped
    """
    # Check if P18 is disabled on this context
    if is_p18_disabled(ctx):
        return None

    # P18 can run with minimal inputs (will use neutral defaults)
    # Only skip if ctx has no relevant attributes at all
    has_any_input = (
        hasattr(ctx, "coherence_state") or
        hasattr(ctx, "p17") or
        hasattr(ctx, "tension_corridor")
    )

    if not has_any_input:
        # Context has none of the expected attributes, skip P18
        return None

    # Run the resolver
    resolver = get_p18_resolver()
    report = resolver.compute(ctx)

    # Attach to context
    if hasattr(ctx, "p18"):
        ctx.p18 = report
    else:
        # Context doesn't have p18 attribute, try to set it anyway
        try:
            setattr(ctx, "p18", report)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass

    # Update coherence_state history if available
    _update_coherence_state(ctx, report)

    return report


def run_p18_directly(
    coherence_state: Optional[Any] = None,
    p17: Optional[Any] = None,
    tension_corridor: Optional[float] = None,
) -> P18TemporalEntropyReport:
    """
    Run P18 directly with explicit inputs (for testing).

    This bypasses the context extraction and allows direct testing
    of the entropy differential with mock objects.

    Args:
        coherence_state: CoherenceState object (optional)
        p17: P17IntegrityReport object (optional)
        tension_corridor: Tension corridor value (optional)

    Returns:
        P18TemporalEntropyReport with computed metrics
    """
    # Create a simple namespace to hold the inputs
    class MockContext:
        pass

    ctx = MockContext()
    ctx.coherence_state = coherence_state
    ctx.p17 = p17
    ctx.tension_corridor = tension_corridor
    ctx.p18 = None  # Add p18 attribute so it can be set

    resolver = get_p18_resolver()
    return resolver.compute(ctx)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p18_disabled(ctx: Any) -> bool:
    """
    Check if P18 is disabled on this context.

    P18 can be disabled by setting ctx._p18_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P18 is disabled, False otherwise
    """
    return getattr(ctx, "_p18_disabled", False)


def has_p18_report(ctx: Any) -> bool:
    """
    Check if context has a P18 report attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p18 is set and not None
    """
    return getattr(ctx, "p18", None) is not None


def get_p18_report(ctx: Any) -> Optional[P18TemporalEntropyReport]:
    """
    Get the P18 report from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The P18TemporalEntropyReport if present, None otherwise
    """
    return getattr(ctx, "p18", None)


def get_entropy_now(ctx: Any) -> float:
    """
    Get the current entropy value from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Entropy value in [0.0, 1.0], or 0.5 if no report
    """
    report = get_p18_report(ctx)
    if report is None:
        return 0.5
    return report.entropy_now


def get_entropy_trend(ctx: Any) -> EntropyTrend:
    """
    Get the entropy trend from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        EntropyTrend, or INSUFFICIENT_HISTORY if no report
    """
    report = get_p18_report(ctx)
    if report is None:
        return EntropyTrend.INSUFFICIENT_HISTORY
    return report.trend


def get_volatility_band(ctx: Any) -> VolatilityBand:
    """
    Get the volatility band from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        VolatilityBand, or UNKNOWN if no report
    """
    report = get_p18_report(ctx)
    if report is None:
        return VolatilityBand.UNKNOWN
    return report.volatility_band


def is_entropy_increasing(ctx: Any) -> bool:
    """
    Check if entropy is trending upward.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if trend is INCREASING, False otherwise
    """
    report = get_p18_report(ctx)
    if report is None:
        return False
    return report.is_increasing()


def is_entropy_stable(ctx: Any) -> bool:
    """
    Check if entropy is stable.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if trend is STABLE, False otherwise
    """
    report = get_p18_report(ctx)
    if report is None:
        return False
    return report.is_stable()


def is_high_volatility(ctx: Any) -> bool:
    """
    Check if entropy volatility is high.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if volatility_band is HIGH, False otherwise
    """
    report = get_p18_report(ctx)
    if report is None:
        return False
    return report.is_high_volatility()


def get_p18_version() -> str:
    """
    Get the current P18 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P18_VERSION


def _update_coherence_state(ctx: Any, report: P18TemporalEntropyReport) -> None:
    """
    Update coherence_state with P18 metrics.

    This stores the current entropy values in the coherence state
    for use by future P18 computations.

    Args:
        ctx: PipelineContext with coherence_state
        report: The P18 report to store
    """
    coherence_state = getattr(ctx, "coherence_state", None)
    if coherence_state is None:
        return

    # Update snapshot
    if hasattr(coherence_state, "temporal_entropy_snapshot"):
        coherence_state.temporal_entropy_snapshot = report

    # Update current values
    if hasattr(coherence_state, "temporal_entropy_diff"):
        coherence_state.temporal_entropy_diff = report.entropy_now

    if hasattr(coherence_state, "temporal_entropy_volatility"):
        # Map volatility band to numeric value
        volatility_map = {
            VolatilityBand.LOW: 0.1,
            VolatilityBand.MED: 0.5,
            VolatilityBand.HIGH: 0.9,
            VolatilityBand.UNKNOWN: 0.5,
        }
        coherence_state.temporal_entropy_volatility = volatility_map.get(
            report.volatility_band, 0.5
        )

    # Update histories
    if hasattr(coherence_state, "temporal_entropy_diff_history"):
        if report.delta_entropy is not None:
            coherence_state.temporal_entropy_diff_history.append(report.delta_entropy)

    if hasattr(coherence_state, "temporal_entropy_volatility_history"):
        volatility_map = {
            VolatilityBand.LOW: 0.1,
            VolatilityBand.MED: 0.5,
            VolatilityBand.HIGH: 0.9,
            VolatilityBand.UNKNOWN: 0.5,
        }
        vol_value = volatility_map.get(report.volatility_band, 0.5)
        coherence_state.temporal_entropy_volatility_history.append(vol_value)


# Public exports
__all__ = [
    # Singleton
    "get_p18_resolver",
    # Integration
    "maybe_run_p18",
    "run_p18_directly",
    # Helpers
    "is_p18_disabled",
    "has_p18_report",
    "get_p18_report",
    "get_entropy_now",
    "get_entropy_trend",
    "get_volatility_band",
    "is_entropy_increasing",
    "is_entropy_stable",
    "is_high_volatility",
    "get_p18_version",
]
