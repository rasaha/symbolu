"""
P39 Resolver - Multi-Horizon Temporal Forecasting Logic

Implements the deterministic formulas for forecasting coherence stability
across multiple time horizons (short/medium/long).

FORMULAS:
    short_term  = Phase38.score
    medium_term = Phase38.score - ALPHA * drift_index
    long_term   = Phase38.score - BETA * drift_index - GAMMA * entropy_volatility

    Where:
        ALPHA = 0.15 (drift degradation for medium term)
        BETA  = 0.25 (drift degradation for long term)
        GAMMA = 0.15 (entropy volatility degradation for long term)

    All outputs clamped to [0.0, 1.0]

RISK BANDS:
    - score >= 0.75 -> "stable"
    - score >= 0.45 -> "strained"
    - score <  0.45 -> "volatile"

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs
    - Read-only: Does not modify any state
    - Observer-only: Never influences gating or behavior

INVARIANTS:
    - INV-P39-1: Observer-only (no influence on any authoritative phase)
    - INV-P39-2: Deterministic (same inputs -> same outputs)
    - INV-P39-3: Horizon monotonicity (flag if long_term > short_term)
    - INV-P39-4: No horizon can exceed Phase 38 base forecast
    - INV-P39-5: Absence-safe (missing inputs degrade confidence, never inflate)
"""

from typing import Optional

from symbolu_core.mechanical.pipeline.p39_multi_horizon.p39_schema import (
    MultiHorizonForecast,
    ALPHA,
    BETA,
    GAMMA,
    classify_band,
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


def compute_short_term(p38_score: float) -> float:
    """
    Compute short-term horizon score.

    Short-term = P38.score (no degradation)

    INV-P39-4: Result cannot exceed p38_score (trivially satisfied).

    Args:
        p38_score: Phase 38 forecast score [0.0, 1.0]

    Returns:
        Short-term score clamped to [0.0, 1.0]
    """
    return clamp(p38_score)


def compute_medium_term(p38_score: float, drift_index: float) -> float:
    """
    Compute medium-term horizon score.

    medium_term = P38.score - ALPHA * drift_index

    INV-P39-4: Result clamped to max of p38_score.
    INV-P39-5: If drift_index is high, score degrades (never inflates).

    Args:
        p38_score: Phase 38 forecast score [0.0, 1.0]
        drift_index: P19 drift fusion index [0.0, 1.0]

    Returns:
        Medium-term score clamped to [0.0, 1.0]
    """
    raw_score = p38_score - (ALPHA * drift_index)
    # INV-P39-4: Cannot exceed p38_score
    return clamp(raw_score, 0.0, p38_score)


def compute_long_term(
    p38_score: float,
    drift_index: float,
    entropy_volatility: float,
) -> float:
    """
    Compute long-term horizon score.

    long_term = P38.score - BETA * drift_index - GAMMA * entropy_volatility

    INV-P39-4: Result clamped to max of p38_score.
    INV-P39-5: Higher drift/volatility degrades score (never inflates).

    Args:
        p38_score: Phase 38 forecast score [0.0, 1.0]
        drift_index: P19 drift fusion index [0.0, 1.0]
        entropy_volatility: P18 entropy volatility [0.0, 1.0]

    Returns:
        Long-term score clamped to [0.0, 1.0]
    """
    raw_score = p38_score - (BETA * drift_index) - (GAMMA * entropy_volatility)
    # INV-P39-4: Cannot exceed p38_score
    return clamp(raw_score, 0.0, p38_score)


def compute_horizon_divergence(
    short_term: float,
    medium_term: float,
    long_term: float,
) -> float:
    """
    Compute the divergence between horizon scores.

    divergence = max(scores) - min(scores)

    Args:
        short_term: Short-term score
        medium_term: Medium-term score
        long_term: Long-term score

    Returns:
        Divergence value >= 0.0
    """
    scores = [short_term, medium_term, long_term]
    return max(scores) - min(scores)


def check_monotonicity_violation(short_term: float, long_term: float) -> bool:
    """
    Check if long-term score exceeds short-term score (monotonicity violation).

    INV-P39-3: If long_term > short_term, flag divergence but DO NOT correct it.

    Args:
        short_term: Short-term horizon score
        long_term: Long-term horizon score

    Returns:
        True if monotonicity is violated (long_term > short_term)
    """
    return long_term > short_term


def resolve_multi_horizon(
    p38_forecast_score: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
    entropy_volatility: Optional[float] = None,
) -> Optional[MultiHorizonForecast]:
    """
    Resolve the multi-horizon forecast from input signals.

    This is the main resolver function that:
    1. Validates mandatory input (p38_forecast_score)
    2. Applies conservative defaults for missing optional inputs (INV-P39-5)
    3. Computes all three horizon scores using locked formulas
    4. Classifies risk bands
    5. Computes divergence and checks monotonicity
    6. Returns immutable forecast report

    INV-P39-2: Deterministic - same inputs always produce same outputs.
    INV-P39-4: No horizon can exceed P38 base forecast.
    INV-P39-5: Missing inputs use conservative defaults (higher drift/volatility).

    Args:
        p38_forecast_score: Phase 38 forecast score [0.0, 1.0] (REQUIRED)
        drift_fusion_index: P19 drift fusion index [0.0, 1.0]
        entropy_volatility: P18 entropy volatility [0.0, 1.0]

    Returns:
        MultiHorizonForecast if computation possible, None if
        p38_forecast_score is None (mandatory input)
    """
    # P38 forecast score is mandatory
    if p38_forecast_score is None:
        return None

    # INV-P39-5: Apply conservative defaults for missing inputs
    # Missing drift_index defaults to moderate uncertainty (0.5)
    # Missing entropy_volatility defaults to moderate uncertainty (0.5)
    # This degrades confidence (medium/long scores lower), never inflates
    dfi = drift_fusion_index if drift_fusion_index is not None else 0.5
    ev = entropy_volatility if entropy_volatility is not None else 0.5

    # Compute horizon scores
    short_term = compute_short_term(p38_forecast_score)
    medium_term = compute_medium_term(p38_forecast_score, dfi)
    long_term = compute_long_term(p38_forecast_score, dfi, ev)

    # Classify bands
    short_band = classify_band(short_term)
    medium_band = classify_band(medium_term)
    long_band = classify_band(long_term)

    # Compute divergence
    divergence = compute_horizon_divergence(short_term, medium_term, long_term)

    # Check monotonicity (INV-P39-3)
    monotonicity_violated = check_monotonicity_violation(short_term, long_term)

    # Build debug info
    debug = {
        "formula_weights": {
            "alpha": ALPHA,
            "beta": BETA,
            "gamma": GAMMA,
        },
        "computed_values": {
            "raw_short_term": p38_forecast_score,
            "raw_medium_term": p38_forecast_score - (ALPHA * dfi),
            "raw_long_term": p38_forecast_score - (BETA * dfi) - (GAMMA * ev),
        },
        "defaults_applied": {
            "drift_fusion_index": drift_fusion_index is None,
            "entropy_volatility": entropy_volatility is None,
        },
    }

    return create_forecast(
        short_term_score=short_term,
        medium_term_score=medium_term,
        long_term_score=long_term,
        short_term_band=short_band,
        medium_term_band=medium_band,
        long_term_band=long_band,
        horizon_divergence=divergence,
        p38_forecast_score=p38_forecast_score,
        drift_fusion_index=drift_fusion_index,
        entropy_volatility=entropy_volatility,
        monotonicity_violated=monotonicity_violated,
        debug=debug,
    )


# Public exports
__all__ = [
    # Core functions
    "clamp",
    "compute_short_term",
    "compute_medium_term",
    "compute_long_term",
    "compute_horizon_divergence",
    "check_monotonicity_violation",
    "resolve_multi_horizon",
]
