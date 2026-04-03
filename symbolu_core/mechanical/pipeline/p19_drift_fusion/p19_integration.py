"""
P19 - Drift Fusion Integration

Integration functions for running P19 within the pipeline.
Provides singleton access and pipeline-friendly entry points.

Usage:
    from symbolu_core.mechanical.pipeline.p19_drift_fusion import maybe_run_p19

    # In pipeline after P17 and P18:
    maybe_run_p19(ctx)

    # Access report:
    if ctx.p19 is not None:
        print(f"Drift index: {ctx.p19.drift_fusion_index}")
        print(f"Risk band: {ctx.p19.drift_risk_band}")

CRITICAL CONSTRAINTS:
    ❌ Must NOT:
        - Infer intent
        - Infer emotion
        - Select regime
        - Gate actions
        - Trigger any side effects
"""

from __future__ import annotations

from typing import Any, List, Optional

from symbolu_core.mechanical.pipeline.p19_drift_fusion.p19_schema import (
    P19_VERSION,
    P19DriftFusionReport,
    DriftRiskBand,
    DriftPatternTag,
)
from symbolu_core.mechanical.pipeline.p19_drift_fusion.p19_resolver import (
    P19DriftFusion,
)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_p19_resolver: Optional[P19DriftFusion] = None


def get_p19_resolver() -> P19DriftFusion:
    """
    Get the singleton P19DriftFusion instance.

    Returns:
        The shared P19DriftFusion instance
    """
    global _p19_resolver
    if _p19_resolver is None:
        _p19_resolver = P19DriftFusion()
    return _p19_resolver


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p19(ctx: Any) -> Optional[P19DriftFusionReport]:
    """
    Run P19 drift fusion if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P19 should run
    2. Runs the drift fusion computation
    3. Attaches the report to ctx.p19
    4. Updates coherence_state if available

    P19 is designed to run after P17 and P18, as it fuses their signals.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The P19DriftFusionReport if run, None if skipped
    """
    # Check if P19 is disabled on this context
    if is_p19_disabled(ctx):
        return None

    # P19 can run with minimal inputs (will use neutral defaults)
    # Only skip if ctx has no relevant attributes at all
    has_any_input = (
        hasattr(ctx, "coherence_state") or
        hasattr(ctx, "p17") or
        hasattr(ctx, "p18")
    )

    if not has_any_input:
        # Context has none of the expected attributes, skip P19
        return None

    # Run the resolver
    resolver = get_p19_resolver()
    report = resolver.compute(ctx)

    # If all inputs were None, report is None
    if report is None:
        return None

    # Attach to context
    if hasattr(ctx, "p19"):
        ctx.p19 = report
    else:
        # Context doesn't have p19 attribute, try to set it anyway
        try:
            setattr(ctx, "p19", report)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass

    # Update coherence_state if available
    _update_coherence_state(ctx, report)

    return report


def run_p19_directly(
    semantic_integrity_score: Optional[float] = None,
    cognitive_drift_v3: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
    temporal_entropy_volatility: Optional[float] = None,
    coherence_fused: Optional[float] = None,
) -> Optional[P19DriftFusionReport]:
    """
    Run P19 directly with explicit inputs (for testing).

    This bypasses the context extraction and allows direct testing
    of the drift fusion with mock values.

    Args:
        semantic_integrity_score: P17 semantic integrity [0, 1]
        cognitive_drift_v3: P17 cognitive drift [0, 1]
        temporal_entropy_diff: P18 normalized entropy diff [0, 1]
        temporal_entropy_volatility: P18 entropy volatility [0, 1]
        coherence_fused: P16 fused coherence [0, 1]

    Returns:
        P19DriftFusionReport with computed metrics, or None if all inputs None
    """
    resolver = get_p19_resolver()
    return resolver.compute_from_values(
        semantic_integrity_score=semantic_integrity_score,
        cognitive_drift_v3=cognitive_drift_v3,
        temporal_entropy_diff=temporal_entropy_diff,
        temporal_entropy_volatility=temporal_entropy_volatility,
        coherence_fused=coherence_fused,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p19_disabled(ctx: Any) -> bool:
    """
    Check if P19 is disabled on this context.

    P19 can be disabled by setting ctx._p19_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P19 is disabled, False otherwise
    """
    return getattr(ctx, "_p19_disabled", False)


def has_p19_report(ctx: Any) -> bool:
    """
    Check if context has a P19 report attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p19 is set and not None
    """
    return getattr(ctx, "p19", None) is not None


def get_p19_report(ctx: Any) -> Optional[P19DriftFusionReport]:
    """
    Get the P19 report from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The P19DriftFusionReport if present, None otherwise
    """
    return getattr(ctx, "p19", None)


def get_drift_fusion_index(ctx: Any) -> float:
    """
    Get the drift fusion index from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Drift fusion index in [0.0, 1.0], or 0.0 if no report
    """
    report = get_p19_report(ctx)
    if report is None:
        return 0.0
    return report.drift_fusion_index


def get_drift_risk_band(ctx: Any) -> str:
    """
    Get the drift risk band from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Risk band string ("low", "moderate", "high"), or "low" if no report
    """
    report = get_p19_report(ctx)
    if report is None:
        return "low"
    return report.drift_risk_band


def get_drift_pattern_tags(ctx: Any) -> List[str]:
    """
    Get the drift pattern tags from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        List of pattern tag strings, or empty list if no report
    """
    report = get_p19_report(ctx)
    if report is None:
        return []
    return list(report.drift_pattern_tags)


def is_low_risk(ctx: Any) -> bool:
    """
    Check if drift risk is low.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if risk band is "low", False otherwise
    """
    report = get_p19_report(ctx)
    if report is None:
        return True  # Default to safe assumption
    return report.is_low_risk()


def is_moderate_risk(ctx: Any) -> bool:
    """
    Check if drift risk is moderate.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if risk band is "moderate", False otherwise
    """
    report = get_p19_report(ctx)
    if report is None:
        return False
    return report.is_moderate_risk()


def is_high_risk(ctx: Any) -> bool:
    """
    Check if drift risk is high.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if risk band is "high", False otherwise
    """
    report = get_p19_report(ctx)
    if report is None:
        return False
    return report.is_high_risk()


def has_semantic_drift(ctx: Any) -> bool:
    """
    Check if semantic drift pattern is detected.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if semantic_drift tag is present, False otherwise
    """
    report = get_p19_report(ctx)
    if report is None:
        return False
    return report.has_semantic_drift()


def has_cognitive_drift(ctx: Any) -> bool:
    """
    Check if cognitive drift pattern is detected.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if cognitive_drift tag is present, False otherwise
    """
    report = get_p19_report(ctx)
    if report is None:
        return False
    return report.has_cognitive_drift()


def has_temporal_instability(ctx: Any) -> bool:
    """
    Check if temporal instability pattern is detected.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if temporal_instability tag is present, False otherwise
    """
    report = get_p19_report(ctx)
    if report is None:
        return False
    return report.has_temporal_instability()


def get_p19_version() -> str:
    """
    Get the current P19 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P19_VERSION


def _update_coherence_state(ctx: Any, report: P19DriftFusionReport) -> None:
    """
    Update coherence_state with P19 metrics.

    This stores the current drift fusion values in the coherence state
    for observability and history tracking.

    NOTE: This only updates observation fields. P19 is observation-only
    and does NOT modify any scoring or behavior fields.

    Args:
        ctx: PipelineContext with coherence_state
        report: The P19 report to store
    """
    coherence_state = getattr(ctx, "coherence_state", None)
    if coherence_state is None:
        return

    # Update current values (observation only)
    if hasattr(coherence_state, "drift_fusion_index"):
        coherence_state.drift_fusion_index = report.drift_fusion_index

    if hasattr(coherence_state, "drift_risk_band"):
        coherence_state.drift_risk_band = report.drift_risk_band

    if hasattr(coherence_state, "drift_pattern_tags"):
        coherence_state.drift_pattern_tags = list(report.drift_pattern_tags)

    # Update histories
    if hasattr(coherence_state, "drift_fusion_index_history"):
        coherence_state.drift_fusion_index_history.append(report.drift_fusion_index)

    if hasattr(coherence_state, "drift_risk_band_history"):
        coherence_state.drift_risk_band_history.append(report.drift_risk_band)

    if hasattr(coherence_state, "drift_pattern_tags_history"):
        coherence_state.drift_pattern_tags_history.append(list(report.drift_pattern_tags))


# Public exports
__all__ = [
    # Singleton
    "get_p19_resolver",
    # Integration
    "maybe_run_p19",
    "run_p19_directly",
    # Helpers
    "is_p19_disabled",
    "has_p19_report",
    "get_p19_report",
    "get_drift_fusion_index",
    "get_drift_risk_band",
    "get_drift_pattern_tags",
    "is_low_risk",
    "is_moderate_risk",
    "is_high_risk",
    "has_semantic_drift",
    "has_cognitive_drift",
    "has_temporal_instability",
    "get_p19_version",
]
