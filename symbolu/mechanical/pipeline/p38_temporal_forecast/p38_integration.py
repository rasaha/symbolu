"""
P38 - Temporal Coherence Forecasting Pipeline Integration

Integration functions for running P38 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu.mechanical.pipeline.p38_temporal_forecast import maybe_run_p38

    # In pipeline after P18, P19:
    maybe_run_p38(ctx)

    # Access forecast:
    if ctx.p38 is not None:
        print(f"Forecast score: {ctx.p38.forecast_score}")
        print(f"Trend: {ctx.p38.forecast_trend}")

CRITICAL CONSTRAINTS:
    - Must NOT change regime, discourse, semantics, or lexical selection
    - Must NOT influence DHA, Persona Engine, Renderer
    - Must NOT influence insight gating (P32)
    - Must NOT infer intent or emotion
    - Must NOT gate actions or trigger side effects

INVARIANTS:
    - INV-P38-1: Forecast never influences current decisions
    - INV-P38-2: Forecast never escalates authority
    - INV-P38-3: Observer-only behavior enforced
    - INV-P38-4: Deterministic math only
    - INV-P38-5: No acoustic dependency
    - INV-P38-6: Monotonic safety (forecast does not amplify instability)
"""

from __future__ import annotations

from typing import Any, List, Optional

from symbolu.mechanical.pipeline.p38_temporal_forecast.p38_schema import (
    Phase38TemporalForecast,
    P38_VERSION,
    create_empty_forecast,
)
from symbolu.mechanical.pipeline.p38_temporal_forecast.p38_resolver import (
    resolve_forecast,
)


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_current_quality(ctx: Any) -> Optional[float]:
    """
    Extract current coherence quality (phase12_quality) from context.

    Reads from:
    - ctx.coherence_state.coherence_v3_quality (primary)
    - ctx.phase12_quality (fallback)

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Current quality in [0.0, 1.0], or None if unavailable
    """
    # Try coherence_state first
    if hasattr(ctx, "coherence_state") and ctx.coherence_state is not None:
        quality = getattr(ctx.coherence_state, "coherence_v3_quality", None)
        if quality is not None:
            return float(quality)

    # Try direct attribute
    if hasattr(ctx, "phase12_quality"):
        quality = getattr(ctx, "phase12_quality", None)
        if quality is not None:
            return float(quality)

    return None


def _extract_coherence_history(ctx: Any) -> List[float]:
    """
    Extract coherence history from context.

    Reads from:
    - ctx.coherence_history (list of past coherence snapshots)
    - ctx.coherence_state.coherence_v3_quality_history (fallback)

    Returns coherence scores as a flat list of floats.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        List of coherence scores (empty if unavailable)
    """
    history: List[float] = []

    # Try ctx.coherence_history first
    if hasattr(ctx, "coherence_history"):
        raw_history = getattr(ctx, "coherence_history", None)
        if raw_history is not None:
            for item in raw_history:
                # Handle dict-like snapshots
                if isinstance(item, dict):
                    score = item.get("coherence_v3_quality") or item.get("quality")
                    if score is not None:
                        history.append(float(score))
                # Handle object snapshots
                elif hasattr(item, "coherence_v3_quality"):
                    score = getattr(item, "coherence_v3_quality", None)
                    if score is not None:
                        history.append(float(score))
                # Handle direct float values
                elif isinstance(item, (int, float)):
                    history.append(float(item))

    # Fallback to coherence_state history
    if not history and hasattr(ctx, "coherence_state") and ctx.coherence_state is not None:
        cs = ctx.coherence_state
        if hasattr(cs, "coherence_v3_quality_history"):
            raw_history = getattr(cs, "coherence_v3_quality_history", None)
            if raw_history:
                history = [float(v) for v in raw_history if v is not None]

    return history


def _extract_drift_fusion_index(ctx: Any) -> Optional[float]:
    """
    Extract P19 drift fusion index from context.

    Reads from:
    - ctx.phase19_drift_fusion_index (per spec)
    - ctx.p19.drift_fusion_index (fallback)
    - ctx.coherence_state.drift_fusion_index (fallback)

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Drift fusion index in [0.0, 1.0], or None if unavailable
    """
    # Try direct attribute per spec
    if hasattr(ctx, "phase19_drift_fusion_index"):
        dfi = getattr(ctx, "phase19_drift_fusion_index", None)
        if dfi is not None:
            return float(dfi)

    # Try ctx.p19
    if hasattr(ctx, "p19") and ctx.p19 is not None:
        dfi = getattr(ctx.p19, "drift_fusion_index", None)
        if dfi is not None:
            return float(dfi)

    # Fallback to coherence_state
    if hasattr(ctx, "coherence_state") and ctx.coherence_state is not None:
        dfi = getattr(ctx.coherence_state, "drift_fusion_index", None)
        if dfi is not None:
            return float(dfi)

    return None


def _extract_temporal_entropy_diff(ctx: Any) -> Optional[float]:
    """
    Extract P18 temporal entropy diff from context.

    Reads from:
    - ctx.phase18_temporal_entropy_diff (per spec)
    - ctx.p18.delta_entropy (fallback, normalized to [0.0, 1.0])

    Note: P18 delta_entropy is in [-1.0, 1.0], so we normalize to [0.0, 1.0]:
        normalized = (delta_entropy + 1.0) / 2.0

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Temporal entropy diff in [0.0, 1.0], or None if unavailable
    """
    # Try direct attribute per spec
    if hasattr(ctx, "phase18_temporal_entropy_diff"):
        ted = getattr(ctx, "phase18_temporal_entropy_diff", None)
        if ted is not None:
            return float(ted)

    # Try ctx.p18
    if hasattr(ctx, "p18") and ctx.p18 is not None:
        delta = getattr(ctx.p18, "delta_entropy", None)
        if delta is not None:
            # Normalize from [-1, 1] to [0, 1]
            normalized = (float(delta) + 1.0) / 2.0
            return max(0.0, min(1.0, normalized))

    return None


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p38(ctx: Any) -> Optional[Phase38TemporalForecast]:
    """
    Run P38 temporal coherence forecasting if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P38 should run
    2. Extracts input signals from context
    3. Runs the forecast computation
    4. Attaches the report to ctx.p38

    P38 is designed to run after P18 (temporal entropy) and P19 (drift fusion).
    It reads from coherence history for trend analysis.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The Phase38TemporalForecast if run, None if skipped
    """
    # Check if P38 is disabled on this context
    if is_p38_disabled(ctx):
        return None

    # Extract input signals
    current_quality = _extract_current_quality(ctx)
    coherence_history = _extract_coherence_history(ctx)
    drift_fusion_index = _extract_drift_fusion_index(ctx)
    temporal_entropy_diff = _extract_temporal_entropy_diff(ctx)

    # Current quality is mandatory - skip if unavailable
    if current_quality is None:
        return None

    # Run the resolver
    forecast = resolve_forecast(
        current_quality=current_quality,
        coherence_history=coherence_history,
        drift_fusion_index=drift_fusion_index,
        temporal_entropy_diff=temporal_entropy_diff,
    )

    if forecast is None:
        return None

    # Attach to context (observer-only append)
    _attach_forecast_to_context(ctx, forecast)

    return forecast


def run_p38_directly(
    current_quality: Optional[float] = None,
    coherence_history: Optional[List[float]] = None,
    drift_fusion_index: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
) -> Optional[Phase38TemporalForecast]:
    """
    Run P38 directly with explicit inputs (for testing).

    This bypasses context extraction and allows direct testing
    with mock values.

    Args:
        current_quality: P12 coherence_v3_quality [0.0, 1.0]
        coherence_history: List of past coherence scores
        drift_fusion_index: P19 drift_fusion_index [0.0, 1.0]
        temporal_entropy_diff: P18 temporal entropy diff [0.0, 1.0]

    Returns:
        Phase38TemporalForecast if current_quality provided, None otherwise
    """
    return resolve_forecast(
        current_quality=current_quality,
        coherence_history=coherence_history,
        drift_fusion_index=drift_fusion_index,
        temporal_entropy_diff=temporal_entropy_diff,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p38_disabled(ctx: Any) -> bool:
    """
    Check if P38 is disabled on this context.

    P38 can be disabled by setting ctx._p38_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P38 is disabled, False otherwise
    """
    return getattr(ctx, "_p38_disabled", False)


def has_p38_forecast(ctx: Any) -> bool:
    """
    Check if context has a P38 forecast attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p38 is set and not None
    """
    return getattr(ctx, "p38", None) is not None


def get_p38_forecast(ctx: Any) -> Optional[Phase38TemporalForecast]:
    """
    Get the P38 forecast from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The Phase38TemporalForecast if present, None otherwise
    """
    return getattr(ctx, "p38", None)


def get_forecast_score(ctx: Any) -> float:
    """
    Get the forecast score from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Forecast score in [0.0, 1.0], or 0.5 if no forecast
    """
    forecast = get_p38_forecast(ctx)
    if forecast is None:
        return 0.5
    return forecast.forecast_score


def get_forecast_trend(ctx: Any) -> str:
    """
    Get the forecast trend from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Trend string ("improving", "stable", "declining"), or "stable" if no forecast
    """
    forecast = get_p38_forecast(ctx)
    if forecast is None:
        return "stable"
    return forecast.forecast_trend


def get_forecast_confidence(ctx: Any) -> float:
    """
    Get the forecast confidence from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Confidence in [0.0, 1.0], or 0.0 if no forecast
    """
    forecast = get_p38_forecast(ctx)
    if forecast is None:
        return 0.0
    return forecast.confidence


def is_forecast_improving(ctx: Any) -> bool:
    """
    Check if forecast trend is improving.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if trend is "improving", False otherwise
    """
    forecast = get_p38_forecast(ctx)
    if forecast is None:
        return False
    return forecast.is_improving()


def is_forecast_stable(ctx: Any) -> bool:
    """
    Check if forecast trend is stable.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if trend is "stable" or no forecast
    """
    forecast = get_p38_forecast(ctx)
    if forecast is None:
        return True  # Default to stable
    return forecast.is_stable()


def is_forecast_declining(ctx: Any) -> bool:
    """
    Check if forecast trend is declining.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if trend is "declining", False otherwise
    """
    forecast = get_p38_forecast(ctx)
    if forecast is None:
        return False
    return forecast.is_declining()


def get_p38_version() -> str:
    """
    Get the current P38 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P38_VERSION


def _attach_forecast_to_context(
    ctx: Any,
    forecast: Phase38TemporalForecast,
) -> None:
    """
    Attach the P38 forecast to context.

    This is observer-only: we only append to ctx.p38, we do NOT
    modify any other context fields or influence behavior.

    Args:
        ctx: PipelineContext
        forecast: The P38 forecast to attach
    """
    # Attach to p38 attribute
    if hasattr(ctx, "p38"):
        ctx.p38 = forecast
    else:
        try:
            setattr(ctx, "p38", forecast)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p38",
    "run_p38_directly",
    # Helpers
    "is_p38_disabled",
    "has_p38_forecast",
    "get_p38_forecast",
    "get_forecast_score",
    "get_forecast_trend",
    "get_forecast_confidence",
    "is_forecast_improving",
    "is_forecast_stable",
    "is_forecast_declining",
    "get_p38_version",
]
