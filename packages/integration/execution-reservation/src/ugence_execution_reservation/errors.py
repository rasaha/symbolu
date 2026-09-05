"""Typed errors. Every one is a *refusal*; none is ever promoted to a permission."""

from __future__ import annotations


class ExecutionReservationError(Exception):
    """Base class for every error this package raises."""


class ContractViolation(ExecutionReservationError, ValueError):
    """A caller supplied structurally invalid input (naive datetime, blank id, wrong type)."""


class ReceiptIntegrityError(ExecutionReservationError, ValueError):
    """A receipt body does not re-derive its own result fingerprint / receipt id."""


class ReceiptNotFoundError(ExecutionReservationError, LookupError):
    """No receipt exists for the given id."""


class ReservationNotFoundError(ExecutionReservationError, LookupError):
    """No reservation exists for the given id."""


class IllegalTransitionError(ExecutionReservationError):
    """The requested reservation transition is forbidden from the current state.

    Raised, never silently coerced: releasing a DISPATCHED or OUTCOME_UNCERTAIN
    reservation, observing a never-dispatched one, and similar are refusals.
    """


class StoreUnavailableError(ExecutionReservationError):
    """The durable store cannot be reached. Callers fail closed and retry the same key."""


class ProductionModeRefused(ExecutionReservationError):
    """A reference-grade adapter was asked to run in production mode."""
