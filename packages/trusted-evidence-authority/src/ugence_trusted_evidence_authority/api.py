"""Canonical public API for the Ugence Trusted Evidence Authority (TEV-1).

The deliberately small, supported public surface. Import from here (or the
equivalently-exported top-level :mod:`ugence_trusted_evidence_authority`). Every
symbol below is a stable contract shape, vocabulary or pinned constant;
``public_api.json`` snapshots this surface and
``tests/packaging/test_public_api.py`` asserts they agree — in the source tree,
in the built wheel, and in an isolated installed runtime.

What this surface does and does not contain
-------------------------------------------
It contains **no verifier, no trust anchor, no key, no signature and no signing
callable**. Those are **TEV-2** (ADR §30).

It **does** export :class:`EvidenceVerificationReceiptPayload` — the structural
receipt-payload shape ADR §30 and the §32 ledger assign to TEV-1 ("*shape =
TEV-1, service = TEV-2*"). It is a **declarative payload contract, not an
authority-issued receipt and not proof of verification**. A caller may write a
declared outcome, refusal reasons, stage declarations, verifier/key/protocol
identifiers and verification coordinates into one; **none of those declarations
establishes authenticity**. Every payload reports ``STRUCTURAL_UNVERIFIED``,
``authenticity_verified`` stays ``False``, and ``CRYPTOGRAPHICALLY_AUTHENTIC``
stays in ``unestablished_trust_stages`` whatever the payload declares.

Signing, signed envelopes, cryptographic verification, trust-anchor resolution,
key validation, key revocation, receipt issuance and receipt re-verification
remain **TEV-2**. Nothing exported here authorizes deployment, execution, policy
sufficiency, benchmark acceptance, economic truth or causal attribution.

Every constructible object in this API reports its own limits: its
:attr:`structural_status` is permanently ``STRUCTURAL_UNVERIFIED`` and its
:attr:`unestablished_trust_stages` is never empty.
"""

from __future__ import annotations

from . import __version__
from .contracts import (
    EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    EVIDENCE_LIFECYCLE_TRANSITIONS,
    EVIDENCE_TRUST_STAGE_ORDER,
    EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN,
    RECEIPT_REPORTABLE_TRUST_STAGES,
    TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS,
    TEV2_TRUSTED_EVIDENCE_REFUSAL_REASONS,
    TRUSTED_EVIDENCE_CANONICALIZATION_VERSION,
    TRUSTED_EVIDENCE_REFUSAL_REASONS,
    ApplicabilityCoordinate,
    ApplicabilityDeclaration,
    CanonicalEvidenceIdentity,
    DeclaredVerificationOutcome,
    EvidenceClaimBinding,
    EvidenceLifecycleState,
    EvidenceObservation,
    EvidenceProvenanceChain,
    EvidenceSchemaRef,
    EvidenceScopeBinding,
    EvidenceStructuralStatus,
    EvidenceTrustStage,
    EvidenceVerificationReceiptPayload,
    EvidenceVerificationRequest,
    TrustedEvidenceCanonicalizationError,
    TrustedEvidenceContractError,
    TrustedEvidenceLifecycleError,
    TrustedEvidenceRefusalReason,
    canonical_bytes,
    canonical_digest,
    is_valid_lifecycle_transition,
    require_valid_lifecycle_transition,
)

from .authority import (
    ED25519_PUBLIC_KEY_SIZE,
    ED25519_SEED_SIZE,
    ED25519_SIGNATURE_SIZE,
    RECEIPT_SCOPE_EXPECTATION_DIGEST_DOMAIN,
    SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN,
    SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1,
    SIGNED_INPUT_LENGTH_PREFIX_BYTES,
    SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN,
    SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1,
    TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
    TRUSTED_EVIDENCE_PROTOCOL_V1_ID,
    TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION,
    TRUSTED_EVIDENCE_RECEIPT_ID_DOMAIN,
    TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1,
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
    TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
    DenyAllTrustAnchorDirectory,
    Ed25519EvidenceAuthenticityProtocol,
    Ed25519ReceiptSigner,
    EvidenceAdmissionOutcome,
    EvidenceVerificationAuditRecord,
    EvidenceVerificationAuthority,
    EvidenceVerificationDetermination,
    EvidenceVerificationProtocolPort,
    KeyRevocation,
    ProtocolExecutionResult,
    ReceiptIssuer,
    ReceiptScopeExpectation,
    ReceiptSignerPort,
    ReceiptSigningInput,
    ReceiptVerificationKind,
    ReceiptVerificationOutcome,
    ScopeBoundVerificationResult,
    SignatureOnlyVerificationResult,
    SignedEvidenceSubmission,
    SignedEvidenceVerificationReceipt,
    SignedReceiptVerifier,
    StaticTrustAnchorDirectory,
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustAnchorRecord,
    TrustAnchorResolution,
    TrustAnchorResolverPort,
    TrustedEvidenceSigningKey,
    TrustedEvidenceVerificationKey,
    audit_record_for_determination,
    audit_record_for_receipt_verification,
    decode_public_key,
    decode_signature,
    derive_receipt_id,
    encode_public_key,
    encode_signature,
    framed_signed_input,
    signed_evidence_input_bytes,
    signed_receipt_input_bytes,
)

__all__ = [
    "__version__",
    # typed contract-validation errors
    "TrustedEvidenceContractError",
    "TrustedEvidenceCanonicalizationError",
    "TrustedEvidenceLifecycleError",
    # vocabularies
    "ApplicabilityDeclaration",
    "DeclaredVerificationOutcome",
    "EvidenceLifecycleState",
    "EvidenceStructuralStatus",
    "EvidenceTrustStage",
    "TrustedEvidenceRefusalReason",
    # contract shapes
    "ApplicabilityCoordinate",
    "EvidenceSchemaRef",
    "EvidenceObservation",
    "EvidenceScopeBinding",
    "EvidenceClaimBinding",
    "EvidenceProvenanceChain",
    "CanonicalEvidenceIdentity",
    "EvidenceVerificationRequest",
    "EvidenceVerificationReceiptPayload",
    # the one canonicalization path and the one digest path
    "canonical_bytes",
    "canonical_digest",
    # lifecycle relation
    "is_valid_lifecycle_transition",
    "require_valid_lifecycle_transition",
    # pinned constants
    "TRUSTED_EVIDENCE_CANONICALIZATION_VERSION",
    "EVIDENCE_IDENTITY_DIGEST_DOMAIN",
    "EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN",
    "EVIDENCE_TRUST_STAGE_ORDER",
    "RECEIPT_REPORTABLE_TRUST_STAGES",
    "EVIDENCE_LIFECYCLE_TRANSITIONS",
    "TRUSTED_EVIDENCE_REFUSAL_REASONS",
    "TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS",
    "TEV2_TRUSTED_EVIDENCE_REFUSAL_REASONS",
    # ==================================================================== #
    # TEV-2 — the verification-authority layer (ADR §30)
    # ==================================================================== #
    # cryptographic profile, encodings and signed-byte framing (DD-9)
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
    # key material — private seeds enter only through the first of these
    "TrustedEvidenceSigningKey",
    "TrustedEvidenceVerificationKey",
    # trust anchors, key lifecycle and exact-coordinate resolution
    "TRUST_ANCHOR_RECORD_DIGEST_DOMAIN",
    "TrustAnchorCapability",
    "TrustAnchorCoordinate",
    "KeyRevocation",
    "TrustAnchorRecord",
    "TrustAnchorResolution",
    "TrustAnchorResolverPort",
    "StaticTrustAnchorDirectory",
    "DenyAllTrustAnchorDirectory",
    # the two signed artifacts and their signed-byte reconstruction
    "SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1",
    "SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1",
    "SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN",
    "SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN",
    "SignedEvidenceSubmission",
    "SignedEvidenceVerificationReceipt",
    "signed_evidence_input_bytes",
    "signed_receipt_input_bytes",
    # verification: the protocol boundary and the authority
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
    # signing and issuance — the narrow boundary
    "ReceiptSigningInput",
    "ReceiptSignerPort",
    "Ed25519ReceiptSigner",
    "ReceiptIssuer",
    # independent re-verification — two explicit operations, two result types
    "RECEIPT_SCOPE_EXPECTATION_DIGEST_DOMAIN",
    "ReceiptVerificationKind",
    "ReceiptVerificationOutcome",
    "ReceiptScopeExpectation",
    "SignatureOnlyVerificationResult",
    "ScopeBoundVerificationResult",
    "SignedReceiptVerifier",
    # deterministic audit records
    "EvidenceVerificationAuditRecord",
    "audit_record_for_determination",
    "audit_record_for_receipt_verification",
]
