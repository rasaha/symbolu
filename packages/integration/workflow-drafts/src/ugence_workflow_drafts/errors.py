"""Typed errors. Every one is a *refusal*; none is ever promoted to a permission."""

from __future__ import annotations


class WorkflowDraftsError(Exception):
    """Base class for every error this package raises."""


class ContractViolation(WorkflowDraftsError, ValueError):
    """A caller supplied structurally invalid input (blank id, wrong type, a document
    over the size limit, a digest that does not match its document)."""


class DraftSupersessionError(WorkflowDraftsError, ValueError):
    """A superseding draft is inadmissible.

    It names no recorded predecessor, crosses a tenant, names a predecessor that is
    already superseded (lineage is linear), or changes nothing.
    """


class DuplicateDraftError(WorkflowDraftsError, ValueError):
    """A draft with this derived id is already recorded; records are never edited."""


class CrossTenantRefused(WorkflowDraftsError, ValueError):
    """A read or write named a tenant other than the one this store is bound to."""


class DraftStorageError(WorkflowDraftsError, RuntimeError):
    """The durable store could not be opened, read or written."""


class DraftProductionModeError(DraftStorageError):
    """A non-durable location (in memory, a URI) was refused in production mode."""
