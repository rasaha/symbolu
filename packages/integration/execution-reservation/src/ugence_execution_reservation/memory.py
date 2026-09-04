"""In-memory reference adapter — tests only, refused in production mode.

Implements all four ports with a process-local lock. Decision Authority's own
``InMemoryExecutionRepository`` is composed for the ``ExecutionRepository``
methods so the reference semantics are the kernel's, not a copy.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Optional

from ugence_action_clearance import TrustedSignal
from ugence_decision_authority.repositories.execution_repository import (
    InMemoryExecutionRepository,
)
from ugence_governance_contracts.api import ExecutionBusinessOutcome

from ._canon import require_nonempty, require_tzaware
from .errors import (
    IllegalTransitionError,
    ProductionModeRefused,
    ReceiptIntegrityError,
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
from .consumption import build_consumption_signal
from .version import MATURITY

__all__ = ["InMemoryExecutionReservationStore"]


class InMemoryExecutionReservationStore:
    maturity = MATURITY

    def __init__(self, *, production_mode: bool = False, source_id: str = "memory-ledger") -> None:
        if production_mode:
            raise ProductionModeRefused(
                "InMemoryExecutionReservationStore is a test reference adapter and is "
                "refused in production mode; use SqliteExecutionReservationStore on a file")
        self._lock = threading.RLock()
        self._closed = False
        self._source_id = source_id
        self._receipts: dict[str, ClearanceReceipt] = {}
        self._receipt_bytes: dict[str, bytes] = {}
        self._receipt_events: dict[str, list[ReceiptLifecycleEvent]] = {}
        self._reservations: dict[str, ExecutionReservation] = {}
        self._heads: dict[tuple[str, str], str] = {}
        self._reservation_events: dict[str, list[ReservationEvent]] = {}
        self._da = InMemoryExecutionRepository()

    # ------------------------------------------------------------------ #
    def close(self) -> None:
        self._closed = True

    def _guard(self) -> None:
        if self._closed:
            raise StoreUnavailableError("store closed")

    # ------------------------------------------------------------------ #
    # ClearanceReceiptRepository
    # ------------------------------------------------------------------ #
    def put_receipt(self, receipt: ClearanceReceipt) -> PutReceiptResult:
        verify_receipt_body(receipt.body)
        with self._lock:
            self._guard()
            rid = receipt.receipt_id
            presented = receipt.canonical_bytes()
            if rid in self._receipts:
                return (PutReceiptResult.ALREADY_EXISTS_IDENTICAL
                        if self._receipt_bytes[rid] == presented
                        else PutReceiptResult.CONFLICT_DIFFERENT_BODY)
            self._receipts[rid] = receipt
            self._receipt_bytes[rid] = presented
            self._receipt_events[rid] = []
            if receipt.is_clear:
                self._append_receipt_event(rid, ReceiptLifecycleState.ISSUED,
                                           receipt.created_at, "workflow_service",
                                           trigger="CLEAR result persisted")
            return PutReceiptResult.CREATED

    def _append_receipt_event(self, rid: str, event_type: ReceiptLifecycleState,
                              occurred_at: datetime, owner: str, *, trigger: str = "",
                              ref: str = "") -> ReceiptLifecycleEvent:
        require_tzaware(occurred_at, "occurred_at")
        events = self._receipt_events[rid]
        seq = len(events)
        ev = ReceiptLifecycleEvent(event_id=f"{rid}:{seq}", receipt_id=rid, sequence=seq,
                                   event_type=event_type, occurred_at=occurred_at,
                                   owner=owner, trigger=trigger, ref=ref)
        events.append(ev)
        return ev

    def get_receipt(self, receipt_id: str) -> Optional[ClearanceReceipt]:
        with self._lock:
            self._guard()
            return self._receipts.get(receipt_id)

    def get_receipt_by_result_fingerprint(self, result_fingerprint: str) -> Optional[ClearanceReceipt]:
        return self.get_receipt("acr_" + result_fingerprint)

    def list_receipts_for_authorization(self, tenant_id: str, authorization_ref: str) -> tuple[ClearanceReceipt, ...]:
        with self._lock:
            self._guard()
            return tuple(r for r in self._receipts.values()
                         if r.tenant_id == tenant_id and r.authorization_ref == authorization_ref)

    def supersede_receipt(self, receipt_id: str, reason: str, superseding_ref: str, *,
                          occurred_at: datetime) -> SupersessionResult:
        with self._lock:
            self._guard()
            old = self._receipts.get(receipt_id)
            if old is None:
                return SupersessionResult.NOT_FOUND
            new = self._receipts.get(superseding_ref)
            if new is None:
                return SupersessionResult.SUCCESSOR_NOT_FOUND
            if new.lineage_key != old.lineage_key or new.receipt_id == old.receipt_id:
                return SupersessionResult.LINEAGE_MISMATCH
            if any(e.event_type is ReceiptLifecycleState.SUPERSEDED for e in self._receipt_events[receipt_id]):
                return SupersessionResult.ALREADY_SUPERSEDED
            self._append_receipt_event(receipt_id, ReceiptLifecycleState.SUPERSEDED, occurred_at,
                                       "workflow_service", trigger=reason, ref=superseding_ref)
            return SupersessionResult.SUPERSEDED

    def revoke_receipt(self, receipt_id: str, reason: str, upstream_ref: str, *,
                       occurred_at: datetime) -> RevocationResult:
        with self._lock:
            self._guard()
            if receipt_id not in self._receipts:
                return RevocationResult.NOT_FOUND
            if any(e.event_type is ReceiptLifecycleState.REVOKED for e in self._receipt_events[receipt_id]):
                return RevocationResult.ALREADY_REVOKED
            self._append_receipt_event(receipt_id, ReceiptLifecycleState.REVOKED, occurred_at,
                                       "workflow_service", trigger=reason, ref=upstream_ref)
            return RevocationResult.REVOKED

    def invalidate_receipt(self, receipt_id: str, reason: str, *, occurred_at: datetime) -> bool:
        with self._lock:
            self._guard()
            if receipt_id not in self._receipts:
                return False
            self._append_receipt_event(receipt_id, ReceiptLifecycleState.INVALIDATED, occurred_at,
                                       "audit_process", trigger=reason)
            return True

    def receipt_events(self, receipt_id: str) -> tuple[ReceiptLifecycleEvent, ...]:
        with self._lock:
            self._guard()
            return tuple(self._receipt_events.get(receipt_id, ()))

    def lifecycle_state_at(self, receipt_id: str, as_of: datetime) -> Optional[ReceiptLifecycleState]:
        with self._lock:
            self._guard()
            r = self._receipts.get(receipt_id)
            if r is None:
                return None
            return derive_lifecycle_state(r, self._receipt_events[receipt_id], as_of)

    # ------------------------------------------------------------------ #
    # ExecutionReservationPort
    # ------------------------------------------------------------------ #
    def _append_reservation_event(self, res: ExecutionReservation, event_type: str,
                                  from_state: Optional[ReservationState], occurred_at: datetime,
                                  ref: str = "") -> None:
        events = self._reservation_events.setdefault(res.reservation_id, [])
        seq = len(events)
        events.append(ReservationEvent(event_id=f"{res.reservation_id}:{seq}",
                                       reservation_id=res.reservation_id, sequence=seq,
                                       event_type=event_type, from_state=from_state,
                                       to_state=res.state, occurred_at=occurred_at, ref=ref))

    def reserve_once(self, execution_key: ExecutionKey, clearance_receipt_ref: str,
                     expected_authorization_ref: str, expected_action_fingerprint: str,
                     reservation_ttl_s: int, *, as_of: datetime) -> ReserveOnceOutcome:
        require_tzaware(as_of, "reserve_once.as_of")
        with self._lock:
            self._guard()
            receipt = self._receipts.get(clearance_receipt_ref)
            lifecycle = (derive_lifecycle_state(receipt, self._receipt_events[clearance_receipt_ref], as_of)
                         if receipt is not None else None)
            refusal = validate_receipt_for_reservation(receipt, lifecycle, execution_key,
                                                       expected_authorization_ref,
                                                       expected_action_fingerprint, as_of)
            if refusal is not None:
                return ReserveOnceOutcome(refusal[0], None, refusal[1])
            head_id = self._heads.get((execution_key.tenant_id, execution_key.serialized))
            head = self._reservations.get(head_id) if head_id else None
            verdict = classify_head(head, as_of)
            if verdict is not None:
                return ReserveOnceOutcome(verdict, head, f"head state {head.state.value}")
            generation = 1
            if head is not None:
                generation = head.generation + 1
                if head.is_abandoned_at(as_of):
                    released = self._replace(head, state=ReservationState.RELEASED)
                    self._append_reservation_event(released, "RELEASED_ABANDONED", head.state, as_of)
            res = ExecutionReservation(
                reservation_id=reservation_id_for(execution_key, generation),
                execution_key=execution_key, clearance_receipt_ref=clearance_receipt_ref,
                authorization_ref=expected_authorization_ref,
                action_fingerprint=expected_action_fingerprint,
                state=ReservationState.RESERVED, generation=generation, created_at=as_of,
                reservation_ttl_s=reservation_ttl_s,
                lease_expires_at=lease_end(as_of, reservation_ttl_s))
            self._reservations[res.reservation_id] = res
            self._heads[(execution_key.tenant_id, execution_key.serialized)] = res.reservation_id
            self._append_reservation_event(res, "RESERVED", None, as_of, ref=clearance_receipt_ref)
            return ReserveOnceOutcome(ReservationResult.ACQUIRED, res, "reservation acquired")

    def _replace(self, res: ExecutionReservation, **changes) -> ExecutionReservation:
        data = {**res.__dict__, **changes}
        new = ExecutionReservation(**data)
        self._reservations[new.reservation_id] = new
        return new

    def _require(self, reservation_id: str) -> ExecutionReservation:
        res = self._reservations.get(reservation_id)
        if res is None:
            raise ReservationNotFoundError(reservation_id)
        return res

    def get_reservation(self, reservation_id: str) -> Optional[ExecutionReservation]:
        with self._lock:
            self._guard()
            return self._reservations.get(reservation_id)

    def get_head(self, execution_key: ExecutionKey) -> Optional[ExecutionReservation]:
        with self._lock:
            self._guard()
            head_id = self._heads.get((execution_key.tenant_id, execution_key.serialized))
            return self._reservations.get(head_id) if head_id else None

    def mark_dispatched(self, reservation_id: str, dispatch_request_id: str, *,
                        dispatch_deadline: datetime, as_of: datetime,
                        provider_operation_id: str = "") -> ExecutionReservation:
        require_tzaware(as_of, "as_of")
        require_tzaware(dispatch_deadline, "dispatch_deadline")
        require_nonempty(dispatch_request_id, "dispatch_request_id")
        with self._lock:
            self._guard()
            res = self._require(reservation_id)
            if res.state is not ReservationState.RESERVED:
                raise IllegalTransitionError(f"cannot dispatch from {res.state.value}")
            if res.is_abandoned_at(as_of):
                raise IllegalTransitionError("reservation lease lapsed; re-reserve before dispatch")
            if dispatch_deadline <= as_of:
                raise IllegalTransitionError("dispatch_deadline must follow as_of")
            new = self._replace(res, state=ReservationState.DISPATCHED, dispatched_at=as_of,
                                dispatch_deadline=dispatch_deadline,
                                dispatch_request_id=dispatch_request_id,
                                provider_operation_id=provider_operation_id)
            self._append_reservation_event(new, "DISPATCHED", res.state, as_of, ref=dispatch_request_id)
            return new

    def mark_outcome_uncertain(self, reservation_id: str, *, as_of: datetime) -> ExecutionReservation:
        require_tzaware(as_of, "as_of")
        with self._lock:
            self._guard()
            res = self._require(reservation_id)
            if res.state is ReservationState.OUTCOME_UNCERTAIN:
                return res
            if res.state is not ReservationState.DISPATCHED:
                raise IllegalTransitionError(f"cannot mark uncertain from {res.state.value}")
            new = self._replace(res, state=ReservationState.OUTCOME_UNCERTAIN)
            self._append_reservation_event(new, "OUTCOME_UNCERTAIN", res.state, as_of)
            return new

    def renew_lease(self, reservation_id: str, *, lease_expires_at: datetime,
                    as_of: datetime) -> ExecutionReservation:
        require_tzaware(as_of, "as_of")
        require_tzaware(lease_expires_at, "lease_expires_at")
        with self._lock:
            self._guard()
            res = self._require(reservation_id)
            if res.state is not ReservationState.RESERVED or res.is_abandoned_at(as_of):
                raise IllegalTransitionError("only a live RESERVED lease can be renewed")
            if lease_expires_at <= res.lease_expires_at:
                raise IllegalTransitionError("lease renewal must extend the lease")
            new = self._replace(res, lease_expires_at=lease_expires_at)
            self._append_reservation_event(new, "LEASE_RENEWED", res.state, as_of)
            return new

    def record_observation(self, reservation_id: str, observation_ref: str,
                           outcome: ExecutionBusinessOutcome, *, as_of: datetime) -> ExecutionReservation:
        require_tzaware(as_of, "as_of")
        require_nonempty(observation_ref, "observation_ref")
        with self._lock:
            self._guard()
            res = self._require(reservation_id)
            if observation_ref in res.observation_refs:
                return res  # duplicate callback: idempotent no-op (scenario 36)
            if res.state in (ReservationState.RESERVED, ReservationState.RELEASED,
                             ReservationState.AVAILABLE):
                raise IllegalTransitionError(f"cannot observe a reservation in {res.state.value}")
            target = observation_target(outcome)
            refs = res.observation_refs + (observation_ref,)
            if STATE_RANK[target] > STATE_RANK[res.state]:
                new = self._replace(res, state=target, observation_refs=refs)
                self._append_reservation_event(new, "OBSERVED", res.state, as_of, ref=observation_ref)
            else:
                new = self._replace(res, observation_refs=refs)
                self._append_reservation_event(new, "OBSERVATION_LATE", res.state, as_of, ref=observation_ref)
            return new

    def record_reconciliation(self, reservation_id: str, reconciliation_ref: str,
                              outcome: ReconciledOutcome, *, as_of: datetime) -> ExecutionReservation:
        require_tzaware(as_of, "as_of")
        require_nonempty(reconciliation_ref, "reconciliation_ref")
        with self._lock:
            self._guard()
            res = self._require(reservation_id)
            if res.reconciliation_ref == reconciliation_ref:
                return res
            if not (is_post_dispatch(res.state) or res.state in (
                    ReservationState.RECONCILED_FAILURE, ReservationState.RECONCILED_SUCCESS)):
                raise IllegalTransitionError(f"cannot reconcile from {res.state.value}")
            target = (ReservationState.RECONCILED_SUCCESS if outcome is ReconciledOutcome.SUCCESS
                      else ReservationState.RECONCILED_FAILURE)
            if STATE_RANK[target] > STATE_RANK[res.state]:
                new = self._replace(res, state=target, reconciliation_ref=reconciliation_ref)
                self._append_reservation_event(new, "RECONCILED", res.state, as_of, ref=reconciliation_ref)
            else:
                new = res
                self._append_reservation_event(new, "RECONCILIATION_LATE", res.state, as_of, ref=reconciliation_ref)
            return new

    def release(self, reservation_id: str, *, as_of: datetime) -> ExecutionReservation:
        require_tzaware(as_of, "as_of")
        with self._lock:
            self._guard()
            res = self._require(reservation_id)
            if res.state is ReservationState.RELEASED:
                return res
            if res.state not in (ReservationState.RESERVED, ReservationState.RECONCILED_FAILURE):
                raise IllegalTransitionError(
                    f"release from {res.state.value} is forbidden: an uncertain or dispatched "
                    "reservation is never released without reconciliation")
            new = self._replace(res, state=ReservationState.RELEASED)
            self._append_reservation_event(new, "RELEASED", res.state, as_of)
            return new

    def reservation_events(self, reservation_id: str) -> tuple[ReservationEvent, ...]:
        with self._lock:
            self._guard()
            return tuple(self._reservation_events.get(reservation_id, ()))

    # ------------------------------------------------------------------ #
    # PriorConsumptionSource
    # ------------------------------------------------------------------ #
    def consumption_signal(self, execution_key: ExecutionKey, *, as_of: datetime,
                           freshness_s: int = 60) -> TrustedSignal:
        try:
            head = self.get_head(execution_key)
            unavailable = False
        except StoreUnavailableError:
            head, unavailable = None, True
        return build_consumption_signal(execution_key, head, as_of=as_of, freshness_s=freshness_s,
                                        unavailable=unavailable, source_id=self._source_id,
                                        provenance_ref=f"{self._source_id}:prior-consumption")

    # ------------------------------------------------------------------ #
    # Decision Authority ExecutionRepository — composed kernel reference adapter
    # ------------------------------------------------------------------ #
    def create_execution_intent(self, intent):
        self._guard(); return self._da.create_execution_intent(intent)

    def save_execution_snapshot(self, intent):
        self._guard(); return self._da.save_execution_snapshot(intent)

    def get_execution_intent(self, intent_id):
        self._guard(); return self._da.get_execution_intent(intent_id)

    def get_intent_history(self, intent_id):
        self._guard(); return self._da.get_intent_history(intent_id)

    def lookup_by_execution_idempotency_key(self, tenant_id, key):
        self._guard(); return self._da.lookup_by_execution_idempotency_key(tenant_id, key)

    def record_execution_attempt(self, attempt):
        self._guard(); return self._da.record_execution_attempt(attempt)

    def get_execution_attempt(self, attempt_id):
        self._guard(); return self._da.get_execution_attempt(attempt_id)

    def get_attempt_history(self, intent_id):
        self._guard(); return self._da.get_attempt_history(intent_id)

    def attempt_count(self, intent_id):
        self._guard(); return self._da.attempt_count(intent_id)

    def record_execution_record(self, record):
        self._guard(); return self._da.record_execution_record(record)

    def get_execution_records(self, intent_id):
        self._guard(); return self._da.get_execution_records(intent_id)

    def lookup_by_external_request_id(self, external_request_id):
        self._guard(); return self._da.lookup_by_external_request_id(external_request_id)

    def record_reconciliation_result(self, result):
        self._guard(); return self._da.record_reconciliation_result(result)

    def get_reconciliation_history(self, intent_id):
        self._guard(); return self._da.get_reconciliation_history(intent_id)

    def record_compensation_requirement(self, comp):
        self._guard(); return self._da.record_compensation_requirement(comp)

    def save_compensation_snapshot(self, comp):
        self._guard(); return self._da.save_compensation_snapshot(comp)

    def get_compensation(self, compensation_id):
        self._guard(); return self._da.get_compensation(compensation_id)

    def get_compensation_history(self, intent_id):
        self._guard(); return self._da.get_compensation_history(intent_id)
