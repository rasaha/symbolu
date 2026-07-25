"""CompensationService — records and resolves governed compensation requirements.

A compensation requirement is a **proposal or obligation**, never an automatic
rollback. Phase 4C records it; any compensating action must pass through the normal
governance chain (a new governed action request in Phase 4B). Resolution appends a
new immutable revision and never mutates the original execution outcome.
"""

from __future__ import annotations

from typing import Optional

from ..common import Clock, IdFactory, new_id, utc_now
from ..identity.actor import ActorType
from ..audit.events import AuditEventType
from ..execution.compensation import CompensationRequirement
from ..execution.status import (
    CompensationApprovalStatus,
    CompensationType,
)
from ..errors import CompensationNotFoundError
from ..identity import IdentityProvider
from ..policy import EvidenceAccessPolicy, Permission
from ..repositories.execution_repository import InMemoryExecutionRepository
from ..audit import AuditService
from ._execution_authz import authorize_execution


class CompensationService:
    def __init__(
        self,
        execution_repository: InMemoryExecutionRepository,
        audit_service: AuditService,
        identity_provider: IdentityProvider,
        access_policy: EvidenceAccessPolicy,
        *,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._repo = execution_repository
        self._audit = audit_service
        self._identity = identity_provider
        self._policy = access_policy
        self._new_id = id_factory
        self._clock = clock

    def _emit(self, event_type, entity_id, actor, actor_type, corr, payload):
        self._audit.record(
            event_type=event_type, entity_type="execution", entity_id=entity_id,
            actor_type=actor_type, actor_id=actor, correlation_id=corr, payload=payload)

    def create_compensation_requirement(
        self, *, intent_id: str, reconciliation_id: str, actor: str,
        reason_codes: tuple[str, ...],
        proposed_compensation_type: CompensationType = CompensationType.MANUAL_INTERVENTION,
        affected_effects: tuple[str, ...] = (), required_authority: str = "",
    ) -> CompensationRequirement:
        intent = self._repo.get_execution_intent(intent_id)
        actor_type = authorize_execution(
            self._identity, self._policy, self._audit, actor=actor,
            permission=Permission.CREATE_COMPENSATION_REQUIREMENT,
            tenant_id=intent.tenant_id, correlation_id=intent.correlation_id,
            entity_id=intent_id)
        comp = CompensationRequirement(
            compensation_id=self._new_id("comp"), execution_intent_id=intent_id,
            reconciliation_id=reconciliation_id, tenant_id=intent.tenant_id,
            reason_codes=reason_codes, affected_effects=affected_effects,
            proposed_compensation_type=proposed_compensation_type,
            required_authority=required_authority,
            approval_status=CompensationApprovalStatus.PROPOSED, created_by=actor,
            created_at=self._clock())
        self._repo.record_compensation_requirement(comp)
        self._emit(AuditEventType.COMPENSATION_REQUIRED, comp.compensation_id, actor,
                   actor_type, intent.correlation_id,
                   {"intent_id": intent_id, "reconciliation_id": reconciliation_id,
                    "type": proposed_compensation_type.value})
        return comp

    def resolve_compensation_requirement(
        self, *, compensation_id: str, actor: str, resolution_ref: str,
        status: CompensationApprovalStatus = CompensationApprovalStatus.RESOLVED,
    ) -> CompensationRequirement:
        comp = self._repo.get_compensation(compensation_id)
        intent = self._repo.get_execution_intent(comp.execution_intent_id)
        actor_type = authorize_execution(
            self._identity, self._policy, self._audit, actor=actor,
            permission=Permission.RESOLVE_COMPENSATION_REQUIREMENT,
            tenant_id=comp.tenant_id, correlation_id=intent.correlation_id,
            entity_id=compensation_id)
        resolved = comp.resolved(by=actor, at=self._clock(),
                                 resolution_ref=resolution_ref, status=status)
        self._repo.save_compensation_snapshot(resolved)
        self._emit(AuditEventType.COMPENSATION_RESOLVED, compensation_id, actor,
                   actor_type, intent.correlation_id,
                   {"resolution_ref": resolution_ref, "status": status.value})
        return resolved

    def get_compensation_history(self, intent_id: str) -> tuple[CompensationRequirement, ...]:
        return self._repo.get_compensation_history(intent_id)
