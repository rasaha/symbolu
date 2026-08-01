"""Durable audit reference store (§6) — SQLite append-only, hash-linked.

A reference **durable** implementation behind the same shape as the in-memory
``AuditLog``: append-only, hash-linked (tamper-evident), tenant-partitioned,
schema-versioned, and recoverable after restart. It uses SQLite append-only event
semantics (stdlib ``sqlite3``); a Postgres-compatible adapter could implement the
same interface.

This is a durable-interface reference, not production-grade storage validation
(see evidence discipline). The term used is **tamper-evident** (the hash chain
detects modification); it is not *tamper-proof*.

Retained regardless of active-risk decay: raw events, finding records,
provider-evidence records, recipe/policy versions, and lifecycle/reset/closure/
eviction/state-limit records. Active-risk decay never deletes raw evidence;
administrative reset appends an immutable event and deletes nothing.
"""

from __future__ import annotations

import sqlite3

from .canonical import canonical_bytes, digest

SCHEMA_VERSION = "ctd.audit/1.0.0"
_GENESIS = "sha-256:" + "0" * 64


class DurableAuditLog:
    """SQLite-backed append-only, hash-chained audit log."""

    def __init__(self, path: str = ":memory:"):
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()
        self._last_digest = self._load_last_digest()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                seq INTEGER PRIMARY KEY,
                kind TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                assembly_key TEXT NOT NULL,
                event_id TEXT NOT NULL,
                prev_digest TEXT NOT NULL,
                record_digest TEXT NOT NULL,
                detail_json TEXT NOT NULL
            )
        """)
        # append-only guard: forbid UPDATE/DELETE on audit_events
        cur.execute("""
            CREATE TRIGGER IF NOT EXISTS audit_no_update
            BEFORE UPDATE ON audit_events
            BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END
        """)
        cur.execute("""
            CREATE TRIGGER IF NOT EXISTS audit_no_delete
            BEFORE DELETE ON audit_events
            BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tenant_asm ON audit_events "
                    "(tenant_id, assembly_key)")
        cur.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
                    (SCHEMA_VERSION,))
        self._conn.commit()

    def _load_last_digest(self) -> str:
        row = self._conn.execute(
            "SELECT record_digest FROM audit_events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else _GENESIS

    def schema_version(self) -> str:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return row[0] if row else ""

    def append(self, kind: str, *, tenant_id: str = "", assembly_key: str = "",
               event_id: str = "", detail: dict | None = None):
        detail = detail or {}
        seq = self._next_seq()
        body = {"seq": seq, "kind": kind, "tenant_id": tenant_id,
                "assembly_key": assembly_key, "event_id": event_id,
                "prev_digest": self._last_digest, "detail": detail}
        rec_digest = digest(body, domain="CTD-AUDIT")
        self._conn.execute(
            "INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?)",
            (seq, kind, tenant_id, assembly_key, event_id, self._last_digest,
             rec_digest, canonical_bytes(detail).decode("utf-8")))
        self._conn.commit()
        self._last_digest = rec_digest
        return _Row(seq, kind, tenant_id, assembly_key, event_id,
                    self._last_digest, rec_digest, detail)

    def _next_seq(self) -> int:
        row = self._conn.execute("SELECT COALESCE(MAX(seq),-1)+1 FROM audit_events"
                                 ).fetchone()
        return int(row[0])

    def __len__(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0])

    def all(self) -> list:
        return [self._row(r) for r in self._conn.execute(
            "SELECT * FROM audit_events ORDER BY seq")]

    def for_assembly(self, tenant_id: str, assembly_key: str) -> list:
        return [self._row(r) for r in self._conn.execute(
            "SELECT * FROM audit_events WHERE tenant_id=? AND assembly_key=? "
            "ORDER BY seq", (tenant_id, assembly_key))]

    def raw_events(self) -> list[dict]:
        """RAW_EVIDENCE records in order (for deterministic replay recovery)."""
        return [r.detail | {"tenant_id": r.tenant_id, "assembly_key": r.assembly_key,
                            "event_id": r.event_id}
                for r in self.all() if r.kind == "RAW_EVIDENCE"]

    def verify_chain(self) -> bool:
        prev = _GENESIS
        for r in self.all():
            body = {"seq": r.seq, "kind": r.kind, "tenant_id": r.tenant_id,
                    "assembly_key": r.assembly_key, "event_id": r.event_id,
                    "prev_digest": prev, "detail": r.detail}
            if digest(body, domain="CTD-AUDIT") != r.record_digest:
                return False
            prev = r.record_digest
        return True

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row(r):
        import json
        return _Row(r[0], r[1], r[2], r[3], r[4], r[5], r[6], json.loads(r[7]))


class _Row:
    __slots__ = ("seq", "kind", "tenant_id", "assembly_key", "event_id",
                 "prev_digest", "record_digest", "detail")

    def __init__(self, seq, kind, tenant_id, assembly_key, event_id,
                 prev_digest, record_digest, detail):
        self.seq, self.kind, self.tenant_id = seq, kind, tenant_id
        self.assembly_key, self.event_id = assembly_key, event_id
        self.prev_digest, self.record_digest, self.detail = (
            prev_digest, record_digest, detail)

    def to_dict(self) -> dict:
        return {"seq": self.seq, "kind": self.kind, "tenant_id": self.tenant_id,
                "assembly_key": self.assembly_key, "event_id": self.event_id,
                "prev_digest": self.prev_digest, "record_digest": self.record_digest,
                "detail": self.detail}
