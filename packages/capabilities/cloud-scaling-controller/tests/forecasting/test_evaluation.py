"""ForecastEvaluationRecord matching/metrics and deterministic aggregate report."""

from __future__ import annotations

import math

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.forecasting import (
    AbstentionReason,
    CanonicalCapacitySeries,
    EvaluationStatus,
    ForecastHorizon,
    ForecastTarget,
    PersistenceForecaster,
    UncertaintyConfig,
    UncertaintyMethod,
    aggregate_evaluations,
    evaluate_forecast,
    forecast_with_evidence,
)

H1 = ForecastHorizon(60.0)


def _evidence(values, *, horizon=H1, uncertainty=None, npol=...):
    s = CanonicalCapacitySeries.build(fx.cpu_series_states(values, cadence_seconds=60.0))
    if npol is ...:
        npol = fx.cpu_norm_policy()
    return forecast_with_evidence(
        s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, horizon, PersistenceForecaster(),
        normalization_policy=npol,
        uncertainty_config=uncertainty or UncertaintyConfig(method=UncertaintyMethod.NONE),
    )


def test_evaluated_record_has_errors_and_digest():
    ev = _evidence([10.0, 20.0, 30.0])            # persistence point = 30 at t=120
    forecast_for = ev.forecast.forecast_for       # t=180
    actual = fx.cpu_state(forecast_for, 25.0)     # actual CPU 25
    rec = evaluate_forecast(ev, actual, match_tolerance_seconds=5.0)
    assert rec.status is EvaluationStatus.EVALUATED
    assert rec.point_forecast == 30.0
    assert rec.actual_value == 25.0
    assert rec.signed_error == 5.0
    assert rec.absolute_error == 5.0
    assert rec.squared_error == 25.0
    assert rec.digest().startswith("sha256:")
    assert rec.forecast_evidence_digest == ev.digest()


def test_no_actual_is_unmatched():
    ev = _evidence([10.0, 20.0, 30.0])
    rec = evaluate_forecast(ev, None, match_tolerance_seconds=5.0)
    assert rec.status is EvaluationStatus.UNMATCHED
    assert rec.reason == "no_actual_available"


def test_actual_outside_tolerance_is_unmatched():
    ev = _evidence([10.0, 20.0, 30.0])
    late = fx.cpu_state(ev.forecast.forecast_for.replace(second=59), 25.0)  # ~59s off
    rec = evaluate_forecast(ev, late, match_tolerance_seconds=5.0)
    assert rec.status is EvaluationStatus.UNMATCHED
    assert rec.reason == "actual_outside_tolerance"


def test_subject_mismatch_actual_recorded():
    ev = _evidence([10.0, 20.0, 30.0])
    other = fx.cpu_state(ev.forecast.forecast_for, 25.0, subj=fx.subject("wl-OTHER"))
    rec = evaluate_forecast(ev, other, match_tolerance_seconds=5.0)
    assert rec.status is EvaluationStatus.SUBJECT_MISMATCH


def test_abstention_is_recorded_not_scored():
    ev = _evidence([10.0, 20.0, 30.0], npol=None)  # missing policy -> abstain
    assert ev.forecast.is_abstained
    rec = evaluate_forecast(ev, None, match_tolerance_seconds=5.0)
    assert rec.status is EvaluationStatus.ABSTAINED
    assert rec.reason == AbstentionReason.MISSING_NORMALIZATION_POLICY.value
    assert rec.signed_error is None


def test_interval_coverage_recorded_when_available():
    ev = _evidence([0.0, 10.0, 5.0, 20.0, 15.0, 30.0],
                   uncertainty=UncertaintyConfig(requested_coverage=0.8, min_calibration_samples=5,
                                                 match_tolerance_seconds=5.0))
    assert ev.forecast.uncertainty.available  # interval [25, 45]
    inside = fx.cpu_state(ev.forecast.forecast_for, 40.0)
    rec = evaluate_forecast(ev, inside, match_tolerance_seconds=5.0)
    assert rec.interval_covered is True
    assert rec.interval_width == 20.0
    outside = fx.cpu_state(ev.forecast.forecast_for, 90.0)
    rec2 = evaluate_forecast(ev, outside, match_tolerance_seconds=5.0)
    assert rec2.interval_covered is False


def test_aggregate_metrics_are_deterministic():
    ev = _evidence([10.0, 20.0, 30.0])
    r_eval = evaluate_forecast(ev, fx.cpu_state(ev.forecast.forecast_for, 25.0),
                               match_tolerance_seconds=5.0)   # error +5
    ev2 = _evidence([10.0, 20.0, 40.0])                        # point 40
    r_eval2 = evaluate_forecast(ev2, fx.cpu_state(ev2.forecast.forecast_for, 47.0),
                                match_tolerance_seconds=5.0)  # error -7
    r_abst = evaluate_forecast(_evidence([10.0, 20.0, 30.0], npol=None), None,
                               match_tolerance_seconds=5.0)
    agg = aggregate_evaluations([r_eval, r_eval2, r_abst], model_id="persistence")
    assert agg.record_count == 3
    assert agg.abstention_count == 1
    assert agg.evaluated_count == 2
    assert abs(agg.mean_absolute_error - 6.0) < 1e-9         # (5 + 7)/2
    assert abs(agg.root_mean_squared_error - math.sqrt((25 + 49) / 2)) < 1e-9
    assert abs(agg.mean_signed_error - (-1.0)) < 1e-9         # (5 + -7)/2
    assert abs(agg.abstention_rate - (1 / 3)) < 1e-9


def test_aggregate_omits_percentage_error_metrics():
    agg = aggregate_evaluations([], model_id="x")
    d = agg.to_canonical_dict()
    assert not any("percent" in k or "mape" in k.lower() for k in d)
