"""Typed domain errors for the AI-Assisted Hiring module.

Every failure mode in this module raises an explicit, typed exception derived
from :class:`HiringError`. None of these subclass ``ValueError``, so when they
are raised inside a pydantic validator they propagate as-is rather than being
wrapped into a ``pydantic.ValidationError`` — callers always receive the precise
domain error type.

Structural/type validation performed by pydantic itself (missing required
fields, wrong enum member, wrong scalar type) still raises
``pydantic.ValidationError``; business-invariant violations raise the errors
below.
"""

from __future__ import annotations

from decision_governance.api.errors import DomainValidationError, GovernanceError

# Phase 5A: the error base is now the kernel's ``GovernanceError``. ``HiringError``
# is kept as an alias so every existing ``class X(HiringError)`` and every
# ``isinstance(e, HiringError)`` continues to behave identically, while the neutral
# ``DomainValidationError`` raised by kernel contracts shares the same root.
HiringError = GovernanceError

__all__ = ["HiringError", "GovernanceError", "DomainValidationError"]


# --- Boundary / authorization ---------------------------------------------
class BoundaryViolationError(HiringError):
    """The AI/human decision boundary was violated.

    Raised when an AI or service principal attempts to author a binding
    decision or drive a binding workflow transition, or when a non-human actor
    is presented as a human decision-maker.
    """


class UnauthenticatedActorError(HiringError):
    """An actor could not be authenticated for the requested action."""


class OverrideRequiredError(HiringError):
    """A decision diverges from the AI recommendation without a recorded override."""


# --- Workflow --------------------------------------------------------------
class InvalidTransitionError(HiringError):
    """An illegal workflow state transition was requested."""


class BindingTransitionRequiresDecisionError(HiringError):
    """A binding transition was requested without a valid human decision."""


class BlockedEvaluationError(HiringError):
    """A REVIEW_BLOCKED evaluation was routed into review or decision."""


# --- Repository + Phase-4A/4B/4C error families: extracted to the DGM kernel
# in Phase 5B; re-exported here so ai_hiring.errors keeps the same objects.
from decision_governance.api.errors import (  # noqa: F401,E402
    AIDecisionAuthorityError,
    ActionMappingNotFoundError,
    ActionMappingNotPublishedError,
    ActionParameterValidationError,
    ActionRequestAlreadyAuthorizedError,
    ActionRequestAuthorizationError,
    ActionRequestError,
    ActionRequestNotExecutableError,
    ActionRequestNotFoundError,
    ActionRequestNotReadyError,
    ActionRequestSupersededError,
    ActionTypeMismatchError,
    AppendOnlyViolationError,
    AssessmentNotLinkableError,
    AuthorizationExpiredError,
    AuthorizationNotExecutableError,
    AuthorizationResponseMismatchError,
    AuthorizationSubmissionError,
    CERBindingError,
    CERExpiredError,
    CERExpiredForExecutionError,
    CaseFinalizedError,
    CaseVersionNotFoundError,
    CompensationNotFoundError,
    CompensationRequiredError,
    CrossTenantActionRequestError,
    CrossTenantCaseAccessError,
    CrossTenantExecutionError,
    DecisionAuthorityError,
    DecisionCaseAuthorizationError,
    DecisionCaseError,
    DecisionCaseNotFoundError,
    DecisionNotActionableError,
    DecisionReadinessError,
    DecisionSupersededError,
    DelegatedPolicyScopeError,
    DuplicateActionRequestError,
    DuplicateDecisionError,
    DuplicateExternalExecutionError,
    ExecutionAttemptNotFoundError,
    ExecutionAuthorizationError,
    ExecutionError,
    ExecutionIdempotencyConflictError,
    ExecutionIntentNotFoundError,
    ExecutionMismatchError,
    ExecutionOutcomeUnknownError,
    ExecutionParameterMismatchError,
    ExecutionRecordNotFoundError,
    ExecutionTargetMismatchError,
    ExternalDispatchError,
    ExternalRequestMismatchError,
    InvalidActionRequestTransitionError,
    InvalidCaseTransitionError,
    InvalidExecutionTransitionError,
    MalformedExternalResponseError,
    ProhibitedActionParameterError,
    RecommendationNotFoundError,
    RecommendationValidationError,
    ReconciliationIncompleteError,
    RecordNotFoundError,
    RepositoryError,
    RequiredReviewIncompleteError,
    ReviewTaskNotFoundError,
    SegregationOfDutiesError,
    TargetSystemNotPermittedError,
    UnauthorizedOverrideError,
    UnsafeRetryError,
    VersionConflictError,
)

# --- Phase 2: evidence ingestion & normalization ---------------------------
class IngestionError(HiringError):
    """Base class for evidence-ingestion errors."""


class IntegrityValidationError(IngestionError):
    """A raw submission failed integrity validation (empty, oversized, corrupt)."""


class UnsupportedFormatError(IngestionError):
    """No parser is registered for the declared evidence format."""


class ContentExtractionError(IngestionError):
    """Content could not be extracted from a submission (e.g. undecodable bytes)."""


class DuplicateEvidenceError(IngestionError):
    """Identical raw content already exists for this candidate/assessment stage."""


class LineageError(HiringError):
    """A lineage graph could not be constructed or reconstructed."""


# --- Phase 2.5: evidence boundary hardening --------------------------------
class ResourceLimitError(IngestionError):
    """A configured resource-consumption limit was exceeded."""


class ArchiveSafetyError(IngestionError):
    """An archive (e.g. DOCX/ZIP) failed a safety check (bomb, traversal, ...)."""


class StructuredLimitError(ResourceLimitError):
    """A structured document (JSON/CSV) exceeded a complexity limit."""


class TextLimitError(ResourceLimitError):
    """A text/source submission exceeded a size/shape limit."""


class EmptyExtractionError(IngestionError):
    """Extraction produced no usable content; evidence fails closed."""


class EncryptedContentError(IngestionError):
    """The submission appears encrypted and cannot be extracted."""


class ManualReviewRequiredError(IngestionError):
    """Extraction outcome is ambiguous and must be routed for human review."""


class EvidenceIntegrityError(HiringError):
    """Base class for integrity (hash / reconstruction) failures."""


class HashMismatchError(EvidenceIntegrityError):
    """A raw or normalized hash did not match its expected value."""


class ReconstructionError(EvidenceIntegrityError):
    """Chunks failed to reconstruct the normalized content exactly."""


class EvidenceIneligibleError(HiringError):
    """Evidence does not satisfy the fail-closed evaluation-eligibility policy."""


class EvidenceAccessDeniedError(HiringError):
    """An authorization check denied access to evidence or search."""


class TenantMismatchError(HiringError):
    """A cross-tenant (or cross-application) scope violation was detected."""


# Lineage integrity (subclasses of LineageError)
class LineageCycleError(LineageError):
    """A lineage edge would introduce a cycle."""


class LineageParentNotFoundError(LineageError):
    """A referenced parent lineage node does not exist."""


class LineageContextMismatchError(LineageError):
    """A lineage edge crosses tenant/candidate/application context."""


class LineageVersionRegressionError(LineageError):
    """A lineage edge regresses or breaks monotonic version ancestry."""


class LineageConflictingParentError(LineageError):
    """A version node has conflicting immediate predecessors."""


# --- Phase 3A: capability ontology & rubric contracts ----------------------
class OntologyError(HiringError):
    """Base class for capability-ontology errors."""


class CapabilityNotFoundError(OntologyError):
    """A referenced capability (or version) does not exist."""


class ImmutableCapabilityError(OntologyError):
    """An attempt was made to overwrite a published, immutable capability."""


class CapabilityCycleError(OntologyError):
    """The capability hierarchy would contain a cycle."""


class RubricError(HiringError):
    """Base class for rubric-contract errors."""


class RubricNotFoundError(RubricError):
    """A referenced rubric (or version) does not exist."""


class RubricValidationError(RubricError):
    """A rubric failed contract validation."""


class InvalidLifecycleTransitionError(RubricError):
    """An illegal rubric (or capability) lifecycle transition was requested."""


class ImmutableRubricError(RubricError):
    """An attempt was made to mutate a published, immutable rubric."""


class ApprovalError(RubricError):
    """An approval-workflow rule was violated (e.g. segregation of duties)."""


class UnknownReasonCodeError(RubricError):
    """A rubric referenced a reason code outside the frozen taxonomy."""


class UnknownScoringScaleError(RubricError):
    """A rubric referenced an unknown scoring scale."""


class UnknownEvidenceTypeError(RubricError):
    """A rubric or capability referenced an unknown evidence type."""


# --- Phase 3B: deterministic assessment runtime ----------------------------
class AssessmentError(HiringError):
    """Base class for deterministic-assessment-runtime errors."""


class AssessmentWorkspaceNotFoundError(AssessmentError):
    """A referenced assessment workspace does not exist."""


class AssessmentNotFoundError(AssessmentError):
    """A referenced assessment does not exist."""


class AssessmentAlreadyFinalizedError(AssessmentError):
    """An operation was attempted on a finalized (immutable) assessment."""


class AssessmentSupersededError(AssessmentError):
    """An operation was attempted on a superseded assessment/workspace."""


class PublishedRubricRequiredError(AssessmentError):
    """A workspace requires a PUBLISHED rubric; none was found."""


class CapabilityVersionMismatchError(AssessmentError):
    """A rubric-referenced capability version does not match the ontology."""


class EvidenceBindingNotFoundError(AssessmentError):
    """A referenced evidence binding does not exist."""


class EvidenceNotEligibleForAssessmentError(AssessmentError):
    """Evidence failed the fail-closed eligibility check for assessment use."""


class QuarantinedEvidenceBindingError(AssessmentError):
    """An attempt was made to bind quarantined / non-job-relevant evidence."""


class ObservationValidationError(AssessmentError):
    """A supplied observation failed deterministic validation."""


class ObservationScaleMismatchError(ObservationValidationError):
    """A supplied observation's declared scale does not match the rubric."""


class ObservationValueOutOfRangeError(ObservationValidationError):
    """A supplied observation value is not a member of its declared scale."""


class ObservationSupplierNotAuthorizedError(ObservationValidationError):
    """The observation supplier is not authorized for this criterion."""


class AIObservationNotAllowedError(ObservationValidationError):
    """An AI-supplied observation was rejected — Phase 3B forbids inference."""


class ReasonCodeNotPermittedError(AssessmentError):
    """A reason code is unknown or not permitted for this criterion/rubric."""


class RequiredUncertaintyMissingError(AssessmentError):
    """The published contract requires uncertainty that was not supplied."""


class BlockingConflictError(AssessmentError):
    """An unresolved conflict blocks assessment finalization per contract."""


class AssessmentIncompleteError(AssessmentError):
    """Assessment cannot be finalized because it is structurally incomplete."""


class AssessmentAuthorizationError(AssessmentError):
    """The actor is not authorized for the requested assessment operation."""


class CrossTenantAssessmentAccessError(AssessmentAuthorizationError):
    """A cross-tenant assessment access was attempted and denied."""


# --- H1 hiring product entities (requisition / job def / candidate / application
#     / evidence intake). Application-local, additive. -----------------------
class HiringProductError(HiringError):
    """Base for H1 candidate-facing hiring product errors."""


class RequisitionNotFoundError(HiringProductError):
    """No requisition exists for the given id (or not in the caller's tenant)."""


class JobDefinitionNotFoundError(HiringProductError):
    """No job definition exists for the given id (or not in the caller's tenant)."""


class CandidateNotFoundError(HiringProductError):
    """No candidate exists for the given id (or not in the caller's tenant)."""


class ApplicationNotFoundError(HiringProductError):
    """No application exists for the given id (or not in the caller's tenant)."""


class EvidenceIntakeNotFoundError(HiringProductError):
    """No evidence-intake item exists for the given id (or not in tenant)."""


class IllegalRequisitionTransitionError(InvalidTransitionError):
    """An illegal requisition lifecycle transition was requested."""


class IllegalJobDefinitionTransitionError(InvalidTransitionError):
    """An illegal job-definition lifecycle transition was requested."""


class IllegalCandidateTransitionError(InvalidTransitionError):
    """An illegal candidate lifecycle transition was requested."""


class IllegalApplicationTransitionError(InvalidTransitionError):
    """An illegal application lifecycle transition was requested."""


class DuplicateApplicationError(HiringProductError):
    """An active application already exists for this candidate + requisition."""


class IneligibleApplicationError(HiringProductError):
    """The structural eligibility preconditions for the application do not hold."""


class NotReadyForAssessmentError(HiringProductError):
    """Required evidence is incomplete; the application cannot advance to ASSESSMENT."""


class CrossTenantHiringAccessError(TenantMismatchError):
    """A cross-tenant hiring product access was attempted and denied."""


