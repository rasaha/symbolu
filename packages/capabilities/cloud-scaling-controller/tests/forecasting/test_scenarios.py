"""Deterministic demand-shape scenarios and remaining edge cases.

These verify Phase-2 CONTRACTS and INVARIANTS on synthetic fixtures. They deliberately do
NOT assert production forecast accuracy — a low error on a synthetic ramp is a property of
the fixture, not evidence of real-world predictive quality.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState, CapacityState, InfrastructureState, Measurement, Unit,
)
from ugence_cloud_scaling_controller.forecasting import (
    AbstentionReason,
    CanonicalCapacitySeries,
    EvaluationStatus,
    ForecastHorizon,
    ForecastTarget,
    LinearTrendForecaster,
    PersistenceForecaster,
    UncertaintyConfig,
    UncertaintyMethod,
    evaluate_forecast,
    forecast_with_evidence,
    run_replay_evaluation,
)

H1 = ForecastHorizon(60.0)
NPOL = fx.cpu_norm_policy()
UCFG = UncertaintyConfig(min_calibration_samples=3, match_tolerance_seconds=5.0)


def _replay(values, forecaster):
    obs = fx.cpu_series_states(values, cadence_seconds=60.0)
    return run_replay_evaluation(
        obs, ForecastTarget.CPU_UTILIZATION, H1, forecaster,
        normalization_policy=NPOL, uncertainty_config=UCFG, match_tolerance_seconds=5.0,
    )


# ---- demand shapes ---------------------------------------------------------------

def test_stable_demand():
    res = _replay([50.0] * 10, PersistenceForecaster())
    # Persistence on flat demand: every matched forecast is exact.
    for r in res.records:
        if r.status is EvaluationStatus.EVALUATED:
            assert r.absolute_error == 0.0


def test_gradual_increase_linear_trend_tracks_ramp():
    res = _replay([float(4 * i) for i in range(12)], LinearTrendForecaster())  # 0..44%
    evaluated = [r for r in res.records if r.status is EvaluationStatus.EVALUATED]
    assert evaluated  # some matched
    for r in evaluated:
        assert r.absolute_error < 1e-6  # fixture is exactly linear


def test_gradual_decrease_stays_in_domain():
    res = _replay([100.0 - 5 * i for i in range(15)], PersistenceForecaster())
    assert res.aggregate.record_count == 15
    # No forecast should be a domain violation on a gentle decrease within [0,100].
    for r in res.records:
        assert r.status is not EvaluationStatus.ABSTAINED or \
            r.reason != AbstentionReason.FORECAST_OUTSIDE_DOMAIN.value


def test_sudden_spike_is_forecast_or_abstained_never_crashes():
    values = [20.0] * 6 + [95.0] + [20.0] * 6
    res = _replay(values, PersistenceForecaster())
    assert res.aggregate.forecast_count + res.aggregate.abstention_count == res.aggregate.record_count


def test_sudden_recovery():
    values = [90.0] * 6 + [10.0] * 6
    res = _replay(values, PersistenceForecaster())
    assert res.aggregate.record_count == 12


def test_missing_observations_reduce_samples_without_imputation():
    states = []
    for i, v in enumerate([10.0, None, 30.0, None, 50.0, 60.0, 70.0]):
        states.append(fx.cpu_state(fx.at(60 * i), v))
    s = CanonicalCapacitySeries.build(states)
    from ugence_cloud_scaling_controller.forecasting import build_input_window
    w = build_input_window(s, ForecastTarget.CPU_UTILIZATION, fx.at(360), H1)
    assert w.missingness.missing_count == 2
    assert w.sample_count == 5


def test_long_gap_flagged_as_irregular_cadence():
    states = [fx.cpu_state(fx.at(0), 10.0), fx.cpu_state(fx.at(60), 20.0),
              fx.cpu_state(fx.at(3660), 30.0)]  # ~1h gap
    s = CanonicalCapacitySeries.build(states)
    ev = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, fx.at(3660), H1,
                                PersistenceForecaster(), normalization_policy=NPOL,
                                uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE))
    assert ev.forecast.abstention_reason is AbstentionReason.IRREGULAR_CADENCE


# ---- structural edge cases -------------------------------------------------------

def test_unit_mismatch_abstains():
    subj = fx.subject()
    states = [
        CanonicalCapacityState(subject=subj, observed_at=fx.at(0),
                               infrastructure=InfrastructureState(cpu_utilization=Measurement(50.0, Unit.PERCENT)),
                               capacity=CapacityState(running_replicas=3)),
        CanonicalCapacityState(subject=subj, observed_at=fx.at(60),
                               infrastructure=InfrastructureState(cpu_utilization=Measurement(0.6, Unit.RATIO)),
                               capacity=CapacityState(running_replicas=3)),
        CanonicalCapacityState(subject=subj, observed_at=fx.at(120),
                               infrastructure=InfrastructureState(cpu_utilization=Measurement(55.0, Unit.PERCENT)),
                               capacity=CapacityState(running_replicas=3)),
    ]
    s = CanonicalCapacitySeries.build(states)
    ev = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, fx.at(120), H1,
                                PersistenceForecaster(), normalization_policy=NPOL,
                                uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE))
    assert ev.forecast.abstention_reason is AbstentionReason.INCONSISTENT_UNIT


def test_exact_horizon_boundary_matches():
    s = CanonicalCapacitySeries.build(fx.cpu_series_states([10.0, 20.0, 30.0]))
    ev = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, H1,
                                PersistenceForecaster(), normalization_policy=NPOL,
                                uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE))
    exact = fx.cpu_state(ev.forecast.forecast_for, 33.0)  # delta = 0
    rec = evaluate_forecast(ev, exact, match_tolerance_seconds=0.0)
    assert rec.status is EvaluationStatus.EVALUATED
    assert rec.match_delta_seconds == 0.0


def test_actual_just_outside_tolerance_is_unmatched():
    s = CanonicalCapacitySeries.build(fx.cpu_series_states([10.0, 20.0, 30.0]))
    ev = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, H1,
                                PersistenceForecaster(), normalization_policy=NPOL,
                                uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE))
    just_out = fx.cpu_state(ev.forecast.forecast_for + timedelta(seconds=6), 33.0)
    rec = evaluate_forecast(ev, just_out, match_tolerance_seconds=5.0)
    assert rec.status is EvaluationStatus.UNMATCHED
    assert rec.reason == "actual_outside_tolerance"


def test_insufficient_history_scenario():
    s = CanonicalCapacitySeries.build(fx.cpu_series_states([10.0, 20.0]))
    ev = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, H1,
                                LinearTrendForecaster(), normalization_policy=NPOL,
                                uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE))
    assert ev.forecast.abstention_reason is AbstentionReason.INSUFFICIENT_HISTORY


def test_running_replicas_forecast_scenario():
    subj = fx.subject()
    states = [fx.replicas_state(fx.at(60 * i), 3 + i, subj=subj) for i in range(6)]
    s = CanonicalCapacitySeries.build(states)
    ev = forecast_with_evidence(s, ForecastTarget.RUNNING_REPLICAS, s.end_event_time, H1,
                                PersistenceForecaster(), normalization_policy=NPOL,
                                uncertainty_config=UncertaintyConfig(min_calibration_samples=3,
                                                                     match_tolerance_seconds=5.0))
    assert ev.forecast.is_forecast
    assert ev.forecast.unit == "replicas"
