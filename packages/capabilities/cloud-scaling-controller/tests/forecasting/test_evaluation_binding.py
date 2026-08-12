"""Final correction 1: EVALUATED records are structurally bound to the canonical actual state.

Adversarial proof that a caller cannot present a forged actual value / digest / subject / unit,
and that reconstruction (from_dict) re-validates the binding rather than bypassing it.
"""

from __future__ import annotations

import dataclasses

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState, CapacityState, InfrastructureState, Measurement, Unit,
)
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
NONE_UC = UncertaintyConfig(method=UncertaintyMethod.NONE)


def _evidence(values=(10.0, 20.0, 30.0)):
    s = CanonicalCapacitySeries.build(fx.cpu_series_states(list(values), cadence_seconds=60.0))
    return forecast_with_evidence(
        s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, H1, PersistenceForecaster(),
        normalization_policy=fx.cpu_norm_policy(), uncertainty_config=NONE_UC,
    )


def _valid(ev=None, actual_cpu=25.0):
    ev = ev or _evidence()
    actual = fx.cpu_state(ev.forecast.forecast_for, actual_cpu)
    rec = evaluate_forecast(ev, actual, match_tolerance_seconds=5.0)
    assert rec.status is EvaluationStatus.EVALUATED
    return ev, rec, actual


def test_evaluated_embeds_the_actual_state():
    _ev, rec, actual = _valid()
    assert rec.actual_state is actual
    assert rec.actual_state_digest == actual.digest()
    assert rec.actual_value == 25.0
    assert rec.unit == "percent"


def test_forged_actual_value_against_real_state_rejected():
    _ev, rec, _actual = _valid()               # embedded state has cpu = 25
    with pytest.raises(EvaluationError, match="actual_value"):
        dataclasses.replace(rec, actual_value=99.0, signed_error=rec.point_forecast - 99.0,
                            absolute_error=abs(rec.point_forecast - 99.0),
                            squared_error=(rec.point_forecast - 99.0) ** 2)


def test_embedding_unrelated_state_rejected():
    _ev, rec, _actual = _valid()
    other = fx.cpu_state(rec.forecast_for, 99.0)  # different content -> different digest
    with pytest.raises(EvaluationError, match="forged digest|embedded actual_state"):
        dataclasses.replace(rec, actual_state=other)  # digest no longer matches


def test_digest_without_embedded_state_rejected():
    _ev, rec, _actual = _valid()
    with pytest.raises(EvaluationError, match="requires the embedded actual_state"):
        dataclasses.replace(rec, actual_state=None)


def test_subject_binding_mismatch_rejected():
    _ev, rec, _actual = _valid()
    with pytest.raises(EvaluationError, match="subject"):
        dataclasses.replace(rec, subject=fx.subject("wl-OTHER"))


def test_unit_mismatch_against_state_rejected():
    _ev, rec, _actual = _valid()
    with pytest.raises(EvaluationError, match="unit"):
        dataclasses.replace(rec, unit="ratio")   # embedded sample unit is percent


def test_target_mismatch_rejected():
    # EVALUATED claiming a target the embedded state does not carry is rejected.
    _ev, rec, _actual = _valid()
    with pytest.raises(EvaluationError, match="target"):
        dataclasses.replace(rec, target=ForecastTarget.MEMORY_UTILIZATION.value)


def test_contradictory_interval_rejected():
    ev = _evidence([0.0, 10.0, 5.0, 20.0, 15.0, 30.0])
    ev = forecast_with_evidence(
        CanonicalCapacitySeries.build(fx.cpu_series_states([0.0, 10.0, 5.0, 20.0, 15.0, 30.0], cadence_seconds=60.0)),
        ForecastTarget.CPU_UTILIZATION, fx.at(300), H1, PersistenceForecaster(),
        normalization_policy=fx.cpu_norm_policy(),
        uncertainty_config=UncertaintyConfig(requested_coverage=0.8, min_calibration_samples=5, match_tolerance_seconds=5.0))
    actual = fx.cpu_state(ev.forecast.forecast_for, 40.0)
    rec = evaluate_forecast(ev, actual, match_tolerance_seconds=5.0)
    if rec.interval_covered is not None:
        with pytest.raises(EvaluationError, match="interval_covered|interval_width"):
            dataclasses.replace(rec, interval_covered=not rec.interval_covered)


def test_non_finite_outcome_rejected():
    _ev, rec, _actual = _valid()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, point_forecast=float("inf"),
                            signed_error=float("inf"), absolute_error=float("inf"),
                            squared_error=float("inf"))


# ---- reconstruction / deserialization boundary re-validates ----------------------

def test_roundtrip_from_dict_preserves_identity():
    _ev, rec, _actual = _valid()
    data = rec.to_canonical_dict(include_digest=False)
    clone = ForecastEvaluationRecord.from_dict(data)
    assert clone.digest() == rec.digest()
    assert clone.status is EvaluationStatus.EVALUATED
    assert clone.actual_state is not None
    assert clone.actual_state.digest() == rec.actual_state_digest


def test_from_dict_rejects_forged_actual_value():
    _ev, rec, _actual = _valid()
    data = rec.to_canonical_dict(include_digest=False)
    data["actual_value"] = 99.0   # inconsistent with the embedded state (cpu 25)
    with pytest.raises(EvaluationError, match="actual_value"):
        ForecastEvaluationRecord.from_dict(data)


def test_from_dict_rejects_forged_digest():
    _ev, rec, _actual = _valid()
    data = rec.to_canonical_dict(include_digest=False)
    data["actual_state_digest"] = "sha256:forged"
    with pytest.raises(EvaluationError, match="forged digest|embedded actual_state"):
        ForecastEvaluationRecord.from_dict(data)


def test_from_dict_rejects_tampered_errors():
    _ev, rec, _actual = _valid()
    data = rec.to_canonical_dict(include_digest=False)
    data["signed_error"] = 12345.0
    with pytest.raises(EvaluationError, match="signed_error"):
        ForecastEvaluationRecord.from_dict(data)


def test_evidence_digest_binds_actual_state_content():
    # Two records whose only difference is the actual state's measured value differ in digest.
    ev = _evidence()
    a = evaluate_forecast(ev, fx.cpu_state(ev.forecast.forecast_for, 25.0), match_tolerance_seconds=5.0)
    b = evaluate_forecast(ev, fx.cpu_state(ev.forecast.forecast_for, 26.0), match_tolerance_seconds=5.0)
    assert a.digest() != b.digest()
