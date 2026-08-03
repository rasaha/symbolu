"""Callable rubric API facade + optional FastAPI adapter.

Framework-agnostic surface over the rubric service and validator with an
authorization hook (authoring/approving/publishing are human governance
actions). No evaluation endpoints — only rubric contracts are managed here.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from ..common import new_id
from ..domain.enums import ActorType
from ..errors import EvidenceAccessDeniedError, UnauthenticatedActorError
from ugence_decision_authority.api.identity import IdentityProvider
from ..rubrics.rubric import Rubric
from ..services.rubric_service import RubricService
from ..services.rubric_validation_service import RubricValidationResult


class CreateRubricRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    rubric: Rubric


class RubricActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    rubric_id: str


class ValidateRubricRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    rubric: Rubric


class RubricAPI:
    def __init__(self, rubric_service: RubricService,
                 identity_provider: IdentityProvider) -> None:
        self._svc = rubric_service
        self._identity = identity_provider

    def _require_human(self, principal_id: str) -> None:
        identity = self._identity.authenticate(principal_id)
        if not identity.authenticated:
            raise UnauthenticatedActorError(f"principal '{principal_id}' not authenticated")
        if identity.actor_type is not ActorType.HUMAN:
            raise EvidenceAccessDeniedError(
                "only a human governance actor may manage rubrics")

    # POST /rubrics
    def create_rubric(self, request: CreateRubricRequest) -> Rubric:
        self._require_human(request.principal_id)
        return self._svc.create(request.rubric, author_id=request.principal_id)

    # POST /rubrics/validate
    def validate_rubric(self, request: ValidateRubricRequest) -> RubricValidationResult:
        self._require_human(request.principal_id)
        return self._svc.validate(request.rubric)

    # POST /rubrics/{id}/submit|approve|publish (via action requests)
    def submit_rubric(self, request: RubricActionRequest) -> Rubric:
        self._require_human(request.principal_id)
        return self._svc.submit(request.rubric_id, author_id=request.principal_id)

    def approve_rubric(self, request: RubricActionRequest) -> Rubric:
        self._require_human(request.principal_id)
        return self._svc.approve(request.rubric_id, approver_id=request.principal_id)

    def publish_rubric(self, request: RubricActionRequest) -> Rubric:
        self._require_human(request.principal_id)
        return self._svc.publish(request.rubric_id, publisher_id=request.principal_id)

    # GET /rubrics/{id}
    def get_rubric(self, rubric_id: str) -> Rubric:
        return self._svc.get_current(rubric_id)

    def get_published_rubric(self, rubric_id: str):
        return self._svc.get_published(rubric_id)

    def get_rubric_history(self, rubric_id: str) -> tuple[Rubric, ...]:
        return self._svc.history(rubric_id)


def build_rubric_router(api: RubricAPI):  # pragma: no cover - optional adapter
    from fastapi import APIRouter, HTTPException

    from ..errors import HiringError

    router = APIRouter(prefix="/ai-hiring/rubrics", tags=["rubrics"])

    def _guard(fn):
        try:
            return fn()
        except HiringError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("")
    def _create(request: CreateRubricRequest):
        return _guard(lambda: api.create_rubric(request))

    @router.post("/validate")
    def _validate(request: ValidateRubricRequest):
        return _guard(lambda: api.validate_rubric(request))

    @router.post("/publish")
    def _publish(request: RubricActionRequest):
        return _guard(lambda: api.publish_rubric(request))

    @router.get("/{rubric_id}")
    def _get(rubric_id: str):
        return _guard(lambda: api.get_rubric(rubric_id))

    return router
