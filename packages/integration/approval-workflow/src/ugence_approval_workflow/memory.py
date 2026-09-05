"""In-memory reference adapter — tests and local composition, refused in production.

Process-local, protected by one re-entrant lock. It implements the same rules as the
SQLite adapter by calling the same pure transition functions; only storage differs.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Optional

from ugence_governance_contracts.api import Validity

from ._canon import require_nonempty, require_tzaware
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

__all__ = ["InMemoryApprovalWorkflowStore"]


class InMemoryApprovalWorkflowStore:
    """Reference adapter for :class:`~ugence_approval_workflow.ports.ApprovalWorkflowPort`."""

    maturity = MATURITY

    def __init__(self, eligibility: ApproverEligibilityPort, *,
                 production_mode: bool = False) -> None:
        if production_mode:
            raise ProductionModeRefused(
                "InMemoryApprovalWorkflowStore is a test reference adapter and is refused "
                "in production mode; use SqliteApprovalWorkflowStore on a file path")
        if not isinstance(eligibility, ApproverEligibilityPort):
            raise ContractViolation(
                "an ApproverEligibilityPort is required at construction; without one the "
                "package would record decisions by nobody in particular")
        self._eligibility = eligibility
        self._lock = threading.RLock()
        self._closed = False
        self._records: dict[str, ApprovalRecord] = {}
        self._events: dict[str, list[ApprovalEvent]] = {}
        self._consumptions: dict[str, tuple[str, str]] = {}  # serialized key -> (id, approval_id)

    # ------------------------------------------------------------------ #
    def close(self) -> None:
        self._closed = True

    def _guard(self) -> None:
        if self._closed:
            raise StoreUnavailableError("store closed")

    def _require(self, approval_id: str) -> ApprovalRecord:
        record = self._records.get(require_nonempty(approval_id, "approval_id"))
        if record is None:
            raise ApprovalNotFoundError(f"no approval '{approval_id}'")
        return record

    def _append(self, record: ApprovalRecord, occurred_at: datetime, actor: str,
                detail: str = "") -> ApprovalEvent:
        events = self._events.setdefault(record.approval_id, [])
        seq = len(events)
        event = ApprovalEvent(event_id=f"{record.approval_id}:{seq}", approval_id=record.approval_id,
                              sequence=seq, event_type=record.state, occurred_at=occurred_at,
                              actor=actor, detail=detail)
        events.append(event)
        return event

    def _store(self, record: ApprovalRecord, occurred_at: datetime, actor: str,
               detail: str = "") -> ApprovalRecord:
        self._records[record.approval_id] = record
        self._append(record, occurred_at, actor, detail)
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
        with self._lock:
            self._guard()
            if record.supersedes:
                refusal = superseding_refusal(self._records.get(record.supersedes), subject)
                if refusal:
                    raise ContractViolation(refusal)
            if record.approval_id in self._records:
                raise ApprovalAlreadyExistsError(
                    f"approval '{record.approval_id}' already exists; raise a new request with "
                    "a higher request_ordinal rather than reusing a standing decision")
            return self._store(record, as_of, requested_by, subject.subject_kind)

    def present_for_decision(self, approval_id: str, *, as_of: datetime) -> ApprovalRecord:
        with self._lock:
            self._guard()
            record = self._require(approval_id)
            approvers = self._eligibility.eligible_approvers(
                tenant_id=record.tenant_id, subject_kind=record.subject_kind,
                subject_digest=record.subject_digest, required_role=record.required_role,
                as_of=as_of)
            evolved = next_on_present(record, as_of=as_of, eligible_approvers=tuple(approvers))
            return self._store(evolved, as_of, "", f"eligible={len(approvers)}")

    def _eligibility_for(self, record: ApprovalRecord, approver: ApproverRef, as_of: datetime):
        return self._eligibility.is_eligible(
            tenant_id=record.tenant_id, approver=approver, required_role=record.required_role,
            scope=f"{record.subject_kind}:{record.subject_digest}", as_of=as_of)

    def decide(self, approval_id: str, *, approver: ApproverRef, decision: ReviewDecision,
               as_of: datetime, justification: str = "",
               accepted_finding_ids: tuple[str, ...] = (),
               signature_reference: str = "",
               authentication_reference: str = "") -> ApprovalRecord:
        with self._lock:
            self._guard()
            record = self._require(approval_id)
            evolved = next_on_decide(
                record, approver=approver, decision=decision,
                eligibility=self._eligibility_for(record, approver, as_of), as_of=as_of,
                justification=justification, accepted_finding_ids=accepted_finding_ids,
                signature_reference=signature_reference,
                authentication_reference=authentication_reference)
            return self._store(evolved, as_of, approver.approver_id, decision.value)

    def request_exception(self, approval_id: str, *, requested_by: str, justification: str,
                          exception_validity: Validity, as_of: datetime) -> ApprovalRecord:
        with self._lock:
            self._guard()
            record = self._require(approval_id)
            evolved = next_on_exception_request(
                record, requested_by=requested_by, justification=justification,
                exception_validity=exception_validity, as_of=as_of)
            return self._store(evolved, as_of, requested_by, "exception requested")

    def decide_exception(self, approval_id: str, *, approver: ApproverRef, granted: bool,
                         as_of: datetime, justification: str = "",
                         signature_reference: str = "") -> ApprovalRecord:
        with self._lock:
            self._guard()
            record = self._require(approval_id)
            evolved = next_on_exception_decision(
                record, approver=approver, granted=granted,
                eligibility=self._eligibility_for(record, approver, as_of), as_of=as_of,
                justification=justification, signature_reference=signature_reference)
            return self._store(evolved, as_of, approver.approver_id, "exception decided")

    def withdraw(self, approval_id: str, *, by: str, as_of: datetime,
                 justification: str = "") -> ApprovalRecord:
        with self._lock:
            self._guard()
            record = self._require(approval_id)
            evolved = next_on_withdraw(record, by=by, as_of=as_of, justification=justification)
            return self._store(evolved, as_of, by, "withdrawn")

    def consume(self, approval_id: str, *, consumer_ref: str, subject_digest: str,
                as_of: datetime) -> ConsumeOutcome:
        require_tzaware(as_of, "consume.as_of")
        with self._lock:
            self._guard()
            record = self._records.get(approval_id)
            tenant = record.tenant_id if record is not None else "unknown"
            key = ConsumptionKey(tenant_id=tenant, approval_id=approval_id,
                                 subject_digest=subject_digest, consumer_ref=consumer_ref)
            held = self._consumptions.get(key.serialized)
            if held is not None:
                return ConsumeOutcome(ConsumptionResult.ALREADY_CONSUMED, key,
                                      consumption_id=held[0], holder=held[0],
                                      reason="this consumption key is already held")
            refusal = validate_for_consumption(record, key, as_of)
            if refusal is not None:
                result, reason = refusal
                holder = self._consumptions.get(key.serialized, ("", ""))[0]
                return ConsumeOutcome(result, key, holder=holder, reason=reason)
            if record is None:  # unreachable: a missing record is already NOT_GRANTED
                return ConsumeOutcome(ConsumptionResult.UNKNOWN, key, reason="record vanished")
            consumption_id = consumption_id_for(key)
            evolved = next_on_consume(record, consumer_ref=consumer_ref, as_of=as_of)
            self._consumptions[key.serialized] = (consumption_id, approval_id)
            self._store(evolved, as_of, consumer_ref, consumption_id)
            return ConsumeOutcome(ConsumptionResult.CONSUMED_FIRST, key,
                                  consumption_id=consumption_id)

    # ------------------------------------------------------------------ #
    def get_approval(self, approval_id: str) -> Optional[ApprovalRecord]:
        with self._lock:
            self._guard()
            return self._records.get(approval_id)

    def state_at(self, approval_id: str, *, as_of: datetime) -> ApprovalState:
        with self._lock:
            self._guard()
            return self._require(approval_id).state_at(as_of)

    def list_open(self, *, tenant_id: str, required_role: str = "",
                  as_of: datetime) -> tuple[ApprovalRecord, ...]:
        require_tzaware(as_of, "list_open.as_of")
        role = required_role.strip()
        with self._lock:
            self._guard()
            return tuple(sorted(
                (r for r in self._records.values()
                 if r.tenant_id == tenant_id and r.state_at(as_of) in OPEN_STATES
                 and (not role or r.required_role == role)),
                key=lambda r: r.approval_id))

    def approval_events(self, approval_id: str) -> tuple[ApprovalEvent, ...]:
        with self._lock:
            self._guard()
            return tuple(self._events.get(approval_id, ()))
