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
    claim,
    identity,
    observation,
    provenance,
    receipt,
    scope,
    schema,
)
from ugence_trusted_evidence_authority.api import (
    ApplicabilityCoordinate,
    ApplicabilityDeclaration,
    CanonicalEvidenceIdentity,
    DeclaredVerificationOutcome,
    EvidenceClaimBinding,
    EvidenceLifecycleState,
    EvidenceSchemaRef,
    EvidenceTrustStage,
    EvidenceVerificationReceiptPayload,
    TrustedEvidenceRefusalReason,
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
    "claim.claim_ref": dict(claim=claim(claim_ref="claim-2")),
    "claim.metric_ref": dict(claim=claim(metric_ref="metric-2")),
    "claim.unit": dict(claim=claim(unit="percent")),
    "claim.measurement_semantics_ref": dict(
        claim=claim(measurement_semantics_ref="semantics-2")
    ),
    "claim.applicability": dict(claim=EvidenceClaimBinding.not_applicable()),
    "claim/metric-only": dict(claim=claim(claim_ref="")),
    "claim/claim-only": dict(claim=claim(metric_ref="")),
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


# --------------------------------------------------------------------------- #
# Receipt-payload mutation matrix
# --------------------------------------------------------------------------- #

RECEIPT_BASELINE = receipt()
RECEIPT_BASELINE_DIGEST = RECEIPT_BASELINE.canonical_digest()

_S = EvidenceTrustStage
_R = TrustedEvidenceRefusalReason

#: One mutation per receipt-payload field. Every one must move the digest.
RECEIPT_MUTATIONS = {
    "receipt_id": dict(receipt_id="receipt-2"),
    "schema.schema_id": dict(
        schema=EvidenceSchemaRef(schema_id="ugence.receipt.other", schema_version="1")
    ),
    "schema.schema_version": dict(
        schema=EvidenceSchemaRef(
            schema_id="ugence.receipt.evidence-verification", schema_version="2"
        )
    ),
    "source_evidence_identity_digest": dict(source_evidence_identity_digest=OTHER_DIGEST),
    "evidence_content_digest": dict(evidence_content_digest=OTHER_DIGEST),
    "verification_request_digest": dict(verification_request_digest=OTHER_DIGEST),
    "scope.tenant_id": dict(scope=scope(tenant_id="tenant-2")),
    "scope.subject_ref": dict(scope=scope(subject_ref="subject-2")),
    "scope.assessment_purpose_ref": dict(scope=scope(assessment_purpose_ref="purpose-2")),
    "scope.usage_scope_ref": dict(scope=scope(usage_scope_ref="scope-2")),
    "scope.assessed_system_binding_ref": dict(scope=scope(assessed_system_binding_ref="bind-2")),
    "verified_at": dict(verified_at=RECEIPT_BASELINE.verified_at + timedelta(microseconds=1)),
    "verifier_authority_id": dict(verifier_authority_id="verifier-authority-2"),
    "verifier_key_id": dict(verifier_key_id="key-2"),
    "verification_protocol_id": dict(verification_protocol_id="ugence.tap.other"),
    "verification_protocol_version": dict(verification_protocol_version="2"),
    "declared_outcome": dict(
        declared_outcome=DeclaredVerificationOutcome.DECLARED_REFUSED,
        declared_cleared_stages=(_S.STRUCTURALLY_CONSTRUCTIBLE,),
        declared_refusal_reasons=(_R.TRUSTED_EVIDENCE_TENANT_MISMATCH,),
    ),
    "declared_cleared_stages": dict(
        declared_cleared_stages=(_S.STRUCTURALLY_CONSTRUCTIBLE, _S.CURRENTLY_VALID)
    ),
    "declared_unattempted_stages": dict(
        declared_cleared_stages=(_S.STRUCTURALLY_CONSTRUCTIBLE,),
        declared_unattempted_stages=(_S.PROVENANCE_VERIFIED,),
    ),
    "declared_refusal_reasons": dict(
        declared_outcome=DeclaredVerificationOutcome.DECLARED_REFUSED,
        declared_cleared_stages=(_S.STRUCTURALLY_CONSTRUCTIBLE,),
        declared_refusal_reasons=(_R.TRUSTED_EVIDENCE_STALE,),
    ),
    "evidence_valid_from": dict(
        evidence_valid_from=RECEIPT_BASELINE.evidence_valid_from + timedelta(seconds=1)
    ),
    "evidence_valid_from/absent": dict(evidence_valid_from=None),
    "evidence_valid_to": dict(
        evidence_valid_to=RECEIPT_BASELINE.evidence_valid_to + timedelta(seconds=1)
    ),
    "evidence_valid_to/absent": dict(evidence_valid_to=None),
    "receipt_valid_from": dict(
        receipt_valid_from=RECEIPT_BASELINE.receipt_valid_from + timedelta(seconds=1)
    ),
    "receipt_valid_from/absent": dict(receipt_valid_from=None),
    "receipt_valid_to": dict(
        receipt_valid_to=RECEIPT_BASELINE.receipt_valid_to + timedelta(seconds=1)
    ),
    "receipt_valid_to/absent": dict(receipt_valid_to=None),
}


@pytest.mark.parametrize("coordinate", sorted(RECEIPT_MUTATIONS))
def test_every_receipt_coordinate_changes_the_digest(coordinate):
    mutated = receipt(**RECEIPT_MUTATIONS[coordinate])
    assert mutated != RECEIPT_BASELINE, coordinate
    assert mutated.canonical_bytes() != RECEIPT_BASELINE.canonical_bytes(), coordinate
    assert mutated.canonical_digest() != RECEIPT_BASELINE_DIGEST, coordinate


def test_the_receipt_mutation_matrix_covers_every_declared_field():
    covered = {key.split("/")[0].split(".")[0] for key in RECEIPT_MUTATIONS}
    declared = {
        f.name for f in dataclasses.fields(EvidenceVerificationReceiptPayload)
    }
    assert declared - covered == set()


def test_all_mutated_receipt_digests_are_pairwise_distinct():
    digests = {
        name: receipt(**kw).canonical_digest() for name, kw in RECEIPT_MUTATIONS.items()
    }
    assert len(set(digests.values())) == len(digests)


def test_evidence_and_receipt_validity_move_the_digest_independently():
    """The two intervals are separate coordinates, not one reused pair."""

    evidence_shift = receipt(
        evidence_valid_to=RECEIPT_BASELINE.evidence_valid_to + timedelta(days=1)
    )
    receipt_shift = receipt(
        receipt_valid_to=RECEIPT_BASELINE.receipt_valid_to + timedelta(days=1)
    )
    assert evidence_shift.canonical_digest() != RECEIPT_BASELINE_DIGEST
    assert receipt_shift.canonical_digest() != RECEIPT_BASELINE_DIGEST
    assert evidence_shift.canonical_digest() != receipt_shift.canonical_digest()


def test_reordered_stage_and_reason_input_produces_identical_bytes():
    """Order-irrelevant collections: reordering must NOT move the digest."""

    forward = receipt(
        declared_cleared_stages=(_S.STRUCTURALLY_CONSTRUCTIBLE, _S.CURRENTLY_VALID)
    )
    backward = receipt(
        declared_cleared_stages=(_S.CURRENTLY_VALID, _S.STRUCTURALLY_CONSTRUCTIBLE)
    )
    assert forward.canonical_bytes() == backward.canonical_bytes()

    a = receipt(
        declared_outcome=DeclaredVerificationOutcome.DECLARED_REFUSED,
        declared_cleared_stages=(_S.STRUCTURALLY_CONSTRUCTIBLE,),
        declared_refusal_reasons=(_R.TRUSTED_EVIDENCE_STALE, _R.TRUSTED_EVIDENCE_REVOKED),
    )
    b = receipt(
        declared_outcome=DeclaredVerificationOutcome.DECLARED_REFUSED,
        declared_cleared_stages=(_S.STRUCTURALLY_CONSTRUCTIBLE,),
        declared_refusal_reasons=(_R.TRUSTED_EVIDENCE_REVOKED, _R.TRUSTED_EVIDENCE_STALE),
    )
    assert a.canonical_bytes() == b.canonical_bytes()


def test_custody_order_still_moves_the_digest_where_order_is_meaningful():
    """Contrast with the order-irrelevant collections above."""

    forward = identity(provenance=provenance(custody_refs=("a", "b")))
    backward = identity(provenance=provenance(custody_refs=("b", "a")))
    assert forward.canonical_digest() != backward.canonical_digest()


def test_cross_claim_and_cross_unit_replay_is_detectable():
    base = identity()
    for replayed in (
        claim(claim_ref="claim-other"),
        claim(metric_ref="metric-other"),
        claim(unit="percent"),
        claim(measurement_semantics_ref="semantics-other"),
        EvidenceClaimBinding.not_applicable(),
    ):
        mutated = identity(claim=replayed)
        assert mutated.canonical_digest() != base.canonical_digest()
        assert mutated.coordinate_identity != base.coordinate_identity
