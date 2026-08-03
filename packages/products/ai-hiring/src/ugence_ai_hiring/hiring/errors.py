"""Hiring-domain error taxonomy — canonical import surface.

The hiring domain's typed error families live physically in ``ugence_ai_hiring.errors``
(the historical package retained for import stability). This module is the
*canonical* place to import them from when writing hiring-domain and application
code, mirroring the ``applications.ugence_ai_hiring`` / ``ugence_ai_hiring.hiring`` package
structure. It re-exports the **hiring-specific** families only — the
domain-neutral base (:class:`GovernanceError` / :class:`DomainValidationError`)
and the neutral repository / governance-chain error families remain owned by the
kernel (``ugence_decision_authority.errors``).

Identity is preserved: every name below is the *same class object* as the one
under ``ugence_ai_hiring.errors`` and, for the base, ``ugence_decision_authority.errors``.
``isinstance`` and ``except`` behavior is therefore unchanged across all three
import surfaces.
"""

from __future__ import annotations

# Domain-neutral base, owned by the kernel. ``HiringError`` is an alias of the
# kernel base, so hiring errors and neutral kernel errors share one root.
from ugence_decision_authority.api.errors import DomainValidationError, GovernanceError

from ugence_ai_hiring.errors import HiringError

# --- Hiring-specific error families (defined in the hiring layer) -----------
from ugence_ai_hiring.errors import (
    # Boundary / authorization
    BoundaryViolationError,
    OverrideRequiredError,
    UnauthenticatedActorError,
    # Workflow
    BindingTransitionRequiresDecisionError,
    BlockedEvaluationError,
    InvalidTransitionError,
    # Phase 2: evidence ingestion & normalization
    ContentExtractionError,
    DuplicateEvidenceError,
    IngestionError,
    IntegrityValidationError,
    LineageError,
    UnsupportedFormatError,
    # Phase 2.5: evidence boundary hardening
    ArchiveSafetyError,
    EmptyExtractionError,
    EncryptedContentError,
    EvidenceAccessDeniedError,
    EvidenceIneligibleError,
    EvidenceIntegrityError,
    HashMismatchError,
    LineageConflictingParentError,
    LineageContextMismatchError,
    LineageCycleError,
    LineageParentNotFoundError,
    LineageVersionRegressionError,
    ManualReviewRequiredError,
    ReconstructionError,
    ResourceLimitError,
    StructuredLimitError,
    TenantMismatchError,
    TextLimitError,
    # Phase 3A: capability ontology & rubric contracts
    ApprovalError,
    CapabilityCycleError,
    CapabilityNotFoundError,
    ImmutableCapabilityError,
    ImmutableRubricError,
    InvalidLifecycleTransitionError,
    OntologyError,
    RubricError,
    RubricNotFoundError,
    RubricValidationError,
    UnknownEvidenceTypeError,
    UnknownReasonCodeError,
    UnknownScoringScaleError,
    # Phase 3B: deterministic assessment runtime
    AIObservationNotAllowedError,
    AssessmentAlreadyFinalizedError,
    AssessmentAuthorizationError,
    AssessmentError,
    AssessmentIncompleteError,
    AssessmentNotFoundError,
    AssessmentSupersededError,
    AssessmentWorkspaceNotFoundError,
    BlockingConflictError,
    CapabilityVersionMismatchError,
    CrossTenantAssessmentAccessError,
    EvidenceBindingNotFoundError,
    EvidenceNotEligibleForAssessmentError,
    ObservationScaleMismatchError,
    ObservationSupplierNotAuthorizedError,
    ObservationValidationError,
    ObservationValueOutOfRangeError,
    PublishedRubricRequiredError,
    QuarantinedEvidenceBindingError,
    ReasonCodeNotPermittedError,
    RequiredUncertaintyMissingError,
)

__all__ = [
    "GovernanceError",
    "DomainValidationError",
    "HiringError",
    "BoundaryViolationError",
    "OverrideRequiredError",
    "UnauthenticatedActorError",
    "BindingTransitionRequiresDecisionError",
    "BlockedEvaluationError",
    "InvalidTransitionError",
    "ContentExtractionError",
    "DuplicateEvidenceError",
    "IngestionError",
    "IntegrityValidationError",
    "LineageError",
    "UnsupportedFormatError",
    "ArchiveSafetyError",
    "EmptyExtractionError",
    "EncryptedContentError",
    "EvidenceAccessDeniedError",
    "EvidenceIneligibleError",
    "EvidenceIntegrityError",
    "HashMismatchError",
    "LineageConflictingParentError",
    "LineageContextMismatchError",
    "LineageCycleError",
    "LineageParentNotFoundError",
    "LineageVersionRegressionError",
    "ManualReviewRequiredError",
    "ReconstructionError",
    "ResourceLimitError",
    "StructuredLimitError",
    "TenantMismatchError",
    "TextLimitError",
    "ApprovalError",
    "CapabilityCycleError",
    "CapabilityNotFoundError",
    "ImmutableCapabilityError",
    "ImmutableRubricError",
    "InvalidLifecycleTransitionError",
    "OntologyError",
    "RubricError",
    "RubricNotFoundError",
    "RubricValidationError",
    "UnknownEvidenceTypeError",
    "UnknownReasonCodeError",
    "UnknownScoringScaleError",
    "AIObservationNotAllowedError",
    "AssessmentAlreadyFinalizedError",
    "AssessmentAuthorizationError",
    "AssessmentError",
    "AssessmentIncompleteError",
    "AssessmentNotFoundError",
    "AssessmentSupersededError",
    "AssessmentWorkspaceNotFoundError",
    "BlockingConflictError",
    "CapabilityVersionMismatchError",
    "CrossTenantAssessmentAccessError",
    "EvidenceBindingNotFoundError",
    "EvidenceNotEligibleForAssessmentError",
    "ObservationScaleMismatchError",
    "ObservationSupplierNotAuthorizedError",
    "ObservationValidationError",
    "ObservationValueOutOfRangeError",
    "PublishedRubricRequiredError",
    "QuarantinedEvidenceBindingError",
    "ReasonCodeNotPermittedError",
    "RequiredUncertaintyMissingError",
]
