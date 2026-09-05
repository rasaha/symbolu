"""SQLite adapter — ratified decision D-3 (D-22 Posture B).

Single-node durable persistence on stdlib ``sqlite3``: WAL journal, every write
inside ``BEGIN IMMEDIATE`` (one writer at a time across processes on one host),
the reservation head under ``UNIQUE(tenant_id, execution_key)`` with
``INSERT … ON CONFLICT DO NOTHING``, and one append-only, hash-linked
``ledger_events`` table with triggers that refuse UPDATE and DELETE. The *shape*
is that of ``ugence_storygraph.durable_audit`` — copied, never imported.

What this is not: distributed, replicated, highly available, or a production
enforcement store. ``distributed_strong_consistency`` stays disclaimed. A
``:memory:`` path is refused in production mode because it is not durable.

Decision Authority records are stored as their own JSON (``model_dump(mode="json")``)
and rebuilt with ``model_validate``; this adapter therefore satisfies the frozen
``ExecutionRepository`` protocol structurally without touching the kernel.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from ugence_action_clearance import TrustedSignal
from ugence_decision_authority.errors import (
    CompensationNotFoundError,
    ExecutionAttemptNotFoundError,
    ExecutionIntentNotFoundError,
    VersionConflictError,
)
from ugence_decision_authority.execution.compensation import CompensationRequirement
from ugence_decision_authority.execution.execution_attempt import ExecutionAttempt
from ugence_decision_authority.execution.execution_intent import ExecutionIntent
from ugence_decision_authority.execution.execution_record import ExecutionRecord
from ugence_decision_authority.execution.reconciliation import ReconciliationResult
from ugence_decision_authority.execution.status import TERMINAL_EXECUTION_STATUSES
from ugence_governance_contracts.api import ExecutionBusinessOutcome

from ._canon import canonical_json, digest, from_iso, iso, require_nonempty, require_tzaware
from .consumption import build_consumption_signal
from .errors import (
    IllegalTransitionError,
    ProductionModeRefused,
    ReservationNotFoundError,
    StoreUnavailableError,
)
from .execution_key import ExecutionKey
from .receipts import (
    ClearanceReceipt,
    PutReceiptResult,
    ReceiptLifecycleEvent,
    ReceiptLifecycleState,
    RevocationResult,
    SupersessionResult,
    derive_lifecycle_state,
    verify_receipt_body,
)
from .reservation import (
    STATE_RANK,
    ExecutionReservation,
    ReconciledOutcome,
    ReservationEvent,
    ReservationResult,
    ReservationState,
    ReserveOnceOutcome,
    classify_head,
    is_post_dispatch,
    lease_end,
    observation_target,
    reservation_id_for,
    validate_receipt_for_reservation,
)
from .version import MATURITY

__all__ = ["SqliteExecutionReservationStore", "SCHEMA_VERSION"]

SCHEMA_VERSION = "execution_reservation.store/1.0.0"
_GENESIS = "0" * 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS receipts (
    receipt_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, authorization_ref TEXT NOT NULL,
    action_fingerprint TEXT NOT NULL, target_ref TEXT NOT NULL, operation TEXT NOT NULL,
    profile_id TEXT NOT NULL, clearance_status TEXT NOT NULL, result_fingerprint TEXT NOT NULL,
    record_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS receipts_by_auth ON receipts (tenant_id, authorization_ref);
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, execution_key TEXT NOT NULL,
    state TEXT NOT NULL, generation INTEGER NOT NULL, record_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reservation_heads (
    tenant_id TEXT NOT NULL, execution_key TEXT NOT NULL, reservation_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, execution_key));
CREATE TABLE IF NOT EXISTS ledger_events (
    seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, tenant_id TEXT NOT NULL,
    subject_id TEXT NOT NULL, sequence INTEGER NOT NULL, event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL, detail_json TEXT NOT NULL,
    prev_digest TEXT NOT NULL, record_digest TEXT NOT NULL,
    UNIQUE (kind, subject_id, sequence));
CREATE TRIGGER IF NOT EXISTS ledger_events_no_update BEFORE UPDATE ON ledger_events
    BEGIN SELECT RAISE(ABORT, 'ledger_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_events_no_delete BEFORE DELETE ON ledger_events
    BEGIN SELECT RAISE(ABORT, 'ledger_events is append-only'); END;
CREATE TABLE IF NOT EXISTS da_intents (
    intent_id TEXT NOT NULL, version INTEGER NOT NULL, tenant_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL, status TEXT NOT NULL, record_json TEXT NOT NULL,
    PRIMARY KEY (intent_id, version));
CREATE INDEX IF NOT EXISTS da_intents_idem ON da_intents (tenant_id, idempotency_key);
CREATE TABLE IF NOT EXISTS da_attempts (
    attempt_id TEXT PRIMARY KEY, intent_id TEXT NOT NULL, attempt_number INTEGER NOT NULL,
    record_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS da_records (
    record_id TEXT PRIMARY KEY, intent_id TEXT NOT NULL, external_request_id TEXT NOT NULL,
    seq INTEGER NOT NULL, record_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS da_recons (
    seq INTEGER PRIMARY KEY, intent_id TEXT NOT NULL, record_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS da_comps (
    compensation_id TEXT NOT NULL, revision INTEGER NOT NULL, intent_id TEXT NOT NULL,
    created_at TEXT NOT NULL, record_json TEXT NOT NULL,
    PRIMARY KEY (compensation_id, revision));
"""


class SqliteExecutionReservationStore:
    maturity = MATURITY

    def __init__(self, path: str, *, production_mode: bool = False,
                 source_id: str = "sqlite-ledger", busy_timeout_ms: int = 5000) -> None:
        if production_mode and (path == ":memory:" or path.startswith("file::memory:")):
            raise ProductionModeRefused("an in-memory SQLite database is not durable; "
                                        "production mode requires a file path")
        self.path = path
        self.production_mode = production_mode
        self._source_id = source_id
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

    def _read(self):
        return self._c()

    def _append_event(self, c: sqlite3.Connection, kind: str, tenant_id: str, subject_id: str,
                      event_type: str, occurred_at: datetime, detail: dict) -> int:
        """Append one hash-linked event inside the caller's transaction; returns its sequence."""

        row = c.execute("SELECT COALESCE(MAX(sequence), -1) FROM ledger_events WHERE kind=? AND subject_id=?",
                        (kind, subject_id)).fetchone()
        sequence = int(row[0]) + 1
        prev = c.execute("SELECT record_digest FROM ledger_events ORDER BY seq DESC LIMIT 1").fetchone()
        prev_digest = prev[0] if prev else _GENESIS
        occurred = iso(occurred_at, "occurred_at")
        payload = {"kind": kind, "tenant_id": tenant_id, "subject_id": subject_id,
                   "sequence": sequence, "event_type": event_type, "occurred_at": occurred,
                   "detail": detail, "prev_digest": prev_digest}
        c.execute("INSERT INTO ledger_events (kind, tenant_id, subject_id, sequence, event_type, "
                  "occurred_at, detail_json, prev_digest, record_digest) VALUES (?,?,?,?,?,?,?,?,?)",
                  (kind, tenant_id, subject_id, sequence, event_type, occurred,
                   canonical_json(detail), prev_digest, digest(payload)))
        return sequence

    def verify_chain(self) -> bool:
        prev = _GENESIS
        for row in self._read().execute(
                "SELECT kind, tenant_id, subject_id, sequence, event_type, occurred_at, detail_json, "
                "prev_digest, record_digest FROM ledger_events ORDER BY seq"):
            kind, tenant, subject, sequence, etype, occurred, detail_json, prev_digest, record_digest = row
            if prev_digest != prev:
                return False
            payload = {"kind": kind, "tenant_id": tenant, "subject_id": subject, "sequence": sequence,
                       "event_type": etype, "occurred_at": occurred,
                       "detail": json.loads(detail_json), "prev_digest": prev_digest}
            if digest(payload) != record_digest:
                return False
            prev = record_digest
        return True

    # ------------------------------------------------------------------ #
    # ClearanceReceiptRepository
    # ------------------------------------------------------------------ #
    def put_receipt(self, receipt: ClearanceReceipt) -> PutReceiptResult:
        verify_receipt_body(receipt.body)
        presented = receipt.canonical_bytes().decode("utf-8")
        with self._tx() as c:
            row = c.execute("SELECT record_json FROM receipts WHERE receipt_id=?",
                            (receipt.receipt_id,)).fetchone()
            if row is not None:
                return (PutReceiptResult.ALREADY_EXISTS_IDENTICAL if row[0] == presented
                        else PutReceiptResult.CONFLICT_DIFFERENT_BODY)
            c.execute("INSERT INTO receipts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (receipt.receipt_id, receipt.tenant_id, receipt.authorization_ref,
                       receipt.authorized_action_fingerprint, receipt.target_ref, receipt.operation,
                       receipt.profile_id, receipt.body.clearance_status.value,
                       receipt.body.result_fingerprint, presented, iso(receipt.created_at)))
            if receipt.is_clear:
                self._append_event(c, "receipt", receipt.tenant_id, receipt.receipt_id,
                                   ReceiptLifecycleState.ISSUED.value, receipt.created_at,
                                   {"owner": "workflow_service", "trigger": "CLEAR result persisted", "ref": ""})
            return PutReceiptResult.CREATED

    def _receipt_row(self, c, receipt_id: str) -> Optional[ClearanceReceipt]:
        row = c.execute("SELECT record_json FROM receipts WHERE receipt_id=?", (receipt_id,)).fetchone()
        return ClearanceReceipt.from_dict(json.loads(row[0])) if row else None

    def get_receipt(self, receipt_id: str) -> Optional[ClearanceReceipt]:
        return self._receipt_row(self._read(), receipt_id)

    def get_receipt_by_result_fingerprint(self, result_fingerprint: str) -> Optional[ClearanceReceipt]:
        return self.get_receipt("acr_" + result_fingerprint)

    def list_receipts_for_authorization(self, tenant_id: str, authorization_ref: str) -> tuple[ClearanceReceipt, ...]:
        rows = self._read().execute(
            "SELECT record_json FROM receipts WHERE tenant_id=? AND authorization_ref=? ORDER BY created_at, receipt_id",
            (tenant_id, authorization_ref)).fetchall()
        return tuple(ClearanceReceipt.from_dict(json.loads(r[0])) for r in rows)

    def _receipt_events_in(self, c, receipt_id: str) -> tuple[ReceiptLifecycleEvent, ...]:
        rows = c.execute("SELECT sequence, event_type, occurred_at, detail_json FROM ledger_events "
                         "WHERE kind='receipt' AND subject_id=? ORDER BY sequence", (receipt_id,)).fetchall()
        out = []
        for sequence, etype, occurred, detail_json in rows:
            d = json.loads(detail_json)
            out.append(ReceiptLifecycleEvent(event_id=f"{receipt_id}:{sequence}", receipt_id=receipt_id,
                                             sequence=sequence, event_type=ReceiptLifecycleState(etype),
                                             occurred_at=from_iso(occurred), owner=d.get("owner", ""),
                                             trigger=d.get("trigger", ""), ref=d.get("ref", "")))
        return tuple(out)

    def receipt_events(self, receipt_id: str) -> tuple[ReceiptLifecycleEvent, ...]:
        return self._receipt_events_in(self._read(), receipt_id)

    def supersede_receipt(self, receipt_id: str, reason: str, superseding_ref: str, *,
                          occurred_at: datetime) -> SupersessionResult:
        with self._tx() as c:
            old = self._receipt_row(c, receipt_id)
            if old is None:
                return SupersessionResult.NOT_FOUND
            new = self._receipt_row(c, superseding_ref)
            if new is None:
                return SupersessionResult.SUCCESSOR_NOT_FOUND
            if new.lineage_key != old.lineage_key or new.receipt_id == old.receipt_id:
                return SupersessionResult.LINEAGE_MISMATCH
            if any(e.event_type is ReceiptLifecycleState.SUPERSEDED for e in self._receipt_events_in(c, receipt_id)):
                return SupersessionResult.ALREADY_SUPERSEDED
            self._append_event(c, "receipt", old.tenant_id, receipt_id,
                               ReceiptLifecycleState.SUPERSEDED.value, occurred_at,
                               {"owner": "workflow_service", "trigger": reason, "ref": superseding_ref})
            return SupersessionResult.SUPERSEDED

    def revoke_receipt(self, receipt_id: str, reason: str, upstream_ref: str, *,
                       occurred_at: datetime) -> RevocationResult:
        with self._tx() as c:
            r = self._receipt_row(c, receipt_id)
            if r is None:
                return RevocationResult.NOT_FOUND
            if any(e.event_type is ReceiptLifecycleState.REVOKED for e in self._receipt_events_in(c, receipt_id)):
                return RevocationResult.ALREADY_REVOKED
            self._append_event(c, "receipt", r.tenant_id, receipt_id,
                               ReceiptLifecycleState.REVOKED.value, occurred_at,
                               {"owner": "workflow_service", "trigger": reason, "ref": upstream_ref})
            return RevocationResult.REVOKED

    def invalidate_receipt(self, receipt_id: str, reason: str, *, occurred_at: datetime) -> bool:
        with self._tx() as c:
            r = self._receipt_row(c, receipt_id)
            if r is None:
                return False
            self._append_event(c, "receipt", r.tenant_id, receipt_id,
                               ReceiptLifecycleState.INVALIDATED.value, occurred_at,
                               {"owner": "audit_process", "trigger": reason, "ref": ""})
            return True

    def lifecycle_state_at(self, receipt_id: str, as_of: datetime) -> Optional[ReceiptLifecycleState]:
        c = self._read()
        r = self._receipt_row(c, receipt_id)
        if r is None:
            return None
        return derive_lifecycle_state(r, self._receipt_events_in(c, receipt_id), as_of)

    # ------------------------------------------------------------------ #
    # ExecutionReservationPort
    # ------------------------------------------------------------------ #
    def _res_row(self, c, reservation_id: str) -> Optional[ExecutionReservation]:
        row = c.execute("SELECT record_json FROM reservations WHERE reservation_id=?",
                        (reservation_id,)).fetchone()
        return ExecutionReservation.from_dict(json.loads(row[0])) if row else None

    def _head_in(self, c, key: ExecutionKey) -> Optional[ExecutionReservation]:
        row = c.execute("SELECT reservation_id FROM reservation_heads WHERE tenant_id=? AND execution_key=?",
                        (key.tenant_id, key.serialized)).fetchone()
        return self._res_row(c, row[0]) if row else None

    def _write_res(self, c, res: ExecutionReservation, event_type: str,
                   from_state: Optional[ReservationState], occurred_at: datetime, ref: str = "") -> None:
        c.execute("INSERT INTO reservations (reservation_id, tenant_id, execution_key, state, generation, record_json) "
                  "VALUES (?,?,?,?,?,?) ON CONFLICT(reservation_id) DO UPDATE SET state=excluded.state, "
                  "record_json=excluded.record_json",
                  (res.reservation_id, res.tenant_id, res.execution_key.serialized, res.state.value,
                   res.generation, canonical_json(res.to_dict())))
        self._append_event(c, "reservation", res.tenant_id, res.reservation_id, event_type, occurred_at,
                           {"from_state": from_state.value if from_state else None,
                            "to_state": res.state.value, "ref": ref})

    def reserve_once(self, execution_key: ExecutionKey, clearance_receipt_ref: str,
                     expected_authorization_ref: str, expected_action_fingerprint: str,
                     reservation_ttl_s: int, *, as_of: datetime) -> ReserveOnceOutcome:
        require_tzaware(as_of, "reserve_once.as_of")
        with self._tx() as c:
            receipt = self._receipt_row(c, clearance_receipt_ref)
            lifecycle = (derive_lifecycle_state(receipt, self._receipt_events_in(c, clearance_receipt_ref), as_of)
                         if receipt is not None else None)
            refusal = validate_receipt_for_reservation(receipt, lifecycle, execution_key,
                                                       expected_authorization_ref,
                                                       expected_action_fingerprint, as_of)
            if refusal is not None:
                return ReserveOnceOutcome(refusal[0], None, refusal[1])
            head = self._head_in(c, execution_key)
            verdict = classify_head(head, as_of)
            if verdict is not None:
                return ReserveOnceOutcome(verdict, head, f"head state {head.state.value}")
            generation = 1
            if head is not None:
                generation = head.generation + 1
                if head.is_abandoned_at(as_of):
                    released = ExecutionReservation(**{**head.__dict__, "state": ReservationState.RELEASED})
                    self._write_res(c, released, "RELEASED_ABANDONED", head.state, as_of)
            res = ExecutionReservation(
                reservation_id=reservation_id_for(execution_key, generation),
                execution_key=execution_key, clearance_receipt_ref=clearance_receipt_ref,
                authorization_ref=expected_authorization_ref,
                action_fingerprint=expected_action_fingerprint,
                state=ReservationState.RESERVED, generation=generation, created_at=as_of,
                reservation_ttl_s=reservation_ttl_s,
                lease_expires_at=lease_end(as_of, reservation_ttl_s))
            # The uniqueness decision: a conditional insert on the head under the
            # write lock. Only the first generation inserts; later generations update
            # a head whose state classify_head already proved free.
            if head is None:
                cur = c.execute("INSERT INTO reservation_heads (tenant_id, execution_key, reservation_id) "
                                "VALUES (?,?,?) ON CONFLICT DO NOTHING",
                                (execution_key.tenant_id, execution_key.serialized, res.reservation_id))
                if cur.rowcount != 1:
                    return ReserveOnceOutcome(ReservationResult.CONFLICT, None,
                                              "head appeared inside the write transaction")
            else:
                c.execute("UPDATE reservation_heads SET reservation_id=? WHERE tenant_id=? AND execution_key=?",
                          (res.reservation_id, execution_key.tenant_id, execution_key.serialized))
            self._write_res(c, res, "RESERVED", None, as_of, ref=clearance_receipt_ref)
            return ReserveOnceOutcome(ReservationResult.ACQUIRED, res, "reservation acquired")

    def _require_in(self, c, reservation_id: str) -> ExecutionReservation:
        res = self._res_row(c, reservation_id)
        if res is None:
            raise ReservationNotFoundError(reservation_id)
        return res

    def get_reservation(self, reservation_id: str) -> Optional[ExecutionReservation]:
        return self._res_row(self._read(), reservation_id)

    def get_head(self, execution_key: ExecutionKey) -> Optional[ExecutionReservation]:
        return self._head_in(self._read(), execution_key)

    def mark_dispatched(self, reservation_id: str, dispatch_request_id: str, *,
                        dispatch_deadline: datetime, as_of: datetime,
                        provider_operation_id: str = "") -> ExecutionReservation:
        require_tzaware(as_of, "as_of")
        require_tzaware(dispatch_deadline, "dispatch_deadline")
        require_nonempty(dispatch_request_id, "dispatch_request_id")
        with self._tx() as c:
            res = self._require_in(c, reservation_id)
            if res.state is not ReservationState.RESERVED:
                raise IllegalTransitionError(f"cannot dispatch from {res.state.value}")
            if res.is_abandoned_at(as_of):
                raise IllegalTransitionError("reservation lease lapsed; re-reserve before dispatch")
            if dispatch_deadline <= as_of:
                raise IllegalTransitionError("dispatch_deadline must follow as_of")
            new = ExecutionReservation(**{**res.__dict__, "state": ReservationState.DISPATCHED,
                                          "dispatched_at": as_of, "dispatch_deadline": dispatch_deadline,
                                          "dispatch_request_id": dispatch_request_id,
                                          "provider_operation_id": provider_operation_id})
            self._write_res(c, new, "DISPATCHED", res.state, as_of, ref=dispatch_request_id)
            return new

    def mark_outcome_uncertain(self, reservation_id: str, *, as_of: datetime) -> ExecutionReservation:
        require_tzaware(as_of, "as_of")
        with self._tx() as c:
            res = self._require_in(c, reservation_id)
            if res.state is ReservationState.OUTCOME_UNCERTAIN:
                return res
            if res.state is not ReservationState.DISPATCHED:
                raise IllegalTransitionError(f"cannot mark uncertain from {res.state.value}")
            new = ExecutionReservation(**{**res.__dict__, "state": ReservationState.OUTCOME_UNCERTAIN})
            self._write_res(c, new, "OUTCOME_UNCERTAIN", res.state, as_of)
            return new

    def renew_lease(self, reservation_id: str, *, lease_expires_at: datetime,
                    as_of: datetime) -> ExecutionReservation:
        require_tzaware(as_of, "as_of")
        require_tzaware(lease_expires_at, "lease_expires_at")
        with self._tx() as c:
            res = self._require_in(c, reservation_id)
            if res.state is not ReservationState.RESERVED or res.is_abandoned_at(as_of):
                raise IllegalTransitionError("only a live RESERVED lease can be renewed")
            if lease_expires_at <= res.lease_expires_at:
                raise IllegalTransitionError("lease renewal must extend the lease")
            new = ExecutionReservation(**{**res.__dict__, "lease_expires_at": lease_expires_at})
            self._write_res(c, new, "LEASE_RENEWED", res.state, as_of)
            return new

    def record_observation(self, reservation_id: str, observation_ref: str,
                           outcome: ExecutionBusinessOutcome, *, as_of: datetime) -> ExecutionReservation:
        require_tzaware(as_of, "as_of")
        require_nonempty(observation_ref, "observation_ref")
        with self._tx() as c:
            res = self._require_in(c, reservation_id)
            if observation_ref in res.observation_refs:
                return res
            if res.state in (ReservationState.RESERVED, ReservationState.RELEASED, ReservationState.AVAILABLE):
                raise IllegalTransitionError(f"cannot observe a reservation in {res.state.value}")
            target = observation_target(outcome)
            refs = res.observation_refs + (observation_ref,)
            if STATE_RANK[target] > STATE_RANK[res.state]:
                new = ExecutionReservation(**{**res.__dict__, "state": target, "observation_refs": refs})
                self._write_res(c, new, "OBSERVED", res.state, as_of, ref=observation_ref)
            else:
                new = ExecutionReservation(**{**res.__dict__, "observation_refs": refs})
                self._write_res(c, new, "OBSERVATION_LATE", res.state, as_of, ref=observation_ref)
            return new

    def record_reconciliation(self, reservation_id: str, reconciliation_ref: str,
                              outcome: ReconciledOutcome, *, as_of: datetime) -> ExecutionReservation:
        require_tzaware(as_of, "as_of")
        require_nonempty(reconciliation_ref, "reconciliation_ref")
        with self._tx() as c:
            res = self._require_in(c, reservation_id)
            if res.reconciliation_ref == reconciliation_ref:
                return res
            if not (is_post_dispatch(res.state) or res.state in (
                    ReservationState.RECONCILED_FAILURE, ReservationState.RECONCILED_SUCCESS)):
                raise IllegalTransitionError(f"cannot reconcile from {res.state.value}")
            target = (ReservationState.RECONCILED_SUCCESS if outcome is ReconciledOutcome.SUCCESS
                      else ReservationState.RECONCILED_FAILURE)
            if STATE_RANK[target] > STATE_RANK[res.state]:
                new = ExecutionReservation(**{**res.__dict__, "state": target,
                                              "reconciliation_ref": reconciliation_ref})
                self._write_res(c, new, "RECONCILED", res.state, as_of, ref=reconciliation_ref)
            else:
                new = res
                self._write_res(c, new, "RECONCILIATION_LATE", res.state, as_of, ref=reconciliation_ref)
            return new

    def release(self, reservation_id: str, *, as_of: datetime) -> ExecutionReservation:
        require_tzaware(as_of, "as_of")
        with self._tx() as c:
            res = self._require_in(c, reservation_id)
            if res.state is ReservationState.RELEASED:
                return res
            if res.state not in (ReservationState.RESERVED, ReservationState.RECONCILED_FAILURE):
                raise IllegalTransitionError(
                    f"release from {res.state.value} is forbidden: an uncertain or dispatched "
                    "reservation is never released without reconciliation")
            new = ExecutionReservation(**{**res.__dict__, "state": ReservationState.RELEASED})
            self._write_res(c, new, "RELEASED", res.state, as_of)
            return new

    def reservation_events(self, reservation_id: str) -> tuple[ReservationEvent, ...]:
        rows = self._read().execute(
            "SELECT sequence, event_type, occurred_at, detail_json FROM ledger_events "
            "WHERE kind='reservation' AND subject_id=? ORDER BY sequence", (reservation_id,)).fetchall()
        out = []
        for sequence, etype, occurred, detail_json in rows:
            d = json.loads(detail_json)
            out.append(ReservationEvent(event_id=f"{reservation_id}:{sequence}", reservation_id=reservation_id,
                                        sequence=sequence, event_type=etype,
                                        from_state=ReservationState(d["from_state"]) if d.get("from_state") else None,
                                        to_state=ReservationState(d["to_state"]),
                                        occurred_at=from_iso(occurred), ref=d.get("ref", "")))
        return tuple(out)

    # ------------------------------------------------------------------ #
    # PriorConsumptionSource
    # ------------------------------------------------------------------ #
    def consumption_signal(self, execution_key: ExecutionKey, *, as_of: datetime,
                           freshness_s: int = 60) -> TrustedSignal:
        try:
            head = self.get_head(execution_key)
            unavailable = False
        except (StoreUnavailableError, sqlite3.Error):
            head, unavailable = None, True
        return build_consumption_signal(execution_key, head, as_of=as_of, freshness_s=freshness_s,
                                        unavailable=unavailable, source_id=self._source_id,
                                        provenance_ref=f"{self._source_id}:prior-consumption")

    # ------------------------------------------------------------------ #
    # Decision Authority ExecutionRepository (structural conformance)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _dump(model) -> str:
        return json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def create_execution_intent(self, intent: ExecutionIntent) -> ExecutionIntent:
        with self._tx() as c:
            if c.execute("SELECT 1 FROM da_intents WHERE intent_id=? LIMIT 1",
                         (intent.execution_intent_id,)).fetchone():
                raise VersionConflictError(
                    f"execution intent '{intent.execution_intent_id}' already exists")
            c.execute("INSERT INTO da_intents VALUES (?,?,?,?,?,?)",
                      (intent.execution_intent_id, intent.version, intent.tenant_id,
                       intent.execution_idempotency_key, intent.status.value, self._dump(intent)))
            return intent

    def save_execution_snapshot(self, intent: ExecutionIntent) -> ExecutionIntent:
        with self._tx() as c:
            if not c.execute("SELECT 1 FROM da_intents WHERE intent_id=? LIMIT 1",
                             (intent.execution_intent_id,)).fetchone():
                raise ExecutionIntentNotFoundError(
                    f"execution intent '{intent.execution_intent_id}' not found")
            c.execute("INSERT OR REPLACE INTO da_intents VALUES (?,?,?,?,?,?)",
                      (intent.execution_intent_id, intent.version, intent.tenant_id,
                       intent.execution_idempotency_key, intent.status.value, self._dump(intent)))
            return intent

    def get_intent_history(self, intent_id: str) -> tuple[ExecutionIntent, ...]:
        rows = self._read().execute("SELECT record_json FROM da_intents WHERE intent_id=? ORDER BY version",
                                    (intent_id,)).fetchall()
        if not rows:
            raise ExecutionIntentNotFoundError(f"execution intent '{intent_id}' not found")
        return tuple(ExecutionIntent.model_validate(json.loads(r[0])) for r in rows)

    def get_execution_intent(self, intent_id: str) -> ExecutionIntent:
        return self.get_intent_history(intent_id)[-1]

    def lookup_by_execution_idempotency_key(self, tenant_id: str, key: str) -> Optional[ExecutionIntent]:
        row = self._read().execute(
            "SELECT intent_id FROM da_intents WHERE tenant_id=? AND idempotency_key=? AND idempotency_key<>'' "
            "ORDER BY rowid LIMIT 1", (tenant_id, key)).fetchone()
        if row is None:
            return None
        intent = self.get_execution_intent(row[0])
        return None if intent.status in TERMINAL_EXECUTION_STATUSES else intent

    def record_execution_attempt(self, attempt: ExecutionAttempt) -> ExecutionAttempt:
        with self._tx() as c:
            if c.execute("SELECT 1 FROM da_attempts WHERE attempt_id=?", (attempt.execution_attempt_id,)).fetchone():
                raise VersionConflictError(f"attempt '{attempt.execution_attempt_id}' already exists")
            c.execute("INSERT INTO da_attempts VALUES (?,?,?,?)",
                      (attempt.execution_attempt_id, attempt.execution_intent_id, attempt.attempt_number,
                       self._dump(attempt)))
            return attempt

    def get_execution_attempt(self, attempt_id: str) -> ExecutionAttempt:
        row = self._read().execute("SELECT record_json FROM da_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        if row is None:
            raise ExecutionAttemptNotFoundError(f"attempt '{attempt_id}' not found")
        return ExecutionAttempt.model_validate(json.loads(row[0]))

    def get_attempt_history(self, intent_id: str) -> tuple[ExecutionAttempt, ...]:
        rows = self._read().execute("SELECT record_json FROM da_attempts WHERE intent_id=? ORDER BY attempt_number",
                                    (intent_id,)).fetchall()
        return tuple(ExecutionAttempt.model_validate(json.loads(r[0])) for r in rows)

    def attempt_count(self, intent_id: str) -> int:
        return int(self._read().execute("SELECT COUNT(*) FROM da_attempts WHERE intent_id=?", (intent_id,)).fetchone()[0])

    def record_execution_record(self, record: ExecutionRecord) -> ExecutionRecord:
        with self._tx() as c:
            if c.execute("SELECT 1 FROM da_records WHERE record_id=?", (record.execution_record_id,)).fetchone():
                raise VersionConflictError(f"execution record '{record.execution_record_id}' already exists")
            seq = int(c.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM da_records").fetchone()[0])
            c.execute("INSERT INTO da_records VALUES (?,?,?,?,?)",
                      (record.execution_record_id, record.execution_intent_id, record.external_request_id,
                       seq, self._dump(record)))
            return record

    def get_execution_records(self, intent_id: str) -> tuple[ExecutionRecord, ...]:
        rows = self._read().execute("SELECT record_json FROM da_records WHERE intent_id=? ORDER BY seq",
                                    (intent_id,)).fetchall()
        return tuple(ExecutionRecord.model_validate(json.loads(r[0])) for r in rows)

    def lookup_by_external_request_id(self, external_request_id: str) -> tuple[ExecutionRecord, ...]:
        if not external_request_id:
            return ()
        rows = self._read().execute("SELECT record_json FROM da_records WHERE external_request_id=? ORDER BY seq",
                                    (external_request_id,)).fetchall()
        return tuple(ExecutionRecord.model_validate(json.loads(r[0])) for r in rows)

    def record_reconciliation_result(self, result: ReconciliationResult) -> ReconciliationResult:
        with self._tx() as c:
            c.execute("INSERT INTO da_recons (intent_id, record_json) VALUES (?,?)",
                      (result.execution_intent_id, self._dump(result)))
            return result

    def get_reconciliation_history(self, intent_id: str) -> tuple[ReconciliationResult, ...]:
        rows = self._read().execute("SELECT record_json FROM da_recons WHERE intent_id=? ORDER BY seq",
                                    (intent_id,)).fetchall()
        return tuple(ReconciliationResult.model_validate(json.loads(r[0])) for r in rows)

    def record_compensation_requirement(self, comp: CompensationRequirement) -> CompensationRequirement:
        with self._tx() as c:
            if c.execute("SELECT 1 FROM da_comps WHERE compensation_id=? LIMIT 1", (comp.compensation_id,)).fetchone():
                raise VersionConflictError(f"compensation '{comp.compensation_id}' already exists")
            c.execute("INSERT INTO da_comps VALUES (?,?,?,?,?)",
                      (comp.compensation_id, comp.revision, comp.execution_intent_id,
                       iso(comp.created_at), self._dump(comp)))
            return comp

    def save_compensation_snapshot(self, comp: CompensationRequirement) -> CompensationRequirement:
        with self._tx() as c:
            if not c.execute("SELECT 1 FROM da_comps WHERE compensation_id=? LIMIT 1", (comp.compensation_id,)).fetchone():
                raise CompensationNotFoundError(f"compensation '{comp.compensation_id}' not found")
            c.execute("INSERT OR REPLACE INTO da_comps VALUES (?,?,?,?,?)",
                      (comp.compensation_id, comp.revision, comp.execution_intent_id,
                       iso(comp.created_at), self._dump(comp)))
            return comp

    def get_compensation(self, compensation_id: str) -> CompensationRequirement:
        row = self._read().execute("SELECT record_json FROM da_comps WHERE compensation_id=? ORDER BY revision DESC LIMIT 1",
                                   (compensation_id,)).fetchone()
        if row is None:
            raise CompensationNotFoundError(f"compensation '{compensation_id}' not found")
        return CompensationRequirement.model_validate(json.loads(row[0]))

    def get_compensation_history(self, intent_id: str) -> tuple[CompensationRequirement, ...]:
        ids = [r[0] for r in self._read().execute(
            "SELECT DISTINCT compensation_id FROM da_comps WHERE intent_id=?", (intent_id,)).fetchall()]
        return tuple(sorted((self.get_compensation(cid) for cid in ids), key=lambda c: c.created_at))
