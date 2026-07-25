"""Procurement execution: supplier accepted / rejected / unknown / timeout / dup."""

from __future__ import annotations

import pytest

from decision_governance.errors import InvalidExecutionTransitionError

from applications.procurement import ProcurementConfiguration
from applications.procurement.api import ProcurementAPI
from domains.procurement.actions import CREATE_PURCHASE_ORDER
from domains.procurement.approvals import PurchaseApproval, PurchaseRecommendation
from domains.procurement.suppliers import SupplierOutcome

from .conftest import APPROVER, REQUESTER, build_platform, make_request


def _to_authorized_request(api, request):
    case, _ = api.submit_and_assess(request, actor=REQUESTER)
    api.recommend(case_id=case.decision_case_id,
                  recommendation=PurchaseRecommendation.APPROVE, generated_by=REQUESTER)
    decision = api.decide(case_id=case.decision_case_id,
                          approval=PurchaseApproval.APPROVED, approver=APPROVER)
    req = api.request_action(decision=decision, request=request, actor=APPROVER)
    api.authorize(action_request_id=req.action_request_id, actor=APPROVER)
    return req


def test_supplier_accepted_reconciles():
    platform = build_platform()
    api = ProcurementAPI(platform)
    result = api.run(request=make_request(), requester=REQUESTER, approver=APPROVER)
    assert result.reconciliation_status == "RECONCILED"


def test_supplier_rejected_requires_compensation():
    platform = build_platform()
    platform.supplier_adapter._outcomes = {CREATE_PURCHASE_ORDER: SupplierOutcome.REJECTED}
    api = ProcurementAPI(platform)
    result = api.run(request=make_request(), requester=REQUESTER, approver=APPROVER)
    assert result.reconciliation_status == "COMPENSATION_REQUIRED"
    assert result.compensation_required


def test_supplier_unknown_is_indeterminate():
    platform = build_platform()
    platform.supplier_adapter._outcomes = {CREATE_PURCHASE_ORDER: SupplierOutcome.UNKNOWN}
    api = ProcurementAPI(platform)
    result = api.run(request=make_request(), requester=REQUESTER, approver=APPROVER)
    assert result.reconciliation_status == "INDETERMINATE"


def test_supplier_transport_timeout_is_recorded():
    platform = build_platform(
        ProcurementConfiguration(supplier_timing_out=frozenset({CREATE_PURCHASE_ORDER})))
    api = ProcurementAPI(platform)
    req = _to_authorized_request(api, make_request())
    intent = platform.execution_service.create_execution_intent(
        action_request_id=req.action_request_id, created_by=APPROVER)
    attempt = platform.execution_service.dispatch_execution(
        intent_id=intent.execution_intent_id, actor=APPROVER)
    assert attempt.transport_status.value == "TIMED_OUT"


def test_duplicate_dispatch_is_rejected():
    platform = build_platform()
    api = ProcurementAPI(platform)
    req = _to_authorized_request(api, make_request())
    intent = platform.execution_service.create_execution_intent(
        action_request_id=req.action_request_id, created_by=APPROVER)
    platform.execution_service.dispatch_execution(
        intent_id=intent.execution_intent_id, actor=APPROVER)
    with pytest.raises(InvalidExecutionTransitionError):
        platform.execution_service.dispatch_execution(
            intent_id=intent.execution_intent_id, actor=APPROVER)
