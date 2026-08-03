"""Evidence-collection intake service (H1).

Records collected evidence against an application with an explicit provenance
descriptor and content hash, under tenant isolation, and captures both the intake
and its provenance binding on the hiring-owned domain audit trail. It defines the
intake/collection surface only — it does not read, extract, normalize, or score
evidence content (later phases).
"""

from __future__ import annotations

from typing import Callable, Optional

from ugence_decision_authority.api.common import new_id

from ..domain_audit.events import HiringDomainEventType
from ..domain_audit.service import HiringDomainAuditService
from ..intake.intake import EvidenceIntakeItem, EvidenceProvenance
from ..repositories.product_repositories import (
    ApplicationRepository,
    EvidenceIntakeRepository,
)
from ._hiring_context import ActorContext, guard_tenant


class EvidenceIntakeService:
    def __init__(
        self,
        *,
        evidence_intake: EvidenceIntakeRepository,
        applications: ApplicationRepository,
        audit: HiringDomainAuditService,
        id_factory: Callable[[str], str] = new_id,
    ) -> None:
        self._intake = evidence_intake
        self._apps = applications
        self._audit = audit
        self._new_id = id_factory

    def intake_evidence(
        self, ctx: ActorContext, *, application_id: str, evidence_type: str,
        content_hash: str, provenance: EvidenceProvenance, intake_id: Optional[str] = None,
        correlation_id: str = "",
    ) -> EvidenceIntakeItem:
        # The application must exist and be in-tenant.
        app = self._apps.get(application_id)
        guard_tenant(ctx, record_tenant_id=app.tenant_id, entity_type="application",
                     entity_id=application_id, audit=self._audit)

        iid = intake_id or self._new_id("intk")
        item = EvidenceIntakeItem(
            intake_id=iid, tenant_id=ctx.tenant_id, application_id=application_id,
            candidate_id=app.candidate_id, requisition_id=app.requisition_id,
            evidence_type=evidence_type, content_hash=content_hash, provenance=provenance,
            correlation_id=correlation_id,
        )
        self._intake.add(item)
        self._audit.record(
            event_type=HiringDomainEventType.EVIDENCE_INTAKE_RECEIVED, entity_type="evidence_intake",
            entity_id=iid, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, actor_type=ctx.actor_type,
            new_state="RECEIVED", entity_version=item.version, correlation_id=correlation_id,
            payload={"application_id": application_id, "evidence_type": evidence_type,
                     "content_hash": content_hash},
        )
        self._audit.record(
            event_type=HiringDomainEventType.EVIDENCE_INTAKE_PROVENANCE_BOUND,
            entity_type="evidence_intake", entity_id=iid, tenant_id=ctx.tenant_id,
            actor_id=ctx.actor_id, actor_type=ctx.actor_type, entity_version=item.version,
            correlation_id=correlation_id,
            payload={"source": provenance.source.value, "collected_by": provenance.collected_by,
                     "source_ref": provenance.source_ref},
        )
        return item
