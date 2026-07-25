"""ActionRequestService — turns an effective decision into a governed request.

Creates immutable action requests from effective ``DecisionRecord``s, selects the
exact published action mapping (pinning its version), validates requested
parameters, and manages the lifecycle (validation, cancellation, supersession). It
enforces authorization and emits audit events. It **never executes** an action,
never calls a downstream system, and never mutates the underlying decision.
"""

from __future__ import annotations

from typing import Mapping, Optional

from ..action_requests.action_mapping import ActionMapping, ParameterSchema
from ..action_requests.action_request import ActionRequest
from ..action_requests.lifecycle import is_legal_transition
from ..action_requests.status import (
    ActionMappingStatus,
    ActionRequestStatus,
    AUTHORIZED_STATUSES,
    TERMINAL_REQUEST_STATUSES,
)
from ..common import Clock, IdFactory, new_id, utc_now
from ..decision_cases.status import CaseStatus, EffectiveStatus
from ..decision_cases.subject import VersionedRef
from ..domain.enums import ActorType, AuditEventType
from ..errors import (
    ActionMappingNotFoundError,
    ActionMappingNotPublishedError,
    ActionRequestAlreadyAuthorizedError,
    ActionRequestNotReadyError,
    ActionParameterValidationError,
    ActionTypeMismatchError,
    DecisionNotActionableError,
    DecisionSupersededError,
    DuplicateActionRequestError,
    InvalidActionRequestTransitionError,
    ProhibitedActionParameterError,
    TargetSystemNotPermittedError,
)
from ..policies.decision_boundary import IdentityProvider
from ..policies.evidence_access_policy import EvidenceAccessPolicy, Permission
from ..repositories.action_request_repository import ActionRequestRepository
from ..repositories.decision_case_repository import DecisionCaseRepository
from .action_request_validation_service import ActionRequestValidationService
from .audit_service import AuditService
from ._action_authz import authorize_action

_DEAD_CASE_STATUSES = frozenset({CaseStatus.CANCELLED, CaseStatus.CLOSED})
_CREDENTIAL_MARKERS = ("password", "secret", "token", "credential", "api_key",
                       "apikey", "private_key", "access_key")


class ActionRequestService:
    def __init__(
        self,
        action_request_repository: ActionRequestRepository,
        decision_case_repository: DecisionCaseRepository,
        validation_service: ActionRequestValidationService,
        audit_service: AuditService,
        identity_provider: IdentityProvider,
        access_policy: EvidenceAccessPolicy,
        *,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._repo = action_request_repository
        self._cases = decision_case_repository
        self._validation = validation_service
        self._audit = audit_service
        self._identity = identity_provider
        self._policy = access_policy
        self._new_id = id_factory
        self._clock = clock

    # --- helpers ----------------------------------------------------------
    def _authorize(self, actor: str, permission: Permission, tenant_id: str,
                   correlation_id: str, entity_id: str) -> ActorType:
        return authorize_action(
            self._identity, self._policy, self._audit, actor=actor,
            permission=permission, tenant_id=tenant_id, correlation_id=correlation_id,
            entity_id=entity_id)

    def _emit(self, event_type, entity_id, actor, actor_type, corr, payload):
        self._audit.record(
            event_type=event_type, entity_type="action_request", entity_id=entity_id,
            actor_type=actor_type, actor_id=actor, correlation_id=corr, payload=payload)

    def _resolve_published_mapping(self, mapping_id: str) -> ActionMapping:
        mapping = self._repo.get_published_mapping(mapping_id)
        if mapping is None:
            # Distinguish "no mapping at all" from "exists but not published".
            try:
                self._repo.get_action_mapping(mapping_id, 1)
            except ActionMappingNotFoundError:
                raise ActionMappingNotFoundError(
                    f"no action mapping '{mapping_id}'") from None
            raise ActionMappingNotPublishedError(
                f"action mapping '{mapping_id}' has no PUBLISHED version")
        return mapping

    def _validate_parameters(self, mapping: ActionMapping,
                             params: Mapping[str, str]) -> None:
        keys = tuple(params.keys())
        for key in keys:
            low = key.lower()
            if key in mapping.prohibited_fields or any(m in low for m in _CREDENTIAL_MARKERS):
                raise ProhibitedActionParameterError(
                    f"parameter '{key}' is prohibited for this mapping")
        unknown = mapping.parameter_schema.unknown_fields(keys)
        if unknown:
            raise ActionParameterValidationError(
                f"unknown parameters for action: {sorted(unknown)}")
        missing = mapping.parameter_schema.missing_required(keys)
        if missing:
            raise ActionParameterValidationError(
                f"missing required parameters: {sorted(missing)}")

    # --- mapping management ----------------------------------------------
    def publish_action_mapping(self, mapping: ActionMapping, *, actor: str,
                               tenant_id: str) -> ActionMapping:
        corr = self._new_id("corr")
        actor_type = self._authorize(actor, Permission.MANAGE_ACTION_MAPPING, tenant_id,
                                     corr, mapping.mapping_id)
        published = mapping.model_copy(update={
            "status": ActionMappingStatus.PUBLISHED,
            "content_hash": mapping.compute_hash()})
        self._repo.save_action_mapping(published)
        self._emit(AuditEventType.ACTION_MAPPING_PUBLISHED, mapping.mapping_id, actor,
                   actor_type, corr, {"version": published.version,
                                      "content_hash": published.content_hash})
        return published

    def get_action_mapping(self, mapping_id: str, version: int) -> ActionMapping:
        return self._repo.get_action_mapping(mapping_id, version)

    # --- request creation -------------------------------------------------
    def create_action_request(
        self, *, decision_id: str, mapping_id: str, target_system: str,
        created_by: str, requested_parameters: Optional[Mapping[str, str]] = None,
        idempotency_key: str = "", correlation_id: Optional[str] = None,
    ) -> ActionRequest:
        params = dict(requested_parameters or {})
        decision = self._cases.get_decision(decision_id)
        corr = correlation_id or self._new_id("corr")
        actor_type = self._authorize(created_by, Permission.CREATE_ACTION_REQUEST,
                                     decision.tenant_id, corr, decision.decision_case_id)

        # Decision must be effective and not superseded.
        if decision.effective_status is not EffectiveStatus.EFFECTIVE:
            raise DecisionSupersededError(
                f"decision '{decision_id}' is {decision.effective_status.value}")
        if self._validation.decision_is_superseded(decision.decision_case_id, decision_id):
            raise DecisionSupersededError(
                f"decision '{decision_id}' has been superseded by a later decision")

        case = self._cases.get_case(decision.decision_case_id)
        if case.status in _DEAD_CASE_STATUSES:
            raise DecisionNotActionableError(
                f"case '{case.decision_case_id}' is {case.status.value}")

        # Resolve + pin the published mapping; it must match the decision.
        mapping = self._resolve_published_mapping(mapping_id)
        if mapping.decision_outcome != decision.outcome:
            raise DecisionNotActionableError(
                f"decision outcome {decision.outcome.value} is not action-producing "
                f"under mapping '{mapping_id}'")
        if mapping.decision_type != decision.decision_type:
            raise ActionTypeMismatchError(
                f"mapping decision_type {mapping.decision_type} != "
                f"decision {decision.decision_type}")
        if target_system != mapping.target_system_type:
            raise TargetSystemNotPermittedError(
                f"target '{target_system}' not permitted; mapping allows "
                f"'{mapping.target_system_type}'")
        self._validate_parameters(mapping, params)

        # Idempotency: an active request for the same key must not duplicate.
        if idempotency_key:
            existing = self._repo.find_active_by_idempotency_key(
                decision.tenant_id, idempotency_key)
            if existing is not None:
                candidate_key = self._content_key(
                    decision, mapping, target_system, params)
                if existing.content_key() == candidate_key:
                    return existing  # idempotent no-op
                raise DuplicateActionRequestError(
                    f"idempotency key '{idempotency_key}' already maps to a "
                    "different active request")

        request = ActionRequest(
            action_request_id=self._new_id("areq"), tenant_id=decision.tenant_id,
            decision_case_id=decision.decision_case_id,
            decision_case_version=case.version, decision_id=decision_id,
            action_type=mapping.permitted_action_type, target_system=target_system,
            subject_refs=case.subject_refs, requested_parameters=params,
            policy_refs=decision.policy_refs, authority_ref=decision.decided_by,
            action_mapping_ref=VersionedRef(ref_id=mapping.mapping_id,
                                            version=mapping.version, kind="action_mapping"),
            status=ActionRequestStatus.DRAFT, version=1,
            request_version_id=self._new_id("rv"), created_by=created_by,
            created_at=self._clock(), correlation_id=corr,
            idempotency_key=idempotency_key)
        self._repo.create_action_request(request)
        self._emit(AuditEventType.ACTION_MAPPING_SELECTED, mapping.mapping_id, created_by,
                   actor_type, corr, {"mapping_version": mapping.version,
                                      "content_hash": mapping.content_hash})
        self._emit(AuditEventType.ACTION_REQUEST_CREATED, request.action_request_id,
                   created_by, actor_type, corr,
                   {"decision_id": decision_id, "action_type": request.action_type,
                    "target_system": target_system,
                    "parameters_hash": request.parameters_hash(),
                    "idempotency_key": idempotency_key})
        return request

    def _content_key(self, decision, mapping, target_system, params) -> str:
        from ..common import canonical_hash
        return canonical_hash({
            "decision_id": decision.decision_id,
            "action_type": mapping.permitted_action_type,
            "target_system": target_system,
            "mapping": f"{mapping.mapping_id}:{mapping.version}",
            "parameters": dict(params),
        })

    # --- lifecycle --------------------------------------------------------
    def validate_action_request(self, *, request_id: str, actor: str):
        request = self._repo.get_action_request(request_id)
        actor_type = self._authorize(actor, Permission.VALIDATE_ACTION_REQUEST,
                                     request.tenant_id, request.correlation_id, request_id)
        result = self._validation.validate(request)
        if result.valid and request.status is ActionRequestStatus.DRAFT:
            self._transition(request, ActionRequestStatus.READY_FOR_BINDING)
        self._emit(AuditEventType.ACTION_REQUEST_VALIDATED, request_id, actor, actor_type,
                   request.correlation_id,
                   {"valid": result.valid, "blockers": list(result.blocker_codes)})
        return result

    def cancel_action_request(self, *, request_id: str, actor: str) -> ActionRequest:
        request = self._repo.get_action_request(request_id)
        actor_type = self._authorize(actor, Permission.CANCEL_ACTION_REQUEST,
                                     request.tenant_id, request.correlation_id, request_id)
        if request.status in TERMINAL_REQUEST_STATUSES:
            raise InvalidActionRequestTransitionError(
                f"request is already {request.status.value}")
        evolved = self._transition(request, ActionRequestStatus.CANCELLED)
        self._emit(AuditEventType.ACTION_REQUEST_CANCELLED, request_id, actor, actor_type,
                   request.correlation_id, {})
        return evolved

    def supersede_action_request(self, *, request_id: str, target_system: str,
                                 actor: str,
                                 requested_parameters: Optional[Mapping[str, str]] = None
                                 ) -> ActionRequest:
        """Mark a request superseded and create a fresh request from the same decision."""
        request = self._repo.get_action_request(request_id)
        actor_type = self._authorize(actor, Permission.SUPERSEDE_ACTION_REQUEST,
                                     request.tenant_id, request.correlation_id, request_id)
        if request.status in TERMINAL_REQUEST_STATUSES:
            raise InvalidActionRequestTransitionError(
                f"request is already {request.status.value}")
        self._transition(request, ActionRequestStatus.SUPERSEDED)
        replacement = self.create_action_request(
            decision_id=request.decision_id,
            mapping_id=request.action_mapping_ref.ref_id, target_system=target_system,
            created_by=actor,
            requested_parameters=requested_parameters or dict(request.requested_parameters),
            correlation_id=request.correlation_id)
        self._emit(AuditEventType.ACTION_REQUEST_SUPERSEDED, request_id, actor, actor_type,
                   request.correlation_id,
                   {"superseded_by": replacement.action_request_id})
        return replacement

    def _transition(self, request: ActionRequest,
                    target: ActionRequestStatus, **changes) -> ActionRequest:
        if not is_legal_transition(request.status, target):
            raise InvalidActionRequestTransitionError(
                f"illegal transition {request.status.value} -> {target.value}")
        evolved = request.evolve(request_version_id=self._new_id("rv"),
                                 status=target, **changes)
        return self._repo.save_action_request_snapshot(evolved)

    # --- reads ------------------------------------------------------------
    def get_action_request(self, request_id: str) -> ActionRequest:
        return self._repo.get_action_request(request_id)

    def get_action_request_history(self, request_id: str) -> tuple[ActionRequest, ...]:
        return self._repo.get_action_request_history(request_id)
