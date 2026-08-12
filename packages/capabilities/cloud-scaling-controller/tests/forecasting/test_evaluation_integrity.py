"""Correction A: controlled evaluation construction rejects contradictory/forged records."""

from __future__ import annotations

import dataclasses

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.forecasting import (
    CanonicalCapacitySeries,
    EvaluationStatus,
    ForecastHorizon,
    ForecastTarget,
    PersistenceForecaster,
    UncertaintyConfig,
    UncertaintyMethod,
    evaluate_forecast,
    forecast_with_evidence,
)
from ugence_cloud_scaling_controller.forecasting.evaluation import (
    EvaluationError,
    ForecastEvaluationRecord,
)

H1 = ForecastHorizon(60.0)


def _evidence(values, *, uncertainty=None):
    s = CanonicalCapacitySeries.build(fx.cpu_series_states(values, cadence_seconds=60.0))
    return forecast_with_evidence(
        s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, H1, PersistenceForecaster(),
        normalization_policy=fx.cpu_norm_policy(),
        uncertainty_config=uncertainty or UncertaintyConfig(method=UncertaintyMethod.NONE),
    )


def _valid_evaluated():
    ev = _evidence([10.0, 20.0, 30.0])            # persistence point = 30
    actual = fx.cpu_state(ev.forecast.forecast_for, 25.0)
    rec = evaluate_forecast(ev, actual, match_tolerance_seconds=5.0)
    assert rec.status is EvaluationStatus.EVALUATED
    return rec


# ---- the supported factory derives everything ------------------------------------

def test_service_derives_actual_value_and_unit_from_state():
    ev = _evidence([10.0, 20.0, 30.0])
    actual = fx.cpu_state(ev.forecast.forecast_for, 25.0)
    rec = evaluate_forecast(ev, actual, match_tolerance_seconds=5.0)
    assert rec.actual_value == 25.0            # from the canonical state, not a caller scalar
    assert rec.unit == "percent"
    assert rec.signed_error == 5.0             # recomputed 30 - 25
    assert rec.actual_state_digest == actual.digest()


# ---- direct construction rejects contradictions ----------------------------------

def test_contradictory_signed_error_rejected():
    rec = _valid_evaluated()
    with pytest.raises(EvaluationError, match="signed_error"):
        dataclasses.replace(rec, signed_error=999.0)


def test_contradictory_actual_value_rejected():
    rec = _valid_evaluated()
    # Changing only actual_value makes signed/abs/squared inconsistent -> rejected.
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, actual_value=1.0)


def test_contradictory_absolute_and_squared_rejected():
    rec = _valid_evaluated()
    with pytest.raises(EvaluationError, match="absolute_error"):
        dataclasses.replace(rec, absolute_error=123.0)
    with pytest.raises(EvaluationError, match="squared_error"):
        dataclasses.replace(rec, squared_error=123.0)


def test_altered_interval_coverage_rejected():
    ev = _evidence([0.0, 10.0, 5.0, 20.0, 15.0, 30.0],
                   uncertainty=UncertaintyConfig(requested_coverage=0.8, min_calibration_samples=5,
                                                 match_tolerance_seconds=5.0))
    actual = fx.cpu_state(ev.forecast.forecast_for, 40.0)
    rec = evaluate_forecast(ev, actual, match_tolerance_seconds=5.0)
    assert rec.interval_covered is not None
    with pytest.raises(EvaluationError, match="interval_covered"):
        dataclasses.replace(rec, interval_covered=not rec.interval_covered)
    with pytest.raises(EvaluationError, match="interval_width"):
        dataclasses.replace(rec, interval_width=(rec.interval_width or 0.0) + 5.0)


def test_evaluated_without_unit_rejected():
    rec = _valid_evaluated()
    with pytest.raises(EvaluationError, match="unit"):
        dataclasses.replace(rec, unit=None)


def test_non_finite_fields_rejected():
    rec = _valid_evaluated()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, actual_value=float("nan"), signed_error=float("nan"),
                            absolute_error=float("nan"), squared_error=float("nan"))


def test_forged_state_digest_rejected():
    rec = _valid_evaluated()
    # The digest is checked against the EMBEDDED actual state — a forged digest is rejected.
    with pytest.raises(EvaluationError, match="forged digest|embedded actual_state"):
        dataclasses.replace(rec, actual_state_digest="sha256:forged")


def test_abstained_record_cannot_carry_scored_fields():
    ev = _evidence([10.0, 20.0, 30.0])
    # Build a legitimate abstained record by scoring an abstained forecast.
    ab = _evidence([10.0, 20.0, 30.0])
    # Force abstention via missing policy:
    s = CanonicalCapacitySeries.build(fx.cpu_series_states([10.0, 20.0, 30.0]))
    ab = forecast_with_evidence(s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, H1,
                                PersistenceForecaster(), normalization_policy=None,
                                uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE))
    rec = evaluate_forecast(ab, None, match_tolerance_seconds=5.0)
    assert rec.status is EvaluationStatus.ABSTAINED
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, signed_error=1.0, absolute_error=1.0, squared_error=1.0)


def test_unmatched_on_unit_mismatch_between_forecast_and_actual():
    from ugence_cloud_scaling_controller.canonical import (
        CanonicalCapacityState, InfrastructureState, Measurement, Unit, CapacityState,
    )
    ev = _evidence([10.0, 20.0, 30.0])  # forecast unit = percent
    subj = fx.subject()
    # Actual carries CPU as a RATIO, not percent -> unit mismatch, never silently compared.
    actual = CanonicalCapacityState(
        subject=subj, observed_at=ev.forecast.forecast_for,
        infrastructure=InfrastructureState(cpu_utilization=Measurement(0.25, Unit.RATIO)),
        capacity=CapacityState(running_replicas=4))
    rec = evaluate_forecast(ev, actual, match_tolerance_seconds=5.0)
    assert rec.status is EvaluationStatus.UNMATCHED
    assert rec.reason == "actual_unit_mismatch"
