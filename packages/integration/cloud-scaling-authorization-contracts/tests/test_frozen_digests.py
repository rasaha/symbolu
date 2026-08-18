"""The frozen, production-shaped end-to-end fixture.

One chain, pinned at every stage: a canonical Cloud Scaling recommendation through the real
Phase-3 pipeline, the real Phase 4C projection, a real Risk Authority decision, a real
Ed25519 producer attestation, a policy/target binding, and the resulting candidate.

Every constant below was computed independently from the built chain and then pinned. They
are regression anchors: if any canonicalization, field set or binding rule moves, these
fail rather than silently re-baselining.

**These are not the RA illustrative fixture.** The Risk Authority conformance vector
``sha256:eb4526a6679470e603bbc757cde7cfac9c7b2258256eaecef729e356a1df6c38`` is an RA
*canonicalization* fixture that uses the older illustrative subject-type value. It is not
the production Phase 4C adapter-output fixture, it is not replaced or reinterpreted here,
and no digest below is expected to equal it.
"""

from __future__ import annotations

import pytest

from conftest import (
    build_attestation,
    build_decision,
    build_policy_binding,
    build_projection,
    build_target_scope,
)
from ugence_cloud_scaling_authorization_contracts import (
    build_capacity_authorization_candidate,
    is_canonical_digest,
)

# --- the pinned production-shaped chain ----------------------------------------------
FROZEN_RECOMMENDATION_DIGEST = (
    "sha256:1b69d6a4c45b06d96587443be3ca0eca3910f9d107d53aca0fe97b65c70b1b78"
)
FROZEN_CONTEXT_DIGEST = (
    "sha256:d0bd58ff75993e4451575315f99678e0ac22b84f36bf7223cd9928cf9aee5f6f"
)
FROZEN_SUBJECT_DIGEST = (
    "sha256:13a27fea8c625e3d8d9d1c163e645ce690441dcc4c677d23600ace148dc3ad25"
)
FROZEN_REQUEST_DIGEST = (
    "sha256:06fb8dc06e693f843826a634685cbd6fc7b645cfc684d27d5fa4160a2311b568"
)
FROZEN_IDEMPOTENCY_KEY = (
    "sha256:031179d6a8b9b1d77ec851e73b7a01f281ff88cf231677628c8012a170b4f41b"
)
FROZEN_DECISION_DIGEST = (
    "sha256:d08f94ba8ba174e3929da24efc151fa2cebb9743329a3a61c71f65e46aa23101"
)
FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST = (
    "sha256:1035d2fc2ab8f4b443f815562f9f6ad8e4ce0032633f03a12e04e691c24cf2d0"
)
FROZEN_TARGET_SCOPE_DIGEST = (
    "sha256:b97f41c98353aaafdb9aef4fa12309b459900ce002affc206b5c3239b82c3baa"
)
FROZEN_POLICY_BINDING_DIGEST = (
    "sha256:8961f6b2b78e811d556b7e43af99807eb368e65ca3b0fa7c6109aa952b5b9808"
)
FROZEN_CANDIDATE_DIGEST = (
    "sha256:db72ffffc5bf4ecfe8a5f9fe187efb5e8439355e559fcc34b391cc4c9282a313"
)
#: Superseded by the F-2 audit remediation. The pre-remediation candidate digest bound
#: ``policy_binding``/``producer_attestation`` only through derived scalars while still
#: *carrying* the objects, so a rogue policy issuer or forged producer signature could ride
#: along under an unchanged, self-validating digest. The payload now binds both artifacts'
#: complete canonical forms — two added keys, nothing removed — so the digest moved. Pinned
#: here so a silent revert to the weaker payload is caught rather than re-baselined.
SUPERSEDED_PRE_F2_CANDIDATE_DIGEST = (
    "sha256:61718405a6affa83e96184a6c7259666fb266766db0fb09bc7502141625d2ed5"
)

#: The RA illustrative canonicalization fixture. Documented here so it is never mistaken
#: for a Phase 4C or Phase 5A production digest, and asserted to be distinct from all of
#: them.
RA_ILLUSTRATIVE_FIXTURE = (
    "sha256:eb4526a6679470e603bbc757cde7cfac9c7b2258256eaecef729e356a1df6c38"
)


@pytest.fixture(scope="module")
def frozen_chain():
    projection = build_projection()
    decision = build_decision(projection)
    attestation = build_attestation(recommendation_digest=projection.recommendation_digest)
    scope = build_target_scope(projection)
    binding = build_policy_binding(scope)
    candidate = build_capacity_authorization_candidate(
        projection=projection, decision=decision, producer_attestation=attestation,
        policy_binding=binding, target_scope=scope,
    )
    return projection, decision, attestation, scope, binding, candidate


def test_phase4_digests_are_frozen(frozen_chain):
    projection, _, _, _, _, _ = frozen_chain
    assert projection.recommendation_digest == FROZEN_RECOMMENDATION_DIGEST
    assert projection.context_digest == FROZEN_CONTEXT_DIGEST
    assert projection.subject_digest == FROZEN_SUBJECT_DIGEST
    assert projection.request_digest == FROZEN_REQUEST_DIGEST
    assert projection.idempotency_key == FROZEN_IDEMPOTENCY_KEY


def test_decision_digest_is_frozen(frozen_chain):
    _, decision, _, _, _, _ = frozen_chain
    assert decision.decision_digest == FROZEN_DECISION_DIGEST


def test_phase5_binding_digests_are_frozen(frozen_chain):
    _, _, attestation, scope, binding, _ = frozen_chain
    assert attestation.signing_payload_digest == FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST
    assert scope.digest() == FROZEN_TARGET_SCOPE_DIGEST
    assert binding.digest() == FROZEN_POLICY_BINDING_DIGEST


def test_candidate_digest_is_frozen(frozen_chain):
    *_, candidate = frozen_chain
    assert candidate.candidate_digest == FROZEN_CANDIDATE_DIGEST
    assert candidate.digest() == FROZEN_CANDIDATE_DIGEST


def test_every_frozen_digest_is_distinct_and_canonical():
    frozen = [
        FROZEN_RECOMMENDATION_DIGEST, FROZEN_CONTEXT_DIGEST, FROZEN_SUBJECT_DIGEST,
        FROZEN_REQUEST_DIGEST, FROZEN_IDEMPOTENCY_KEY, FROZEN_DECISION_DIGEST,
        FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST, FROZEN_TARGET_SCOPE_DIGEST,
        FROZEN_POLICY_BINDING_DIGEST, FROZEN_CANDIDATE_DIGEST,
    ]
    assert len(set(frozen)) == len(frozen), "two stages produced the same digest"
    assert all(is_canonical_digest(d) for d in frozen)


def test_the_ra_illustrative_fixture_is_not_a_phase5a_digest():
    """The RA fixture is a different artifact under an older illustrative subject type."""

    frozen = {
        FROZEN_RECOMMENDATION_DIGEST, FROZEN_CONTEXT_DIGEST, FROZEN_SUBJECT_DIGEST,
        FROZEN_REQUEST_DIGEST, FROZEN_IDEMPOTENCY_KEY, FROZEN_DECISION_DIGEST,
        FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST, FROZEN_TARGET_SCOPE_DIGEST,
        FROZEN_POLICY_BINDING_DIGEST, FROZEN_CANDIDATE_DIGEST,
    }
    assert RA_ILLUSTRATIVE_FIXTURE not in frozen



def test_the_pre_f2_candidate_digest_is_not_reachable(frozen_chain):
    """The weaker pre-remediation payload must never be produced again.

    If a future edit dropped ``policy_binding`` or ``producer_attestation`` back out of the
    canonical payload, the candidate digest would return to the superseded value. Pinning
    it as a *negative* anchor makes that revert a test failure rather than a re-baseline.
    """

    *_, candidate = frozen_chain
    assert candidate.candidate_digest != SUPERSEDED_PRE_F2_CANDIDATE_DIGEST
    assert candidate.candidate_digest == FROZEN_CANDIDATE_DIGEST


def test_only_the_candidate_digest_moved_in_the_f2_remediation(frozen_chain):
    """Every upstream Phase 4 / Phase 5 binding digest is unchanged by F-2.

    F-2 changed only what the *candidate* payload covers. A moved upstream digest would
    mean the remediation had reached into a frozen contract it must not touch.
    """

    projection, decision, attestation, scope, binding, _ = frozen_chain
    assert projection.recommendation_digest == FROZEN_RECOMMENDATION_DIGEST
    assert projection.context_digest == FROZEN_CONTEXT_DIGEST
    assert projection.subject_digest == FROZEN_SUBJECT_DIGEST
    assert projection.request_digest == FROZEN_REQUEST_DIGEST
    assert projection.idempotency_key == FROZEN_IDEMPOTENCY_KEY
    assert decision.decision_digest == FROZEN_DECISION_DIGEST
    assert attestation.signing_payload_digest == FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST
    assert scope.digest() == FROZEN_TARGET_SCOPE_DIGEST
    assert binding.digest() == FROZEN_POLICY_BINDING_DIGEST
