"""Plain constructors for representative contracts, used by the package tests.

Deliberately **not** a conftest fixture module and deliberately **not** shipped
in the wheel. These are thin wrappers that call the public constructors with
default coordinates and pass through keyword overrides; they contain no
validation logic of their own, so a test that builds through them still
exercises the real public constructor and its real invariants.

The independent probe harness (``adversarial_probes.py``) imports **none** of
this — it builds everything from the curated public API alone.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from ugence_trusted_evidence_authority.api import (
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
    EvidenceTrustStage,
    EvidenceVerificationReceiptPayload,
    EvidenceVerificationRequest,
    TrustedEvidenceRefusalReason,
)

CONTENT_DIGEST = hashlib.sha256(b"evidence-content").hexdigest()
CONTEXT_DIGEST = hashlib.sha256(b"assessment-context").hexdigest()
BINDING_DIGEST = hashlib.sha256(b"system-binding").hexdigest()
OTHER_DIGEST = hashlib.sha256(b"something-else").hexdigest()

OBSERVED_FROM = datetime(2026, 3, 1, 10, 0, 0, 250000, tzinfo=timezone.utc)
OBSERVED_TO = datetime(2026, 3, 1, 11, 0, 0, tzinfo=timezone.utc)
COLLECTED_AT = datetime(2026, 3, 1, 12, 0, 0, 500000, tzinfo=timezone.utc)
VALID_FROM = datetime(2026, 3, 1, tzinfo=timezone.utc)
VALID_TO = datetime(2026, 9, 1, tzinfo=timezone.utc)
AS_OF = datetime(2026, 6, 1, tzinfo=timezone.utc)


def schema(**kw) -> EvidenceSchemaRef:
    return EvidenceSchemaRef(
        **{"schema_id": "ugence.evidence.control-test", "schema_version": "1", **kw}
    )


def observation(**kw) -> EvidenceObservation:
    return EvidenceObservation(
        **{
            "producer_id": "prod-a",
            "collected_at": COLLECTED_AT,
            "observed_from": OBSERVED_FROM,
            "observed_to": OBSERVED_TO,
            "issuer_id": "issuer-b",
            **kw,
        }
    )


def scope(**kw) -> EvidenceScopeBinding:
    return EvidenceScopeBinding(
        **{
            "tenant_id": "tenant-1",
            "assessment_context_ref": "ctx-1",
            "assessment_context_digest": CONTEXT_DIGEST,
            "subject_ref": "subject-1",
            "assessment_purpose_ref": "purpose-readiness",
            "usage_scope_ref": "scope-general",
            "assessed_system_applicability": ApplicabilityDeclaration.APPLICABLE,
            "assessed_system_binding_ref": "bind-1",
            "assessed_system_binding_digest": BINDING_DIGEST,
            **kw,
        }
    )


def claim(**kw) -> EvidenceClaimBinding:
    return EvidenceClaimBinding(
        **{
            "applicability": ApplicabilityDeclaration.APPLICABLE,
            "claim_ref": "claim-1",
            "metric_ref": "metric-resolution-rate",
            "unit": "ratio",
            "measurement_semantics_ref": "semantics-1",
            **kw,
        }
    )


def provenance(**kw) -> EvidenceProvenanceChain:
    return EvidenceProvenanceChain(
        **{"chain_ref": "chain-1", "custody_refs": ("custody-1", "custody-2"), **kw}
    )


def identity(**kw) -> CanonicalEvidenceIdentity:
    return CanonicalEvidenceIdentity(
        **{
            "evidence_id": "ev-1",
            "evidence_type": "CONTROL_TEST_RESULT",
            "schema": schema(),
            "content_digest": CONTENT_DIGEST,
            "observation": observation(),
            "scope": scope(),
            "claim": claim(),
            "provenance": provenance(),
            "lifecycle_state": EvidenceLifecycleState.SUBMITTED,
            "geography": ApplicabilityCoordinate.applicable("US"),
            "domain": ApplicabilityCoordinate.not_applicable(),
            "intended_outcome": ApplicabilityCoordinate.applicable("ticket-resolution"),
            "valid_from": VALID_FROM,
            "valid_to": VALID_TO,
            **kw,
        }
    )


def request(**kw) -> EvidenceVerificationRequest:
    return EvidenceVerificationRequest(
        **{
            "evidence": identity(),
            "expected_content_digest": CONTENT_DIGEST,
            "expected_tenant_id": "tenant-1",
            "expected_assessment_context_ref": "ctx-1",
            "expected_assessment_context_digest": CONTEXT_DIGEST,
            "expected_subject_ref": "subject-1",
            "expected_assessment_purpose_ref": "purpose-readiness",
            "expected_usage_scope_ref": "scope-general",
            "expected_assessed_system_binding_ref": "bind-1",
            "expected_assessed_system_binding_digest": BINDING_DIGEST,
            "as_of": AS_OF,
            "requested_trust_stages": (
                EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
                EvidenceTrustStage.CURRENTLY_VALID,
            ),
            **kw,
        }
    )


VERIFIED_AT = datetime(2026, 6, 1, 8, 0, 0, 750000, tzinfo=timezone.utc)
RECEIPT_VALID_FROM = datetime(2026, 6, 1, tzinfo=timezone.utc)
RECEIPT_VALID_TO = datetime(2026, 12, 1, tzinfo=timezone.utc)


def receipt(**kw) -> EvidenceVerificationReceiptPayload:
    """A representative *declared-admitted* payload.

    Deliberately the most favourable-looking shape a caller can build — every
    reportable stage cleared, an authoritative-sounding verifier — so the tests
    that assert it is still structurally unverified are testing the case that
    matters.
    """

    base = dict(
        receipt_id="receipt-1",
        schema=EvidenceSchemaRef(
            schema_id="ugence.receipt.evidence-verification", schema_version="1"
        ),
        source_evidence_identity_digest=identity().canonical_digest(),
        evidence_content_digest=CONTENT_DIGEST,
        verification_request_digest=request().canonical_digest(),
        scope=scope(),
        verified_at=VERIFIED_AT,
        verifier_authority_id="verifier-authority-1",
        verifier_key_id="key-1",
        verification_protocol_id="ugence.tap.verification",
        verification_protocol_version="1",
        declared_outcome=DeclaredVerificationOutcome.DECLARED_ADMITTED,
        declared_cleared_stages=(
            EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
            EvidenceTrustStage.PROVENANCE_VERIFIED,
            EvidenceTrustStage.CONTEXT_SYSTEM_BOUND,
            EvidenceTrustStage.CURRENTLY_VALID,
        ),
        declared_unattempted_stages=(),
        declared_refusal_reasons=(),
        evidence_valid_from=VALID_FROM,
        evidence_valid_to=VALID_TO,
        receipt_valid_from=RECEIPT_VALID_FROM,
        receipt_valid_to=RECEIPT_VALID_TO,
    )
    base.update(kw)
    return EvidenceVerificationReceiptPayload(**base)


def refused_receipt(**kw) -> EvidenceVerificationReceiptPayload:
    return receipt(
        **{
            "declared_outcome": DeclaredVerificationOutcome.DECLARED_REFUSED,
            "declared_cleared_stages": (
                EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
            ),
            "declared_unattempted_stages": (EvidenceTrustStage.CURRENTLY_VALID,),
            "declared_refusal_reasons": (
                TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_TENANT_MISMATCH,
            ),
            **kw,
        }
    )
