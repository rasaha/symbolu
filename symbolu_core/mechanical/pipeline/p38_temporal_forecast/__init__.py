"""
P38 - Temporal Coherence Forecasting

Phase 38 forecasts near-future coherence stability based on recent
coherence history. This is part of the predictive intelligence layer.

This phase is:
    - Read-only
    - Observer-only
    - Non-authoritative
    - Non-gating
    - Non-persona
    - Non-renderer

Usage:
    from symbolu_core.mechanical.pipeline.p38_temporal_forecast import maybe_run_p38

    # In pipeline after P18, P19:
    maybe_run_p38(ctx)

    # Access forecast:
    if ctx.p38 is not None:
        print(f"Forecast: {ctx.p38.forecast_score}")
        print(f"Trend: {ctx.p38.forecast_trend}")
        print(f"Confidence: {ctx.p38.confidence}")

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs
    - Read-only: Does not modify system behavior
    - Observer-only: Never used for gating or behavior modification

INVARIANTS:
    - INV-P38-1: Forecast never influences current decisions
    - INV-P38-2: Forecast never escalates authority
    - INV-P38-3: Observer-only behavior enforced
    - INV-P38-4: Deterministic math only
    - INV-P38-5: No acoustic dependency
    - INV-P38-6: Monotonic safety (forecast does not amplify instability)
"""

from symbolu_core.mechanical.pipeline.p38_temporal_forecast.p38_schema import (
    P38_VERSION,
    ForecastTrend,
    ForecastHorizon,
    W_CURRENT_QUALITY,
    W_HISTORY_MEAN,
    W_DRIFT_FUSION,
    W_TEMPORAL_ENTROPY,
    TREND_IMPROVING_THRESHOLD,
    TREND_DECLINING_THRESHOLD,
    CONFIDENCE_HISTORY_DIVISOR,
    Phase38TemporalForecast,
    create_forecast,
    create_empty_forecast,
)

from symbolu_core.mechanical.pipeline.p38_temporal_forecast.p38_resolver import (
    clamp,
    compute_history_mean,
    compute_forecast_score,
    classify_trend,
    compute_confidence,
    resolve_forecast,
)

from symbolu_core.mechanical.pipeline.p38_temporal_forecast.p38_integration import (
    maybe_run_p38,
    run_p38_directly,
    is_p38_disabled,
    has_p38_forecast,
    get_p38_forecast,
    get_forecast_score,
    get_forecast_trend,
    get_forecast_confidence,
    is_forecast_improving,
    is_forecast_stable,
    is_forecast_declining,
    get_p38_version,
)


__all__ = [
    # Version
    "P38_VERSION",
    # Type Aliases
    "ForecastTrend",
    "ForecastHorizon",
    # Constants
    "W_CURRENT_QUALITY",
    "W_HISTORY_MEAN",
    "W_DRIFT_FUSION",
    "W_TEMPORAL_ENTROPY",
    "TREND_IMPROVING_THRESHOLD",
    "TREND_DECLINING_THRESHOLD",
    "CONFIDENCE_HISTORY_DIVISOR",
    # Dataclasses
    "Phase38TemporalForecast",
    # Schema Helpers
    "create_forecast",
    "create_empty_forecast",
    # Resolver Functions
    "clamp",
    "compute_history_mean",
    "compute_forecast_score",
    "classify_trend",
    "compute_confidence",
    "resolve_forecast",
    # Integration
    "maybe_run_p38",
    "run_p38_directly",
    # Integration Helpers
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
