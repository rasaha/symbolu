"""Procurement domain: request, assessment, recommendation, decision, mappings."""

from __future__ import annotations

import pytest

from decision_governance.actions.control_plane import ActionControlPlanePort
from decision_governance.decisions import DecisionOutcome, ProposedOutcome
from decision_governance.execution.external_system import ExternalExecutionPort
from decision_governance.ports.linked_record import LinkedRecordPort

from domains.procurement.actions import all_mappings
from domains.procurement.approvals import (
    PurchaseApproval,
    PurchaseRecommendation,
    decision_outcome_for,
    proposed_outcome_for,
)
from domains.procurement.errors import PurchaseRequestValidationError
from domains.procurement.policies import AssessmentStatus, BudgetAuthorityAdapter
from domains.procurement.suppliers import SupplierExecutionAdapter
from domains.procurement.requests import PurchaseItem, PurchaseRequest, SupplierReference
from domains.procurement.requests import BudgetReference

from .conftest import make_request


def test_purchase_request_total_amount():
    req = make_request(unit_cost=100_000, quantity=3)
    assert req.total_amount == 300_000


def test_purchase_request_rejects_empty_items():
    from decision_governance.errors import DomainValidationError
    with pytest.raises(DomainValidationError):
        PurchaseRequest(
            request_id="pr", tenant_id="t1", requester="r",
            supplier=SupplierReference(supplier_id="s"),
            items=(), budget=BudgetReference(budget_id="b"))


def test_deterministic_assessment_finalizes_valid_request(platform, request_factory):
    assessment = platform.assessment_service.assess(request_factory())
    assert assessment.status is AssessmentStatus.FINALIZED
    assert not assessment.blocked
    assert not assessment.failed_checks


def test_assessment_flags_budget_insufficiency(platform):
    req = make_request(unit_cost=1_000_000, quantity=10, available=1)
    assessment = platform.assessment_service.assess(req)
    failed = {c.check_id for c in assessment.failed_checks}
    assert "budget_sufficient" in failed
    # budget_sufficient is non-blocking; structural checks passed → not blocked.
    assert not assessment.blocked


def test_request_validator_rejects_zero_total(platform):
    req = make_request(unit_cost=0, quantity=1)
    with pytest.raises(PurchaseRequestValidationError):
        platform.request_validator.validate(req)


def test_recommendation_maps_to_kernel_proposed_outcome(api, request_factory):
    case, _ = api.submit_and_assess(request_factory(), actor="requester-1")
    rec = api.recommend(case_id=case.decision_case_id,
                        recommendation=PurchaseRecommendation.APPROVE,
                        generated_by="requester-1")
    assert rec.proposed_outcome is ProposedOutcome.ADVANCE
    assert rec.__class__.__module__.startswith(("ugence_decision_authority.", "decision_governance."))


def test_decision_maps_to_kernel_decision_outcome(api, request_factory):
    case, _ = api.submit_and_assess(request_factory(), actor="requester-1")
    api.recommend(case_id=case.decision_case_id,
                  recommendation=PurchaseRecommendation.APPROVE, generated_by="requester-1")
    decision = api.decide(case_id=case.decision_case_id,
                          approval=PurchaseApproval.APPROVED, approver="approver-1")
    assert decision.outcome is DecisionOutcome.ADVANCE
    assert decision.__class__.__module__.startswith(("ugence_decision_authority.", "decision_governance."))


def test_outcome_mapping_tables():
    assert proposed_outcome_for(PurchaseRecommendation.REJECT) is ProposedOutcome.REJECT
    assert decision_outcome_for(PurchaseApproval.REJECTED) is DecisionOutcome.REJECT
    assert decision_outcome_for(PurchaseApproval.APPROVED_WITH_CONDITIONS) is DecisionOutcome.ADVANCE


def test_action_mappings_are_kernel_action_mappings():
    mappings = all_mappings()
    assert {m.permitted_action_type for m in mappings} == {
        "CREATE_PURCHASE_ORDER", "CANCEL_REQUEST",
        "ROUTE_TO_SENIOR_APPROVER", "REQUEST_MORE_INFORMATION"}
    for m in mappings:
        assert m.__class__.__module__.startswith(("ugence_decision_authority.", "decision_governance."))


def test_adapters_conform_to_kernel_ports():
    assert isinstance(BudgetAuthorityAdapter(), ActionControlPlanePort)
    assert isinstance(SupplierExecutionAdapter(), ExternalExecutionPort)
    assert isinstance(
        platform_linked_adapter := _linked_adapter(), LinkedRecordPort)


def _linked_adapter():
    from domains.procurement.adapters import ProcurementAssessmentLinkedRecordAdapter
    from domains.procurement.policies import InMemoryProcurementAssessmentRepository
    return ProcurementAssessmentLinkedRecordAdapter(InMemoryProcurementAssessmentRepository())
