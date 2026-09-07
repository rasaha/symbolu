"""Deterministic canonical payload and domain-separated digest binding, pinned.

Every literal below was produced once from the pinned fixtures and is asserted
byte for byte thereafter. A moved frame element, a moved canonical rule, a moved
fixture or a moved domain tag fails here before it fails anywhere subtler.
Ed25519 signing is deterministic, so the reference signature is pinned too.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

import ugence_reasoning_method_result_attestation as ra
from _fixtures import PRODUCED_AT, SIGNED_AT, anchor_of, assessment, engine_signer, result, signed

PINNED_RESULT_DIGEST = "56f7174da2768f9c37bd816c8b91593b750be9638f0207ab7dae3f23bdb84db4"
PINNED_PROJECTION_DIGEST = "sha256:4bedf596bb66e4a7d7494cb833773e6fee95786676c6c2fa32f0545dcd43b27d"
PINNED_PAYLOAD_DIGEST = "sha256:3e5add9d75912a6879e4f082392b77f4277a737ad85fe3b764b457e014b25053"
PINNED_SIGNATURE = (
    "ab769d262ffb8d557fb765233d3b3c63ceb3510ed83a5953a0c5d64d253128e1"
    "bd19967e672d1def6d301b405b2576c30d18f1c16b5dd9d2b91e44c814411900"
)
PINNED_ENGINE_PUBLIC_KEY = "8a88e3dd7409f195fd52db2d3cba5d72ca6709bf1d94121bf3748801b40f6f5c"
PINNED_ANCHOR_DIGEST = "sha256:acfa67e547a91c7a263d0e5fccb7bd1361cd5e1e8014ff3f1b916dcf8b9c4abe"
PINNED_FRAME_LENGTH = 1096
PINNED_FRAME_PREFIX = (
    b"\x00\x00\x00G" + b"ugence.reasoning-method-result-attestation/comparison-result-signing/v1"
)


def test_happy_the_pinned_vectors_reproduce_exactly():
    sr = signed()
    assert sr.result_digest == PINNED_RESULT_DIGEST
    assert sr.comparison_result_digest == PINNED_PROJECTION_DIGEST
    assert sr.signing_payload_digest == PINNED_PAYLOAD_DIGEST
    assert sr.signature == PINNED_SIGNATURE
    assert anchor_of(engine_signer()).public_key == PINNED_ENGINE_PUBLIC_KEY
    assert ra.anchor_record_digest(anchor_of(engine_signer())) == PINNED_ANCHOR_DIGEST
    frame = sr.signed_bytes()
    assert len(frame) == PINNED_FRAME_LENGTH
    assert frame.startswith(PINNED_FRAME_PREFIX)


def test_the_digest_recomputes_with_plain_json_and_hashlib_importing_nothing_from_the_package():
    """The canonical rule, restated by hand: sorted keys, compact separators,
    non-ASCII preserved, UTC microsecond timestamps, and the domain frame."""

    sr = signed()
    projection = {
        "authority_resolution_basis": "REQUESTER_ASSERTED",
        "engine_identity": "ugence-readiness-comparison",
        "engine_version": "0.2.0",
        "produced_at": "2026-09-06T11:00:00.000000Z",
        "request_digest": "a" * 64,
        "request_id": "cmp.synthetic",
        "result_digest": PINNED_RESULT_DIGEST,
        "schema_version": "readiness_comparison.result.v1",
    }
    payload = {
        "result": projection,
        "result_digest": PINNED_RESULT_DIGEST,
        "schema_version": "reasoning_method.signed_comparison_result.v1",
        "signature_algorithm": "Ed25519",
        "signature_encoding": "ugence.trusted-evidence-authority/encoding/base16-lower/v1",
        "signature_profile": "ugence.trusted-evidence-authority/signature/ed25519-sha512-pure/v1",
        "signed_at": "2026-09-06T12:00:00.000000Z",
        "signer_identity": "ugence-readiness-comparison",
        "signer_key_id": "engine-key-1",
        "signer_role": "COMPARISON_ENGINE",
        "signing_domain": "ugence.reasoning-method-result-attestation/comparison-result-signing/v1",
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    domain = payload["signing_domain"].encode()
    frame = len(domain).to_bytes(4, "big") + domain + body
    assert frame == sr.signed_bytes()
    assert "sha256:" + hashlib.sha256(body).hexdigest() == PINNED_PAYLOAD_DIGEST
    projection_body = json.dumps(projection, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False).encode()
    assert "sha256:" + hashlib.sha256(projection_body).hexdigest() == PINNED_PROJECTION_DIGEST


def test_the_governance_result_digest_is_the_contracts_own_never_recomputed_here():
    """The bare-hex ``result_digest`` is what the governance contract settles; this
    package re-runs the contract and compares, it does not re-implement it."""

    res = result()
    assert signed(res=res).result_digest == res.result_digest
    assert ra.recomputed_result_digest(res) == dataclasses.replace(res, result_digest="").result_digest


def test_the_signed_fields_are_exactly_the_declared_set_and_exclude_the_signature():
    payload = signed().signing_payload()
    assert tuple(sorted(payload)) == ra.COMPARISON_RESULT_SIGNED_FIELDS
    assert tuple(sorted(payload["result"])) == ra.COMPARISON_RESULT_PROJECTED_FIELDS
    assert "signature" not in payload
    assert payload["signing_domain"] == ra.COMPARISON_RESULT_ATTESTATION_SIGNING_DOMAIN
    assert payload["schema_version"] == ra.COMPARISON_RESULT_ATTESTATION_SCHEMA_VERSION
    assert payload["result_digest"] == payload["result"]["result_digest"]


def test_every_covered_field_moves_the_payload_digest():
    base = signed()
    variants = [
        dataclasses.replace(base, signer_key_id="engine-key-2"),
        dataclasses.replace(base, signed_at=SIGNED_AT.replace(microsecond=1)),
        dataclasses.replace(base, result=result(produced_at=PRODUCED_AT.replace(microsecond=1))),
        dataclasses.replace(base, result=result(request_id="cmp.other")),
        dataclasses.replace(base, result=result(request_digest="b" * 64)),
        dataclasses.replace(base, result=result(engine_version="0.3.0")),
        dataclasses.replace(base, result=result(assessment(assessment_id="a.other"))),
        dataclasses.replace(base, result=result(assessment(), assessment("tree_of_thought", assessment_id="a.2"))),
    ]
    digests = {v.signing_payload_digest for v in variants} | {base.signing_payload_digest}
    assert len(digests) == len(variants) + 1
    # Changing the signature alone changes nothing the signature covers.
    assert dataclasses.replace(base, signature="ab" * 64).signing_payload_digest == base.signing_payload_digest


def test_the_result_digest_is_time_free_but_the_projection_is_not():
    """The governance ``result_digest`` excludes ``produced_at`` (ADR §2); the signed
    projection binds the instant as well, so both facts are visible."""

    a = result()
    b = result(produced_at=PRODUCED_AT.replace(hour=13))
    assert a.result_digest == b.result_digest
    assert ra.comparison_result_digest(a) != ra.comparison_result_digest(b)


def test_mapping_insertion_order_never_moves_the_canonical_bytes():
    """Sorted keys are part of the canonical rule, not an accident of construction:
    two mappings with the same entries in different insertion orders are one message,
    and it is the one plain ``json.dumps(sort_keys=True)`` produces."""

    a = ra.canonical_bytes({"zeta": "1", "alpha": {"y": "2", "x": "3"}})
    b = ra.canonical_bytes({"alpha": {"x": "3", "y": "2"}, "zeta": "1"})
    assert a == b == b'{"alpha":{"x":"3","y":"2"},"zeta":"1"}'
    assert ra.canonical_digest({"zeta": "1", "alpha": "2"}) == ra.canonical_digest({"alpha": "2", "zeta": "1"})


def test_the_domain_prefix_makes_two_domains_two_messages_even_over_identical_json():
    payload = signed().signing_payload()
    a = ra.comparison_result_signing_bytes(payload)
    other = dict(payload, signing_domain="ugence.other/domain/v1")
    b = ra.comparison_result_signing_bytes(other)
    assert a != b and a[4:4 + 71] != b[4:4 + 24]


@pytest.mark.parametrize(
    "value",
    [1.5, b"bytes", {1, 2}, object()],
    ids=["float", "bytes", "set", "object"],
)
def test_values_with_no_canonical_form_are_refused_never_rendered(value):
    with pytest.raises(ra.ComparisonResultAttestationContractError):
        ra.canonical_bytes({"k": value})


def test_non_nfc_text_and_str_subclasses_are_refused_not_normalized():
    class S(str):
        pass

    with pytest.raises(ra.ComparisonResultAttestationContractError):
        ra.canonical_bytes({"k": "e\u0301"})  # decomposed é
    with pytest.raises(ra.ComparisonResultAttestationContractError):
        ra.canonical_bytes({"k": S("x")})
    with pytest.raises(ra.ComparisonResultAttestationContractError):
        ra.canonical_comparison_result(result(request_id="e\u0301"))


def test_str_subclasses_are_refused_at_every_identifier_seam_not_only_in_the_projection():
    class S(str):
        def __eq__(self, other):  # a comparison nobody should be able to override
            return True

        __hash__ = str.__hash__

    base = signed()
    for field in ("signer_identity", "signer_key_id", "schema_version",
                  "signing_domain", "signature_algorithm", "signature_profile", "signature_encoding"):
        with pytest.raises(ra.ComparisonResultAttestationContractError, match="exactly a str"):
            dataclasses.replace(base, **{field: S(getattr(base, field))})
    with pytest.raises(ra.ComparisonResultAttestationContractError, match="exactly a str"):
        ra.canonical_comparison_result(result(request_id=S("cmp.synthetic")))
