"""Trusted-evidence contract shapes, enums, canonicalization and vocabulary.

Import the curated surface from :mod:`ugence_trusted_evidence_authority.api` (or
the equivalently-exported top-level package) rather than from these modules
directly.
"""

from __future__ import annotations

from .canonical import (
    EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    TRUSTED_EVIDENCE_CANONICALIZATION_VERSION,
    canonical_bytes,
    canonical_digest,
)
from .enums import (
    EVIDENCE_TRUST_STAGE_ORDER,
    ApplicabilityDeclaration,
    EvidenceLifecycleState,
    EvidenceStructuralStatus,
    EvidenceTrustStage,
)
from .errors import (
    TrustedEvidenceCanonicalizationError,
    TrustedEvidenceContractError,
    TrustedEvidenceLifecycleError,
)
from .identity import (
    ApplicabilityCoordinate,
    CanonicalEvidenceIdentity,
    EvidenceObservation,
    EvidenceProvenanceChain,
    EvidenceScopeBinding,
    EvidenceSchemaRef,
)
from .lifecycle import (
    EVIDENCE_LIFECYCLE_TRANSITIONS,
    is_valid_lifecycle_transition,
    require_valid_lifecycle_transition,
)
from .reasons import TRUSTED_EVIDENCE_REFUSAL_REASONS, TrustedEvidenceRefusalReason
from .requests import EvidenceVerificationRequest

__all__ = [
    # errors
    "TrustedEvidenceContractError",
    "TrustedEvidenceCanonicalizationError",
    "TrustedEvidenceLifecycleError",
    # enums
    "ApplicabilityDeclaration",
    "EvidenceLifecycleState",
    "EvidenceStructuralStatus",
    "EvidenceTrustStage",
    "TrustedEvidenceRefusalReason",
    # contracts
    "ApplicabilityCoordinate",
    "EvidenceSchemaRef",
    "EvidenceObservation",
    "EvidenceScopeBinding",
    "EvidenceProvenanceChain",
    "CanonicalEvidenceIdentity",
    "EvidenceVerificationRequest",
    # canonicalization
    "canonical_bytes",
    "canonical_digest",
    # lifecycle
    "is_valid_lifecycle_transition",
    "require_valid_lifecycle_transition",
    # pinned constants
    "TRUSTED_EVIDENCE_CANONICALIZATION_VERSION",
    "EVIDENCE_IDENTITY_DIGEST_DOMAIN",
    "EVIDENCE_TRUST_STAGE_ORDER",
    "EVIDENCE_LIFECYCLE_TRANSITIONS",
    "TRUSTED_EVIDENCE_REFUSAL_REASONS",
]
