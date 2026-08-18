"""The TEV-2 verification-authority layer (ADR §30, milestone TEV-2).

TEV-1 shipped contract *shapes* and minted no authority. This subpackage is the
authority: "the verification authority, trust anchors, key trust/revocation,
signing, independent verification" (ADR §30, TEV-2).

The three roles, kept apart (ADR §8 — "no row may absorb another")
------------------------------------------------------------------
======================================  ===================================
:class:`~.verification.EvidenceVerificationAuthority`   verifies; holds no key
:class:`~.issuance.ReceiptIssuer`                       signs; verifies nothing
:class:`~.reverification.SignedReceiptVerifier`         re-verifies; holds no key
======================================  ===================================

A deployment wires them in sequence, but no object performs two of the three
roles and none can reach another's capability.

What is still true after TEV-2
------------------------------
* **A receipt authorizes nothing** — not deployment, not runtime action, not
  policy sufficiency, not economic value, not causal attribution (§13.2, E-12).
  A *verified* receipt authorizes exactly as much: nothing.
* **Possession is not validity** (§8.1.3). Holding an envelope, or a
  :class:`~.reverification.ReceiptVerification` object, establishes nothing —
  trust is recomputed at an explicit instant, every time.
* **A signature alone is not trusted verification.** A signature says a key
  signed a frame; whether that key was resolved, entitled, in-window and
  unrevoked is a separate check, and §13.3 rules that a receipt "whose signature
  does not verify against a configured trust anchor is **not** a receipt".
* **A producer cannot verify its own evidence** (E-3). Enforced structurally by
  :class:`~.trust.TrustAnchorCapability`: one key, one role, unrepresentable
  otherwise.
* **No component authorizes itself** (E-5). Trust anchors come from the
  composition root; nothing here self-declares an entitlement.
* **The clock is never read** (§22.9). Every instant is an explicit parameter.
* **Stage 6 is never asserted** (§12). Policy sufficiency is requirement-
  relative and belongs to the consuming evaluation engine.

What TEV-2 deliberately does not do
-----------------------------------
No Benchmark Registry (BR-1/BR-2), no policy applicability resolution, no
Readiness/UVI-EV-1 integration, no RA-5 replacement (E-13, DD-6), no Cloud
Scaling integration, no ActionGate or deployment authorization, no credential
issuance, no forecasting, attribution, valuation or ROI (GV-F → GV-V), no
network trust-anchor retrieval, no cloud KMS (DD-10), no certificate-authority
infrastructure, no receipt persistence or distribution service, and no
multi-algorithm cryptographic agility.

Import the curated surface from :mod:`ugence_trusted_evidence_authority.api`
rather than from these modules directly.
"""

from __future__ import annotations

from .audit import (
    EvidenceVerificationAuditRecord,
    audit_record_for_determination,
    audit_record_for_receipt_verification,
)
from .ed25519 import (
    ED25519_PUBLIC_KEY_SIZE,
    ED25519_SEED_SIZE,
    ED25519_SIGNATURE_SIZE,
    TrustedEvidenceSigningKey,
    TrustedEvidenceVerificationKey,
)
from .envelope import (
    SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN,
    SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1,
    SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN,
    SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1,
    SignedEvidenceSubmission,
    SignedEvidenceVerificationReceipt,
    signed_evidence_input_bytes,
    signed_receipt_input_bytes,
)
from .issuance import ReceiptIssuer
from .profile import (
    SIGNED_INPUT_LENGTH_PREFIX_BYTES,
    TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1,
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
    TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
    decode_public_key,
    decode_signature,
    encode_public_key,
    encode_signature,
    framed_signed_input,
)
from .reverification import (
    ReceiptVerification,
    ReceiptVerificationOutcome,
    SignedReceiptVerifier,
)
from .signing import Ed25519ReceiptSigner, ReceiptSignerPort, ReceiptSigningInput
from .trust import (
    TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
    DenyAllTrustAnchorDirectory,
    KeyRevocation,
    StaticTrustAnchorDirectory,
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustAnchorRecord,
    TrustAnchorResolution,
    TrustAnchorResolverPort,
)
from .verification import (
    TRUSTED_EVIDENCE_PROTOCOL_V1_ID,
    TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION,
    TRUSTED_EVIDENCE_RECEIPT_ID_DOMAIN,
    Ed25519EvidenceAuthenticityProtocol,
    EvidenceAdmissionOutcome,
    EvidenceVerificationAuthority,
    EvidenceVerificationDetermination,
    EvidenceVerificationProtocolPort,
    ProtocolExecutionResult,
    derive_receipt_id,
)

__all__ = [
    # cryptographic profile and encodings (DD-9)
    "TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1",
    "TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1",
    "TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN",
    "TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN",
    "SIGNED_INPUT_LENGTH_PREFIX_BYTES",
    "ED25519_SEED_SIZE",
    "ED25519_PUBLIC_KEY_SIZE",
    "ED25519_SIGNATURE_SIZE",
    "encode_signature",
    "decode_signature",
    "encode_public_key",
    "decode_public_key",
    "framed_signed_input",
    # key material
    "TrustedEvidenceSigningKey",
    "TrustedEvidenceVerificationKey",
    # trust anchors
    "TRUST_ANCHOR_RECORD_DIGEST_DOMAIN",
    "TrustAnchorCapability",
    "TrustAnchorCoordinate",
    "KeyRevocation",
    "TrustAnchorRecord",
    "TrustAnchorResolution",
    "TrustAnchorResolverPort",
    "StaticTrustAnchorDirectory",
    "DenyAllTrustAnchorDirectory",
    # signed artifacts
    "SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1",
    "SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1",
    "SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN",
    "SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN",
    "SignedEvidenceSubmission",
    "SignedEvidenceVerificationReceipt",
    "signed_evidence_input_bytes",
    "signed_receipt_input_bytes",
    # verification
    "TRUSTED_EVIDENCE_PROTOCOL_V1_ID",
    "TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION",
    "TRUSTED_EVIDENCE_RECEIPT_ID_DOMAIN",
    "EvidenceAdmissionOutcome",
    "ProtocolExecutionResult",
    "EvidenceVerificationProtocolPort",
    "Ed25519EvidenceAuthenticityProtocol",
    "EvidenceVerificationDetermination",
    "EvidenceVerificationAuthority",
    "derive_receipt_id",
    # signing and issuance
    "ReceiptSigningInput",
    "ReceiptSignerPort",
    "Ed25519ReceiptSigner",
    "ReceiptIssuer",
    # independent re-verification
    "ReceiptVerificationOutcome",
    "ReceiptVerification",
    "SignedReceiptVerifier",
    # deterministic audit
    "EvidenceVerificationAuditRecord",
    "audit_record_for_determination",
    "audit_record_for_receipt_verification",
]
