"""Empirical rolling-origin residual uncertainty (non-Gaussian, calibration-gated)."""

from __future__ import annotations

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.forecasting import (
    CanonicalCapacitySeries,
    ForecastHorizon,
    ForecastTarget,
    PersistenceForecaster,
    UncertaintyConfig,
    UncertaintyMethod,
    build_input_window,
    compute_uncertainty,
)
from ugence_cloud_scaling_controller.forecasting.uncertainty import (
    UncertaintyError,
    REASON_INSUFFICIENT_CALIBRATION,
    REASON_NOT_REQUESTED,
    rolling_origin_residuals,
)


def _window_1step(values):
    """Window at the last observation with a 60s (== cadence) horizon (one step ahead)."""
    states = fx.cpu_series_states(values, cadence_seconds=60.0)
    s = CanonicalCapacitySeries.build(states)
    return build_input_window(s, ForecastTarget.CPU_UTILIZATION,
                              states[-1].observed_at, ForecastHorizon(60.0))


def test_rolling_origin_residuals_are_empirical():
    w = _window_1step([0.0, 10.0, 5.0, 20.0, 15.0, 30.0])
    res = rolling_origin_residuals(
        w, PersistenceForecaster(), UncertaintyConfig(match_tolerance_seconds=5.0)
    )
    assert res == [10.0, -5.0, 15.0, -5.0, 15.0]


def test_interval_from_empirical_quantiles():
    w = _window_1step([0.0, 10.0, 5.0, 20.0, 15.0, 30.0])
    cfg = UncertaintyConfig(requested_coverage=0.8, min_calibration_samples=5,
                            match_tolerance_seconds=5.0)
    iv = compute_uncertainty(w, PersistenceForecaster(), point=30.0, config=cfg)
    assert iv.available is True
    assert iv.calibration_sample_count == 5
    assert iv.lower == 25.0   # 30 + q0.1(residuals) = 30 + (-5)
    assert iv.upper == 45.0   # 30 + q0.9(residuals) = 30 + 15
    assert iv.width == 20.0


def test_insufficient_calibration_is_typed_unavailable():
    w = _window_1step([0.0, 10.0, 5.0, 20.0, 15.0, 30.0])
    cfg = UncertaintyConfig(min_calibration_samples=6, match_tolerance_seconds=5.0)
    iv = compute_uncertainty(w, PersistenceForecaster(), point=30.0, config=cfg)
    assert iv.available is False
    assert iv.unavailable_reason == REASON_INSUFFICIENT_CALIBRATION
    assert iv.insufficient_calibration is True


def test_method_none_is_point_only_not_abstention():
    w = _window_1step([0.0, 10.0, 5.0, 20.0])
    cfg = UncertaintyConfig(method=UncertaintyMethod.NONE)
    iv = compute_uncertainty(w, PersistenceForecaster(), point=20.0, config=cfg)
    assert iv.available is False
    assert iv.unavailable_reason == REASON_NOT_REQUESTED
    assert iv.insufficient_calibration is False


def test_coverage_must_be_in_open_unit_interval():
    """`UncertaintyError`, not bare `Exception`. `pytest.raises(Exception)` asserts no
    contract at all — it passes for a `TypeError` from a refactor as readily as for the
    module's own refusal — and this statement is the sole killer of the coverage gate, so
    what it asserts is the whole of that guard's published evidence."""

    for bad in (0.0, 1.0):
        with pytest.raises(UncertaintyError):
            UncertaintyConfig(requested_coverage=bad)


def test_config_digest_reflects_coverage():
    a = UncertaintyConfig(requested_coverage=0.8).digest()
    b = UncertaintyConfig(requested_coverage=0.9).digest()
    assert a != b
