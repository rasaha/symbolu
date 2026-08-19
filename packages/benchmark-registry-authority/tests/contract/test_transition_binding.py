"""One structural representation per transition, shipped as an asserted mapping."""

from __future__ import annotations

import pytest

import _builders as fx
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_REGISTRATION_TRANSITIONS,
    BENCHMARK_TRANSITION_PAYLOAD_BINDING,
    BENCHMARK_UNBOUND_PAYLOAD_TYPES,
    BenchmarkAdmissionDecisionPayload,
    BenchmarkAdmissionOutcome,
    BenchmarkConflictRecordPayload,
    BenchmarkPostAdmissionRejectionEventPayload,
    BenchmarkRegistrationEventPayload,
    BenchmarkRegistrationState,
    BenchmarkRegistryLifecycleError,
    BenchmarkRegistryRefusalReason,
    BenchmarkRevocationEventPayload,
    BenchmarkSubmissionRecordPayload,
    bound_payload_for_transition,
    require_bound_payload_for_transition,
)

S = BenchmarkRegistrationState
O = BenchmarkAdmissionOutcome  # noqa: E741

EXPECTED = {
    (None, S.SUBMITTED): (BenchmarkSubmissionRecordPayload, None),
    (S.SUBMITTED, S.ADMITTED): (BenchmarkAdmissionDecisionPayload, O.ADMITTED),
    (S.SUBMITTED, S.REJECTED): (BenchmarkAdmissionDecisionPayload, O.REJECTED),
    (S.ADMITTED, S.REJECTED): (BenchmarkPostAdmissionRejectionEventPayload, None),
    (S.ADMITTED, S.REGISTERED): (BenchmarkRegistrationEventPayload, None),
    (S.REGISTERED, S.REVOKED): (BenchmarkRevocationEventPayload, None),
}

VALID_CASES = [
    ((None, S.SUBMITTED), fx.submission_record),
    ((S.SUBMITTED, S.ADMITTED), fx.admission_decision),
    ((S.SUBMITTED, S.REJECTED), fx.rejected_admission_decision),
    ((S.ADMITTED, S.REJECTED), fx.post_admission_rejection),
    ((S.ADMITTED, S.REGISTERED), fx.registration_event),
    ((S.REGISTERED, S.REVOKED), fx.revocation_event),
]


def test_happy_the_binding_is_exactly_the_ratified_six_rows():
    assert dict(BENCHMARK_TRANSITION_PAYLOAD_BINDING) == EXPECTED


@pytest.mark.parametrize(
    "transition,builder", VALID_CASES, ids=[str(t) for t, _ in VALID_CASES]
)
def test_happy_each_transition_accepts_its_bound_payload(transition, builder):
    require_bound_payload_for_transition(*transition, builder())


def test_the_binding_is_immutable():
    with pytest.raises(TypeError):
        BENCHMARK_TRANSITION_PAYLOAD_BINDING[(None, S.SUBMITTED)] = (int, None)


def test_every_admissible_arrow_has_exactly_one_bound_representation():
    arrows = {
        (a, b)
        for a, successors in BENCHMARK_REGISTRATION_TRANSITIONS.items()
        for b in successors
    }
    bound = {k for k in BENCHMARK_TRANSITION_PAYLOAD_BINDING if k[0] is not None}
    assert arrows == bound


def test_no_transition_accepts_a_second_payload_type():
    for transition, builder in VALID_CASES:
        for _other_transition, other_builder in VALID_CASES:
            payload = other_builder()
            expected_cls, required_outcome = BENCHMARK_TRANSITION_PAYLOAD_BINDING[
                transition
            ]
            matches = type(payload) is expected_cls and (
                required_outcome is None
                or getattr(payload, "declared_outcome", None) is required_outcome
            )
            if matches:
                continue
            with pytest.raises(BenchmarkRegistryLifecycleError):
                require_bound_payload_for_transition(*transition, payload)


def test_no_payload_type_may_serve_a_transition_it_is_not_bound_to():
    with pytest.raises(BenchmarkRegistryLifecycleError):
        require_bound_payload_for_transition(
            S.ADMITTED, S.REGISTERED, fx.revocation_event()
        )
    with pytest.raises(BenchmarkRegistryLifecycleError):
        require_bound_payload_for_transition(
            S.REGISTERED, S.REVOKED, fx.registration_event()
        )


def test_the_two_admission_transitions_are_separated_by_declared_outcome():
    with pytest.raises(BenchmarkRegistryLifecycleError) as excinfo:
        require_bound_payload_for_transition(
            S.SUBMITTED, S.ADMITTED, fx.rejected_admission_decision()
        )
    assert "declared_outcome=ADMITTED" in str(excinfo.value)
    with pytest.raises(BenchmarkRegistryLifecycleError):
        require_bound_payload_for_transition(
            S.SUBMITTED, S.REJECTED, fx.admission_decision()
        )


def test_an_unbound_transition_has_no_representation():
    assert bound_payload_for_transition(S.REVOKED, S.REGISTERED) is None
    with pytest.raises(BenchmarkRegistryLifecycleError) as excinfo:
        require_bound_payload_for_transition(
            S.REVOKED, S.REGISTERED, fx.registration_event()
        )
    assert excinfo.value.reason is (
        BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION
    )


def test_a_subclass_of_the_bound_type_is_refused():
    import dataclasses

    genuine = fx.registration_event()
    subclass = dataclasses.dataclass(frozen=True)(
        type("SubRegistration", (type(genuine),), {})
    )
    forged = subclass(
        **{f.name: getattr(genuine, f.name) for f in dataclasses.fields(genuine)}
    )
    with pytest.raises(BenchmarkRegistryLifecycleError):
        require_bound_payload_for_transition(S.ADMITTED, S.REGISTERED, forged)


def test_the_conflict_record_is_bound_to_no_transition():
    assert BENCHMARK_UNBOUND_PAYLOAD_TYPES == (BenchmarkConflictRecordPayload,)
    for transition in EXPECTED:
        with pytest.raises(BenchmarkRegistryLifecycleError):
            require_bound_payload_for_transition(*transition, fx.conflict_record())


def test_only_the_initial_transition_has_a_none_predecessor():
    none_keys = [k for k in BENCHMARK_TRANSITION_PAYLOAD_BINDING if k[0] is None]
    assert none_keys == [(None, S.SUBMITTED)]


def test_a_bare_string_state_is_refused_by_the_binding_lookup():
    from ugence_benchmark_registry_authority.api import (
        BenchmarkRegistryContractError,
    )

    with pytest.raises(BenchmarkRegistryContractError):
        bound_payload_for_transition("SUBMITTED", S.ADMITTED)
