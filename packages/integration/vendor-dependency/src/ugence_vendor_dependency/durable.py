"""The one durable home of vendor declarations (front-door ruling FD-13.2).

    THIS FILE RECORDS AND READS. IT NEVER INSPECTS, RANKS, SCORES, APPROVES,
    ONBOARDS, VERIFIES, ENFORCES, EDITS OR DELETES. ITS ONLY WRITE IS ``declare``.

``SqliteVendorDeclarations`` implements the read-only :class:`VendorDependencyPort`
over a sqlite file in the seam-5 and seam-8 posture: a plain file path under a
writable volume, no server, no driver, no DSN, no network. It is bound to exactly one
tenant at construction; a read or write naming any other tenant is a typed refusal,
never an empty answer. Records are append-only: a declaration is never edited, a
changed declaration is a new one that ``supersedes`` its predecessor, and the
supersession is admitted only by :func:`supersession_refusals`.

**Everything the package refuses, it still refuses.** What is stored is the
declaration record and nothing else: an opaque ``vendor_ref``, never a vendor's
address, endpoint, credential, contract terms, pricing or contact data (there is no
field that could carry them); the risk posture exactly as the declarer spelled it,
uninterpreted (VR-3, FD-13.4) — never ordered, compared, ranked or scored here or
anywhere; the ``policy_ref`` recorded and never resolved (VR-4). This file adds
persistence, and persistence only — no taxonomy, no ordering, no comparison, no
approval, no onboarding status.

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
from .version import CONTRACT_VERSION
from .declaration import (
    VendorDependencyDeclaration,
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
    select_by_risk_posture,
    select_for_system,
    select_for_tenant,
    select_for_vendor,
)

__all__ = ["SqliteVendorDeclarations", "SCHEMA_VERSION", "LEGACY_SCHEMA_VERSION"]

#: Moved to v2 in 0.3.0. The *table* is unchanged — the vocabulary binding travels in
#: ``record_json`` with the rest of the record — but a v2 file holds a shape a v1 file
#: never held, and the meta row is the only thing that can say which.
SCHEMA_VERSION = "vendor_dependency.sqlite.v2"

#: Files written before the binding. They stay **readable**, and are closed to writes
#: **permanently**: appending a v2 record to a v1 file would make its own schema row a
#: lie, and MIG-5 ruled that no migration follows
#: (docs/architecture/VOCABULARY_BINDING_MIGRATION_SCOPING.md), so this is the end state
#: rather than a waiting room.
LEGACY_SCHEMA_VERSION = "vendor_dependency.sqlite.v1"

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS declarations ("
    " seq INTEGER PRIMARY KEY AUTOINCREMENT,"
    " declaration_id TEXT NOT NULL UNIQUE,"
    " tenant_id TEXT NOT NULL,"
    " vendor_ref TEXT NOT NULL,"
    " system_id TEXT NOT NULL,"
    " system_version TEXT NOT NULL,"
    " risk_posture_label TEXT NOT NULL,"
    " policy_ref TEXT NOT NULL,"
    " supersedes TEXT NOT NULL,"
    " record_digest TEXT NOT NULL,"
    " record_json TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS declarations_tenant ON declarations(tenant_id)",
    "CREATE TABLE IF NOT EXISTS declarations_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
)


def _is_non_durable(path: str) -> bool:
    return path == ":memory:" or path.startswith("file:")


class SqliteVendorDeclarations:
    """A tenant-bound, append-only sqlite file satisfying :class:`VendorDependencyPort`."""

    kind = "SqliteVendorDeclarations"

    def __init__(self, path: str, *, tenant_id: str, production_mode: bool = False,
                 busy_timeout_ms: int = 5000) -> None:
        self.tenant_id = require_nonempty(tenant_id, "SqliteVendorDeclarations.tenant_id")
        self.path = require_nonempty(path, "SqliteVendorDeclarations.path")
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
            # OR IGNORE leaves an existing file's own version in place, so this reads
            # what the file says rather than what this build would have written.
            self.schema_version = self._db_handle.execute(
                "SELECT value FROM declarations_meta WHERE key = 'schema_version'"
            ).fetchone()[0]
            if self.schema_version not in (SCHEMA_VERSION, LEGACY_SCHEMA_VERSION):
                self._db_handle.close()
                self._db_handle = None
                raise DeclarationStorageError(
                    f"this declarations file records schema {self.schema_version!r}, which "
                    f"this build does not know; it reads {SCHEMA_VERSION!r} and "
                    f"{LEGACY_SCHEMA_VERSION!r}")
            #: A v1 file is readable and closed to writes. Stated as a field so a
            #: composition root can see the posture without provoking a refusal.
            self.accepts_writes = self.schema_version == SCHEMA_VERSION
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

    def _rows(self) -> List[VendorDependencyDeclaration]:
        try:
            cursor = self._db().execute(
                "SELECT record_json, record_digest FROM declarations WHERE tenant_id = ? "
                "ORDER BY seq", (self.tenant_id,))
            rows = cursor.fetchall()
        except sqlite3.Error as exc:
            raise DeclarationStorageError(f"cannot read the declarations file: {exc}") from exc
        out: List[VendorDependencyDeclaration] = []
        for record_json, stored_digest in rows:
            declaration = declaration_from_record(json.loads(record_json))
            if declaration.record_digest() != stored_digest:
                raise ContractViolation(
                    f"declaration {declaration.declaration_id} does not match its recorded "
                    "digest; the record was altered outside this package")
            out.append(declaration)
        return out

    # -- the one write (FD-13.4) ------------------------------------------- #
    def declare(self, declaration: VendorDependencyDeclaration) -> VendorDependencyDeclaration:
        """Append one declaration. Refuses a foreign tenant, a duplicate derived id and
        an inadmissible supersession; never edits or deletes."""

        if not isinstance(declaration, VendorDependencyDeclaration):
            raise ContractViolation("declare takes a VendorDependencyDeclaration")
        self._require_tenant(declaration.tenant_id)
        if not self.accepts_writes:
            raise DeclarationStorageError(
                f"this file is {self.schema_version!r} and holds records written before "
                "the vocabulary binding; it stays readable and takes no new records. "
                "It is closed permanently: MIG-5 ruled migration out of scope "
                "(docs/architecture/VOCABULARY_BINDING_MIGRATION_SCOPING.md), because a "
                "binding asserted for a record written before any vocabulary was "
                "published would be false rather than merely unverifiable. Open a "
                "current file for new records and read this one alongside it")
        if declaration.record_version != CONTRACT_VERSION:
            raise ContractViolation(
                f"declare takes a {CONTRACT_VERSION} declaration; "
                f"{declaration.record_version!r} is a historical shape that can be read "
                "and not written, so a new record cannot reach the file without naming "
                "the vocabulary its posture was written against")
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
                    "INSERT INTO declarations(declaration_id, tenant_id, vendor_ref, system_id, "
                    "system_version, risk_posture_label, policy_ref, supersedes, "
                    "record_digest, record_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (declaration.declaration_id, declaration.tenant_id, declaration.vendor_ref,
                     declaration.system_id, declaration.system_version,
                     declaration.risk_posture_label, declaration.policy_ref,
                     declaration.supersedes, declaration.record_digest(),
                     json.dumps(record, sort_keys=True, separators=(",", ":"))))
            except sqlite3.IntegrityError as exc:
                raise DuplicateDeclarationError(str(exc)) from exc
            except sqlite3.Error as exc:
                raise DeclarationStorageError(
                    f"cannot write the declarations file: {exc}") from exc
        return declaration

    # -- the VendorDependencyPort reads ------------------------------------- #
    def get_declaration(self, declaration_id: str) -> Optional[VendorDependencyDeclaration]:
        with self._lock:
            for declaration in self._rows():
                if declaration.declaration_id == declaration_id:
                    return declaration
        return None

    def declarations_for_tenant(self, *, tenant_id: str,
                                as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]:
        self._require_tenant(tenant_id)
        with self._lock:
            return select_for_tenant(self._rows(), tenant_id=tenant_id, as_of=as_of)

    def declarations_for_vendor(self, *, tenant_id: str, vendor_ref: str,
                                as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]:
        self._require_tenant(tenant_id)
        with self._lock:
            return select_for_vendor(self._rows(), tenant_id=tenant_id, vendor_ref=vendor_ref,
                                     as_of=as_of)

    def declarations_for_system(self, *, tenant_id: str, system_id: str,
                                system_version: str = "",
                                as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]:
        self._require_tenant(tenant_id)
        with self._lock:
            return select_for_system(self._rows(), tenant_id=tenant_id, system_id=system_id,
                                     system_version=system_version, as_of=as_of)

    def declarations_by_risk_posture(self, *, tenant_id: str, risk_posture_label: str,
                                     as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]:
        """Declarations whose posture text matches exactly. Exact text equality only:
        no ordering, no ranking, no severity comparison (VR-3, FD-13.4)."""

        self._require_tenant(tenant_id)
        with self._lock:
            return select_by_risk_posture(self._rows(), tenant_id=tenant_id,
                                          risk_posture_label=risk_posture_label, as_of=as_of)

    # -- diagnostics, read-only --------------------------------------------- #
    def count(self) -> int:
        with self._lock:
            return len(self._rows())

    def all_declared_at(self, as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]:
        with self._lock:
            return declared_at(self._rows(), as_of=as_of)
