#!/usr/bin/env python3
"""Session-scoped external ephemeral key-value table (SQLite reference backend).

Stores EXPLICIT fact records only — never model hidden states, slot tensors, gradients, answer labels,
evaluation ground truth, or arbitrary prompts. All interactions happen OUTSIDE the model at write /
query time. Provides deterministic identity, session/tenant isolation, TTL expiry, versioning,
deletion, provenance, and bounded overhead. Stdlib only (sqlite3), so it is available everywhere.

The model is never trained against this table and its weights/gradients are never touched here.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

SCHEMA = """
CREATE TABLE IF NOT EXISTS ephemeral_memory (
    session_id          TEXT NOT NULL,
    tenant_id           TEXT NOT NULL,
    memory_key          TEXT NOT NULL,
    fact_or_entity_id   TEXT NOT NULL,
    typed_value         TEXT NOT NULL,
    value_type          TEXT NOT NULL,
    source_event_id     TEXT NOT NULL,
    evidence_reference  TEXT NOT NULL,
    version             INTEGER NOT NULL,
    created_at          REAL NOT NULL,
    expires_at          REAL NOT NULL,
    authorization_scope TEXT NOT NULL,
    deleted             INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, tenant_id, memory_key, version)
);
"""

FORBIDDEN_VALUE_MARKERS = ("hidden_state", "slot_tensor", "gradient", "ground_truth", "answer_label")


@dataclass
class LookupResult:
    found: bool
    typed_value: str = None
    version: int = None
    provenance: dict = None
    reason: str = None


class TableUnavailable(Exception):
    pass


class UnauthorizedLookup(Exception):
    pass


class EphemeralTable:
    def __init__(self, path=":memory:", clock=None, read_latency_s=0.0, available=True):
        self._clock = clock or time.time
        self._read_latency = read_latency_s
        self._available = available
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self.ops = {"writes": 0, "reads": 0, "bytes_written": 0}

    # ------------------------------------------------------------------ lifecycle helpers
    def set_available(self, available: bool):
        self._available = available

    def _now(self):
        return self._clock()

    def _guard(self):
        if not self._available:
            raise TableUnavailable("ephemeral table unavailable")

    # ------------------------------------------------------------------ write path
    def write_fact(self, *, session_id, tenant_id, memory_key, fact_or_entity_id, typed_value,
                   value_type, source_event_id, evidence_reference, authorization_scope, ttl_s):
        """Write an EXPLICIT fact record. Auto-increments version for an existing key. Rejects any
        attempt to store forbidden content (hidden states / tensors / gradients / labels)."""
        self._guard()
        for bad in FORBIDDEN_VALUE_MARKERS:
            if bad in str(value_type).lower() or bad in str(typed_value).lower():
                raise ValueError(f"refusing to store forbidden content: {bad}")
        now = self._now()
        cur = self._conn.execute(
            "SELECT COALESCE(MAX(version),0) FROM ephemeral_memory WHERE session_id=? AND tenant_id=? AND memory_key=?",
            (session_id, tenant_id, memory_key))
        version = int(cur.fetchone()[0]) + 1
        row = (session_id, tenant_id, memory_key, str(fact_or_entity_id), str(typed_value), str(value_type),
               str(source_event_id), str(evidence_reference), version, now, now + float(ttl_s),
               str(authorization_scope), 0)
        self._conn.execute(
            "INSERT INTO ephemeral_memory VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
        self._conn.commit()
        self.ops["writes"] += 1
        self.ops["bytes_written"] += sum(len(str(x).encode()) for x in row)
        return version

    # ------------------------------------------------------------------ query path
    def lookup(self, *, session_id, tenant_id, memory_key, authorization_scope, requested_version=None):
        """Deterministic lookup scoped to (session, tenant). Returns the latest non-deleted, non-expired
        version by default (or a specific version). Enforces isolation, TTL, deletion, and auth scope.
        Never returns cross-session or cross-tenant rows."""
        self._guard()
        if self._read_latency:
            time.sleep(self._read_latency)
        self.ops["reads"] += 1
        now = self._now()
        q = ("SELECT typed_value, value_type, version, source_event_id, evidence_reference, expires_at, "
             "authorization_scope, deleted FROM ephemeral_memory "
             "WHERE session_id=? AND tenant_id=? AND memory_key=?")
        params = [session_id, tenant_id, memory_key]
        if requested_version is not None:
            q += " AND version=?"
            params.append(int(requested_version))
        q += " ORDER BY version DESC"
        for (tv, vt, ver, sev, evref, exp, scope, deleted) in self._conn.execute(q, params):
            if deleted:
                continue
            if exp <= now:
                continue
            if authorization_scope != scope:
                raise UnauthorizedLookup(f"scope mismatch for {memory_key}")
            return LookupResult(True, typed_value=tv, version=ver, provenance={
                "source_event_id": sev, "evidence_reference": evref, "version": ver,
                "value_type": vt, "authorization_scope": scope, "fallback_used": True,
                "session_id": session_id, "tenant_id": tenant_id, "memory_key": memory_key})
        return LookupResult(False, reason="missing_or_expired_or_deleted")

    def delete(self, *, session_id, tenant_id, memory_key, version=None):
        self._guard()
        if version is None:
            self._conn.execute("UPDATE ephemeral_memory SET deleted=1 WHERE session_id=? AND tenant_id=? AND memory_key=?",
                               (session_id, tenant_id, memory_key))
        else:
            self._conn.execute("UPDATE ephemeral_memory SET deleted=1 WHERE session_id=? AND tenant_id=? AND memory_key=? AND version=?",
                               (session_id, tenant_id, memory_key, int(version)))
        self._conn.commit()

    def cleanup_session(self, session_id):
        """Session-completion cleanup: remove all rows for a session (deterministic lifecycle end)."""
        self._guard()
        t0 = time.time()
        self._conn.execute("DELETE FROM ephemeral_memory WHERE session_id=?", (session_id,))
        self._conn.commit()
        return time.time() - t0

    def peak_size_bytes(self):
        cur = self._conn.execute("SELECT COALESCE(SUM(LENGTH(typed_value)+LENGTH(memory_key)+LENGTH(evidence_reference)),0) FROM ephemeral_memory")
        return int(cur.fetchone()[0])

    def row_count(self):
        return int(self._conn.execute("SELECT COUNT(*) FROM ephemeral_memory").fetchone()[0])

    def close(self):
        self._conn.close()
