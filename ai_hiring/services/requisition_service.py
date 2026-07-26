"""Requisition & job-definition application service (H1).

Creates and drives the structural lifecycle of requisitions and their job
definitions, persisting immutable versions and recording every state change on the
hiring-owned domain audit trail. Enforces tenant isolation. No scoring or decisions.
"""

from __future__ import annotations

from typing import Callable, Optional

from decision_governance.api.common import new_id

from ..domain_audit.events import HiringDomainEventType
from ..domain_audit.service import HiringDomainAuditService
from ..repositories.product_repositories import (
    JobDefinitionRepository,
    RequisitionRepository,
)
from ..requisitions.job_definition import JobDefinition
from ..requisitions.requisition import JobRequisition
from ..requisitions.status import JobDefinitionStatus, RequisitionStatus
from ._hiring_context import ActorContext, guard_tenant

_STATUS_EVENT = {
    RequisitionStatus.OPEN: HiringDomainEventType.REQUISITION_OPENED,
    RequisitionStatus.ON_HOLD: HiringDomainEventType.REQUISITION_PUT_ON_HOLD,
    RequisitionStatus.FILLED: HiringDomainEventType.REQUISITION_FILLED,
    RequisitionStatus.CLOSED: HiringDomainEventType.REQUISITION_CLOSED,
    RequisitionStatus.CANCELLED: HiringDomainEventType.REQUISITION_CANCELLED,
}


class RequisitionService:
    def __init__(
        self,
        *,
        requisitions: RequisitionRepository,
        job_definitions: JobDefinitionRepository,
        audit: HiringDomainAuditService,
        id_factory: Callable[[str], str] = new_id,
    ) -> None:
        self._reqs = requisitions
        self._defs = job_definitions
        self._audit = audit
        self._new_id = id_factory

    # --- requisitions ------------------------------------------------------
    def create_requisition(
        self, ctx: ActorContext, *, title: str, requisition_id: Optional[str] = None,
        department: str = "", employment_type: str = "", location: str = "",
        headcount: int = 1, description: str = "", correlation_id: str = "",
    ) -> JobRequisition:
        rid = requisition_id or self._new_id("req")
        req = JobRequisition(
            requisition_id=rid, tenant_id=ctx.tenant_id, title=title,
            department=department, employment_type=employment_type, location=location,
            headcount=headcount, description=description, created_by=ctx.actor_id,
            correlation_id=correlation_id,
        )
        self._reqs.add(req)
        self._audit.record(
            event_type=HiringDomainEventType.REQUISITION_CREATED, entity_type="requisition",
            entity_id=rid, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, new_state=req.status.value, entity_version=req.version,
            correlation_id=correlation_id,
        )
        return req

    def _transition(self, ctx: ActorContext, requisition_id: str, new_status: RequisitionStatus) -> JobRequisition:
        current = self._reqs.get(requisition_id)
        guard_tenant(ctx, record_tenant_id=current.tenant_id, entity_type="requisition",
                     entity_id=requisition_id, audit=self._audit)
        updated = current.with_status(new_status)  # validates transition (raises if illegal)
        self._reqs.add(updated)
        self._audit.record(
            event_type=_STATUS_EVENT[new_status], entity_type="requisition",
            entity_id=requisition_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, previous_state=current.status.value,
            new_state=updated.status.value, entity_version=updated.version,
            correlation_id=current.correlation_id,
        )
        return updated

    def open_requisition(self, ctx, requisition_id): return self._transition(ctx, requisition_id, RequisitionStatus.OPEN)
    def hold_requisition(self, ctx, requisition_id): return self._transition(ctx, requisition_id, RequisitionStatus.ON_HOLD)

    def resume_requisition(self, ctx, requisition_id):
        # ON_HOLD -> OPEN uses the REQUISITION_RESUMED event for clarity.
        current = self._reqs.get(requisition_id)
        guard_tenant(ctx, record_tenant_id=current.tenant_id, entity_type="requisition",
                     entity_id=requisition_id, audit=self._audit)
        updated = current.with_status(RequisitionStatus.OPEN)
        self._reqs.add(updated)
        self._audit.record(
            event_type=HiringDomainEventType.REQUISITION_RESUMED, entity_type="requisition",
            entity_id=requisition_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, previous_state=current.status.value,
            new_state=updated.status.value, entity_version=updated.version,
            correlation_id=current.correlation_id,
        )
        return updated

    def fill_requisition(self, ctx, requisition_id): return self._transition(ctx, requisition_id, RequisitionStatus.FILLED)
    def close_requisition(self, ctx, requisition_id): return self._transition(ctx, requisition_id, RequisitionStatus.CLOSED)
    def cancel_requisition(self, ctx, requisition_id): return self._transition(ctx, requisition_id, RequisitionStatus.CANCELLED)

    # --- job definitions ---------------------------------------------------
    def draft_job_definition(
        self, ctx: ActorContext, *, requisition_id: str, rubric_id: str, rubric_version: int,
        required_capability_ids: tuple[str, ...] = (), required_evidence_types: tuple[str, ...] = (),
        job_definition_id: Optional[str] = None, correlation_id: str = "",
    ) -> JobDefinition:
        requisition = self._reqs.get(requisition_id)  # must exist
        guard_tenant(ctx, record_tenant_id=requisition.tenant_id, entity_type="requisition",
                     entity_id=requisition_id, audit=self._audit)
        jid = job_definition_id or self._new_id("jd")
        jd = JobDefinition(
            job_definition_id=jid, requisition_id=requisition_id, tenant_id=ctx.tenant_id,
            rubric_id=rubric_id, rubric_version=rubric_version,
            required_capability_ids=tuple(required_capability_ids),
            required_evidence_types=tuple(required_evidence_types),
            created_by=ctx.actor_id, correlation_id=correlation_id,
        )
        self._defs.add(jd)
        self._audit.record(
            event_type=HiringDomainEventType.JOB_DEFINITION_DRAFTED, entity_type="job_definition",
            entity_id=jid, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, actor_type=ctx.actor_type,
            new_state=jd.status.value, entity_version=jd.version, correlation_id=correlation_id,
        )
        return jd

    def publish_job_definition(self, ctx: ActorContext, job_definition_id: str) -> JobDefinition:
        return self._def_transition(ctx, job_definition_id, JobDefinitionStatus.PUBLISHED,
                                    HiringDomainEventType.JOB_DEFINITION_PUBLISHED)

    def retire_job_definition(self, ctx: ActorContext, job_definition_id: str) -> JobDefinition:
        return self._def_transition(ctx, job_definition_id, JobDefinitionStatus.RETIRED,
                                    HiringDomainEventType.JOB_DEFINITION_RETIRED)

    def _def_transition(self, ctx, job_definition_id, new_status, event_type) -> JobDefinition:
        current = self._defs.get(job_definition_id)
        guard_tenant(ctx, record_tenant_id=current.tenant_id, entity_type="job_definition",
                     entity_id=job_definition_id, audit=self._audit)
        updated = current.with_status(new_status)
        self._defs.add(updated)
        self._audit.record(
            event_type=event_type, entity_type="job_definition", entity_id=job_definition_id,
            tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, actor_type=ctx.actor_type,
            previous_state=current.status.value, new_state=updated.status.value,
            entity_version=updated.version, correlation_id=current.correlation_id,
        )
        return updated
