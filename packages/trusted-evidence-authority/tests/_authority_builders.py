"""TEV-2 builders and the **non-production** test key vectors.

Same posture as :mod:`_builders`: thin wrappers over the real public
constructors, no validation logic of their own, deliberately not a conftest
fixture module and deliberately not shipped in the wheel. The independent probe
harness imports **none** of this.

============================================================================
THESE KEYS ARE NOT PRODUCTION KEYS AND MUST NEVER BE USED AS ONE
============================================================================

Every seed below is a **fixed, public, hard-coded, byte-obvious test vector**
committed to a public source tree. Two of them are the RFC 8032 §7.1 published
test vectors — literally the most widely-known Ed25519 private keys in
existence. The rest are trivially-patterned byte ranges.

They exist because the package must be deterministic: ``os``, ``secrets`` and
``random`` are banned package-wide by
``tests/packaging/test_no_clock_or_environment.py`` so that every output is a
pure function of its inputs, which means a test cannot generate a key. Fixed
vectors are the only option, and making them *unmistakably* fake is the
mitigation.

Every seed constant is named ``NON_PRODUCTION_*`` so a grep for a leaked key in
this repository, or an operator reading a stack trace, cannot mistake one for
real material. ``tests/authority/test_key_material_hygiene.py`` asserts the
naming convention holds and that none of these bytes can reach a canonical byte
sequence, a digest, an envelope, a ``repr``, an exception or the built wheel.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from _builders import (  # noqa: F401 - re-exported for TEV-2 tests
    AS_OF,
    CONTENT_DIGEST,
    identity,
    request,
    schema,
)
from ugence_trusted_evidence_authority.api import (
    SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1,
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
    Ed25519EvidenceAuthenticityProtocol,
    Ed25519ReceiptSigner,
    EvidenceSchemaRef,
    EvidenceVerificationAuthority,
    ReceiptIssuer,
    SignedEvidenceSubmission,
    SignedReceiptVerifier,
    StaticTrustAnchorDirectory,
    TrustAnchorCapability,
    TrustAnchorRecord,
    TrustedEvidenceSigningKey,
    encode_public_key,
    encode_signature,
    signed_evidence_input_bytes,
)

# --------------------------------------------------------------------------- #
# NON-PRODUCTION test key material — see the module docstring
# --------------------------------------------------------------------------- #

#: NOT A PRODUCTION KEY. Bytes 0x00..0x1f, in order.
NON_PRODUCTION_PRODUCER_SEED = bytes(range(0, 32))
#: NOT A PRODUCTION KEY. Bytes 0x20..0x3f, in order.
NON_PRODUCTION_AUTHORITY_SEED = bytes(range(32, 64))
#: NOT A PRODUCTION KEY. Bytes 0x40..0x5f, in order — a second, wrong authority.
NON_PRODUCTION_ATTACKER_SEED = bytes(range(64, 96))
#: NOT A PRODUCTION KEY. RFC 8032 §7.1 TEST 1 secret key, published in the RFC.
NON_PRODUCTION_RFC8032_TEST1_SEED = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc4"
    "4449c5697b326919703bac031cae7f60"
)

PRODUCER_AUTHORITY_ID = "ugence-evidence-producer-nonprod"
PRODUCER_KEY_ID = "producer-key-nonprod-1"
VERIFIER_AUTHORITY_ID = "ugence-trusted-evidence-authority-nonprod"
VERIFIER_KEY_ID = "authority-key-nonprod-1"
TRUST_ANCHOR_SET_ID = "nonprod-trust-anchor-set"
TRUST_ANCHOR_SET_VERSION = "1"

VERIFIED_AT = datetime(2026, 6, 1, 8, 0, 0, 750000, tzinfo=timezone.utc)
KEY_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
KEY_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
LATER = AS_OF + timedelta(days=30)


def producer_signing_key() -> TrustedEvidenceSigningKey:
    """NOT A PRODUCTION KEY."""

    return TrustedEvidenceSigningKey(NON_PRODUCTION_PRODUCER_SEED)


def authority_signing_key() -> TrustedEvidenceSigningKey:
    """NOT A PRODUCTION KEY."""

    return TrustedEvidenceSigningKey(NON_PRODUCTION_AUTHORITY_SEED)


def attacker_signing_key() -> TrustedEvidenceSigningKey:
    """NOT A PRODUCTION KEY. A second key, for substitution tests."""

    return TrustedEvidenceSigningKey(NON_PRODUCTION_ATTACKER_SEED)


def receipt_schema() -> EvidenceSchemaRef:
    return EvidenceSchemaRef(
        schema_id="ugence.receipt.evidence-verification", schema_version="1"
    )


def producer_anchor(**kw) -> TrustAnchorRecord:
    return TrustAnchorRecord(
        **{
            "authority_id": PRODUCER_AUTHORITY_ID,
            "key_id": PRODUCER_KEY_ID,
            "capability": TrustAnchorCapability.EVIDENCE_PRODUCTION,
            "public_key": encode_public_key(
                producer_signing_key().verification_key.public_key_bytes
            ),
            "trust_anchor_set_id": TRUST_ANCHOR_SET_ID,
            "trust_anchor_set_version": TRUST_ANCHOR_SET_VERSION,
            "effective_from": KEY_FROM,
            "effective_to": KEY_TO,
            **kw,
        }
    )


def authority_anchor(**kw) -> TrustAnchorRecord:
    return TrustAnchorRecord(
        **{
            "authority_id": VERIFIER_AUTHORITY_ID,
            "key_id": VERIFIER_KEY_ID,
            "capability": TrustAnchorCapability.RECEIPT_ISSUANCE,
            "public_key": encode_public_key(
                authority_signing_key().verification_key.public_key_bytes
            ),
            "trust_anchor_set_id": TRUST_ANCHOR_SET_ID,
            "trust_anchor_set_version": TRUST_ANCHOR_SET_VERSION,
            "effective_from": KEY_FROM,
            "effective_to": KEY_TO,
            **kw,
        }
    )


def directory(*anchors) -> StaticTrustAnchorDirectory:
    return StaticTrustAnchorDirectory(
        anchors or (producer_anchor(), authority_anchor()),
        trust_anchor_set_id=TRUST_ANCHOR_SET_ID,
        trust_anchor_set_version=TRUST_ANCHOR_SET_VERSION,
    )


def submission(evidence=None, *, signing_key=None, **kw) -> SignedEvidenceSubmission:
    """A correctly producer-signed submission over the standard evidence."""

    evidence = identity() if evidence is None else evidence
    key = producer_signing_key() if signing_key is None else signing_key
    producer_authority_id = kw.pop("producer_authority_id", PRODUCER_AUTHORITY_ID)
    producer_key_id = kw.pop("producer_key_id", PRODUCER_KEY_ID)
    signature = kw.pop(
        "signature",
        encode_signature(
            key.sign(
                signed_evidence_input_bytes(
                    evidence=evidence,
                    producer_authority_id=producer_authority_id,
                    producer_key_id=producer_key_id,
                )
            )
        ),
    )
    return SignedEvidenceSubmission(
        **{
            "envelope_schema": SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1,
            "evidence": evidence,
            "evidence_identity_digest": evidence.canonical_digest(),
            "producer_authority_id": producer_authority_id,
            "producer_key_id": producer_key_id,
            "signature_profile": TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
            "signed_input_domain": TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
            "signature": signature,
            **kw,
        }
    )


def signer(**kw) -> Ed25519ReceiptSigner:
    return Ed25519ReceiptSigner(
        **{
            "signer_authority_id": VERIFIER_AUTHORITY_ID,
            "signing_key_id": VERIFIER_KEY_ID,
            "signing_key": authority_signing_key(),
            **kw,
        }
    )


def authority(trust_anchors=None, **kw) -> EvidenceVerificationAuthority:
    return EvidenceVerificationAuthority(
        **{
            "authority_id": VERIFIER_AUTHORITY_ID,
            "trust_anchors": directory() if trust_anchors is None else trust_anchors,
            "protocol": Ed25519EvidenceAuthenticityProtocol(),
            "receipt_schema": receipt_schema(),
            **kw,
        }
    )


def issuer(**kw) -> ReceiptIssuer:
    return ReceiptIssuer(**{"signer": signer(), **kw})


def reverifier(trust_anchors=None) -> SignedReceiptVerifier:
    return SignedReceiptVerifier(
        trust_anchors=directory() if trust_anchors is None else trust_anchors
    )


def determination(**kw):
    """Run the standard happy path and return the ADMITTED determination."""

    return authority(kw.pop("trust_anchors", None)).verify(
        kw.pop("submission_", submission()),
        kw.pop("request_", request()),
        verified_at=kw.pop("verified_at", VERIFIED_AT),
        verifier_key_id=kw.pop("verifier_key_id", VERIFIER_KEY_ID),
        **kw,
    )


def envelope(**kw):
    """Run the standard happy path all the way to a signed receipt envelope."""

    return issuer().issue(determination(**kw))
