"""Audit-owned fixture construction for the TEV-2 (PR #1446) closure re-audit.

Builds a genuine, correctly-signed envelope and its matching trust anchor from
the curated public API alone (``ugence_trusted_evidence_authority.api``) — no
package test helper, no ``_builders``/``_authority_builders``, no private
submodule. A probe that reused the suite's own fixture code could only
re-confirm the suite's own assumptions about what a "genuine" envelope looks
like; building it independently means every fixture in this audit stands on
its own.

Import this after putting the package's ``src`` on ``sys.path`` (see any probe
script's own path setup — pass the checkout root as argv[1]).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import ugence_trusted_evidence_authority.api as api

NOW = datetime(2026, 6, 2, tzinfo=timezone.utc)
AUTHORITY_ID = "authority-reaudit"
KEY_ID = "key-reaudit-1"
TENANT_ID = "tenant-reaudit"
TRUST_SET_ID = "reaudit-set"
TRUST_SET_VERSION = "1"


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def signing_key(seed_byte: int = 0x11) -> "api.TrustedEvidenceSigningKey":
    return api.TrustedEvidenceSigningKey(bytes([seed_byte]) * api.ED25519_SEED_SIZE)


def scope(**overrides) -> "api.EvidenceScopeBinding":
    kwargs = dict(
        tenant_id=TENANT_ID,
        assessment_context_ref="ctx-reaudit",
        assessment_context_digest=_digest("ctx-reaudit"),
        subject_ref="subject-reaudit",
        assessment_purpose_ref="purpose-reaudit",
        usage_scope_ref="usage-reaudit",
        assessed_system_applicability=api.ApplicabilityDeclaration.APPLICABLE,
        assessed_system_binding_ref="system-reaudit",
        assessed_system_binding_digest=_digest("system-reaudit"),
    )
    kwargs.update(overrides)
    return api.EvidenceScopeBinding(**kwargs)


def payload(sc=None, **overrides) -> "api.EvidenceVerificationReceiptPayload":
    sc = sc or scope()
    kwargs = dict(
        receipt_id="receipt-reaudit-0001",
        schema=api.EvidenceSchemaRef(schema_id="ugence.evidence.reaudit", schema_version="1"),
        source_evidence_identity_digest=_digest("source-identity"),
        evidence_content_digest=_digest("evidence-content"),
        verification_request_digest=_digest("verification-request"),
        scope=sc,
        verified_at=NOW,
        verifier_authority_id=AUTHORITY_ID,
        verifier_key_id=KEY_ID,
        verification_protocol_id=api.TRUSTED_EVIDENCE_PROTOCOL_V1_ID,
        verification_protocol_version=api.TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION,
        declared_outcome=api.DeclaredVerificationOutcome.DECLARED_ADMITTED,
        declared_cleared_stages=(
            api.EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
            api.EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
        ),
        declared_unattempted_stages=(),
        declared_refusal_reasons=(),
    )
    kwargs.update(overrides)
    return api.EvidenceVerificationReceiptPayload(**kwargs)


def genuine_envelope(sk=None, pl=None):
    """A payload signed for real, plus the signing key that produced it."""

    sk = sk or signing_key()
    pl = pl or payload()
    frame = api.signed_receipt_input_bytes(
        payload=pl, signer_authority_id=AUTHORITY_ID, signing_key_id=KEY_ID)
    sig = sk.sign(frame)
    envelope = api.SignedEvidenceVerificationReceipt(
        envelope_schema=api.SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1,
        payload=pl,
        payload_canonical_digest=pl.canonical_digest(),
        signature_profile=api.TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
        signed_input_domain=api.TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
        signer_authority_id=AUTHORITY_ID,
        signing_key_id=KEY_ID,
        signature=api.encode_signature(sig),
    )
    return envelope, sk, frame


def genuine_anchor(sk) -> "api.TrustAnchorRecord":
    pub = sk.verification_key.public_key_bytes
    return api.TrustAnchorRecord(
        authority_id=AUTHORITY_ID,
        key_id=KEY_ID,
        capability=api.TrustAnchorCapability.RECEIPT_ISSUANCE,
        public_key=api.encode_public_key(pub),
        trust_anchor_set_id=TRUST_SET_ID,
        trust_anchor_set_version=TRUST_SET_VERSION,
    )


def verifier_for(anchor) -> "api.SignedReceiptVerifier":
    directory = api.StaticTrustAnchorDirectory(
        (anchor,), trust_anchor_set_id=TRUST_SET_ID, trust_anchor_set_version=TRUST_SET_VERSION)
    return api.SignedReceiptVerifier(trust_anchors=directory)


def full_expectation(sc=None, pl=None) -> "api.ReceiptScopeExpectation":
    sc = sc or scope()
    pl = pl or payload(sc)
    return api.ReceiptScopeExpectation(
        tenant_id=sc.tenant_id,
        assessment_context_ref=sc.assessment_context_ref,
        subject_ref=sc.subject_ref,
        assessed_system_binding_digest=sc.assessed_system_binding_digest,
        assessment_purpose_ref=sc.assessment_purpose_ref,
        usage_scope_ref=sc.usage_scope_ref,
        evidence_content_digest=pl.evidence_content_digest,
        verification_protocol_id=pl.verification_protocol_id,
        verification_protocol_version=pl.verification_protocol_version,
    )
