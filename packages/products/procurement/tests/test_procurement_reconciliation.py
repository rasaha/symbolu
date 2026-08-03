"""Procurement reconciliation: matched, mismatch, compensation."""

from __future__ import annotations

from ugence_procurement.routes import ProcurementAPI
from ugence_procurement.actions import CREATE_PURCHASE_ORDER
from ugence_procurement.approvals import PurchaseApproval, PurchaseRecommendation
from ugence_procurement.suppliers import SupplierOutcome

from .conftest import APPROVER, REQUESTER, build_platform, make_request


def _drive_to_dispatch(api, platform, request):
    case, _ = api.submit_and_assess(request, actor=REQUESTER)
    api.recommend(case_id=case.decision_case_id,
                  recommendation=PurchaseRecommendation.APPROVE, generated_by=REQUESTER)
    decision = api.decide(case_id=case.decision_case_id,
                          approval=PurchaseApproval.APPROVED, approver=APPROVER)
    req = api.request_action(decision=decision, request=request, actor=APPROVER)
    api.authorize(action_request_id=req.action_request_id, actor=APPROVER)
    intent = platform.execution_service.create_execution_intent(
        action_request_id=req.action_request_id, created_by=APPROVER)
    platform.execution_service.dispatch_execution(
        intent_id=intent.execution_intent_id, actor=APPROVER)
    return intent


def test_matched_outcome_reconciles():
    platform = build_platform()
    api = ProcurementAPI(platform)
    intent = _drive_to_dispatch(api, platform, make_request())
    platform.reconciliation_service.query_external_status(
        intent_id=intent.execution_intent_id, actor=APPROVER)
    result = platform.reconciliation_service.reconcile_execution(
        intent_id=intent.execution_intent_id, actor=APPROVER)
    assert result.status.value == "RECONCILED"


def test_mismatched_observed_parameters():
    platform = build_platform()
    # Supplier reports a different amount than authorized.
    platform.supplier_adapter._observed_overrides = {
        CREATE_PURCHASE_ORDER: {"amount": "999", "supplier_id": "sup-1", "budget_id": "bud-1"}}
    api = ProcurementAPI(platform)
    intent = _drive_to_dispatch(api, platform, make_request())
    platform.reconciliation_service.query_external_status(
        intent_id=intent.execution_intent_id, actor=APPROVER)
    result = platform.reconciliation_service.reconcile_execution(
        intent_id=intent.execution_intent_id, actor=APPROVER)
    assert result.status.value == "MISMATCHED"


def test_compensation_requirement_lifecycle():
    platform = build_platform()
    platform.supplier_adapter._outcomes = {CREATE_PURCHASE_ORDER: SupplierOutcome.REJECTED}
    api = ProcurementAPI(platform)
    intent = _drive_to_dispatch(api, platform, make_request())
    platform.reconciliation_service.query_external_status(
        intent_id=intent.execution_intent_id, actor=APPROVER)
    result = platform.reconciliation_service.reconcile_execution(
        intent_id=intent.execution_intent_id, actor=APPROVER)
    assert result.status.value == "COMPENSATION_REQUIRED"

    # A compensation requirement can be raised and resolved through the kernel.
    requirement = platform.compensation_service.create_compensation_requirement(
        intent_id=intent.execution_intent_id, reconciliation_id=result.reconciliation_id,
        actor=APPROVER, reason_codes=("SUPPLIER_REJECTED",))
    resolved = platform.compensation_service.resolve_compensation_requirement(
        compensation_id=requirement.compensation_id, actor=APPROVER,
        resolution_ref="cancelled-po-123")
    assert resolved.compensation_id == requirement.compensation_id
