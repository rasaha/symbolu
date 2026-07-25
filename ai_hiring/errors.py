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
