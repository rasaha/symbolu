"""
P39 - Multi-Horizon Temporal Forecasting Pipeline Integration

Integration functions for running P39 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu_core.mechanical.pipeline.p39_multi_horizon import maybe_run_p39

    # In pipeline after P38:
    maybe_run_p39(ctx)

    # Access forecast:
    if ctx.p39_multi_horizon is not None:
        print(f"Short: {ctx.p39_multi_horizon.short_term_score}")
        print(f"Medium: {ctx.p39_multi_horizon.medium_term_score}")
        print(f"Long: {ctx.p39_multi_horizon.long_term_score}")

CRITICAL CONSTRAINTS:
    - Must NOT change regime, discourse, semantics, or lexical selection
    - Must NOT influence DHA, Persona Engine, Renderer
    - Must NOT influence insight gating (P32)
    - Must NOT infer intent or emotion
    - Must NOT gate actions or trigger side effects

INVARIANTS:
    - INV-P39-1: Observer-only (no influence on any authoritative phase)
    - INV-P39-2: Deterministic (same inputs -> same outputs)
    - INV-P39-3: Horizon monotonicity (flag if long_term > short_term)
    - INV-P39-4: No horizon can exceed Phase 38 base forecast
    - INV-P39-5: Absence-safe (missing inputs degrade confidence, never inflate)
"""

from __future__ import annotations

from typing import Any, Optional

from symbolu_core.mechanical.pipeline.p39_multi_horizon.p39_schema import (
    MultiHorizonForecast,
    P39_VERSION,
)
from symbolu_core.mechanical.pipeline.p39_multi_horizon.p39_resolver import (
    resolve_multi_horizon,
)


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_p38_forecast_score(ctx: Any) -> Optional[float]:
    """
    Extract Phase 38 forecast score from context.

    Reads from:
    - ctx.p38.forecast_score (primary)

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        P38 forecast score in [0.0, 1.0], or None if unavailable
    """
    if hasattr(ctx, "p38") and ctx.p38 is not None:
        score = getattr(ctx.p38, "forecast_score", None)
        if score is not None:
            return float(score)
    return None


def _extract_drift_fusion_index(ctx: Any) -> Optional[float]:
    """
    Extract P19 drift fusion index from context.

    Reads from:
    - ctx.p19.drift_fusion_index (primary)
    - ctx.phase19_drift_fusion_index (fallback)

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Drift fusion index in [0.0, 1.0], or None if unavailable
    """
    # Try ctx.p19 first
    if hasattr(ctx, "p19") and ctx.p19 is not None:
        dfi = getattr(ctx.p19, "drift_fusion_index", None)
        if dfi is not None:
            return float(dfi)

    # Try direct attribute
    if hasattr(ctx, "phase19_drift_fusion_index"):
        dfi = getattr(ctx, "phase19_drift_fusion_index", None)
        if dfi is not None:
            return float(dfi)

    return None


def _extract_entropy_volatility(ctx: Any) -> Optional[float]:
    """
    Extract P18 entropy volatility from context.

    Reads from:
    - ctx.p18.volatility_band (converted to numeric)
    - ctx.p18.entropy_now as fallback indicator

    The volatility is mapped:
        - LOW -> 0.2
        - MED -> 0.5
        - HIGH -> 0.8
        - UNKNOWN -> None (use default)

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Entropy volatility in [0.0, 1.0], or None if unavailable
    """
    if hasattr(ctx, "p18") and ctx.p18 is not None:
        # Try volatility_band first
        band = getattr(ctx.p18, "volatility_band", None)
        if band is not None:
            # Handle enum or string
            band_value = band.value if hasattr(band, "value") else str(band)
            volatility_map = {
                "LOW": 0.2,
                "MED": 0.5,
                "HIGH": 0.8,
            }
            if band_value in volatility_map:
                return volatility_map[band_value]

        # Fallback: use entropy_now as a proxy for volatility
        entropy_now = getattr(ctx.p18, "entropy_now", None)
        if entropy_now is not None:
            return float(entropy_now)

    return None


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p39(ctx: Any) -> Optional[MultiHorizonForecast]:
    """
    Run P39 multi-horizon forecasting if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P39 should run
    2. Extracts input signals from context
    3. Runs the multi-horizon computation
    4. Attaches the report to ctx.p39_multi_horizon

    P39 is designed to run after P38 (temporal forecast).
    It requires P38 forecast score to be present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The MultiHorizonForecast if run, None if skipped
    """
    # Check if P39 is disabled on this context
    if is_p39_disabled(ctx):
        return None

    # Extract input signals
    p38_forecast_score = _extract_p38_forecast_score(ctx)
    drift_fusion_index = _extract_drift_fusion_index(ctx)
    entropy_volatility = _extract_entropy_volatility(ctx)

    # P38 forecast score is mandatory - skip if unavailable
    if p38_forecast_score is None:
        return None

    # Run the resolver
    forecast = resolve_multi_horizon(
        p38_forecast_score=p38_forecast_score,
        drift_fusion_index=drift_fusion_index,
        entropy_volatility=entropy_volatility,
    )

    if forecast is None:
        return None

    # Attach to context (observer-only append)
    _attach_forecast_to_context(ctx, forecast)

    return forecast


def run_p39_directly(
    p38_forecast_score: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
    entropy_volatility: Optional[float] = None,
) -> Optional[MultiHorizonForecast]:
    """
    Run P39 directly with explicit inputs (for testing).

    This bypasses context extraction and allows direct testing
    with mock values.

    Args:
        p38_forecast_score: Phase 38 forecast score [0.0, 1.0]
        drift_fusion_index: P19 drift fusion index [0.0, 1.0]
        entropy_volatility: P18 entropy volatility [0.0, 1.0]

    Returns:
        MultiHorizonForecast if p38_forecast_score provided, None otherwise
    """
    return resolve_multi_horizon(
        p38_forecast_score=p38_forecast_score,
        drift_fusion_index=drift_fusion_index,
        entropy_volatility=entropy_volatility,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p39_disabled(ctx: Any) -> bool:
    """
    Check if P39 is disabled on this context.

    P39 can be disabled by setting ctx._p39_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P39 is disabled, False otherwise
    """
    return getattr(ctx, "_p39_disabled", False)


def has_p39_forecast(ctx: Any) -> bool:
    """
    Check if context has a P39 forecast attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p39_multi_horizon is set and not None
    """
    return getattr(ctx, "p39_multi_horizon", None) is not None


def get_p39_forecast(ctx: Any) -> Optional[MultiHorizonForecast]:
    """
    Get the P39 forecast from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The MultiHorizonForecast if present, None otherwise
    """
    return getattr(ctx, "p39_multi_horizon", None)


def get_short_term_score(ctx: Any) -> float:
    """
    Get the short-term score from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Short-term score in [0.0, 1.0], or 0.5 if no forecast
    """
    forecast = get_p39_forecast(ctx)
    if forecast is None:
        return 0.5
    return forecast.short_term_score


def get_medium_term_score(ctx: Any) -> float:
    """
    Get the medium-term score from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Medium-term score in [0.0, 1.0], or 0.5 if no forecast
    """
    forecast = get_p39_forecast(ctx)
    if forecast is None:
        return 0.5
    return forecast.medium_term_score


def get_long_term_score(ctx: Any) -> float:
    """
    Get the long-term score from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Long-term score in [0.0, 1.0], or 0.5 if no forecast
    """
    forecast = get_p39_forecast(ctx)
    if forecast is None:
        return 0.5
    return forecast.long_term_score


def get_horizon_divergence(ctx: Any) -> float:
    """
    Get the horizon divergence from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Divergence value >= 0.0, or 0.0 if no forecast
    """
    forecast = get_p39_forecast(ctx)
    if forecast is None:
        return 0.0
    return forecast.horizon_divergence


def is_any_horizon_volatile(ctx: Any) -> bool:
    """
    Check if any horizon is volatile.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if any horizon is volatile, False otherwise
    """
    forecast = get_p39_forecast(ctx)
    if forecast is None:
        return False
    return forecast.any_horizon_volatile()


def are_all_horizons_stable(ctx: Any) -> bool:
    """
    Check if all horizons are stable.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if all horizons stable, False otherwise (including no forecast)
    """
    forecast = get_p39_forecast(ctx)
    if forecast is None:
        return False
    return forecast.all_horizons_stable()


def get_p39_version() -> str:
    """
    Get the current P39 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P39_VERSION


def _attach_forecast_to_context(
    ctx: Any,
    forecast: MultiHorizonForecast,
) -> None:
    """
    Attach the P39 forecast to context.

    This is observer-only: we only append to ctx.p39_multi_horizon, we do NOT
    modify any other context fields or influence behavior.

    Args:
        ctx: PipelineContext
        forecast: The P39 forecast to attach
    """
    # Attach to p39_multi_horizon attribute
    if hasattr(ctx, "p39_multi_horizon"):
        ctx.p39_multi_horizon = forecast
    else:
        try:
            setattr(ctx, "p39_multi_horizon", forecast)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p39",
    "run_p39_directly",
    # Helpers
    "is_p39_disabled",
    "has_p39_forecast",
    "get_p39_forecast",
    "get_short_term_score",
    "get_medium_term_score",
    "get_long_term_score",
    "get_horizon_divergence",
    "is_any_horizon_volatile",
    "are_all_horizons_stable",
    "get_p39_version",
]
