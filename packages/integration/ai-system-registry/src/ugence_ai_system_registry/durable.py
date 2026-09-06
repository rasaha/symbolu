"""The one durable home of registrations (front-door ruling FD-9.2).

    THIS STORE RECORDS AND READS. IT NEVER ADMITS, GATES, PROMOTES, ATTESTS,
    EDITS OR DELETES. ITS ONLY WRITE IS ``register``.

``SqliteSystemRegistry`` implements the read-only :class:`SystemRegistryPort` over a
sqlite file in the seam-1 posture: a plain file path under a writable volume, no
server, no driver, no DSN, no network. It is bound to exactly one tenant at
construction; a read or write naming any other tenant is a typed refusal, never an
empty answer. Records are append-only: a registration is never edited, a changed
system is a new registration that ``supersedes`` its predecessor, and the
supersession is admitted only by :func:`supersession_refusals` (D-3).

No clock is read here. Every ``as_of`` is the caller's instant, exactly as the pure
selectors take it, so a lapsed registration is absent from an answer without a
sweeper. D-5 stands: this store reaches no system of record; it is the local file the
composing deployment owns.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import List, Optional

from ._canon import require_nonempty
from .errors import (
    ContractViolation,
    CrossTenantRefused,
    DuplicateRegistrationError,
    RegistryProductionModeError,
    RegistryStorageError,
)
from .registration import (
    SystemRegistration,
    registration_from_record,
    registration_record,
    require_admissible_supersession,
)
from .registry import (
    registered_at,
    select_by_classification,
    select_for_system,
    select_for_tenant,
)

__all__ = ["SqliteSystemRegistry", "SCHEMA_VERSION"]

SCHEMA_VERSION = "ai_system_registry.sqlite.v1"

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS registrations ("
    " seq INTEGER PRIMARY KEY AUTOINCREMENT,"
    " registration_id TEXT NOT NULL UNIQUE,"
    " tenant_id TEXT NOT NULL,"
    " system_id TEXT NOT NULL,"
    " system_version TEXT NOT NULL,"
    " classification_label TEXT NOT NULL,"
    " supersedes TEXT NOT NULL,"
    " record_digest TEXT NOT NULL,"
    " record_json TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS registrations_tenant ON registrations(tenant_id)",
    "CREATE TABLE IF NOT EXISTS registry_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
)


def _is_non_durable(path: str) -> bool:
    return path == ":memory:" or path.startswith("file:")


class SqliteSystemRegistry:
    """A tenant-bound, append-only sqlite registry satisfying :class:`SystemRegistryPort`."""

    kind = "SqliteSystemRegistry"

    def __init__(self, path: str, *, tenant_id: str, production_mode: bool = False,
                 busy_timeout_ms: int = 5000) -> None:
        self.tenant_id = require_nonempty(tenant_id, "SqliteSystemRegistry.tenant_id")
        self.path = require_nonempty(path, "SqliteSystemRegistry.path")
        self.production_mode = bool(production_mode)
        if self.production_mode and _is_non_durable(self.path):
            raise RegistryProductionModeError(
                "a durable file path is required in production mode; an in-memory or URI "
                "registry is refused")
        self._lock = threading.Lock()
        try:
            self._conn: Optional[sqlite3.Connection] = sqlite3.connect(
                self.path, check_same_thread=False, isolation_level=None)
            self._conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
            if not _is_non_durable(self.path):
                self._conn.execute("PRAGMA journal_mode=WAL")
            for statement in _SCHEMA:
                self._conn.execute(statement)
            self._conn.execute(
                "INSERT OR IGNORE INTO registry_meta(key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,))
            self._conn.execute(
                "INSERT OR IGNORE INTO registry_meta(key, value) VALUES ('tenant_id', ?)",
                (self.tenant_id,))
            bound = self._conn.execute(
                "SELECT value FROM registry_meta WHERE key = 'tenant_id'").fetchone()[0]
            if bound != self.tenant_id:
                self._conn.close()
                self._conn = None
                raise CrossTenantRefused(
                    "this registry file is bound to another tenant; a registry is never "
                    "re-bound")
        except sqlite3.Error as exc:
            raise RegistryStorageError(f"cannot open the registry: {exc}") from exc

    # ------------------------------------------------------------------ #
    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RegistryStorageError("the registry is closed")
        return self._conn

    def _require_tenant(self, tenant_id: str) -> None:
        if tenant_id != self.tenant_id:
            raise CrossTenantRefused(
                f"this registry is bound to one tenant; a read or write for tenant "
                f"{tenant_id!r} is refused")

    def _rows(self) -> List[SystemRegistration]:
        try:
            cursor = self._db().execute(
                "SELECT record_json, record_digest FROM registrations WHERE tenant_id = ? "
                "ORDER BY seq", (self.tenant_id,))
            rows = cursor.fetchall()
        except sqlite3.Error as exc:
            raise RegistryStorageError(f"cannot read the registry: {exc}") from exc
        out: List[SystemRegistration] = []
        for record_json, stored_digest in rows:
            registration = registration_from_record(json.loads(record_json))
            if registration.record_digest() != stored_digest:
                raise ContractViolation(
                    f"registration {registration.registration_id} does not match its recorded "
                    "digest; the record was altered outside this package")
            out.append(registration)
        return out

    # -- the one write ----------------------------------------------------- #
    def register(self, registration: SystemRegistration) -> SystemRegistration:
        """Append one registration. Refuses a foreign tenant, a duplicate derived id and
        an inadmissible supersession (D-3); never edits or deletes."""
        if not isinstance(registration, SystemRegistration):
            raise ContractViolation("register takes a SystemRegistration")
        self._require_tenant(registration.tenant_id)
        with self._lock:
            existing = {r.registration_id: r for r in self._rows()}
            if registration.registration_id in existing:
                raise DuplicateRegistrationError(
                    f"registration {registration.registration_id} is already recorded; "
                    "records are never edited")
            predecessor = existing.get(registration.supersedes) if registration.supersedes else None
            require_admissible_supersession(registration, predecessor)
            record = registration_record(registration)
            try:
                self._db().execute(
                    "INSERT INTO registrations(registration_id, tenant_id, system_id, "
                    "system_version, classification_label, supersedes, record_digest, record_json)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (registration.registration_id, registration.tenant_id,
                     registration.system_id, registration.system_version,
                     registration.classification_label, registration.supersedes,
                     registration.record_digest(),
                     json.dumps(record, sort_keys=True, separators=(",", ":"))))
            except sqlite3.IntegrityError as exc:
                raise DuplicateRegistrationError(str(exc)) from exc
            except sqlite3.Error as exc:
                raise RegistryStorageError(f"cannot write the registry: {exc}") from exc
        return registration

    # -- the SystemRegistryPort reads --------------------------------------- #
    def get_registration(self, registration_id: str) -> Optional[SystemRegistration]:
        with self._lock:
            for registration in self._rows():
                if registration.registration_id == registration_id:
                    return registration
        return None

    def registrations_for_tenant(self, *, tenant_id: str,
                                 as_of: datetime) -> tuple[SystemRegistration, ...]:
        self._require_tenant(tenant_id)
        with self._lock:
            return select_for_tenant(self._rows(), tenant_id=tenant_id, as_of=as_of)

    def registrations_for_system(self, *, tenant_id: str, system_id: str,
                                 system_version: str = "",
                                 as_of: datetime) -> tuple[SystemRegistration, ...]:
        self._require_tenant(tenant_id)
        with self._lock:
            return select_for_system(self._rows(), tenant_id=tenant_id, system_id=system_id,
                                     system_version=system_version, as_of=as_of)

    def registrations_by_classification(self, *, tenant_id: str, classification_label: str,
                                        as_of: datetime) -> tuple[SystemRegistration, ...]:
        self._require_tenant(tenant_id)
        with self._lock:
            return select_by_classification(self._rows(), tenant_id=tenant_id,
                                            classification_label=classification_label,
                                            as_of=as_of)

    # -- diagnostics, read-only --------------------------------------------- #
    def count(self) -> int:
        with self._lock:
            return len(self._rows())

    def all_registered_at(self, as_of: datetime) -> tuple[SystemRegistration, ...]:
        with self._lock:
            return registered_at(self._rows(), as_of=as_of)
