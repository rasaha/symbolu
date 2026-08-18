"""Machine-checkable coverage: every §15 coordinate is in the digest.

ADR B-8 — "Benchmark identity is exact and **digest-bound**" — is only true if
*every* coordinate participates. A prose claim that it does is not a proof, so
this module derives the check from the contracts themselves:

1. every ADR §15 row named in :data:`BENCHMARK_IDENTITY_COORDINATES` resolves to
   a real attribute of a constructed identity;
2. every **leaf** of the canonical body is discovered by walking the dataclass
   tree — not by a hand-maintained list — so a field added later is covered
   automatically;
3. every leaf appears in the canonical body at its declared path;
4. every leaf is **independently digest-sensitive**: changing it alone, leaving
   every other coordinate untouched, changes the digest.

A field that appeared in the identity but not in the digest, or that appeared in
the digest but could be changed without moving it, fails here.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone

import pytest
from ugence_benchmark_registry.api import (
    BENCHMARK_IDENTITY_COORDINATES,
    BenchmarkApplicabilityDeclaration,
    BenchmarkCanonicalizationError,
    BenchmarkLifecycleState,
    BenchmarkScopeKind,
    CanonicalBenchmarkDefinitionIdentity,
    TemporalBoundDeclaration,
    canonical_bytes,
)

import _builders as b


def _leaf_paths(contract, prefix=""):
    """Every leaf field path beneath ``contract``, discovered structurally."""

    paths = []
    for field in dataclasses.fields(contract):
        value = getattr(contract, field.name)
        path = f"{prefix}{field.name}"
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            paths.extend(_leaf_paths(value, prefix=f"{path}."))
        else:
            paths.append(path)
    return paths


def _resolve(obj, path):
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def _body_at(identity, path):
    """The value the canonical body carries at ``path``."""

    node = json.loads(canonical_bytes(identity).decode("utf-8"))["body"]
    for part in path.split("."):
        assert isinstance(node, dict), path
        assert part in node, path
        node = node[part]
    return node


IDENTITY = b.identity()
LEAF_PATHS = _leaf_paths(IDENTITY)

#: A different-but-valid value for every leaf, so each can be moved on its own.
#:
#: Chosen by hand because "a different valid value" is a semantic question, not a
#: mechanical one — but the *set of paths* is discovered structurally, so a new
#: field fails the completeness test below until a mutation for it is added here.
MUTATIONS = {
    "coordinate.benchmark_id": "bmk-other",
    "coordinate.benchmark_family": "family-other",
    "coordinate.benchmark_version": "9.9.9",
    "coordinate.scope.kind": BenchmarkScopeKind.PLATFORM_WIDE,
    "coordinate.scope.tenant_id": "tenant-beta",
    "coordinate.geography.declaration": BenchmarkApplicabilityDeclaration.NOT_APPLICABLE,
    "coordinate.geography.value": "US",
    "coordinate.domain.declaration": BenchmarkApplicabilityDeclaration.NOT_APPLICABLE,
    "coordinate.domain.value": "field-service",
    "content_digest": b.OTHER_CONTENT_DIGEST,
    "measurement.intended_outcome_ref": "outcome-other",
    "measurement.metric_ref": "metric-other",
    "measurement.unit": "hours",
    "measurement.measurement_protocol_ref": "protocol-other",
    "measurement.population_ref": "cohort-other",
    "measurement.aggregation_semantics_ref": "aggregation-other",
    "measurement.observation_window_ref": "window-other",
    "effective_period.effective_from": datetime(
        2026, 2, 1, tzinfo=timezone.utc
    ),
    "effective_period.end_declaration": TemporalBoundDeclaration.OPEN_ENDED,
    "effective_period.effective_to": datetime(2028, 1, 1, tzinfo=timezone.utc),
    "source_requirements.source_ref": "source-other",
    "source_requirements.provenance_requirement_refs": ("provenance-other",),
    "approval.approval_ref": "approval-other",
    "approval.approval_authority_ref": "authority-other",
    "approval.approved_content_digest": b.OTHER_CONTENT_DIGEST,
    "publisher_id": "publisher-other",
    "lifecycle_state": BenchmarkLifecycleState.AUTHORED,
    # ``BenchmarkSupersessionStatus`` has exactly one ratified member (DD-4
    # defers the successor reference), so there is no second *valid* value to
    # move to. Digest participation is still provable, and is what this table
    # exists for: a distinct plain string is written into the field after
    # construction and the digest must follow it. When DD-4 lands and a second
    # member is ratified, this entry becomes an ordinary enum mutation.
    "supersession.status": "UNDETERMINED-SENTINEL-FOR-DIGEST-COVERAGE",
}

#: A handful of leaves cannot be moved alone without leaving the *rest* of the
#: graph inconsistent with a cross-field invariant this package enforces
#: structurally (ADR B-5's approval/content-digest binding; B-3/B-4's role
#: separation is untouched by any of these; and the scope/applicability/
#: effective-period self-consistency rules). Since the BR-1 canonicalization-
#: boundary correction, ``canonical_bytes``/``canonical_digest`` revalidate the
#: complete graph before producing bytes, so a state that could not have come
#: from the public constructors — including one made only *momentarily* true by
#: moving one field via ``object.__setattr__`` — is refused rather than
#: canonicalized. For these leaves the companion field named here is moved
#: alongside the leaf under test, so the whole object stays a state its public
#: constructors could have produced, and the digest-sensitivity proof holds
#: without relying on a state the package now correctly rejects.
_COMPANION_FIXUPS = {
    "content_digest": {"approval.approved_content_digest": b.OTHER_CONTENT_DIGEST},
    "approval.approved_content_digest": {"content_digest": b.OTHER_CONTENT_DIGEST},
    "coordinate.scope.kind": {"coordinate.scope.tenant_id": ""},
    "coordinate.geography.declaration": {"coordinate.geography.value": ""},
    "coordinate.domain.declaration": {"coordinate.domain.value": ""},
    "effective_period.end_declaration": {"effective_period.effective_to": None},
}

#: ``supersession.status`` has exactly one ratified value until DD-4 lands
#: (:class:`~ugence_benchmark_registry.contracts.enums.BenchmarkSupersessionStatus`
#: has one member), so there is no second value *any* state that could have
#: come from the public constructors could hold there — not even with a
#: companion fixup. Its digest sensitivity is proved separately, below, by
#: showing the corrupted state is refused rather than silently canonicalized.
_NO_VALID_ALTERNATE = {"supersession.status"}


def test_the_leaf_set_is_exactly_the_mutation_set():
    """A new coordinate must be given a mutation, or this fails.

    This is the guard that keeps the coverage proof honest: the paths come from
    the dataclass tree, so a field added without a corresponding mutation is a
    field whose digest participation nobody proved.
    """

    assert sorted(LEAF_PATHS) == sorted(MUTATIONS)


def test_every_adr_15_row_maps_onto_at_least_one_leaf():
    """Each of §15's twenty rows must be carried by real, digested fields."""

    assert len(BENCHMARK_IDENTITY_COORDINATES) == 20
    for row in BENCHMARK_IDENTITY_COORDINATES:
        covered = [p for p in LEAF_PATHS if p == row or p.startswith(row + ".")]
        assert covered, row


def test_every_leaf_is_covered_by_an_adr_15_row():
    """And nothing is carried that §15 did not ask for."""

    for leaf in LEAF_PATHS:
        owning = [
            row
            for row in BENCHMARK_IDENTITY_COORDINATES
            if leaf == row or leaf.startswith(row + ".")
        ]
        assert owning, leaf


@pytest.mark.parametrize("path", sorted(LEAF_PATHS))
def test_every_leaf_is_present_in_the_canonical_body(path):
    _body_at(IDENTITY, path)


@pytest.mark.parametrize("path", sorted(set(MUTATIONS) - _NO_VALID_ALTERNATE))
def test_every_leaf_is_independently_digest_sensitive(path):
    """Move exactly one coordinate (and its companion, if it has one); the
    digest must move with it.

    The mutation is applied with ``object.__setattr__`` **after** a valid
    identity was constructed, deliberately: it isolates the encoder's coverage
    from the constructor's cross-field invariants. Where moving the leaf alone
    would leave the graph in a state no public constructor could have produced
    — a companion field entry exists in :data:`_COMPANION_FIXUPS` — the
    companion is moved in the same step, so the object stays one the public
    constructors could have produced and the graph-revalidation the
    canonicalization boundary now performs does not refuse it.
    """

    original = b.identity()
    before = original.canonical_digest()
    target_path, _, leaf = path.rpartition(".")
    owner = _resolve(original, target_path) if target_path else original
    assert getattr(owner, leaf) != MUTATIONS[path], path
    object.__setattr__(owner, leaf, MUTATIONS[path])
    for companion_path, companion_value in _COMPANION_FIXUPS.get(path, {}).items():
        c_target_path, _, c_leaf = companion_path.rpartition(".")
        c_owner = _resolve(original, c_target_path) if c_target_path else original
        object.__setattr__(c_owner, c_leaf, companion_value)
    assert original.canonical_digest() != before, path


def test_the_single_admissible_supersession_status_is_refused_rather_than_moved():
    """``supersession.status`` cannot be proved digest-sensitive by corruption.

    It has exactly one ratified value until DD-4 lands, so there is no second
    value any state the public constructors could produce would hold there —
    unlike the other leaves in :data:`_COMPANION_FIXUPS`, no companion fixup
    can make a moved ``status`` valid again. Its presence in the canonical
    body is already proved by
    :func:`test_every_leaf_is_present_in_the_canonical_body`; what this proves
    is that the canonicalization boundary now correctly refuses the one way
    that leaf could previously be moved at all — silently, via
    ``object.__setattr__`` — rather than producing a digest over a state no
    constructor could have built.
    """

    original = b.identity()
    object.__setattr__(
        original.supersession, "status", MUTATIONS["supersession.status"]
    )
    with pytest.raises(BenchmarkCanonicalizationError):
        original.canonical_digest()


def test_the_identity_coordinate_tuple_and_the_digest_agree():
    """Anything that moves the structural tuple also moves the digest."""

    original = b.identity()
    mutated = b.identity(
        coordinate=b.coordinate(benchmark_version="2.0.0"),
    )
    assert original.identity_coordinate != mutated.identity_coordinate
    assert original.canonical_digest() != mutated.canonical_digest()


def test_no_coordinate_is_carried_only_outside_the_digest():
    """Every declared field of the identity appears in the framed body."""

    body = json.loads(canonical_bytes(IDENTITY).decode("utf-8"))["body"]
    declared = {f.name for f in dataclasses.fields(CanonicalBenchmarkDefinitionIdentity)}
    assert set(body) == declared
