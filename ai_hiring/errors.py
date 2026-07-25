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


class HiringError(Exception):
    """Base class for every AI-hiring domain error."""


# --- Validation ------------------------------------------------------------
class DomainValidationError(HiringError):
    """A domain contract invariant was violated."""


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


# --- Repository ------------------------------------------------------------
class RepositoryError(HiringError):
    """Base class for persistence-layer errors."""


class RecordNotFoundError(RepositoryError):
    """A referenced record does not exist."""


class VersionConflictError(RepositoryError):
    """An immutable record version already exists, or a stale version was saved."""


class DuplicateDecisionError(RepositoryError):
    """A binding decision already exists for this candidate/evaluation stage."""


class AppendOnlyViolationError(RepositoryError):
    """An attempt was made to mutate an append-only store."""


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
