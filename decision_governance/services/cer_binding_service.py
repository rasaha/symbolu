"""CERBindingService — builds the minimum-necessary Context Envelope Record.

Assembles only the governance context a runtime authorizer needs (tenant, subject,
authority type/scope, applicable policies, approved action + target, parameter
bounds, required controls, time validity) and binds the *exact* policy and
authority references. It enforces prohibited-field exclusion, hashes and versions
the CER, and **never submits or executes** anything.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from ..actions.action_request import ActionRequest
from ..actions.cer import (
    AuthoritySummary,
    ContextEnvelopeRecord,
    DecisionContext,
    PolicyContext,
    SubjectContext,
)
from ..actions.lifecycle import is_legal_transition
from ..actions.status import ActionRequestStatus
from ..common import Clock, IdFactory, new_id, utc_now
from ..identity.actor import ActorType
from ..audit.events import AuditEventType
from ..errors import (
    ActionRequestNotReadyError,
    CERBindingError,
    ProhibitedActionParameterError,
)
from ..identity import IdentityProvider
from ..policy import EvidenceAccessPolicy, Permission
from ..repositories.action_request_repository import ActionRequestRepository
from ..repositories.decision_case_repository import DecisionCaseRepository
from ..audit import AuditService
from ._action_authz import authorize_action

_CREDENTIAL_MARKERS = ("password", "secret", "token", "credential", "api_key",
                       "apikey", "private_key", "access_key")


class CERBindingService:
    def __init__(
        self,
        action_request_repository: ActionRequestRepository,
        decision_case_repository: DecisionCaseRepository,
        audit_service: AuditService,
        identity_provider: IdentityProvider,
        access_policy: EvidenceAccessPolicy,
        *,
        default_validity: timedelta = timedelta(hours=1),
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._repo = action_request_repository
        self._cases = decision_case_repository
        self._audit = audit_service
        self._identity = identity_provider
        self._policy = access_policy
        self._validity = default_validity
        self._new_id = id_factory
        self._clock = clock

    def bind_cer(self, *, request_id: str, actor: str,
                 data_classifications: tuple[str, ...] = (),
                 runtime_constraints: tuple[str, ...] = ()) -> ContextEnvelopeRecord:
        request = self._repo.get_action_request(request_id)
        actor_type = authorize_action(
            self._identity, self._policy, self._audit, actor=actor,
            permission=Permission.BIND_CER, tenant_id=request.tenant_id,
            correlation_id=request.correlation_id, entity_id=request_id)

        if request.status is not ActionRequestStatus.READY_FOR_BINDING:
            raise ActionRequestNotReadyError(
                f"request must be READY_FOR_BINDING to bind a CER; is {request.status.value}")

        # Defense in depth: no credential-like parameter may enter the CER.
        for key in request.requested_parameters:
            low = key.lower()
            if any(marker in low for marker in _CREDENTIAL_MARKERS):
                raise ProhibitedActionParameterError(
                    f"parameter '{key}' is credential-like and cannot be bound into a CER")

        decision = self._cases.get_decision(request.decision_id)
        case = self._cases.get_case(request.decision_case_id)
        mapping = self._repo.get_action_mapping(
            request.action_mapping_ref.ref_id, request.action_mapping_ref.version)

        # Minimum-necessary context only.
        subject_context = SubjectContext(
            subject_refs=request.subject_refs,
            data_classifications=data_classifications)
        case_auth = case.authority_context
        authority_summary = AuthoritySummary(
            authority_type=decision.authority_type,
            authority_id=decision.decided_by,
            decision_scope=case_auth.decision_scope if case_auth else "",
            segregation_of_duties=case_auth.segregation_of_duties if case_auth else False,
            required_approvals=case_auth.required_approvals if case_auth else 0,
            granting_policy_ref=case_auth.granting_policy_ref if case_auth else None)
        policy_context = PolicyContext(policy_refs=decision.policy_refs)
        decision_context = DecisionContext(
            decision_case_id=decision.decision_case_id,
            decision_case_version=request.decision_case_version,
            decision_id=decision.decision_id, decision_outcome=decision.outcome,
            override_record_id=decision.override_record_id,
            reason_codes=decision.reason_codes)

        issued = self._clock()
        cer = ContextEnvelopeRecord(
            cer_id=self._new_id("cer"), tenant_id=request.tenant_id,
            decision_case_id=request.decision_case_id, decision_id=request.decision_id,
            action_request_id=request.action_request_id, action_type=request.action_type,
            target_system=request.target_system, subject_context=subject_context,
            authority_context=authority_summary, policy_context=policy_context,
            decision_context=decision_context, runtime_constraints=runtime_constraints,
            data_classifications=data_classifications,
            permitted_parameters=tuple(sorted(request.requested_parameters.keys())),
            prohibited_parameters=mapping.prohibited_fields,
            required_controls=mapping.required_context_fields, issued_at=issued,
            expires_at=issued + self._validity, correlation_id=request.correlation_id)
        cer = cer.model_copy(update={"content_hash": cer.compute_hash()})
        if not cer.content_hash:
            raise CERBindingError("failed to compute CER content hash")
        self._repo.save_cer(cer)
        self._audit.record(
            event_type=AuditEventType.CER_CREATED, entity_type="cer", entity_id=cer.cer_id,
            actor_type=actor_type, actor_id=actor, correlation_id=request.correlation_id,
            payload={"action_request_id": request_id, "content_hash": cer.content_hash})

        # Bind the CER to the request (append-only snapshot).
        if not is_legal_transition(request.status, ActionRequestStatus.CER_BOUND):
            raise ActionRequestNotReadyError("request cannot transition to CER_BOUND")
        bound = request.evolve(request_version_id=self._new_id("rv"),
                               status=ActionRequestStatus.CER_BOUND, cer_id=cer.cer_id)
        self._repo.save_action_request_snapshot(bound)
        self._audit.record(
            event_type=AuditEventType.CER_BOUND, entity_type="action_request",
            entity_id=request_id, actor_type=actor_type, actor_id=actor,
            correlation_id=request.correlation_id,
            payload={"cer_id": cer.cer_id, "content_hash": cer.content_hash})
        return cer

    def get_cer(self, cer_id: str) -> ContextEnvelopeRecord:
        return self._repo.get_cer(cer_id)
