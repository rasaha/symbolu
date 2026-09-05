"""Typed errors. Every one is a *refusal*; none is ever promoted to an approval."""

from __future__ import annotations


class ApprovalWorkflowError(Exception):
    """Base class for every error this package raises."""


class ContractViolation(ApprovalWorkflowError, ValueError):
    """A caller supplied structurally invalid input (naive datetime, blank id, wrong type)."""


class ApprovalNotFoundError(ApprovalWorkflowError, LookupError):
    """No approval exists for the given id."""


class ApprovalAlreadyExistsError(ApprovalWorkflowError):
    """A request would collide with an existing approval id.

    Raised rather than silently reusing the record: a standing decision must never
    be inherited by a second request.
    """


class IllegalTransitionError(ApprovalWorkflowError):
    """The requested transition is forbidden from the current state.

    Raised, never silently coerced: deciding a withdrawn request, re-deciding a
    terminal one, granting an exception that was never requested, and similar are
    refusals. Transitions are forward-only.
    """


class EligibilityRefused(ApprovalWorkflowError):
    """The presented approver may not decide this approval.

    Ineligible at the decision instant, an approver kind that may never approve, a
    missing role, or the requester presenting as the sole approver. The package
    decides *structure*; the port decides eligibility; neither authenticates.
    """


class ArtifactIntegrityError(ApprovalWorkflowError, ValueError):
    """A stored approval record does not re-derive its own artifact digest."""


class StoreUnavailableError(ApprovalWorkflowError):
    """The durable store cannot be reached. Callers fail closed and retry the same key."""


class ProductionModeRefused(ApprovalWorkflowError):
    """A reference-grade adapter was asked to run in production mode."""
