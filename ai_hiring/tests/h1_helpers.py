"""Shared harness for H1 hiring-product tests (deterministic wiring)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count

from decision_governance.api.identity import ActorType

from ai_hiring.domain_audit import HiringDomainAuditService, InMemoryHiringDomainAuditRepository
from ai_hiring.repositories.product_repositories import (
    InMemoryApplicationRepository,
    InMemoryCandidateRepository,
    InMemoryEvidenceIntakeRepository,
    InMemoryJobDefinitionRepository,
    InMemoryRequisitionRepository,
)
from ai_hiring.services._hiring_context import ActorContext
from ai_hiring.services.application_service import ApplicationService
from ai_hiring.services.candidate_service import CandidateService
from ai_hiring.services.evidence_intake_service import EvidenceIntakeService
from ai_hiring.services.hiring_reconstruction_service import HiringReconstructionService
from ai_hiring.services.requisition_service import RequisitionService


def deterministic_ids():
    counters: dict[str, count] = {}

    def factory(prefix: str) -> str:
        c = counters.setdefault(prefix, count(1))
        return f"{prefix}_{next(c):04d}"

    return factory


def fixed_clock():
    ticks = count(0)

    def clock() -> datetime:
        # strictly increasing, deterministic timestamps
        return datetime(2026, 1, 1, tzinfo=timezone.utc).replace(microsecond=0) \
            .fromtimestamp(1_760_000_000 + next(ticks), tz=timezone.utc)

    return clock


@dataclass
class Env:
    audit_repo: InMemoryHiringDomainAuditRepository
    audit: HiringDomainAuditService
    reqs: InMemoryRequisitionRepository
    defs: InMemoryJobDefinitionRepository
    cands: InMemoryCandidateRepository
    apps: InMemoryApplicationRepository
    intake: InMemoryEvidenceIntakeRepository
    requisition_service: RequisitionService
    candidate_service: CandidateService
    application_service: ApplicationService
    intake_service: EvidenceIntakeService
    reconstruction_service: HiringReconstructionService


def build_env() -> Env:
    idf = deterministic_ids()
    clk = fixed_clock()
    audit_repo = InMemoryHiringDomainAuditRepository()
    audit = HiringDomainAuditService(audit_repo, id_factory=idf, clock=clk)
    reqs, defs = InMemoryRequisitionRepository(), InMemoryJobDefinitionRepository()
    cands, apps = InMemoryCandidateRepository(), InMemoryApplicationRepository()
    intake = InMemoryEvidenceIntakeRepository()
    return Env(
        audit_repo=audit_repo, audit=audit, reqs=reqs, defs=defs, cands=cands, apps=apps,
        intake=intake,
        requisition_service=RequisitionService(requisitions=reqs, job_definitions=defs, audit=audit, id_factory=idf),
        candidate_service=CandidateService(candidates=cands, audit=audit, id_factory=idf),
        application_service=ApplicationService(applications=apps, requisitions=reqs, job_definitions=defs,
                                               candidates=cands, evidence_intake=intake, audit=audit, id_factory=idf),
        intake_service=EvidenceIntakeService(evidence_intake=intake, applications=apps, audit=audit, id_factory=idf),
        reconstruction_service=HiringReconstructionService(
            requisitions=reqs, job_definitions=defs, candidates=cands, applications=apps,
            evidence_intake=intake, audit_repository=audit_repo),
    )


def ctx(tenant="t1", actor="recruiter1", actor_type=ActorType.HUMAN) -> ActorContext:
    return ActorContext(tenant_id=tenant, actor_id=actor, actor_type=actor_type)


def open_requisition_with_published_def(env: Env, c: ActorContext, *,
                                        required_evidence_types=("resume", "code_sample")):
    """Convenience: an OPEN requisition + PUBLISHED job definition ready for applications."""
    req = env.requisition_service.create_requisition(c, title="Engineer", requisition_id="req1")
    env.requisition_service.open_requisition(c, "req1")
    env.requisition_service.draft_job_definition(
        c, requisition_id="req1", rubric_id="rb1", rubric_version=1,
        required_evidence_types=tuple(required_evidence_types), job_definition_id="jd1")
    env.requisition_service.publish_job_definition(c, "jd1")
    return req
