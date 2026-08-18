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
]
