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



def test_phase_5a_is_still_at_version_0_1_0():
    """P-1: Phase 5B-0A does not re-version Phase 5A."""

    assert p5a.__version__ == "0.1.0"


def test_phase_5a_still_exports_exactly_thirty_seven_symbols():
    """P-2: the Phase 5A public API is unchanged."""

    assert len(p5a.__all__) == 37


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

    Binding one inside a candidate would require a Phase 5A 0.2.0, which is Phase 5B-0B's
    work. The candidate digest before and after verification is identical because the
    candidate never learns the v2 attestation exists.
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
