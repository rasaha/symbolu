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
    coordinate_for,
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
#: **Moved by R-12b.** ``RiskDecision`` gained ``evaluated_at``, so the digest-bound decision
#: snapshot gained a key — the first time in this ADR's history that a Phase 5A change moved a
#: digest *upstream* of the candidate. The superseded value is pinned below.
FROZEN_DECISION_DIGEST = (
    "sha256:6aba137d8d2c057d768b1243469636e4c1137037883adfb9a078c9a3fbbf0ca2"
)
#: Superseded by R-12b. The pre-R-12b snapshot carried ``issued_at`` and ``expires_at`` but no
#: ``evaluated_at`` at all, so the evaluator's stamp lived only on ``SubjectRiskDecision``'s
#: outer field, which no digest covered — and a public ``dataclasses.replace`` moved it ten
#: years with this digest unchanged. Pinned as a negative anchor so dropping the field back out
#: is a failure rather than a re-baseline.
SUPERSEDED_PRE_R12B_DECISION_DIGEST = (
    "sha256:d08f94ba8ba174e3929da24efc151fa2cebb9743329a3a61c71f65e46aa23101"
)
FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST = (
    "sha256:1035d2fc2ab8f4b443f815562f9f6ad8e4ce0032633f03a12e04e691c24cf2d0"
)
#: **Moved by ETS-15** (schema 2). ``cloud_provider`` became a required scope field and
#: ``resource_group`` an Azure-conditional one; canonicalization retains nulls, so the
#: scope's canonical form changed even for a target that sets neither. This is the head of
#: the cascade — every digest below that covers a scope moved because this one did.
FROZEN_TARGET_SCOPE_DIGEST = (
    "sha256:1e9ebadf0075b593b0c44cf3b1f5bcc3ae8d7642329d84958b1058254d15e6e6"
)
#: Superseded by ETS-15. Pinned as a negative anchor for the same reason as every other
#: superseded value here: a payload reproducing it is a schema-1 scope, and schema 1 is
#: refused by ruling (ETS-9), never upgraded.
SUPERSEDED_PRE_ETS15_TARGET_SCOPE_DIGEST = (
    "sha256:b97f41c98353aaafdb9aef4fa12309b459900ce002affc206b5c3239b82c3baa"
)
#: **Moved by ETS-15**, and not because the binding's own field set changed — it did not.
#: The binding covers ``target_scope_digest``, which moved above it.
FROZEN_POLICY_BINDING_DIGEST = (
    "sha256:29ca00f9ad28fbc27d56a96351ff2cd49378da81fce3118bb18104dbd7ff8ca0"
)
SUPERSEDED_PRE_ETS15_POLICY_BINDING_DIGEST = (
    "sha256:8961f6b2b78e811d556b7e43af99807eb368e65ca3b0fa7c6109aa952b5b9808"
)
#: The complete Policy Authority coordinate the candidate now carries (5B-1). Pinned as its
#: own anchor: it is a new artifact in the chain, exactly as the policy binding above is.
#: **Moved by ETS-15**, for the same reason as the binding above: it carries the scope
#: digest too. Worth stating because the ETS audit's cascade did not list it — the audit
#: traced scope -> binding -> candidate and missed that the V2 coordinate binds the scope
#: independently. Measured, not predicted.
FROZEN_POLICY_COORDINATE_BINDING_DIGEST = (
    "sha256:4a83019d4fffd15ad55e470a83a8d86f3b7beed251c8e54f5a954531979adc2c"
)
SUPERSEDED_PRE_ETS15_POLICY_COORDINATE_BINDING_DIGEST = (
    "sha256:ad1d1ad9d3fa574a071e98a8638c283e19d21d744c91b6848baaa0eca6670ed8"
)
#: **Moved by 5B-1.** The candidate gained the required ``policy_coordinate_binding`` field,
#: and every field of a candidate enters its digest payload — so this is the one Phase 5A
#: constant an in-candidate policy coordinate can move, and the floor for any option that
#: binds the coordinate inside the candidate at all (D-5B1-1). The superseded value is pinned
#: below.
#: **Moved again by R-12b**, this time not because the candidate's own payload changed — its
#: field set is untouched — but because ``decision_snapshot_digest`` and ``decision_digest``,
#: which the payload has always covered, moved beneath it. The superseded value is pinned below.
#: **Moved again by ETS-15**, this time because three artifacts it covers moved beneath it.
FROZEN_CANDIDATE_DIGEST = (
    "sha256:bbcd4ad7387d0ac8ead8d3253942123f6191cc65218bc329b67e53d9b8a2250f"
)
#: Superseded by ETS-15 — the R-12b value, correct until schema 2.
SUPERSEDED_PRE_ETS15_CANDIDATE_DIGEST = (
    "sha256:357bb3d4d660034c9abe50000986808a1e9c15fce05b4a22b6cb82836cc50e79"
)
#: Superseded by R-12b — the 5B-1 value, correct until the decision snapshot gained
#: ``evaluated_at``. Pinned for the same reason as the two below it.
SUPERSEDED_PRE_R12B_CANDIDATE_DIGEST = (
    "sha256:be06c65385d73f66c52dd51024c30ed7939a836369db654f381d52270f2aa906"
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

#: Superseded by 5B-1. The pre-repair candidate carried a policy *binding* that could not
#: name a coordinate, so a verified policy proof could not be reconciled against it: one
#: genuine proof verified alongside any candidate whatsoever. Pinned as a negative anchor so
#: dropping the coordinate back out of the payload is a failure rather than a re-baseline.
#:
#: Two other packages pin this same value for the same fixture chain, and both moved with it:
#: ``cloud-scaling-producer-attestation`` (tests/test_frozen_digests.py,
#: tests/test_phase5a_invariants.py) and, transitively, its own
#: ``FROZEN_VERIFIED_ARTIFACT_DIGEST``, which binds the candidate digest.
SUPERSEDED_PRE_5B1_CANDIDATE_DIGEST = (
    "sha256:db72ffffc5bf4ecfe8a5f9fe187efb5e8439355e559fcc34b391cc4c9282a313"
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
        policy_binding=binding,
        policy_coordinate_binding=coordinate_for(binding),
        target_scope=scope,
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


def test_the_policy_coordinate_binding_digest_is_frozen(frozen_chain):
    """5B-1's new artifact, pinned like every other stage of the chain."""

    candidate = frozen_chain[-1]
    coordinate = candidate.policy_coordinate_binding
    assert coordinate.digest() == FROZEN_POLICY_COORDINATE_BINDING_DIGEST
    assert (
        candidate.policy_coordinate_binding_digest
        == FROZEN_POLICY_COORDINATE_BINDING_DIGEST
    )


def test_only_the_candidate_digest_moved_in_the_5b1_repair(frozen_chain):
    """The measurement D-5B1-1 rests on, re-asserted from the built chain.

    Widening the existing binding in place would have moved ``FROZEN_POLICY_BINDING_DIGEST``
    as well. Carrying the coordinate as its own field moves exactly one of the ten, which is
    the floor: no in-candidate binding can move none.

    Still true *of 5B-1*. R-12b later moved ``FROZEN_DECISION_DIGEST`` as well, for an unrelated
    reason — the decision snapshot gained a field — which is why the constants below are the
    current values rather than 5B-1's.
    """

    projection, decision, attestation, scope, binding, candidate = frozen_chain
    assert decision.decision_digest != SUPERSEDED_PRE_R12B_DECISION_DIGEST
    assert projection.recommendation_digest == FROZEN_RECOMMENDATION_DIGEST
    assert projection.context_digest == FROZEN_CONTEXT_DIGEST
    assert projection.subject_digest == FROZEN_SUBJECT_DIGEST
    assert projection.request_digest == FROZEN_REQUEST_DIGEST
    assert projection.idempotency_key == FROZEN_IDEMPOTENCY_KEY
    assert decision.decision_digest == FROZEN_DECISION_DIGEST
    assert attestation.signing_payload_digest == FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST
    assert scope.digest() == FROZEN_TARGET_SCOPE_DIGEST
    assert binding.digest() == FROZEN_POLICY_BINDING_DIGEST
    assert candidate.candidate_digest != SUPERSEDED_PRE_5B1_CANDIDATE_DIGEST


def test_candidate_digest_is_frozen(frozen_chain):
    *_, candidate = frozen_chain
    assert candidate.candidate_digest == FROZEN_CANDIDATE_DIGEST
    assert candidate.digest() == FROZEN_CANDIDATE_DIGEST


def test_every_frozen_digest_is_distinct_and_canonical():
    frozen = [
        FROZEN_RECOMMENDATION_DIGEST, FROZEN_CONTEXT_DIGEST, FROZEN_SUBJECT_DIGEST,
        FROZEN_REQUEST_DIGEST, FROZEN_IDEMPOTENCY_KEY, FROZEN_DECISION_DIGEST,
        FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST, FROZEN_TARGET_SCOPE_DIGEST,
        FROZEN_POLICY_BINDING_DIGEST, FROZEN_POLICY_COORDINATE_BINDING_DIGEST,
        FROZEN_CANDIDATE_DIGEST,
    ]
    assert len(set(frozen)) == len(frozen), "two stages produced the same digest"
    assert all(is_canonical_digest(d) for d in frozen)


def test_the_ra_illustrative_fixture_is_not_a_phase5a_digest():
    """The RA fixture is a different artifact under an older illustrative subject type."""

    frozen = {
        FROZEN_RECOMMENDATION_DIGEST, FROZEN_CONTEXT_DIGEST, FROZEN_SUBJECT_DIGEST,
        FROZEN_REQUEST_DIGEST, FROZEN_IDEMPOTENCY_KEY, FROZEN_DECISION_DIGEST,
        FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST, FROZEN_TARGET_SCOPE_DIGEST,
        FROZEN_POLICY_BINDING_DIGEST, FROZEN_POLICY_COORDINATE_BINDING_DIGEST,
        FROZEN_CANDIDATE_DIGEST,
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
    assert candidate.candidate_digest != SUPERSEDED_PRE_5B1_CANDIDATE_DIGEST
    assert candidate.candidate_digest != SUPERSEDED_PRE_R12B_CANDIDATE_DIGEST
    assert candidate.candidate_digest == FROZEN_CANDIDATE_DIGEST


def test_only_the_candidate_digest_moved_in_the_f2_remediation(frozen_chain):
    """Every upstream Phase 4 / Phase 5 binding digest is unchanged by F-2.

    F-2 changed only what the *candidate* payload covers. A moved upstream digest would
    mean the remediation had reached into a frozen contract it must not touch.

    Still true *of F-2*. ETS-15 later moved the scope, binding and coordinate digests for
    an unrelated reason — schema 2 added two scope fields — which is why the constants
    compared here are the current values rather than F-2's. The Phase 4 digests above
    (recommendation, context, subject, request, idempotency, decision) are untouched by
    ETS-15 by ruling (ETS-8), and asserting them here is what proves it.
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
