"""
Symbol-U Predictive Intelligence Layer

This package contains predictive and forecasting modules that analyze
upstream signals to produce forecast signals about future state.

All modules in this package are:
- Observation-only (do not influence decisions)
- Deterministic (same inputs -> same outputs)
- Non-authoritative (produce forecasts, not decisions)

Submodules:
    - persona_drift: Phase 35 Predictive Persona Drift Model
"""

# Phase 35 exports
from agentic.core.predictive.persona_drift import (
    # Version
    P35_VERSION,
    # Dataclasses
    PredictivePersonaDriftReport,
    # Helpers
    create_report as create_p35_report,
    create_empty_report as create_empty_p35_report,
)

__all__ = [
    # Phase 35
    "P35_VERSION",
    "PredictivePersonaDriftReport",
    "create_p35_report",
    "create_empty_p35_report",
]
