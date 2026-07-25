"""Base error types for the Decision Governance kernel.

Every kernel failure derives from :class:`GovernanceError`. None of these
subclass ``ValueError``, so when raised inside a pydantic validator they
propagate as-is rather than being wrapped into a ``pydantic.ValidationError`` —
callers always receive the precise domain error type.

Consuming applications may alias :class:`GovernanceError` to a domain-specific
base and add their own typed error families; doing so preserves ``isinstance``
across the whole hierarchy.
"""

from __future__ import annotations


class GovernanceError(Exception):
    """Base class for every Decision Governance kernel error."""


class DomainValidationError(GovernanceError):
    """A governance contract invariant was violated."""
