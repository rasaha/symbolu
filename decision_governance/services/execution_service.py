"""ExecutionService — creates execution intents and dispatches them (transport only).

Turns an authorized ``ActionRequest`` into an immutable ``ExecutionIntent``,
validates readiness and expiry, dispatches through the provider-neutral
``ExternalExecutionPort``, and records every attempt immutably. It **never equates
dispatch with success**, never retries without an explicit classification, and
never mutates the underlying decision, action request, CER, or authorization.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping, Optional

from ..actions.status import AUTHORIZED_STATUSES, AuthorizationOutcome
from ..common import Clock, IdFactory, canonical_hash, new_id, utc_now
from ..identity.actor import ActorType
from ..audit.events import AuditEventType
from ..execution.execution_attempt import ExecutionAttempt
from ..execution.execution_intent import ExecutionIntent
from ..execution.external_system import ExternalExecutionPort
from ..execution.lifecycle import is_legal_transition
from ..execution.status import (
    EXECUTABLE_AUTHORIZATION_OUTCOMES,
    ExecutionStatus,
    RetryClassification,
    TransportStatus,
)
from ..errors import (
    ActionRequestNotExecutableError,
    AuthorizationExpiredError,
    AuthorizationNotExecutableError,
    CERExpiredForExecutionError,
    ExecutionIdempotencyConflictError,
    ExecutionParameterMismatchError,
    ExecutionTargetMismatchError,
    ExternalDispatchError,
    InvalidExecutionTransitionError,
    MalformedExternalResponseError,
    UnsafeRetryError,
)
from ..identity import IdentityProvider
from ..policy import EvidenceAccessPolicy, Permission
from ..repositories.action_request_repository import ActionRequestRepository
from ..repositories.execution_repository import ExecutionRepository
from ..audit import AuditService
from .execution_validation_service import ExecutionValidationService
from ._execution_authz import authorize_execution

_TRANSPORT_TO_STATUS = {
    TransportStatus.DISPATCHED: ExecutionStatus.DISPATCHED,
    TransportStatus.ACKNOWLEDGED: ExecutionStatus.ACKNOWLEDGED,
    TransportStatus.TRANSPORT_FAILED: ExecutionStatus.FAILED,
    TransportStatus.TIMED_OUT: ExecutionStatus.OUTCOME_UNKNOWN,
    TransportStatus.UNKNOWN: ExecutionStatus.OUTCOME_UNKNOWN,
}

_TRANSPORT_EVENT = {
    TransportStatus.ACKNOWLEDGED: AuditEventType.EXECUTION_DISPATCH_ACKNOWLEDGED,
    TransportStatus.DISPATCHED: AuditEventType.EXECUTION_DISPATCH_ACKNOWLEDGED,
    TransportStatus.TRANSPORT_FAILED: AuditEventType.EXECUTION_TRANSPORT_FAILED,
    TransportStatus.TIMED_OUT: AuditEventType.EXECUTION_TIMED_OUT,
    TransportStatus.UNKNOWN: AuditEventType.EXECUTION_TIMED_OUT,
}


class ExecutionService:
    def __init__(
        self,
        execution_repository: ExecutionRepository,
        action_request_repository: ActionRequestRepository,
        validation_service: ExecutionValidationService,
        external_port: ExternalExecutionPort,
        audit_service: AuditService,
        identity_provider: IdentityProvider,
        access_policy: EvidenceAccessPolicy,
        *,
        default_validity: timedelta = timedelta(hours=1),
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._repo = execution_repository
        self._requests = action_request_repository
        self._validation = validation_service
        self._port = external_port
        self._audit = audit_service
        self._identity = identity_provider
        self._policy = access_policy
        self._validity = default_validity
        self._new_id = id_factory
        self._clock = clock

    def _emit(self, event_type, entity_id, actor, actor_type, corr, payload):
        self._audit.record(
            event_type=event_type, entity_type="execution", entity_id=entity_id,
            actor_type=actor_type, actor_id=actor, correlation_id=corr, payload=payload)

    def _latest_executable_authorization(self, request):
        responses = self._requests.get_authorization_history(request.action_request_id)
        for resp in reversed(responses):
            if resp.outcome in EXECUTABLE_AUTHORIZATION_OUTCOMES:
                return resp
        return None

    # --- intent creation --------------------------------------------------
    def create_execution_intent(
        self, *, action_request_id: str, created_by: str,
        execution_parameters: Optional[Mapping[str, str]] = None,
        execution_idempotency_key: str = "",
        correlation_id: Optional[str] = None,
    ) -> ExecutionIntent:
        request = self._requests.get_action_request(action_request_id)
        corr = correlation_id or request.correlation_id or self._new_id("corr")
        actor_type = authorize_execution(
            self._identity, self._policy, self._audit, actor=created_by,
            permission=Permission.CREATE_EXECUTION_INTENT, tenant_id=request.tenant_id,
            correlation_id=corr, entity_id=action_request_id)

        if request.status not in AUTHORIZED_STATUSES:
            raise ActionRequestNotExecutableError(
                f"action request '{action_request_id}' is {request.status.value}, "
                "not authorized")
        authz = self._latest_executable_authorization(request)
        if authz is None:
            raise AuthorizationNotExecutableError(
                "no executable authorization exists for this request")
        now = self._clock()
        if authz.expires_at is not None and authz.expires_at < now:
            raise AuthorizationExpiredError("the authorization has expired")
        if not request.cer_id:
            raise ActionRequestNotExecutableError("request has no bound CER")
        cer = self._requests.get_cer(request.cer_id)
        if cer.is_expired(now):
            raise CERExpiredForExecutionError("the bound CER has expired")

        # Parameters must be a subset of what was authorized — no expansion.
        authorized = dict(request.requested_parameters)
        params = dict(execution_parameters) if execution_parameters is not None else authorized
        for key, value in params.items():
            if key not in authorized:
                raise ExecutionParameterMismatchError(
                    f"parameter '{key}' was not authorized")
            if authorized[key] != value:
                raise ExecutionParameterMismatchError(
                    f"parameter '{key}' value differs from the authorized value")

        # Idempotency (distinct from action-request idempotency).
        if execution_idempotency_key:
            existing = self._repo.lookup_by_execution_idempotency_key(
                request.tenant_id, execution_idempotency_key)
            if existing is not None:
                if existing.action_request_id == action_request_id and \
                        dict(existing.authorized_parameters) == params:
                    return existing
                raise ExecutionIdempotencyConflictError(
                    f"execution idempotency key '{execution_idempotency_key}' "
                    "already maps to a different intent")

        intent = ExecutionIntent(
            execution_intent_id=self._new_id("exi"), tenant_id=request.tenant_id,
            action_request_id=action_request_id, action_request_version=request.version,
            authorization_id=authz.authorization_id, cer_id=request.cer_id,
            action_type=request.action_type, target_system=request.target_system,
            authorized_parameters=params,
            authorization_constraints=authz.constraints,
            authorization_obligations=authz.obligations,
            authority_ref=request.authority_ref,
            policy_refs=tuple(f"{r.ref_id}:{r.version}" for r in request.policy_refs),
            correlation_id=corr, execution_idempotency_key=execution_idempotency_key,
            created_by=created_by, created_at=now,
            expires_at=min(x for x in (authz.expires_at, cer.expires_at,
                                       now + self._validity) if x is not None),
            status=ExecutionStatus.INTENT_CREATED, version=1,
            intent_version_id=self._new_id("iv"))
        intent = intent.model_copy(update={"content_hash": intent.compute_hash()})
        self._repo.create_execution_intent(intent)
        self._emit(AuditEventType.EXECUTION_INTENT_CREATED, intent.execution_intent_id,
                   created_by, actor_type, corr,
                   {"action_request_id": action_request_id,
                    "authorization_id": authz.authorization_id,
                    "constrained": authz.outcome is
                    AuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS,
                    "content_hash": intent.content_hash})
        return intent

    def validate_execution(self, *, intent_id: str, actor: str):
        intent = self._repo.get_execution_intent(intent_id)
        actor_type = authorize_execution(
            self._identity, self._policy, self._audit, actor=actor,
            permission=Permission.VIEW_EXECUTION, tenant_id=intent.tenant_id,
            correlation_id=intent.correlation_id, entity_id=intent_id)
        result = self._validation.validate(intent)
        if result.valid and intent.status is ExecutionStatus.INTENT_CREATED:
            self._transition(intent, ExecutionStatus.READY_FOR_DISPATCH)
        self._emit(AuditEventType.EXECUTION_VALIDATED, intent_id, actor, actor_type,
                   intent.correlation_id,
                   {"valid": result.valid, "blockers": list(result.blocker_codes)})
        return result

    # --- dispatch ---------------------------------------------------------
    def dispatch_execution(self, *, intent_id: str, actor: str) -> ExecutionAttempt:
        intent = self._repo.get_execution_intent(intent_id)
        actor_type = authorize_execution(
            self._identity, self._policy, self._audit, actor=actor,
            permission=Permission.DISPATCH_EXECUTION, tenant_id=intent.tenant_id,
            correlation_id=intent.correlation_id, entity_id=intent_id)
        if intent.status is ExecutionStatus.INTENT_CREATED:
            intent = self._transition(intent, ExecutionStatus.READY_FOR_DISPATCH)
        if intent.status is not ExecutionStatus.READY_FOR_DISPATCH:
            raise InvalidExecutionTransitionError(
                f"intent must be READY_FOR_DISPATCH to dispatch; is {intent.status.value}")
        self._guard_expiry(intent)
        return self._dispatch(intent, actor, actor_type,
                              RetryClassification.NOT_RETRYABLE)

    def retry_execution(self, *, intent_id: str, actor: str,
                        retry_classification: RetryClassification,
                        second_approver: Optional[str] = None) -> ExecutionAttempt:
        intent = self._repo.get_execution_intent(intent_id)
        actor_type = authorize_execution(
            self._identity, self._policy, self._audit, actor=actor,
            permission=Permission.RETRY_EXECUTION, tenant_id=intent.tenant_id,
            correlation_id=intent.correlation_id, entity_id=intent_id)
        # No retry without an explicit, safe classification.
        if retry_classification in (RetryClassification.UNSAFE,
                                    RetryClassification.NOT_RETRYABLE):
            raise UnsafeRetryError(
                f"retry classification {retry_classification.value} is not permitted")
        if retry_classification is RetryClassification.REQUIRES_APPROVAL:
            if not second_approver or second_approver == actor:
                raise UnsafeRetryError(
                    "a non-idempotent retry requires a distinct second approver")
            authorize_execution(
                self._identity, self._policy, self._audit, actor=second_approver,
                permission=Permission.RETRY_EXECUTION, tenant_id=intent.tenant_id,
                correlation_id=intent.correlation_id, entity_id=intent_id)
        self._emit(AuditEventType.EXECUTION_RETRY_REQUESTED, intent_id, actor, actor_type,
                   intent.correlation_id,
                   {"retry_classification": retry_classification.value,
                    "second_approver": second_approver})
        # Return the intent to a dispatchable state and dispatch a new attempt.
        if is_legal_transition(intent.status, ExecutionStatus.READY_FOR_DISPATCH):
            intent = self._transition(intent, ExecutionStatus.READY_FOR_DISPATCH)
        self._guard_expiry(intent)
        return self._dispatch(intent, actor, actor_type, retry_classification)

    def _dispatch(self, intent: ExecutionIntent, actor: str, actor_type,
                  retry_classification: RetryClassification) -> ExecutionAttempt:
        intent = self._transition(intent, ExecutionStatus.DISPATCH_PENDING)
        attempt_number = self._repo.attempt_count(intent.execution_intent_id) + 1
        payload_hash = canonical_hash(dict(intent.authorized_parameters))
        self._emit(AuditEventType.EXECUTION_DISPATCH_SUBMITTED,
                   intent.execution_intent_id, actor, actor_type, intent.correlation_id,
                   {"attempt_number": attempt_number, "payload_hash": payload_hash})
        try:
            response = self._port.dispatch(intent)
        except Exception as exc:  # noqa: BLE001 - provider errors never become success
            raise ExternalDispatchError(f"external dispatch failed: {exc}") from exc

        if response.transport_status not in _TRANSPORT_TO_STATUS:
            raise MalformedExternalResponseError(
                "external adapter returned an unknown transport status")

        adapter_id = getattr(self._port, "adapter_id", "external")
        adapter_version = getattr(self._port, "adapter_version", "")
        attempt = ExecutionAttempt(
            execution_attempt_id=self._new_id("exa"),
            execution_intent_id=intent.execution_intent_id,
            attempt_number=attempt_number, adapter_id=adapter_id,
            adapter_version=adapter_version, request_payload_hash=payload_hash,
            dispatched_at=self._clock(), transport_status=response.transport_status,
            external_request_id=response.external_request_id,
            acknowledgement=response.acknowledgement, completed_at=self._clock(),
            error_code=response.error_code, error_detail=response.error_detail,
            retry_classification=response.retry_classification,
            correlation_id=intent.correlation_id)
        self._repo.record_execution_attempt(attempt)
        # Transport outcome only — DISPATCHED/ACKNOWLEDGED is NOT business success.
        self._transition(intent, _TRANSPORT_TO_STATUS[response.transport_status])
        self._emit(_TRANSPORT_EVENT[response.transport_status],
                   intent.execution_intent_id, actor, actor_type, intent.correlation_id,
                   {"attempt_number": attempt_number,
                    "transport_status": response.transport_status.value,
                    "external_request_id": response.external_request_id})
        return attempt

    # --- helpers ----------------------------------------------------------
    def _guard_expiry(self, intent: ExecutionIntent) -> None:
        now = self._clock()
        try:
            responses = self._requests.get_authorization_history(intent.action_request_id)
            authz = next((r for r in reversed(responses)
                          if r.authorization_id == intent.authorization_id), None)
        except Exception:  # noqa: BLE001
            authz = None
        if authz is not None and authz.expires_at is not None and authz.expires_at < now:
            raise AuthorizationExpiredError("authorization expired before dispatch")
        cer = self._requests.get_cer(intent.cer_id)
        if cer.is_expired(now):
            raise CERExpiredForExecutionError("CER expired before dispatch")

    def _transition(self, intent: ExecutionIntent,
                    target: ExecutionStatus) -> ExecutionIntent:
        if intent.status is target:
            return intent
        if not is_legal_transition(intent.status, target):
            raise InvalidExecutionTransitionError(
                f"illegal transition {intent.status.value} -> {target.value}")
        evolved = intent.evolve(intent_version_id=self._new_id("iv"), status=target)
        return self._repo.save_execution_snapshot(evolved)

    # --- reads ------------------------------------------------------------
    def get_execution_intent(self, intent_id: str) -> ExecutionIntent:
        return self._repo.get_execution_intent(intent_id)

    def get_execution_history(self, intent_id: str) -> tuple[ExecutionIntent, ...]:
        return self._repo.get_intent_history(intent_id)

    def get_execution_attempts(self, intent_id: str) -> tuple[ExecutionAttempt, ...]:
        return self._repo.get_attempt_history(intent_id)
