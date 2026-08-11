"""Production Postgres-backed authority store (skeleton + DDL reference).

The RA-6 status runtime ships a deterministic **reference** in-memory store
(:mod:`.store`) for conformance and tests. Production persistence is delegated
here and completes the DDL already reserved by the Risk Authority leaf
(``revocations(tenant_id, kind, target_id, epoch, created_at)`` plus a
tenant-epoch row) — see ``risk_authority/persistence/postgres.py``.

This class **raises clearly** rather than silently degrading, so a reference
adapter is never mistaken for production persistence (RA-6 §18; no-false-claims
§22). It records the authoritative target schema for the production adapter to
build against.

Target tables (all tenant-scoped; strong consistency, serialized-per-tenant,
monotonic writes for authority-changing operations):

    authority_epochs(tenant_id PK, epoch, updated_at)
    authority_epoch_changes(tenant_id, change_id, applied_at,
        PRIMARY KEY(tenant_id, change_id))            -- advance_epoch idempotency
    revocations(tenant_id, kind, target_id, epoch, created_at,
        PRIMARY KEY(tenant_id, kind, target_id))      -- grow-only union
    authority_lifecycle_events(event_id PK, tenant_id, event_type, actor,
        target_kind, target_id, reason, correlation_id, idempotency_key,
        epoch, timestamp)                              -- append-only audit

Convergence for multi-writer/replicated deployments: ``epoch = max(epoch)`` and a
grow-only revocation-set union (RA-6 §4.1) — never an epoch rollback.
"""

from __future__ import annotations

__all__ = ["PostgresNotConfiguredError", "PostgresAuthorityStoreFactory"]


class PostgresNotConfiguredError(NotImplementedError):
    """Raised when the production Postgres store is used before wiring."""


class PostgresAuthorityStoreFactory:
    """Placeholder factory for the production Postgres-backed authority store."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _unavailable(self) -> "PostgresNotConfiguredError":
        return PostgresNotConfiguredError(
            "Postgres authority persistence is a production skeleton; use the "
            "ReferenceAuthorityStore for conformance/tests. See this module's "
            "docstring for the target DDL."
        )

    def authority_store(self):  # noqa: ANN201 - factory stub
        raise self._unavailable()
