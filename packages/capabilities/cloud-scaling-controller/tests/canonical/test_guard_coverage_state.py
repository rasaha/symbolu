"""Isolating tests for the guard sweep — `canonical/state.py`.

Written for phase 2 of the shared-engine adoption. `canonical/state.py` is where raw
observations become the trusted picture the planner reasons over, so a validation gate
that nothing proves is a gate that could silently stop refusing: malformed input would
become a confident recommendation rather than an error. The phase-2 sweep measured 39 of
its guards surviving — deletable with all 646 tests still green.

Each test isolates one gate by constructing an input valid in every respect except the
one field that gate reads, so exactly one refusal can fire. The typed half asserted is
`StateError`, the contract this module publishes; never a message substring.

The bulk of the module validates through a shared field-kind framework (`_v` dispatching
on `_MEASURE`/`_COUNT`/`_BOOL`/`_STR`/`_STR_TUPLE`, reached via `_validate`), so the
tests below drive each *kind* through a sub-state that declares a field of it. That is
deliberate: neutralising a `kind ==` dispatch arm makes the value fall through the elif
chain unvalidated, which is exactly the mutation the sweep applies.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState,
    CapacitySubject,
)
from ugence_cloud_scaling_controller.canonical.provenance import (
    ObservationProvenance,
    ObservationSourceType,
)
from ugence_cloud_scaling_controller.canonical.state import (
    CapacityState,
    DeploymentState,
    EconomicsState,
    ForecastObservation,
    InfrastructureState,
    PerformanceState,
    StateError,
    TopologyState,
    WorkloadState,
    _provenance_from_dict,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
_SOURCE_TYPE = ObservationSourceType.PROMETHEUS


def _subject(**over):
    fields = dict(workload_id="app", tenant_id="tenant-1")
    fields.update(over)
    return CapacitySubject(**fields)


# ======================================================================================= #
# the shared field-kind framework — one probe per kind, and per dispatch arm
# ======================================================================================= #


def test_a_measurement_field_that_is_not_a_measurement_is_refused():
    """Kills both the `kind == _MEASURE` dispatch arm and the check it routes into:
    neutralise either and a bare float is admitted as a Measurement."""

    with pytest.raises(StateError):
        WorkloadState(request_rate=0.5)


def test_a_boolean_field_that_is_not_a_bool_is_refused():
    """1 is truthy and an int, so nothing downstream objects — only the bool gate does."""

    with pytest.raises(StateError):
        DeploymentState(deploy_active=1)


def test_a_string_field_that_is_not_a_non_empty_string_is_refused():
    with pytest.raises(StateError):
        DeploymentState(rollout_phase="")


def test_a_string_field_that_is_not_a_string_at_all_is_refused():
    with pytest.raises(StateError):
        EconomicsState(pricing_model=7)


def test_a_string_tuple_field_that_is_not_a_tuple_is_refused():
    """A list, not a tuple: the framework requires the frozen form."""

    with pytest.raises(StateError):
        TopologyState(dependency_ids=["svc-a"])


def test_a_string_tuple_carrying_an_empty_member_is_refused():
    with pytest.raises(StateError):
        TopologyState(dependency_ids=("svc-a", ""))


@pytest.mark.parametrize(
    "state_cls, kwargs",
    [
        (WorkloadState, {"queue_depth": 3}),
        (PerformanceState, {"latency_p95": 12.5}),
        (InfrastructureState, {"cpu_utilization": 50.0}),
        (DeploymentState, {"deployment_age": 900.0}),
        (EconomicsState, {"estimated_hourly_cost": 1.5}),
        (TopologyState, {"service_id": 7}),
    ],
)
def test_every_substate_validates_its_own_fields(state_cls, kwargs):
    """The `_validate(self)` helper-admission calls, one per sub-state. Deleting the call
    in any of them admits a bare number where a Measurement (or a string) is required,
    and the malformed state flows on to the planner unchallenged.

    `CapacityState` and `ReliabilityState` are absent because their `_validate` calls
    were already killed by the pre-existing suite; the six listed here are the ones the
    phase-2 sweep measured surviving."""

    with pytest.raises(StateError):
        state_cls(**kwargs)


# ======================================================================================= #
# the framework's from_dict path
# ======================================================================================= #


def test_a_substate_payload_that_is_not_a_mapping_is_refused():
    """A list of the field names: the unknown-field set arithmetic passes on it, and the
    first membership test is where it would otherwise die untyped."""

    with pytest.raises(StateError):
        CapacityState.from_dict(["running_replicas"])


def test_a_substate_payload_carrying_an_unknown_field_is_refused():
    with pytest.raises(StateError):
        CapacityState.from_dict({"running_replicas": 3, "phantom_replicas": 1})


def test_a_string_tuple_payload_that_is_not_a_sequence_is_refused():
    """Truthy and not a list or tuple; without the gate `tuple("svc-a")` would silently
    split the string into single characters and admit them as dependency ids."""

    with pytest.raises(StateError):
        TopologyState.from_dict({"dependency_ids": "svc-a"})


def test_a_string_tuple_payload_is_frozen_into_a_tuple_on_the_way_in():
    """The `kind == _STR_TUPLE` dispatch arm in `_from_dict`, which no refusal test can
    reach: a JSON list is the *valid* wire form, and neutralising the arm routes it to the
    catch-all that hands the list through unchanged. The constructor then refuses it as
    "not a tuple" — the same typed contract, so every refusal probe still passes and the
    guard survives. Only reading the rebuilt value back distinguishes the two: this is the
    single decision point in the module whose evidence is a success, not a refusal.

    Measured, not reasoned: the first phase-2 sweep scored this guard SURVIVING against
    the refusal-only probes above."""

    rebuilt = TopologyState.from_dict({"dependency_ids": ["svc-a", "svc-b"]})
    assert rebuilt.dependency_ids == ("svc-a", "svc-b")


# ======================================================================================= #
# ForecastObservation — the embedded prediction the planner may read
# ======================================================================================= #


def _forecast(**over):
    fields = dict(horizon_seconds=900.0, predicted_demand=12.0)
    fields.update(over)
    return ForecastObservation(**fields)


def test_a_required_forecast_field_that_is_not_a_real_number_is_refused():
    """A bool is an int in Python, which is precisely why the gate tests it separately;
    without that test `True` becomes a horizon of one second."""

    with pytest.raises(StateError):
        _forecast(horizon_seconds=True)


def test_an_optional_forecast_bound_that_is_not_a_real_number_is_refused():
    """The bound is optional, so `None` is admissible and cannot probe this gate; a bool
    can, and the ordering check below compares bounds without type-checking them."""

    with pytest.raises(StateError):
        _forecast(lower_bound=True, upper_bound=20.0)


def test_a_forecast_method_that_is_not_a_non_empty_string_is_refused():
    with pytest.raises(StateError):
        _forecast(method="")


def test_a_forecast_payload_that_is_not_a_mapping_is_refused():
    with pytest.raises(StateError):
        ForecastObservation.from_dict(["horizon_seconds", "predicted_demand"])


def test_a_forecast_payload_carrying_an_unknown_field_is_refused():
    with pytest.raises(StateError):
        ForecastObservation.from_dict(
            {"horizon_seconds": 900.0, "predicted_demand": 12.0, "vibes": 1}
        )


def test_a_forecast_payload_missing_a_required_field_is_refused():
    with pytest.raises(StateError):
        ForecastObservation.from_dict({"horizon_seconds": 900.0})


# ======================================================================================= #
# CanonicalCapacityState — the top-level observation
# ======================================================================================= #


def _state(**over):
    fields = dict(subject=_subject(), observed_at=T0)
    fields.update(over)
    return CanonicalCapacityState(**fields)


def test_a_state_subject_that_is_not_a_subject_is_refused():
    with pytest.raises(StateError):
        _state(subject="app")


def test_a_state_correlation_id_that_is_not_a_string_is_refused():
    with pytest.raises(StateError):
        _state(correlation_id=7)


def test_a_state_time_phase_that_is_not_a_string_is_refused():
    with pytest.raises(StateError):
        _state(time_phase=7)


def test_a_substate_of_the_wrong_type_is_refused():
    """The `_SUBSTATE_TYPES` loop: a real sub-state, but slotted into the wrong field, so
    every field it carries is individually valid and only the slot type is wrong."""

    with pytest.raises(StateError):
        _state(capacity=WorkloadState())


def test_a_state_forecast_of_the_wrong_type_is_refused():
    with pytest.raises(StateError):
        _state(forecast={"horizon_seconds": 900.0, "predicted_demand": 12.0})


def test_a_state_provenance_of_the_wrong_type_is_refused():
    with pytest.raises(StateError):
        _state(provenance={"source_type": "prometheus"})


def test_a_measurement_provenance_that_is_not_a_mapping_is_refused():
    """Without the gate, `.items()` on the list is an AttributeError rather than the
    state contract."""

    with pytest.raises(StateError):
        _state(measurement_provenance=[("cpu", None)])


def test_a_measurement_provenance_value_that_is_not_provenance_is_refused():
    with pytest.raises(StateError):
        _state(measurement_provenance={"cpu_utilization": "prometheus"})


# ======================================================================================= #
# CanonicalCapacityState.from_dict and the provenance reader
# ======================================================================================= #


def _state_payload(**over):
    payload = dict(subject=_subject().to_canonical_dict(), observed_at=T0)
    payload.update(over)
    return payload


def test_a_state_payload_that_is_not_a_mapping_is_refused():
    with pytest.raises(StateError):
        CanonicalCapacityState.from_dict(["subject", "observed_at"])


def test_a_state_payload_carrying_an_unknown_field_is_refused():
    with pytest.raises(StateError):
        CanonicalCapacityState.from_dict(_state_payload(weather="sunny"))


def test_a_state_payload_missing_a_required_field_is_refused():
    with pytest.raises(StateError):
        CanonicalCapacityState.from_dict({"subject": _subject().to_canonical_dict()})


def test_a_state_payload_observed_at_that_is_not_a_datetime_is_refused():
    """The subject is malformed too: the dataclass repeats this check with the same
    `StateError`, so the discriminating fallback is `SubjectError` from the subject
    parse — a different contract entirely."""

    payload = _state_payload(observed_at="2026-01-01", subject="app")
    with pytest.raises(StateError):
        CanonicalCapacityState.from_dict(payload)


def _prov_payload(**over):
    payload = dict(source_type="prometheus", observed_at=T0)
    payload.update(over)
    return payload


def test_a_provenance_payload_that_is_not_a_mapping_is_refused():
    with pytest.raises(StateError):
        _provenance_from_dict(["source_type", "observed_at"])


def test_a_provenance_payload_carrying_an_unknown_field_is_refused():
    with pytest.raises(StateError):
        _provenance_from_dict(_prov_payload(origin="guesswork"))


def test_a_provenance_payload_missing_a_required_field_is_refused():
    with pytest.raises(StateError):
        _provenance_from_dict({"source_type": "prometheus"})


def test_a_state_payload_with_measurement_provenance_reads_it_through_the_gate():
    """The `data.get('measurement_provenance')` admission: with it removed the mapping is
    dropped and the reconstructed state silently loses per-signal provenance — the state
    still builds, so only a test that reads the value back can see it."""

    prov = ObservationProvenance(source_type=_SOURCE_TYPE, observed_at=T0)
    payload = _state_payload(
        measurement_provenance={"cpu_utilization": prov.to_canonical_dict()}
    )
    rebuilt = CanonicalCapacityState.from_dict(payload)
    assert rebuilt.provenance_for("cpu_utilization") == prov


def test_a_provenance_payload_naming_an_unknown_source_type_is_refused():
    """The enum lookup's ValueError is re-raised as the state contract; without the
    translation the caller sees a bare ValueError naming an enum it never mentioned."""

    with pytest.raises(StateError):
        _provenance_from_dict(_prov_payload(source_type="crystal_ball"))


def test_a_provenance_payload_whose_record_is_malformed_is_refused_as_a_state_error():
    """`ProvenanceError` is not a `StateError`; the translation is what keeps a
    from_dict caller reading one contract rather than two."""

    with pytest.raises(StateError):
        _provenance_from_dict(_prov_payload(observed_at="2026-01-01"))
