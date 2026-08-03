"""Application application-service (H1).

Owns the structural application lifecycle: submission (gated by deterministic
eligibility + duplicate prevention), screening, assessment advancement (gated by
deterministic evidence readiness), review, closure, and withdrawal. Enforces
tenant isolation and records every transition on the hiring-owned domain audit
trail.

It makes **no binding hiring decision** — the lifecycle stops at the structural
terminal states CLOSED / WITHDRAWN. Accept/reject decisions and offer/rejection
actions are governance concerns for later phases; no actor (human, system, or AI)
is granted hiring decision authority here.
"""

from __future__ import annotations

from typing import Callable, Optional

from ugence_decision_authority.api.common import new_id

from ..domain_audit.events import HiringDomainEventType
from ..domain_audit.service import HiringDomainAuditService
from ..errors import (
    DuplicateApplicationError,
    IneligibleApplicationError,
    NotReadyForAssessmentError,
)
from ..hiring_applications.application import Application
from ..hiring_applications.eligibility import EligibilityResult, evaluate_eligibility
from ..hiring_applications.readiness import ReadinessResult, evaluate_readiness
from ..hiring_applications.status import ApplicationStatus
from ..repositories.product_repositories import (
    ApplicationRepository,
    CandidateRepository,
    EvidenceIntakeRepository,
    JobDefinitionRepository,
    RequisitionRepository,
)
from ._hiring_context import ActorContext, guard_tenant


class ApplicationService:
    def __init__(
        self,
        *,
        applications: ApplicationRepository,
        requisitions: RequisitionRepository,
        job_definitions: JobDefinitionRepository,
        candidates: CandidateRepository,
        evidence_intake: EvidenceIntakeRepository,
        audit: HiringDomainAuditService,
        id_factory: Callable[[str], str] = new_id,
    ) -> None:
        self._apps = applications
        self._reqs = requisitions
        self._defs = job_definitions
        self._candidates = candidates
        self._intake = evidence_intake
        self._audit = audit
        self._new_id = id_factory

    def check_eligibility(
        self, ctx: ActorContext, *, candidate_id: str, requisition_id: str, job_definition_id: str,
    ) -> EligibilityResult:
        requisition = self._reqs.get(requisition_id) if self._reqs.exists(requisition_id) else None
        job_definition = self._defs.get(job_definition_id) if self._defs.exists(job_definition_id) else None
        candidate = self._candidates.get(candidate_id) if self._candidates.exists(candidate_id) else None
        duplicate = self._apps.active_exists(ctx.tenant_id, candidate_id, requisition_id)
        return evaluate_eligibility(
            tenant_id=ctx.tenant_id, requisition=requisition, job_definition=job_definition,
            candidate=candidate, has_active_duplicate=duplicate,
        )

    def submit_application(
        self, ctx: ActorContext, *, candidate_id: str, requisition_id: str, job_definition_id: str,
        application_id: Optional[str] = None, correlation_id: str = "",
    ) -> Application:
        eligibility = self.check_eligibility(
            ctx, candidate_id=candidate_id, requisition_id=requisition_id,
            job_definition_id=job_definition_id,
        )
        if "duplicate_active_application" in eligibility.reasons:
            self._audit.record_denial(
                entity_type="application", entity_id=f"{candidate_id}:{requisition_id}",
                tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, actor_type=ctx.actor_type,
                reason="duplicate_active_application",
            )
            raise DuplicateApplicationError(
                f"candidate '{candidate_id}' already has an active application to "
                f"requisition '{requisition_id}'"
            )
        if not eligibility.eligible:
            self._audit.record_denial(
                entity_type="application", entity_id=f"{candidate_id}:{requisition_id}",
                tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, actor_type=ctx.actor_type,
                reason="ineligible:" + ",".join(eligibility.reasons),
            )
            raise IneligibleApplicationError(
                f"application ineligible: {', '.join(eligibility.reasons)}"
            )

        job_definition = self._defs.get(job_definition_id)
        aid = application_id or self._new_id("app")
        app = Application(
            application_id=aid, tenant_id=ctx.tenant_id, candidate_id=candidate_id,
            requisition_id=requisition_id, job_definition_id=job_definition_id,
            job_definition_version=job_definition.version, created_by=ctx.actor_id,
            correlation_id=correlation_id,
        )
        self._apps.add(app)
        self._audit.record(
            event_type=HiringDomainEventType.APPLICATION_SUBMITTED, entity_type="application",
            entity_id=aid, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, actor_type=ctx.actor_type,
            new_state=app.status.value, entity_version=app.version, correlation_id=correlation_id,
            payload={"candidate_id": candidate_id, "requisition_id": requisition_id},
        )
        return app

    def check_readiness(self, ctx: ActorContext, application_id: str) -> ReadinessResult:
        app = self._apps.get(application_id)
        guard_tenant(ctx, record_tenant_id=app.tenant_id, entity_type="application",
                     entity_id=application_id, audit=self._audit)
        job_definition = self._defs.get(app.job_definition_id)
        collected = self._intake.evidence_types_for_application(application_id)
        return evaluate_readiness(job_definition=job_definition, collected_evidence_types=collected)

    def start_screening(self, ctx, application_id):
        return self._transition(ctx, application_id, ApplicationStatus.SCREENING,
                                HiringDomainEventType.APPLICATION_SCREENING_STARTED)

    def advance_to_assessment(self, ctx: ActorContext, application_id: str) -> Application:
        readiness = self.check_readiness(ctx, application_id)
        if not readiness.ready:
            self._audit.record_denial(
                entity_type="application", entity_id=application_id, tenant_id=ctx.tenant_id,
                actor_id=ctx.actor_id, actor_type=ctx.actor_type,
                reason="not_ready:" + ",".join(readiness.missing_evidence_types),
            )
            raise NotReadyForAssessmentError(
                "missing required evidence: " + ", ".join(readiness.missing_evidence_types)
            )
        return self._transition(ctx, application_id, ApplicationStatus.ASSESSMENT,
                                HiringDomainEventType.APPLICATION_ADVANCED_TO_ASSESSMENT)

    def advance_to_review(self, ctx, application_id):
        return self._transition(ctx, application_id, ApplicationStatus.IN_REVIEW,
                                HiringDomainEventType.APPLICATION_ADVANCED_TO_REVIEW)

    def close_application(self, ctx, application_id):
        return self._transition(ctx, application_id, ApplicationStatus.CLOSED,
                                HiringDomainEventType.APPLICATION_CLOSED)

    def withdraw_application(self, ctx, application_id):
        return self._transition(ctx, application_id, ApplicationStatus.WITHDRAWN,
                                HiringDomainEventType.APPLICATION_WITHDRAWN)

    def _transition(self, ctx, application_id, new_status, event_type) -> Application:
        current = self._apps.get(application_id)
        guard_tenant(ctx, record_tenant_id=current.tenant_id, entity_type="application",
                     entity_id=application_id, audit=self._audit)
        updated = current.with_status(new_status)  # validates transition
        self._apps.add(updated)
        self._audit.record(
            event_type=event_type, entity_type="application", entity_id=application_id,
            tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, actor_type=ctx.actor_type,
            previous_state=current.status.value, new_state=updated.status.value,
            entity_version=updated.version, correlation_id=current.correlation_id,
        )
        return updated
