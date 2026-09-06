"""The one durable home of declarations (front-door ruling FD-12.2).

    THIS FILE RECORDS AND READS. IT NEVER INSPECTS, CLASSIFIES, ADMITS, AUTHORIZES,
    ENFORCES, EDITS OR DELETES. ITS ONLY WRITE IS ``declare``.

``SqliteDataUseDeclarations`` implements the read-only :class:`DataUseDeclarationPort`
over a sqlite file in the seam-5 posture: a plain file path under a writable volume,
no server, no driver, no DSN, no network. It is bound to exactly one tenant at
construction; a read or write naming any other tenant is a typed refusal, never an
empty answer. Records are append-only: a declaration is never edited, a changed
declaration is a new one that ``supersedes`` its predecessor, and the supersession is
admitted only by :func:`supersession_refusals`.

**Everything the package refuses, it still refuses.** What is stored is the
declaration record and nothing else: the reference, not the data (there is no field
that could carry a payload); the label as the declarer spelled it, uninterpreted
(DE-3); the residency label recorded and never evaluated (DE-2). This file adds
persistence, and persistence only — no taxonomy, no ordering, no comparison, no
admission.

No clock is read here. Every ``as_of`` is the caller's instant, exactly as the pure
selectors take it, so a lapsed declaration is absent from an answer without a sweeper.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import List, Optional

from ._canon import require_nonempty
from .declaration import (
    DataUseDeclaration,
    declaration_from_record,
    declaration_record,
    require_admissible_supersession,
)
from .errors import (
    ContractViolation,
    CrossTenantRefused,
    DeclarationProductionModeError,
    DeclarationStorageError,
    DuplicateDeclarationError,
)
from .selectors import (
    declared_at,
    select_by_classification,
    select_for_data,
    select_for_system,
    select_for_tenant,
)

__all__ = ["SqliteDataUseDeclarations", "SCHEMA_VERSION"]

SCHEMA_VERSION = "data_use_admission.sqlite.v1"

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS declarations ("
    " seq INTEGER PRIMARY KEY AUTOINCREMENT,"
    " declaration_id TEXT NOT NULL UNIQUE,"
    " tenant_id TEXT NOT NULL,"
    " data_ref TEXT NOT NULL,"
    " system_id TEXT NOT NULL,"
    " system_version TEXT NOT NULL,"
    " classification_label TEXT NOT NULL,"
    " purpose_label TEXT NOT NULL,"
    " supersedes TEXT NOT NULL,"
    " record_digest TEXT NOT NULL,"
    " record_json TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS declarations_tenant ON declarations(tenant_id)",
    "CREATE TABLE IF NOT EXISTS declarations_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
)


def _is_non_durable(path: str) -> bool:
    return path == ":memory:" or path.startswith("file:")


class SqliteDataUseDeclarations:
    """A tenant-bound, append-only sqlite file satisfying :class:`DataUseDeclarationPort`."""

    kind = "SqliteDataUseDeclarations"

    def __init__(self, path: str, *, tenant_id: str, production_mode: bool = False,
                 busy_timeout_ms: int = 5000) -> None:
        self.tenant_id = require_nonempty(tenant_id, "SqliteDataUseDeclarations.tenant_id")
        self.path = require_nonempty(path, "SqliteDataUseDeclarations.path")
        self.production_mode = bool(production_mode)
        if self.production_mode and _is_non_durable(self.path):
            raise DeclarationProductionModeError(
                "a durable file path is required in production mode; an in-memory or URI "
                "location is refused")
        self._lock = threading.Lock()
        try:
            self._db_handle: Optional[sqlite3.Connection] = sqlite3.connect(
                self.path, check_same_thread=False, isolation_level=None)
            self._db_handle.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
            if not _is_non_durable(self.path):
                self._db_handle.execute("PRAGMA journal_mode=WAL")
            for statement in _SCHEMA:
                self._db_handle.execute(statement)
            self._db_handle.execute(
                "INSERT OR IGNORE INTO declarations_meta(key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,))
            self._db_handle.execute(
                "INSERT OR IGNORE INTO declarations_meta(key, value) VALUES ('tenant_id', ?)",
                (self.tenant_id,))
            bound = self._db_handle.execute(
                "SELECT value FROM declarations_meta WHERE key = 'tenant_id'").fetchone()[0]
            if bound != self.tenant_id:
                self._db_handle.close()
                self._db_handle = None
                raise CrossTenantRefused(
                    "this declarations file is bound to another tenant; a file is never "
                    "re-bound")
        except sqlite3.Error as exc:
            raise DeclarationStorageError(f"cannot open the declarations file: {exc}") from exc

    # ------------------------------------------------------------------ #
    def close(self) -> None:
        with self._lock:
            if self._db_handle is not None:
                self._db_handle.close()
                self._db_handle = None

    def _db(self) -> sqlite3.Connection:
        if self._db_handle is None:
            raise DeclarationStorageError("the declarations file is closed")
        return self._db_handle

    def _require_tenant(self, tenant_id: str) -> None:
        if tenant_id != self.tenant_id:
            raise CrossTenantRefused(
                f"this file is bound to one tenant; a read or write for tenant "
                f"{tenant_id!r} is refused")

    def _rows(self) -> List[DataUseDeclaration]:
        try:
            cursor = self._db().execute(
                "SELECT record_json, record_digest FROM declarations WHERE tenant_id = ? "
                "ORDER BY seq", (self.tenant_id,))
            rows = cursor.fetchall()
        except sqlite3.Error as exc:
            raise DeclarationStorageError(f"cannot read the declarations file: {exc}") from exc
        out: List[DataUseDeclaration] = []
        for record_json, stored_digest in rows:
            declaration = declaration_from_record(json.loads(record_json))
            if declaration.record_digest() != stored_digest:
                raise ContractViolation(
                    f"declaration {declaration.declaration_id} does not match its recorded "
                    "digest; the record was altered outside this package")
            out.append(declaration)
        return out

    # -- the one write (FD-12.5) ------------------------------------------- #
    def declare(self, declaration: DataUseDeclaration) -> DataUseDeclaration:
        """Append one declaration. Refuses a foreign tenant, a duplicate derived id and
        an inadmissible supersession; never edits or deletes."""

        if not isinstance(declaration, DataUseDeclaration):
            raise ContractViolation("declare takes a DataUseDeclaration")
        self._require_tenant(declaration.tenant_id)
        with self._lock:
            existing = {d.declaration_id: d for d in self._rows()}
            if declaration.declaration_id in existing:
                raise DuplicateDeclarationError(
                    f"declaration {declaration.declaration_id} is already recorded; "
                    "records are never edited")
            predecessor = existing.get(declaration.supersedes) if declaration.supersedes else None
            require_admissible_supersession(declaration, predecessor)
            record = declaration_record(declaration)
            try:
                self._db().execute(
                    "INSERT INTO declarations(declaration_id, tenant_id, data_ref, system_id, "
                    "system_version, classification_label, purpose_label, supersedes, "
                    "record_digest, record_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (declaration.declaration_id, declaration.tenant_id, declaration.data_ref,
                     declaration.system_id, declaration.system_version,
                     declaration.classification_label, declaration.purpose_label,
                     declaration.supersedes, declaration.record_digest(),
                     json.dumps(record, sort_keys=True, separators=(",", ":"))))
            except sqlite3.IntegrityError as exc:
                raise DuplicateDeclarationError(str(exc)) from exc
            except sqlite3.Error as exc:
                raise DeclarationStorageError(
                    f"cannot write the declarations file: {exc}") from exc
        return declaration

    # -- the DataUseDeclarationPort reads ----------------------------------- #
    def get_declaration(self, declaration_id: str) -> Optional[DataUseDeclaration]:
        with self._lock:
            for declaration in self._rows():
                if declaration.declaration_id == declaration_id:
                    return declaration
        return None

    def declarations_for_tenant(self, *, tenant_id: str,
                                as_of: datetime) -> tuple[DataUseDeclaration, ...]:
        self._require_tenant(tenant_id)
        with self._lock:
            return select_for_tenant(self._rows(), tenant_id=tenant_id, as_of=as_of)

    def declarations_for_data(self, *, tenant_id: str, data_ref: str,
                              as_of: datetime) -> tuple[DataUseDeclaration, ...]:
        self._require_tenant(tenant_id)
        with self._lock:
            return select_for_data(self._rows(), tenant_id=tenant_id, data_ref=data_ref,
                                   as_of=as_of)

    def declarations_for_system(self, *, tenant_id: str, system_id: str,
                                system_version: str = "",
                                as_of: datetime) -> tuple[DataUseDeclaration, ...]:
        self._require_tenant(tenant_id)
        with self._lock:
            return select_for_system(self._rows(), tenant_id=tenant_id, system_id=system_id,
                                     system_version=system_version, as_of=as_of)

    def declarations_by_classification(self, *, tenant_id: str, classification_label: str,
                                       as_of: datetime) -> tuple[DataUseDeclaration, ...]:
        self._require_tenant(tenant_id)
        with self._lock:
            return select_by_classification(self._rows(), tenant_id=tenant_id,
                                            classification_label=classification_label,
                                            as_of=as_of)

    # -- diagnostics, read-only --------------------------------------------- #
    def count(self) -> int:
        with self._lock:
            return len(self._rows())

    def all_declared_at(self, as_of: datetime) -> tuple[DataUseDeclaration, ...]:
        with self._lock:
            return declared_at(self._rows(), as_of=as_of)
