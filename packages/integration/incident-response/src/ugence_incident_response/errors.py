"""Typed errors. Every one is a *refusal*; none is ever promoted to an action."""

from __future__ import annotations


class IncidentResponseError(Exception):
    """Base class for every error this package raises."""


class ContractViolation(IncidentResponseError, ValueError):
    """A caller supplied structurally invalid input (naive datetime, blank id, wrong type)."""


class IllegalTransitionError(IncidentResponseError):
    """The requested incident transition is forbidden from the current state.

    Raised, never silently coerced. Closing an incident twice, or reopening a
    closed one, are refusals.
    """


class ContainmentLiftRefused(IncidentResponseError):
    """A containment lift was inadmissible.

    Lifting containment is a separate decision, recorded on its own: it may not
    follow automatically from an incident closing, and it may not be inferred.
    """
