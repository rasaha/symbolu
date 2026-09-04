"""Single-node durable persistence on stdlib ``sqlite3`` (ADR durable persistence, D-1 … D-4).

One file holds every Risk Authority store: cases, decisions, envelopes, grants, control
results, evidence, governance events, revocation state and the id counters. Every write
runs inside ``BEGIN IMMEDIATE`` (one writer at a time across processes on one host), the
journal is WAL, and every write also lands in one append-only, hash-linked
``ledger_events`` table so tampering with a stored record or with history is detectable by
:meth:`SqliteRiskAuthorityStore.verify_chain`. The shape copies Policy Authority's
``registry_sqlite.py`` and the storygraph durable audit without importing either.

**Identity (D-3).** Immutable artifacts — decisions, envelopes, evidence, governance
events — refuse an id that already exists with :class:`PersistenceConflictError`. Cases
are mutable aggregates saved on every transition, so a re-save under the same id is an
update *of the same aggregate*: the stored identity fields (tenant, subject, workflow
digest, creation instant) must match or the save is refused. Grants and control results
are replaced, as their ports specify. The id allocator is a durable counter, so a
restarted process never re-mints an id.

**Revocation (D-4).** Epoch advances and revocations are appended as rows and
:class:`SqliteRevocationState` rebuilds the hot-path predicate on open.

**No clock.** Nothing here reads time. Records carry their own instants; the ledger orders
by sequence and links by digest.

**Production posture (D-5).** Every adapter declares ``is_production_authoritative``
``True`` only for a file-backed store; an in-memory SQLite database is process-local like
the reference dicts and is refused by a production application.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from ..crypto.canonical import canonical_bytes, canonical_dumps
from ..crypto.hashing import sha256_hex
from ..domain.authority import AuthorityGrant
from ..domain.controls import ControlResult
from ..domain.decision import RiskDecision
from ..domain.envelope import RiskAuthorizationEnvelope
from ..domain.events import GovernanceEvent
from ..domain.evidence import ControlEvidenceRecord
from ..domain.risk_case import RiskDecisionCase
from ..services.revocation import RevocationState
from .codec import (
    decode_case,
    decode_envelope,
    decode_record,
    encode_case,
    encode_envelope,
    encode_record,
)
from .errors import PersistenceConflictError, PersistenceStorageError

__all__ = [
    "SQLITE_STORE_SCHEMA_VERSION",
    "SqliteRiskAuthorityStore",
    "SqliteRevocationState",
    "SqliteIdAllocator",
]

SQLITE_STORE_SCHEMA_VERSION = "risk-authority-sqlite-1"
_GENESIS = "sha256:" + "0" * 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS risk_cases (
    tenant_id TEXT NOT NULL, case_id TEXT NOT NULL, version INTEGER NOT NULL,
    record_json TEXT NOT NULL, PRIMARY KEY (tenant_id, case_id));
CREATE TABLE IF NOT EXISTS risk_decisions (
    tenant_id TEXT NOT NULL, decision_id TEXT NOT NULL, record_json TEXT NOT NULL,
    PRIMARY KEY (tenant_id, decision_id));
CREATE TABLE IF NOT EXISTS envelopes (
    tenant_id TEXT NOT NULL, envelope_id TEXT NOT NULL, record_json TEXT NOT NULL,
    PRIMARY KEY (tenant_id, envelope_id));
CREATE TABLE IF NOT EXISTS authority_grants (
    tenant_id TEXT NOT NULL, principal_id TEXT NOT NULL, record_json TEXT NOT NULL,
    PRIMARY KEY (tenant_id, principal_id));
CREATE TABLE IF NOT EXISTS control_results (
    tenant_id TEXT NOT NULL, case_id TEXT NOT NULL, record_json TEXT NOT NULL,
    PRIMARY KEY (tenant_id, case_id));
CREATE TABLE IF NOT EXISTS evidence (
    tenant_id TEXT NOT NULL, evidence_id TEXT NOT NULL, record_json TEXT NOT NULL,
    PRIMARY KEY (tenant_id, evidence_id));
CREATE TABLE IF NOT EXISTS governance_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL, event_id TEXT NOT NULL,
    aggregate_id TEXT NOT NULL, record_json TEXT NOT NULL, UNIQUE (tenant_id, event_id));
CREATE TABLE IF NOT EXISTS revocation_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL, kind TEXT NOT NULL,
    target TEXT NOT NULL, epoch INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS id_counters (prefix TEXT PRIMARY KEY, value INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS ledger_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, subject_key TEXT NOT NULL,
    record_digest TEXT NOT NULL, prev_digest TEXT NOT NULL, chain_digest TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger_events
    BEGIN SELECT RAISE(ABORT, 'ledger_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger_events
    BEGIN SELECT RAISE(ABORT, 'ledger_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS gov_no_update BEFORE UPDATE ON governance_events
    BEGIN SELECT RAISE(ABORT, 'governance_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS gov_no_delete BEFORE DELETE ON governance_events
    BEGIN SELECT RAISE(ABORT, 'governance_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS rev_no_update BEFORE UPDATE ON revocation_events
    BEGIN SELECT RAISE(ABORT, 'revocation_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS rev_no_delete BEFORE DELETE ON revocation_events
    BEGIN SELECT RAISE(ABORT, 'revocation_events is append-only'); END;
"""

#: Which table and key column each ledger kind names, and whether the row may be replaced.
_LEDGER_TABLES: dict[str, tuple[str, str, bool]] = {
    "case": ("risk_cases", "case_id", True),
    "decision": ("risk_decisions", "decision_id", False),
    "envelope": ("envelopes", "envelope_id", False),
    "grant": ("authority_grants", "principal_id", True),
    "controls": ("control_results", "case_id", True),
    "evidence": ("evidence", "evidence_id", False),
    "event": ("governance_events", "event_id", False),
    "revocation": ("revocation_events", "seq", False),
}

#: The immutable identity of a case aggregate: a re-save that changes any of these is
#: another aggregate wearing a stored id, and is refused (D-3).
_CASE_IDENTITY = ("tenant_id", "case_id", "subject_id", "workflow_ir_digest", "created_at")


def _is_memory(path: str) -> bool:
    return path == ":memory:" or path.startswith("file::memory:")


class SqliteRiskAuthorityStore:
    """Open (or create) one durable Risk Authority store and expose its adapters."""

    def __init__(self, path: str, *, busy_timeout_ms: int = 5000) -> None:
        if not isinstance(path, str) or not path:
            raise PersistenceStorageError("SqliteRiskAuthorityStore requires a path")
        self.path = path
        self._durable = not _is_memory(path)
        try:
            self._conn: Optional[sqlite3.Connection] = sqlite3.connect(
                path, isolation_level=None, check_same_thread=False, timeout=busy_timeout_ms / 1000
            )
            self._conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
            if self._durable:
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
            with self._tx() as c:
                row = c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
                if row is None:
                    c.execute("INSERT INTO meta VALUES ('schema_version', ?)",
                              (SQLITE_STORE_SCHEMA_VERSION,))
                elif row[0] != SQLITE_STORE_SCHEMA_VERSION:
                    raise PersistenceStorageError(
                        f"store schema {row[0]!r} is not {SQLITE_STORE_SCHEMA_VERSION!r}")
        except sqlite3.Error as exc:
            raise PersistenceStorageError(str(exc)) from exc
        self.cases = _CaseRepository(self)
        self.decisions = _DecisionRepository(self)
        self.envelopes = _EnvelopeRepository(self)
        self.authority = _AuthorityRegistry(self)
        self.controls = _ControlResultRepository(self)
        self.evidence = _EvidenceRepository(self)
        self.events = _GovernanceEventStore(self)
        self.ids = SqliteIdAllocator(self)
        self.revocation = SqliteRevocationState(self)

    # ------------------------------------------------------------------ posture
    @property
    def is_production_authoritative(self) -> bool:
        """``True`` for a file-backed store; an in-memory database is not durable."""

        return self._durable

    # ------------------------------------------------------------------ plumbing
    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _c(self) -> sqlite3.Connection:
        if self._conn is None:
            raise PersistenceStorageError("store closed")
        return self._conn

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = self._c()
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            raise PersistenceStorageError(str(exc)) from exc
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")

    def _append_ledger(self, c: sqlite3.Connection, kind: str, subject_key: str,
                       record_bytes: bytes) -> None:
        prev = c.execute("SELECT chain_digest FROM ledger_events ORDER BY seq DESC LIMIT 1").fetchone()
        prev_digest = prev[0] if prev else _GENESIS
        record_digest = sha256_hex(record_bytes)
        chain = sha256_hex(canonical_bytes(
            {"kind": kind, "subject_key": subject_key, "record_digest": record_digest,
             "prev_digest": prev_digest}))
        c.execute("INSERT INTO ledger_events (kind, subject_key, record_digest, prev_digest, "
                  "chain_digest) VALUES (?,?,?,?,?)",
                  (kind, subject_key, record_digest, prev_digest, chain))

    def _insert_once(self, table: str, kind: str, tenant_id: str, id_column: str, id_value: str,
                     record_json: str, extra: Optional[dict] = None) -> None:
        columns = ["tenant_id", id_column, "record_json"] + list((extra or {}).keys())
        values = [tenant_id, id_value, record_json] + list((extra or {}).values())
        with self._tx() as c:
            try:
                c.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES "
                          f"({', '.join('?' for _ in columns)})", values)
            except sqlite3.IntegrityError as exc:
                raise PersistenceConflictError(
                    f"{table}: {id_column} {id_value!r} already exists for tenant {tenant_id!r} "
                    "(a durable store never overwrites an authority artifact)") from exc
            self._append_ledger(c, kind, f"{tenant_id}/{id_value}", record_json.encode("utf-8"))

    def _replace(self, table: str, kind: str, tenant_id: str, id_column: str, id_value: str,
                 record_json: str) -> None:
        with self._tx() as c:
            c.execute(f"INSERT INTO {table} (tenant_id, {id_column}, record_json) VALUES (?,?,?) "
                      f"ON CONFLICT(tenant_id, {id_column}) DO UPDATE SET record_json=excluded.record_json",
                      (tenant_id, id_value, record_json))
            self._append_ledger(c, kind, f"{tenant_id}/{id_value}", record_json.encode("utf-8"))

    def _load(self, table: str, tenant_id: str, id_column: str, id_value: str) -> Optional[Any]:
        try:
            row = self._c().execute(
                f"SELECT record_json FROM {table} WHERE tenant_id=? AND {id_column}=?",
                (tenant_id, id_value)).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceStorageError(str(exc)) from exc
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except ValueError as exc:
            raise PersistenceStorageError(f"{table}: stored record is not JSON") from exc

    # ------------------------------------------------------------------ integrity
    def verify_chain(self) -> bool:
        """Recompute the hash chain and check every current record against its last entry."""

        c = self._c()
        prev = _GENESIS
        latest: dict[tuple[str, str], str] = {}
        for kind, subject_key, record_digest, prev_digest, chain in c.execute(
                "SELECT kind, subject_key, record_digest, prev_digest, chain_digest "
                "FROM ledger_events ORDER BY seq"):
            if prev_digest != prev or kind not in _LEDGER_TABLES:
                return False
            expected = sha256_hex(canonical_bytes(
                {"kind": kind, "subject_key": subject_key, "record_digest": record_digest,
                 "prev_digest": prev_digest}))
            if expected != chain:
                return False
            latest[(kind, subject_key)] = record_digest
            prev = chain
        for (kind, subject_key), record_digest in latest.items():
            table, column, _ = _LEDGER_TABLES[kind]
            tenant_id, _, id_value = subject_key.partition("/")
            if kind == "revocation":
                row = c.execute("SELECT tenant_id, kind, target, epoch FROM revocation_events "
                                "WHERE seq=?", (int(id_value),)).fetchone()
                stored = canonical_bytes({"tenant_id": row[0], "kind": row[1], "target": row[2],
                                          "epoch": row[3]}) if row else None
            else:
                row = c.execute(f"SELECT record_json FROM {table} WHERE tenant_id=? AND {column}=?",
                                (tenant_id, id_value)).fetchone()
                stored = row[0].encode("utf-8") if row else None
            if stored is None or sha256_hex(stored) != record_digest:
                return False
        return True

    def ledger_length(self) -> int:
        return int(self._c().execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0])


class _Adapter:
    def __init__(self, store: SqliteRiskAuthorityStore) -> None:
        self._store = store

    @property
    def is_production_authoritative(self) -> bool:
        return self._store.is_production_authoritative


class _CaseRepository(_Adapter):
    def save(self, case: RiskDecisionCase) -> None:
        encoded = encode_case(case)
        record_json = canonical_dumps(encoded)
        with self._store._tx() as c:
            row = c.execute("SELECT version, record_json FROM risk_cases WHERE tenant_id=? AND case_id=?",
                            (case.tenant_id, case.case_id)).fetchone()
            if row is None:
                c.execute("INSERT INTO risk_cases (tenant_id, case_id, version, record_json) "
                          "VALUES (?,?,1,?)", (case.tenant_id, case.case_id, record_json))
            else:
                stored = json.loads(row[1])
                if any(stored.get(k) != encoded.get(k) for k in _CASE_IDENTITY):
                    raise PersistenceConflictError(
                        f"risk_cases: case {case.case_id!r} already exists for tenant "
                        f"{case.tenant_id!r} with a different identity; a durable store never "
                        "lets one aggregate wear another's id")
                if len(encoded.get("events", ())) < len(stored.get("events", ())):
                    raise PersistenceConflictError(
                        f"risk_cases: case {case.case_id!r} would lose recorded events")
                c.execute("UPDATE risk_cases SET version=?, record_json=? WHERE tenant_id=? AND case_id=?",
                          (int(row[0]) + 1, record_json, case.tenant_id, case.case_id))
            self._store._append_ledger(c, "case", f"{case.tenant_id}/{case.case_id}",
                                       record_json.encode("utf-8"))

    def get(self, tenant_id: str, case_id: str) -> Optional[RiskDecisionCase]:
        raw = self._store._load("risk_cases", tenant_id, "case_id", case_id)
        return None if raw is None else decode_case(raw)


class _DecisionRepository(_Adapter):
    def save(self, decision: RiskDecision) -> None:
        if not isinstance(decision, RiskDecision):
            raise PersistenceStorageError("save requires a RiskDecision")
        self._store._insert_once("risk_decisions", "decision", decision.tenant_id, "decision_id",
                                 decision.decision_id, canonical_dumps(encode_record(decision)))

    def get(self, tenant_id: str, decision_id: str) -> Optional[RiskDecision]:
        raw = self._store._load("risk_decisions", tenant_id, "decision_id", decision_id)
        return None if raw is None else decode_record(RiskDecision, raw)


class _EnvelopeRepository(_Adapter):
    def save(self, envelope: RiskAuthorizationEnvelope) -> None:
        self._store._insert_once("envelopes", "envelope", envelope.tenant_id, "envelope_id",
                                 envelope.envelope_id, canonical_dumps(encode_envelope(envelope)))

    def get(self, tenant_id: str, envelope_id: str) -> Optional[RiskAuthorizationEnvelope]:
        raw = self._store._load("envelopes", tenant_id, "envelope_id", envelope_id)
        return None if raw is None else decode_envelope(raw)


class _AuthorityRegistry(_Adapter):
    def add_grant(self, grant: AuthorityGrant) -> None:
        if not isinstance(grant, AuthorityGrant):
            raise PersistenceStorageError("add_grant requires an AuthorityGrant")
        self._store._replace("authority_grants", "grant", grant.tenant_id, "principal_id",
                             grant.principal_id, canonical_dumps(encode_record(grant)))

    def get_grant(self, tenant_id: str, principal_id: str) -> Optional[AuthorityGrant]:
        raw = self._store._load("authority_grants", tenant_id, "principal_id", principal_id)
        return None if raw is None else decode_record(AuthorityGrant, raw)


class _ControlResultRepository(_Adapter):
    def put(self, tenant_id: str, case_id: str, results: tuple[ControlResult, ...]) -> None:
        payload = [encode_record(r) for r in results]
        self._store._replace("control_results", "controls", tenant_id, "case_id", case_id,
                             canonical_dumps(payload))

    def get(self, tenant_id: str, case_id: str) -> tuple[ControlResult, ...]:
        raw = self._store._load("control_results", tenant_id, "case_id", case_id)
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise PersistenceStorageError("control_results: expected a list")
        return tuple(decode_record(ControlResult, item) for item in raw)


class _EvidenceRepository(_Adapter):
    def save(self, evidence: ControlEvidenceRecord) -> None:
        self._store._insert_once("evidence", "evidence", evidence.tenant_id, "evidence_id",
                                 evidence.evidence_id, canonical_dumps(encode_record(evidence)))

    def get(self, tenant_id: str, evidence_id: str) -> Optional[ControlEvidenceRecord]:
        raw = self._store._load("evidence", tenant_id, "evidence_id", evidence_id)
        return None if raw is None else decode_record(ControlEvidenceRecord, raw)


class _GovernanceEventStore(_Adapter):
    def append(self, event: GovernanceEvent) -> None:
        if not isinstance(event, GovernanceEvent):
            raise PersistenceStorageError("append requires a GovernanceEvent")
        self._store._insert_once("governance_events", "event", event.tenant_id, "event_id",
                                 event.event_id, canonical_dumps(encode_record(event)),
                                 extra={"aggregate_id": event.aggregate_id})

    def for_aggregate(self, tenant_id: str, aggregate_id: str) -> tuple[GovernanceEvent, ...]:
        rows = self._store._c().execute(
            "SELECT record_json FROM governance_events WHERE tenant_id=? AND aggregate_id=? ORDER BY seq",
            (tenant_id, aggregate_id)).fetchall()
        return tuple(decode_record(GovernanceEvent, json.loads(r[0])) for r in rows)

    def all(self) -> tuple[GovernanceEvent, ...]:
        rows = self._store._c().execute("SELECT record_json FROM governance_events ORDER BY seq").fetchall()
        return tuple(decode_record(GovernanceEvent, json.loads(r[0])) for r in rows)


class SqliteIdAllocator:
    """Durable per-prefix counter with the in-memory allocator's exact id format."""

    def __init__(self, store: SqliteRiskAuthorityStore) -> None:
        self._store = store

    @property
    def is_production_authoritative(self) -> bool:
        return self._store.is_production_authoritative

    def next(self, prefix: str) -> str:
        if not isinstance(prefix, str) or not prefix:
            raise PersistenceStorageError("next requires a non-empty prefix")
        with self._store._tx() as c:
            c.execute("INSERT INTO id_counters (prefix, value) VALUES (?, 0) "
                      "ON CONFLICT(prefix) DO NOTHING", (prefix,))
            c.execute("UPDATE id_counters SET value = value + 1 WHERE prefix=?", (prefix,))
            value = c.execute("SELECT value FROM id_counters WHERE prefix=?", (prefix,)).fetchone()[0]
        return f"{prefix}_{int(value):06d}"


class SqliteRevocationState(RevocationState):
    """:class:`RevocationState` whose every mutation is an appended, ledgered row (D-4)."""

    def __init__(self, store: SqliteRiskAuthorityStore) -> None:
        super().__init__()
        self._store = store
        for tenant_id, kind, target, epoch in store._c().execute(
                "SELECT tenant_id, kind, target, epoch FROM revocation_events ORDER BY seq"):
            self._apply(kind, tenant_id, target, int(epoch))

    @property
    def is_production_authoritative(self) -> bool:
        return self._store.is_production_authoritative

    def _apply(self, kind: str, tenant_id: str, target: str, epoch: int) -> None:
        if kind == "epoch":
            self._epochs[tenant_id] = epoch
        elif kind == "envelope":
            self._revoked_envelopes.add(target)
        elif kind == "subject":
            self._revoked_subjects.add((tenant_id, target))
        elif kind == "model":
            self._revoked_models.add((tenant_id, target))
        else:
            raise PersistenceStorageError(f"revocation_events: unknown kind {kind!r}")

    def _record(self, kind: str, tenant_id: str, target: str, epoch: int) -> None:
        with self._store._tx() as c:
            cur = c.execute("INSERT INTO revocation_events (tenant_id, kind, target, epoch) "
                            "VALUES (?,?,?,?)", (tenant_id, kind, target, epoch))
            self._store._append_ledger(
                c, "revocation", f"{tenant_id}/{cur.lastrowid}",
                canonical_bytes({"tenant_id": tenant_id, "kind": kind, "target": target, "epoch": epoch}))
        self._apply(kind, tenant_id, target, epoch)

    def advance_epoch(self, tenant_id: str) -> int:
        new_epoch = self.current_epoch(tenant_id) + 1
        self._record("epoch", tenant_id, "", new_epoch)
        return new_epoch

    def revoke_envelope(self, envelope_id: str) -> None:
        self._record("envelope", "", envelope_id, 0)

    def revoke_subject(self, tenant_id: str, subject_id: str) -> None:
        self._record("subject", tenant_id, subject_id, 0)

    def revoke_model(self, tenant_id: str, model_id: str) -> None:
        self._record("model", tenant_id, model_id, 0)
