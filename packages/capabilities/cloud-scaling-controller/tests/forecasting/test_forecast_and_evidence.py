"""Forecast service path: point/abstention outputs, invariants, and evidence-digest boundary."""

from __future__ import annotations

from datetime import timedelta

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState, CapacityState, InfrastructureState, Measurement, Unit,
)
from ugence_cloud_scaling_controller.forecasting import (
    AbstentionReason,
    AdmissionPolicy,
    CanonicalCapacitySeries,
    FeatureConfig,
    ForecastHorizon,
    ForecastTarget,
    LinearTrendForecaster,
    PersistenceForecaster,
    UncertaintyConfig,
    UncertaintyMethod,
    forecast_with_evidence,
    generate_forecast,
)


class LimitedForecaster(PersistenceForecaster):
    """Persistence that only supports CPU and horizons <= 10 minutes (for gate tests)."""

    def supported_targets(self):
        return frozenset({ForecastTarget.CPU_UTILIZATION})

    def supports_horizon(self, horizon):
        return horizon.seconds <= 600.0


def _series(values, **kw):
    return CanonicalCapacitySeries.build(fx.cpu_series_states(values, **kw))


def _forecast(values, *, target=ForecastTarget.CPU_UTILIZATION, horizon_min=5,
              forecaster=None, admission=None, uncertainty=None, npol=..., cutoff=None,
              feature=None, expected_subject=None):
    s = _series(values)
    if npol is ...:
        npol = fx.cpu_norm_policy()
    cut = cutoff if cutoff is not None else s.end_event_time
    return forecast_with_evidence(
        s, target, cut, ForecastHorizon.minutes(horizon_min),
        forecaster or PersistenceForecaster(),
        normalization_policy=npol,
        admission_policy=admission,
        uncertainty_config=uncertainty or UncertaintyConfig(method=UncertaintyMethod.NONE),
        feature_config=feature,
        expected_subject=expected_subject,
    )


def test_successful_forecast_is_shadow_and_advisory_only():
    ev = _forecast([10.0, 20.0, 30.0])
    fc = ev.forecast
    assert fc.is_forecast
    assert fc.point_estimate == 30.0
    assert fc.advisory_only is True
    assert fc.shadow_only is True
    assert fc.actuation_performed is False
    assert fc.authority_class == "ADVISORY"
    assert fc.execution_capability == "NONE"
    # Evidence mirrors the shadow-only classification.
    assert ev.advisory_only is True and ev.shadow_only is True
    assert ev.actuation_performed is False


def test_missing_normalization_policy_abstains():
    ev = _forecast([10.0, 20.0, 30.0], npol=None)
    assert ev.forecast.is_abstained
    assert ev.forecast.abstention_reason is AbstentionReason.MISSING_NORMALIZATION_POLICY
    assert ev.normalization_policy_digest is None


def test_insufficient_history_abstains():
    ev = _forecast([10.0, 20.0], forecaster=LinearTrendForecaster())  # 2 < min_history 3
    assert ev.forecast.abstention_reason is AbstentionReason.INSUFFICIENT_HISTORY


def test_unsupported_target_abstains():
    ev = _forecast([10.0, 20.0, 30.0], target=ForecastTarget.MEMORY_UTILIZATION,
                   forecaster=LimitedForecaster())
    assert ev.forecast.abstention_reason is AbstentionReason.UNSUPPORTED_TARGET


def test_unsupported_horizon_abstains():
    ev = _forecast([10.0, 20.0, 30.0], horizon_min=60, forecaster=LimitedForecaster())
    assert ev.forecast.abstention_reason is AbstentionReason.UNSUPPORTED_HORIZON


def test_subject_mismatch_abstains():
    other = fx.subject("wl-OTHER")
    ev = _forecast([10.0, 20.0, 30.0], expected_subject=other)
    assert ev.forecast.abstention_reason is AbstentionReason.SUBJECT_MISMATCH


def test_stale_history_abstains():
    s = _series([10.0, 20.0, 30.0])
    stale_cutoff = s.end_event_time + timedelta(seconds=400)  # > 300s default staleness
    ev = forecast_with_evidence(
        s, ForecastTarget.CPU_UTILIZATION, stale_cutoff, ForecastHorizon.minutes(5),
        PersistenceForecaster(), normalization_policy=fx.cpu_norm_policy(),
        uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE),
    )
    assert ev.forecast.abstention_reason is AbstentionReason.STALE_HISTORY


def test_excessive_missingness_abstains():
    states = [
        fx.cpu_state(fx.at(0), 10.0),
        fx.cpu_state(fx.at(60), None),
        fx.cpu_state(fx.at(120), None),
        fx.cpu_state(fx.at(180), None),
    ]
    s = CanonicalCapacitySeries.build(states)
    ev = forecast_with_evidence(
        s, ForecastTarget.CPU_UTILIZATION, fx.at(180), ForecastHorizon.minutes(5),
        PersistenceForecaster(), normalization_policy=fx.cpu_norm_policy(),
        uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE),
    )
    assert ev.forecast.abstention_reason is AbstentionReason.EXCESSIVE_MISSINGNESS


def test_irregular_cadence_abstains():
    states = [
        fx.cpu_state(fx.at(0), 10.0),
        fx.cpu_state(fx.at(60), 20.0),
        fx.cpu_state(fx.at(400), 30.0),  # irregular gap
    ]
    s = CanonicalCapacitySeries.build(states)
    ev = forecast_with_evidence(
        s, ForecastTarget.CPU_UTILIZATION, fx.at(400), ForecastHorizon.minutes(5),
        PersistenceForecaster(), normalization_policy=fx.cpu_norm_policy(),
        uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE),
    )
    assert ev.forecast.abstention_reason is AbstentionReason.IRREGULAR_CADENCE


def test_forecast_domain_violation_abstains_by_default():
    # Steeply decreasing CPU; linear extrapolation over a long horizon goes below 0%.
    ev = _forecast([50.0, 40.0, 30.0, 20.0, 10.0], horizon_min=60,
                   forecaster=LinearTrendForecaster())
    assert ev.forecast.abstention_reason is AbstentionReason.FORECAST_OUTSIDE_DOMAIN


def test_out_of_domain_retained_only_with_explicit_policy_and_warning():
    ev = _forecast([50.0, 40.0, 30.0, 20.0, 10.0], horizon_min=60,
                   forecaster=LinearTrendForecaster(),
                   admission=AdmissionPolicy(allow_out_of_domain=True))
    assert ev.forecast.is_forecast
    assert ev.forecast.point_estimate < 0.0
    assert any("outside the admissible" in w for w in ev.forecast.warnings)


def test_insufficient_calibration_abstains_unless_point_only_allowed():
    # Only 3 points, 5min horizon => no rolling-origin residual matches => 0 residuals.
    strict = _forecast([10.0, 20.0, 30.0], forecaster=LinearTrendForecaster(),
                       uncertainty=UncertaintyConfig(min_calibration_samples=5,
                                                     match_tolerance_seconds=5.0))
    assert strict.forecast.abstention_reason is AbstentionReason.INSUFFICIENT_CALIBRATION_HISTORY

    lenient = _forecast([10.0, 20.0, 30.0], forecaster=LinearTrendForecaster(),
                        uncertainty=UncertaintyConfig(min_calibration_samples=5,
                                                      match_tolerance_seconds=5.0,
                                                      allow_point_only_when_uncalibrated=True))
    assert lenient.forecast.is_forecast
    assert lenient.forecast.uncertainty.available is False
    assert any("point-only" in w for w in lenient.forecast.warnings)


def test_generate_forecast_matches_evidence_forecast():
    s = _series([10.0, 20.0, 30.0])
    fc = generate_forecast(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time,
                           ForecastHorizon.minutes(5), PersistenceForecaster(),
                           normalization_policy=fx.cpu_norm_policy(),
                           uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE))
    ev = _forecast([10.0, 20.0, 30.0])
    assert fc.point_estimate == ev.forecast.point_estimate
    assert fc.input_window_digest == ev.forecast.input_window_digest


# ---- evidence-digest boundary ----------------------------------------------------

def test_digest_excludes_production_time_and_annotation():
    s = _series([10.0, 20.0, 30.0])
    common = dict(
        normalization_policy=fx.cpu_norm_policy(),
        uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE),
    )
    a = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time,
                               ForecastHorizon.minutes(5), PersistenceForecaster(),
                               evidence_produced_at=fx.at(10_000),
                               diagnostic_annotation="note A", **common)
    b = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time,
                               ForecastHorizon.minutes(5), PersistenceForecaster(),
                               evidence_produced_at=fx.at(20_000),
                               diagnostic_annotation="note B", **common)
    assert a.digest() == b.digest()  # production time + annotation are non-authoritative


def test_digest_changes_when_authoritative_field_changes():
    s = _series([10.0, 20.0, 30.0])
    common = dict(
        normalization_policy=fx.cpu_norm_policy(),
        uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE),
    )
    a = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time,
                               ForecastHorizon.minutes(5), PersistenceForecaster(), **common)
    b = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time,
                               ForecastHorizon.minutes(15), PersistenceForecaster(), **common)
    assert a.digest() != b.digest()  # horizon is authoritative


def test_digest_changes_when_normalization_policy_changes():
    s = _series([10.0, 20.0, 30.0])
    common = dict(uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE))
    a = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time,
                               ForecastHorizon.minutes(5), PersistenceForecaster(),
                               normalization_policy=fx.cpu_norm_policy("pol-A"), **common)
    b = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time,
                               ForecastHorizon.minutes(5), PersistenceForecaster(),
                               normalization_policy=fx.cpu_norm_policy("pol-B"), **common)
    assert a.digest() != b.digest()


def test_evidence_digest_is_reproducible():
    s = _series([10.0, 20.0, 30.0])
    kw = dict(normalization_policy=fx.cpu_norm_policy(),
              uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE))
    a = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time,
                               ForecastHorizon.minutes(5), PersistenceForecaster(), **kw)
    b = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time,
                               ForecastHorizon.minutes(5), PersistenceForecaster(), **kw)
    assert a.digest() == b.digest()
    assert a.digest().startswith("sha256:")
