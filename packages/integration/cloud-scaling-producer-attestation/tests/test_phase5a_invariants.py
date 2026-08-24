"""Phase 5A is untouched, and its frozen digests still hold.

Phase 5B-0A adds an independent producer-authenticity proof. It does **not** widen,
reinterpret or re-version the Phase 5A contract, and it does not treat Phase 5A's carried
v1 attestation as verified. These properties assert that from this side of the boundary, so
a future edit that quietly reinterpreted v1 would fail here as well as in Phase 5A's suite.
"""

from __future__ import annotations

import pathlib

import pytest

from _producer_fixtures import repo_root as _repo_root

import phase5a_fixtures as P5A
from _producer_fixtures import AS_OF, build_attestation, build_verifier

import ugence_cloud_scaling_authorization_contracts as p5a
import ugence_cloud_scaling_producer_attestation as pkg
from ugence_cloud_scaling_producer_attestation import (
    PHASE_5A_V1_SCHEMA_VERSION,
    PRODUCER_ATTESTATION_V2_SCHEMA_VERSION,
    PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE,
    ProducerAuthenticityOutcome,
    canonical_digest,
)

#: Property category: this module's default is declared in ``tests/conftest.py``
#: (``MODULE_PROPERTY_CATEGORY``), and a test that departs from it carries its own
#: ``@pytest.mark.<category>``, which wins. ``tests/test_property_ledger.py`` counts
#: the resolved categories, so the adversarial-to-happy ratio is machine-checked
#: rather than claimed.

O = ProducerAuthenticityOutcome

REPO = _repo_root()
PHASE_5A_DIR = (
    REPO / "packages" / "integration" / "cloud-scaling-authorization-contracts"
)

#: The frozen Phase 5A v1 producer signing-payload digest, named in the ratified brief.
FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST = (
    "sha256:1035d2fc2ab8f4b443f815562f9f6ad8e4ce0032633f03a12e04e691c24cf2d0"
)

#: Phase 5A's negative anchor — a digest that must remain unreachable.
PHASE_5A_NEGATIVE_ANCHOR = (
    "sha256:61718405a6affa83e96184a6c7259666fb266766db0fb09bc7502141625d2ed5"
)



def test_phase_5a_is_at_the_version_this_package_was_pinned_against():
    """P-1: Phase 5B-0A does not re-version Phase 5A — and pins what it reads.

    ``0.5.0`` since R-12b, which re-sourced the decision instants from the digest-bound
    decision snapshot and moved two Phase 5A frozen digests with it; ``0.4.0`` was R-12;
    ``0.2.0`` was 5B-1, which added the required policy coordinate to the candidate. This
    package's source is unchanged by that and its own version does not move; what moves is
    the fixture chain it verifies against. The assertion stays exact rather than becoming a
    range: a version that drifted without this suite being re-measured is the thing worth
    catching.
    """

    assert p5a.__version__ == "0.7.0"


def test_phase_5a_exports_exactly_the_symbols_this_package_was_measured_against():
    """P-2: the Phase 5A public API is pinned; 5B-1 added four symbols and 5B-2 a fifth.

    5B-1: ``PolicyTargetBindingReferenceV2``, ``POLICY_TARGET_BINDING_V2_SCHEMA_VERSION``,
    ``POLICY_COORDINATE_COMPONENTS`` and ``is_policy_authority_digest``. 5B-2 part 1 adds
    ``POLICY_SCOPE_TENANT`` (R-9), and R-12 adds ``TemporalOrderingError`` — the refusal for
    carried instants that are individually valid and collectively impossible.
    """

    assert len(p5a.__all__) == 43
    assert "POLICY_SCOPE_TENANT" in p5a.__all__
    assert "TemporalOrderingError" in p5a.__all__


def test_the_phase_5a_v1_signing_payload_digest_is_unchanged():
    """P-3: the frozen v1 payload digest still reproduces from the genuine fixture."""

    projection = P5A.build_projection()
    attestation = P5A.build_attestation(
        recommendation_digest=projection.recommendation_digest
    )
    assert attestation.signing_payload_digest == FROZEN_PRODUCER_SIGNING_PAYLOAD_DIGEST


def test_the_phase_5a_negative_anchor_is_still_unreachable():
    """P-4: the digest Phase 5A froze as unreachable is still not produced by the chain."""

    candidate = P5A.build_candidate()
    produced = {
        candidate.candidate_digest,
        candidate.recommendation_digest,
        candidate.context_digest,
        candidate.subject_digest,
        candidate.request_digest,
        candidate.decision_digest,
        candidate.producer_signing_payload_digest,
        candidate.target_scope_digest,
        candidate.policy_binding_digest,
    }
    assert PHASE_5A_NEGATIVE_ANCHOR not in produced


def test_the_phase_5a_candidate_digest_is_unaffected_by_a_v2_attestation(candidate):
    """P-5: a v2 proof travels ALONGSIDE the candidate; it is not bound inside it.

    Still true after 5B-1. What that phase bound inside the candidate is the *policy*
    coordinate, not this producer attestation: the candidate digest before and after a
    successful v2 verification is identical, because the candidate never learns the v2
    attestation exists. Binding the attestation inside the candidate remains unratified work.
    """

    before = candidate.candidate_digest
    verifier = build_verifier()
    result = verifier.verify(
        candidate=candidate, attestation=build_attestation(candidate), as_of=AS_OF
    )
    assert result.verified_attestation is not None
    assert candidate.candidate_digest == before
    assert candidate.digest() == before


def test_the_phase_5a_trust_state_is_not_reinterpreted(candidate):
    """P-6: v1 remains ``PRESENT_BUT_NOT_TRUST_VERIFIED`` after a successful v2 proof."""

    verifier = build_verifier()
    verifier.verify(
        candidate=candidate, attestation=build_attestation(candidate), as_of=AS_OF
    )
    assert (
        candidate.producer_attestation.trust_state
        is p5a.EvidenceTrustState.PRESENT_BUT_NOT_TRUST_VERIFIED
    )
    assert len(list(p5a.EvidenceTrustState)) == 1


def test_the_phase_5a_candidate_still_grants_nothing_after_verification(candidate):
    """P-7: producer authenticity does not upgrade a candidate into an authorization."""

    verifier = build_verifier()
    result = verifier.verify(
        candidate=candidate, attestation=build_attestation(candidate), as_of=AS_OF
    )
    assert candidate.grants_authority is False
    assert result.verified_attestation.grants_authority is False


def test_the_v2_schema_tag_and_purpose_are_distinct_from_v1():
    """P-8: the domain separation the two contracts depend on."""

    assert PRODUCER_ATTESTATION_V2_SCHEMA_VERSION != PHASE_5A_V1_SCHEMA_VERSION
    assert PHASE_5A_V1_SCHEMA_VERSION == p5a.PRODUCER_ATTESTATION_SCHEMA_VERSION
    assert PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE != p5a.PRODUCER_SIGNING_PURPOSE
    assert PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE != p5a.PURPOSE_CAPACITY_ACTION


def test_a_v1_signature_can_never_verify_as_a_v2_signature(candidate):
    """P-9: the payloads differ in the schema field before they differ anywhere else."""

    v1 = candidate.producer_attestation
    v2 = build_attestation(candidate)
    assert v1.signing_payload() != v2.signing_payload()
    assert v1.signing_payload()["schema_version"] != v2.signing_payload()["schema_version"]
    assert canonical_digest(v1.signing_payload()) != canonical_digest(v2.signing_payload())


def test_the_v1_attestation_object_is_not_admitted_by_the_v2_verifier(candidate):
    """P-10: v1 is refused by exact type, not adapted, coerced or partially honoured."""

    result = build_verifier().verify(
        candidate=candidate, attestation=candidate.producer_attestation, as_of=AS_OF
    )
    assert result.verified_attestation is None
    assert result.refusal.outcome is O.UNSUPPORTED_EXACT_TYPE


def test_no_phase_5a_source_file_was_modified():
    """P-11: this package's tree adds files; it edits none of Phase 5A's."""

    import subprocess

    changed = subprocess.run(
        ["git", "status", "--porcelain", "--", str(PHASE_5A_DIR)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert changed == "", f"Phase 5A tree was modified:\n{changed}"


def test_the_controller_package_was_not_modified():
    """P-12: the Cloud Scaling Controller stays a key-free advisory leaf, byte for byte."""

    import subprocess

    controller = REPO / "packages" / "capabilities" / "cloud-scaling-controller"
    changed = subprocess.run(
        ["git", "status", "--porcelain", "--", str(controller)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert changed == "", f"the controller tree was modified:\n{changed}"


# --------------------------------------------------------------------------------------- #
# All ten Phase 5A frozen digests, re-verified from this side of the boundary
# --------------------------------------------------------------------------------------- #

#: The complete Phase 5A frozen set, re-asserted here rather than only inside Phase 5A's own
#: suite. The point of duplicating them is exactly that they are duplicated: if Phase 5B-0A
#: ever perturbed the chain Phase 5A pins — a shared canonicalization moving, a fixture
#: drifting — this PR's own suite would fail, instead of the failure surfacing only in a
#: neighbouring package's run.
PHASE_5A_FROZEN_DIGESTS = {
    "recommendation_digest": (
        "sha256:1b69d6a4c45b06d96587443be3ca0eca3910f9d107d53aca0fe97b65c70b1b78"
    ),
    "context_digest": (
        "sha256:d0bd58ff75993e4451575315f99678e0ac22b84f36bf7223cd9928cf9aee5f6f"
    ),
    "subject_digest": (
        "sha256:13a27fea8c625e3d8d9d1c163e645ce690441dcc4c677d23600ace148dc3ad25"
    ),
    "request_digest": (
        "sha256:06fb8dc06e693f843826a634685cbd6fc7b645cfc684d27d5fa4160a2311b568"
    ),
    "idempotency_key": (
        "sha256:031179d6a8b9b1d77ec851e73b7a01f281ff88cf231677628c8012a170b4f41b"
    ),
    # Moved by R-12b: the decision snapshot gained ``evaluated_at``.
    "decision_digest": (
        "sha256:6aba137d8d2c057d768b1243469636e4c1137037883adfb9a078c9a3fbbf0ca2"
    ),
    "producer_signing_payload_digest": (
        "sha256:1035d2fc2ab8f4b443f815562f9f6ad8e4ce0032633f03a12e04e691c24cf2d0"
    ),
    "target_scope_digest": (
        "sha256:b97f41c98353aaafdb9aef4fa12309b459900ce002affc206b5c3239b82c3baa"
    ),
    "policy_binding_digest": (
        "sha256:8961f6b2b78e811d556b7e43af99807eb368e65ca3b0fa7c6109aa952b5b9808"
    ),
    "policy_coordinate_binding_digest": (
        "sha256:ad1d1ad9d3fa574a071e98a8638c283e19d21d744c91b6848baaa0eca6670ed8"
    ),
    # Moved with it: the candidate payload has always covered ``decision_digest`` and
    # ``decision_snapshot_digest``, so the candidate digest moved beneath an unchanged
    # field set.
    "candidate_digest": (
        "sha256:357bb3d4d660034c9abe50000986808a1e9c15fce05b4a22b6cb82836cc50e79"
    ),
}


def test_all_eleven_phase_5a_frozen_digests_still_reproduce():
    """P-13: the complete frozen set, from the genuine chain, unchanged by this package.

    Eleven since 5B-1: the candidate carries the policy coordinate binding, and its digest is
    pinned like every other stage of the chain.
    """

    candidate = P5A.build_candidate()
    produced = {
        name: getattr(candidate, name) for name in PHASE_5A_FROZEN_DIGESTS
    }
    assert produced == PHASE_5A_FROZEN_DIGESTS
    assert len(PHASE_5A_FROZEN_DIGESTS) == 11


def test_the_frozen_digests_are_independently_recomputable():
    """P-14: recomputed from raw canonical bytes via ``hashlib``, not read back.

    ``hashlib`` is banned inside both distributions precisely so each has one digest path.
    Using it here is what makes this an independent check rather than a tautology.
    """

    import hashlib

    from ugence_cloud_scaling_producer_attestation import canonical_bytes

    candidate = P5A.build_candidate()
    for name, artifact in (
        ("target_scope_digest", candidate.target_scope),
        ("policy_binding_digest", candidate.policy_binding),
        ("policy_coordinate_binding_digest", candidate.policy_coordinate_binding),
    ):
        recomputed = "sha256:" + hashlib.sha256(
            canonical_bytes(artifact.to_canonical_dict())
        ).hexdigest()
        assert recomputed == PHASE_5A_FROZEN_DIGESTS[name], name

    recomputed_payload = "sha256:" + hashlib.sha256(
        canonical_bytes(candidate.producer_attestation.signing_payload())
    ).hexdigest()
    assert recomputed_payload == (
        PHASE_5A_FROZEN_DIGESTS["producer_signing_payload_digest"]
    )
    recomputed_candidate = "sha256:" + hashlib.sha256(
        canonical_bytes(candidate.digest_payload())
    ).hexdigest()
    assert recomputed_candidate == PHASE_5A_FROZEN_DIGESTS["candidate_digest"]


def test_a_successful_v2_verification_moves_no_phase_5a_frozen_digest():
    """P-15: the whole point, as one assertion. Verifying changes nothing upstream."""

    candidate = P5A.build_candidate()
    before = {name: getattr(candidate, name) for name in PHASE_5A_FROZEN_DIGESTS}

    result = build_verifier().verify(
        candidate=candidate, attestation=build_attestation(candidate), as_of=AS_OF
    )
    assert result.verified_attestation is not None

    after = {name: getattr(candidate, name) for name in PHASE_5A_FROZEN_DIGESTS}
    assert after == before == PHASE_5A_FROZEN_DIGESTS
