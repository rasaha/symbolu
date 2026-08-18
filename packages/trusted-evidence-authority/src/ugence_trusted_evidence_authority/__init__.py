"""Ugence Trusted Evidence Authority — TEV-1 trusted-evidence contracts.

The platform **Trust Assurance** role's contract package, ratified in
``docs/architecture/ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md``
(E-1, E-2, §6.2) and implementing milestone **TEV-1** of §30. It holds the
immutable contract *shapes* for canonical evidence identity — schema, no
authority.

What this package is
--------------------
* canonical evidence identity and coordinates (:class:`CanonicalEvidenceIdentity`
  and the nested :class:`EvidenceSchemaRef`, :class:`EvidenceObservation`,
  :class:`EvidenceScopeBinding`, :class:`EvidenceClaimBinding`,
  :class:`EvidenceProvenanceChain`, :class:`ApplicabilityCoordinate`) — the
  evidence-side rows of ADR §9, including the claim/metric identity of row 11 and
  the units and measurement semantics of row 12;
* one deterministic canonicalization path and one digest path, versioned and
  domain-separated;
* the ADR §12 six-stage trust vocabulary and the ADR §28 lifecycle relation;
* the typed ADR §11 refusal vocabulary, every member of which is a refusal;
* the input contract a future TEV-2 verifier will accept
  (:class:`EvidenceVerificationRequest`);
* the **structural receipt payload** (:class:`EvidenceVerificationReceiptPayload`)
  — the §13 receipt *shape*, which §30 and the §32 ledger both assign to TEV-1
  ("*shape = TEV-1, service = TEV-2*"). It carries ADR §9 rows 6 and 14-16, the
  verification coordinates that describe an act rather than the evidence.

What this package is **not**
----------------------------
It is **not** a verifier and mints **no** authority. It performs no
trust-anchor resolution, no cryptography, no key management, no revocation
service and no authenticity decision. It contains no placeholder verifier, no
permissive stub, and no field reserved for a later milestone. TEV-2 owns all of
that (ADR §30).

In particular **it issues no signed, authority-issued receipt.** It *does*
export the structural **receipt payload** shape, but that payload is unsigned,
and ADR §13.3 rules that "a receipt that is unsigned … is **not** a receipt.
There is no 'trusted but unsigned' state." The payload carries **no signature
field**, not even an optional or placeholder one: TEV-1 fixes the canonical
content, its canonicalization version and its domain tag — which §13.3 requires
be settled "before signing exists" — and TEV-2 adds the signature, the signed
envelope, key validation, key revocation, receipt issuance and receipt
re-verification. Every verification coordinate on a payload is a **declaration
written by its caller**, never an established fact.

It is explicitly **not** ``ugence-tap-provider`` (the assertion-support scorer,
ADR §6.1 — "assertion-support scoring and evidence verification are different
trust questions and are never merged"), **not**
``risk_authority.integrations.tap`` (the RA-scoped evidence-admission seam that
RA-5 owns and E-13 preserves unchanged), **not** the ``truth_assurance_pipeline``
research corpus, and **not** the Policy Authority, Benchmark Registry, Decision
Authority, ActionGate, Readiness or Governed Value.

It is a **leaf**: stdlib only, no Ugence package, no third-party runtime
dependency. ADR §23 permits TAP to depend on ``governance-contracts``; TEV-1
takes the narrower zero-dependency option because DD-2 — which contracts land in
that leaf — is explicitly blocked on "the concrete contract shapes from
TEV-1/BR-1", and pre-empting it here would decide DD-2 by implementation.
``AssessedSystemBinding`` stays Governance Contracts' single definition (§14);
this package references it by opaque reference and digest and never redefines
it. No ``SystemManifest`` is defined (DD-11).

Nothing here proves authenticity
--------------------------------
Constructing any object in this package is a structural act. It establishes ADR
§12 stage 1 and nothing else: not authenticity, not provenance, not scope
binding, not currency, and not sufficiency for any requirement. Possession,
parsing, canonicalization, digest equality, an authority-looking name, a
lifecycle label and a caller-supplied value are all enumerated non-proofs
(§10). No result of this package authorizes deployment, runtime action, policy
approval, benchmark acceptance, monetary value or causal attribution.

Import the curated surface from :mod:`ugence_trusted_evidence_authority.api`.
"""

from __future__ import annotations

__version__ = "0.2.0"

from .contracts import (  # noqa: E402
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

from .authority import (  # noqa: E402
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

from . import api  # noqa: E402,F401

__all__ = [
    "__version__",
    "TrustedEvidenceContractError",
    "TrustedEvidenceCanonicalizationError",
    "TrustedEvidenceLifecycleError",
    "ApplicabilityDeclaration",
    "DeclaredVerificationOutcome",
    "EvidenceLifecycleState",
    "EvidenceStructuralStatus",
    "EvidenceTrustStage",
    "TrustedEvidenceRefusalReason",
    "ApplicabilityCoordinate",
    "EvidenceSchemaRef",
    "EvidenceObservation",
    "EvidenceScopeBinding",
    "EvidenceClaimBinding",
    "EvidenceProvenanceChain",
    "CanonicalEvidenceIdentity",
    "EvidenceVerificationRequest",
    "EvidenceVerificationReceiptPayload",
    "canonical_bytes",
    "canonical_digest",
    "is_valid_lifecycle_transition",
    "require_valid_lifecycle_transition",
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
    "api",
]
