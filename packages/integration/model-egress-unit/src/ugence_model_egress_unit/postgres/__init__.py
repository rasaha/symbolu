"""PostgreSQL-backed exchange: schema names, deterministic migrations, the store.

Split from the package root so the record types, the canonicalization and the
providers stay importable without a database driver present. Only this subpackage
imports ``psycopg``.
"""

from __future__ import annotations

from .exchange import (
    ClaimedRequest,
    Exchange,
    ExchangeError,
    RequestNotClaimable,
    ResultNotAcknowledgeable,
    TenantMismatch,
    UnscopableConnection,
)
from .migrate import MigrationDrift, applied_versions, migrate
from .migrations import MIGRATIONS, Migration, migration_digest, statements
from .transport import (
    REQUIRED_SSLMODE,
    TransportUnprotected,
    protected_connect,
    require_transport_protection,
    sslmode_of,
)
from .provision import bind_identity, identity_name, identity_report, identity_statements
from .schema import (
    BINDING_TABLE,
    BUDGET_TABLE,
    MIGRATOR_ROLE,
    RESERVATION_TABLE,
    OWNER_ROLE,
    ROLE_NAMES,
    SCHEMA_NAME,
    TENANT_SETTING,
    UNIT_ROLE,
    WORKER_ROLE,
)

__all__ = [
    "REQUIRED_SSLMODE",
    "TransportUnprotected",
    "sslmode_of",
    "require_transport_protection",
    "protected_connect",
    "identity_name",
    "identity_statements",
    "bind_identity",
    "identity_report",
    "SCHEMA_NAME",
    "MIGRATOR_ROLE",
    "BINDING_TABLE",
    "BUDGET_TABLE",
    "RESERVATION_TABLE",
    "OWNER_ROLE",
    "WORKER_ROLE",
    "UNIT_ROLE",
    "ROLE_NAMES",
    "TENANT_SETTING",
    "Migration",
    "MIGRATIONS",
    "migration_digest",
    "statements",
    "migrate",
    "applied_versions",
    "MigrationDrift",
    "Exchange",
    "ClaimedRequest",
    "ExchangeError",
    "TenantMismatch",
    "RequestNotClaimable",
    "ResultNotAcknowledgeable",
    "UnscopableConnection",
]
