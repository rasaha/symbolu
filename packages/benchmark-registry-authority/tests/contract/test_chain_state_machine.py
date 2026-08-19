"""The nine state-machine properties §19 specifies, each proved.

1. every transition accepts only its exact predecessor state and predecessor type;
2. every non-initial ``prev_event_digest`` is independently recomputed and
   mandatory, and only the initial submission record permits ``None``;
3. post-admission rejection refuses a predecessor whose ``declared_outcome`` is
   not ``ADMITTED``;
4. registration refuses a predecessor whose ``declared_outcome`` is ``REJECTED``;
5. neither rejection representation can acquire a successor;
6. neither rejection path can substitute for the other;
7. no single payload can represent transitions having incompatible predecessors;
8. corrupting a predecessor's ``declared_outcome`` or its digest is detected by
   graph revalidation before any byte is produced;
9. the closed relation admits no reverse arrow and no self-transition.
"""

from __future__ import annotations

import dataclasses
import itertools

import pytest

import _builders as fx
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_REGISTRATION_TRANSITIONS,
    BENCHMARK_TERMINAL_REGISTRATION_STATES,
    BenchmarkAdmissionDecisionPayload,
    BenchmarkAdmissionOutcome,
    BenchmarkConflictRecordPayload,
    BenchmarkPostAdmissionRejectionEventPayload,
    BenchmarkRegistrationEventPayload,
    BenchmarkRegistrationState,
    BenchmarkRegistryCanonicalizationError,
    BenchmarkRegistryContractError,
    BenchmarkRegistryLifecycleError,
    BenchmarkRegistryRefusalReason,
    BenchmarkRevocationEventPayload,
    BenchmarkSubmissionRecordPayload,
    canonical_bytes,
    canonical_digest,
    is_valid_registration_transition,
    require_valid_registration_transition,
)

S = BenchmarkRegistrationState
O = BenchmarkAdmissionOutcome  # noqa: E741

ALL_PAYLOADS = (
    ("BenchmarkSubmissionRecordPayload", fx.submission_record),
    ("BenchmarkAdmissionDecisionPayload", fx.admission_decision),
    ("BenchmarkPostAdmissionRejectionEventPayload", fx.post_admission_rejection),
    ("BenchmarkRegistrationEventPayload", fx.registration_event),
    ("BenchmarkRevocationEventPayload", fx.revocation_event),
    ("BenchmarkConflictRecordPayload", fx.conflict_record),
)

NON_INITIAL = [p for p in ALL_PAYLOADS if p[0] != "BenchmarkSubmissionRecordPayload"]


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #
def test_happy_the_whole_chain_constructs_end_to_end():
    event = fx.revocation_event()
    assert event.declared_state is S.REVOKED
    assert event.registration_event.declared_state is S.REGISTERED
    assert event.registration_event.admission_decision.declared_state is S.ADMITTED
    assert (
        event.registration_event.admission_decision.submission_record.declared_state
        is S.SUBMITTED
    )


def test_happy_the_five_states_are_exactly_the_ratified_five():
    assert [s.value for s in BenchmarkRegistrationState] == [
        "SUBMITTED",
        "ADMITTED",
        "REGISTERED",
        "REVOKED",
        "REJECTED",
    ]


# --------------------------------------------------------------------------- #
# 1 · exact predecessor state and predecessor type
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,builder", ALL_PAYLOADS)
def test_no_payload_accepts_a_predecessor_of_the_wrong_exact_type(name, builder):
    """Every nested predecessor field refuses every other payload type."""

    genuine = builder()
    nested = [
        f.name
        for f in dataclasses.fields(genuine)
        if dataclasses.is_dataclass(getattr(genuine, f.name))
    ]
    assert nested, name
    for field_name in nested:
        for _other_name, other_builder in ALL_PAYLOADS:
            other = other_builder()
            if type(other) is type(getattr(genuine, field_name)):
                continue
            kwargs = {
                f.name: getattr(genuine, f.name)
                for f in dataclasses.fields(genuine)
            }
            kwargs[field_name] = other
            with pytest.raises(BenchmarkRegistryContractError):
                type(genuine)(**kwargs)


def test_the_submission_record_refuses_a_payload_where_an_envelope_belongs():
    with pytest.raises(BenchmarkRegistryContractError):
        BenchmarkSubmissionRecordPayload(
            publisher_submission_envelope=fx.approval_envelope(),
            declared_registry_authority_identity=fx.REGISTRY_AUTHORITY_IDENTITY,
            declared_recorded_at=fx.RECORDED_AT,
        )


# --------------------------------------------------------------------------- #
# 2 · prev_event_digest is mandatory, derived, and None in exactly one place
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,builder", ALL_PAYLOADS)
def test_every_payload_always_exposes_prev_event_digest(name, builder):
    payload = builder()
    assert hasattr(payload, "prev_event_digest")
    assert isinstance(type(payload).prev_event_digest, property)


def test_only_the_initial_submission_record_derives_none():
    assert fx.submission_record().prev_event_digest is None
    for name, builder in NON_INITIAL:
        assert builder().prev_event_digest is not None, name


@pytest.mark.parametrize("name,builder", NON_INITIAL)
def test_every_non_initial_prev_event_digest_equals_the_recomputed_predecessor(
    name, builder
):
    payload = builder()
    predecessor = next(
        getattr(payload, f.name)
        for f in dataclasses.fields(payload)
        if dataclasses.is_dataclass(getattr(payload, f.name))
        and type(getattr(payload, f.name)).__name__.endswith("Payload")
    )
    assert payload.prev_event_digest == canonical_digest(predecessor)


@pytest.mark.parametrize("name,builder", ALL_PAYLOADS)
def test_prev_event_digest_is_never_a_constructor_field(name, builder):
    assert "prev_event_digest" not in {
        f.name for f in dataclasses.fields(builder())
    }


@pytest.mark.parametrize("name,builder", ALL_PAYLOADS)
def test_prev_event_digest_cannot_be_assigned(name, builder):
    payload = builder()
    with pytest.raises(AttributeError):
        object.__setattr__(payload, "prev_event_digest", "0" * 64)


# --------------------------------------------------------------------------- #
# 3 and 4 · predecessor declared_outcome gates
# --------------------------------------------------------------------------- #
def test_post_admission_rejection_refuses_a_rejected_predecessor():
    with pytest.raises(BenchmarkRegistryLifecycleError) as excinfo:
        BenchmarkPostAdmissionRejectionEventPayload(
            admission_decision=fx.rejected_admission_decision(),
            declared_refusal_reason=BenchmarkRegistryRefusalReason.NOT_ADMITTED,
            declared_recorded_at=fx.RECORDED_AT,
        )
    assert "declared_outcome=ADMITTED" in str(excinfo.value)


def test_registration_refuses_a_rejected_predecessor():
    with pytest.raises(BenchmarkRegistryLifecycleError) as excinfo:
        BenchmarkRegistrationEventPayload(
            admission_decision=fx.rejected_admission_decision(),
            declared_recorded_at=fx.RECORDED_AT,
        )
    assert "declared_outcome=ADMITTED" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# 5 · neither rejection representation can acquire a successor
# --------------------------------------------------------------------------- #
def test_a_rejected_admission_decision_is_unnestable_by_every_later_payload():
    rejected = fx.rejected_admission_decision()
    for cls, kwargs in (
        (
            BenchmarkRegistrationEventPayload,
            dict(admission_decision=rejected, declared_recorded_at=fx.RECORDED_AT),
        ),
        (
            BenchmarkPostAdmissionRejectionEventPayload,
            dict(
                admission_decision=rejected,
                declared_refusal_reason=(
                    BenchmarkRegistryRefusalReason.NOT_ADMITTED
                ),
                declared_recorded_at=fx.RECORDED_AT,
            ),
        ),
    ):
        with pytest.raises(BenchmarkRegistryLifecycleError):
            cls(**kwargs)


def test_a_post_admission_rejection_event_has_no_field_anywhere_that_accepts_it():
    """Structural absence, not a runtime check: there is nothing to populate."""

    rejection = fx.post_admission_rejection()
    for _name, builder in ALL_PAYLOADS:
        genuine = builder()
        for f in dataclasses.fields(genuine):
            if type(getattr(genuine, f.name)) is type(rejection):
                pytest.fail(
                    f"{type(genuine).__name__}.{f.name} accepts a "
                    "post-admission rejection event; it is terminal and must "
                    "be unnestable"
                )


def test_a_post_admission_rejection_event_is_refused_where_a_decision_belongs():
    rejection = fx.post_admission_rejection()
    for cls, key, extra in (
        (BenchmarkRegistrationEventPayload, "admission_decision", {}),
        (
            BenchmarkPostAdmissionRejectionEventPayload,
            "admission_decision",
            {
                "declared_refusal_reason": (
                    BenchmarkRegistryRefusalReason.NOT_ADMITTED
                )
            },
        ),
    ):
        with pytest.raises(BenchmarkRegistryContractError):
            cls(**{key: rejection, "declared_recorded_at": fx.RECORDED_AT, **extra})


@pytest.mark.parametrize(
    "name,builder",
    [
        ("BenchmarkPostAdmissionRejectionEventPayload", fx.post_admission_rejection),
        ("BenchmarkRevocationEventPayload", fx.revocation_event),
        ("BenchmarkConflictRecordPayload", fx.conflict_record),
    ],
)
def test_every_terminal_payload_reports_itself_terminal(name, builder):
    assert builder().is_terminal is True


def test_a_rejected_admission_decision_reports_itself_terminal():
    assert fx.rejected_admission_decision().is_terminal is True
    assert fx.admission_decision().is_terminal is False


# --------------------------------------------------------------------------- #
# 6 · the two rejection paths cannot substitute for one another
# --------------------------------------------------------------------------- #
def test_the_two_rejection_representations_are_different_exact_types():
    assert type(fx.rejected_admission_decision()) is not type(
        fx.post_admission_rejection()
    )


def test_the_two_rejection_representations_have_different_domains_and_digests():
    import json

    a = json.loads(canonical_bytes(fx.rejected_admission_decision()))
    b = json.loads(canonical_bytes(fx.post_admission_rejection()))
    assert a["domain"] != b["domain"]
    assert a["type"] != b["type"]
    assert canonical_digest(fx.rejected_admission_decision()) != canonical_digest(
        fx.post_admission_rejection()
    )


def test_the_two_rejection_representations_have_different_predecessors():
    """Which is why one type could never serve both transitions."""

    assert fx.rejected_admission_decision().prev_event_digest == canonical_digest(
        fx.submission_record()
    )
    assert fx.post_admission_rejection().prev_event_digest == canonical_digest(
        fx.admission_decision()
    )


# --------------------------------------------------------------------------- #
# 7 · no payload represents transitions with incompatible predecessors
# --------------------------------------------------------------------------- #
def test_the_admission_decision_cannot_represent_the_post_admission_rejection():
    """Its predecessor is a submission record; the other's is an admitted decision."""

    decision = fx.admission_decision()
    nested_types = {
        type(getattr(decision, f.name)).__name__
        for f in dataclasses.fields(decision)
        if dataclasses.is_dataclass(getattr(decision, f.name))
    }
    assert nested_types == {
        "BenchmarkSubmissionRecordPayload",
        "BenchmarkApprovalEnvelope",
    }
    assert "BenchmarkAdmissionDecisionPayload" not in nested_types


def test_an_admitted_decision_carries_no_refusal_reason_and_a_rejected_one_must():
    with pytest.raises(BenchmarkRegistryLifecycleError):
        BenchmarkAdmissionDecisionPayload(
            submission_record=fx.submission_record(),
            approval_envelope=fx.approval_envelope(),
            declared_outcome=O.REJECTED,
            declared_recorded_at=fx.RECORDED_AT,
        )
    with pytest.raises(BenchmarkRegistryLifecycleError):
        BenchmarkAdmissionDecisionPayload(
            submission_record=fx.submission_record(),
            approval_envelope=fx.approval_envelope(),
            declared_outcome=O.ADMITTED,
            declared_recorded_at=fx.RECORDED_AT,
            declared_refusal_reason=(
                BenchmarkRegistryRefusalReason.PUBLISHER_UNTRUSTED
            ),
        )


# --------------------------------------------------------------------------- #
# 8 · corruption is caught by graph revalidation before any byte
# --------------------------------------------------------------------------- #
def test_corrupting_a_predecessor_outcome_is_caught_before_any_byte():
    event = fx.registration_event()
    object.__setattr__(event.admission_decision, "declared_outcome", O.REJECTED)
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(event)


def test_corrupting_a_predecessor_outcome_is_caught_for_the_rejection_event_too():
    event = fx.post_admission_rejection()
    object.__setattr__(event.admission_decision, "declared_outcome", O.REJECTED)
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(event)


def test_corrupting_a_predecessor_digest_input_is_caught_before_any_byte():
    """There is no digest field to corrupt, so corrupt what the digest is over."""

    event = fx.revocation_event()
    object.__setattr__(
        event.registration_event.admission_decision.submission_record,
        "declared_registry_authority_identity",
        "",
    )
    with pytest.raises(BenchmarkRegistryCanonicalizationError):
        canonical_bytes(event)


def test_corruption_changes_the_derived_digest_when_it_is_still_valid():
    """A *valid* substitution moves the digest; an invalid one is refused."""

    event = fx.registration_event()
    before = event.prev_event_digest
    object.__setattr__(
        event.admission_decision, "declared_recorded_at", fx.VALIDITY_FROM
    )
    assert event.prev_event_digest != before


# --------------------------------------------------------------------------- #
# 9 · the closed relation
# --------------------------------------------------------------------------- #
def test_every_state_is_a_key_and_terminal_states_map_to_an_empty_set():
    assert set(BENCHMARK_REGISTRATION_TRANSITIONS) == set(BenchmarkRegistrationState)
    for state in BENCHMARK_TERMINAL_REGISTRATION_STATES:
        assert BENCHMARK_REGISTRATION_TRANSITIONS[state] == frozenset()


def test_the_full_five_by_five_matrix_admits_exactly_five_arrows():
    admitted = [
        (a, b)
        for a, b in itertools.product(BenchmarkRegistrationState, repeat=2)
        if is_valid_registration_transition(a, b)
    ]
    assert set(admitted) == {
        (S.SUBMITTED, S.ADMITTED),
        (S.SUBMITTED, S.REJECTED),
        (S.ADMITTED, S.REGISTERED),
        (S.ADMITTED, S.REJECTED),
        (S.REGISTERED, S.REVOKED),
    }


def test_no_self_transition_is_admissible():
    for state in BenchmarkRegistrationState:
        assert not is_valid_registration_transition(state, state)


def test_no_reverse_arrow_exists():
    for a, b in itertools.product(BenchmarkRegistrationState, repeat=2):
        if is_valid_registration_transition(a, b):
            assert not is_valid_registration_transition(b, a), (a, b)


def test_an_inadmissible_transition_raises_with_the_typed_reason():
    with pytest.raises(BenchmarkRegistryLifecycleError) as excinfo:
        require_valid_registration_transition(S.REVOKED, S.REGISTERED)
    assert excinfo.value.reason is (
        BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION
    )


def test_a_terminal_state_lookup_answers_rather_than_raising():
    assert BENCHMARK_REGISTRATION_TRANSITIONS[S.REVOKED] == frozenset()
    assert BENCHMARK_REGISTRATION_TRANSITIONS[S.REJECTED] == frozenset()


def test_a_bare_string_spelling_of_a_state_is_refused():
    with pytest.raises(BenchmarkRegistryContractError):
        is_valid_registration_transition("SUBMITTED", S.ADMITTED)


def test_the_relation_mapping_is_immutable():
    with pytest.raises(TypeError):
        BENCHMARK_REGISTRATION_TRANSITIONS[S.REVOKED] = frozenset({S.REGISTERED})


def test_the_conflict_record_is_outside_the_chain_and_carries_no_state():
    record = fx.conflict_record()
    assert not hasattr(record, "declared_state")
    assert record.is_terminal is True
    assert isinstance(record, BenchmarkConflictRecordPayload)


def test_a_revocation_event_cannot_be_built_on_anything_but_a_registration():
    with pytest.raises(BenchmarkRegistryContractError):
        BenchmarkRevocationEventPayload(
            registration_event=fx.admission_decision(),
            revocation_envelope=fx.revocation_envelope(),
            declared_recorded_at=fx.RECORDED_AT,
        )
