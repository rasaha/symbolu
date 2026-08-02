"""ActionAuthorizationService — submits a bound request to the control-plane port.

Submits a CER-bound request through the provider-neutral
:class:`ActionControlPlanePort`, records each attempt and immutable response, and
applies the response outcome to a new request snapshot. It preserves constraints
and obligations, keeps ``DENIED``/``INDETERMINATE``/``EXPIRED`` strictly distinct
from approval, and **never calls an enterprise execution system**. An authorized
request is not an executed one.
"""

from __future__ import annotations

from typing import Optional

from ..actions.authorization import ActionAuthorizationResponse
from ..actions.control_plane import ActionControlPlanePort
from ..actions.lifecycle import is_legal_transition
from ..actions.status import (
    ActionRequestStatus,
    AUTHORIZED_STATUSES,
    AuthorizationOutcome,
    OUTCOME_TO_STATUS,
    RETRYABLE_STATUSES,
)
from ..common import Clock, IdFactory, new_id, utc_now
from ..identity.actor import ActorType
from ..audit.events import AuditEventType
from ..errors import (
    ActionRequestAlreadyAuthorizedError,
    ActionRequestNotReadyError,
    AuthorizationResponseMismatchError,
    AuthorizationSubmissionError,
    CERExpiredError,
)
from ..identity import IdentityProvider
from ..policy import EvidenceAccessPolicy, Permission
from ..repositories.action_request_repository import ActionRequestRepository
from ..audit import AuditService
from ._action_authz import authorize_action

_OUTCOME_EVENT = {
    AuthorizationOutcome.AUTHORIZED: AuditEventType.ACTION_AUTHORIZATION_GRANTED,
    AuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS:
        AuditEventType.ACTION_AUTHORIZATION_CONSTRAINED,
    AuthorizationOutcome.DENIED: AuditEventType.ACTION_AUTHORIZATION_DENIED,
    AuthorizationOutcome.INDETERMINATE:
        AuditEventType.ACTION_AUTHORIZATION_INDETERMINATE,
    AuthorizationOutcome.EXPIRED: AuditEventType.ACTION_AUTHORIZATION_EXPIRED,
}

_SUBMITTABLE = frozenset({
    ActionRequestStatus.CER_BOUND, ActionRequestStatus.READY_FOR_AUTHORIZATION,
}) | RETRYABLE_STATUSES


class ActionAuthorizationService:
    def __init__(
        self,
        action_request_repository: ActionRequestRepository,
        control_plane: ActionControlPlanePort,
        audit_service: AuditService,
        identity_provider: IdentityProvider,
        access_policy: EvidenceAccessPolicy,
        *,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._repo = action_request_repository
        self._control_plane = control_plane
        self._audit = audit_service
        self._identity = identity_provider
        self._policy = access_policy
        self._new_id = id_factory
        self._clock = clock

    def submit_for_authorization(self, *, request_id: str, actor: str
                                 ) -> ActionAuthorizationResponse:
        request = self._repo.get_action_request(request_id)
        actor_type = authorize_action(
            self._identity, self._policy, self._audit, actor=actor,
            permission=Permission.SUBMIT_FOR_AUTHORIZATION, tenant_id=request.tenant_id,
            correlation_id=request.correlation_id, entity_id=request_id)

        if request.status in AUTHORIZED_STATUSES:
            raise ActionRequestAlreadyAuthorizedError(
                f"request already {request.status.value}; supersede to re-authorize")
        if request.status not in _SUBMITTABLE:
            raise ActionRequestNotReadyError(
                f"request must be CER-bound to submit; is {request.status.value}")
        if not request.cer_id:
            raise ActionRequestNotReadyError("request has no bound CER")

        cer = self._repo.get_cer(request.cer_id)
        # Fail closed if the CER has already expired at submission time.
        if cer.is_expired(self._clock()):
            raise CERExpiredError(
                f"CER '{cer.cer_id}' has expired; rebind or supersede the request")

        # Advance through the legal chain to AUTHORIZATION_PENDING.
        request = self._advance(request, ActionRequestStatus.READY_FOR_AUTHORIZATION)
        request = self._advance(request, ActionRequestStatus.AUTHORIZATION_PENDING)
        attempt = self._repo.attempt_count(request_id) + 1
        self._repo.record_authorization_attempt(request_id, attempt)
        self._audit.record(
            event_type=AuditEventType.ACTION_AUTHORIZATION_SUBMITTED,
            entity_type="action_request", entity_id=request_id, actor_type=actor_type,
            actor_id=actor, correlation_id=request.correlation_id,
            payload={"cer_id": cer.cer_id, "attempt": attempt})

        # Submit through the provider-neutral port; provider errors are not approvals.
        try:
            response = self._control_plane.authorize(request, cer)
        except Exception as exc:  # noqa: BLE001
            raise AuthorizationSubmissionError(
                f"control plane submission failed: {exc}") from exc

        # Reject a malformed / mismatched response — it never becomes an approval.
        if (response.action_request_id != request.action_request_id
                or response.cer_id != cer.cer_id
                or response.outcome not in OUTCOME_TO_STATUS):
            raise AuthorizationResponseMismatchError(
                "control-plane response does not match the submitted request/CER")

        response = response.model_copy(update={"attempt": attempt})
        self._repo.record_authorization_response(response)

        new_status = OUTCOME_TO_STATUS[response.outcome]
        self._advance(request, new_status)
        self._audit.record(
            event_type=_OUTCOME_EVENT[response.outcome], entity_type="action_request",
            entity_id=request_id, actor_type=actor_type, actor_id=actor,
            correlation_id=request.correlation_id,
            payload={"authorization_id": response.authorization_id,
                     "outcome": response.outcome.value, "attempt": attempt,
                     "constraints": list(response.constraints),
                     "obligations": list(response.obligations)})
        return response

    def _advance(self, request, target: ActionRequestStatus):
        if request.status is target:
            return request
        if not is_legal_transition(request.status, target):
            raise ActionRequestNotReadyError(
                f"illegal transition {request.status.value} -> {target.value}")
        evolved = request.evolve(request_version_id=self._new_id("rv"), status=target)
        return self._repo.save_action_request_snapshot(evolved)

    def get_authorization_history(self, request_id: str
                                  ) -> tuple[ActionAuthorizationResponse, ...]:
        return self._repo.get_authorization_history(request_id)
