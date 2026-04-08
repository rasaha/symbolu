"""
P35 - Predictive Persona Drift Pipeline Integration

Pipeline integration module for Phase 35 predictive persona drift.

This module provides:
- maybe_run_p35: Main pipeline entry point
- run_p35_directly: Testing entry point
- Helper functions for downstream access

Usage:
    from symbolu_core.mechanical.pipeline.p35_predictive_persona_drift import (
        maybe_run_p35,
        get_p35_report,
        get_predicted_drift_score,
    )

    # In pipeline after P19, P33, P34:
    maybe_run_p35(ctx)

    # Access report:
    if ctx.p35 is not None:
        print(f"Predicted drift: {ctx.p35.predicted_drift_score}")
        print(f"Risk band: {ctx.p35.drift_risk_band}")
"""

from symbolu_core.mechanical.pipeline.p35_predictive_persona_drift.p35_integration import (
    # Singleton
    get_p35_resolver,
    # Integration
    maybe_run_p35,
    run_p35_directly,
    # Helpers
    is_p35_disabled,
    has_p35_report,
    get_p35_report,
    get_predicted_drift_score,
    get_drift_risk_band,
    get_trend_direction,
    get_contributing_factors,
    get_confidence,
    is_low_risk,
    is_moderate_risk,
    is_high_risk,
    is_stable,
    is_worsening,
    is_improving,
    get_p35_version,
)

# Re-export from core module
from agentic.core.predictive.persona_drift import (
    P35_VERSION,
    PredictivePersonaDriftReport,
    DriftRiskBand,
    TrendDirection,
    ForecastHorizon,
    create_report,
    create_empty_report,
    risk_band_from_score,
)

__all__ = [
    # Version
    "P35_VERSION",
    # Enums
    "DriftRiskBand",
    "TrendDirection",
    "ForecastHorizon",
    # Dataclasses
    "PredictivePersonaDriftReport",
    # Core helpers
    "create_report",
    "create_empty_report",
    "risk_band_from_score",
    # Singleton
    "get_p35_resolver",
    # Integration
    "maybe_run_p35",
    "run_p35_directly",
    # Helpers
    "is_p35_disabled",
    "has_p35_report",
    "get_p35_report",
    "get_predicted_drift_score",
    "get_drift_risk_band",
    "get_trend_direction",
    "get_contributing_factors",
    "get_confidence",
    "is_low_risk",
    "is_moderate_risk",
    "is_high_risk",
    "is_stable",
    "is_worsening",
    "is_improving",
    "get_p35_version",
]
