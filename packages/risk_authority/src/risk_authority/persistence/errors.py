"""Typed persistence errors. Every one is a :class:`RiskAuthorityError`."""

from __future__ import annotations

from ..domain.errors import RiskAuthorityError

__all__ = [
    "PersistenceStorageError",
    "PersistenceConflictError",
    "PersistenceProductionModeError",
]


class PersistenceStorageError(RiskAuthorityError):
    """The store could not read, write or decode a record; nothing was guessed."""


class PersistenceConflictError(PersistenceStorageError):
    """A record already exists under this id (ADR durable persistence, D-3)."""


class PersistenceProductionModeError(RiskAuthorityError):
    """Production mode was asked to stand on a store that never declared itself durable."""
