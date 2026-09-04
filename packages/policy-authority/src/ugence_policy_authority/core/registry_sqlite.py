"""The durable registry — single-node SQLite (ADR §15.7, closed under decision D-3).

Same seam, same rules as :class:`~.registry.InMemoryPolicyRegistry`, now durable:

* **exact coordinate lookup only** — the tables are keyed by the canonical
  coordinate; no ``latest()``, ``current()`` or partial-id path exists;
* **append-only** — issuance, revocation and supersession live in three tables,
  each guarded by triggers that refuse ``UPDATE`` and ``DELETE``; every append
  also lands in one hash-linked ``ledger_events`` table so tampering by a
  privileged writer is detectable after the fact;
* **idempotent** only for a canonically identical record (byte comparison of the
  same canonical bytes the in-memory registry compares); any other reuse of a
  version slot is a typed :class:`PolicyRegistryConflictError`;
* **tenant isolation** — a cross-tenant probe is an exact-key miss, the same
  ``None`` as a nonexistent record;
* **single-host coordination** — every write runs inside ``BEGIN IMMEDIATE``,
  so writers in different processes on one host are serialized by SQLite's
  lock and a committed revocation is visible to every process at once (WAL
  journal, read-after-write);
* **one act for successor + supersession** — both rows commit or neither.

What it is **not**: replicated, distributed, highly available, or a production
key-custody story. ``distributed_strong_consistency`` and
``eventual_consistency_safety`` are declared disclaimed on the consistency
descriptor, not merely absent from the prose. A ``:memory:`` path is refused in
production mode because it is not durable. The shape of the store follows the
storygraph durable audit log; the code is not imported.

No clock is read. The store records what callers append, at the instants they
supply; ordering is by append sequence, never wall time.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from .adapters import PolicyCoordinate
from .canonical import canonical_bytes, canonical_dumps, sha256_hex
from .codec import (
    PolicyArtifactCodec,
    coordinate_key,
    decode_issued_record,
    decode_revocation_record,
    decode_supersession_record,
    encode_issued_record,
    encode_revocation_record,
    encode_supersession_record,
    identity_slot_key,
)
from .consistency import PolicyRegistryConsistencyDescriptor, PolicyRegistryConsistencyScope
from .errors import (
    PolicyRegistryConflictError,
    PolicyRegistryProductionModeError,
    PolicyRegistryStorageError,
)
from .records import (
    IssuedPolicyRecord,
    PolicyRevocationRecord,
    PolicySupersessionRecord,
)
from .registry import _record_bytes

__all__ = ["SqlitePolicyRegistry", "SQLITE_REGISTRY_SCHEMA_VERSION"]

SQLITE_REGISTRY_SCHEMA_VERSION = "ugence.policy-authority/registry-sqlite/v1"
_GENESIS = "0" * 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS issuances (
    coordinate_key TEXT PRIMARY KEY, identity_slot TEXT NOT NULL UNIQUE,
    policy_family TEXT NOT NULL, policy_id TEXT NOT NULL, scope TEXT NOT NULL,
    tenant_id TEXT NOT NULL, version TEXT NOT NULL, record_id TEXT NOT NULL,
    record_bytes BLOB NOT NULL, payload_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS issuances_identity
    ON issuances (policy_family, policy_id, scope, tenant_id);
CREATE TABLE IF NOT EXISTS revocations (
    coordinate_key TEXT PRIMARY KEY, record_bytes BLOB NOT NULL, payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS supersessions (
    predecessor_key TEXT PRIMARY KEY, successor_key TEXT NOT NULL,
    record_bytes BLOB NOT NULL, payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger_events (
    seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, subject_key TEXT NOT NULL,
    record_digest TEXT NOT NULL, prev_digest TEXT NOT NULL, chain_digest TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS issuances_no_update BEFORE UPDATE ON issuances
    BEGIN SELECT RAISE(ABORT, 'issuances is append-only'); END;
CREATE TRIGGER IF NOT EXISTS issuances_no_delete BEFORE DELETE ON issuances
    BEGIN SELECT RAISE(ABORT, 'issuances is append-only'); END;
CREATE TRIGGER IF NOT EXISTS revocations_no_update BEFORE UPDATE ON revocations
    BEGIN SELECT RAISE(ABORT, 'revocations is append-only'); END;
CREATE TRIGGER IF NOT EXISTS revocations_no_delete BEFORE DELETE ON revocations
    BEGIN SELECT RAISE(ABORT, 'revocations is append-only'); END;
CREATE TRIGGER IF NOT EXISTS supersessions_no_update BEFORE UPDATE ON supersessions
    BEGIN SELECT RAISE(ABORT, 'supersessions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS supersessions_no_delete BEFORE DELETE ON supersessions
    BEGIN SELECT RAISE(ABORT, 'supersessions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger_events
    BEGIN SELECT RAISE(ABORT, 'ledger_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger_events
    BEGIN SELECT RAISE(ABORT, 'ledger_events is append-only'); END;
"""


class SqlitePolicyRegistry:
    """Single-node durable registry. Satisfies :class:`~.registry.PolicyRegistry`."""

    consistency = PolicyRegistryConsistencyDescriptor(
        PolicyRegistryConsistencyScope.SINGLE_NODE_DURABLE
    )

    def __init__(self, path: str, *, codec: PolicyArtifactCodec,
                 production_mode: bool = False, busy_timeout_ms: int = 5000) -> None:
        if not isinstance(codec, PolicyArtifactCodec):
            raise PolicyRegistryStorageError("SqlitePolicyRegistry requires a PolicyArtifactCodec")
        if production_mode and (path == ":memory:" or path.startswith("file::memory:")):
            raise PolicyRegistryProductionModeError(
                "an in-memory SQLite database is not durable; production mode requires a file path")
        self.path = path
        self.production_mode = production_mode
        self._codec = codec
        try:
            self._conn: Optional[sqlite3.Connection] = sqlite3.connect(
                path, isolation_level=None, check_same_thread=False, timeout=busy_timeout_ms / 1000)
            self._conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
            if path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
            with self._tx() as c:
                row = c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
                if row is None:
                    c.execute("INSERT INTO meta VALUES ('schema_version', ?)",
                              (SQLITE_REGISTRY_SCHEMA_VERSION,))
                elif row[0] != SQLITE_REGISTRY_SCHEMA_VERSION:
                    raise PolicyRegistryStorageError(
                        f"registry schema {row[0]!r} is not {SQLITE_REGISTRY_SCHEMA_VERSION!r}")
        except sqlite3.Error as exc:
            raise PolicyRegistryStorageError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Connection plumbing
    # ------------------------------------------------------------------
    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _c(self) -> sqlite3.Connection:
        if self._conn is None:
            raise PolicyRegistryStorageError("registry closed")
        return self._conn

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = self._c()
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            raise PolicyRegistryStorageError(str(exc)) from exc
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")

    def _read(self) -> sqlite3.Connection:
        return self._c()

    def _append_event(self, c: sqlite3.Connection, kind: str, subject_key: str,
                      record_bytes: bytes) -> None:
        prev = c.execute("SELECT chain_digest FROM ledger_events ORDER BY seq DESC LIMIT 1").fetchone()
        prev_digest = prev[0] if prev else _GENESIS
        record_digest = sha256_hex(record_bytes)
        chain = sha256_hex(canonical_bytes(
            {"kind": kind, "subject_key": subject_key, "record_digest": record_digest,
             "prev_digest": prev_digest}))
        c.execute("INSERT INTO ledger_events (kind, subject_key, record_digest, prev_digest, chain_digest) "
                  "VALUES (?,?,?,?,?)", (kind, subject_key, record_digest, prev_digest, chain))

    def verify_chain(self) -> bool:
        """Recompute the hash chain and the digest of every stored record it names."""

        c = self._read()
        tables = {"issuance": ("issuances", "coordinate_key"),
                  "revocation": ("revocations", "coordinate_key"),
                  "supersession": ("supersessions", "predecessor_key")}
        prev = _GENESIS
        for kind, subject_key, record_digest, prev_digest, chain in c.execute(
                "SELECT kind, subject_key, record_digest, prev_digest, chain_digest FROM ledger_events ORDER BY seq"):
            if prev_digest != prev:
                return False
            expected = sha256_hex(canonical_bytes(
                {"kind": kind, "subject_key": subject_key, "record_digest": record_digest,
                 "prev_digest": prev_digest}))
            if expected != chain:
                return False
            table, column = tables.get(kind, (None, None))
            if table is None:
                return False
            row = c.execute(f"SELECT record_bytes FROM {table} WHERE {column}=?", (subject_key,)).fetchone()
            if row is None or sha256_hex(bytes(row[0])) != record_digest:
                return False
            prev = chain
        return True

    def snapshot(self) -> tuple:
        """A comparable view proving a failed operation mutated nothing."""

        c = self._read()
        issued = tuple(sorted(r[0] for r in c.execute("SELECT record_id FROM issuances")))
        revoked = tuple(sorted(r[0] for r in c.execute("SELECT coordinate_key FROM revocations")))
        superseded = tuple(sorted(r[0] for r in c.execute("SELECT predecessor_key FROM supersessions")))
        events = c.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0]
        return (issued, revoked, superseded, events)

    # ------------------------------------------------------------------
    # Issuance
    # ------------------------------------------------------------------
    def _issued_in(self, c: sqlite3.Connection, coordinate: PolicyCoordinate) -> Optional[IssuedPolicyRecord]:
        row = c.execute("SELECT payload_json FROM issuances WHERE coordinate_key=?",
                        (coordinate_key(coordinate),)).fetchone()
        if row is None:
            return None
        try:
            return decode_issued_record(json.loads(row[0]), self._codec)
        except sqlite3.Error as exc:
            raise PolicyRegistryStorageError(str(exc)) from exc

    def append_issuance(self, record: IssuedPolicyRecord) -> IssuedPolicyRecord:
        if not isinstance(record, IssuedPolicyRecord):
            raise PolicyRegistryConflictError("append_issuance requires an IssuedPolicyRecord")
        with self._tx() as c:
            return self._append_issuance_in(c, record)

    def _append_issuance_in(self, c: sqlite3.Connection, record: IssuedPolicyRecord) -> IssuedPolicyRecord:
        coordinate = record.coordinate
        key = coordinate_key(coordinate)
        encoded = _record_bytes(record)
        row = c.execute("SELECT record_bytes FROM issuances WHERE coordinate_key=?", (key,)).fetchone()
        if row is not None:
            if bytes(row[0]) == encoded:
                return self._issued_in(c, coordinate)
            raise PolicyRegistryConflictError(
                f"an issuance record already exists for {coordinate.policy_id}@"
                f"{coordinate.version} with different content; issued versions are "
                "immutable and cannot be overwritten")
        slot = identity_slot_key(coordinate)
        claimed = c.execute("SELECT coordinate_key FROM issuances WHERE identity_slot=?", (slot,)).fetchone()
        if claimed is not None and claimed[0] != key:
            raise PolicyRegistryConflictError(
                f"policy {coordinate.policy_id!r} version {coordinate.version!r} is "
                "already issued with different content; a version identity cannot be reused")
        payload = canonical_dumps(encode_issued_record(record, self._codec))
        c.execute("INSERT INTO issuances VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (key, slot, coordinate.policy_family, coordinate.policy_id, coordinate.scope,
                   coordinate.tenant_id, coordinate.version, record.record_id, encoded, payload))
        self._append_event(c, "issuance", key, encoded)
        return record

    def get_issued(self, coordinate: PolicyCoordinate) -> Optional[IssuedPolicyRecord]:
        if not isinstance(coordinate, PolicyCoordinate):
            return None
        try:
            return self._issued_in(self._read(), coordinate)
        except sqlite3.Error as exc:
            raise PolicyRegistryStorageError(str(exc)) from exc

    def issued_records_for_identity(
        self, *, policy_family: str, policy_id: str, scope: str, tenant_id: str
    ) -> tuple[IssuedPolicyRecord, ...]:
        rows = self._read().execute(
            "SELECT payload_json FROM issuances WHERE policy_family=? AND policy_id=? AND scope=? AND tenant_id=?",
            (policy_family, policy_id, scope, tenant_id)).fetchall()
        matches = [decode_issued_record(json.loads(r[0]), self._codec) for r in rows]
        return tuple(sorted(matches, key=lambda r: (r.coordinate.version, r.record_id)))

    # ------------------------------------------------------------------
    # Revocation
    # ------------------------------------------------------------------
    def append_revocation(self, record: PolicyRevocationRecord) -> PolicyRevocationRecord:
        if not isinstance(record, PolicyRevocationRecord):
            raise PolicyRegistryConflictError("append_revocation requires a PolicyRevocationRecord")
        coordinate = record.coordinate
        key = coordinate_key(coordinate)
        encoded = canonical_bytes(record)
        with self._tx() as c:
            row = c.execute("SELECT record_bytes, payload_json FROM revocations WHERE coordinate_key=?",
                            (key,)).fetchone()
            if row is not None:
                if bytes(row[0]) == encoded:
                    return decode_revocation_record(json.loads(row[1]))
                raise PolicyRegistryConflictError(
                    f"a different revocation record already targets {coordinate.policy_id}@"
                    f"{coordinate.version}; conflicting revocations are rejected")
            c.execute("INSERT INTO revocations VALUES (?,?,?)",
                      (key, encoded, canonical_dumps(encode_revocation_record(record))))
            self._append_event(c, "revocation", key, encoded)
            return record

    def revocations_for(self, coordinate: PolicyCoordinate) -> tuple[PolicyRevocationRecord, ...]:
        if not isinstance(coordinate, PolicyCoordinate):
            return ()
        row = self._read().execute("SELECT payload_json FROM revocations WHERE coordinate_key=?",
                                   (coordinate_key(coordinate),)).fetchone()
        return (decode_revocation_record(json.loads(row[0])),) if row else ()

    # ------------------------------------------------------------------
    # Supersession (`ACC-LC-IA-2`)
    # ------------------------------------------------------------------
    def append_issuance_with_supersession(
        self, record: IssuedPolicyRecord, supersession: PolicySupersessionRecord,
    ) -> tuple[IssuedPolicyRecord, PolicySupersessionRecord]:
        """Both rows in one transaction: either both commit or neither does."""

        if not isinstance(supersession, PolicySupersessionRecord):
            raise PolicyRegistryConflictError(
                "append_issuance_with_supersession requires a PolicySupersessionRecord")
        if supersession.successor_coordinate != record.coordinate:
            raise PolicyRegistryConflictError(
                "the supersession record's successor must be the record being issued")
        with self._tx() as c:
            issued = self._append_issuance_in(c, record)
            stored = self._append_supersession_in(c, supersession)
            return issued, stored

    def append_supersession(self, record: PolicySupersessionRecord) -> PolicySupersessionRecord:
        if not isinstance(record, PolicySupersessionRecord):
            raise PolicyRegistryConflictError("append_supersession requires a PolicySupersessionRecord")
        with self._tx() as c:
            return self._append_supersession_in(c, record)

    def _append_supersession_in(self, c: sqlite3.Connection,
                                record: PolicySupersessionRecord) -> PolicySupersessionRecord:
        coordinate = record.coordinate
        key = coordinate_key(coordinate)
        encoded = canonical_bytes(record)
        row = c.execute("SELECT record_bytes, payload_json FROM supersessions WHERE predecessor_key=?",
                        (key,)).fetchone()
        if row is not None:
            if bytes(row[0]) == encoded:
                return decode_supersession_record(json.loads(row[1]))
            raise PolicyRegistryConflictError(
                f"a different supersession record already targets "
                f"{coordinate.policy_id}@{coordinate.version}; a version cannot be "
                "superseded twice by different successors")
        c.execute("INSERT INTO supersessions VALUES (?,?,?,?)",
                  (key, coordinate_key(record.successor_coordinate), encoded,
                   canonical_dumps(encode_supersession_record(record))))
        self._append_event(c, "supersession", key, encoded)
        return record

    def supersessions_for(self, coordinate: PolicyCoordinate) -> tuple[PolicySupersessionRecord, ...]:
        if not isinstance(coordinate, PolicyCoordinate):
            return ()
        row = self._read().execute("SELECT payload_json FROM supersessions WHERE predecessor_key=?",
                                   (coordinate_key(coordinate),)).fetchone()
        return (decode_supersession_record(json.loads(row[0])),) if row else ()

