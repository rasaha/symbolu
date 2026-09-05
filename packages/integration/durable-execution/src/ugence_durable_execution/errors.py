"""Typed failures. Every one of them is a refusal, never a downgrade.

Nothing in this package converts a failure into permission, a partial result, or a
best-effort continuation. A store that cannot verify what it read raises; an adapter
that cannot establish identity raises; a composition root misconfigured for production
raises at construction rather than at the first consequential call.
"""
from __future__ import annotations

__all__ = [
    "DurableExecutionError",
    "ClockDisciplineError",
    "PostureError",
    "CheckpointIntegrityError",
    "UnrecoverableInstanceError",
    "DefinitionVersionMismatch",
    "BudgetExhausted",
    "InstanceIdentityError",
]


class DurableExecutionError(Exception):
    """Base for every failure raised by this package."""


class ClockDisciplineError(DurableExecutionError):
    """A durable deployment was configured with a process-local clock (ADR §6.4).

    ``time.monotonic()`` has an arbitrary per-process origin, so a ``valid_until``
    minted before a crash and compared after it is compared against an unrelated
    number — the comparison can read as *not yet expired* for an arbitrarily long
    outage. Refused at construction.
    """


class PostureError(DurableExecutionError):
    """A production composition root was handed a bundle that is not durable and
    integrity-checked (``is_production_authoritative`` is False)."""


class CheckpointIntegrityError(DurableExecutionError):
    """A persisted checkpoint failed ``verify()``, ``verify_extension()`` or
    ``validate_execution_states()``.

    Never repaired and never skipped: the row is surfaced and the instance is left
    unrecoverable (ADR §8 row 7).
    """


class UnrecoverableInstanceError(DurableExecutionError):
    """Recovery was attempted on an instance whose durable state cannot be trusted."""


class DefinitionVersionMismatch(DurableExecutionError):
    """An instance started under one ``definition_digest`` was offered another.

    Refuse, do not reinterpret (ADR §8 row 10). Carries both digests so an operator
    can see exactly what changed.
    """

    def __init__(self, instance_id: str, started_with: str, offered: str) -> None:
        super().__init__(
            f"instance {instance_id!r} was started under definition_digest "
            f"{started_with!r} and cannot be recovered under {offered!r}; "
            "refusing rather than reinterpreting persisted state under new semantics"
        )
        self.instance_id = instance_id
        self.started_with = started_with
        self.offered = offered


class BudgetExhausted(DurableExecutionError):
    """A budget reservation was refused because the ledger is at its ceiling.

    Fail closed: the caller does not invoke (ADR §8 row 8).
    """


class InstanceIdentityError(DurableExecutionError):
    """A duplicate ``start`` was attempted with conflicting identifying fields."""
