"""The positive control: verification succeeds only under a trusted, correctly scoped key.

Deliberately small. A producer-authenticity boundary earns its keep by refusing, so the
happy-path properties here are the minimum needed to prove the positive control is real —
that the suite is not passing because *everything* is refused. The adversarial properties
live in ``test_adversarial.py`` and outnumber these at least two to one.
"""

from __future__ import annotations

import pytest

from datetime import timezone

from _producer_fixtures import (
    AS_OF,
    ISSUER_ID,
    PRODUCER_ID,
    PRODUCER_KEY_ID,
    CountingSignatureVerifier,
)
from _producer_fixtures import build_verifier

from ugence_cloud_scaling_producer_attestation import (
    PRODUCER_ATTESTATION_CAPABILITY,
    anchor_record_digest,
    PRODUCER_ATTESTATION_V2_SCHEMA_VERSION,
    PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE,
    VERIFICATION_PROFILE,
    VERIFICATION_PROFILE_VERSION,
    ProducerAuthenticityOutcome,
    VerifiedProducerAttestation,
    require_verified_producer_attestation,
)

#: Property category: this module's default is declared in ``tests/conftest.py``
#: (``MODULE_PROPERTY_CATEGORY``), and a test that departs from it carries its own
#: ``@pytest.mark.<category>``, which wins. ``tests/test_property_ledger.py`` counts
#: the resolved categories, so the adversarial-to-happy ratio is machine-checked
#: rather than claimed.


def test_a_trusted_producer_key_verifies_and_yields_the_artifact(
    verifier, candidate, attestation, as_of
):
    """H-1: the positive control. A trusted, in-window, correctly scoped key verifies."""

    result = verifier.verify(candidate=candidate, attestation=attestation, as_of=as_of)

    assert result.refusal is None, result.refusal
    assert result.outcome is ProducerAuthenticityOutcome.VERIFIED
    assert type(result.verified_attestation) is VerifiedProducerAttestation


def test_the_verified_artifact_binds_the_candidate_it_was_verified_against(
    verifier, candidate, attestation, as_of
):
    """H-2: the artifact names this exact candidate, recommendation, tenant and subject."""

    artifact = verifier.verify(
        candidate=candidate, attestation=attestation, as_of=as_of
    ).verified_attestation

    assert artifact.candidate_digest == candidate.candidate_digest
    assert artifact.recommendation_id == candidate.recommendation_id
    assert artifact.recommendation_digest == candidate.recommendation_digest
    assert artifact.tenant_id == candidate.tenant_id
    assert artifact.subject_id == candidate.subject_id
    assert artifact.subject_type == candidate.subject_type


def test_the_verified_artifact_binds_the_key_that_verified_it(
    verifier, candidate, attestation, anchor, as_of
):
    """H-3: the artifact names the resolved anchor, its coordinate and its capability."""

    artifact = verifier.verify(
        candidate=candidate, attestation=attestation, as_of=as_of
    ).verified_attestation

    assert artifact.verified_producer_id == PRODUCER_ID
    assert artifact.verified_issuer == ISSUER_ID
    assert artifact.verified_key_id == PRODUCER_KEY_ID
    assert artifact.trust_anchor_capability == PRODUCER_ATTESTATION_CAPABILITY.value
    assert artifact.trust_anchor_record_digest == anchor_record_digest(anchor)
    assert artifact.attestation_digest == attestation.digest()
    assert artifact.verification_profile == VERIFICATION_PROFILE
    assert artifact.verification_profile_version == VERIFICATION_PROFILE_VERSION


def test_the_verified_artifact_carries_the_injected_instant_and_no_clock_reading(
    verifier, candidate, attestation, as_of
):
    """H-4: ``verified_as_of_fact`` is exactly the injected instant, normalized to UTC."""

    artifact = verifier.verify(
        candidate=candidate, attestation=attestation, as_of=as_of
    ).verified_attestation

    assert artifact.verified_as_of_fact == AS_OF.astimezone(timezone.utc)
    assert artifact.attestation_issued_at_fact == attestation.issued_at
    assert artifact.anchor_effective_from_fact is not None
    assert artifact.anchor_effective_to_fact is not None


def test_the_verified_artifact_revalidates_at_a_consumption_boundary(
    verifier, candidate, attestation, as_of
):
    """H-5: a genuine artifact survives revalidation, and reports granting nothing."""

    artifact = verifier.verify(
        candidate=candidate, attestation=attestation, as_of=as_of
    ).verified_attestation

    assert require_verified_producer_attestation(artifact) is artifact
    assert artifact.grants_authority is False
    assert artifact.outcome is ProducerAuthenticityOutcome.VERIFIED
    assert artifact.artifact_digest == artifact.digest()


def test_minting_produces_a_v2_attestation_at_the_new_schema_tag(candidate, attestation):
    """H-6: the minted attestation is the new contract, not Phase 5A's frozen v1."""

    assert attestation.schema_version == PRODUCER_ATTESTATION_V2_SCHEMA_VERSION
    assert attestation.signing_purpose == PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE
    assert attestation.tenant_id == candidate.tenant_id
    assert attestation.subject_id == candidate.subject_id
    assert attestation.recommendation_digest == candidate.recommendation_digest


def test_the_signature_is_checked_exactly_once_on_the_recomputed_bytes(
    candidate, attestation, directory, as_of
):
    """H-7: the signature check runs, on the bytes the verifier recomputed, once."""

    counting = CountingSignatureVerifier()
    verifier = build_verifier(directory=directory, signature_verifier=counting)

    result = verifier.verify(candidate=candidate, attestation=attestation, as_of=as_of)

    assert result.refusal is None
    assert counting.calls == 1


def test_verification_is_deterministic_for_identical_inputs(
    verifier, candidate, attestation, as_of
):

#: Every test in this module is a **happy** property unless it carries an
#: explicit override below. ``tests/test_property_ledger.py`` counts these markers and
#: asserts the ratio the ratified design requires, so the ratio is machine-checked
#: rather than claimed.

    """H-8: identical inputs yield an identical artifact digest, every time."""

    first = verifier.verify(candidate=candidate, attestation=attestation, as_of=as_of)
    second = verifier.verify(candidate=candidate, attestation=attestation, as_of=as_of)

    assert (
        first.verified_attestation.artifact_digest
        == second.verified_attestation.artifact_digest
    )
