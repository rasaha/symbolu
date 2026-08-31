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
