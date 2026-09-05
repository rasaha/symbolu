"""Pure transition rules — shared by both adapters, storing nothing.

Every function takes the immutable record and the caller's instant and returns the
next snapshot, or raises a typed refusal. Both adapters call these, so the state
machine has one implementation and the adapters differ only in storage and in how
the single racing consumption is serialized.

An expired record refuses every transition except the derived read: a decision on a
lapsed request would be a decision nobody may make.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ugence_governance_contracts.api import Validity

from ._canon import optional_text, require_nonempty, require_tzaware
from .eligibility import ApproverRef, EligibilityDecision, structural_refusals
from .errors import ContractViolation, EligibilityRefused, IllegalTransitionError
from .records import ApprovalRecord
from .states import ApprovalState, ReviewDecision, require_transition, state_for_decision
from .subject import ApprovalSubject, approval_id_for

__all__ = [
    "build_request", "next_on_present", "next_on_decide", "next_on_exception_request",
    "next_on_exception_decision", "next_on_withdraw", "next_on_consume",
    "superseding_refusal",
]


def _live_state(record: ApprovalRecord, as_of: datetime) -> ApprovalState:
    """The state to transition from, with ``EXPIRED`` already derived."""

    state = record.state_at(require_tzaware(as_of, "as_of"))
    if state is ApprovalState.EXPIRED and record.state is not ApprovalState.EXPIRED:
        raise IllegalTransitionError(
            f"approval '{record.approval_id}' lapsed at "
            f"{record.effective_validity().expires_at}; it can no longer be acted on")
    return state


def build_request(subject: ApprovalSubject, *, requested_by: str, required_role: str,
                  validity: Validity, as_of: datetime, request_ordinal: int = 1,
                  supersedes: str = "", justification: str = "",
                  is_fixture: bool = False) -> ApprovalRecord:
    """The opening ``REQUESTED`` snapshot. Its id is derived, never random."""

    require_tzaware(as_of, "request_approval.as_of")
    if not isinstance(validity, Validity):
        raise ContractViolation("request_approval.validity must be a governance-contracts Validity")
    requester = require_nonempty(requested_by, "requested_by")
    return ApprovalRecord(
        approval_id=approval_id_for(subject, requester, request_ordinal),
        tenant_id=subject.tenant_id, subject_kind=subject.subject_kind,
        subject_digest=subject.subject_digest, subject_ref=subject.subject_ref,
        requested_by=requester, required_role=optional_text(required_role, "required_role"),
        state=ApprovalState.REQUESTED, validity=validity, request_ordinal=request_ordinal,
        supersedes=optional_text(supersedes, "supersedes"),
        justification=optional_text(justification, "justification"), is_fixture=is_fixture)


def next_on_present(record: ApprovalRecord, *, as_of: datetime,
                    eligible_approvers: tuple[ApproverRef, ...]) -> ApprovalRecord:
    """``REQUESTED -> PENDING``. An empty eligible set is a refusal, not a pending queue."""

    current = _live_state(record, as_of)
    require_transition(current, ApprovalState.PENDING)
    if not eligible_approvers:
        raise EligibilityRefused(
            f"no approver is eligible for '{record.required_role or 'any role'}' at {as_of}; "
            "an approval with nobody able to decide it is never presented")
    return record.evolve(state=ApprovalState.PENDING)


def next_on_decide(record: ApprovalRecord, *, approver: ApproverRef, decision: ReviewDecision,
                   eligibility: EligibilityDecision, as_of: datetime, justification: str = "",
                   accepted_finding_ids: tuple[str, ...] = (),
                   signature_reference: str = "",
                   authentication_reference: str = "") -> ApprovalRecord:
    """``PENDING -> GRANTED | REJECTED | CHANGES_REQUIRED``, recorded not granted.

    ``authentication_reference`` (ID-2, AI-D) is the caller's digest-bound reference
    to the verified claims that proved ``approver``; this package records it and
    verifies nothing about it, exactly as it records ``decided_authority_reference``.
    """

    current = _live_state(record, as_of)
    target = state_for_decision(decision)
    require_transition(current, target)
    refusals = structural_refusals(approver=approver, requested_by=record.requested_by,
                                   required_role=record.required_role, decision=eligibility)
    if refusals:
        raise EligibilityRefused("; ".join(refusals))
    return record.evolve(
        state=target, decided_by=approver.approver_id, decided_role=approver.role,
        decided_authority_reference=approver.authority_reference, decided_at=as_of,
        justification=optional_text(justification, "justification") or record.justification,
        accepted_finding_ids=tuple(accepted_finding_ids),
        signature_reference=optional_text(signature_reference, "signature_reference"),
        authentication_reference=optional_text(authentication_reference,
                                               "authentication_reference"))


def next_on_exception_request(record: ApprovalRecord, *, requested_by: str, justification: str,
                              exception_validity: Validity, as_of: datetime) -> ApprovalRecord:
    """``PENDING -> EXCEPTION_REQUESTED``, carrying its own bounded window (D-2).

    An exception is a scoped, time-boxed deviation with a stated justification. It is
    never an open-ended waiver, so an unbounded window is refused.
    """

    current = _live_state(record, as_of)
    require_transition(current, ApprovalState.EXCEPTION_REQUESTED)
    if not isinstance(exception_validity, Validity):
        raise ContractViolation("exception_validity must be a governance-contracts Validity")
    if exception_validity.expires_at is None:
        raise ContractViolation(
            "an exception must be time-boxed: exception_validity requires expires_at")
    return record.evolve(
        state=ApprovalState.EXCEPTION_REQUESTED,
        exception_requested_by=require_nonempty(requested_by, "requested_by"),
        exception_justification=require_nonempty(justification, "exception justification"),
        exception_validity=exception_validity)


def next_on_exception_decision(record: ApprovalRecord, *, approver: ApproverRef, granted: bool,
                               eligibility: EligibilityDecision, as_of: datetime,
                               justification: str = "",
                               signature_reference: str = "") -> ApprovalRecord:
    """``EXCEPTION_REQUESTED -> EXCEPTION_GRANTED | EXCEPTION_DENIED``.

    The same structural rules as an ordinary decision: an exception is not a second
    approval route around them.
    """

    current = _live_state(record, as_of)
    target = ApprovalState.EXCEPTION_GRANTED if granted else ApprovalState.EXCEPTION_DENIED
    require_transition(current, target)
    refusals = structural_refusals(approver=approver, requested_by=record.exception_requested_by
                                   or record.requested_by,
                                   required_role=record.required_role, decision=eligibility)
    if refusals:
        raise EligibilityRefused("; ".join(refusals))
    return record.evolve(
        state=target, decided_by=approver.approver_id, decided_role=approver.role,
        decided_authority_reference=approver.authority_reference, decided_at=as_of,
        exception_justification=optional_text(justification, "justification")
        or record.exception_justification,
        signature_reference=optional_text(signature_reference, "signature_reference"))


def next_on_withdraw(record: ApprovalRecord, *, by: str, as_of: datetime,
                     justification: str = "") -> ApprovalRecord:
    """Withdrawal by the requester's side. Terminal; a new request starts fresh."""

    current = _live_state(record, as_of)
    require_transition(current, ApprovalState.WITHDRAWN)
    return record.evolve(state=ApprovalState.WITHDRAWN, decided_by=require_nonempty(by, "by"),
                         decided_at=as_of,
                         justification=optional_text(justification, "justification")
                         or record.justification)


def next_on_consume(record: ApprovalRecord, *, consumer_ref: str,
                    as_of: datetime) -> ApprovalRecord:
    """``GRANTED | EXCEPTION_GRANTED -> CONSUMED``. Admissibility is checked first,
    by :func:`~ugence_approval_workflow.consumption.validate_for_consumption`."""

    require_tzaware(as_of, "consume.as_of")
    require_transition(record.state, ApprovalState.CONSUMED)
    return record.evolve(state=ApprovalState.CONSUMED,
                         consumer_ref=require_nonempty(consumer_ref, "consumer_ref"),
                         consumed_at=as_of)


def superseding_refusal(prior: Optional[ApprovalRecord], subject: ApprovalSubject) -> str:
    """Why a superseding request is inadmissible, or ``""``.

    Re-review after ``CHANGES_REQUIRED`` must bind a *different* subject digest: a
    changed subject never inherits a standing decision.
    """

    if prior is None:
        return "the superseded approval does not exist"
    if prior.subject_digest == subject.subject_digest:
        return ("a superseding request must bind a different subject digest; "
                "resubmitting the same subject would reuse a standing decision")
    if prior.tenant_id != subject.tenant_id:
        return "a superseding request must stay within the same tenant"
    return ""
