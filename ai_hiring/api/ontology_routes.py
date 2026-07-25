"""Callable ontology API facade + optional FastAPI adapter.

Framework-agnostic surface over the ontology service with an authorization hook
(publishing/retiring capabilities is a human governance action). No evaluation
endpoints.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from ..common import new_id
from ..domain.enums import ActorType
from ..errors import EvidenceAccessDeniedError, UnauthenticatedActorError
from ..ontology.capability import Capability, CapabilityStatus
from ..policies.decision_boundary import IdentityProvider
from ..services.ontology_service import OntologyService


class PublishCapabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    capability: Capability


class OntologyAPI:
    """Ontology governance surface with a human-authorization hook."""

    def __init__(self, ontology_service: OntologyService,
                 identity_provider: IdentityProvider) -> None:
        self._svc = ontology_service
        self._identity = identity_provider

    def _require_human(self, principal_id: str) -> None:
        identity = self._identity.authenticate(principal_id)
        if not identity.authenticated:
            raise UnauthenticatedActorError(f"principal '{principal_id}' not authenticated")
        if identity.actor_type is not ActorType.HUMAN:
            raise EvidenceAccessDeniedError(
                "only a human governance actor may modify the ontology")

    # POST /ontology
    def publish_capability(self, request: PublishCapabilityRequest,
                           *, correlation_id: Optional[str] = None) -> Capability:
        self._require_human(request.principal_id)
        return self._svc.publish(request.capability, actor_id=request.principal_id,
                                 correlation_id=correlation_id or new_id("corr"))

    # POST /ontology/{id}/retire
    def retire_capability(self, capability_id: str, *, principal_id: str) -> Capability:
        self._require_human(principal_id)
        return self._svc.retire(capability_id, actor_id=principal_id)

    # GET /ontology
    def list_capabilities(self) -> tuple[Capability, ...]:
        return self._svc.list()

    # GET /ontology/{id}
    def get_capability(self, capability_id: str) -> Capability:
        return self._svc.get(capability_id)

    def get_capability_history(self, capability_id: str) -> tuple[Capability, ...]:
        return self._svc.history(capability_id)


def build_ontology_router(api: OntologyAPI):  # pragma: no cover - optional adapter
    from fastapi import APIRouter, HTTPException

    from ..errors import HiringError

    router = APIRouter(prefix="/ai-hiring/ontology", tags=["ontology"])

    def _guard(fn):
        try:
            return fn()
        except HiringError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("")
    def _publish(request: PublishCapabilityRequest):
        return _guard(lambda: api.publish_capability(request))

    @router.get("")
    def _list():
        return _guard(api.list_capabilities)

    @router.get("/{capability_id}")
    def _get(capability_id: str):
        return _guard(lambda: api.get_capability(capability_id))

    return router
