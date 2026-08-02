"""Action-request repository (port + in-memory adapter).

Append-only and versioned. Action-request snapshots, CERs, and authorization
responses are never overwritten or deleted; corrections append new snapshots and
attempts. Idempotency-key lookup returns the active request for a key. Authorization
attempts and responses are stored separately from the request version chain.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..actions.action_mapping import ActionMapping
from ..actions.action_request import ActionRequest
from ..actions.authorization import ActionAuthorizationResponse
from ..actions.cer import ContextEnvelopeRecord
from ..actions.status import (
    ActionMappingStatus,
    TERMINAL_REQUEST_STATUSES,
)
from ..errors import (
    ActionMappingNotFoundError,
    ActionRequestNotFoundError,
    VersionConflictError,
)


@runtime_checkable
class ActionRequestRepository(Protocol):
    # requests (append-only version chain)
    def create_action_request(self, req: ActionRequest) -> ActionRequest: ...
    def save_action_request_snapshot(self, req: ActionRequest) -> ActionRequest: ...
    def get_action_request(self, request_id: str) -> ActionRequest: ...
    def get_action_request_history(self, request_id: str) -> tuple[ActionRequest, ...]: ...
    def list_action_requests(self, tenant_id: str) -> tuple[ActionRequest, ...]: ...
    def find_active_by_idempotency_key(
        self, tenant_id: str, key: str) -> Optional[ActionRequest]: ...
    # mappings (published versions)
    def save_action_mapping(self, mapping: ActionMapping) -> ActionMapping: ...
    def get_action_mapping(self, mapping_id: str, version: int) -> ActionMapping: ...
    def get_published_mapping(self, mapping_id: str) -> Optional[ActionMapping]: ...
    # CERs (immutable)
    def save_cer(self, cer: ContextEnvelopeRecord) -> ContextEnvelopeRecord: ...
    def get_cer(self, cer_id: str) -> ContextEnvelopeRecord: ...
    # authorization attempts + responses (append-only, separate stores)
    def record_authorization_attempt(self, request_id: str, attempt: int) -> None: ...
    def record_authorization_response(
        self, response: ActionAuthorizationResponse) -> ActionAuthorizationResponse: ...
    def get_authorization_history(
        self, request_id: str) -> tuple[ActionAuthorizationResponse, ...]: ...


class InMemoryActionRequestRepository:
    def __init__(self) -> None:
        self._requests: dict[str, list[ActionRequest]] = {}
        self._idempotency: dict[tuple[str, str], str] = {}  # (tenant, key) -> request_id
        self._mappings: dict[tuple[str, int], ActionMapping] = {}
        self._mapping_versions: dict[str, list[ActionMapping]] = {}
        self._cers: dict[str, ContextEnvelopeRecord] = {}
        self._attempts: dict[str, list[int]] = {}
        self._responses: dict[str, list[ActionAuthorizationResponse]] = {}

    # --- requests ---------------------------------------------------------
    def create_action_request(self, req: ActionRequest) -> ActionRequest:
        if req.action_request_id in self._requests:
            raise VersionConflictError(
                f"action request '{req.action_request_id}' already exists")
        self._requests[req.action_request_id] = [req]
        if req.idempotency_key:
            self._idempotency[(req.tenant_id, req.idempotency_key)] = req.action_request_id
        return req

    def save_action_request_snapshot(self, req: ActionRequest) -> ActionRequest:
        chain = self._requests.get(req.action_request_id)
        if chain is None:
            raise ActionRequestNotFoundError(
                f"action request '{req.action_request_id}' not found")
        chain.append(req)
        return req

    def get_action_request(self, request_id: str) -> ActionRequest:
        chain = self._requests.get(request_id)
        if not chain:
            raise ActionRequestNotFoundError(f"action request '{request_id}' not found")
        return max(chain, key=lambda r: r.version)

    def get_action_request_history(self, request_id: str) -> tuple[ActionRequest, ...]:
        chain = self._requests.get(request_id)
        if not chain:
            raise ActionRequestNotFoundError(f"action request '{request_id}' not found")
        return tuple(sorted(chain, key=lambda r: r.version))

    def list_action_requests(self, tenant_id: str) -> tuple[ActionRequest, ...]:
        latest = [self.get_action_request(rid) for rid in self._requests]
        return tuple(sorted(
            (r for r in latest if r.tenant_id == tenant_id),
            key=lambda r: r.action_request_id))

    def find_active_by_idempotency_key(
        self, tenant_id: str, key: str) -> Optional[ActionRequest]:
        request_id = self._idempotency.get((tenant_id, key))
        if request_id is None:
            return None
        req = self.get_action_request(request_id)
        if req.status in TERMINAL_REQUEST_STATUSES:
            return None
        return req

    # --- mappings ---------------------------------------------------------
    def save_action_mapping(self, mapping: ActionMapping) -> ActionMapping:
        pinned = (mapping.mapping_id, mapping.version)
        if pinned in self._mappings:
            raise VersionConflictError(
                f"action mapping '{mapping.mapping_id}' v{mapping.version} already exists")
        self._mappings[pinned] = mapping
        self._mapping_versions.setdefault(mapping.mapping_id, []).append(mapping)
        return mapping

    def get_action_mapping(self, mapping_id: str, version: int) -> ActionMapping:
        mapping = self._mappings.get((mapping_id, version))
        if mapping is None:
            raise ActionMappingNotFoundError(
                f"action mapping '{mapping_id}' v{version} not found")
        return mapping

    def get_published_mapping(self, mapping_id: str) -> Optional[ActionMapping]:
        versions = self._mapping_versions.get(mapping_id)
        if not versions:
            return None
        published = [m for m in versions if m.status is ActionMappingStatus.PUBLISHED]
        if not published:
            return None
        return max(published, key=lambda m: m.version)

    # --- CERs -------------------------------------------------------------
    def save_cer(self, cer: ContextEnvelopeRecord) -> ContextEnvelopeRecord:
        if cer.cer_id in self._cers:
            raise VersionConflictError(f"CER '{cer.cer_id}' already exists; CERs are immutable")
        self._cers[cer.cer_id] = cer
        return cer

    def get_cer(self, cer_id: str) -> ContextEnvelopeRecord:
        cer = self._cers.get(cer_id)
        if cer is None:
            raise ActionRequestNotFoundError(f"CER '{cer_id}' not found")
        return cer

    # --- authorization ----------------------------------------------------
    def record_authorization_attempt(self, request_id: str, attempt: int) -> None:
        self._attempts.setdefault(request_id, []).append(attempt)

    def record_authorization_response(
        self, response: ActionAuthorizationResponse) -> ActionAuthorizationResponse:
        self._responses.setdefault(response.action_request_id, []).append(response)
        return response

    def get_authorization_history(
        self, request_id: str) -> tuple[ActionAuthorizationResponse, ...]:
        return tuple(self._responses.get(request_id, ()))

    def attempt_count(self, request_id: str) -> int:
        return len(self._responses.get(request_id, ()))
