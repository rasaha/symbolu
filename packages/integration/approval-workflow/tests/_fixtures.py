"""Shared builders. Every instant is explicit; no test reads a clock either."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from ugence_governance_contracts.api import Validity

from ugence_approval_workflow import (
    ApprovalSubject,
    ApproverKind,
    ApproverRef,
    InMemoryApprovalWorkflowStore,
    SqliteApprovalWorkflowStore,
    StaticApproverEligibility,
)

TENANT = "tenant-a"
SUBJECT_KIND = "decision_case"
DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64
REQUESTER = "requester-1"
ROLE = "risk-approver"

T0 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(minutes=5)
T2 = T0 + timedelta(minutes=10)
AFTER_WINDOW = T0 + timedelta(days=8)

APPROVER = ApproverRef(approver_id="approver-1", approver_kind=ApproverKind.HUMAN, role=ROLE,
                       authority_reference="directory://roles/risk-approver")
SECOND_APPROVER = ApproverRef(approver_id="approver-2", approver_kind=ApproverKind.HUMAN, role=ROLE)
AI_APPROVER = ApproverRef(approver_id="model-7", approver_kind=ApproverKind.AI, role=ROLE)


def subject(digest: str = DIGEST, *, kind: str = SUBJECT_KIND, tenant: str = TENANT) -> ApprovalSubject:
    return ApprovalSubject(tenant_id=tenant, subject_kind=kind, subject_digest=digest,
                           subject_ref="case_1")


def window(issued: datetime = T0, *, days: int = 7) -> Validity:
    return Validity(issued_at=issued, expires_at=issued + timedelta(days=days))


def directory(*approvers: ApproverRef) -> StaticApproverEligibility:
    return StaticApproverEligibility(approvers or (APPROVER, SECOND_APPROVER))


def sqlite_path(tmp_path) -> str:
    return os.path.join(str(tmp_path), "approvals.sqlite3")


def memory_store(*approvers: ApproverRef) -> InMemoryApprovalWorkflowStore:
    return InMemoryApprovalWorkflowStore(directory(*approvers))


def sqlite_store(tmp_path, *approvers: ApproverRef) -> SqliteApprovalWorkflowStore:
    return SqliteApprovalWorkflowStore(sqlite_path(tmp_path), directory(*approvers))


def granted(store, *, as_of=T1, approver: ApproverRef = APPROVER):
    """Drive one approval to GRANTED through the real transitions."""

    from ugence_approval_workflow import ReviewDecision

    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    store.present_for_decision(record.approval_id, as_of=T0)
    return store.decide(record.approval_id, approver=approver,
                        decision=ReviewDecision.GRANT, as_of=as_of)
