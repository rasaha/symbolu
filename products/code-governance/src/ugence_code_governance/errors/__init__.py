"""Product-owned error taxonomy for Code Governance.

These errors are raised by the product boundary only. They never leak upstream
capability exceptions unchanged; adapters translate as needed. Every error is a
subclass of :class:`CodeGovernanceError` so callers can trap the product cleanly.
"""
from __future__ import annotations


class CodeGovernanceError(Exception):
    """Base class for every Code Governance product error."""


# --- ingestion -----------------------------------------------------------
class IngestionError(CodeGovernanceError):
    """Base for GitHub read-only ingestion failures."""


class MalformedEventError(IngestionError):
    """A webhook/fixture payload is missing required fields or is ill-formed."""


class UnsupportedEventError(IngestionError):
    """A syntactically valid event whose action is not handled in this phase."""


class TenantMismatchError(IngestionError):
    """An event resolves to a tenant other than the one the caller scoped."""


class SignatureVerificationError(IngestionError):
    """HMAC signature verification failed for a supplied secret + signature."""


# --- evidence / claims ---------------------------------------------------
class EvidenceError(CodeGovernanceError):
    """Base for evidence-record failures."""


class ContentDigestMismatchError(EvidenceError):
    """A record's declared content digest does not match its normalized payload."""


class StaleEvidenceError(EvidenceError):
    """Evidence is bound to a head SHA other than the current governed head."""


class EvidenceNotFoundError(EvidenceError):
    """No evidence record exists for the requested reference (and tenant)."""


class ClaimError(CodeGovernanceError):
    """Base for claim-manifest failures."""


# --- decision authority boundary ----------------------------------------
class DecisionAuthorityRequiredError(CodeGovernanceError):
    """A binding decision was requested without an explicit authorized actor.

    The Workflow Service owns coordination, never authority. The
    decision-recording stage fails closed when no authorized actor is supplied.
    """


# --- workflow ------------------------------------------------------------
class WorkflowError(CodeGovernanceError):
    """Base for Workflow Service failures."""


class InvalidWorkflowTransitionError(WorkflowError):
    """A stage was requested from a state that does not permit it (fail closed)."""


class ChainIncompleteError(WorkflowError):
    """A required governance-chain link is absent; the chain fails closed."""


# --- persistence ---------------------------------------------------------
class PersistenceError(CodeGovernanceError):
    """Base for repository failures."""


class RecordNotFoundError(PersistenceError):
    """A referenced record could not be loaded from its repository."""


class CrossTenantAccessError(PersistenceError):
    """A lookup crossed a tenant boundary and was refused."""


class ImmutableRecordError(PersistenceError):
    """An attempt to overwrite an existing immutable revision was refused."""


__all__ = [
    "CodeGovernanceError",
    "IngestionError",
    "MalformedEventError",
    "UnsupportedEventError",
    "TenantMismatchError",
    "SignatureVerificationError",
    "EvidenceError",
    "ContentDigestMismatchError",
    "StaleEvidenceError",
    "EvidenceNotFoundError",
    "ClaimError",
    "DecisionAuthorityRequiredError",
    "WorkflowError",
    "InvalidWorkflowTransitionError",
    "ChainIncompleteError",
    "PersistenceError",
    "RecordNotFoundError",
    "CrossTenantAccessError",
    "ImmutableRecordError",
]
