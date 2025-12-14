"""
Phase 35 - Predictive Persona Drift Model

Core module for predicting persona drift based on upstream signals.

This module provides:
- PredictivePersonaDriftReport: Immutable report dataclass
- Formula computation for drift scoring
- Trend analysis for direction classification

INVARIANTS:
    - INV-P35-1: Forecast never influences current decisions
    - INV-P35-2: Prediction never escalates authority
    - INV-P35-3: Observer-only behavior enforced
    - INV-P35-4: Deterministic math only
    - INV-P35-5: No acoustic dependency

Usage:
    from symbolu.core.predictive.persona_drift import (
        PredictivePersonaDriftReport,
        create_report,
        compute_base_drift_score,
        classify_trend_direction,
    )
"""

from symbolu.core.predictive.persona_drift.drift_report import (
    # Version
    P35_VERSION,
    # Enums
    DriftRiskBand,
    TrendDirection,
    ForecastHorizon,
    # Constants
    ALLOWED_CONTRIBUTING_FACTORS,
    W_DRIFT_FUSION_INDEX,
    W_SCHEMA_DRIFT,
    W_TEMPORAL_ENTROPY_DIFF,
    W_COHERENCE_QUALITY,
    W_UCF_SCORE,
    RISK_BAND_LOW_THRESHOLD,
    RISK_BAND_HIGH_THRESHOLD,
    TREND_CHANGE_THRESHOLD,
    TREND_MIN_SIGNALS,
    SCHEMA_INSTABILITY_THRESHOLD,
    TEMPORAL_ENTROPY_THRESHOLD,
    COHERENCE_DECAY_THRESHOLD,
    IDENTITY_HARMONICS_THRESHOLD,
    CROSS_SIGNAL_VOLATILITY_THRESHOLD,
    # Dataclasses
    PredictivePersonaDriftReport,
    # Helpers
    create_report,
    risk_band_from_score,
    create_empty_report,
)

from symbolu.core.predictive.persona_drift.drift_formula import (
    clamp,
    compute_base_drift_score,
    compute_variance,
    compute_confidence,
    compute_contributing_factors,
    compute_signal_variance,
)

from symbolu.core.predictive.persona_drift.drift_trend_analyzer import (
    SignalSnapshot,
    compute_signal_deltas,
    classify_trend_direction,
    analyze_trend_from_histories,
)


# Public exports
__all__ = [
    # Version
    "P35_VERSION",
    # Enums
    "DriftRiskBand",
    "TrendDirection",
    "ForecastHorizon",
    # Constants
    "ALLOWED_CONTRIBUTING_FACTORS",
    "W_DRIFT_FUSION_INDEX",
    "W_SCHEMA_DRIFT",
    "W_TEMPORAL_ENTROPY_DIFF",
    "W_COHERENCE_QUALITY",
    "W_UCF_SCORE",
    "RISK_BAND_LOW_THRESHOLD",
    "RISK_BAND_HIGH_THRESHOLD",
    "TREND_CHANGE_THRESHOLD",
    "TREND_MIN_SIGNALS",
    "SCHEMA_INSTABILITY_THRESHOLD",
    "TEMPORAL_ENTROPY_THRESHOLD",
    "COHERENCE_DECAY_THRESHOLD",
    "IDENTITY_HARMONICS_THRESHOLD",
    "CROSS_SIGNAL_VOLATILITY_THRESHOLD",
    # Dataclasses
    "PredictivePersonaDriftReport",
    # Report Helpers
    "create_report",
    "risk_band_from_score",
    "create_empty_report",
    # Formula Functions
    "clamp",
    "compute_base_drift_score",
    "compute_variance",
    "compute_confidence",
    "compute_contributing_factors",
    "compute_signal_variance",
    # Trend Analysis
    "SignalSnapshot",
    "compute_signal_deltas",
    "classify_trend_direction",
    "analyze_trend_from_histories",
]
