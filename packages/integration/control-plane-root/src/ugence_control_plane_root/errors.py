"""Typed errors. Every one is a *refusal*; none is ever promoted to an action."""

from __future__ import annotations

__all__ = [
    "ControlPlaneRootError", "ContractViolation", "LedgerIntegrityError",
    "SchemaVersionMismatch",
]


class ControlPlaneRootError(Exception):
    """Base class for every error this package raises."""


class ContractViolation(ControlPlaneRootError, ValueError):
    """Structurally invalid input: a blank id, a naive datetime, a wrong type."""


class LedgerIntegrityError(ControlPlaneRootError):
    """The hash chain does not verify, or an append would break it.

    Tamper-**evident**, never tamper-proof: this says a chain no longer agrees
    with itself, not that nobody could have changed it.
    """


class SchemaVersionMismatch(ControlPlaneRootError):
    """The store was written at a schema version this package does not write.

    Refused rather than migrated. A root that silently migrated somebody's audit
    store would be doing the one thing an append-only ledger must never do.
    """
