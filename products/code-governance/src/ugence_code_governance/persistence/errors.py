"""Typed errors for the durable shadow store.

Every failure fails closed with a structured, typed error. There is no silent
destructive behavior.
"""
from __future__ import annotations

from ..errors import PersistenceError


class DurableStoreError(PersistenceError):
    """Base for durable shadow-store failures."""


class SchemaError(DurableStoreError):
    """Store schema is missing, malformed, or an unsupported version."""


class SchemaIncompatibleError(SchemaError):
    """The store's schema version is not supported by this application version."""


class IntegrityFailure(DurableStoreError):
    """A recomputed fingerprint or binding did not match what was stored."""


class RecordCollisionError(DurableStoreError):
    """Same record id with a different payload (append-only violation)."""


class ImmutableViolationError(DurableStoreError):
    """An attempt to mutate or delete an immutable historical record."""


class EventChainError(DurableStoreError):
    """The workflow-event journal is broken, mis-linked, or out of order."""


class TenantIsolationError(DurableStoreError):
    """A cross-tenant read/linkage was attempted and refused."""


class ProhibitedFieldError(DurableStoreError):
    """A payload contained a prohibited (credential/PII) field."""


class ReferenceMissingError(DurableStoreError):
    """A referenced record could not be found in the store."""


class TransactionAbortedError(DurableStoreError):
    """A stage transaction was rolled back; no partial state is visible."""


class InjectedFailure(DurableStoreError):
    """Deterministic failure injected at a transaction boundary (tests only)."""


__all__ = [
    "DurableStoreError",
    "SchemaError",
    "SchemaIncompatibleError",
    "IntegrityFailure",
    "RecordCollisionError",
    "ImmutableViolationError",
    "EventChainError",
    "TenantIsolationError",
    "ProhibitedFieldError",
    "ReferenceMissingError",
    "TransactionAbortedError",
    "InjectedFailure",
]
