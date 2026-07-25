"""Callable API surface with authorization hooks.

The repository does not depend on a web framework at its core (FastAPI is an
optional extra), so the primary surface here is a framework-agnostic callable
facade, :class:`HiringAPI`. Each method applies an authorization hook at the API
boundary *in addition to* the service/policy enforcement beneath it — the
boundary is defended in depth, never by UI convention.

An optional FastAPI adapter is provided via :func:`build_fastapi_router`, which
imports FastAPI lazily so this module is importable without it installed.
"""

from __future__ import annotations

from typing import Optional

from ..common import new_id
from ..domain.audit import AuditEvent
from ..domain.decision import Decision
from ..domain.enums import ActorType, WorkflowState
from ..domain.evaluation import CandidateEvaluation
from ..domain.recommendation import Recommendation
from ..errors import BoundaryViolationError, UnauthenticatedActorError
from ..policies import decision_boundary as boundary
from ..policies import transition_policy as tp
from ..services import (
    AuditService,
    DecisionService,
    EvaluationService,
    RecommendationService,
    WorkflowService,
)
from .schemas import (
    CreateDecisionRequest,
    CreateEvaluationRequest,
    CreateRecommendationRequest,
    TransitionRequest,
)


class HiringAPI:
    """Framework-agnostic facade wiring the services with authorization hooks."""

    def __init__(
        self,
        *,
        evaluation_service: EvaluationService,
        recommendation_service: RecommendationService,
        decision_service: DecisionService,
        workflow_service: WorkflowService,
        audit_service: AuditService,
        identity_provider: boundary.IdentityProvider,
    ) -> None:
        self._evaluations = evaluation_service
        self._recommendations = recommendation_service
        self._decisions = decision_service
        self._workflow = workflow_service
        self._audit = audit_service
        self._identity = identity_provider

    # --- authorization hooks (placeholders for a real IdP) -----------------
    def _authorize(
        self, principal_id: str, allowed: frozenset[ActorType]
    ) -> boundary.ActorIdentity:
        identity = self._identity.authenticate(principal_id)
        if not identity.authenticated:
            raise UnauthenticatedActorError(f"principal '{principal_id}' is not authenticated")
        if identity.actor_type not in allowed:
            raise BoundaryViolationError(
                f"principal '{principal_id}' ({identity.actor_type.value}) is not "
                f"permitted for this operation"
            )
        return identity

    _AI_OR_SERVICE = frozenset({ActorType.AI, ActorType.SYSTEM})
    _HUMAN_ONLY = frozenset({ActorType.HUMAN})
    _ANY = frozenset({ActorType.AI, ActorType.HUMAN, ActorType.SYSTEM})

    # --- endpoints ---------------------------------------------------------
    def create_evaluation(
        self, request: CreateEvaluationRequest, *, correlation_id: Optional[str] = None
    ) -> CandidateEvaluation:
        """POST /ai-hiring/evaluations — AI/service principals only."""
        identity = self._authorize(request.principal_id, self._AI_OR_SERVICE)
        return self._evaluations.store(
            request.evaluation,
            actor_type=identity.actor_type,
            actor_id=identity.actor_id,
            correlation_id=correlation_id or new_id("corr"),
        )

    def create_recommendation(
        self, request: CreateRecommendationRequest, *, correlation_id: Optional[str] = None
    ) -> Recommendation:
        """POST /ai-hiring/recommendations — AI/service principals only."""
        identity = self._authorize(request.principal_id, self._AI_OR_SERVICE)
        return self._recommendations.create(
            evaluation_id=request.evaluation_id,
            suggested_disposition=request.suggested_disposition,
            supporting_layers=request.supporting_layers,
            caveats=request.caveats,
            actor_id=identity.actor_id,
            correlation_id=correlation_id or new_id("corr"),
        )

    def create_decision(
        self, request: CreateDecisionRequest, *, correlation_id: Optional[str] = None
    ) -> Decision:
        """POST /ai-hiring/decisions — authenticated humans only."""
        # API-boundary hook; the service authenticates again against the IdP.
        self._authorize(request.principal_id, self._HUMAN_ONLY)
        return self._decisions.create(
            recommendation_id=request.recommendation_id,
            human_actor_id=request.principal_id,
            disposition=request.disposition,
            panel=request.panel,
            rationale_job_related=request.rationale_job_related,
            override=request.override,
            approval=request.approval,
            correlation_id=correlation_id,
        )

    def transition_workflow(
        self,
        candidate_id: str,
        request: TransitionRequest,
        *,
        correlation_id: Optional[str] = None,
    ):
        """POST /ai-hiring/workflows/{candidate_id}/transition.

        For non-binding process transitions. Binding review outcomes
        (ADVANCE/HOLD/REJECT) must go through the decisions endpoint, which
        supplies the required human decision.
        """
        if tp.requires_human_decision(request.target):
            raise BoundaryViolationError(
                f"transition to {request.target.value} is binding; use the "
                "decisions endpoint so a human decision backs it"
            )
        allowed = (
            self._HUMAN_ONLY
            if request.target in tp.AUTHORIZED_HUMAN_STATES
            and request.actor_type is not ActorType.SYSTEM
            else self._ANY
        )
        identity = self._authorize(request.principal_id, allowed)
        return self._workflow.transition(
            candidate_id,
            request.target,
            actor_type=identity.actor_type,
            actor_id=identity.actor_id,
            correlation_id=correlation_id or new_id("corr"),
        )

    def get_evaluation(
        self, evaluation_id: str, *, principal_id: str
    ) -> CandidateEvaluation:
        """GET /ai-hiring/evaluations/{evaluation_id} — any authenticated principal."""
        self._authorize(principal_id, self._ANY)
        return self._evaluations.get(evaluation_id)

    def get_candidate_audit(
        self, candidate_id: str, *, principal_id: str
    ) -> tuple[AuditEvent, ...]:
        """GET /ai-hiring/candidates/{candidate_id}/audit — ordered audit history."""
        self._authorize(principal_id, self._ANY)
        return self._audit.history(candidate_id)


def build_fastapi_router(api: HiringAPI):  # pragma: no cover - optional adapter
    """Build a FastAPI ``APIRouter`` over a :class:`HiringAPI`.

    FastAPI is an optional dependency; it is imported lazily so this module
    stays importable without it. Not exercised by the Phase-1 test suite.
    """
    from fastapi import APIRouter, HTTPException  # type: ignore

    from ..errors import HiringError

    router = APIRouter(prefix="/ai-hiring", tags=["ai-hiring"])

    def _guard(fn):
        try:
            return fn()
        except HiringError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/evaluations")
    def _create_evaluation(request: CreateEvaluationRequest):
        return _guard(lambda: api.create_evaluation(request))

    @router.post("/recommendations")
    def _create_recommendation(request: CreateRecommendationRequest):
        return _guard(lambda: api.create_recommendation(request))

    @router.post("/decisions")
    def _create_decision(request: CreateDecisionRequest):
        return _guard(lambda: api.create_decision(request))

    @router.post("/workflows/{candidate_id}/transition")
    def _transition(candidate_id: str, request: TransitionRequest):
        return _guard(lambda: api.transition_workflow(candidate_id, request))

    @router.get("/evaluations/{evaluation_id}")
    def _get_evaluation(evaluation_id: str, principal_id: str):
        return _guard(lambda: api.get_evaluation(evaluation_id, principal_id=principal_id))

    @router.get("/candidates/{candidate_id}/audit")
    def _get_audit(candidate_id: str, principal_id: str):
        return _guard(lambda: api.get_candidate_audit(candidate_id, principal_id=principal_id))

    return router
