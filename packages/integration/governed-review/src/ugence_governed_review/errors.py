"""Typed errors. Every one is a refusal or a contract violation, never a permit."""

from __future__ import annotations


class GovernedReviewError(Exception):
    """Base class."""


class ContractViolation(GovernedReviewError):
    """A caller supplied something the binding contract does not accept."""


class ClockDisciplineError(ContractViolation):
    """The injected clock returned something other than a timezone-aware datetime."""
