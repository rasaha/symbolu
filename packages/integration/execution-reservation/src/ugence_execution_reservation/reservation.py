"""Execution reservation — vocabulary, record, port and the pure decision rules (phase G).

Everything that decides *without* touching a store lives here so the in-memory and
SQLite adapters share one set of rules:

* :func:`validate_receipt_for_reservation` — checks 1–9 of the design's validation
  list, all computed over the **immutable** receipt and the caller-supplied
  instant, so nothing here can race. Only the uniqueness decision races, and the
  adapters make it inside a single write transaction.
* :func:`classify_head` — what an existing reservation means for a new caller.
* :func:`observation_target` and :data:`STATE_RANK` — observations only move a
  reservation *forward*; a late or duplicate observation can never downgrade a
  terminal state, so any arrival order converges to one state.

The nine states, eight results and the uncertain-outcome rule are exactly the
design's (``EXECUTION_RESERVATION_STATE_MACHINE.md``, ``EXECUTION_RESERVATION_CONTRACT.md``).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from ugence_governance_contracts.api import (
    ExecutionBusinessOutcome,
    IdempotencyDisposition,
    IdempotencyResolution,
    Validity,
    ValidityStatus,
)

from ._canon import iso, require_tzaware
from .errors import ContractViolation, ReceiptIntegrityError
from .execution_key import ExecutionKey
from .receipts import ClearanceReceipt, ReceiptLifecycleState, verify_receipt_body

__all__ = [
    "ReservationState",
    "ReservationResult",
    "ReconciledOutcome",
    "ExecutionReservation",
    "ReservationEvent",
    "ReserveOnceOutcome",
    "ExecutionReservationPort",
    "validate_receipt_for_reservation",
    "classify_head",
    "observation_target",
    "STATE_RANK",
    "reservation_id_for",
]


class ReservationState(str, Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    DISPATCHED = "DISPATCHED"
    OBSERVED_SUCCESS = "OBSERVED_SUCCESS"
    OBSERVED_FAILURE = "OBSERVED_FAILURE"
    OUTCOME_UNCERTAIN = "OUTCOME_UNCERTAIN"
    RECONCILED_SUCCESS = "RECONCILED_SUCCESS"
    RECONCILED_FAILURE = "RECONCILED_FAILURE"
    RELEASED = "RELEASED"


class ReservationResult(str, Enum):
    ACQUIRED = "ACQUIRED"
    ALREADY_RESERVED = "ALREADY_RESERVED"
    ALREADY_DISPATCHED = "ALREADY_DISPATCHED"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"
    CONFLICT = "CONFLICT"
    INVALID_RECEIPT = "INVALID_RECEIPT"
    EXPIRED_CLEARANCE = "EXPIRED_CLEARANCE"
    STALE_AUTHORIZATION = "STALE_AUTHORIZATION"


class ReconciledOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


#: Forward-only ordering for post-dispatch states. A transition is applied only when
#: the target outranks the current state, so any arrival order converges.
STATE_RANK = {
    ReservationState.DISPATCHED: 1,
    ReservationState.OUTCOME_UNCERTAIN: 2,
    ReservationState.OBSERVED_FAILURE: 3,
    ReservationState.OBSERVED_SUCCESS: 4,
    ReservationState.RECONCILED_FAILURE: 5,
    ReservationState.RECONCILED_SUCCESS: 6,
}

#: Keys in these head states are free for a new reservation.
_REACQUIRABLE = frozenset({ReservationState.AVAILABLE, ReservationState.RELEASED,
                           ReservationState.RECONCILED_FAILURE})
_POST_DISPATCH = frozenset({ReservationState.DISPATCHED, ReservationState.OUTCOME_UNCERTAIN,
                            ReservationState.OBSERVED_FAILURE, ReservationState.OBSERVED_SUCCESS})


def reservation_id_for(key: ExecutionKey, generation: int) -> str:
    """Deterministic id: no UUID, no clock. Generation separates re-reservations."""

    return "rsv_" + hashlib.sha256(f"{key.serialized}:{generation}".encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class ExecutionReservation:
    reservation_id: str
    execution_key: ExecutionKey
    clearance_receipt_ref: str
    authorization_ref: str
    action_fingerprint: str
    state: ReservationState
    generation: int
    created_at: datetime
    reservation_ttl_s: int
    lease_expires_at: datetime
    dispatched_at: Optional[datetime] = None
    dispatch_deadline: Optional[datetime] = None
    dispatch_request_id: str = ""
    provider_operation_id: str = ""
    observation_refs: tuple[str, ...] = ()
    reconciliation_ref: str = ""

    @property
    def tenant_id(self) -> str:
        return self.execution_key.tenant_id

    @property
    def target_ref(self) -> str:
        return self.execution_key.target_ref

    @property
    def operation(self) -> str:
        return self.execution_key.operation

    @property
    def lease(self) -> Validity:
        """Bounds RESERVED pre-dispatch; a lapsed lease with no dispatch is abandoned."""

        return Validity(issued_at=self.created_at, expires_at=self.lease_expires_at)

    @property
    def dispatch_validity(self) -> Optional[Validity]:
        if self.dispatched_at is None or self.dispatch_deadline is None:
            return None
        return Validity(issued_at=self.dispatched_at, expires_at=self.dispatch_deadline)

    def is_abandoned_at(self, as_of: datetime) -> bool:
        return (self.state is ReservationState.RESERVED
                and self.lease.status_at(as_of) is ValidityStatus.EXPIRED)

    def to_dict(self) -> dict:
        return {
            "reservation_id": self.reservation_id,
            "execution_key": {
                "tenant_id": self.execution_key.tenant_id,
                "authorization_ref": self.execution_key.authorization_ref,
                "authorized_action_fingerprint": self.execution_key.authorized_action_fingerprint,
                "target_ref": self.execution_key.target_ref,
                "operation": self.execution_key.operation,
            },
            "execution_key_serialized": self.execution_key.serialized,
            "clearance_receipt_ref": self.clearance_receipt_ref,
            "authorization_ref": self.authorization_ref,
            "action_fingerprint": self.action_fingerprint,
            "state": self.state.value,
            "generation": self.generation,
            "created_at": iso(self.created_at),
            "reservation_ttl_s": self.reservation_ttl_s,
            "lease_expires_at": iso(self.lease_expires_at),
            "dispatched_at": iso(self.dispatched_at) if self.dispatched_at else None,
            "dispatch_deadline": iso(self.dispatch_deadline) if self.dispatch_deadline else None,
            "dispatch_request_id": self.dispatch_request_id,
            "provider_operation_id": self.provider_operation_id,
            "observation_refs": list(self.observation_refs),
            "reconciliation_ref": self.reconciliation_ref,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutionReservation":
        from ._canon import from_iso
        k = d["execution_key"]
        return cls(
            reservation_id=d["reservation_id"],
            execution_key=ExecutionKey(**k),
            clearance_receipt_ref=d["clearance_receipt_ref"],
            authorization_ref=d["authorization_ref"],
            action_fingerprint=d["action_fingerprint"],
            state=ReservationState(d["state"]),
            generation=int(d["generation"]),
            created_at=from_iso(d["created_at"]),
            reservation_ttl_s=int(d["reservation_ttl_s"]),
            lease_expires_at=from_iso(d["lease_expires_at"]),
            dispatched_at=from_iso(d["dispatched_at"]) if d.get("dispatched_at") else None,
            dispatch_deadline=from_iso(d["dispatch_deadline"]) if d.get("dispatch_deadline") else None,
            dispatch_request_id=d.get("dispatch_request_id", ""),
            provider_operation_id=d.get("provider_operation_id", ""),
            observation_refs=tuple(d.get("observation_refs", ())),
            reconciliation_ref=d.get("reconciliation_ref", ""),
        )


@dataclass(frozen=True)
class ReservationEvent:
    event_id: str
    reservation_id: str
    sequence: int
    event_type: str
    from_state: Optional[ReservationState]
    to_state: ReservationState
    occurred_at: datetime
    ref: str = ""

    def to_dict(self) -> dict:
        return {"event_id": self.event_id, "reservation_id": self.reservation_id,
                "sequence": self.sequence, "event_type": self.event_type,
                "from_state": self.from_state.value if self.from_state else None,
                "to_state": self.to_state.value, "occurred_at": iso(self.occurred_at),
                "ref": self.ref}


@dataclass(frozen=True)
class ReserveOnceOutcome:
    result: ReservationResult
    reservation: Optional[ExecutionReservation]
    reason: str = ""

    @property
    def is_acquired(self) -> bool:
        return self.result is ReservationResult.ACQUIRED

    @property
    def resolution(self) -> Optional[IdempotencyResolution]:
        """Neutral projection. Refusals (INVALID_RECEIPT, EXPIRED_CLEARANCE,
        STALE_AUTHORIZATION) are not resolutions and project to ``None``."""

        if self.reservation is None and self.result is not ReservationResult.CONFLICT:
            return None
        key = (self.reservation.execution_key if self.reservation is not None else None)
        if key is None:
            return None
        ik = key.to_idempotency_key()
        if self.result is ReservationResult.ACQUIRED:
            return IdempotencyResolution(key=ik, disposition=IdempotencyDisposition.FIRST)
        if self.result in (ReservationResult.ALREADY_RESERVED, ReservationResult.ALREADY_DISPATCHED,
                           ReservationResult.ALREADY_COMPLETED):
            return IdempotencyResolution(key=ik, disposition=IdempotencyDisposition.DUPLICATE,
                                         duplicate_of=self.reservation.reservation_id)
        return IdempotencyResolution(key=ik, disposition=IdempotencyDisposition.UNKNOWN)


# --------------------------------------------------------------------------- #
# Pure decision rules
# --------------------------------------------------------------------------- #
def validate_receipt_for_reservation(
    receipt: Optional[ClearanceReceipt],
    lifecycle: Optional[ReceiptLifecycleState],
    key: ExecutionKey,
    expected_authorization_ref: str,
    expected_action_fingerprint: str,
    as_of: datetime,
) -> Optional[tuple[ReservationResult, str]]:
    """Checks 1–9. ``None`` means the receipt admits a reservation for ``key``."""

    require_tzaware(as_of, "reserve_once.as_of")
    if receipt is None:
        return ReservationResult.INVALID_RECEIPT, "receipt missing"
    try:
        verify_receipt_body(receipt.body)
    except ReceiptIntegrityError as exc:
        return ReservationResult.INVALID_RECEIPT, f"receipt body altered: {exc}"
    if not receipt.is_clear:
        return ReservationResult.INVALID_RECEIPT, f"receipt status {receipt.body.clearance_status.value} is not CLEAR"
    if receipt.tenant_id != key.tenant_id:
        return ReservationResult.INVALID_RECEIPT, "tenant mismatch"
    if receipt.authorization_ref != expected_authorization_ref or receipt.authorization_ref != key.authorization_ref:
        return ReservationResult.INVALID_RECEIPT, "authorization mismatch"
    if (receipt.authorized_action_fingerprint != expected_action_fingerprint
            or receipt.authorized_action_fingerprint != key.authorized_action_fingerprint):
        return ReservationResult.INVALID_RECEIPT, "action fingerprint mismatch"
    if receipt.target_ref != key.target_ref:
        return ReservationResult.INVALID_RECEIPT, "target mismatch"
    if receipt.operation != key.operation:
        return ReservationResult.INVALID_RECEIPT, "operation mismatch"
    if lifecycle is None:
        return ReservationResult.INVALID_RECEIPT, "receipt was never ISSUED"
    if lifecycle is ReceiptLifecycleState.REVOKED:
        return ReservationResult.STALE_AUTHORIZATION, "receipt revoked by upstream event"
    if lifecycle in (ReceiptLifecycleState.SUPERSEDED, ReceiptLifecycleState.INVALIDATED):
        return ReservationResult.INVALID_RECEIPT, f"receipt lifecycle is {lifecycle.value}"
    status = receipt.validity.status_at(as_of)
    if status is ValidityStatus.EXPIRED:
        return ReservationResult.EXPIRED_CLEARANCE, "receipt past valid_until"
    if status is ValidityStatus.NOT_YET_VALID:
        return ReservationResult.INVALID_RECEIPT, "reservation instant precedes evaluation"
    return None


def classify_head(head: Optional[ExecutionReservation], as_of: datetime) -> Optional[ReservationResult]:
    """What an existing head reservation means for a new caller; ``None`` = key is free.

    A RESERVED head whose lease lapsed with no dispatch is *abandoned* and also
    reports ``None`` (the adapter releases it, then acquires). DISPATCHED and
    OUTCOME_UNCERTAIN are never treated as free — that is the uncertain-outcome rule.
    """

    if head is None or head.state in _REACQUIRABLE:
        return None
    if head.state is ReservationState.RESERVED:
        return None if head.is_abandoned_at(as_of) else ReservationResult.ALREADY_RESERVED
    if head.state in (ReservationState.DISPATCHED, ReservationState.OUTCOME_UNCERTAIN,
                      ReservationState.OBSERVED_FAILURE):
        return ReservationResult.ALREADY_DISPATCHED
    if head.state in (ReservationState.OBSERVED_SUCCESS, ReservationState.RECONCILED_SUCCESS):
        return ReservationResult.ALREADY_COMPLETED
    return ReservationResult.CONFLICT


def observation_target(outcome: ExecutionBusinessOutcome) -> ReservationState:
    if outcome in (ExecutionBusinessOutcome.SUCCEEDED, ExecutionBusinessOutcome.DUPLICATE):
        return ReservationState.OBSERVED_SUCCESS
    if outcome in (ExecutionBusinessOutcome.FAILED, ExecutionBusinessOutcome.REJECTED):
        return ReservationState.OBSERVED_FAILURE
    return ReservationState.OUTCOME_UNCERTAIN


def lease_end(created_at: datetime, reservation_ttl_s: int) -> datetime:
    if not isinstance(reservation_ttl_s, int) or reservation_ttl_s <= 0:
        raise ContractViolation("reservation_ttl_s must be a positive integer")
    return created_at + timedelta(seconds=reservation_ttl_s)


def is_post_dispatch(state: ReservationState) -> bool:
    return state in _POST_DISPATCH


# --------------------------------------------------------------------------- #
# Port
# --------------------------------------------------------------------------- #
@runtime_checkable
class ExecutionReservationPort(Protocol):
    def reserve_once(self, execution_key: ExecutionKey, clearance_receipt_ref: str,
                     expected_authorization_ref: str, expected_action_fingerprint: str,
                     reservation_ttl_s: int, *, as_of: datetime) -> ReserveOnceOutcome: ...
    def get_reservation(self, reservation_id: str) -> Optional[ExecutionReservation]: ...
    def get_head(self, execution_key: ExecutionKey) -> Optional[ExecutionReservation]: ...
    def mark_dispatched(self, reservation_id: str, dispatch_request_id: str, *,
                        dispatch_deadline: datetime, as_of: datetime,
                        provider_operation_id: str = "") -> ExecutionReservation: ...
    def mark_outcome_uncertain(self, reservation_id: str, *, as_of: datetime) -> ExecutionReservation: ...
    def renew_lease(self, reservation_id: str, *, lease_expires_at: datetime,
                    as_of: datetime) -> ExecutionReservation: ...
    def record_observation(self, reservation_id: str, observation_ref: str,
                           outcome: ExecutionBusinessOutcome, *, as_of: datetime) -> ExecutionReservation: ...
    def record_reconciliation(self, reservation_id: str, reconciliation_ref: str,
                              outcome: ReconciledOutcome, *, as_of: datetime) -> ExecutionReservation: ...
    def release(self, reservation_id: str, *, as_of: datetime) -> ExecutionReservation: ...
    def reservation_events(self, reservation_id: str) -> tuple[ReservationEvent, ...]: ...

