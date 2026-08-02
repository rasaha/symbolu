"""Typed, fail-closed errors and failure codes for read-only enterprise adapters.

Every adapter failure is structured. A source failure is NEVER silently turned
into a positive signal — it fails closed with a typed failure code that product
policy can map to HOLD / BLOCK / ESCALATE (never to CLEAR).
"""
from __future__ import annotations

from enum import Enum

from ..errors import CodeGovernanceError


class AdapterError(CodeGovernanceError):
    """Base for read-only adapter failures."""


class ReadOnlyBoundaryViolation(AdapterError):
    """A non-read (mutating) operation or unapproved target was attempted."""


class AdapterConfigurationError(AdapterError):
    """An adapter/source was not registered, or its version is unapproved."""


class AdapterResponseError(AdapterError):
    """A source response was too large, malformed, or an unexpected content type."""


class ArtifactIdentityMismatch(AdapterError):
    """The source's returned artifact identity did not match the governed change."""


class CredentialLeakError(AdapterError):
    """A credential-like value was about to cross a prohibited boundary."""


class AdapterFailureCode(str, Enum):
    """Structured source-failure classes (never a positive signal)."""

    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_TIMEOUT = "SOURCE_TIMEOUT"
    SOURCE_RATE_LIMITED = "SOURCE_RATE_LIMITED"
    SOURCE_UNAUTHORIZED = "SOURCE_UNAUTHORIZED"
    SOURCE_FORBIDDEN = "SOURCE_FORBIDDEN"
    SOURCE_RESPONSE_TOO_LARGE = "SOURCE_RESPONSE_TOO_LARGE"
    SOURCE_SCHEMA_INVALID = "SOURCE_SCHEMA_INVALID"
    SOURCE_IDENTITY_MISMATCH = "SOURCE_IDENTITY_MISMATCH"
    ARTIFACT_IDENTITY_MISMATCH = "ARTIFACT_IDENTITY_MISMATCH"
    SOURCE_DATA_STALE = "SOURCE_DATA_STALE"
    SOURCE_DATA_CONFLICT = "SOURCE_DATA_CONFLICT"
    READ_ONLY_BOUNDARY_VIOLATION = "READ_ONLY_BOUNDARY_VIOLATION"
    ADAPTER_VERSION_UNAPPROVED = "ADAPTER_VERSION_UNAPPROVED"
    SOURCE_NOT_REGISTERED = "SOURCE_NOT_REGISTERED"
    UNEXPECTED_CONTENT_TYPE = "UNEXPECTED_CONTENT_TYPE"


#: Failure codes that must never be retried (deterministic, not transient).
NON_RETRYABLE_FAILURES = frozenset({
    AdapterFailureCode.SOURCE_SCHEMA_INVALID,
    AdapterFailureCode.SOURCE_IDENTITY_MISMATCH,
    AdapterFailureCode.ARTIFACT_IDENTITY_MISMATCH,
    AdapterFailureCode.READ_ONLY_BOUNDARY_VIOLATION,
    AdapterFailureCode.ADAPTER_VERSION_UNAPPROVED,
    AdapterFailureCode.SOURCE_NOT_REGISTERED,
    AdapterFailureCode.SOURCE_UNAUTHORIZED,
    AdapterFailureCode.SOURCE_FORBIDDEN,
    AdapterFailureCode.UNEXPECTED_CONTENT_TYPE,
    AdapterFailureCode.SOURCE_RESPONSE_TOO_LARGE,
})


__all__ = [
    "AdapterError",
    "ReadOnlyBoundaryViolation",
    "AdapterConfigurationError",
    "AdapterResponseError",
    "ArtifactIdentityMismatch",
    "CredentialLeakError",
    "AdapterFailureCode",
    "NON_RETRYABLE_FAILURES",
]
