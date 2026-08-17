"""Canonical public API for the Ugence Trusted Evidence Authority (TEV-1).

The deliberately small, supported public surface. Import from here (or the
equivalently-exported top-level :mod:`ugence_trusted_evidence_authority`). Every
symbol below is a stable contract shape, vocabulary or pinned constant;
``public_api.json`` snapshots this surface and
``tests/packaging/test_public_api.py`` asserts they agree — in the source tree,
in the built wheel, and in an isolated installed runtime.

There is no verifier here, and no result type
---------------------------------------------
This surface contains no verifier, no trust anchor, no key, no signature, no
receipt, and no object that reports a verification outcome. Those are **TEV-2**
(ADR §30). Nothing exported here authorizes deployment, runtime action, policy
approval, benchmark acceptance, monetary value or causal attribution.

Every constructible object in this API reports its own limits: an evidence
identity's :attr:`structural_status` is permanently ``STRUCTURAL_UNVERIFIED``
and its :attr:`unestablished_trust_stages` is never empty.
"""

from __future__ import annotations

from . import __version__
from .contracts import (
    EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    EVIDENCE_LIFECYCLE_TRANSITIONS,
    EVIDENCE_TRUST_STAGE_ORDER,
    TRUSTED_EVIDENCE_CANONICALIZATION_VERSION,
    TRUSTED_EVIDENCE_REFUSAL_REASONS,
    ApplicabilityCoordinate,
    ApplicabilityDeclaration,
    CanonicalEvidenceIdentity,
    EvidenceLifecycleState,
    EvidenceObservation,
    EvidenceProvenanceChain,
    EvidenceSchemaRef,
    EvidenceScopeBinding,
    EvidenceStructuralStatus,
    EvidenceTrustStage,
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
    "EvidenceLifecycleState",
    "EvidenceStructuralStatus",
    "EvidenceTrustStage",
    "TrustedEvidenceRefusalReason",
    # contract shapes
    "ApplicabilityCoordinate",
    "EvidenceSchemaRef",
    "EvidenceObservation",
    "EvidenceScopeBinding",
    "EvidenceProvenanceChain",
    "CanonicalEvidenceIdentity",
    "EvidenceVerificationRequest",
    # the one canonicalization path and the one digest path
    "canonical_bytes",
    "canonical_digest",
    # lifecycle relation
    "is_valid_lifecycle_transition",
    "require_valid_lifecycle_transition",
    # pinned constants
    "TRUSTED_EVIDENCE_CANONICALIZATION_VERSION",
    "EVIDENCE_IDENTITY_DIGEST_DOMAIN",
    "EVIDENCE_TRUST_STAGE_ORDER",
    "EVIDENCE_LIFECYCLE_TRANSITIONS",
    "TRUSTED_EVIDENCE_REFUSAL_REASONS",
]
