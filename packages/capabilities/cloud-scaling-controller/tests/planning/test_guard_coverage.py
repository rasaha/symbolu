"""Isolating tests for the guard sweep — one decision point, one discriminating fact.

Written for the `planning/` phase of the shared-engine adoption (guard-coverage ADR,
controller phase 1). The pre-existing Phase-3 suite proves the pipeline *behaves*: it
recommends when it should, abstains when evidence is missing, and refuses malformed
input. What it did not prove is which gate decided. The first sweep measured 156 of 219
guards surviving — `topology.py:89`'s `isinstance` check on an edge's upstream could be
deleted outright and all 486 tests stayed green, because nothing ever built an edge with
a wrong-typed upstream.

Every test here neutralises that: it constructs an input that is valid in every respect
*except* the one field the target guard reads, so exactly one gate can refuse it. Under
ADR §6's within-class criterion a kill that only shows "something was rejected"
attributes nothing; isolation is what makes the typed error class attributable here,
because no sibling gate can fire on the same input.

The typed half asserted is the exception class the module publishes — `TopologyError`,
`CostError`, `CandidateError`, `ConstraintError`, `PolicyError`, `ScoringError`,
`RecommendationError`, `PipelineError` — or, for the pipeline, the typed
`RecommendationAbstentionReason` member. Never a message substring.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import ph_helpers as H
from ugence_cloud_scaling_controller.canonical import CapacitySubject
from ugence_cloud_scaling_controller.planning import (
    DependencyEdge,
    DependencyKind,
    DependencyTopology,
    TopologyError,
)

T0 = H.T0


def _subject(**over):
    fields = dict(workload_id="app", tenant_id="tenant-1")
    fields.update(over)
    return CapacitySubject(**fields)


def _edge(**over):
    """A valid capacity-coupling edge; override exactly one field per test."""

    fields = dict(
        upstream=_subject(workload_id="app"),
        downstream=_subject(workload_id="db"),
        kind=DependencyKind.CAPACITY_BOUND,
        downstream_current_capacity=20,
        required_per_upstream_unit=2.0,
    )
    fields.update(over)
    return DependencyEdge(**fields)


# ======================================================================================= #
# topology.py — DependencyEdge.__post_init__
# ======================================================================================= #


def test_an_edge_upstream_that_is_not_a_subject_is_refused():
    """Everything else valid: only the upstream type gate can refuse this."""

    with pytest.raises(TopologyError):
        _edge(upstream="app")


def test_an_edge_downstream_that_is_not_a_subject_is_refused():
    with pytest.raises(TopologyError):
        _edge(downstream="db")


def test_an_edge_kind_that_is_not_a_dependency_kind_is_refused():
    """The string value of a real member, which is not the member itself."""

    with pytest.raises(TopologyError):
        _edge(kind="capacity_bound")


# ======================================================================================= #
# topology.py — DependencyEdge.from_dict
# ======================================================================================= #


def _edge_payload(**over):
    payload = dict(
        upstream=_subject(workload_id="app").to_canonical_dict(),
        downstream=_subject(workload_id="db").to_canonical_dict(),
        kind=DependencyKind.CAPACITY_BOUND.value,
        downstream_current_capacity=20,
        required_per_upstream_unit=2.0,
    )
    payload.update(over)
    return payload


def test_an_edge_payload_that_is_not_a_mapping_is_refused():
    with pytest.raises(TopologyError):
        DependencyEdge.from_dict([("upstream", {})])


def test_an_edge_payload_carrying_an_unknown_field_is_refused():
    """A payload that is otherwise exactly valid, plus one field the schema does not
    name — so only the unknown-field gate can refuse it."""

    with pytest.raises(TopologyError):
        DependencyEdge.from_dict(_edge_payload(nonsense=1))


@pytest.mark.parametrize("missing", ["upstream", "downstream", "kind"])
def test_an_edge_payload_missing_a_required_field_is_refused(missing):
    payload = _edge_payload()
    del payload[missing]
    with pytest.raises(TopologyError):
        DependencyEdge.from_dict(payload)


# ======================================================================================= #
# topology.py — DependencyTopology.__post_init__
# ======================================================================================= #


def _topology(**over):
    fields = dict(subject=_subject(workload_id="app"), as_of=T0, edges=(_edge(),))
    fields.update(over)
    return DependencyTopology(**fields)


def test_a_topology_subject_that_is_not_a_subject_is_refused():
    with pytest.raises(TopologyError):
        _topology(subject="app")


def test_a_topology_as_of_that_is_not_a_datetime_is_refused():
    with pytest.raises(TopologyError):
        _topology(as_of="2026-01-01T00:00:00Z")


@pytest.mark.parametrize("bad", ["", 7])
def test_a_topology_evidence_source_that_is_not_a_non_empty_string_is_refused(bad):
    """`None` is allowed and an absent source is not this gate's business; an empty
    string and a non-string are the two halves this guard rejects."""

    with pytest.raises(TopologyError):
        _topology(evidence_source=bad)


def test_a_topology_edge_that_is_not_a_dependency_edge_is_refused():
    with pytest.raises(TopologyError):
        _topology(edges=("app->db",))


def test_an_edge_whose_upstream_leaves_the_anchor_scope_is_refused():
    """Scope-compatible in every field but tenant, and the downstream stays compatible,
    so only the upstream scope gate can refuse this."""

    stray = _edge(upstream=_subject(workload_id="app", tenant_id="tenant-OTHER"))
    with pytest.raises(TopologyError):
        _topology(edges=(stray,))


# ======================================================================================= #
# topology.py — DependencyTopology.from_dict
# ======================================================================================= #


def _topology_payload(**over):
    payload = dict(
        subject=_subject(workload_id="app").to_canonical_dict(),
        as_of=T0,
        edges=[_edge_payload()],
    )
    payload.update(over)
    return payload


def test_a_topology_payload_that_is_not_a_mapping_is_refused():
    with pytest.raises(TopologyError):
        DependencyTopology.from_dict([("subject", {})])


@pytest.mark.parametrize("missing", ["subject", "as_of"])
def test_a_topology_payload_missing_a_required_field_is_refused(missing):
    payload = _topology_payload()
    del payload[missing]
    with pytest.raises(TopologyError):
        DependencyTopology.from_dict(payload)


def test_a_topology_payload_as_of_that_is_not_a_datetime_is_refused():
    """`from_dict`'s own as_of gate, isolated from the dataclass gate that repeats it.

    The subject is malformed too, deliberately. Both gates check the same thing and both
    raise `TopologyError`, so a payload whose only fault is `as_of` cannot tell them
    apart — delete this one and the dataclass still refuses, identically typed. Making
    the subject bad as well moves the fallback into `CapacitySubject.from_dict`, which
    raises `SubjectError`: this gate refuses first and refuses as a topology error, and
    without it the caller gets a different contract entirely.
    """

    payload = _topology_payload(as_of="2026-01-01T00:00:00Z", subject="not-a-subject")
    with pytest.raises(TopologyError):
        DependencyTopology.from_dict(payload)


class _EdgeStream:
    """Truthy, iterable, and not a list or tuple — yielding a *valid* edge payload."""

    def __init__(self, payload):
        self._payload = payload

    def __iter__(self):
        return iter((self._payload,))


def test_a_topology_payload_whose_edges_are_not_a_sequence_is_refused():
    """The sequence gate, isolated from what iterating a bad value would hit anyway.

    A mapping would work as a non-sequence, but iterating one yields its keys and the
    per-edge `from_dict` then raises `TopologyError` on its own — the same class, so the
    mutant would look killed for the wrong reason. This value iterates to a payload that
    is valid in every respect, so with the gate removed the topology is built
    successfully and nothing refuses at all.
    """

    with pytest.raises(TopologyError):
        DependencyTopology.from_dict(
            _topology_payload(edges=_EdgeStream(_edge_payload()))
        )


def test_a_duplicate_pair_and_a_contradictory_pair_are_both_refused_as_topology_errors():
    """Evidence for the `diagnostic-only` exclusion of the conflicting-kind guard.

    `seen[key] != edge.kind` chooses between two messages on a path that raises
    `TopologyError` either way: with the guard neutralised, a contradictory pair falls
    through to the duplicate-edge refusal on the next line. No input can distinguish
    them by the typed half, because there is only one typed half. This test records that
    both shapes are refused, and refused as the same contract — which is what makes the
    guard a diagnosis rather than a decision.
    """

    same = (_edge(), _edge())
    contradictory = (
        _edge(kind=DependencyKind.CAPACITY_BOUND),
        _edge(kind=DependencyKind.THROUGHPUT_BOUND),
    )
    for edges in (same, contradictory):
        with pytest.raises(TopologyError):
            _topology(edges=edges)


# ======================================================================================= #
# cost.py — Money.from_dict
# ======================================================================================= #

from ugence_cloud_scaling_controller.planning import (  # noqa: E402
    CostBasis,
    CostBook,
    CostError,
    CostEvidence,
    Money,
)


def test_a_money_payload_that_is_not_a_mapping_is_refused():
    """A list of exactly the two field names: every later gate happens to pass on it
    (`set()` finds no unknown key, `in` finds both required ones), and indexing it with
    a string is a `TypeError`, not a `CostError` — so only this gate can produce the
    typed refusal."""

    with pytest.raises(CostError):
        Money.from_dict(["amount_minor", "currency"])


def test_a_money_payload_carrying_an_unknown_field_is_refused():
    with pytest.raises(CostError):
        Money.from_dict({"amount_minor": 100, "currency": "USD", "tip": 1})


def test_a_money_payload_missing_its_required_fields_is_refused():
    """Empty mapping: without this gate the constructor call is a `KeyError`."""

    with pytest.raises(CostError):
        Money.from_dict({})


# ======================================================================================= #
# cost.py — CostEvidence.__post_init__
# ======================================================================================= #


def _money(**over):
    fields = dict(amount_minor=100, currency="USD")
    fields.update(over)
    return Money(**fields)


def _cost_evidence(**over):
    fields = dict(
        subject=_subject(workload_id="app"),
        unit_price=_money(),
        basis=CostBasis.PER_REPLICA_HOUR,
        effective_from=T0,
        effective_until=H.at(3600),
    )
    fields.update(over)
    return CostEvidence(**fields)


def test_a_cost_subject_that_is_not_a_subject_is_refused():
    with pytest.raises(CostError):
        _cost_evidence(subject="app")


def test_a_unit_price_that_is_not_money_is_refused():
    """Without this gate the negative-price check reads `.amount_minor` off an int and
    the caller gets an `AttributeError` instead of the cost contract."""

    with pytest.raises(CostError):
        _cost_evidence(unit_price=100)


def test_a_basis_that_is_not_a_cost_basis_is_refused():
    with pytest.raises(CostError):
        _cost_evidence(basis="per_replica_hour")


def test_effective_bounds_that_are_not_datetimes_are_refused():
    """Both bounds wrong, and chosen so their string comparison keeps the ordering gate
    quiet — with this gate removed, nothing refuses at all."""

    with pytest.raises(CostError):
        _cost_evidence(effective_from="2026-01-01", effective_until="2027-01-01")


@pytest.mark.parametrize("bad", ["", 7])
def test_a_cost_evidence_source_that_is_not_a_non_empty_string_is_refused(bad):
    with pytest.raises(CostError):
        _cost_evidence(evidence_source=bad)


# ======================================================================================= #
# cost.py — CostEvidence.from_dict
# ======================================================================================= #


def _cost_evidence_payload(**over):
    payload = dict(
        subject=_subject(workload_id="app").to_canonical_dict(),
        unit_price={"amount_minor": 100, "currency": "USD"},
        basis=CostBasis.PER_REPLICA_HOUR.value,
        effective_from=T0,
        effective_until=H.at(3600),
    )
    payload.update(over)
    return payload


def test_a_cost_evidence_payload_that_is_not_a_mapping_is_refused():
    """The field-name-list probe again: every later gate passes on it and the datetime
    check would die as a `TypeError`, so the typed refusal is this gate's alone."""

    with pytest.raises(CostError):
        CostEvidence.from_dict(
            ["subject", "unit_price", "basis", "effective_from", "effective_until"]
        )


def test_a_cost_evidence_payload_carrying_an_unknown_field_is_refused():
    with pytest.raises(CostError):
        CostEvidence.from_dict(_cost_evidence_payload(surcharge=1))


def test_a_cost_evidence_payload_missing_a_required_field_is_refused():
    """`basis` is the one to drop: without this gate the enum lookup is a `KeyError`
    the surrounding `except ValueError` does not translate."""

    payload = _cost_evidence_payload()
    del payload["basis"]
    with pytest.raises(CostError):
        CostEvidence.from_dict(payload)


def test_a_cost_evidence_payload_with_non_datetime_bounds_is_refused():
    """The subject is malformed too — the dataclass repeats this check with the same
    `CostError`, so the discriminating fallback is `SubjectError` from the subject
    parse, exactly as with the topology as_of gate."""

    payload = _cost_evidence_payload(effective_from="2026-01-01", subject="app")
    with pytest.raises(CostError):
        CostEvidence.from_dict(payload)


# ======================================================================================= #
# cost.py — CostBook.__post_init__ / from_dict
# ======================================================================================= #


def test_a_cost_book_subject_that_is_not_a_subject_is_refused():
    """Empty entries, so the per-entry scope check never touches the bad subject and
    only this gate can refuse it."""

    with pytest.raises(CostError):
        CostBook(subject="app", entries=())


def test_a_cost_book_entry_that_is_not_cost_evidence_is_refused():
    with pytest.raises(CostError):
        CostBook(subject=_subject(workload_id="app"), entries=("evidence",))


def test_a_cost_book_payload_that_is_not_a_mapping_is_refused():
    """`["subject"]` passes the unknown- and required-field gates; without this one the
    entries read is an `AttributeError` on `.get`."""

    with pytest.raises(CostError):
        CostBook.from_dict(["subject"])


def test_a_cost_book_payload_missing_its_subject_is_refused():
    with pytest.raises(CostError):
        CostBook.from_dict({})


def test_a_cost_book_payload_whose_entries_are_not_a_sequence_is_refused():
    """A truthy non-sequence iterating to one fully valid entry: with the gate removed
    the book is built successfully and nothing refuses."""

    with pytest.raises(CostError):
        CostBook.from_dict(
            {
                "subject": _subject(workload_id="app").to_canonical_dict(),
                "entries": _EdgeStream(_cost_evidence_payload()),
            }
        )


# ======================================================================================= #
# constraints.py — OperatingConstraints.__post_init__
# ======================================================================================= #

from ugence_cloud_scaling_controller.planning import (  # noqa: E402
    ConstraintError,
    OperatingConstraints,
)


def _constraints(**over):
    fields = dict(min_capacity=1, max_capacity=10)
    fields.update(over)
    return OperatingConstraints(**fields)


def test_a_capacity_bound_that_is_not_an_int_is_refused():
    """1.5 passes every later comparison (`1.5 < 0` is False, `10 < 1.5` is False), so
    with the int gate removed the constraints construct successfully."""

    with pytest.raises(ConstraintError):
        _constraints(min_capacity=1.5)


def test_a_regional_quota_that_is_not_a_nonnegative_int_is_refused():
    """Kills both halves of the quota admission: the not-None gate that routes into the
    check and the check itself — either one removed admits a negative quota."""

    with pytest.raises(ConstraintError):
        _constraints(regional_quota=-1)


def test_an_infinite_cooldown_is_refused():
    """`inf` is the probe the finiteness gate alone can catch: it is a float, and
    `inf < 0` is False, so nothing downstream refuses it."""

    with pytest.raises(ConstraintError):
        _constraints(cooldown_seconds=float("inf"))


def test_a_none_cooldown_is_refused_as_a_constraint_error():
    """Evidence for the `diagnostic-only` exclusion of `_finite_number`'s None branch,
    and the kill for the helper-admission call itself: with the call deleted,
    `None < 0` is a TypeError and the constraint contract is gone.

    The None branch inside the helper is excluded rather than scored because no call
    site passes `allow_none=True`: for every reachable input the branch chooses between
    "is required" and "must be a finite number", both `ConstraintError`, so no input
    distinguishes them by the typed half.
    """

    with pytest.raises(ConstraintError):
        _constraints(cooldown_seconds=None)


def test_a_negative_cooldown_is_refused():
    with pytest.raises(ConstraintError):
        _constraints(cooldown_seconds=-1.0)


def test_a_last_change_at_that_is_not_a_datetime_is_refused():
    with pytest.raises(ConstraintError):
        _constraints(last_change_at="yesterday")


def test_a_nonpositive_forecast_validity_is_refused():
    """Kills the not-None routing gate and the `<= 0` check: -5.0 is finite, so only
    those two stand between it and admission."""

    with pytest.raises(ConstraintError):
        _constraints(forecast_validity_seconds=-5.0)


def test_a_nan_forecast_validity_is_refused():
    """The finiteness helper call is what this isolates: with the call deleted,
    `nan <= 0` is False and the NaN is admitted outright."""

    with pytest.raises(ConstraintError):
        _constraints(forecast_validity_seconds=float("nan"))


def test_a_protection_flag_that_is_not_a_bool_is_refused():
    with pytest.raises(ConstraintError):
        _constraints(protect_slo="yes")


def test_a_dependency_ceiling_that_is_not_a_mapping_is_refused():
    """Without the gate, `.items()` on the list is an AttributeError, not the
    constraint contract."""

    with pytest.raises(ConstraintError):
        _constraints(dependency_capacity_ceiling=[("db", 1)])


def test_a_dependency_ceiling_key_that_is_not_a_non_empty_string_is_refused():
    with pytest.raises(ConstraintError):
        _constraints(dependency_capacity_ceiling={"": 1})


def test_a_dependency_ceiling_value_that_is_not_a_nonnegative_int_is_refused():
    with pytest.raises(ConstraintError):
        _constraints(dependency_capacity_ceiling={"db": -1})


def test_a_prohibited_action_that_is_not_a_non_empty_string_is_refused():
    with pytest.raises(ConstraintError):
        _constraints(prohibited_actions=("",))


def test_a_max_cost_increase_that_is_not_a_nonnegative_int_is_refused():
    """Kills both the not-None routing gate and the check it routes into."""

    with pytest.raises(ConstraintError):
        _constraints(max_cost_increase_minor=-1)


def test_a_none_safety_margin_is_refused_as_a_constraint_error():
    """The helper-admission call for the safety margin: with it deleted, the range gate
    compares `0.0 <= None` and the caller gets a TypeError instead. NaN would not do
    here — the range gate happens to refuse NaN with the same class."""

    with pytest.raises(ConstraintError):
        _constraints(safety_margin_fraction=None)


# ======================================================================================= #
# constraints.py — OperatingConstraints.from_dict
# ======================================================================================= #


def test_a_constraints_payload_that_is_not_a_mapping_is_refused():
    """The field-name-list probe: no unknown key, both required names present as list
    members, and the first indexing is a TypeError without this gate."""

    with pytest.raises(ConstraintError):
        OperatingConstraints.from_dict(["min_capacity", "max_capacity"])


def test_a_constraints_payload_missing_a_required_field_is_refused():
    with pytest.raises(ConstraintError):
        OperatingConstraints.from_dict({})


# ======================================================================================= #
# candidates.py — ResourceChange
# ======================================================================================= #

from ugence_cloud_scaling_controller.planning import (  # noqa: E402
    ActionKind,
    CandidateActionPlan,
    CandidateError,
    ResourceChange,
    generate_candidates,
)


def _change(**over):
    fields = dict(
        subject=_subject(workload_id="app"),
        current_capacity=3,
        proposed_capacity=4,
        role="primary",
    )
    fields.update(over)
    return ResourceChange(**fields)


def test_a_change_subject_that_is_not_a_subject_is_refused():
    with pytest.raises(CandidateError):
        _change(subject="app")


def test_a_change_role_outside_the_two_named_roles_is_refused():
    with pytest.raises(CandidateError):
        _change(role="observer")


def test_a_change_payload_that_is_not_a_mapping_is_refused():
    """Field-name-list probe; without the gate the subject parse is a TypeError."""

    with pytest.raises(CandidateError):
        ResourceChange.from_dict(["subject", "current_capacity", "proposed_capacity"])


def _change_payload(**over):
    payload = dict(
        subject=_subject(workload_id="app").to_canonical_dict(),
        current_capacity=3,
        proposed_capacity=4,
        role="primary",
    )
    payload.update(over)
    return payload


def test_a_change_payload_carrying_an_unknown_field_is_refused():
    with pytest.raises(CandidateError):
        ResourceChange.from_dict(_change_payload(velocity=1))


def test_a_change_payload_missing_a_required_field_is_refused():
    with pytest.raises(CandidateError):
        ResourceChange.from_dict({})


# ======================================================================================= #
# candidates.py — CandidateActionPlan.__post_init__
# ======================================================================================= #


def _plan(**over):
    fields = dict(
        plan_id="p1",
        action_kind=ActionKind.SCALE_UP,
        changes=(_change(),),
    )
    fields.update(over)
    return CandidateActionPlan(**fields)


def test_a_plan_id_that_is_not_a_non_empty_string_is_refused():
    with pytest.raises(CandidateError):
        _plan(plan_id="")


def test_an_action_kind_that_is_not_the_enum_member_is_refused():
    """The member's own string value, on a plan shaped so every kind-specific branch
    the mutant falls into passes: a coordinated shape satisfies the `else` arm, so with
    the type gate removed the plan constructs successfully."""

    coordinated = (
        _change(),
        _change(subject=_subject(workload_id="db"), role="dependency",
                current_capacity=10, proposed_capacity=12),
    )
    with pytest.raises(CandidateError):
        _plan(action_kind="coordinated", changes=coordinated)


class _FakeChange:
    """Carries the one attribute read before the type gate, and nothing after it."""

    role = "dependency"


def test_a_plan_change_that_is_not_a_resource_change_is_refused():
    """The roles read happens before the type gate, so the impostor must carry `role`;
    without the gate the subject read on it is an AttributeError, not the candidate
    contract."""

    with pytest.raises(CandidateError):
        _plan(changes=(_change(), _FakeChange()))


def test_a_duplicate_subject_within_one_plan_is_refused():
    """Two changes for the same subject in an otherwise valid coordinated plan — with
    the duplicate gate removed the plan constructs successfully."""

    dup = (
        _change(),
        _change(role="dependency", current_capacity=5, proposed_capacity=6),
    )
    with pytest.raises(CandidateError):
        _plan(action_kind=ActionKind.COORDINATED, changes=dup)


def test_a_timing_that_is_not_a_real_number_is_refused():
    """Without the gate, `'fast' < 0` is a TypeError."""

    with pytest.raises(CandidateError):
        _plan(timing_seconds="fast")


def test_a_negative_timing_is_refused():
    with pytest.raises(CandidateError):
        _plan(timing_seconds=-1.0)


def test_an_empty_plan_is_refused_as_a_candidate_error():
    """Evidence for the `diagnostic-only` exclusion of the empty-changes guard: with it
    removed, the primary-count gate refuses the same empty plan with the same class —
    an empty tuple has zero 'primary' roles. No input reaches one without the other."""

    with pytest.raises(CandidateError):
        _plan(changes=())


def test_a_scale_up_whose_primary_shrinks_is_refused():
    """Delta -1 with exactly one changed resource: the direction gate is the only one
    that can refuse it, and with it removed the plan constructs."""

    with pytest.raises(CandidateError):
        _plan(changes=(_change(proposed_capacity=2),))


def test_a_scale_up_that_changes_more_than_the_primary_is_refused():
    two_moved = (
        _change(),
        _change(subject=_subject(workload_id="db"), role="dependency",
                current_capacity=10, proposed_capacity=12),
    )
    with pytest.raises(CandidateError):
        _plan(changes=two_moved)


def test_a_scale_down_that_changes_more_than_the_primary_is_refused():
    two_moved = (
        _change(proposed_capacity=2),
        _change(subject=_subject(workload_id="db"), role="dependency",
                current_capacity=10, proposed_capacity=12),
    )
    with pytest.raises(CandidateError):
        _plan(action_kind=ActionKind.SCALE_DOWN, changes=two_moved)


def test_a_coordinated_plan_with_a_static_primary_is_refused():
    """Primary delta zero while two dependencies move: the zero-primary gate alone
    refuses it, since the >=2-changes gate is satisfied."""

    static_primary = (
        _change(proposed_capacity=3),
        _change(subject=_subject(workload_id="db"), role="dependency",
                current_capacity=10, proposed_capacity=12),
        _change(subject=_subject(workload_id="cache"), role="dependency",
                current_capacity=2, proposed_capacity=3),
    )
    with pytest.raises(CandidateError):
        _plan(action_kind=ActionKind.COORDINATED, changes=static_primary)


# ======================================================================================= #
# candidates.py — CandidateActionPlan.from_dict
# ======================================================================================= #


def _plan_payload(**over):
    payload = dict(
        plan_id="p1",
        action_kind=ActionKind.SCALE_UP.value,
        changes=[_change_payload()],
    )
    payload.update(over)
    return payload


def test_a_plan_payload_that_is_not_a_mapping_is_refused():
    """The action-kind lookup on the probe list is a TypeError the surrounding
    `except ValueError` does not translate."""

    with pytest.raises(CandidateError):
        CandidateActionPlan.from_dict(["plan_id", "action_kind", "changes"])


def test_a_plan_payload_carrying_an_unknown_field_is_refused():
    with pytest.raises(CandidateError):
        CandidateActionPlan.from_dict(_plan_payload(urgency=1))


def test_a_plan_payload_missing_a_required_field_is_refused():
    with pytest.raises(CandidateError):
        CandidateActionPlan.from_dict({})


def test_a_plan_payload_whose_changes_are_not_a_sequence_is_refused():
    """A truthy non-sequence iterating to one valid change: with the gate removed the
    plan constructs successfully."""

    with pytest.raises(CandidateError):
        CandidateActionPlan.from_dict(
            _plan_payload(changes=_EdgeStream(_change_payload()))
        )


# ======================================================================================= #
# candidates.py — generate_candidates argument gates
# ======================================================================================= #


def test_an_invalid_current_capacity_is_refused_as_a_candidate_error():
    """Evidence for the `diagnostic-only` exclusion of the current_capacity gate:
    current flows into the NO_CHANGE plan's ResourceChange unconditionally, whose own
    validation refuses every value this gate refuses, with the same class."""

    with pytest.raises(CandidateError):
        generate_candidates(
            _subject(workload_id="app"),
            current_capacity=-1,
            required_capacity=2,
            allowed_step=1,
            min_capacity=0,
            max_capacity=10,
        )


def test_a_negative_required_capacity_is_refused():
    """-1 is the probe this gate alone can catch. A fractional requirement would not
    do: the exact-requirement target (`lo <= required <= hi`) would carry it into a
    ResourceChange, whose own validation refuses it with the same class. A negative
    requirement is dropped by that very clamp, steps down to a valid target of 0, and
    generates successfully with the gate removed."""

    with pytest.raises(CandidateError):
        generate_candidates(
            _subject(workload_id="app"),
            current_capacity=1,
            required_capacity=-1,
            allowed_step=1,
            min_capacity=0,
            max_capacity=10,
        )


def test_an_allowed_step_below_one_is_refused():
    """required == current on purpose: neither stepping branch runs, so the mutant
    returns a NO_CHANGE-only candidate set instead of looping on a zero step."""

    with pytest.raises(CandidateError):
        generate_candidates(
            _subject(workload_id="app"),
            current_capacity=2,
            required_capacity=2,
            allowed_step=0,
            min_capacity=0,
            max_capacity=10,
        )


# ======================================================================================= #
# policy.py — RecommendationPolicy
# ======================================================================================= #

from ugence_cloud_scaling_controller.planning import (  # noqa: E402
    FEATURE_NAMES,
    PolicyError,
    RecommendationPolicy,
    ScoreBreakdown,
)


def test_a_policy_id_that_is_not_a_non_empty_string_is_refused():
    with pytest.raises(PolicyError):
        H.policy(policy_id="")


def test_a_threshold_above_one_is_refused():
    """Finite and non-negative, so only the [0, 1] range gate can refuse it."""

    with pytest.raises(PolicyError):
        H.policy(coverage_floor=2.0)


def test_a_tie_epsilon_above_one_is_refused():
    with pytest.raises(PolicyError):
        H.policy(tie_epsilon=2.0)


def test_a_policy_payload_that_is_not_a_mapping_is_refused():
    """`["policy_id"]` passes the unknown-key set arithmetic; without the gate,
    `dict.update` on it raises a plain ValueError, not the policy contract."""

    with pytest.raises(PolicyError):
        RecommendationPolicy.from_dict(["policy_id"])


def test_a_policy_payload_carrying_an_unknown_field_is_refused():
    with pytest.raises(PolicyError):
        RecommendationPolicy.from_dict({"policy_id": "p", "w_speed": 1.0})


# ======================================================================================= #
# policy.py — ScoreBreakdown
# ======================================================================================= #


def _breakdown(**over):
    fields = dict(
        features={f: 0.0 for f in FEATURE_NAMES},
        contributions={f: 0.0 for f in FEATURE_NAMES},
        total_score=0.0,
        policy_id="p",
        policy_digest="sha256:d",
    )
    fields.update(over)
    return ScoreBreakdown(**fields)


def test_breakdown_features_that_are_not_a_mapping_are_refused():
    with pytest.raises(PolicyError):
        _breakdown(features=[("coverage", 0.0)])


def test_an_unknown_feature_name_is_refused_as_a_policy_error():
    """Evidence for the `diagnostic-only` exclusion of the per-key unknown-feature
    gate: any key-set deviation it can see — replaced or added — is also refused by the
    exact-cover gate below it, with the same class, and a wrong-typed value under the
    bogus key is refused by the finiteness gate between them, again with the same
    class. No input reaches one without the others."""

    features = {f: 0.0 for f in FEATURE_NAMES}
    features.pop("hold_bias")
    features["bogus"] = 0.0
    with pytest.raises(PolicyError):
        _breakdown(features=features)


def test_a_feature_set_that_does_not_cover_the_fixed_names_is_refused():
    """A strict subset — no unknown key for the per-key gate, every value finite — so
    the exact-cover gate alone refuses it; without it the canonical rebuild is a
    KeyError on the missing name."""

    features = {f: 0.0 for f in FEATURE_NAMES}
    features.pop("hold_bias")
    with pytest.raises(PolicyError):
        _breakdown(features=features)


def test_a_non_finite_total_score_is_refused():
    """NaN is the probe: the recomputation gate's `abs(sum - NaN) > tol` is False, so
    with the finiteness gate removed the breakdown constructs successfully."""

    with pytest.raises(PolicyError):
        _breakdown(total_score=float("nan"))


def test_a_breakdown_payload_that_is_not_a_mapping_is_refused():
    with pytest.raises(PolicyError):
        ScoreBreakdown.from_dict(
            ["policy_id", "policy_digest", "features", "contributions", "total_score"]
        )


def test_a_breakdown_payload_carrying_an_unknown_field_is_refused():
    payload = _breakdown().to_canonical_dict()
    payload["audited"] = True
    with pytest.raises(PolicyError):
        ScoreBreakdown.from_dict(payload)


def test_a_breakdown_payload_missing_a_required_field_is_refused():
    with pytest.raises(PolicyError):
        ScoreBreakdown.from_dict({})


# ======================================================================================= #
# scoring.py — build_context / plan_cost_delta_minor
# ======================================================================================= #

from ugence_cloud_scaling_controller.canonical import (  # noqa: E402
    CanonicalCapacityState,
)
from ugence_cloud_scaling_controller.planning import (  # noqa: E402
    CostBook as _CostBook,
    ScoringError,
    build_context,
    plan_cost_delta_minor,
)


def _ctx_inputs(**over):
    subj = over.pop("subj", H.subject())
    fields = dict(
        forecast_evidence=H.build_forecast_evidence(8, subj=subj),
        current_state=H.replicas_state(H.at(180.0), 6, subj=subj),
        topology=None,
        cost_book=H.cost_book(subj=subj),
        constraints=H.constraints(),
        recommendation_time=H.at(190.0),
    )
    fields.update(over)
    return fields


def _build_context(**over):
    f = _ctx_inputs(**over)
    return build_context(
        f["forecast_evidence"], f["current_state"], f["topology"], f["cost_book"],
        f["constraints"], recommendation_time=f["recommendation_time"],
    )


def test_context_from_an_abstained_forecast_is_refused():
    """Without the point-forecast gate, `float(None)` on the absent point estimate is a
    TypeError, not the scoring contract."""

    with pytest.raises(ScoringError):
        _build_context(forecast_evidence=H.build_abstained_forecast(subj=H.subject()))


def test_context_from_a_non_planning_target_is_refused():
    """A genuine CPU forecast: every later gate passes on it, so with the target gate
    removed the context builds successfully."""

    with pytest.raises(ScoringError):
        _build_context(forecast_evidence=H.build_cpu_forecast_evidence(subj=H.subject()))


def test_context_without_current_capacity_is_refused():
    """A state with no capacity block: without the gate, reading `.running_replicas`
    off None is an AttributeError."""

    from ugence_cloud_scaling_controller.canonical import InfrastructureState, Measurement, Unit
    bare = CanonicalCapacityState(
        subject=H.subject(), observed_at=H.at(180.0),
        infrastructure=InfrastructureState(cpu_utilization=Measurement(50.0, Unit.PERCENT)),
    )
    with pytest.raises(ScoringError):
        _build_context(current_state=bare)


def test_context_with_an_evidence_free_dependency_edge_is_refused():
    """A capacity-bound edge with both evidence fields absent: without the gate,
    `int(None)` on the missing downstream capacity is a TypeError."""

    dep = H.subject(workload_id="db")
    topo = H.topology(dependency=dep, downstream_current=None, required_per_upstream_unit=None)
    with pytest.raises(ScoringError):
        _build_context(topology=topo)


def test_context_without_a_primary_unit_price_is_refused():
    """An empty cost book: without the gate the baseline-cost multiply on None is a
    TypeError."""

    with pytest.raises(ScoringError):
        _build_context(cost_book=_CostBook(subject=H.subject(), entries=()))


def test_a_plan_cost_for_an_unpriced_resource_is_refused():
    """The context prices only the primary; the plan changes a second subject. Without
    the gate the cost multiply on None is a TypeError."""

    ctx = H.make_ctx()
    plan = CandidateActionPlan(
        plan_id="p1",
        action_kind=ActionKind.COORDINATED,
        changes=(
            _change(),
            _change(subject=_subject(workload_id="db"), role="dependency",
                    current_capacity=10, proposed_capacity=12),
        ),
    )
    with pytest.raises(ScoringError):
        plan_cost_delta_minor(plan, ctx)


# ======================================================================================= #
# pipeline.py — recommend_capacity_action argument gates
# ======================================================================================= #

from ugence_cloud_scaling_controller.planning import (  # noqa: E402
    PipelineError,
    RecommendationAbstention,
    RecommendationAbstentionReason,
    recommend_capacity_action,
)


def _recommend(**over):
    subj = over.pop("subj", H.subject())
    kw = dict(
        forecast_evidence=H.build_forecast_evidence(8, subj=subj),
        current_state=H.replicas_state(H.at(180.0), 6, subj=subj),
        cost_book=H.cost_book(subj=subj),
        constraints=H.constraints(),
        policy=H.policy(),
        recommendation_time=H.at(190.0),
        validity_seconds=60.0,
    )
    kw.update(over)
    return recommend_capacity_action(
        kw.pop("forecast_evidence"), kw.pop("current_state"), kw.pop("cost_book"),
        kw.pop("constraints"), kw.pop("policy"), **kw,
    )


def test_a_recommendation_time_that_is_not_a_datetime_is_refused():
    with pytest.raises(PipelineError):
        _recommend(recommendation_time="now")


def test_a_policy_that_is_not_a_recommendation_policy_is_refused():
    """Truthy, so the `policy or default` fallback keeps it; without the gate the first
    policy read is an AttributeError on an int."""

    with pytest.raises(PipelineError):
        _recommend(policy=42)


def test_a_current_state_that_is_not_canonical_is_refused():
    """Not None — None is a typed MISSING_CANONICAL_STATE abstention, a different
    contract this gate does not own."""

    with pytest.raises(PipelineError):
        _recommend(current_state="state")


def test_a_forecast_evidence_that_is_not_typed_evidence_is_refused():
    with pytest.raises(PipelineError):
        _recommend(forecast_evidence="evidence")


def test_constraints_that_are_not_operating_constraints_are_refused():
    with pytest.raises(PipelineError):
        _recommend(constraints="tight")


def test_a_validity_seconds_that_is_not_a_positive_finite_number_is_refused():
    """NaN: without the gate, `timedelta(seconds=NaN)` raises a plain ValueError, not
    the pipeline contract."""

    with pytest.raises(PipelineError):
        _recommend(validity_seconds=float("nan"))


def test_a_cost_book_that_is_not_a_cost_book_is_refused():
    with pytest.raises(PipelineError):
        _recommend(cost_book="book")


def test_a_topology_that_is_not_a_dependency_topology_is_refused():
    with pytest.raises(PipelineError):
        _recommend(topology="topo")


def test_every_scoring_failure_is_pre_gated_into_a_typed_abstention():
    """Evidence for the `unreachable-behind-earlier-guard` exclusion of the pipeline's
    ScoringError arm.

    The same inputs that make `build_context` raise are abstained by the pipeline's own
    pre-gates before the context is ever built: an abstained forecast is refused as
    FORECAST_ABSTAINED here, and raises ScoringError only when the context build is
    invoked directly. The arm is a jacket the pre-gates keep unreachable, so its
    reason-collapse mutation has nothing to observe it.
    """

    subj = H.subject()
    abstained = H.build_abstained_forecast(subj=subj)
    out = _recommend(subj=subj, forecast_evidence=abstained)
    assert isinstance(out, RecommendationAbstention)
    assert out.reason is RecommendationAbstentionReason.FORECAST_ABSTAINED
    with pytest.raises(ScoringError):
        _build_context(forecast_evidence=abstained, subj=subj)


# ======================================================================================= #
# recommendation.py — EvaluatedCandidate
# ======================================================================================= #

import dataclasses  # noqa: E402

from ugence_cloud_scaling_controller.forecasting import ForecastHorizon  # noqa: E402
from ugence_cloud_scaling_controller.forecasting.window import WindowError  # noqa: E402
from ugence_cloud_scaling_controller.planning import (  # noqa: E402
    CapacityActionRecommendation,
    EvaluatedCandidate,
    RecommendationError,
    evaluate_feasibility,
    generate_candidates,
    score_candidate,
)
from ugence_cloud_scaling_controller.planning.scoring import select_best  # noqa: E402


def _evaluated(**over):
    fields = dict(
        plan=_plan(),
        feasible=True,
        violations=(),
        cost_delta_minor=1000,
        score_breakdown=_breakdown(),
    )
    fields.update(over)
    return EvaluatedCandidate(**fields)


def test_an_evaluated_plan_that_is_not_a_candidate_plan_is_refused():
    with pytest.raises(RecommendationError):
        _evaluated(plan="plan")


def test_a_feasible_flag_that_is_not_a_bool_is_refused():
    """1 is truthy, so every feasible-branch invariant passes on it; only the type gate
    can refuse it."""

    with pytest.raises(RecommendationError):
        _evaluated(feasible=1)


def test_a_violation_that_is_not_a_non_empty_string_is_refused():
    with pytest.raises(RecommendationError):
        _evaluated(feasible=False, violations=("",), score_breakdown=None)


def test_a_cost_delta_that_is_not_an_int_is_refused():
    with pytest.raises(RecommendationError):
        _evaluated(cost_delta_minor="0")


def test_a_feasible_candidate_with_violations_is_refused():
    with pytest.raises(RecommendationError):
        _evaluated(violations=("below_min_capacity",))


def test_a_feasible_candidate_without_a_score_is_refused():
    with pytest.raises(RecommendationError):
        _evaluated(score_breakdown=None)


def test_an_infeasible_candidate_without_violations_is_refused():
    with pytest.raises(RecommendationError):
        _evaluated(feasible=False, violations=(), score_breakdown=None)


def test_an_infeasible_candidate_with_a_score_is_refused():
    with pytest.raises(RecommendationError):
        _evaluated(feasible=False, violations=("below_min_capacity",))


def test_an_evaluated_payload_that_is_not_a_mapping_is_refused():
    with pytest.raises(RecommendationError):
        EvaluatedCandidate.from_dict(["plan", "feasible", "violations", "cost_delta_minor"])


def test_an_evaluated_payload_carrying_an_unknown_field_is_refused():
    payload = _evaluated().to_canonical_dict()
    payload["confidence"] = 1.0
    with pytest.raises(RecommendationError):
        EvaluatedCandidate.from_dict(payload)


def test_an_evaluated_payload_missing_a_required_field_is_refused():
    with pytest.raises(RecommendationError):
        EvaluatedCandidate.from_dict({})


# ======================================================================================= #
# recommendation.py — CapacityActionRecommendation, perturbed from a genuine record
# ======================================================================================= #


class _Delegate:
    """Not an instance of the declared type, but behaves exactly like one."""

    def __init__(self, real):
        object.__setattr__(self, "_real", real)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_real"), name)


@pytest.fixture(scope="module")
def record():
    """One genuine pipeline-built recommendation, perturbed per test via replace()."""

    out = _recommend()
    assert isinstance(out, CapacityActionRecommendation)
    return out


def _perturbed(record, **over):
    return dataclasses.replace(record, **over)


def test_a_recommendation_id_that_is_not_a_non_empty_string_is_refused(record):
    with pytest.raises(RecommendationError):
        _perturbed(record, recommendation_id="")


def test_a_record_forecast_evidence_that_is_not_typed_evidence_is_refused(record):
    with pytest.raises(RecommendationError):
        _perturbed(record, forecast_evidence="fe")


def test_a_record_state_that_is_not_canonical_is_refused(record):
    with pytest.raises(RecommendationError):
        _perturbed(record, current_state="state")


def test_a_record_cost_book_that_is_not_a_cost_book_is_refused(record):
    with pytest.raises(RecommendationError):
        _perturbed(record, cost_book="book")


def test_a_record_constraints_that_are_not_operating_constraints_are_refused(record):
    """A delegating impostor, because a plain wrong-typed value dies inside the
    context build whose except-jacket re-raises the same class. The impostor answers
    every read the whole re-validation makes, so with the type gate removed the record
    constructs successfully."""

    with pytest.raises(RecommendationError):
        _perturbed(record, constraints=_Delegate(record.constraints))


def test_a_record_policy_that_is_not_a_recommendation_policy_is_refused(record):
    with pytest.raises(RecommendationError):
        _perturbed(record, policy="pol")


def test_a_record_topology_that_is_not_a_dependency_topology_is_refused(record):
    with pytest.raises(RecommendationError):
        _perturbed(record, topology="topo")


def test_a_record_time_that_is_not_a_datetime_is_refused(record):
    with pytest.raises(RecommendationError):
        _perturbed(record, recommendation_time="now")


def test_a_record_validity_that_is_not_a_positive_finite_number_is_refused(record):
    """NaN: the validity-window comparison downstream builds `timedelta(seconds=NaN)`,
    a plain ValueError rather than the recommendation contract."""

    with pytest.raises(RecommendationError):
        _perturbed(record, validity_seconds=float("nan"))


def test_a_record_candidate_that_is_not_evaluated_is_refused(record):
    with pytest.raises(RecommendationError):
        _perturbed(record, evaluated_candidates=record.evaluated_candidates + ("x",))


def test_a_forecast_for_a_different_subject_is_refused(record):
    """Numerically identical forecast bound to another tenant: nothing downstream keys
    on the forecast's subject, so with the binding gate removed the record constructs."""

    other = H.subject(tenant_id="tenant-2")
    with pytest.raises(RecommendationError):
        _perturbed(record, forecast_evidence=H.build_forecast_evidence(8, subj=other))


def test_a_cost_book_for_a_different_subject_is_refused(record):
    """Same workload, different tenant: the context prices by workload_id, so the
    mutant finds the price and constructs."""

    other = H.subject(tenant_id="tenant-2")
    with pytest.raises(RecommendationError):
        _perturbed(record, cost_book=H.cost_book(subj=other))


def test_a_topology_for_a_different_subject_is_refused(record):
    """Edge-free, so the context's dependency selection is untouched and only the
    binding gate can refuse it."""

    other = H.subject(tenant_id="tenant-2")
    topo = DependencyTopology(subject=other, as_of=H.at(120.0), edges=())
    with pytest.raises(RecommendationError):
        _perturbed(record, topology=topo)


# ======================================================================================= #
# recommendation.py — temporal gates, via a manually assembled record
# ======================================================================================= #


def _manual_record(*, rec_time, policy=None, validity=60.0, selected=None):
    """Assemble a record exactly the way the pipeline would, but without the pipeline's
    own temporal pre-gates — the record's construction-time validation is the subject
    under test, so the inputs must reach it."""

    subj = H.subject()
    pol = policy or H.policy()
    fe = H.build_forecast_evidence(8, subj=subj)
    st = H.replicas_state(H.at(100.0), 6, subj=subj)
    cb = H.cost_book(subj=subj)
    con = H.constraints()
    ctx = build_context(fe, st, None, cb, con, recommendation_time=rec_time)
    plans = generate_candidates(
        ctx.primary_subject, ctx.current_capacity, ctx.required_capacity,
        allowed_step=con.allowed_step, min_capacity=con.min_capacity,
        max_capacity=con.effective_ceiling(), dependency=ctx.dependency_subject,
        dependency_current=ctx.dependency_current, dependency_required=ctx.dependency_required,
    )
    ecs = []
    for p in plans:
        viol = tuple(v.value for v in evaluate_feasibility(p, ctx))
        cost = plan_cost_delta_minor(p, ctx)
        if viol:
            ecs.append(EvaluatedCandidate(plan=p, feasible=False, violations=viol,
                                          cost_delta_minor=cost))
        else:
            ecs.append(EvaluatedCandidate(plan=p, feasible=True, violations=(),
                                          cost_delta_minor=cost,
                                          score_breakdown=score_candidate(p, ctx, pol)))
    triples = [(ec.plan.plan_id, ec.score_breakdown.features["coverage"], ec.total_score)
               for ec in ecs if ec.feasible]
    winner, _ambiguous = select_best(triples, pol)
    sel = selected or winner or sorted(t[0] for t in triples)[0]
    return CapacityActionRecommendation(
        recommendation_id="manual-1", forecast_evidence=fe, current_state=st,
        cost_book=cb, constraints=con, policy=pol, evaluated_candidates=tuple(ecs),
        selected_plan_id=sel, recommendation_time=rec_time, validity_seconds=validity,
    )


def test_a_record_timed_before_the_forecast_cutoff_is_refused():
    """State observed earlier still, so only the cutoff gate can refuse it; with the
    gate removed every recomputation matches and the record constructs."""

    with pytest.raises(RecommendationError):
        _manual_record(rec_time=H.at(170.0))


def test_a_record_timed_at_or_past_the_forecast_horizon_is_refused_either_way():
    """Evidence for the `diagnostic-only` exclusion of the horizon-expiry gate: with it
    removed, the validity-window gate refuses the same input with the same class —
    validity_end > rec_time >= forecast_for, and forecast_for is pinned to the
    canonical endpoint two gates above."""

    with pytest.raises(RecommendationError):
        _manual_record(rec_time=H.at(2000.0))


def test_a_non_positive_forecast_horizon_cannot_be_constructed_at_all():
    """Evidence for the `unreachable-behind-earlier-guard` exclusion of the record's
    horizon-positivity gate: the forecasting layer's own constructor is the earlier
    guard, so no forecast the record can embed carries a non-positive horizon."""

    with pytest.raises(WindowError):
        ForecastHorizon(seconds=0)
    with pytest.raises(WindowError):
        ForecastHorizon(seconds=-1.0)


def test_an_all_tied_selection_is_refused_as_a_recommendation_error():
    """Evidence for the `diagnostic-only` exclusion of the ambiguity gate: with every
    weight zero all feasible candidates tie, `select_best` answers (None, True), and
    with the gate removed the winner-identity gate refuses None != selected with the
    same class."""

    zero = H.policy(w_coverage=0.0, w_bottleneck_risk=0.0, w_reliability_risk=0.0,
                    w_cost=0.0, w_change_magnitude=0.0, w_uncertainty=0.0, w_hold_bias=0.0)
    with pytest.raises(RecommendationError):
        _manual_record(rec_time=H.at(190.0), policy=zero, selected="plan-no-change")


# ======================================================================================= #
# recommendation.py — tamper detection, via forged evaluated candidates
# ======================================================================================= #


def _swap(record, plan_id, forged):
    new = tuple(forged if ec.plan.plan_id == plan_id else ec
                for ec in record.evaluated_candidates)
    return dataclasses.replace(record, evaluated_candidates=new)


def _capped_record():
    """A record with a genuinely infeasible candidate: the +2 step exceeds the cost cap
    while the +1 step stays under it."""

    out = _recommend(constraints=H.constraints(max_cost_increase_minor=1500))
    assert isinstance(out, CapacityActionRecommendation)
    infeasible = [ec for ec in out.evaluated_candidates if not ec.feasible]
    assert infeasible, "scenario must produce an infeasible candidate"
    return out, infeasible[0]


def test_a_forged_feasibility_flag_is_refused(record):
    """Evidence for the `diagnostic-only` exclusion of the feasibility-recompute gate.

    The gates interlock: a candidate's own invariant ties `feasible` to the emptiness
    of `violations`, and the recompute derives expected feasibility from expected
    violations — so any forged flag that can be constructed at all also carries a
    violations set that mismatches the recomputation, and the violations gate refuses
    it with the same class. Both flip directions are exercised here.
    """

    out, inf = _capped_record()
    forged_up = EvaluatedCandidate(plan=inf.plan, feasible=True, violations=(),
                                   cost_delta_minor=inf.cost_delta_minor,
                                   score_breakdown=_breakdown())
    with pytest.raises(RecommendationError):
        _swap(out, inf.plan.plan_id, forged_up)

    feas = next(ec for ec in record.evaluated_candidates
                if ec.feasible and ec.plan.plan_id != record.selected_plan_id)
    forged_down = EvaluatedCandidate(plan=feas.plan, feasible=False,
                                     violations=("cooldown_active",),
                                     cost_delta_minor=feas.cost_delta_minor)
    with pytest.raises(RecommendationError):
        _swap(record, feas.plan.plan_id, forged_down)


def test_a_forged_violation_set_is_refused():
    """Feasibility and cost kept truthful, the violation *names* swapped — only the
    violations-recompute gate can see it, and with it removed the record constructs."""

    out, inf = _capped_record()
    forged = EvaluatedCandidate(plan=inf.plan, feasible=False,
                                violations=("cooldown_active",),
                                cost_delta_minor=inf.cost_delta_minor)
    with pytest.raises(RecommendationError):
        _swap(out, inf.plan.plan_id, forged)


def _losing_feasible(record):
    return next(ec for ec in record.evaluated_candidates
                if ec.feasible and ec.plan.plan_id != record.selected_plan_id)


def test_a_forged_total_score_is_refused(record):
    """Lowered — never raised — on a losing candidate, so the selection outcome is
    untouched and only the score-recompute gate can see the forgery. The contribution
    moves with the total to keep the breakdown internally consistent."""

    ec = _losing_feasible(record)
    sb = ec.score_breakdown
    contributions = dict(sb.contributions)
    contributions["coverage"] -= 0.5
    forged_sb = ScoreBreakdown(features=dict(sb.features), contributions=contributions,
                               total_score=sb.total_score - 0.5, policy_id=sb.policy_id,
                               policy_digest=sb.policy_digest)
    forged = dataclasses.replace(ec, score_breakdown=forged_sb)
    with pytest.raises(RecommendationError):
        _swap(record, ec.plan.plan_id, forged)


def test_a_score_bound_to_a_foreign_policy_digest_is_refused(record):
    ec = _losing_feasible(record)
    sb = ec.score_breakdown
    forged_sb = ScoreBreakdown(features=dict(sb.features),
                               contributions=dict(sb.contributions),
                               total_score=sb.total_score, policy_id=sb.policy_id,
                               policy_digest="sha256:" + "0" * 64)
    forged = dataclasses.replace(ec, score_breakdown=forged_sb)
    with pytest.raises(RecommendationError):
        _swap(record, ec.plan.plan_id, forged)


def test_a_forged_feature_value_is_refused(record):
    """A non-coverage feature on a losing candidate, with contributions and total
    untouched: the selection triple reads only coverage and the total, so nothing but
    the per-feature recompute gate can see it."""

    ec = _losing_feasible(record)
    sb = ec.score_breakdown
    features = dict(sb.features)
    features["uncertainty"] += 0.5
    forged_sb = ScoreBreakdown(features=features, contributions=dict(sb.contributions),
                               total_score=sb.total_score, policy_id=sb.policy_id,
                               policy_digest=sb.policy_digest)
    forged = dataclasses.replace(ec, score_breakdown=forged_sb)
    with pytest.raises(RecommendationError):
        _swap(record, ec.plan.plan_id, forged)


def test_the_candidate_set_gates_behind_the_canonical_binding_are_evidenced(record):
    """Evidence for four exclusions in the candidate-set machinery, each measured:

    - empty evaluated_candidates (`diagnostic-only`): the canonical set-equality gate
      refuses an empty set with the same class, and the canonical set is never empty;
    - the duplicate gates at the by-id build and the recompute loop (`diagnostic-only`,
      mutually jacketing): a duplicated candidate is refused by whichever of the two
      stands, with the same class, so neither's mutation is observable while the other
      exists;
    - a missing NO_CHANGE baseline (`unreachable-behind-earlier-guard`): canonical
      generation always emits NO_CHANGE first, so its absence from the evaluated set
      trips the set-equality gate before the baseline gate is reached;
    - a selected id pointing at an infeasible candidate (`diagnostic-only`): the winner
      is drawn from feasible triples only, so the winner-identity gate refuses the
      mismatch with the same class.
    """

    with pytest.raises(RecommendationError):
        dataclasses.replace(record, evaluated_candidates=())

    dup = record.evaluated_candidates + (record.evaluated_candidates[0],)
    with pytest.raises(RecommendationError):
        dataclasses.replace(record, evaluated_candidates=dup)

    sans_baseline = tuple(ec for ec in record.evaluated_candidates
                          if ec.plan.action_kind is not ActionKind.NO_CHANGE)
    with pytest.raises(RecommendationError):
        dataclasses.replace(record, evaluated_candidates=sans_baseline)

    out, inf = _capped_record()
    with pytest.raises(RecommendationError):
        dataclasses.replace(out, selected_plan_id=inf.plan.plan_id)


def test_canonical_candidate_generation_is_unique_by_construction():
    """Evidence for the `equivalent-mutant` exclusion of the defensive uniqueness gate:
    across a spread of configurations, generation never emits two plans with one id."""

    for cur, req, step in ((6, 8, 1), (6, 8, 2), (8, 2, 3), (5, 5, 1), (0, 20, 4)):
        plans = generate_candidates(
            H.subject(), current_capacity=cur, required_capacity=req,
            allowed_step=step, min_capacity=0, max_capacity=20,
        )
        ids = [p.plan_id for p in plans]
        assert len(ids) == len(set(ids))


# ======================================================================================= #
# recommendation.py — from_dict probes
# ======================================================================================= #


def test_a_recommendation_payload_that_is_not_a_mapping_is_refused():
    """The full required-name list as a list: required-minus-set and surplus arithmetic
    both pass on it, and the first string indexing is a TypeError."""

    with pytest.raises(RecommendationError):
        CapacityActionRecommendation.from_dict([
            "recommendation_id", "forecast_evidence", "canonical_state", "cost_book",
            "constraints", "policy", "evaluated_candidates", "selected_plan_id",
            "recommendation_time", "validity_seconds",
        ])


def test_a_recommendation_payload_time_that_is_not_a_datetime_is_refused(record):
    """The topology is malformed too: the reconstruction right after this gate parses
    it through `DependencyTopology.from_dict`, whose `TopologyError` is a different
    contract — so the typed refusal can only be this gate's."""

    payload = dict(record.to_canonical_dict())
    payload["recommendation_time"] = "now"
    payload["topology"] = 123
    with pytest.raises(RecommendationError):
        CapacityActionRecommendation.from_dict(payload)


def test_a_forecast_evidence_payload_that_is_not_a_mapping_is_refused():
    """Without the gate, `.get` on the list is an AttributeError."""

    from ugence_cloud_scaling_controller.planning.recommendation import (
        _forecast_evidence_from_dict,
    )
    with pytest.raises(RecommendationError):
        _forecast_evidence_from_dict(["forecast"])


def test_an_embedded_forecast_that_is_not_a_mapping_is_refused():
    from ugence_cloud_scaling_controller.planning.recommendation import (
        _forecast_evidence_from_dict,
    )
    with pytest.raises(RecommendationError):
        _forecast_evidence_from_dict({"forecast": "fc"})


# ======================================================================================= #
# recommendation.py — RecommendationAbstention
# ======================================================================================= #


def _abstention(**over):
    fields = dict(
        subject=H.subject(),
        reason=RecommendationAbstentionReason.MISSING_FORECAST,
        recommendation_time=T0,
    )
    fields.update(over)
    return RecommendationAbstention(**fields)


def test_an_abstention_subject_that_is_not_a_subject_is_refused():
    with pytest.raises(RecommendationError):
        _abstention(subject="app")


def test_an_abstention_reason_that_is_not_the_typed_enum_is_refused():
    """The member's own string value, which is not the member."""

    with pytest.raises(RecommendationError):
        _abstention(reason="missing_forecast")


def test_an_abstention_time_that_is_not_a_datetime_is_refused():
    with pytest.raises(RecommendationError):
        _abstention(recommendation_time="now")


def test_an_abstention_that_disclaims_advisory_only_is_refused():
    with pytest.raises(RecommendationError):
        _abstention(advisory_only=False)


def test_an_abstention_claiming_actuation_is_refused():
    with pytest.raises(RecommendationError):
        _abstention(actuation_performed=True)


def test_the_abstention_canonical_dict_carries_its_evidence_digest_by_default():
    """The `include_digest` arm: the default serialization must embed the digest, and
    the digest's own self-exclusion must omit it."""

    ab = _abstention()
    assert ab.to_canonical_dict()["evidence_digest"] == ab.digest()
    assert "evidence_digest" not in ab.to_canonical_dict(include_digest=False)


def test_an_abstention_payload_that_is_not_a_mapping_is_refused():
    with pytest.raises(RecommendationError):
        RecommendationAbstention.from_dict(["subject", "reason", "recommendation_time"])


def test_an_abstention_payload_missing_a_required_field_is_refused():
    with pytest.raises(RecommendationError):
        RecommendationAbstention.from_dict({})


def test_an_abstention_payload_time_that_is_not_a_datetime_is_refused():
    """The subject is malformed too, so the mutant's fallback is the subject parser's
    SubjectError — a different contract."""

    with pytest.raises(RecommendationError):
        RecommendationAbstention.from_dict(
            {"subject": "x", "reason": "missing_forecast", "recommendation_time": "now"}
        )
