"""Callable ActionRequest API facade + optional FastAPI adapter.

A framework-agnostic surface over the Phase-4B services. Every operation is
authorized and audited inside the services; this facade only shapes typed
requests. The surface deliberately exposes **no** downstream-execution endpoint —
no ``execute_action``, ``apply_action``, ``send_offer``, ``update_ats``,
``create_purchase_order``, ``invoke_actiongate_directly``, or
``record_execution_success``. Phase 4B prepares and authorizes; it never executes.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from ..action_requests.action_mapping import ActionMapping
from ..action_requests.action_request import ActionRequest
from ..action_requests.authorization import ActionAuthorizationResponse
from ..action_requests.cer import ContextEnvelopeRecord
from ..action_requests.validation import ActionRequestValidationResult
from ..policies.decision_boundary import IdentityProvider
from ..services.action_authorization_service import ActionAuthorizationService
from ..services.action_request_service import ActionRequestService
from ..services.cer_binding_service import CERBindingService


class PublishMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    tenant_id: str
    mapping: ActionMapping


class CreateActionRequestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    decision_id: str
    mapping_id: str
    target_system: str
    requested_parameters: dict[str, str] = {}
    idempotency_key: str = ""


class ActionRequestActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    request_id: str


class BindCERRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    request_id: str
    data_classifications: tuple[str, ...] = ()
    runtime_constraints: tuple[str, ...] = ()


class SupersedeActionRequestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    request_id: str
    target_system: str
    requested_parameters: Optional[dict[str, str]] = None


class ActionRequestAPI:
    """Thin typed facade over the Phase-4B services. No execution surface."""

    def __init__(
        self,
        action_request_service: ActionRequestService,
        cer_binding_service: CERBindingService,
        authorization_service: ActionAuthorizationService,
        identity_provider: IdentityProvider,
    ) -> None:
        self._requests = action_request_service
        self._cer = cer_binding_service
        self._authz = authorization_service
        self._identity = identity_provider

    # mappings
    def publish_action_mapping(self, request: PublishMappingRequest) -> ActionMapping:
        return self._requests.publish_action_mapping(
            request.mapping, actor=request.principal_id, tenant_id=request.tenant_id)

    def get_action_mapping(self, mapping_id: str, version: int) -> ActionMapping:
        return self._requests.get_action_mapping(mapping_id, version)

    # requests
    def create_action_request(self, request: CreateActionRequestRequest) -> ActionRequest:
        return self._requests.create_action_request(
            decision_id=request.decision_id, mapping_id=request.mapping_id,
            target_system=request.target_system, created_by=request.principal_id,
            requested_parameters=request.requested_parameters,
            idempotency_key=request.idempotency_key)

    def get_action_request(self, request_id: str) -> ActionRequest:
        return self._requests.get_action_request(request_id)

    def get_action_request_history(self, request_id: str) -> tuple[ActionRequest, ...]:
        return self._requests.get_action_request_history(request_id)

    def validate_action_request(self, request: ActionRequestActionRequest
                                ) -> ActionRequestValidationResult:
        return self._requests.validate_action_request(
            request_id=request.request_id, actor=request.principal_id)

    def cancel_action_request(self, request: ActionRequestActionRequest) -> ActionRequest:
        return self._requests.cancel_action_request(
            request_id=request.request_id, actor=request.principal_id)

    def supersede_action_request(self, request: SupersedeActionRequestRequest
                                 ) -> ActionRequest:
        return self._requests.supersede_action_request(
            request_id=request.request_id, target_system=request.target_system,
            actor=request.principal_id,
            requested_parameters=request.requested_parameters)

    # CER
    def bind_cer(self, request: BindCERRequest) -> ContextEnvelopeRecord:
        return self._cer.bind_cer(
            request_id=request.request_id, actor=request.principal_id,
            data_classifications=request.data_classifications,
            runtime_constraints=request.runtime_constraints)

    def get_cer(self, cer_id: str) -> ContextEnvelopeRecord:
        return self._cer.get_cer(cer_id)

    # authorization
    def submit_for_authorization(self, request: ActionRequestActionRequest
                                 ) -> ActionAuthorizationResponse:
        return self._authz.submit_for_authorization(
            request_id=request.request_id, actor=request.principal_id)

    def get_authorization_history(self, request_id: str
                                  ) -> tuple[ActionAuthorizationResponse, ...]:
        return self._authz.get_authorization_history(request_id)


def build_action_request_router(api: ActionRequestAPI):  # pragma: no cover - optional
    from fastapi import APIRouter, HTTPException

    from ..errors import HiringError

    router = APIRouter(prefix="/ai-hiring/action-requests", tags=["action-requests"])

    def _guard(fn):
        try:
            return fn()
        except HiringError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/mappings")
    def _publish_mapping(request: PublishMappingRequest):
        return _guard(lambda: api.publish_action_mapping(request))

    @router.get("/mappings/{mapping_id}/{version}")
    def _get_mapping(mapping_id: str, version: int):
        return _guard(lambda: api.get_action_mapping(mapping_id, version))

    @router.post("")
    def _create(request: CreateActionRequestRequest):
        return _guard(lambda: api.create_action_request(request))

    @router.get("/{request_id}")
    def _get(request_id: str):
        return _guard(lambda: api.get_action_request(request_id))

    @router.get("/{request_id}/history")
    def _history(request_id: str):
        return _guard(lambda: api.get_action_request_history(request_id))

    @router.post("/validate")
    def _validate(request: ActionRequestActionRequest):
        return _guard(lambda: api.validate_action_request(request))

    @router.post("/bind-cer")
    def _bind(request: BindCERRequest):
        return _guard(lambda: api.bind_cer(request))

    @router.get("/cer/{cer_id}")
    def _get_cer(cer_id: str):
        return _guard(lambda: api.get_cer(cer_id))

    @router.post("/submit")
    def _submit(request: ActionRequestActionRequest):
        return _guard(lambda: api.submit_for_authorization(request))

    @router.get("/{request_id}/authorizations")
    def _authz_history(request_id: str):
        return _guard(lambda: api.get_authorization_history(request_id))

    @router.post("/cancel")
    def _cancel(request: ActionRequestActionRequest):
        return _guard(lambda: api.cancel_action_request(request))

    @router.post("/supersede")
    def _supersede(request: SupersedeActionRequestRequest):
        return _guard(lambda: api.supersede_action_request(request))

    return router
