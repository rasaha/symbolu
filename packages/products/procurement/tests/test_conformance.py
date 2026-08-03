"""Run the reusable kernel conformance kit against the Procurement domain."""

from __future__ import annotations

from ugence_decision_authority.api.repositories import (
    InMemoryActionRequestRepository,
    InMemoryDecisionCaseRepository,
    InMemoryExecutionRepository,
)
from ugence_decision_authority.api.services import (
    ActionAuthorizationService,
    ActionRequestService,
    CaseDecisionService,
    DecisionCaseService,
    ExecutionService,
    ReconciliationService,
)
from ugence_decision_authority.conformance import (
    LifecycleOutcome,
    SimpleFixture,
    run_domain_conformance,
)

from ugence_procurement.routes import ProcurementAPI
from ugence_procurement.approvals import PurchaseApproval, PurchaseRecommendation

from .conftest import APPROVER, REQUESTER, build_platform, make_request

_SERVICE_TYPES = {
    "decision_case_service": DecisionCaseService,
    "case_decision_service": CaseDecisionService,
    "action_request_service": ActionRequestService,
    "action_authorization_service": ActionAuthorizationService,
    "execution_service": ExecutionService,
    "reconciliation_service": ReconciliationService,
}
_REPO_TYPES = {
    "decision_case_repo": InMemoryDecisionCaseRepository,
    "action_request_repo": InMemoryActionRequestRepository,
    "execution_repo": InMemoryExecutionRepository,
}


def _run_lifecycle(platform) -> LifecycleOutcome:
    api = ProcurementAPI(platform)
    request = make_request()
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
    platform.reconciliation_service.query_external_status(
        intent_id=intent.execution_intent_id, actor=APPROVER)
    recon = platform.reconciliation_service.reconcile_execution(
        intent_id=intent.execution_intent_id, actor=APPROVER)
    return LifecycleOutcome(
        audit_events=tuple(platform.audit_service._repo.all()),
        reconciliation_status=recon.status.value,
        records=(decision, req, recon),
        audit_repository=platform.audit_service._repo)


def procurement_fixture() -> SimpleFixture:
    return SimpleFixture(
        name="procurement", _build=build_platform, _run=_run_lifecycle,
        _service_types=_SERVICE_TYPES, _repo_types=_REPO_TYPES)


def test_procurement_passes_kernel_conformance():
    report = run_domain_conformance(procurement_fixture())
    assert report.passed, report.failures
    # A meaningful battery actually ran.
    assert len(report.results) >= 15
