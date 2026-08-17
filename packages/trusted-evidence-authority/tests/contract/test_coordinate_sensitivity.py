"""Every load-bearing coordinate changes the digest; replay is detectable.

ADR §26.5: "every artifact binds exact identity + digests; tenant, context,
subject and ``AssessedSystemBinding`` mismatches are refusals, so a favourable
result for one system/tenant is **mechanically detectable when replayed under
another**". These tests prove the mechanism, coordinate by coordinate, rather
than asserting that a helper was called.
"""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest
from _builders import (
    CONTENT_DIGEST,
    OTHER_DIGEST,
    identity,
    observation,
    provenance,
    scope,
    schema,
)
from ugence_trusted_evidence_authority.api import (
    ApplicabilityCoordinate,
    ApplicabilityDeclaration,
    CanonicalEvidenceIdentity,
    EvidenceLifecycleState,
)

BASELINE = identity()
BASELINE_DIGEST = BASELINE.canonical_digest()


#: One mutation per load-bearing coordinate of the whole identity graph, keyed
#: by the coordinate's dotted path. Every one must move the digest.
MUTATIONS = {
    "evidence_id": dict(evidence_id="ev-2"),
    "evidence_type": dict(evidence_type="ATTESTATION"),
    "schema.schema_id": dict(schema=schema(schema_id="ugence.evidence.other")),
    "schema.schema_version": dict(schema=schema(schema_version="2")),
    "content_digest": dict(content_digest=OTHER_DIGEST),
    "observation.producer_id": dict(observation=observation(producer_id="prod-b")),
    "observation.issuer_id": dict(observation=observation(issuer_id="issuer-c")),
    "observation.issuer_id/absent": dict(observation=observation(issuer_id="")),
    "observation.collected_at": dict(
        observation=observation(collected_at=BASELINE.observation.collected_at + timedelta(seconds=1))
    ),
    "observation.observed_from": dict(
        observation=observation(
            observed_from=BASELINE.observation.observed_from - timedelta(seconds=1)
        )
    ),
    "observation.observed_to": dict(
        observation=observation(
            observed_to=BASELINE.observation.observed_to + timedelta(seconds=1)
        )
    ),
    "observation.observed_to/absent": dict(observation=observation(observed_to=None)),
    "scope.tenant_id": dict(scope=scope(tenant_id="tenant-2")),
    "scope.assessment_context_ref": dict(scope=scope(assessment_context_ref="ctx-2")),
    "scope.assessment_context_digest": dict(
        scope=scope(assessment_context_digest=OTHER_DIGEST)
    ),
    "scope.subject_ref": dict(scope=scope(subject_ref="subject-2")),
    "scope.assessment_purpose_ref": dict(
        scope=scope(assessment_purpose_ref="purpose-forecast")
    ),
    "scope.usage_scope_ref": dict(scope=scope(usage_scope_ref="scope-evaluation-only")),
    "scope.assessed_system_binding_ref": dict(
        scope=scope(assessed_system_binding_ref="bind-2")
    ),
    "scope.assessed_system_binding_digest": dict(
        scope=scope(assessed_system_binding_digest=OTHER_DIGEST)
    ),
    "scope.assessed_system_applicability": dict(
        scope=scope(
            assessed_system_applicability=ApplicabilityDeclaration.NOT_APPLICABLE,
            assessed_system_binding_ref="",
            assessed_system_binding_digest="",
        )
    ),
    "provenance.chain_ref": dict(provenance=provenance(chain_ref="chain-2")),
    "provenance.custody_refs/content": dict(
        provenance=provenance(custody_refs=("custody-1", "custody-3"))
    ),
    "provenance.custody_refs/order": dict(
        provenance=provenance(custody_refs=("custody-2", "custody-1"))
    ),
    "provenance.custody_refs/length": dict(
        provenance=provenance(custody_refs=("custody-1",))
    ),
    "lifecycle_state": dict(lifecycle_state=EvidenceLifecycleState.RETAINED),
    "geography/value": dict(geography=ApplicabilityCoordinate.applicable("EU")),
    "geography/declaration": dict(geography=ApplicabilityCoordinate.not_applicable()),
    "domain/declaration": dict(domain=ApplicabilityCoordinate.applicable("support")),
    "intended_outcome/value": dict(
        intended_outcome=ApplicabilityCoordinate.applicable("cost-reduction")
    ),
    "valid_from": dict(valid_from=BASELINE.valid_from + timedelta(seconds=1)),
    "valid_from/absent": dict(valid_from=None),
    "valid_to": dict(valid_to=BASELINE.valid_to + timedelta(seconds=1)),
    "valid_to/absent": dict(valid_to=None),
}


@pytest.mark.parametrize("coordinate", sorted(MUTATIONS))
def test_every_load_bearing_coordinate_changes_the_digest(coordinate):
    mutated = identity(**MUTATIONS[coordinate])
    assert mutated != BASELINE, coordinate
    assert mutated.canonical_bytes() != BASELINE.canonical_bytes(), coordinate
    assert mutated.canonical_digest() != BASELINE_DIGEST, coordinate


def test_the_mutation_matrix_covers_every_declared_field():
    """Structural coverage: no top-level field escapes the matrix.

    A field added later without a mutation case fails here rather than shipping
    silently outside the replay-detection guarantee.
    """

    covered = {key.split("/")[0].split(".")[0] for key in MUTATIONS}
    declared = {f.name for f in dataclasses.fields(CanonicalEvidenceIdentity)}
    assert declared - covered == set()


def test_all_mutated_digests_are_pairwise_distinct():
    digests = {
        name: identity(**kw).canonical_digest() for name, kw in MUTATIONS.items()
    }
    assert len(set(digests.values())) == len(digests)


# --------------------------------------------------------------------------- #
# Replay across each scope axis
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "axis,replayed",
    [
        ("tenant", dict(tenant_id="tenant-2")),
        ("context", dict(assessment_context_ref="ctx-2")),
        ("context-digest", dict(assessment_context_digest=OTHER_DIGEST)),
        ("subject", dict(subject_ref="subject-2")),
        ("system-binding", dict(assessed_system_binding_ref="bind-2")),
        ("system-binding-digest", dict(assessed_system_binding_digest=OTHER_DIGEST)),
        ("purpose", dict(assessment_purpose_ref="purpose-forecast")),
        ("usage-scope", dict(usage_scope_ref="scope-evaluation-only")),
    ],
)
def test_replaying_one_evidence_item_under_another_scope_is_detectable(axis, replayed):
    """A favourable item copied across a scope axis cannot keep its digest."""

    original = identity()
    copied = identity(scope=scope(**replayed))
    assert original.scope.scope_identity != copied.scope.scope_identity, axis
    assert original.canonical_digest() != copied.canonical_digest(), axis


def test_a_content_digest_swap_is_detectable():
    assert (
        identity(content_digest=OTHER_DIGEST).canonical_digest()
        != identity(content_digest=CONTENT_DIGEST).canonical_digest()
    )


def test_coordinate_identity_moves_with_every_replay_axis():
    base = identity().coordinate_identity
    for replayed in (
        dict(tenant_id="tenant-2"),
        dict(subject_ref="subject-2"),
        dict(assessment_purpose_ref="purpose-forecast"),
        dict(usage_scope_ref="scope-evaluation-only"),
        dict(assessed_system_binding_digest=OTHER_DIGEST),
    ):
        assert identity(scope=scope(**replayed)).coordinate_identity != base


def test_two_identities_differing_only_in_the_evidence_id_share_no_digest():
    """Even the weakest coordinate is load-bearing."""

    assert (
        identity(evidence_id="ev-1").canonical_digest()
        != identity(evidence_id="ev-1 ".strip() + "x").canonical_digest()
    )
