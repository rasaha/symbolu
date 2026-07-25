"""Callable DecisionCase API facade + optional FastAPI adapter.

A framework-agnostic surface over the three case services. Every operation is
authorized and audited inside the services; this facade only shapes typed
requests. The surface deliberately exposes **no** execution endpoint — no
``execute_decision``, ``send_to_actiongate``, ``construct_cer``, ``rank_candidates``,
``auto_hire``, or ``auto_reject``. Phase 4A stops at recording a decision.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from ..decision_cases.authority import AuthorityContext
from ..decision_cases.case import DecisionCase
from ..decision_cases.decision import DecisionRecord
from ..decision_cases.recommendation import RecommendationRecord
from ..decision_cases.review import ReviewTask
from ..decision_cases.status import (
    DecisionOutcome,
    GeneratorType,
    OperatingMode,
    ProposedOutcome,
    ReviewTaskType,
)
from ..decision_cases.subject import VersionedRef
from ..decision_cases.validation import DecisionReadinessResult
from ..ontology.taxonomy import ReasonCode
from ..policies.decision_boundary import IdentityProvider
from ..rubrics.uncertainty import UncertaintyLevel
from ..services.case_decision_service import CaseDecisionService
from ..services.case_recommendation_service import CaseRecommendationService
from ..services.decision_case_service import DecisionCaseService


class CreateCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    tenant_id: str
    decision_type: str
    subject_ids: tuple[str, ...]
    policy_refs: tuple[VersionedRef, ...] = ()
    operating_mode: OperatingMode = OperatingMode.DELIBERATIVE
    require_recommendation: bool = False


class LinkAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    case_id: str
    assessment_id: str
    version: int


class SubmitRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    case_id: str
    recommendation_type: str
    proposed_outcome: ProposedOutcome
    generator_type: GeneratorType
    assessment_refs: tuple[VersionedRef, ...] = ()
    policy_refs: tuple[VersionedRef, ...] = ()
    reason_codes: tuple[ReasonCode, ...] = ()
    uncertainty: Optional[UncertaintyLevel] = None
    model_provenance: Optional[str] = None


class RejectRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    case_id: str
    recommendation_id: str
    reason_codes: tuple[ReasonCode, ...] = ()


class AssignReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    case_id: str
    task_type: ReviewTaskType
    assigned_to: Optional[str] = None
    required_role: str = ""


class CompleteReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    case_id: str
    task_id: str


class RecordDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    case_id: str
    outcome: DecisionOutcome
    authority: AuthorityContext
    reason_codes: tuple[ReasonCode, ...]
    recommendation_refs: tuple[VersionedRef, ...] = ()
    assessment_refs: tuple[VersionedRef, ...] = ()
    policy_refs: tuple[VersionedRef, ...] = ()
    override_reason_codes: tuple[ReasonCode, ...] = ()
    override_notes: str = ""
    policy_default_outcome: Optional[DecisionOutcome] = None


class CaseActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    case_id: str


class DecisionCaseAPI:
    """Thin typed facade over the Phase-4A case services. No execution surface."""

    def __init__(
        self,
        case_service: DecisionCaseService,
        recommendation_service: CaseRecommendationService,
        decision_service: CaseDecisionService,
        identity_provider: IdentityProvider,
    ) -> None:
        self._cases = case_service
        self._recs = recommendation_service
        self._decisions = decision_service
        self._identity = identity_provider

    # cases
    def create_decision_case(self, request: CreateCaseRequest) -> DecisionCase:
        return self._cases.create_case(
            tenant_id=request.tenant_id, decision_type=request.decision_type,
            subject_ids=request.subject_ids, created_by=request.principal_id,
            policy_refs=request.policy_refs, operating_mode=request.operating_mode,
            require_recommendation=request.require_recommendation)

    def get_decision_case(self, case_id: str) -> DecisionCase:
        return self._cases.get_case(case_id)

    def get_decision_case_history(self, case_id: str) -> tuple[DecisionCase, ...]:
        return self._cases.get_case_history(case_id)

    def link_assessment(self, request: LinkAssessmentRequest) -> DecisionCase:
        return self._cases.link_assessment(
            case_id=request.case_id, assessment_id=request.assessment_id,
            version=request.version, actor=request.principal_id)

    # recommendations
    def submit_recommendation(self, request: SubmitRecommendationRequest) -> RecommendationRecord:
        return self._recs.submit_recommendation(
            case_id=request.case_id, recommendation_type=request.recommendation_type,
            proposed_outcome=request.proposed_outcome, generated_by=request.principal_id,
            generator_type=request.generator_type, assessment_refs=request.assessment_refs,
            policy_refs=request.policy_refs, reason_codes=request.reason_codes,
            uncertainty=request.uncertainty, model_provenance=request.model_provenance)

    def reject_recommendation(self, request: RejectRecommendationRequest) -> RecommendationRecord:
        return self._recs.reject_recommendation(
            case_id=request.case_id, recommendation_id=request.recommendation_id,
            actor=request.principal_id, reason_codes=request.reason_codes)

    # reviews
    def assign_review(self, request: AssignReviewRequest) -> ReviewTask:
        return self._cases.assign_review(
            case_id=request.case_id, task_type=request.task_type,
            assigned_to=request.assigned_to, required_role=request.required_role,
            actor=request.principal_id)

    def complete_review(self, request: CompleteReviewRequest) -> ReviewTask:
        return self._cases.complete_review(
            case_id=request.case_id, task_id=request.task_id, actor=request.principal_id)

    def validate_decision_readiness(self, request: CaseActionRequest) -> DecisionReadinessResult:
        return self._cases.validate_decision_readiness(
            case_id=request.case_id, actor=request.principal_id)

    # decisions
    def record_decision(self, request: RecordDecisionRequest) -> DecisionRecord:
        return self._decisions.record_decision(
            case_id=request.case_id, outcome=request.outcome, authority=request.authority,
            decided_by=request.principal_id, reason_codes=request.reason_codes,
            recommendation_refs=request.recommendation_refs,
            assessment_refs=request.assessment_refs, policy_refs=request.policy_refs,
            override_reason_codes=request.override_reason_codes,
            override_notes=request.override_notes,
            policy_default_outcome=request.policy_default_outcome)

    def get_decision(self, decision_id: str) -> DecisionRecord:
        return self._decisions.get_decision(decision_id)

    # lifecycle
    def supersede_case(self, request: CaseActionRequest) -> DecisionCase:
        return self._cases.supersede_case(case_id=request.case_id, actor=request.principal_id)

    def cancel_case(self, request: CaseActionRequest) -> DecisionCase:
        return self._cases.cancel_case(case_id=request.case_id, actor=request.principal_id)

    def close_case(self, request: CaseActionRequest) -> DecisionCase:
        return self._cases.close_case(case_id=request.case_id, actor=request.principal_id)


def build_decision_case_router(api: DecisionCaseAPI):  # pragma: no cover - optional adapter
    from fastapi import APIRouter, HTTPException

    from ..errors import HiringError

    router = APIRouter(prefix="/ai-hiring/decision-cases", tags=["decision-cases"])

    def _guard(fn):
        try:
            return fn()
        except HiringError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("")
    def _create(request: CreateCaseRequest):
        return _guard(lambda: api.create_decision_case(request))

    @router.get("/{case_id}")
    def _get(case_id: str):
        return _guard(lambda: api.get_decision_case(case_id))

    @router.get("/{case_id}/history")
    def _history(case_id: str):
        return _guard(lambda: api.get_decision_case_history(case_id))

    @router.post("/assessments")
    def _link(request: LinkAssessmentRequest):
        return _guard(lambda: api.link_assessment(request))

    @router.post("/recommendations")
    def _rec(request: SubmitRecommendationRequest):
        return _guard(lambda: api.submit_recommendation(request))

    @router.post("/recommendations/reject")
    def _rec_reject(request: RejectRecommendationRequest):
        return _guard(lambda: api.reject_recommendation(request))

    @router.post("/reviews")
    def _assign(request: AssignReviewRequest):
        return _guard(lambda: api.assign_review(request))

    @router.post("/reviews/complete")
    def _complete(request: CompleteReviewRequest):
        return _guard(lambda: api.complete_review(request))

    @router.post("/readiness")
    def _ready(request: CaseActionRequest):
        return _guard(lambda: api.validate_decision_readiness(request))

    @router.post("/decisions")
    def _decide(request: RecordDecisionRequest):
        return _guard(lambda: api.record_decision(request))

    @router.post("/supersede")
    def _supersede(request: CaseActionRequest):
        return _guard(lambda: api.supersede_case(request))

    @router.post("/cancel")
    def _cancel(request: CaseActionRequest):
        return _guard(lambda: api.cancel_case(request))

    @router.post("/close")
    def _close(request: CaseActionRequest):
        return _guard(lambda: api.close_case(request))

    return router
