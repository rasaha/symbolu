"""
P38 Resolver - Temporal Coherence Forecasting Logic

Implements the deterministic formula for forecasting near-future coherence
stability based on recent coherence history.

FORMULA:
    forecast_score =
        0.40 * current_quality +
        0.30 * mean(last_3_coherence_scores) +
        0.20 * (1 - drift_fusion_index) +
        0.10 * (1 - temporal_entropy_diff)

    Clamp result to [0.0, 1.0]

TREND RULES:
    - improving: forecast_score > current_quality + 0.05
    - declining: forecast_score < current_quality - 0.05
    - stable: otherwise

CONFIDENCE:
    - min(1.0, history_count / 5)

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs
    - Read-only: Does not modify any state
    - Observer-only: Never influences gating or behavior

INVARIANTS:
    - INV-P38-1: Forecast never influences current decisions
    - INV-P38-4: Deterministic math only
    - INV-P38-6: Monotonic safety
"""

from typing import List, Optional

from symbolu.mechanical.pipeline.p38_temporal_forecast.p38_schema import (
    Phase38TemporalForecast,
    ForecastTrend,
    W_CURRENT_QUALITY,
    W_HISTORY_MEAN,
    W_DRIFT_FUSION,
    W_TEMPORAL_ENTROPY,
    TREND_IMPROVING_THRESHOLD,
    TREND_DECLINING_THRESHOLD,
    CONFIDENCE_HISTORY_DIVISOR,
    create_forecast,
)


# =============================================================================
# Core Functions
# =============================================================================


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp a value to [min_val, max_val].

    Args:
        value: Value to clamp
        min_val: Minimum bound (default 0.0)
        max_val: Maximum bound (default 1.0)

    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))


def compute_history_mean(history: List[float], window: int = 3) -> float:
    """
    Compute mean of the last N history values.

    Args:
        history: List of coherence scores
        window: Number of recent values to use (default 3)

    Returns:
        Mean of last N values, or 0.5 if history is empty
    """
    if not history:
        return 0.5  # Neutral default

    # Take the last `window` values
    recent = history[-window:] if len(history) >= window else history
    return sum(recent) / len(recent)


def compute_forecast_score(
    current_quality: float,
    history_mean: float,
    drift_fusion_index: float,
    temporal_entropy_diff: float,
) -> float:
    """
    Compute the forecast score using the locked formula.

    Formula:
        forecast_score =
            0.40 * current_quality +
            0.30 * history_mean +
            0.20 * (1 - drift_fusion_index) +
            0.10 * (1 - temporal_entropy_diff)

    Args:
        current_quality: Current P12 coherence quality [0.0, 1.0]
        history_mean: Mean of last 3 coherence scores [0.0, 1.0]
        drift_fusion_index: P19 drift fusion index [0.0, 1.0]
        temporal_entropy_diff: P18 temporal entropy diff [0.0, 1.0]

    Returns:
        Forecast score clamped to [0.0, 1.0]
    """
    raw_score = (
        W_CURRENT_QUALITY * current_quality
        + W_HISTORY_MEAN * history_mean
        + W_DRIFT_FUSION * (1.0 - drift_fusion_index)
        + W_TEMPORAL_ENTROPY * (1.0 - temporal_entropy_diff)
    )
    return clamp(raw_score)


def classify_trend(
    forecast_score: float,
    current_quality: float,
) -> ForecastTrend:
    """
    Classify the forecast trend based on score comparison.

    Rules:
        - improving: forecast_score > current_quality + 0.05
        - declining: forecast_score < current_quality - 0.05
        - stable: otherwise

    Args:
        forecast_score: Computed forecast score
        current_quality: Current P12 quality

    Returns:
        Trend classification
    """
    if forecast_score > current_quality + TREND_IMPROVING_THRESHOLD:
        return "improving"
    elif forecast_score < current_quality - TREND_DECLINING_THRESHOLD:
        return "declining"
    else:
        return "stable"


def compute_confidence(history_count: int) -> float:
    """
    Compute confidence based on history availability.

    Formula:
        confidence = min(1.0, history_count / 5)

    Args:
        history_count: Number of history points available

    Returns:
        Confidence in [0.0, 1.0]
    """
    return min(1.0, history_count / CONFIDENCE_HISTORY_DIVISOR)


def resolve_forecast(
    current_quality: Optional[float] = None,
    coherence_history: Optional[List[float]] = None,
    drift_fusion_index: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
) -> Optional[Phase38TemporalForecast]:
    """
    Resolve the temporal coherence forecast from input signals.

    This is the main resolver function that:
    1. Validates inputs (returns None if insufficient)
    2. Applies neutral defaults for missing optional inputs
    3. Computes forecast score using locked formula
    4. Classifies trend
    5. Computes confidence
    6. Returns immutable forecast report

    Args:
        current_quality: P12 coherence_v3_quality [0.0, 1.0]
        coherence_history: List of past coherence scores
        drift_fusion_index: P19 drift_fusion_index [0.0, 1.0]
        temporal_entropy_diff: P18 delta_entropy normalized to [0.0, 1.0]

    Returns:
        Phase38TemporalForecast if computation possible, None if
        current_quality is None (mandatory input)
    """
    # Current quality is mandatory
    if current_quality is None:
        return None

    # Apply neutral defaults
    history = coherence_history or []
    dfi = drift_fusion_index if drift_fusion_index is not None else 0.0
    ted = temporal_entropy_diff if temporal_entropy_diff is not None else 0.5

    # Compute history mean
    history_mean = compute_history_mean(history, window=3)

    # Compute forecast score
    forecast_score = compute_forecast_score(
        current_quality=current_quality,
        history_mean=history_mean,
        drift_fusion_index=dfi,
        temporal_entropy_diff=ted,
    )

    # Classify trend
    forecast_trend = classify_trend(forecast_score, current_quality)

    # Compute confidence
    history_count = len(history)
    confidence = compute_confidence(history_count)

    # Build debug info
    debug = {
        "formula_weights": {
            "current_quality": W_CURRENT_QUALITY,
            "history_mean": W_HISTORY_MEAN,
            "drift_fusion": W_DRIFT_FUSION,
            "temporal_entropy": W_TEMPORAL_ENTROPY,
        },
        "computed_values": {
            "raw_current_contrib": W_CURRENT_QUALITY * current_quality,
            "raw_history_contrib": W_HISTORY_MEAN * history_mean,
            "raw_drift_contrib": W_DRIFT_FUSION * (1.0 - dfi),
            "raw_entropy_contrib": W_TEMPORAL_ENTROPY * (1.0 - ted),
        },
    }

    return create_forecast(
        forecast_score=forecast_score,
        forecast_trend=forecast_trend,
        confidence=confidence,
        current_quality=current_quality,
        history_mean=history_mean,
        drift_fusion_index=drift_fusion_index,
        temporal_entropy_diff=temporal_entropy_diff,
        history_count=history_count,
        debug=debug,
    )


# Public exports
__all__ = [
    # Core functions
    "clamp",
    "compute_history_mean",
    "compute_forecast_score",
    "classify_trend",
    "compute_confidence",
    "resolve_forecast",
]
