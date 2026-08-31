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
