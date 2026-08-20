"""BR-2B's planning functions: total, pure, and unable to cause anything."""

from __future__ import annotations

import dataclasses
import pathlib

import pytest

import _builders as fx
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_REGISTRATION_TRANSITIONS,
    BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES,
    BenchmarkRegistrationRecordPresence,
    BenchmarkRegistrationState,
    BenchmarkRegistryContractError,
    BenchmarkRegistryRefusalReason,
    BenchmarkTransitionPlan,
    BenchmarkTransitionRefusal,
    canonical_bytes,
    is_byte_identical_resubmission,
    plan_submission_outcome,
    plan_transition,
)

_S = BenchmarkRegistrationState
_P = BenchmarkRegistrationRecordPresence
_R = BenchmarkRegistryRefusalReason

SRC = (
    pathlib.Path(__file__).resolve().parents[2]
    / "src"
    / "ugence_benchmark_registry_authority"
)

ALL_PAIRS = [
    (a, b) for a in BenchmarkRegistrationState for b in BenchmarkRegistrationState
]


def _occupied(**overrides):
    return fx.snapshot_assertion(**overrides)


def test_happy_an_admissible_move_yields_a_plan():
    outcome = plan_transition(_occupied(), _S.REGISTERED)
    assert isinstance(outcome, BenchmarkTransitionPlan)
    assert outcome.planned_to_state is _S.REGISTERED


# --------------------------------------------------------------------------- #
# Total: a plan or a refusal, never an exception and never a third thing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("from_state,to_state", ALL_PAIRS)
def test_plan_transition_is_total_over_the_whole_vocabulary(from_state, to_state):
    outcome = plan_transition(
        _occupied(asserted_current_state=from_state), to_state
    )
    assert isinstance(
        outcome, (BenchmarkTransitionPlan, BenchmarkTransitionRefusal)
    )
    admitted = to_state in BENCHMARK_REGISTRATION_TRANSITIONS[from_state]
    if admitted and not (
        from_state is _S.ADMITTED and to_state is _S.REJECTED
    ):
        assert isinstance(outcome, BenchmarkTransitionPlan)
    elif not admitted:
        assert isinstance(outcome, BenchmarkTransitionRefusal)


@pytest.mark.parametrize("from_state,to_state", ALL_PAIRS)
def test_a_refusal_always_carries_a_ratified_reason(from_state, to_state):
    outcome = plan_transition(
        _occupied(asserted_current_state=from_state), to_state
    )
    if isinstance(outcome, BenchmarkTransitionRefusal):
        assert outcome.declared_refusal_reason in set(
            BenchmarkRegistryRefusalReason
        )


def test_an_inadmissible_move_is_refused_rather_than_raised():
    outcome = plan_transition(_occupied(asserted_current_state=_S.REVOKED), _S.REGISTERED)
    assert isinstance(outcome, BenchmarkTransitionRefusal)
    assert outcome.declared_refusal_reason is _R.UNAUTHORIZED_TRANSITION


def test_the_post_admission_record_gate_survives_the_total_layer():
    """Wrapping the constructor must not soften the gate it wraps."""

    refused = plan_transition(
        _occupied(
            asserted_current_state=_S.ADMITTED,
            asserted_registration_record_presence=_P.RECORD_APPENDED,
        ),
        _S.REJECTED,
    )
    assert isinstance(refused, BenchmarkTransitionRefusal)
    assert refused.declared_refusal_reason is _R.LIFECYCLE_CONFLICT

    planned = plan_transition(
        _occupied(
            asserted_current_state=_S.ADMITTED,
            asserted_registration_record_presence=_P.NO_RECORD_APPENDED,
        ),
        _S.REJECTED,
    )
    assert isinstance(planned, BenchmarkTransitionPlan)


# --------------------------------------------------------------------------- #
# Fail closed on anything malformed
# --------------------------------------------------------------------------- #
def test_a_bare_string_state_is_refused_not_coerced():
    with pytest.raises(BenchmarkRegistryContractError):
        plan_transition(_occupied(), "REGISTERED")


def test_a_foreign_snapshot_is_refused_by_exact_type():
    @dataclasses.dataclass(frozen=True)
    class Lookalike:
        coordinate: object
        asserted_current_state: object
        asserted_registration_record_presence: object

    impostor = Lookalike(
        coordinate=fx.coordinate(),
        asserted_current_state=_S.ADMITTED,
        asserted_registration_record_presence=_P.NO_RECORD_APPENDED,
    )
    with pytest.raises(BenchmarkRegistryContractError):
        plan_transition(impostor, _S.REGISTERED)
    with pytest.raises(BenchmarkRegistryContractError):
        plan_submission_outcome(impostor, fx.submission_record())


def test_neither_bytes_nor_a_digest_may_stand_in_for_a_record():
    record = fx.submission_record()
    for impostor in (canonical_bytes(record), "a1" * 32, None, 7):
        with pytest.raises(BenchmarkRegistryContractError):
            is_byte_identical_resubmission(record, impostor)
        with pytest.raises(BenchmarkRegistryContractError):
            is_byte_identical_resubmission(impostor, record)


# --------------------------------------------------------------------------- #
# Idempotence compares canonical BYTES, recomputed here
# --------------------------------------------------------------------------- #
def test_two_equal_records_are_byte_identical():
    assert is_byte_identical_resubmission(
        fx.submission_record(), fx.submission_record()
    )


def test_one_changed_field_makes_them_not_byte_identical():
    assert not is_byte_identical_resubmission(
        fx.submission_record(),
        fx.submission_record(declared_recorded_at=fx.AS_OF),
    )


def test_the_comparison_is_over_bytes_and_not_over_digests():
    """D-06 says bytes, so the source must compare bytes.

    A digest comparison would pass every behavioural test here while being the
    thing the ruling excludes, so this is asserted structurally: the planning
    module reaches for ``canonical_bytes`` and never for ``canonical_digest``.
    """

    source = (SRC / "contracts" / "planning.py").read_text()
    body = source.split('"""', 2)[-1]
    assert "canonical_bytes(" in body
    assert "canonical_digest" not in body


def test_the_functions_are_pure_and_mutate_no_argument():
    snapshot = _occupied()
    proposed, occupant = fx.submission_record(), fx.submission_record()
    before = (
        canonical_bytes(snapshot),
        canonical_bytes(proposed),
        canonical_bytes(occupant),
    )
    first = plan_submission_outcome(snapshot, proposed, occupant)
    second = plan_submission_outcome(snapshot, proposed, occupant)
    after = (
        canonical_bytes(snapshot),
        canonical_bytes(proposed),
        canonical_bytes(occupant),
    )
    assert before == after
    assert canonical_bytes(first) == canonical_bytes(second)


# --------------------------------------------------------------------------- #
# Submission outcomes — D-05 and D-06's calculation, none of its consequences
# --------------------------------------------------------------------------- #
def test_an_unoccupied_slot_yields_the_initial_plan():
    outcome = plan_submission_outcome(
        fx.unoccupied_assertion(), fx.submission_record()
    )
    assert isinstance(outcome, BenchmarkTransitionPlan)
    assert outcome.planned_to_state is _S.SUBMITTED
    assert outcome.planned_payload_type_name == "BenchmarkSubmissionRecordPayload"


def test_a_byte_identical_resubmission_is_the_idempotent_refusal():
    outcome = plan_submission_outcome(
        _occupied(), fx.submission_record(), fx.submission_record()
    )
    assert isinstance(outcome, BenchmarkTransitionRefusal)
    assert outcome.declared_refusal_reason is _R.IDEMPOTENT_DUPLICATE


def test_a_different_submission_at_one_locator_is_a_typed_conflict():
    outcome = plan_submission_outcome(
        _occupied(),
        fx.submission_record(declared_recorded_at=fx.AS_OF),
        fx.submission_record(),
    )
    assert isinstance(outcome, BenchmarkTransitionRefusal)
    assert outcome.declared_refusal_reason is _R.COORDINATE_SLOT_CONFLICT


def test_last_writer_wins_is_not_among_the_outcomes():
    """Every non-identical submission at an occupied slot is refused."""

    for changed in ("declared_registry_authority_identity",):
        outcome = plan_submission_outcome(
            _occupied(),
            fx.submission_record(**{changed: "someone-else"}),
            fx.submission_record(),
        )
        assert isinstance(outcome, BenchmarkTransitionRefusal)


def test_the_same_identity_digest_under_another_locator_is_aliasing():
    other = fx.coordinate(benchmark_version="9.9.9")
    proposed = fx.submission_record(
        publisher_submission_envelope=fx.publisher_envelope(coordinate=other)
    )
    outcome = plan_submission_outcome(_occupied(), proposed, fx.submission_record())
    assert isinstance(outcome, BenchmarkTransitionRefusal)
    assert outcome.declared_refusal_reason is _R.DIGEST_ALREADY_BOUND


def test_an_unequal_locator_routed_as_a_collision_is_rejection_only():
    other = fx.coordinate(benchmark_version="9.9.9")
    proposed = fx.submission_record(
        publisher_submission_envelope=fx.publisher_envelope(
            coordinate=other, benchmark_identity_digest="d4" * 32
        )
    )
    outcome = plan_submission_outcome(_occupied(), proposed, fx.submission_record())
    assert isinstance(outcome, BenchmarkTransitionRefusal)
    assert outcome.declared_refusal_reason is _R.CONFUSABLE_COORDINATE


def test_the_confusable_refusal_rewrites_neither_locator():
    """Rejection-only: no normalization, no casefolding, nothing stored."""

    other = fx.coordinate(benchmark_version="9.9.9")
    proposed = fx.submission_record(
        publisher_submission_envelope=fx.publisher_envelope(
            coordinate=other, benchmark_identity_digest="d4" * 32
        )
    )
    snapshot = _occupied()
    outcome = plan_submission_outcome(snapshot, proposed, fx.submission_record())
    assert outcome.snapshot.coordinate == snapshot.coordinate
    assert proposed.publisher_submission_envelope.coordinate == other


def test_no_confusable_algorithm_is_claimed_by_the_planner():
    from ugence_benchmark_registry_authority.api import (
        BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT as contract,
    )

    assert contract["algorithm_identifier"] is None
    assert contract["unicode_version"] is None
    assert contract["rewrite_permitted"] is False


# --------------------------------------------------------------------------- #
# Self-inconsistent assertions fail closed
# --------------------------------------------------------------------------- #
def test_an_unoccupied_slot_handed_an_occupant_fails_closed():
    outcome = plan_submission_outcome(
        fx.unoccupied_assertion(), fx.submission_record(), fx.submission_record()
    )
    assert isinstance(outcome, BenchmarkTransitionRefusal)
    assert outcome.declared_refusal_reason is _R.STALE_REGISTRY_SNAPSHOT


def test_an_occupied_slot_handed_no_occupant_fails_closed():
    outcome = plan_submission_outcome(_occupied(), fx.submission_record())
    assert isinstance(outcome, BenchmarkTransitionRefusal)
    assert outcome.declared_refusal_reason is _R.STALE_REGISTRY_SNAPSHOT


def test_an_occupant_at_another_locator_fails_closed():
    elsewhere = fx.submission_record(
        publisher_submission_envelope=fx.publisher_envelope(
            coordinate=fx.coordinate(benchmark_version="7.7.7")
        )
    )
    outcome = plan_submission_outcome(_occupied(), fx.submission_record(), elsewhere)
    assert isinstance(outcome, BenchmarkTransitionRefusal)
    assert outcome.declared_refusal_reason is _R.STALE_REGISTRY_SNAPSHOT


# --------------------------------------------------------------------------- #
# Nothing planned is authoritative, and nothing consumes a plan
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("to_state", list(BenchmarkRegistrationState))
def test_every_outcome_derives_the_five_false_properties(to_state):
    outcome = plan_transition(_occupied(), to_state)
    for prop in BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES:
        assert getattr(outcome, prop) is False


def test_the_planning_module_exports_no_function_taking_a_plan():
    import inspect

    from ugence_benchmark_registry_authority.contracts import planning

    for name in planning.__all__:
        value = getattr(planning, name)
        if not inspect.isfunction(value):
            continue
        for parameter in inspect.signature(value).parameters.values():
            assert "BenchmarkTransitionPlan" not in str(parameter.annotation), name


def test_the_planning_module_names_no_authoritative_verb():
    forbidden = (
        "apply",
        "commit",
        "append",
        "admit",
        "register",
        "revoke",
        "resolve",
        "persist",
        "write",
    )
    from ugence_benchmark_registry_authority.contracts import planning

    for name in planning.__all__:
        lowered = name.lower()
        for verb in forbidden:
            assert verb not in lowered, name


def test_the_planner_reads_no_clock_and_holds_no_store():
    source = (SRC / "contracts" / "planning.py").read_text()
    body = source.split('"""', 2)[-1]
    for banned in ("datetime.now", "time.time", ".now(", "Port", "import os"):
        assert banned not in body, banned
