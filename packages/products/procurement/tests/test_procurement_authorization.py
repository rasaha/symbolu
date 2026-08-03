"""Procurement authorization: spending limits, approval chain, SoD, authority."""

from __future__ import annotations

import pytest

from ugence_decision_authority.decisions import AuthorityContext, AuthorityType, DecisionOutcome
from ugence_decision_authority.errors import AIDecisionAuthorityError, SegregationOfDutiesError
from ugence_decision_authority.vocabulary import ReasonCode

from ugence_procurement import ProcurementConfiguration
from ugence_procurement.routes import ProcurementAPI
from ugence_procurement.actions import PROCUREMENT_DECISION_TYPE
from ugence_procurement.approvals import PurchaseApproval, PurchaseRecommendation

from .conftest import APPROVER, REQUESTER, TENANT, build_platform, make_request


def _to_decision(api, request):
    case, _ = api.submit_and_assess(request, actor=REQUESTER)
    api.recommend(case_id=case.decision_case_id,
                  recommendation=PurchaseRecommendation.APPROVE, generated_by=REQUESTER)
    return case, api.decide(case_id=case.decision_case_id,
                            approval=PurchaseApproval.APPROVED, approver=APPROVER)


def test_within_limit_is_authorized():
    platform = build_platform(
        ProcurementConfiguration(approval_threshold=1_000_000, hard_limit=10_000_000))
    api = ProcurementAPI(platform)
    _, decision = _to_decision(api, make_request(unit_cost=100_000, quantity=2))  # 200k
    req = api.request_action(decision=decision, request=make_request(unit_cost=100_000, quantity=2),
                             actor=APPROVER)
    resp = api.authorize(action_request_id=req.action_request_id, actor=APPROVER)
    assert resp.outcome.value == "AUTHORIZED"


def test_above_threshold_is_authorized_with_constraints():
    platform = build_platform(
        ProcurementConfiguration(approval_threshold=100_000, hard_limit=10_000_000))
    api = ProcurementAPI(platform)
    request = make_request(unit_cost=100_000, quantity=5)  # 500k > 100k threshold
    _, decision = _to_decision(api, request)
    req = api.request_action(decision=decision, request=request, actor=APPROVER)
    resp = api.authorize(action_request_id=req.action_request_id, actor=APPROVER)
    assert resp.outcome.value == "AUTHORIZED_WITH_CONSTRAINTS"
    assert resp.constraints  # senior-approval constraint attached


def test_above_hard_limit_is_denied_and_not_executable():
    platform = build_platform(
        ProcurementConfiguration(approval_threshold=100, hard_limit=1_000))
    api = ProcurementAPI(platform)
    request = make_request(unit_cost=100_000, quantity=5)  # 500k > hard limit
    _, decision = _to_decision(api, request)
    req = api.request_action(decision=decision, request=request, actor=APPROVER)
    resp = api.authorize(action_request_id=req.action_request_id, actor=APPROVER)
    assert resp.outcome.value == "DENIED"
    # A denied request cannot proceed to execution.
    from ugence_decision_authority.errors import ActionRequestNotExecutableError
    with pytest.raises(ActionRequestNotExecutableError):
        platform.execution_service.create_execution_intent(
            action_request_id=req.action_request_id, created_by=APPROVER)


def test_restricted_supplier_is_denied():
    platform = build_platform(
        ProcurementConfiguration(restricted_suppliers=frozenset({"sup-block"})))
    api = ProcurementAPI(platform)
    request = make_request(supplier_id="sup-block")
    _, decision = _to_decision(api, request)
    req = api.request_action(decision=decision, request=request, actor=APPROVER)
    resp = api.authorize(action_request_id=req.action_request_id, actor=APPROVER)
    assert resp.outcome.value == "DENIED"


def test_ai_actor_may_not_decide():
    platform = build_platform()
    api = ProcurementAPI(platform)
    case, _ = api.submit_and_assess(make_request(), actor=REQUESTER)
    api.recommend(case_id=case.decision_case_id,
                  recommendation=PurchaseRecommendation.APPROVE, generated_by=REQUESTER)
    with pytest.raises(AIDecisionAuthorityError):
        api.decide(case_id=case.decision_case_id, approval=PurchaseApproval.APPROVED,
                   approver="ai-1")


def test_segregation_of_duties_blocks_self_approval():
    platform = build_platform()
    api = ProcurementAPI(platform)
    case, _ = api.submit_and_assess(make_request(), actor=REQUESTER)
    # APPROVER authors the recommendation…
    api.recommend(case_id=case.decision_case_id,
                  recommendation=PurchaseRecommendation.APPROVE, generated_by=APPROVER)
    # …and then tries to be the sole binding authority with SoD required.
    authority = AuthorityContext(
        authority_id=APPROVER, authority_type=AuthorityType.HUMAN_APPROVER,
        decision_scope=PROCUREMENT_DECISION_TYPE, segregation_of_duties=True)
    with pytest.raises(SegregationOfDutiesError):
        platform.case_decision_service.record_decision(
            case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
            authority=authority, decided_by=APPROVER,
            reason_codes=(ReasonCode.NOT_APPLICABLE,))
