"""Errors raised by this package.

The validation surface does NOT raise. A malformed artifact is a *result*
(``INVALID``/``INDETERMINATE``), not an exception, because callers must be able to
collect and compare outcomes deterministically without exception control flow.

These exceptions are for programmer errors — a caller asking this package a
question it structurally cannot answer.
"""

from __future__ import annotations


class AgentConstitutionContractError(Exception):
    """Base class for every error this package raises."""


class UnknownArtifactKind(AgentConstitutionContractError):
    """Raised when a validation request names an artifact kind that does not exist.

    Distinct from an unrecognized *schema version* of a known kind: that is data
    the package can be asked about and answers INDETERMINATE. An unknown *kind* is
    a caller bug, because the kind set is a closed constant of this build.
    """


class MalformedVersionError(AgentConstitutionContractError, ValueError):
    """Raised when a string is compared as a semantic version but is not one."""


class DigestScopeError(AgentConstitutionContractError):
    """Raised when a digest is requested for a value with no computable scope."""


__all__ = [
    "AgentConstitutionContractError",
    "UnknownArtifactKind",
    "MalformedVersionError",
    "DigestScopeError",
]
