"""The positive controls every refusal test below is measured against."""

from __future__ import annotations

import pytest

import ugence_reasoning_method_result_attestation as ra
from _fixtures import (
    AS_OF,
    ENGINE,
    ENGINE_ID,
    ENGINE_KEY,
    anchor_of,
    engine_signer,
    result,
    signed,
    verifier,
    verify,
)

OUT = ra.ComparisonResultVerificationOutcome


def test_happy_a_genuine_signed_result_verifies_under_the_engine_role_and_binds_every_fact():
    signer = engine_signer()
    anchor = anchor_of(signer)
    sr = signed(signer)
    r = verify(verifier(anchor), sr)
    assert r.outcome is OUT.VERIFIED
    assert r.refusal_reason is None
    assert r.signer_role is ENGINE
    assert r.signer_identity == ENGINE_ID
    assert r.signer_key_id == ENGINE_KEY
    assert r.engine_identity == ENGINE_ID
    assert r.result_digest == result().result_digest == sr.result_digest
    assert r.signing_payload_digest == sr.signing_payload_digest
    assert r.anchor_record_digest == ra.anchor_record_digest(anchor)
    assert r.anchor_coordinate_digest == ra.anchor_coordinate_digest(
        ra.comparison_result_signer_coordinate(role=ENGINE, signer_identity=ENGINE_ID, signer_key_id=ENGINE_KEY)
    )
    assert r.evaluated_at == AS_OF
    assert r.establishes == "PROVENANCE_AND_INTEGRITY_ONLY"
    assert r.role_establishes == ra.COMPARISON_RESULT_ATTESTER_ROLE_ESTABLISHES[ENGINE]
    assert r.factual_correctness_established is False


def test_happy_the_verification_record_has_a_recomputable_citation_digest():
    """The digest the composition root hands the advisor: recomputed from the record,
    never stored, moved by every field, and reproducible with plain JSON and SHA-256."""

    import hashlib
    import json

    anchor = anchor_of(engine_signer())
    r = verify(verifier(anchor), signed())
    digest = ra.verification_result_digest(r)
    assert digest.startswith("sha256:") and len(digest) == 71
    assert digest == ra.canonical_digest(r)
    body = json.dumps({
        "anchor_coordinate_digest": r.anchor_coordinate_digest, "anchor_record_digest": r.anchor_record_digest,
        "detail": r.detail, "engine_identity": r.engine_identity, "evaluated_at": "2026-09-06T12:05:00.000000Z",
        "outcome": "VERIFIED", "refusal_reason": None, "result_digest": r.result_digest,
        "signer_identity": r.signer_identity, "signer_key_id": r.signer_key_id, "signer_role": "COMPARISON_ENGINE",
        "signing_payload_digest": r.signing_payload_digest,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert digest == "sha256:" + hashlib.sha256(body).hexdigest()
    later = verify(verifier(anchor), signed(), as_of=AS_OF.replace(minute=6))
    assert ra.verification_result_digest(later) != digest
    with pytest.raises(ra.ComparisonResultAttestationContractError):
        ra.verification_result_digest(object())  # type: ignore[arg-type]


def test_happy_the_wrapper_holds_the_result_unchanged_and_by_identity():
    res = result()
    sr = signed(res=res)
    assert sr.result is res
    assert sr.result_digest == res.result_digest
    assert ra.canonical_comparison_result(sr.result) == ra.canonical_comparison_result(res)
    assert sr.comparison_result_digest == ra.comparison_result_digest(res)


def test_happy_the_directories_the_verifier_and_the_signer_satisfy_the_ports():
    assert isinstance(verifier(), ra.ComparisonResultVerifierPort)
    assert isinstance(ra.DenyAllTrustAnchorDirectory(), ra.TrustAnchorResolverPort)
    assert isinstance(engine_signer(), ra.ComparisonResultSignerPort)
    assert ra.MATURITY == "REFERENCE_GRADE_NOT_PRODUCTION_READY"


def test_happy_deny_all_in_production_composes_and_refuses_everything():
    v = ra.Ed25519ComparisonResultVerifier(
        trust_anchor_resolver=ra.DenyAllTrustAnchorDirectory(), production_mode=True
    )
    r = verify(v, signed())
    assert r.outcome is OUT.REFUSED
    assert r.refusal_reason in (
        ra.ComparisonResultRefusalReason.ANCHOR_UNKNOWN,
        ra.ComparisonResultRefusalReason.ANCHOR_UNAVAILABLE,
    )
    assert v.production_mode is True
