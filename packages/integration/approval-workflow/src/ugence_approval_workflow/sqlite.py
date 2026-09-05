"""SQLite adapter — single-node durable persistence (D-22 Posture B).

Stdlib ``sqlite3`` only: WAL journal, every write inside ``BEGIN IMMEDIATE`` (one
writer at a time across processes on one host), the consumption row under
``UNIQUE(consumption_key)`` with ``INSERT … ON CONFLICT DO NOTHING``, and one
append-only, hash-linked ``ledger_events`` table whose triggers refuse UPDATE and
DELETE. The *shape* is that of
``packages/integration/execution-reservation/.../sqlite.py`` — copied, never imported.

What this is not: distributed, replicated, highly available, or an enforcement
store. Distributed strong consistency stays disclaimed. A ``:memory:`` path is
refused in production mode because it is not durable.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from ugence_governance_contracts.api import Validity

from ._canon import canonical_json, digest, from_iso, iso, require_nonempty, require_tzaware
from .consumption import (
    ConsumeOutcome,
    ConsumptionKey,
    ConsumptionResult,
    consumption_id_for,
    validate_for_consumption,
)
from .eligibility import ApproverEligibilityPort, ApproverRef
from .errors import (
    ApprovalAlreadyExistsError,
    ApprovalNotFoundError,
    ContractViolation,
    ProductionModeRefused,
    StoreUnavailableError,
)
from .records import ApprovalEvent, ApprovalRecord
from .states import OPEN_STATES, ApprovalState, ReviewDecision
from .subject import ApprovalSubject
from .version import MATURITY
from .workflow import (
    build_request,
    next_on_consume,
    next_on_decide,
    next_on_exception_decision,
    next_on_exception_request,
    next_on_present,
    next_on_withdraw,
    superseding_refusal,
)

__all__ = ["SqliteApprovalWorkflowStore", "SCHEMA_VERSION"]

SCHEMA_VERSION = "approval_workflow.store/1.0.0"
_GENESIS = "0" * 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, subject_kind TEXT NOT NULL,
    subject_digest TEXT NOT NULL, required_role TEXT NOT NULL, state TEXT NOT NULL,
    requested_by TEXT NOT NULL, artifact_digest TEXT NOT NULL, record_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS approvals_by_tenant ON approvals (tenant_id, state);
CREATE TABLE IF NOT EXISTS consumptions (
    consumption_key TEXT PRIMARY KEY, consumption_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
    approval_id TEXT NOT NULL, subject_digest TEXT NOT NULL, consumer_ref TEXT NOT NULL,
    consumed_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS consumptions_one_per_approval ON consumptions (approval_id);
CREATE TABLE IF NOT EXISTS ledger_events (
    seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, tenant_id TEXT NOT NULL,
    subject_id TEXT NOT NULL, sequence INTEGER NOT NULL, event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL, actor TEXT NOT NULL, detail_json TEXT NOT NULL,
    prev_digest TEXT NOT NULL, record_digest TEXT NOT NULL,
    UNIQUE (kind, subject_id, sequence));
CREATE TRIGGER IF NOT EXISTS ledger_events_no_update BEFORE UPDATE ON ledger_events
    BEGIN SELECT RAISE(ABORT, 'ledger_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_events_no_delete BEFORE DELETE ON ledger_events
    BEGIN SELECT RAISE(ABORT, 'ledger_events is append-only'); END;
"""


class SqliteApprovalWorkflowStore:
    """Durable adapter for :class:`~ugence_approval_workflow.ports.ApprovalWorkflowPort`."""

    maturity = MATURITY

    def __init__(self, path: str, eligibility: ApproverEligibilityPort, *,
                 production_mode: bool = False, busy_timeout_ms: int = 5000) -> None:
        if production_mode and (path == ":memory:" or path.startswith("file::memory:")):
            raise ProductionModeRefused("an in-memory SQLite database is not durable; "
                                        "production mode requires a file path")
        if not isinstance(eligibility, ApproverEligibilityPort):
            raise ContractViolation(
                "an ApproverEligibilityPort is required at construction; without one the "
                "package would record decisions by nobody in particular")
        self.path = path
        self.production_mode = production_mode
        self._eligibility = eligibility
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

    def _append_event(self, c: sqlite3.Connection, kind: str, tenant_id: str, subject_id: str,
                      event_type: str, occurred_at: datetime, actor: str, detail: dict) -> int:
        """Append one hash-linked event inside the caller's transaction; returns its sequence."""

        row = c.execute("SELECT COALESCE(MAX(sequence), -1) FROM ledger_events "
                        "WHERE kind=? AND subject_id=?", (kind, subject_id)).fetchone()
        sequence = int(row[0]) + 1
        prev = c.execute("SELECT record_digest FROM ledger_events ORDER BY seq DESC LIMIT 1").fetchone()
        prev_digest = prev[0] if prev else _GENESIS
        occurred = iso(occurred_at, "occurred_at")
        payload = {"kind": kind, "tenant_id": tenant_id, "subject_id": subject_id,
                   "sequence": sequence, "event_type": event_type, "occurred_at": occurred,
                   "actor": actor, "detail": detail, "prev_digest": prev_digest}
        c.execute("INSERT INTO ledger_events (kind, tenant_id, subject_id, sequence, event_type, "
                  "occurred_at, actor, detail_json, prev_digest, record_digest) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (kind, tenant_id, subject_id, sequence, event_type, occurred, actor,
                   canonical_json(detail), prev_digest, digest(payload)))
        return sequence

    def verify_chain(self) -> bool:
        """Recompute the hash chain over every event; a single altered row breaks it."""

        prev = _GENESIS
        for row in self._c().execute(
                "SELECT kind, tenant_id, subject_id, sequence, event_type, occurred_at, actor, "
                "detail_json, prev_digest, record_digest FROM ledger_events ORDER BY seq"):
            (kind, tenant, subject, sequence, etype, occurred, actor, detail_json,
             prev_digest, record_digest) = row
            if prev_digest != prev:
                return False
            payload = {"kind": kind, "tenant_id": tenant, "subject_id": subject,
                       "sequence": sequence, "event_type": etype, "occurred_at": occurred,
                       "actor": actor, "detail": json.loads(detail_json), "prev_digest": prev_digest}
            if digest(payload) != record_digest:
                return False
            prev = record_digest
        return True

    # ------------------------------------------------------------------ #
    def _row(self, c: sqlite3.Connection, approval_id: str) -> Optional[ApprovalRecord]:
        row = c.execute("SELECT record_json, artifact_digest FROM approvals WHERE approval_id=?",
                        (approval_id,)).fetchone()
        if row is None:
            return None
        record = ApprovalRecord.from_dict(json.loads(row[0]))
        record.verify(row[1])
        return record

    def _require(self, c: sqlite3.Connection, approval_id: str) -> ApprovalRecord:
        record = self._row(c, require_nonempty(approval_id, "approval_id"))
        if record is None:
            raise ApprovalNotFoundError(f"no approval '{approval_id}'")
        return record

    def _write(self, c: sqlite3.Connection, record: ApprovalRecord, occurred_at: datetime,
               actor: str, detail: dict) -> ApprovalRecord:
        c.execute("INSERT INTO approvals (approval_id, tenant_id, subject_kind, subject_digest, "
                  "required_role, state, requested_by, artifact_digest, record_json) "
                  "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(approval_id) DO UPDATE SET "
                  "state=excluded.state, artifact_digest=excluded.artifact_digest, "
                  "record_json=excluded.record_json",
                  (record.approval_id, record.tenant_id, record.subject_kind, record.subject_digest,
                   record.required_role, record.state.value, record.requested_by,
                   record.artifact_digest(), canonical_json(record.to_dict())))
        self._append_event(c, "approval", record.tenant_id, record.approval_id,
                           record.state.value, occurred_at, actor, detail)
        return record

    # ------------------------------------------------------------------ #
    # ApprovalWorkflowPort
    # ------------------------------------------------------------------ #
    def request_approval(self, subject: ApprovalSubject, *, requested_by: str,
                         required_role: str, validity: Validity, as_of: datetime,
                         request_ordinal: int = 1, supersedes: str = "",
                         justification: str = "", is_fixture: bool = False) -> ApprovalRecord:
        record = build_request(subject, requested_by=requested_by, required_role=required_role,
                               validity=validity, as_of=as_of, request_ordinal=request_ordinal,
                               supersedes=supersedes, justification=justification,
                               is_fixture=is_fixture)
        with self._tx() as c:
            if record.supersedes:
                refusal = superseding_refusal(self._row(c, record.supersedes), subject)
                if refusal:
                    raise ContractViolation(refusal)
            if self._row(c, record.approval_id) is not None:
                raise ApprovalAlreadyExistsError(
                    f"approval '{record.approval_id}' already exists; raise a new request with "
                    "a higher request_ordinal rather than reusing a standing decision")
            return self._write(c, record, as_of, requested_by,
                               {"subject_kind": subject.subject_kind,
                                "subject_ref": subject.subject_ref})

    def present_for_decision(self, approval_id: str, *, as_of: datetime) -> ApprovalRecord:
        with self._tx() as c:
            record = self._require(c, approval_id)
            approvers = self._eligibility.eligible_approvers(
                tenant_id=record.tenant_id, subject_kind=record.subject_kind,
                subject_digest=record.subject_digest, required_role=record.required_role,
                as_of=as_of)
            evolved = next_on_present(record, as_of=as_of, eligible_approvers=tuple(approvers))
            return self._write(c, evolved, as_of, "", {"eligible": len(approvers)})

    def _eligibility_for(self, record: ApprovalRecord, approver: ApproverRef, as_of: datetime):
        return self._eligibility.is_eligible(
            tenant_id=record.tenant_id, approver=approver, required_role=record.required_role,
            scope=f"{record.subject_kind}:{record.subject_digest}", as_of=as_of)

    def decide(self, approval_id: str, *, approver: ApproverRef, decision: ReviewDecision,
               as_of: datetime, justification: str = "",
               accepted_finding_ids: tuple[str, ...] = (),
               signature_reference: str = "") -> ApprovalRecord:
        with self._tx() as c:
            record = self._require(c, approval_id)
            evolved = next_on_decide(
                record, approver=approver, decision=decision,
                eligibility=self._eligibility_for(record, approver, as_of), as_of=as_of,
                justification=justification, accepted_finding_ids=accepted_finding_ids,
                signature_reference=signature_reference)
            return self._write(c, evolved, as_of, approver.approver_id,
                               {"decision": decision.value, "role": approver.role})

    def request_exception(self, approval_id: str, *, requested_by: str, justification: str,
                          exception_validity: Validity, as_of: datetime) -> ApprovalRecord:
        with self._tx() as c:
            record = self._require(c, approval_id)
            evolved = next_on_exception_request(
                record, requested_by=requested_by, justification=justification,
                exception_validity=exception_validity, as_of=as_of)
            return self._write(c, evolved, as_of, requested_by,
                               {"expires_at": iso(exception_validity.expires_at, "expires_at")})

    def decide_exception(self, approval_id: str, *, approver: ApproverRef, granted: bool,
                         as_of: datetime, justification: str = "",
                         signature_reference: str = "") -> ApprovalRecord:
        with self._tx() as c:
            record = self._require(c, approval_id)
            evolved = next_on_exception_decision(
                record, approver=approver, granted=granted,
                eligibility=self._eligibility_for(record, approver, as_of), as_of=as_of,
                justification=justification, signature_reference=signature_reference)
            return self._write(c, evolved, as_of, approver.approver_id, {"granted": bool(granted)})

    def withdraw(self, approval_id: str, *, by: str, as_of: datetime,
                 justification: str = "") -> ApprovalRecord:
        with self._tx() as c:
            record = self._require(c, approval_id)
            evolved = next_on_withdraw(record, by=by, as_of=as_of, justification=justification)
            return self._write(c, evolved, as_of, by, {})

    def consume(self, approval_id: str, *, consumer_ref: str, subject_digest: str,
                as_of: datetime) -> ConsumeOutcome:
        """The one racing decision: the unique insert happens inside a single write
        transaction, so exactly one caller ever consumes a granted approval."""

        require_tzaware(as_of, "consume.as_of")
        try:
            with self._tx() as c:
                record = self._row(c, require_nonempty(approval_id, "approval_id"))
                tenant = record.tenant_id if record is not None else "unknown"
                key = ConsumptionKey(tenant_id=tenant, approval_id=approval_id,
                                     subject_digest=subject_digest, consumer_ref=consumer_ref)
                held = c.execute("SELECT consumption_id FROM consumptions WHERE consumption_key=?",
                                 (key.serialized,)).fetchone()
                if held is not None:
                    return ConsumeOutcome(ConsumptionResult.ALREADY_CONSUMED, key,
                                          consumption_id=held[0], holder=held[0],
                                          reason="this consumption key is already held")
                refusal = validate_for_consumption(record, key, as_of)
                if refusal is not None:
                    result, reason = refusal
                    other = c.execute("SELECT consumption_id FROM consumptions WHERE approval_id=?",
                                      (approval_id,)).fetchone()
                    return ConsumeOutcome(result, key, holder=other[0] if other else "",
                                          reason=reason)
                consumption_id = consumption_id_for(key)
                inserted = c.execute(
                    "INSERT INTO consumptions (consumption_key, consumption_id, tenant_id, "
                    "approval_id, subject_digest, consumer_ref, consumed_at) VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT DO NOTHING",
                    (key.serialized, consumption_id, key.tenant_id, approval_id, subject_digest,
                     consumer_ref, iso(as_of, "as_of"))).rowcount
                if inserted != 1:
                    other = c.execute("SELECT consumption_id FROM consumptions WHERE approval_id=?",
                                      (approval_id,)).fetchone()
                    return ConsumeOutcome(ConsumptionResult.ALREADY_CONSUMED, key,
                                          holder=other[0] if other else "",
                                          reason="another consumer holds this approval")
                evolved = next_on_consume(record, consumer_ref=consumer_ref, as_of=as_of)
                self._write(c, evolved, as_of, consumer_ref, {"consumption_id": consumption_id})
                return ConsumeOutcome(ConsumptionResult.CONSUMED_FIRST, key,
                                      consumption_id=consumption_id)
        except sqlite3.Error as exc:
            raise StoreUnavailableError(str(exc)) from exc

    # ------------------------------------------------------------------ #
    def get_approval(self, approval_id: str) -> Optional[ApprovalRecord]:
        return self._row(self._c(), approval_id)

    def state_at(self, approval_id: str, *, as_of: datetime) -> ApprovalState:
        return self._require(self._c(), approval_id).state_at(as_of)

    def list_open(self, *, tenant_id: str, required_role: str = "",
                  as_of: datetime) -> tuple[ApprovalRecord, ...]:
        require_tzaware(as_of, "list_open.as_of")
        role = required_role.strip()
        rows = self._c().execute(
            "SELECT record_json, artifact_digest FROM approvals WHERE tenant_id=? "
            "ORDER BY approval_id", (tenant_id,)).fetchall()
        out = []
        for record_json, artifact in rows:
            record = ApprovalRecord.from_dict(json.loads(record_json))
            record.verify(artifact)
            if record.state_at(as_of) in OPEN_STATES and (not role or record.required_role == role):
                out.append(record)
        return tuple(out)

    def approval_events(self, approval_id: str) -> tuple[ApprovalEvent, ...]:
        rows = self._c().execute(
            "SELECT sequence, event_type, occurred_at, actor, detail_json FROM ledger_events "
            "WHERE kind='approval' AND subject_id=? ORDER BY sequence", (approval_id,)).fetchall()
        return tuple(
            ApprovalEvent(event_id=f"{approval_id}:{seq}", approval_id=approval_id, sequence=seq,
                          event_type=ApprovalState(etype), occurred_at=from_iso(occurred),
                          actor=actor, detail=detail_json)
            for seq, etype, occurred, actor, detail_json in rows)
