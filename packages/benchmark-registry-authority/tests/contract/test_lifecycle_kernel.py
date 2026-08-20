"""BR-2B's kernel contracts: a plan is not a transition, and cannot pretend to be.

The governing rule these properties enforce is D-01 as amended: *BR-2B may
determine what transition would be valid; BR-2D is the first phase permitted to
assert that a transition occurred.*
"""

from __future__ import annotations

import dataclasses

import pytest

import _builders as fx
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_REGISTRATION_TRANSITIONS,
    BENCHMARK_TRANSITION_PAYLOAD_BINDING,
    BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES,
    BenchmarkRegistrationRecordPresence,
    BenchmarkRegistrationState,
    BenchmarkRegistryContractError,
    BenchmarkRegistryLifecycleError,
    BenchmarkRegistryRefusalReason,
    BenchmarkRegistrySnapshotAssertion,
    BenchmarkTransitionPlan,
    BenchmarkTransitionRefusal,
    canonical_digest,
)

_S = BenchmarkRegistrationState
_P = BenchmarkRegistrationRecordPresence

KERNEL_BUILDERS = (
    ("BenchmarkRegistrySnapshotAssertion", fx.snapshot_assertion),
    ("BenchmarkTransitionPlan", fx.transition_plan),
    ("BenchmarkTransitionRefusal", fx.transition_refusal),
)

#: Every ordered state pair the closed relation does **not** admit.
INADMISSIBLE_PAIRS = [
    (a, b)
    for a in BenchmarkRegistrationState
    for b in BenchmarkRegistrationState
    if b not in BENCHMARK_REGISTRATION_TRANSITIONS[a]
]


def test_happy_all_three_kernel_contracts_construct_and_canonicalize():
    for name, builder in KERNEL_BUILDERS:
        raw = canonical_digest(builder())
        assert len(raw) == 64, name


# --------------------------------------------------------------------------- #
# A plan for an inadmissible move does not exist
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("from_state,to_state", INADMISSIBLE_PAIRS)
def test_no_plan_exists_for_a_move_the_closed_relation_refuses(
    from_state, to_state
):
    """Unconstructible, not merely refusable — there is no invalid-plan object."""

    snapshot = fx.snapshot_assertion(asserted_current_state=from_state)
    with pytest.raises(BenchmarkRegistryLifecycleError) as caught:
        BenchmarkTransitionPlan(snapshot=snapshot, planned_to_state=to_state)
    assert caught.value.reason in (
        BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION,
        BenchmarkRegistryRefusalReason.LIFECYCLE_CONFLICT,
    )


@pytest.mark.parametrize("terminal", [_S.REVOKED, _S.REJECTED])
def test_a_terminal_state_admits_no_plan_at_all(terminal):
    snapshot = fx.snapshot_assertion(asserted_current_state=terminal)
    for to_state in BenchmarkRegistrationState:
        with pytest.raises(BenchmarkRegistryLifecycleError):
            BenchmarkTransitionPlan(
                snapshot=snapshot, planned_to_state=to_state
            )


@pytest.mark.parametrize("state", list(BenchmarkRegistrationState))
def test_no_self_transition_can_be_planned(state):
    """An event that changed nothing must not be appendable to an append-only log."""

    snapshot = fx.snapshot_assertion(asserted_current_state=state)
    with pytest.raises(BenchmarkRegistryLifecycleError):
        BenchmarkTransitionPlan(snapshot=snapshot, planned_to_state=state)


# --------------------------------------------------------------------------- #
# The one gate the closed relation cannot express
# --------------------------------------------------------------------------- #
def test_post_admission_rejection_is_planned_only_while_nothing_is_registered():
    permitted = BenchmarkTransitionPlan(
        snapshot=fx.snapshot_assertion(
            asserted_current_state=_S.ADMITTED,
            asserted_registration_record_presence=_P.NO_RECORD_APPENDED,
        ),
        planned_to_state=_S.REJECTED,
    )
    assert permitted.planned_to_state is _S.REJECTED

    with pytest.raises(BenchmarkRegistryLifecycleError) as caught:
        BenchmarkTransitionPlan(
            snapshot=fx.snapshot_assertion(
                asserted_current_state=_S.ADMITTED,
                asserted_registration_record_presence=_P.RECORD_APPENDED,
            ),
            planned_to_state=_S.REJECTED,
        )
    assert caught.value.reason is (
        BenchmarkRegistryRefusalReason.LIFECYCLE_CONFLICT
    )


def test_an_appended_record_does_not_block_any_other_admissible_arrow():
    """The gate is specific to ADMITTED -> REJECTED, and must not over-reach."""

    plan = BenchmarkTransitionPlan(
        snapshot=fx.snapshot_assertion(
            asserted_current_state=_S.ADMITTED,
            asserted_registration_record_presence=_P.RECORD_APPENDED,
        ),
        planned_to_state=_S.REGISTERED,
    )
    assert plan.planned_to_state is _S.REGISTERED


# --------------------------------------------------------------------------- #
# The unoccupied assertion
# --------------------------------------------------------------------------- #
def test_an_unoccupied_locator_admits_only_the_initial_move():
    plan = BenchmarkTransitionPlan(
        snapshot=fx.unoccupied_assertion(), planned_to_state=_S.SUBMITTED
    )
    assert plan.planned_predecessor_state is None
    assert plan.planned_payload_type_name == "BenchmarkSubmissionRecordPayload"

    for to_state in (_S.ADMITTED, _S.REGISTERED, _S.REVOKED, _S.REJECTED):
        with pytest.raises(BenchmarkRegistryLifecycleError):
            BenchmarkTransitionPlan(
                snapshot=fx.unoccupied_assertion(), planned_to_state=to_state
            )


def test_an_unoccupied_locator_cannot_also_assert_an_appended_record():
    """A locator holding nothing carries no registration record."""

    with pytest.raises(BenchmarkRegistryLifecycleError) as caught:
        fx.unoccupied_assertion(
            asserted_registration_record_presence=_P.RECORD_APPENDED
        )
    assert caught.value.reason is (
        BenchmarkRegistryRefusalReason.STALE_REGISTRY_SNAPSHOT
    )


def test_the_unoccupied_derivation_has_no_second_spelling():
    assert fx.unoccupied_assertion().asserts_unoccupied_locator is True
    assert fx.snapshot_assertion().asserts_unoccupied_locator is False
    names = {f.name for f in dataclasses.fields(fx.snapshot_assertion())}
    assert "asserts_unoccupied_locator" not in names


# --------------------------------------------------------------------------- #
# The plan is bound to the exact assertion it was computed from
# --------------------------------------------------------------------------- #
def test_the_plan_digest_is_recomputed_from_the_nested_assertion():
    plan = fx.transition_plan()
    assert plan.snapshot_digest == canonical_digest(plan.snapshot)


def test_substituting_the_assertion_moves_the_plan_digest():
    """A plan cannot be quoted against a state it was never computed for."""

    baseline = fx.transition_plan()
    moved = fx.transition_plan(
        snapshot=fx.snapshot_assertion(
            coordinate=fx.coordinate(benchmark_version="9.9.9")
        )
    )
    assert baseline.snapshot_digest != moved.snapshot_digest
    assert canonical_digest(baseline) != canonical_digest(moved)


def test_the_refusal_is_bound_to_its_assertion_the_same_way():
    refusal = fx.transition_refusal()
    assert refusal.snapshot_digest == canonical_digest(refusal.snapshot)


def test_a_plan_and_a_refusal_over_one_assertion_are_distinct_artifacts():
    """Distinct digest domains, so neither can be read as the other."""

    assert canonical_digest(fx.transition_plan()) != canonical_digest(
        fx.transition_refusal()
    )


# --------------------------------------------------------------------------- #
# No clock, no authority
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,builder", KERNEL_BUILDERS)
def test_no_kernel_contract_carries_a_recorded_time(name, builder):
    """D-11 as amended: BR-2A and BR-2B read no clock."""

    instance = builder()
    names = {f.name for f in dataclasses.fields(instance)}
    assert "declared_recorded_at" not in names, name
    assert not hasattr(instance, "declared_recorded_at"), name
    assert "effective_at" not in names, name


@pytest.mark.parametrize("name,builder", KERNEL_BUILDERS)
def test_every_kernel_contract_derives_the_five_false_properties(name, builder):
    instance = builder()
    for prop in BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES:
        assert getattr(instance, prop) is False, f"{name}.{prop}"


@pytest.mark.parametrize("name,builder", KERNEL_BUILDERS)
def test_no_kernel_contract_carries_a_boolean_field(name, builder):
    """D-15: an unavailable guarantee is never a flippable Boolean."""

    for f in dataclasses.fields(builder()):
        assert f.type is not bool, f"{name}.{f.name}"


@pytest.mark.parametrize("name,builder", KERNEL_BUILDERS)
def test_every_kernel_contract_is_frozen(name, builder):
    instance = builder()
    field = dataclasses.fields(instance)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, field, None)


# --------------------------------------------------------------------------- #
# Closed vocabularies stay closed
# --------------------------------------------------------------------------- #
def test_a_bare_string_state_is_refused_everywhere_in_the_kernel():
    """A ``str``-valued enum compares equal to its value; closed means closed."""

    with pytest.raises(BenchmarkRegistryContractError):
        fx.snapshot_assertion(asserted_current_state="ADMITTED")
    with pytest.raises(BenchmarkRegistryContractError):
        fx.transition_plan(planned_to_state="REGISTERED")
    with pytest.raises(BenchmarkRegistryContractError):
        fx.transition_refusal(refused_to_state="REVOKED")


def test_a_bare_string_record_presence_is_refused():
    with pytest.raises(BenchmarkRegistryContractError):
        fx.snapshot_assertion(
            asserted_registration_record_presence="NO_RECORD_APPENDED"
        )


def test_the_record_presence_enum_admits_exactly_two_members():
    assert [p.value for p in BenchmarkRegistrationRecordPresence] == [
        "NO_RECORD_APPENDED",
        "RECORD_APPENDED",
    ]


def test_a_refusal_reason_outside_the_br2_vocabulary_is_refused():
    with pytest.raises(BenchmarkRegistryContractError):
        fx.transition_refusal(declared_refusal_reason="UNAUTHORIZED_TRANSITION")


def test_a_foreign_object_cannot_stand_in_for_the_nested_assertion():
    """Exact-type identity, so a same-shaped lookalike is not admissible."""

    @dataclasses.dataclass(frozen=True)
    class LookalikeAssertion:
        coordinate: object
        asserted_current_state: object
        asserted_registration_record_presence: object

    impostor = LookalikeAssertion(
        coordinate=fx.coordinate(),
        asserted_current_state=_S.ADMITTED,
        asserted_registration_record_presence=_P.NO_RECORD_APPENDED,
    )
    with pytest.raises(BenchmarkRegistryContractError):
        BenchmarkTransitionPlan(
            snapshot=impostor, planned_to_state=_S.REGISTERED
        )
    with pytest.raises(BenchmarkRegistryContractError):
        BenchmarkTransitionRefusal(
            snapshot=impostor,
            refused_to_state=_S.REVOKED,
            declared_refusal_reason=(
                BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION
            ),
        )


def test_a_subclass_of_the_assertion_is_not_the_assertion():
    class Subclassed(BenchmarkRegistrySnapshotAssertion):
        pass

    with pytest.raises(BenchmarkRegistryContractError):
        BenchmarkTransitionPlan(
            snapshot=Subclassed(
                coordinate=fx.coordinate(),
                asserted_current_state=_S.ADMITTED,
                asserted_registration_record_presence=_P.NO_RECORD_APPENDED,
            ),
            planned_to_state=_S.REGISTERED,
        )


# --------------------------------------------------------------------------- #
# The plan names the ratified payload shape, and does not invent one
# --------------------------------------------------------------------------- #
def test_every_planned_payload_name_is_the_one_the_binding_ratifies():
    for (from_state, to_state), (
        payload,
        _outcome,
    ) in BENCHMARK_TRANSITION_PAYLOAD_BINDING.items():
        snapshot = (
            fx.unoccupied_assertion()
            if from_state is None
            else fx.snapshot_assertion(asserted_current_state=from_state)
        )
        plan = BenchmarkTransitionPlan(
            snapshot=snapshot, planned_to_state=to_state
        )
        assert plan.planned_payload_type_name == payload.__name__


def test_the_plan_names_a_payload_type_rather_than_carrying_the_class():
    """A class object is not a canonicalizable value."""

    plan = fx.transition_plan()
    assert isinstance(plan.planned_payload_type_name, str)
    names = {f.name for f in dataclasses.fields(plan)}
    assert "planned_payload_type_name" not in names


def test_terminality_is_derived_and_matches_the_closed_relation():
    for to_state in BenchmarkRegistrationState:
        from_states = [
            s
            for s in BenchmarkRegistrationState
            if to_state in BENCHMARK_REGISTRATION_TRANSITIONS[s]
        ]
        if not from_states:
            continue
        plan = BenchmarkTransitionPlan(
            snapshot=fx.snapshot_assertion(
                asserted_current_state=from_states[0]
            ),
            planned_to_state=to_state,
        )
        expected = not BENCHMARK_REGISTRATION_TRANSITIONS[to_state]
        assert plan.is_terminal is expected, to_state


def test_a_refusal_is_always_terminal_because_it_plans_nothing():
    assert fx.transition_refusal().is_terminal is True
