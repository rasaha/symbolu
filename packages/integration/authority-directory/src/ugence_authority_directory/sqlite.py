"""SQLite adapter — single-node durable persistence (D-22 Posture B).

Stdlib ``sqlite3`` only: WAL journal, every write inside ``BEGIN IMMEDIATE`` (one
writer at a time across processes on one host), and one append-only, hash-linked
``directory_events`` table whose triggers refuse UPDATE and DELETE. The *shape* is
that of the sibling integration packages — copied, never imported.

What this is not: distributed, replicated, highly available, an identity provider, or
a store of anything secret. It holds non-secret references only. Distributed strong
consistency stays disclaimed, and a ``:memory:`` path is refused in production mode
because it is not durable.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from typing import Iterator, Optional

from ._canon import canonical_json, digest, from_iso, iso, require_nonempty, require_tzaware
from .delegation import delegation_refusals
from .directory import CommitteeReport
from .errors import (
    DelegationRefused,
    GrantAlreadyExistsError,
    GrantNotFoundError,
    ProductionModeRefused,
    StoreUnavailableError,
)
from .grants import GrantEvent, GrantEventType, RoleGrant
from .selection import build_committee_report, select_for_principal, select_holders
from .version import MATURITY

__all__ = ["SqliteAuthorityDirectory", "SCHEMA_VERSION"]

SCHEMA_VERSION = "authority_directory.store/1.0.0"
_GENESIS = "0" * 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS grants (
    grant_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, principal_id TEXT NOT NULL,
    principal_kind TEXT NOT NULL, role TEXT NOT NULL, scope TEXT NOT NULL,
    member_of TEXT NOT NULL, delegation_ref TEXT NOT NULL, revoked_at TEXT NOT NULL,
    record_digest TEXT NOT NULL, record_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS grants_by_role ON grants (tenant_id, role);
CREATE INDEX IF NOT EXISTS grants_by_principal ON grants (tenant_id, principal_id);
CREATE TABLE IF NOT EXISTS directory_events (
    seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, tenant_id TEXT NOT NULL,
    subject_id TEXT NOT NULL, sequence INTEGER NOT NULL, event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL, actor TEXT NOT NULL, detail_json TEXT NOT NULL,
    prev_digest TEXT NOT NULL, record_digest TEXT NOT NULL,
    UNIQUE (kind, subject_id, sequence));
CREATE TRIGGER IF NOT EXISTS directory_events_no_update BEFORE UPDATE ON directory_events
    BEGIN SELECT RAISE(ABORT, 'directory_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS directory_events_no_delete BEFORE DELETE ON directory_events
    BEGIN SELECT RAISE(ABORT, 'directory_events is append-only'); END;
"""


class SqliteAuthorityDirectory:
    """Durable adapter for :class:`~ugence_authority_directory.directory.AuthorityDirectoryPort`."""

    maturity = MATURITY

    def __init__(self, path: str, *, production_mode: bool = False,
                 busy_timeout_ms: int = 5000) -> None:
        if production_mode and (path == ":memory:" or path.startswith("file::memory:")):
            raise ProductionModeRefused("an in-memory SQLite database is not durable; "
                                        "production mode requires a file path")
        self.path = path
        self.production_mode = production_mode
        try:
            self._conn: Optional[sqlite3.Connection] = sqlite3.connect(
                path, isolation_level=None, check_same_thread=False,
                timeout=busy_timeout_ms / 1000)
            self._conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
            if path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
            with self._tx() as c:
                row = c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
                if row is None:
                    c.execute("INSERT INTO meta VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
                elif row[0] != SCHEMA_VERSION:
                    raise StoreUnavailableError(f"schema version {row[0]} != {SCHEMA_VERSION}")
        except sqlite3.Error as exc:
            raise StoreUnavailableError(str(exc)) from exc

    # ------------------------------------------------------------------ #
    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _c(self) -> sqlite3.Connection:
        if self._conn is None:
            raise StoreUnavailableError("store closed")
        return self._conn

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = self._c()
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            raise StoreUnavailableError(str(exc)) from exc
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")

    def _append_event(self, c: sqlite3.Connection, tenant_id: str, subject_id: str,
                      event_type: str, occurred_at: datetime, actor: str, detail: dict) -> int:
        row = c.execute("SELECT COALESCE(MAX(sequence), -1) FROM directory_events "
                        "WHERE kind='grant' AND subject_id=?", (subject_id,)).fetchone()
        sequence = int(row[0]) + 1
        prev = c.execute("SELECT record_digest FROM directory_events "
                         "ORDER BY seq DESC LIMIT 1").fetchone()
        prev_digest = prev[0] if prev else _GENESIS
        occurred = iso(occurred_at, "occurred_at")
        payload = {"kind": "grant", "tenant_id": tenant_id, "subject_id": subject_id,
                   "sequence": sequence, "event_type": event_type, "occurred_at": occurred,
                   "actor": actor, "detail": detail, "prev_digest": prev_digest}
        c.execute("INSERT INTO directory_events (kind, tenant_id, subject_id, sequence, "
                  "event_type, occurred_at, actor, detail_json, prev_digest, record_digest) "
                  "VALUES ('grant',?,?,?,?,?,?,?,?,?)",
                  (tenant_id, subject_id, sequence, event_type, occurred, actor,
                   canonical_json(detail), prev_digest, digest(payload)))
        return sequence

    def verify_chain(self) -> bool:
        """Recompute the hash chain over every event; a single altered row breaks it."""

        prev = _GENESIS
        for row in self._c().execute(
                "SELECT kind, tenant_id, subject_id, sequence, event_type, occurred_at, actor, "
                "detail_json, prev_digest, record_digest FROM directory_events ORDER BY seq"):
            (kind, tenant, subject, sequence, etype, occurred, actor, detail_json,
             prev_digest, record_digest) = row
            if prev_digest != prev:
                return False
            payload = {"kind": kind, "tenant_id": tenant, "subject_id": subject,
                       "sequence": sequence, "event_type": etype, "occurred_at": occurred,
                       "actor": actor, "detail": json.loads(detail_json),
                       "prev_digest": prev_digest}
            if digest(payload) != record_digest:
                return False
            prev = record_digest
        return True

    # ------------------------------------------------------------------ #
    def _row(self, c: sqlite3.Connection, grant_id: str) -> Optional[RoleGrant]:
        row = c.execute("SELECT record_json, record_digest FROM grants WHERE grant_id=?",
                        (grant_id,)).fetchone()
        if row is None:
            return None
        grant = RoleGrant.from_dict(json.loads(row[0]))
        grant.verify(row[1])
        return grant

    def _all(self, c: sqlite3.Connection, *, tenant_id: str = "") -> tuple[RoleGrant, ...]:
        sql = "SELECT record_json, record_digest FROM grants"
        args: tuple = ()
        if tenant_id:
            sql += " WHERE tenant_id=?"
            args = (tenant_id,)
        out = []
        for record_json, record_digest in c.execute(sql + " ORDER BY grant_id", args):
            grant = RoleGrant.from_dict(json.loads(record_json))
            grant.verify(record_digest)
            out.append(grant)
        return tuple(out)

    def _write(self, c: sqlite3.Connection, grant: RoleGrant) -> RoleGrant:
        c.execute("INSERT INTO grants (grant_id, tenant_id, principal_id, principal_kind, role, "
                  "scope, member_of, delegation_ref, revoked_at, record_digest, record_json) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(grant_id) DO UPDATE SET "
                  "revoked_at=excluded.revoked_at, record_digest=excluded.record_digest, "
                  "record_json=excluded.record_json",
                  (grant.grant_id, grant.tenant_id, grant.principal_id,
                   grant.principal.principal_kind.value, grant.role, grant.scope,
                   grant.member_of, grant.delegation_ref,
                   iso(grant.revoked_at, "revoked_at") if grant.revoked_at else "",
                   grant.record_digest(), canonical_json(grant.to_dict())))
        return grant

    # ------------------------------------------------------------------ #
    # AuthorityDirectoryPort
    # ------------------------------------------------------------------ #
    def put_grant(self, grant: RoleGrant, *, as_of: datetime, loaded_by: str = "") -> RoleGrant:
        require_tzaware(as_of, "put_grant.as_of")
        with self._tx() as c:
            if self._row(c, grant.grant_id) is not None:
                raise GrantAlreadyExistsError(
                    f"grant '{grant.grant_id}' already exists; a grant is a record and is "
                    "never overwritten")
            if grant.is_delegated:
                refusals = delegation_refusals(grant, self._row(c, grant.delegation_ref), as_of)
                if refusals:
                    raise DelegationRefused("; ".join(refusals))
            stored = replace(grant, loaded_by=loaded_by.strip()) if loaded_by else grant
            self._write(c, stored)
            self._append_event(c, stored.tenant_id, stored.grant_id,
                               GrantEventType.GRANTED.value, as_of, loaded_by,
                               {"role": stored.role, "scope": stored.scope,
                                "delegated": stored.is_delegated})
            return stored

    def revoke_grant(self, grant_id: str, *, as_of: datetime, reason: str = "",
                     actor: str = "") -> RoleGrant:
        with self._tx() as c:
            grant = self._row(c, require_nonempty(grant_id, "grant_id"))
            if grant is None:
                raise GrantNotFoundError(f"no grant '{grant_id}'")
            revoked = grant.revoked(as_of=as_of, reason=reason)
            self._write(c, revoked)
            self._append_event(c, revoked.tenant_id, revoked.grant_id,
                               GrantEventType.REVOKED.value, as_of, actor,
                               {"reason": revoked.revocation_reason})
            return revoked

    def get_grant(self, grant_id: str) -> Optional[RoleGrant]:
        return self._row(self._c(), grant_id)

    def grants_for(self, *, tenant_id: str, principal_id: str,
                   as_of: datetime) -> tuple[RoleGrant, ...]:
        return select_for_principal(self._all(self._c(), tenant_id=tenant_id),
                                    tenant_id=tenant_id, principal_id=principal_id, as_of=as_of)

    def holders_of(self, *, tenant_id: str, role: str, scope: str,
                   as_of: datetime) -> tuple[RoleGrant, ...]:
        return select_holders(self._all(self._c(), tenant_id=tenant_id), tenant_id=tenant_id,
                              role=role, scope=scope, as_of=as_of)

    def committee_report(self, *, tenant_id: str, committee_id: str, role: str, scope: str,
                         as_of: datetime) -> Optional[CommitteeReport]:
        return build_committee_report(self._all(self._c(), tenant_id=tenant_id),
                                      tenant_id=tenant_id, committee_id=committee_id,
                                      role=role, scope=scope, as_of=as_of)

    def grant_events(self, grant_id: str) -> tuple[GrantEvent, ...]:
        rows = self._c().execute(
            "SELECT sequence, event_type, occurred_at, actor, detail_json FROM directory_events "
            "WHERE kind='grant' AND subject_id=? ORDER BY sequence", (grant_id,)).fetchall()
        return tuple(
            GrantEvent(event_id=f"{grant_id}:{seq}", grant_id=grant_id, sequence=seq,
                       event_type=GrantEventType(etype), occurred_at=from_iso(occurred),
                       actor=actor, detail=detail_json)
            for seq, etype, occurred, actor, detail_json in rows)
