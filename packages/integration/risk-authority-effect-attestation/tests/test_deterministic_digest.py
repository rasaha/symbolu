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

import ugence_risk_authority_effect_attestation as ea
from _fixtures import ATTESTED_AT, anchor_of, attestation, observation, provider_signer

PINNED_OBSERVATION_DIGEST = "sha256:4f33a01727086b55bfb9a1753e1ff2005d35dbd9c523a1885fec1b0d5b54ec94"
PINNED_PAYLOAD_DIGEST = "sha256:efe8b45dd3bc750d3f23df74703c920d24458f6db5df5cfffd937b458f744e3b"
PINNED_SIGNATURE = (
    "86284602d9e63ce04d931db8f411b67e26415e048c54e9c9a2c62803cafac05d"
    "af984514e0c61fec530e4bc3135912e7db688ecc22d6cf4c1d363b9fe825d70f"
)
PINNED_PROVIDER_PUBLIC_KEY = "8a88e3dd7409f195fd52db2d3cba5d72ca6709bf1d94121bf3748801b40f6f5c"
PINNED_ANCHOR_DIGEST = "sha256:6d3c71b24378d4ff52e547d7c9309c7101b6e335bc29f90ce5694eb0a8ff6e7b"
PINNED_FRAME_LENGTH = 876
PINNED_FRAME_PREFIX = (
    b"\x00\x00\x00F" + b"ugence.risk-authority-effect-attestation/effect-attestation-signing/v1"
)


def test_happy_the_pinned_vectors_reproduce_exactly():
    att = attestation()
    assert att.observation_digest == PINNED_OBSERVATION_DIGEST
    assert att.signing_payload_digest == PINNED_PAYLOAD_DIGEST
    assert att.signature == PINNED_SIGNATURE
    assert anchor_of(provider_signer()).public_key == PINNED_PROVIDER_PUBLIC_KEY
    assert ea.anchor_record_digest(anchor_of(provider_signer())) == PINNED_ANCHOR_DIGEST
    frame = att.signed_bytes()
    assert len(frame) == PINNED_FRAME_LENGTH
    assert frame.startswith(PINNED_FRAME_PREFIX)


def test_the_digest_recomputes_with_plain_json_and_hashlib_importing_nothing_from_the_package():
    """The canonical rule, restated by hand: sorted keys, compact separators,
    non-ASCII preserved, UTC microsecond timestamps, and the domain frame."""

    att = attestation()
    payload = {
        "attested_at": "2026-09-06T12:00:00.000000Z",
        "attester_identity": "provider-alpha",
        "attester_key_id": "provider-key-1",
        "attester_role": "EXECUTING_PROVIDER",
        "observation": {
            "business_outcome": "SUCCEEDED",
            "final": True,
            "fingerprint": "fp-1",
            "observed_parameters": {"amount": "12.50", "order_id": "o-1"},
            "provider_trace_id": "trace-1",
            "reason": "",
        },
        "observation_digest": PINNED_OBSERVATION_DIGEST,
        "schema_version": "risk_authority.effect_attestation.v1",
        "signature_algorithm": "Ed25519",
        "signature_encoding": "ugence.trusted-evidence-authority/encoding/base16-lower/v1",
        "signature_profile": "ugence.trusted-evidence-authority/signature/ed25519-sha512-pure/v1",
        "signing_domain": "ugence.risk-authority-effect-attestation/effect-attestation-signing/v1",
        "tenant_id": "tenant-a",
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    domain = payload["signing_domain"].encode()
    frame = len(domain).to_bytes(4, "big") + domain + body
    assert frame == att.signed_bytes()
    assert "sha256:" + hashlib.sha256(body).hexdigest() == PINNED_PAYLOAD_DIGEST
    obs_body = json.dumps(payload["observation"], sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode()
    assert "sha256:" + hashlib.sha256(obs_body).hexdigest() == PINNED_OBSERVATION_DIGEST


def test_the_signed_fields_are_exactly_the_declared_set_and_exclude_the_signature():
    payload = attestation().signing_payload()
    assert tuple(sorted(payload)) == ea.EFFECT_ATTESTATION_SIGNED_FIELDS
    assert "signature" not in payload
    assert payload["signing_domain"] == ea.EFFECT_ATTESTATION_SIGNING_DOMAIN
    assert payload["schema_version"] == ea.EFFECT_ATTESTATION_SCHEMA_VERSION


def test_every_covered_field_moves_the_payload_digest():
    base = attestation()
    variants = [
        dataclasses.replace(base, tenant_id="tenant-b"),
        dataclasses.replace(base, attester_identity="provider-beta"),
        dataclasses.replace(base, attester_key_id="provider-key-2"),
        dataclasses.replace(base, attester_role=ea.EffectAttesterRole.INDEPENDENT_OBSERVER),
        dataclasses.replace(base, attested_at=ATTESTED_AT.replace(microsecond=1)),
        dataclasses.replace(base, observation=observation(final=False)),
        dataclasses.replace(base, observation=observation(observed_parameters={"order_id": "o-1"})),
        dataclasses.replace(base, observation=observation(reason="r")),
    ]
    digests = {v.signing_payload_digest for v in variants} | {base.signing_payload_digest}
    assert len(digests) == len(variants) + 1
    # Changing the signature alone changes nothing the signature covers.
    assert dataclasses.replace(base, signature="ab" * 64).signing_payload_digest == base.signing_payload_digest


def test_parameter_order_does_not_move_the_digest_but_parameter_content_does():
    a = observation(observed_parameters={"order_id": "o-1", "amount": "12.50"})
    b = observation(observed_parameters={"amount": "12.50", "order_id": "o-1"})
    assert ea.observation_digest(a) == ea.observation_digest(b)
    assert ea.observation_digest(observation(observed_parameters={"amount": "12.50"})) != ea.observation_digest(a)


def test_the_domain_prefix_makes_two_domains_two_messages_even_over_identical_json():
    payload = attestation().signing_payload()
    a = ea.effect_attestation_signing_bytes(payload)
    other = dict(payload, signing_domain="ugence.other/domain/v1")
    b = ea.effect_attestation_signing_bytes(other)
    assert a != b and a[4:4 + 70] != b[4:4 + 24]


@pytest.mark.parametrize(
    "value",
    [1.5, b"bytes", {1, 2}, object()],
    ids=["float", "bytes", "set", "object"],
)
def test_values_with_no_canonical_form_are_refused_never_rendered(value):
    with pytest.raises(ea.EffectAttestationContractError):
        ea.canonical_bytes({"k": value})


def test_non_nfc_text_and_str_subclasses_are_refused_not_normalized():
    class S(str):
        pass

    with pytest.raises(ea.EffectAttestationContractError):
        ea.canonical_bytes({"k": "é"})  # decomposed é
    with pytest.raises(ea.EffectAttestationContractError):
        ea.canonical_bytes({"k": S("x")})
    with pytest.raises(ea.EffectAttestationContractError):
        ea.canonical_observation(observation(observed_parameters={"k": 1}))  # type: ignore[dict-item]


def test_str_subclasses_are_refused_at_every_identifier_seam_not_only_in_the_projection():
    class S(str):
        def __eq__(self, other):  # a comparison nobody should be able to override
            return True

        __hash__ = str.__hash__

    base = attestation()
    for field in ("tenant_id", "attester_identity", "attester_key_id", "schema_version",
                  "signing_domain", "signature_algorithm", "signature_profile", "signature_encoding"):
        with pytest.raises(ea.EffectAttestationContractError, match="exactly a str"):
            dataclasses.replace(base, **{field: S(getattr(base, field))})
    with pytest.raises(ea.EffectAttestationContractError, match="exactly a str"):
        ea.canonical_observation(observation(reason=S("r")))
    with pytest.raises(ea.EffectAttestationContractError, match="exactly a str"):
        ea.canonical_observation(observation(observed_parameters={S("k"): "v"}))
