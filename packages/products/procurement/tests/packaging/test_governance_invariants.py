"""Governance / authority-boundary invariants enforced by the product.

These encode the hard boundaries from PRODUCT_BOUNDARY.md / AUTHORITY_MODEL.md:
recommendation is not decision, decision is not authorization, authorization is not
execution, constraints narrow but never broaden, failure fails closed, and a supplier
acknowledgement is not business completion.
"""

from __future__ import annotations

import pytest

from ugence_procurement import ProcurementConfiguration
from ugence_procurement.routes import ProcurementAPI
from ugence_procurement.actions.mappings import CREATE_PURCHASE_ORDER
from ugence_procurement.approvals.mappings import PurchaseApproval, PurchaseRecommendation
from ugence_procurement.suppliers.outcomes import SupplierOutcome, business_outcome_for
from ugence_decision_authority.api.contracts import (
    AuthorityContext,
    AuthorityType,
    BusinessOutcome,
    TransportStatus,
)

from ..conftest import APPROVER, REQUESTER, AI_ACTOR, build_platform, make_request


# --- recommendation is not decision ------------------------------------------

def test_recommendation_does_not_create_a_binding_decision():
    platform = build_platform()
    api = ProcurementAPI(platform)
    case, _ = api.submit_and_assess(make_request(), actor=REQUESTER)
    api.recommend(case_id=case.decision_case_id,
                  recommendation=PurchaseRecommendation.APPROVE, generated_by=REQUESTER)
    # No binding decision record exists on the case yet — a recommendation is advisory.
    assert platform.decision_case_repo.list_decisions(case.decision_case_id) == ()


def test_only_a_human_authority_may_approve():
    """An AI actor / non-human authority cannot produce a binding approval."""
    platform = build_platform()
    api = ProcurementAPI(platform)
    case, _ = api.submit_and_assess(make_request(), actor=REQUESTER)
    api.recommend(case_id=case.decision_case_id,
                  recommendation=PurchaseRecommendation.APPROVE, generated_by=REQUESTER)
    with pytest.raises(Exception):
        # Attempt an AI-authored decision through the raw kernel service with a
        # non-human authority context — must be rejected by the kernel.
        authority = AuthorityContext(
            authority_id=AI_ACTOR, authority_type=AuthorityType.AI_ASSISTANT,
            decision_scope="purchase_approval")
        platform.case_decision_service.record_decision(
            case_id=case.decision_case_id, outcome=__import__(
                "ugence_decision_authority.api.contracts", fromlist=["DecisionOutcome"]
            ).DecisionOutcome.ADVANCE,
            authority=authority, decided_by=AI_ACTOR, reason_codes=())


# --- decision is not authorization / authorization is not execution ----------

def test_decision_does_not_auto_dispatch():
    platform = build_platform()
    api = ProcurementAPI(platform)
    case, _ = api.submit_and_assess(make_request(), actor=REQUESTER)
    api.recommend(case_id=case.decision_case_id,
                  recommendation=PurchaseRecommendation.APPROVE, generated_by=REQUESTER)
    api.decide(case_id=case.decision_case_id,
               approval=PurchaseApproval.APPROVED, approver=APPROVER)
    # Deciding created no execution and dispatched nothing to the supplier.
    assert not platform.execution_repo.all() if hasattr(platform.execution_repo, "all") \
        else not list(getattr(platform.execution_repo, "_data", {}).values())
    assert not platform.supplier_adapter._dispatched


def test_authorization_does_not_auto_dispatch():
    platform = build_platform()
    api = ProcurementAPI(platform)
    request = make_request()
    case, _ = api.submit_and_assess(request, actor=REQUESTER)
    api.recommend(case_id=case.decision_case_id,
                  recommendation=PurchaseRecommendation.APPROVE, generated_by=REQUESTER)
    decision = api.decide(case_id=case.decision_case_id,
                          approval=PurchaseApproval.APPROVED, approver=APPROVER)
    req = api.request_action(decision=decision, request=request, actor=APPROVER)
    auth = api.authorize(action_request_id=req.action_request_id, actor=APPROVER)
    assert auth.outcome.value == "AUTHORIZED"
    # Authorization must not have dispatched anything to the supplier.
    assert not platform.supplier_adapter._dispatched


# --- constraints narrow but never broaden ------------------------------------

def test_above_threshold_authorization_carries_constraints():
    platform = build_platform()
    api = ProcurementAPI(platform)
    request = make_request(request_id="pr-big", unit_cost=2_000_000, quantity=1)
    case, _ = api.submit_and_assess(request, actor=REQUESTER)
    api.recommend(case_id=case.decision_case_id,
                  recommendation=PurchaseRecommendation.APPROVE, generated_by=REQUESTER)
    decision = api.decide(case_id=case.decision_case_id,
                          approval=PurchaseApproval.APPROVED, approver=APPROVER)
    req = api.request_action(decision=decision, request=request, actor=APPROVER)
    auth = api.authorize(action_request_id=req.action_request_id, actor=APPROVER)
    assert auth.outcome.value == "AUTHORIZED_WITH_CONSTRAINTS"
    assert auth.constraints, "senior-approval constraint must be preserved, not dropped"


# --- failure fails closed -----------------------------------------------------

def _authorize(api, request):
    case, _ = api.submit_and_assess(request, actor=REQUESTER)
    api.recommend(case_id=case.decision_case_id,
                  recommendation=PurchaseRecommendation.APPROVE, generated_by=REQUESTER)
    decision = api.decide(case_id=case.decision_case_id,
                          approval=PurchaseApproval.APPROVED, approver=APPROVER)
    req = api.request_action(decision=decision, request=request, actor=APPROVER)
    return api.authorize(action_request_id=req.action_request_id, actor=APPROVER)


def test_restricted_supplier_fails_closed_denied():
    platform = build_platform(
        ProcurementConfiguration(restricted_suppliers=frozenset({"sup-restricted"})))
    api = ProcurementAPI(platform)
    auth = _authorize(api, make_request(supplier_id="sup-restricted"))
    assert auth.outcome.value == "DENIED"
    assert not platform.supplier_adapter._dispatched


def test_above_hard_limit_fails_closed_denied():
    platform = build_platform(ProcurementConfiguration(hard_limit=1_000_000))
    api = ProcurementAPI(platform)
    auth = _authorize(api, make_request(request_id="pr-hard", unit_cost=5_000_000, quantity=1))
    assert auth.outcome.value == "DENIED"


def test_unknown_supplier_reference_fails_closed():
    from ugence_procurement.validation.request_validation import ProcurementRequestValidator
    from ugence_procurement.errors import SupplierNotKnownError, BudgetNotKnownError

    v = ProcurementRequestValidator(known_suppliers=frozenset({"sup-1"}),
                                    known_budgets=frozenset({"bud-1"}))
    with pytest.raises(SupplierNotKnownError):
        v.validate(make_request(supplier_id="ghost"))
    with pytest.raises(BudgetNotKnownError):
        v.validate(make_request(budget_id="ghost"))


# --- supplier acknowledgement is not business completion ----------------------

def test_supplier_ack_is_not_a_business_outcome():
    from ugence_procurement.suppliers.adapter import SupplierExecutionAdapter

    adapter = SupplierExecutionAdapter()

    class _Intent:
        action_type = CREATE_PURCHASE_ORDER
        authorized_parameters = {"amount": "1"}

    resp = adapter.dispatch(_Intent())
    # A transport acknowledgement carries NO business outcome.
    assert resp.transport_status is TransportStatus.ACKNOWLEDGED
    assert not hasattr(resp, "business_outcome") or getattr(resp, "business_outcome", None) is None


def test_unknown_and_timeout_outcomes_are_not_success():
    assert business_outcome_for(SupplierOutcome.UNKNOWN) is BusinessOutcome.UNKNOWN
    assert business_outcome_for(SupplierOutcome.TIMED_OUT) is BusinessOutcome.UNKNOWN
    assert business_outcome_for(SupplierOutcome.REJECTED) is BusinessOutcome.REJECTED
    assert business_outcome_for(SupplierOutcome.ACCEPTED) is BusinessOutcome.SUCCEEDED


def test_supplier_rejection_requires_compensation_not_success():
    platform = build_platform()
    platform.supplier_adapter._outcomes = {CREATE_PURCHASE_ORDER: SupplierOutcome.REJECTED}
    api = ProcurementAPI(platform)
    result = api.run(request=make_request(), requester=REQUESTER, approver=APPROVER)
    assert result.reconciliation_status == "COMPENSATION_REQUIRED"
    assert result.compensation_required is True
