"""Typed errors. A refusal that is part of the contract is a ``DecisionOutcome``, not
an exception; exceptions are for contract violations at the seams."""

from __future__ import annotations


class GovernedReviewServiceError(Exception):
    """Base class for this package's errors."""


class ContractViolation(GovernedReviewServiceError, ValueError):
    """A caller broke a structural rule of a service input."""


class ClockDisciplineError(GovernedReviewServiceError):
    """The injected clock returned something other than a tz-aware datetime."""
