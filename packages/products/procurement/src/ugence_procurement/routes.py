"""Callable procurement API facade over the DGM governance lifecycle.

A framework-agnostic surface that walks a purchase request through the full
governance chain on the unchanged kernel: assess → link → recommend → decide →
action request → CER → authorize → dispatch → observe → reconcile (→ compensate).
Every governance operation is authorized and audited inside the kernel services;
this facade only orchestrates domain-shaped calls.

It never executes anything for real — the supplier adapter is offline and
deterministic — and it exposes no endpoint that fabricates an outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ugence_decision_authority.api.contracts import (
    AuthorityContext,
    AuthorityType,
    DecisionOutcome,
    DecisionRecord,
    GeneratorType,
    RecommendationRecord,
)
from ugence_decision_authority.api.vocabulary import ReasonCode

from .actions import (
    CANCEL_REQUEST,
    CREATE_PURCHASE_ORDER,
    PROCUREMENT_DECISION_TYPE,
    REQUEST_MORE_INFORMATION,
    ROUTE_TO_SENIOR_APPROVER,
    SUPPLIER_SYSTEM_TYPE,
)
from .approvals import (
    PurchaseApproval,
    PurchaseRecommendation,
    decision_outcome_for,
    proposed_outcome_for,
)
from .requests import PurchaseRequest

# Which action mapping fires for each decision outcome.
_MAPPING_FOR_OUTCOME = {
    DecisionOutcome.ADVANCE: ("proc.create_po", CREATE_PURCHASE_ORDER),
    DecisionOutcome.REJECT: ("proc.cancel", CANCEL_REQUEST),
    DecisionOutcome.HOLD: ("proc.route_senior", ROUTE_TO_SENIOR_APPROVER),
    DecisionOutcome.DEFER: ("proc.request_info", REQUEST_MORE_INFORMATION),
}


@dataclass
class ProcurementRunResult:
    """The records produced by a full end-to-end procurement run."""

    case_id: str
    assessment_id: str
    recommendation: RecommendationRecord
    decision: DecisionRecord
    action_request_id: str
    authorization_outcome: str
    reconciliation_status: str
    compensation_required: bool


class ProcurementAPI:
    """A callable facade bound to a wired :class:`ProcurementPlatform`."""

    def __init__(self, platform) -> None:
        self._p = platform

    # --- governance-case stages --------------------------------------------

    def submit_and_assess(self, request: PurchaseRequest, *, actor: str):
        """Validate the request, run the deterministic assessment, open a case,
        and link the finalized assessment. Returns ``(case, assessment)``."""
        self._p.request_validator.validate(request)
        assessment = self._p.assessment_service.assess(request)
        case = self._p.decision_case_service.create_case(
            tenant_id=request.tenant_id, decision_type=PROCUREMENT_DECISION_TYPE,
            subject_ids=(request.request_id,), created_by=actor)
        self._p.decision_case_service.link_assessment(
            case_id=case.decision_case_id, assessment_id=assessment.assessment_id,
            version=assessment.version, actor=actor)
        return case, assessment

    def recommend(self, *, case_id: str, recommendation: PurchaseRecommendation,
                  generated_by: str) -> RecommendationRecord:
        return self._p.case_recommendation_service.submit_recommendation(
            case_id=case_id, recommendation_type="policy",
            proposed_outcome=proposed_outcome_for(recommendation),
            generated_by=generated_by, generator_type=GeneratorType.DETERMINISTIC_POLICY,
            reason_codes=(ReasonCode.NOT_APPLICABLE,))

    def decide(self, *, case_id: str, approval: PurchaseApproval,
               approver: str) -> DecisionRecord:
        authority = AuthorityContext(
            authority_id=approver, authority_type=AuthorityType.HUMAN_APPROVER,
            decision_scope=PROCUREMENT_DECISION_TYPE)
        return self._p.case_decision_service.record_decision(
            case_id=case_id, outcome=decision_outcome_for(approval),
            authority=authority, decided_by=approver,
            reason_codes=(ReasonCode.NOT_APPLICABLE,))

    # --- action / authorization / execution stages -------------------------

    def request_action(self, *, decision: DecisionRecord, request: PurchaseRequest,
                       actor: str):
        mapping_id, _action_type = _MAPPING_FOR_OUTCOME[decision.outcome]
        if mapping_id == "proc.create_po":
            params = {
                "amount": str(request.total_amount),
                "supplier_id": request.supplier.supplier_id,
                "budget_id": request.budget.budget_id,
            }
        else:
            params = {"request_id": request.request_id}
        return self._p.action_request_service.create_action_request(
            decision_id=decision.decision_id, mapping_id=mapping_id,
            target_system=SUPPLIER_SYSTEM_TYPE, created_by=actor,
            requested_parameters=params)

    def authorize(self, *, action_request_id: str, actor: str):
        self._p.action_request_service.validate_action_request(
            request_id=action_request_id, actor=actor)
        self._p.cer_binding_service.bind_cer(request_id=action_request_id, actor=actor)
        return self._p.action_authorization_service.submit_for_authorization(
            request_id=action_request_id, actor=actor)

    def dispatch_and_observe(self, *, action_request_id: str, actor: str):
        intent = self._p.execution_service.create_execution_intent(
            action_request_id=action_request_id, created_by=actor)
        self._p.execution_service.dispatch_execution(
            intent_id=intent.execution_intent_id, actor=actor)
        self._p.reconciliation_service.query_external_status(
            intent_id=intent.execution_intent_id, actor=actor)
        return self._p.reconciliation_service.reconcile_execution(
            intent_id=intent.execution_intent_id, actor=actor)

    # --- end to end ---------------------------------------------------------

    def run(self, *, request: PurchaseRequest, requester: str, approver: str,
            recommendation: PurchaseRecommendation = PurchaseRecommendation.APPROVE,
            approval: PurchaseApproval = PurchaseApproval.APPROVED) -> ProcurementRunResult:
        """Walk a request through the entire governance lifecycle."""
        case, assessment = self.submit_and_assess(request, actor=requester)
        rec = self.recommend(case_id=case.decision_case_id,
                             recommendation=recommendation, generated_by=requester)
        decision = self.decide(case_id=case.decision_case_id, approval=approval,
                               approver=approver)
        req = self.request_action(decision=decision, request=request, actor=approver)
        auth = self.authorize(action_request_id=req.action_request_id, actor=approver)
        recon = self.dispatch_and_observe(
            action_request_id=req.action_request_id, actor=approver)
        return ProcurementRunResult(
            case_id=case.decision_case_id, assessment_id=assessment.assessment_id,
            recommendation=rec, decision=decision,
            action_request_id=req.action_request_id,
            authorization_outcome=auth.outcome.value,
            reconciliation_status=recon.status.value,
            compensation_required=recon.status.value == "COMPENSATION_REQUIRED")
