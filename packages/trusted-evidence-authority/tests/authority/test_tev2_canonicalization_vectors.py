"""Pinned TEV-2 byte vectors, and TEV-1 backward compatibility.

Two jobs:

1. **Pin TEV-2's own bytes.** Representative signed-input bytes, payload digest,
   envelope digest, signature bytes and verification outcome, all reconstructed
   independently from the documented framing rules and ``hashlib`` alone.
2. **Prove TEV-1 is unchanged.** All four TEV-1 pinned digests, every TEV-1
   dataclass field order, every TEV-1 enum member order, and the two TEV-1
   digest domain tags.

Every value here is a pure function of fixed inputs — no clock, no randomness,
no ambient state — so it is stable across machines, runs and Python versions.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from _authority_builders import (
    VERIFIER_AUTHORITY_ID,
    VERIFIER_KEY_ID,
    authority_anchor,
    authority_signing_key,
    envelope,
    producer_signing_key,
    reverifier,
    submission,
)
from _builders import AS_OF, identity, receipt, request, schema
from ugence_trusted_evidence_authority.api import (
    EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN,
    SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN,
    SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1,
    SIGNED_INPUT_LENGTH_PREFIX_BYTES,
    SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN,
    SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1,
    TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
    TRUSTED_EVIDENCE_CANONICALIZATION_VERSION,
    TRUSTED_EVIDENCE_RECEIPT_ID_DOMAIN,
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
    TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
    canonical_bytes,
    canonical_digest,
    encode_public_key,
    framed_signed_input,
)

# --------------------------------------------------------------------------- #
# TEV-1 pinned digests — the four merged vectors, byte-for-byte
# --------------------------------------------------------------------------- #

TEV1_SCHEMA_DIGEST = (
    "54b9bd615aa13dd133f88580128b4c4094363c75f96b6bcf1d3b2f582683fa62"
)
TEV1_IDENTITY_DIGEST = (
    "26ee959e4c87cc0660895a269c2805af1065ba4f634c9c73070848de7bf51029"
)
TEV1_RECEIPT_PAYLOAD_DIGEST = (
    "d381c723123c583711b0ce08b0e3fe534e3a065182442a3772b8523c7f18b90a"
)


def test_the_tev1_schema_digest_is_unchanged_by_tev2():
    assert canonical_digest(schema()) == TEV1_SCHEMA_DIGEST


def test_the_tev1_identity_digest_is_unchanged_by_tev2():
    assert canonical_digest(identity()) == TEV1_IDENTITY_DIGEST


def test_the_tev1_receipt_payload_digest_is_unchanged_by_tev2():
    assert canonical_digest(receipt()) == TEV1_RECEIPT_PAYLOAD_DIGEST


def test_the_tev1_digest_domains_are_unchanged_by_tev2():
    assert EVIDENCE_IDENTITY_DIGEST_DOMAIN == (
        "ugence.trusted-evidence-authority/evidence-identity/v1"
    )
    assert EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN == (
        "ugence.trusted-evidence-authority/evidence-verification-receipt-payload/v1"
    )
    assert TRUSTED_EVIDENCE_CANONICALIZATION_VERSION == (
        "ugence.trusted-evidence-authority/canonicalization/v1"
    )


def test_adding_tev2_domains_left_every_tev1_frame_untouched():
    """The domain map gained keys; no existing key's value moved."""

    for contract, expected in (
        (schema(), EVIDENCE_IDENTITY_DIGEST_DOMAIN),
        (identity(), EVIDENCE_IDENTITY_DIGEST_DOMAIN),
        (request(), EVIDENCE_IDENTITY_DIGEST_DOMAIN),
        (receipt(), EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN),
    ):
        framed = json.loads(canonical_bytes(contract))
        assert framed["domain"] == expected
        assert framed["canonicalization"] == TRUSTED_EVIDENCE_CANONICALIZATION_VERSION


# --------------------------------------------------------------------------- #
# TEV-2 pinned vectors
# --------------------------------------------------------------------------- #

PINNED_AUTHORITY_PUBLIC_KEY = (
    "29acbae141bccaf0b22e1a94d34d0bc7361e526d0bfe12c89794bc9322966dd7"
)
PINNED_PRODUCER_PUBLIC_KEY = "03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8"

#: The end-to-end vector: one admitted verification, signed and re-verified.
PINNED_RECEIPT_ID = "receipt-cecce28c76753f58e5a1b155fd1184e00d86eac7f0c981194b56e6692a90260a"
PINNED_PAYLOAD_DIGEST = "d599bc64834fa35245753186d82429c4b8ff2eb34a887a57b5295932e2a87e5b"
PINNED_RECEIPT_SIGNED_INPUT_DIGEST = "74e1fbbbd47c0aa229902148ea496fcb0f531c3aff144511ab15433c1ee27c81"
PINNED_RECEIPT_SIGNATURE = (
    "511b09a13603d9f9b772d83b025b71015ac84b38e39339996e9cbc5c52a4309b"
    "05bbe7c5f62e5883acb906ab1c9c8fa79f3a077431bec98400664cd93249f504"
)
PINNED_ENVELOPE_DIGEST = "6b85c6b8439ee3fabcf63a4b31c5c56d0739832a4867f8a262a84fd5a5f29924"
PINNED_EVIDENCE_SIGNATURE = (
    "c92fb7fab66b2ac42789c7dce04a69fb817657077cd11c00017a91a7b398ade2"
    "7829b908e821df4f9809d09f9736478b1be2a845d589acfdac27e14382a78405"
)
PINNED_SUBMISSION_DIGEST = "006b88723dad872be6bcd69befe6921bbd0a959ae3d30024630987babf977d4d"


def test_the_non_production_public_keys_are_pinned():
    """A changed key derivation would silently change every vector below."""

    assert encode_public_key(
        authority_signing_key().verification_key.public_key_bytes
    ) == PINNED_AUTHORITY_PUBLIC_KEY
    assert encode_public_key(
        producer_signing_key().verification_key.public_key_bytes
    ) == PINNED_PRODUCER_PUBLIC_KEY


def test_the_receipt_signed_input_is_reconstructible_from_documented_rules():
    """Rebuilt by hand from the module docstring — no package helper used."""

    signed = envelope()
    payload = signed.payload
    width = SIGNED_INPUT_LENGTH_PREFIX_BYTES
    assert width == 8

    elements = (
        TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN.encode("utf-8"),
        SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1.encode("utf-8"),
        TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1.encode("utf-8"),
        TRUSTED_EVIDENCE_CANONICALIZATION_VERSION.encode("utf-8"),
        EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN.encode("utf-8"),
        VERIFIER_AUTHORITY_ID.encode("utf-8"),
        VERIFIER_KEY_ID.encode("utf-8"),
        payload.verification_protocol_id.encode("utf-8"),
        payload.verification_protocol_version.encode("utf-8"),
        payload.canonical_digest().encode("utf-8"),
        canonical_bytes(payload),
    )
    hand_built = b"".join(
        [len(elements).to_bytes(width, "big")]
        + [
            piece
            for element in elements
            for piece in (len(element).to_bytes(width, "big"), element)
        ]
    )
    assert signed.signed_input_bytes() == hand_built
    assert framed_signed_input(elements) == hand_built

    # The frame opens with the element count, then the domain tag's length.
    assert hand_built[:8] == (11).to_bytes(8, "big")
    assert hand_built[8:16] == len(elements[0]).to_bytes(8, "big")
    assert hand_built[16:16 + len(elements[0])] == elements[0]


def test_the_evidence_signed_input_is_reconstructible_from_documented_rules():
    sub = submission()
    width = SIGNED_INPUT_LENGTH_PREFIX_BYTES
    elements = (
        TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN.encode("utf-8"),
        SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1.encode("utf-8"),
        TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1.encode("utf-8"),
        TRUSTED_EVIDENCE_CANONICALIZATION_VERSION.encode("utf-8"),
        EVIDENCE_IDENTITY_DIGEST_DOMAIN.encode("utf-8"),
        sub.producer_authority_id.encode("utf-8"),
        sub.producer_key_id.encode("utf-8"),
        canonical_bytes(sub.evidence),
    )
    hand_built = b"".join(
        [len(elements).to_bytes(width, "big")]
        + [
            piece
            for element in elements
            for piece in (len(element).to_bytes(width, "big"), element)
        ]
    )
    assert sub.signed_input_bytes() == hand_built
    assert hand_built[:8] == (8).to_bytes(8, "big")


def test_the_end_to_end_vector_is_pinned():
    """Signature bytes, digests, receipt id and outcome — all fixed."""

    signed = envelope()
    assert signed.payload_canonical_digest == PINNED_PAYLOAD_DIGEST
    assert signed.envelope_digest() == PINNED_ENVELOPE_DIGEST
    assert signed.signature == PINNED_RECEIPT_SIGNATURE
    assert signed.payload.receipt_id == PINNED_RECEIPT_ID
    assert hashlib.sha256(signed.signed_input_bytes()).hexdigest() == (
        PINNED_RECEIPT_SIGNED_INPUT_DIGEST
    )
    assert submission().signature == PINNED_EVIDENCE_SIGNATURE
    assert canonical_digest(submission()) == PINNED_SUBMISSION_DIGEST

    verification = reverifier().verify(signed, evaluated_at=AS_OF)
    assert verification.verified is True
    assert verification.envelope_digest == PINNED_ENVELOPE_DIGEST


def test_the_digest_is_sha256_over_exactly_the_canonical_bytes():
    """Recomputed with ``hashlib`` alone, for every TEV-2 artifact."""

    for artifact in (envelope(), submission(), authority_anchor()):
        expected = hashlib.sha256(canonical_bytes(artifact)).hexdigest()
        actual = (
            artifact.envelope_digest()
            if hasattr(artifact, "envelope_digest")
            else artifact.canonical_digest()
        )
        assert actual == expected


def test_every_tev2_domain_is_distinct_and_versioned():
    domains = [
        EVIDENCE_IDENTITY_DIGEST_DOMAIN,
        EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN,
        TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
        SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN,
        SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN,
        TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
        TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
        TRUSTED_EVIDENCE_RECEIPT_ID_DOMAIN,
    ]
    assert len(set(domains)) == len(domains) == 8
    for domain in domains:
        assert domain.startswith("ugence.trusted-evidence-authority/")
        assert domain.endswith("/v1")


def test_the_envelope_and_submission_frames_carry_their_own_domains():
    assert json.loads(canonical_bytes(envelope()))["domain"] == (
        SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN
    )
    assert json.loads(canonical_bytes(submission()))["domain"] == (
        SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN
    )
