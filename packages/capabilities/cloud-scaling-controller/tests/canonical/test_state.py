"""CanonicalCapacityState + measurement + provenance + subject tests (section 19.1)."""

from __future__ import annotations

import dataclasses
import math
from datetime import datetime, timezone

import pytest

from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState, CapacitySubject, CapacityState, DeploymentState,
    ForecastObservation, InfrastructureState, Measurement, ObservationProvenance,
    ObservationSourceType, PerformanceState, ReliabilityState, Unit, WorkloadState,
)
from ugence_cloud_scaling_controller.canonical.measurement import MeasurementError
from ugence_cloud_scaling_controller.canonical.identity import SubjectError
from ugence_cloud_scaling_controller.canonical.provenance import ProvenanceError
from ugence_cloud_scaling_controller.canonical.state import StateError

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


def _subject():
    return CapacitySubject(workload_id="w1", tenant_id="t1")


def _minimal():
    return CanonicalCapacityState(subject=_subject(), observed_at=NOW)


# --- partial / complete / immutability / equality -----------------------------------

def test_partial_state_allowed():
    s = _minimal()
    assert s.workload is None and s.infrastructure is None


def test_complete_state_roundtrip_and_digest_stable():
    s = CanonicalCapacityState(
        subject=_subject(), observed_at=NOW, correlation_id="c", time_phase="peak",
        workload=WorkloadState(queue_depth=Measurement(5, Unit.COUNT)),
        performance=PerformanceState(latency_p99=Measurement(200.0, Unit.MILLISECONDS)),
        infrastructure=InfrastructureState(cpu_utilization=Measurement(80.0, Unit.PERCENT)),
        capacity=CapacityState(running_replicas=3, ready_replicas=3, desired_replicas=3),
        reliability=ReliabilityState(error_rate=Measurement(0.1, Unit.RATE), restart_count=0),
        deployment=DeploymentState(deploy_active=False),
        forecast=ForecastObservation(horizon_seconds=300.0, predicted_demand=1.2),
        provenance=ObservationProvenance(ObservationSourceType.PROMETHEUS, NOW),
    )
    rebuilt = CanonicalCapacityState.from_dict(s.to_canonical_dict())
    assert rebuilt.digest() == s.digest()
    assert CanonicalCapacityState.from_dict(s.to_canonical_dict()).digest() == s.digest()


def test_immutable():
    s = _minimal()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.observed_at = NOW  # type: ignore[misc]


def test_deterministic_equality():
    assert _minimal() == _minimal()
    assert _minimal().digest() == _minimal().digest()


def test_unknown_top_level_field_fails_closed():
    data = _minimal().to_canonical_dict()
    data["bogus_signal"] = 1
    with pytest.raises(StateError):
        CanonicalCapacityState.from_dict(data)


def test_missing_optional_groups_ok():
    assert _minimal().to_canonical_dict()["workload"] is None


# --- numeric / type validation -------------------------------------------------------

def test_bool_rejected_where_number_expected():
    with pytest.raises(MeasurementError):
        Measurement(True, Unit.RATIO)


def test_nan_and_inf_rejected():
    with pytest.raises(MeasurementError):
        Measurement(float("nan"), Unit.RATIO)
    with pytest.raises(MeasurementError):
        Measurement(math.inf, Unit.PERCENT)


def test_ratio_and_percent_domains():
    with pytest.raises(MeasurementError):
        Measurement(1.5, Unit.RATIO)
    with pytest.raises(MeasurementError):
        Measurement(150.0, Unit.PERCENT)
    Measurement(0.5, Unit.RATIO)
    Measurement(50.0, Unit.PERCENT)


def test_illegal_negative_count_and_duration():
    with pytest.raises(MeasurementError):
        Measurement(-1, Unit.COUNT)
    with pytest.raises(MeasurementError):
        Measurement(-5.0, Unit.SECONDS)


def test_count_must_be_integer_valued():
    with pytest.raises(MeasurementError):
        Measurement(2.5, Unit.COUNT)


def test_negative_restart_count_rejected():
    with pytest.raises(StateError):
        ReliabilityState(restart_count=-1)


def test_contradictory_replica_limits_rejected():
    with pytest.raises(StateError):
        CapacityState(min_replicas=5, max_replicas=2)


def test_desired_running_ready_healthy_distinct():
    c = CapacityState(desired_replicas=5, running_replicas=4, ready_replicas=3, healthy_replicas=2)
    assert (c.desired_replicas, c.running_replicas, c.ready_replicas, c.healthy_replicas) == (5, 4, 3, 2)


# --- subject / scope -----------------------------------------------------------------

def test_missing_workload_id_fails_closed():
    with pytest.raises(SubjectError):
        CapacitySubject(workload_id="")


def test_empty_scope_string_rejected():
    with pytest.raises(SubjectError):
        CapacitySubject(workload_id="w", tenant_id="")


def test_subject_equality_and_serialization():
    a = CapacitySubject(workload_id="w", region="r")
    b = CapacitySubject(workload_id="w", region="r")
    assert a == b
    assert CapacitySubject.from_dict(a.to_canonical_dict()) == a


# --- provenance ----------------------------------------------------------------------

def test_missing_provenance_is_explicit():
    p = ObservationProvenance.missing(NOW)
    assert p.is_missing and p.source_type is ObservationSourceType.UNKNOWN


def test_provenance_observation_vs_collection_time_distinct():
    p = ObservationProvenance(ObservationSourceType.PROMETHEUS, observed_at=NOW,
                              collected_at=datetime(2026, 8, 11, 12, 5, tzinfo=timezone.utc))
    assert p.observed_at != p.collected_at


def test_invalid_timestamp_type_rejected():
    with pytest.raises(ProvenanceError):
        ObservationProvenance(ObservationSourceType.FIXTURE, observed_at="2026-08-11")  # type: ignore[arg-type]


def test_measurement_level_provenance_overrides_state_level():
    state_prov = ObservationProvenance(ObservationSourceType.PROMETHEUS, NOW, source_id="global")
    cpu_prov = ObservationProvenance(ObservationSourceType.CLOUDWATCH, NOW, source_id="cpu-specific")
    s = CanonicalCapacityState(subject=_subject(), observed_at=NOW,
                               provenance=state_prov, measurement_provenance={"cpu": cpu_prov})
    assert s.provenance_for("cpu").source_id == "cpu-specific"
    assert s.provenance_for("memory").source_id == "global"


def test_measurement_provenance_bad_key_rejected():
    with pytest.raises(StateError):
        CanonicalCapacityState(subject=_subject(), observed_at=NOW,
                               measurement_provenance={"": ObservationProvenance(
                                   ObservationSourceType.FIXTURE, NOW)})


# --- schema version / forecast -------------------------------------------------------

def test_unsupported_schema_version_fails_closed():
    with pytest.raises(StateError):
        CanonicalCapacityState(subject=_subject(), observed_at=NOW, schema_version="capacity-state-99")


def test_invalid_observed_at_type():
    with pytest.raises(StateError):
        CanonicalCapacityState(subject=_subject(), observed_at="now")  # type: ignore[arg-type]


def test_forecast_validation():
    with pytest.raises(StateError):
        ForecastObservation(horizon_seconds=0.0, predicted_demand=1.0)
    with pytest.raises(StateError):
        ForecastObservation(horizon_seconds=10.0, predicted_demand=1.0, confidence=1.5)
    with pytest.raises(StateError):
        ForecastObservation(horizon_seconds=10.0, predicted_demand=1.0, lower_bound=5.0, upper_bound=1.0)
