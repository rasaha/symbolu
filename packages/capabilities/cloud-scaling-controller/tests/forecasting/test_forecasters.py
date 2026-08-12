"""Baseline forecaster determinism, identity, and history requirements."""

from __future__ import annotations

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.forecasting import (
    CanonicalCapacitySeries,
    ForecastHorizon,
    ForecastTarget,
    LinearTrendForecaster,
    PersistenceForecaster,
    build_input_window,
)
from ugence_cloud_scaling_controller.forecasting.forecasters import ForecasterError


def _window(values, cutoff_idx=None, horizon_min=5):
    states = fx.cpu_series_states(values)
    s = CanonicalCapacitySeries.build(states)
    idx = len(values) - 1 if cutoff_idx is None else cutoff_idx
    return build_input_window(s, ForecastTarget.CPU_UTILIZATION, states[idx].observed_at,
                              ForecastHorizon.minutes(horizon_min))


def test_persistence_returns_last_value():
    w = _window([10.0, 20.0, 30.0])
    assert PersistenceForecaster().point_estimate(w) == 30.0


def test_persistence_is_deterministic():
    w = _window([5.0, 7.0, 9.0])
    f = PersistenceForecaster()
    assert f.point_estimate(w) == f.point_estimate(w)


def test_linear_trend_extrapolates_ramp():
    # value = 10*i at 60s cadence; slope = 10/60 per second; +5min(300s) => +50 from last.
    w = _window([0.0, 10.0, 20.0, 30.0])  # last=30 at t=180; forecast_for=180+300=480 => 80
    got = LinearTrendForecaster().point_estimate(w)
    assert abs(got - 80.0) < 1e-6


def test_linear_trend_requires_min_history():
    w = _window([10.0, 20.0])  # only 2 points, default min_history=3
    assert LinearTrendForecaster().point_estimate(w) is None
    # persistence needs only 1
    assert PersistenceForecaster().point_estimate(w) == 20.0


def test_linear_trend_min_history_config_validated():
    with pytest.raises(ForecasterError):
        LinearTrendForecaster({"min_history": 1})


def test_config_digest_reflects_config():
    a = LinearTrendForecaster({"min_history": 3}).config_digest()
    b = LinearTrendForecaster({"min_history": 4}).config_digest()
    assert a != b
    assert a == LinearTrendForecaster({"min_history": 3}).config_digest()


def test_model_identity_present():
    assert PersistenceForecaster().model_id == "persistence"
    assert LinearTrendForecaster().model_id == "linear_trend"
    assert PersistenceForecaster().model_version
    assert LinearTrendForecaster().model_version


def test_forecasters_support_all_controller_targets_and_positive_horizons():
    f = PersistenceForecaster()
    for t in ForecastTarget:
        assert f.supports_target(t)
    assert f.supports_horizon(ForecastHorizon.minutes(60))
