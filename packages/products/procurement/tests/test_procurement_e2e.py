"""Procurement end-to-end: purchase request → … → reconciliation on the kernel."""

from __future__ import annotations

from ugence_decision_authority.audit import AuditEventType, audit_namespace, AuditNamespace

from ugence_procurement.routes import ProcurementAPI
from ugence_procurement.approvals import PurchaseApproval, PurchaseRecommendation

from .conftest import APPROVER, REQUESTER, build_platform, make_request


def test_full_lifecycle_runs_on_the_kernel():
    platform = build_platform()
    api = ProcurementAPI(platform)
    result = api.run(
        request=make_request(), requester=REQUESTER, approver=APPROVER,
        recommendation=PurchaseRecommendation.APPROVE, approval=PurchaseApproval.APPROVED)

    assert result.authorization_outcome == "AUTHORIZED"
    assert result.reconciliation_status == "RECONCILED"
    assert not result.compensation_required

    # The whole chain was audited on the kernel.
    emitted = {e.event_type for e in platform.audit_service._repo.all()}
    assert AuditEventType.DECISION_CASE_CREATED in emitted
    assert AuditEventType.DECISION_RECORDED in emitted
    assert AuditEventType.ACTION_AUTHORIZATION_GRANTED in emitted
    assert AuditEventType.EXECUTION_RECONCILED in emitted


def test_procurement_emits_only_kernel_namespace_events():
    """A structurally different domain still emits only KERNEL governance events —
    never a hiring-domain event."""
    platform = build_platform()
    api = ProcurementAPI(platform)
    api.run(request=make_request(), requester=REQUESTER, approver=APPROVER)
    emitted = {e.event_type for e in platform.audit_service._repo.all()}
    non_kernel = {e for e in emitted if audit_namespace(e) is not AuditNamespace.KERNEL}
    assert not non_kernel, f"procurement emitted non-kernel events: {non_kernel}"


def test_rejected_request_maps_to_cancel_action():
    platform = build_platform()
    api = ProcurementAPI(platform)
    request = make_request()
    case, _ = api.submit_and_assess(request, actor=REQUESTER)
    api.recommend(case_id=case.decision_case_id,
                  recommendation=PurchaseRecommendation.REJECT, generated_by=REQUESTER)
    decision = api.decide(case_id=case.decision_case_id,
                          approval=PurchaseApproval.REJECTED, approver=APPROVER)
    req = api.request_action(decision=decision, request=request, actor=APPROVER)
    assert req.action_type == "CANCEL_REQUEST"
