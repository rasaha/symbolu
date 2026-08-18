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


@pytest.mark.parametrize("path", sorted(MUTATIONS))
def test_every_leaf_is_independently_digest_sensitive(path):
    """Move exactly one coordinate; the digest must move with it.

    The mutation is applied with ``object.__setattr__`` **after** a valid
    identity was constructed, deliberately: it isolates the encoder's coverage
    from the constructor's cross-field invariants, so a coordinate is proved
    digest-bound even where a legal constructor call could not move it alone
    (``approval.approved_content_digest`` must equal ``content_digest``, and
    ``supersession.status`` has one admissible value).
    """

    original = b.identity()
    before = original.canonical_digest()
    target_path, _, leaf = path.rpartition(".")
    owner = _resolve(original, target_path) if target_path else original
    assert getattr(owner, leaf) != MUTATIONS[path], path
    object.__setattr__(owner, leaf, MUTATIONS[path])
    assert original.canonical_digest() != before, path


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
