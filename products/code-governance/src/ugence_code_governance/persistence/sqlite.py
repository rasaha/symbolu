"""DURABLE_SHADOW_REFERENCE store — stdlib sqlite3, append-only, hash-linked.

Local, deterministic, transactional, restart-safe, tenant-aware, append-oriented,
integrity-verifiable, dependency-light. It is **not** a production enforcement
store, an authoritative execution ledger, a distributed transaction system, or a
high-availability database. No external database dependency is introduced.

Pattern adapted (not copied) from the StoryGraph ``DurableAuditLog`` reference:
WAL mode, append-only triggers, hash-linked records/events, schema-versioned meta,
tenant partitioning, restart recovery.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

from .envelope import RecordEnvelope, WorkflowEventRecord
from .errors import (
    EventChainError,
    InjectedFailure,
    IntegrityFailure,
    RecordCollisionError,
    SchemaIncompatibleError,
    TenantIsolationError,
)
from .schema import (
    FINGERPRINT_DOMAIN_VERSION,
    GENESIS,
    SERIALIZATION_VERSION,
    STORE_CLASSIFICATION,
    STORE_SCHEMA_VERSION,
)
from .serialization import canonical_json, loads


@dataclass(frozen=True)
class DurableStoreConfig:
    """Configuration for a durable shadow store."""

    path: str = ":memory:"
    application_version: str = "0.2.0"
    wal: bool = True


class DurableShadowStore:
    """A local, append-only, integrity-verified durable shadow store."""

    classification = STORE_CLASSIFICATION

    def __init__(self, config: Optional[DurableStoreConfig] = None) -> None:
        self._config = config or DurableStoreConfig()
        self._conn = sqlite3.connect(self._config.path)
        self._conn.row_factory = sqlite3.Row
        if self._config.wal and self._config.path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        #: deterministic failure-injection point (tests only): a boundary label.
        self._inject_at: Optional[str] = None
        self._init_schema()

    # --- schema ----------------------------------------------------------
    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS store_meta (key TEXT PRIMARY KEY, value TEXT)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS records (
                tenant_id TEXT NOT NULL,
                record_id TEXT NOT NULL,
                record_type TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                workflow_id TEXT NOT NULL,
                workflow_revision_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                canonical_payload TEXT NOT NULL,
                payload_fingerprint TEXT NOT NULL,
                previous_record_fingerprint TEXT,
                envelope_fingerprint TEXT NOT NULL,
                stored_at INTEGER,
                PRIMARY KEY (tenant_id, record_id)
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                tenant_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                workflow_id TEXT NOT NULL,
                workflow_revision_id TEXT NOT NULL,
                previous_event_fingerprint TEXT NOT NULL,
                from_state TEXT NOT NULL,
                to_state TEXT NOT NULL,
                event_type TEXT NOT NULL,
                referenced_record_ids TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                event_fingerprint TEXT NOT NULL,
                seq INTEGER,
                PRIMARY KEY (tenant_id, event_id)
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workflow_index (
                tenant_id TEXT NOT NULL,
                workflow_revision_id TEXT NOT NULL,
                workflow_id TEXT NOT NULL,
                current_state TEXT NOT NULL,
                chain_id TEXT,
                last_event_fingerprint TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, workflow_revision_id)
            )""")
        # Append-only tamper-evidence on the canonical historical tables.
        cur.execute("""CREATE TRIGGER IF NOT EXISTS records_no_update
            BEFORE UPDATE ON records BEGIN
            SELECT RAISE(ABORT, 'records are append-only'); END""")
        cur.execute("""CREATE TRIGGER IF NOT EXISTS records_no_delete
            BEFORE DELETE ON records BEGIN
            SELECT RAISE(ABORT, 'records are append-only'); END""")
        cur.execute("""CREATE TRIGGER IF NOT EXISTS events_no_update
            BEFORE UPDATE ON events BEGIN
            SELECT RAISE(ABORT, 'events are append-only'); END""")
        cur.execute("""CREATE TRIGGER IF NOT EXISTS events_no_delete
            BEFORE DELETE ON events BEGIN
            SELECT RAISE(ABORT, 'events are append-only'); END""")
        # Store metadata (initialize once; validate on reopen).
        existing = dict(cur.execute("SELECT key, value FROM store_meta").fetchall())
        if not existing:
            meta = {
                "schema_version": STORE_SCHEMA_VERSION,
                "serialization_version": SERIALIZATION_VERSION,
                "fingerprint_domain_version": FINGERPRINT_DOMAIN_VERSION,
                "application_version": self._config.application_version,
                "classification": STORE_CLASSIFICATION,
                "created_at": "deterministic",
            }
            cur.executemany("INSERT INTO store_meta (key, value) VALUES (?, ?)", list(meta.items()))
        else:
            self._validate_schema(existing)
        self._conn.commit()

    def _validate_schema(self, meta: Mapping[str, str]) -> None:
        stored = meta.get("schema_version")
        if stored != STORE_SCHEMA_VERSION:
            raise SchemaIncompatibleError(
                f"store schema {stored!r} != supported {STORE_SCHEMA_VERSION!r}")

    @property
    def schema_version(self) -> str:
        return STORE_SCHEMA_VERSION

    def store_meta(self) -> Dict[str, str]:
        rows = self._conn.execute("SELECT key, value FROM store_meta").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def health_check(self) -> Dict[str, object]:
        meta = self.store_meta()
        return {
            "ok": meta.get("schema_version") == STORE_SCHEMA_VERSION,
            "schema_version": meta.get("schema_version"),
            "classification": STORE_CLASSIFICATION,
            "record_count": self._conn.execute("SELECT COUNT(*) c FROM records").fetchone()["c"],
            "event_count": self._conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"],
        }

    # --- failure injection (tests only) ---------------------------------
    def _maybe_inject(self, boundary: str) -> None:
        if self._inject_at == boundary:
            raise InjectedFailure(f"injected failure at boundary {boundary!r}")

    # --- read ------------------------------------------------------------
    def get_record(self, tenant_id: str, record_id: str) -> Optional[RecordEnvelope]:
        row = self._conn.execute(
            "SELECT * FROM records WHERE tenant_id=? AND record_id=?",
            (tenant_id, record_id)).fetchone()
        return self._row_to_envelope(row) if row else None

    def list_for_workflow(self, tenant_id: str, workflow_id: str) -> Tuple[RecordEnvelope, ...]:
        rows = self._conn.execute(
            "SELECT * FROM records WHERE tenant_id=? AND workflow_id=? ORDER BY record_id",
            (tenant_id, workflow_id)).fetchall()
        return tuple(self._row_to_envelope(r) for r in rows)

    def list_for_revision(self, tenant_id: str, revision_id: str) -> Tuple[RecordEnvelope, ...]:
        rows = self._conn.execute(
            "SELECT * FROM records WHERE tenant_id=? AND workflow_revision_id=? ORDER BY record_id",
            (tenant_id, revision_id)).fetchall()
        return tuple(self._row_to_envelope(r) for r in rows)

    def events_for_workflow(self, tenant_id: str, workflow_id: str) -> Tuple[WorkflowEventRecord, ...]:
        rows = self._conn.execute(
            "SELECT * FROM events WHERE tenant_id=? AND workflow_id=? ORDER BY seq",
            (tenant_id, workflow_id)).fetchall()
        return tuple(self._row_to_event(r) for r in rows)

    def get_index(self, tenant_id: str, revision_id: str) -> Optional[Dict[str, object]]:
        row = self._conn.execute(
            "SELECT * FROM workflow_index WHERE tenant_id=? AND workflow_revision_id=?",
            (tenant_id, revision_id)).fetchone()
        return dict(row) if row else None

    def revisions_for(self, tenant_id: str, workflow_id: str) -> Tuple[Dict[str, object], ...]:
        rows = self._conn.execute(
            "SELECT * FROM workflow_index WHERE tenant_id=? AND workflow_id=? ORDER BY workflow_revision_id",
            (tenant_id, workflow_id)).fetchall()
        return tuple(dict(r) for r in rows)

    def _row_to_envelope(self, row: sqlite3.Row) -> RecordEnvelope:
        return RecordEnvelope(
            record_id=row["record_id"], record_type=row["record_type"],
            schema_version=row["schema_version"], tenant_id=row["tenant_id"],
            workflow_id=row["workflow_id"], workflow_revision_id=row["workflow_revision_id"],
            created_at=row["created_at"], canonical_payload=loads(row["canonical_payload"]),
            payload_fingerprint=row["payload_fingerprint"],
            previous_record_fingerprint=row["previous_record_fingerprint"],
            envelope_fingerprint=row["envelope_fingerprint"])

    def _row_to_event(self, row: sqlite3.Row) -> WorkflowEventRecord:
        return WorkflowEventRecord(
            event_id=row["event_id"], tenant_id=row["tenant_id"], workflow_id=row["workflow_id"],
            workflow_revision_id=row["workflow_revision_id"],
            previous_event_fingerprint=row["previous_event_fingerprint"],
            from_state=row["from_state"], to_state=row["to_state"], event_type=row["event_type"],
            referenced_record_ids=tuple(loads(row["referenced_record_ids"])),
            occurred_at=row["occurred_at"], event_fingerprint=row["event_fingerprint"])

    # --- atomic stage commit --------------------------------------------
    def commit_stage(
        self,
        *,
        tenant_id: str,
        workflow_id: str,
        revision_id: str,
        records: List[RecordEnvelope],
        event: WorkflowEventRecord,
        current_state: str,
        chain_id: Optional[str] = None,
    ) -> None:
        """Persist stage records + one workflow event + index update atomically.

        On any failure the whole stage rolls back — a stage never becomes visible
        as completed if a required record failed to persist. ``put_if_absent``
        semantics: an identical re-commit is idempotent; a conflicting id fails.
        """
        cur = self._conn.cursor()
        try:
            cur.execute("BEGIN")
            for env in records:
                self._put_if_absent(cur, env)
            self._maybe_inject("after_records")
            self._append_event(cur, event)
            self._maybe_inject("after_event")
            cur.execute(
                """INSERT INTO workflow_index
                   (tenant_id, workflow_revision_id, workflow_id, current_state, chain_id,
                    last_event_fingerprint, updated_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(tenant_id, workflow_revision_id) DO UPDATE SET
                     current_state=excluded.current_state, chain_id=excluded.chain_id,
                     last_event_fingerprint=excluded.last_event_fingerprint,
                     updated_at=excluded.updated_at""",
                (tenant_id, revision_id, workflow_id, current_state, chain_id,
                 event.event_fingerprint, event.occurred_at))
            self._maybe_inject("before_commit")
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def _put_if_absent(self, cur: sqlite3.Cursor, env: RecordEnvelope) -> None:
        row = cur.execute(
            "SELECT envelope_fingerprint FROM records WHERE tenant_id=? AND record_id=?",
            (env.tenant_id, env.record_id)).fetchone()
        if row is not None:
            if row["envelope_fingerprint"] == env.envelope_fingerprint:
                return  # idempotent: identical content already present
            raise RecordCollisionError(
                f"record {env.record_id} already exists with different content")
        cur.execute(
            """INSERT INTO records
               (tenant_id, record_id, record_type, schema_version, workflow_id,
                workflow_revision_id, created_at, canonical_payload, payload_fingerprint,
                previous_record_fingerprint, envelope_fingerprint, stored_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?, NULL)""",
            (env.tenant_id, env.record_id, env.record_type, env.schema_version, env.workflow_id,
             env.workflow_revision_id, env.created_at, canonical_json(env.canonical_payload),
             env.payload_fingerprint, env.previous_record_fingerprint, env.envelope_fingerprint))

    def _append_event(self, cur: sqlite3.Cursor, event: WorkflowEventRecord) -> None:
        row = cur.execute(
            "SELECT event_fingerprint FROM events WHERE tenant_id=? AND event_id=?",
            (event.tenant_id, event.event_id)).fetchone()
        if row is not None:
            if row["event_fingerprint"] == event.event_fingerprint:
                return
            raise RecordCollisionError(
                f"event {event.event_id} already exists with different content")
        # verify previous-event linkage (per tenant+workflow)
        last = cur.execute(
            "SELECT event_fingerprint FROM events WHERE tenant_id=? AND workflow_id=? "
            "ORDER BY seq DESC LIMIT 1", (event.tenant_id, event.workflow_id)).fetchone()
        expected_prev = last["event_fingerprint"] if last else GENESIS
        if event.previous_event_fingerprint != expected_prev:
            raise EventChainError(
                f"event {event.event_id} previous fingerprint mismatch "
                f"(expected {expected_prev[:12]}…)")
        seq_row = cur.execute("SELECT COALESCE(MAX(seq), 0)+1 AS n FROM events").fetchone()
        cur.execute(
            """INSERT INTO events
               (tenant_id, event_id, workflow_id, workflow_revision_id,
                previous_event_fingerprint, from_state, to_state, event_type,
                referenced_record_ids, occurred_at, event_fingerprint, seq)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (event.tenant_id, event.event_id, event.workflow_id, event.workflow_revision_id,
             event.previous_event_fingerprint, event.from_state, event.to_state,
             event.event_type, canonical_json(list(event.referenced_record_ids)),
             event.occurred_at, event.event_fingerprint, seq_row["n"]))

    def last_event_fingerprint(self, tenant_id: str, workflow_id: str) -> str:
        row = self._conn.execute(
            "SELECT event_fingerprint FROM events WHERE tenant_id=? AND workflow_id=? "
            "ORDER BY seq DESC LIMIT 1", (tenant_id, workflow_id)).fetchone()
        return row["event_fingerprint"] if row else GENESIS

    # --- integrity verification -----------------------------------------
    def verify_records(self, tenant_id: str, workflow_id: str) -> None:
        for env in self.list_for_workflow(tenant_id, workflow_id):
            if env.tenant_id != tenant_id:
                raise TenantIsolationError("record tenant mismatch")
            if not env.recompute_and_verify():
                raise IntegrityFailure(f"record {env.record_id} fingerprint mismatch")

    def verify_event_chain(self, tenant_id: str, workflow_id: str) -> None:
        prev = GENESIS
        for ev in self.events_for_workflow(tenant_id, workflow_id):
            if ev.tenant_id != tenant_id:
                raise TenantIsolationError("event tenant mismatch")
            if ev.previous_event_fingerprint != prev:
                raise EventChainError(f"event {ev.event_id} broken previous linkage")
            if ev.recompute() != ev.event_fingerprint:
                raise EventChainError(f"event {ev.event_id} fingerprint mismatch")
            prev = ev.event_fingerprint

    # --- lifecycle -------------------------------------------------------
    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "DurableShadowStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def open_durable_store(path: str = ":memory:", *, application_version: str = "0.2.0") -> DurableShadowStore:
    """Open (creating if needed) a durable shadow store, validating its schema."""
    return DurableShadowStore(DurableStoreConfig(path=path, application_version=application_version))


__all__ = ["DurableStoreConfig", "DurableShadowStore", "open_durable_store"]
