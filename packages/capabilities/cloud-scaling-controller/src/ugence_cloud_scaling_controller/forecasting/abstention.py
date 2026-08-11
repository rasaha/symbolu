"""Typed abstention reasons for shadow capacity forecasting.

An abstention is a *first-class, evidence-producing* Phase-2 output: when the input
history is unreliable the layer declines to forecast rather than manufacture a
plausible-looking prediction. Every reason here is a stable, machine-readable enum value
so downstream readers and evaluation can aggregate abstentions by cause.

These reasons name why a forecast was *not* produced. They are descriptive capacity
intelligence only — never a risk verdict, an authorization, or an execution signal.
"""

from __future__ import annotations

from enum import Enum

FORECAST_STATUS_FORECAST = "forecast"
FORECAST_STATUS_ABSTAINED = "abstained"


class AbstentionReason(str, Enum):
    """Stable, typed reasons a forecaster declines to produce a point estimate."""

    INSUFFICIENT_HISTORY = "insufficient_history"
    STALE_HISTORY = "stale_history"
    EXCESSIVE_MISSINGNESS = "excessive_missingness"
    SUBJECT_MISMATCH = "subject_mismatch"
    TENANT_SCOPE_MISMATCH = "tenant_scope_mismatch"
    INVALID_TIME_ORDER = "invalid_time_order"
    CONFLICTING_DUPLICATE = "conflicting_duplicate"
    UNSUPPORTED_TARGET = "unsupported_target"
    UNSUPPORTED_HORIZON = "unsupported_horizon"
    IRREGULAR_CADENCE = "irregular_cadence"
    MISSING_NORMALIZATION_POLICY = "missing_normalization_policy"
    INVALID_MEASUREMENT = "invalid_measurement"
    INCONSISTENT_UNIT = "inconsistent_unit"
    INSUFFICIENT_CALIBRATION_HISTORY = "insufficient_calibration_history"
    FORECAST_OUTSIDE_DOMAIN = "forecast_outside_domain"


__all__ = [
    "FORECAST_STATUS_FORECAST",
    "FORECAST_STATUS_ABSTAINED",
    "AbstentionReason",
]
