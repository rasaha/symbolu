"""Shared harness for H2 recommendation/synthesis tests (deterministic wiring)."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count

from ugence_decision_authority.api.identity import ActorType
from ugence_governance_provider_framework.api import AssertionAssessmentIntegration
from ugence_governance_provider_framework.contracts import AssertionCoverage
from ugence_governance_provider_framework.reference.assertion import DeterministicAssertionProvider

from ugence_ai_hiring.domain_audit import HiringDomainAuditService, InMemoryHiringDomainAuditRepository
from ugence_ai_hiring.intake.intake import EvidenceProvenance, IntakeSource
from ugence_ai_hiring.recommendations import (
    ClaimAssertionEvaluator,
    DeterministicRecommendationGenerator,
)
from ugence_ai_hiring.repositories.product_repositories import (
    InMemoryApplicationRepository,
    InMemoryCandidateRepository,
    InMemoryEvidenceIntakeRepository,
    InMemoryJobDefinitionRepository,
    InMemoryRequisitionRepository,
)
from ugence_ai_hiring.repositories.recommendation_repositories import (
    InMemoryClaimAssertionBindingRepository,
    InMemoryClaimRepository,
    InMemoryEvidencePackageRepository,
    InMemoryRecommendationRepository,
    InMemoryReviewerDispositionRepository,
)
from ugence_ai_hiring.services._hiring_context import ActorContext
from ugence_ai_hiring.services.application_service import ApplicationService
from ugence_ai_hiring.services.candidate_service import CandidateService
from ugence_ai_hiring.services.evidence_intake_service import EvidenceIntakeService
from ugence_ai_hiring.services.recommendation_generation_service import RecommendationGenerationService
from ugence_ai_hiring.services.recommendation_reconstruction_service import (
    RecommendationReconstructionService,
)
from ugence_ai_hiring.services.requisition_service import RequisitionService
from ugence_ai_hiring.synthesis import EvidenceSynthesisService


def _ids():
    counters: dict[str, count] = {}

    def factory(prefix: str) -> str:
        return f"{prefix}_{next(counters.setdefault(prefix, count(1))):04d}"

    return factory


@dataclass
class H2Env:
    audit_repo: InMemoryHiringDomainAuditRepository
    audit: HiringDomainAuditService
    reqs: InMemoryRequisitionRepository
    defs: InMemoryJobDefinitionRepository
    cands: InMemoryCandidateRepository
    apps: InMemoryApplicationRepository
    intake: InMemoryEvidenceIntakeRepository
    packages: InMemoryEvidencePackageRepository
    recs: InMemoryRecommendationRepository
    claims: InMemoryClaimRepository
    bindings: InMemoryClaimAssertionBindingRepository
    dispositions: InMemoryReviewerDispositionRepository
    requisition_service: RequisitionService
    candidate_service: CandidateService
    application_service: ApplicationService
    intake_service: EvidenceIntakeService
    synthesis_service: EvidenceSynthesisService
    generation_service: RecommendationGenerationService
    reconstruction_service: RecommendationReconstructionService


def build_h2_env() -> H2Env:
    idf = _ids()
    ar = InMemoryHiringDomainAuditRepository()
    au = HiringDomainAuditService(ar, id_factory=idf)
    reqs, defs = InMemoryRequisitionRepository(), InMemoryJobDefinitionRepository()
    cands, apps = InMemoryCandidateRepository(), InMemoryApplicationRepository()
    intake = InMemoryEvidenceIntakeRepository()
    pkgs, recs = InMemoryEvidencePackageRepository(), InMemoryRecommendationRepository()
    claims = InMemoryClaimRepository()
    binds, disps = InMemoryClaimAssertionBindingRepository(), InMemoryReviewerDispositionRepository()
    return H2Env(
        audit_repo=ar, audit=au, reqs=reqs, defs=defs, cands=cands, apps=apps, intake=intake,
        packages=pkgs, recs=recs, claims=claims, bindings=binds, dispositions=disps,
        requisition_service=RequisitionService(requisitions=reqs, job_definitions=defs, audit=au, id_factory=idf),
        candidate_service=CandidateService(candidates=cands, audit=au, id_factory=idf),
        application_service=ApplicationService(applications=apps, requisitions=reqs, job_definitions=defs,
                                               candidates=cands, evidence_intake=intake, audit=au, id_factory=idf),
        intake_service=EvidenceIntakeService(evidence_intake=intake, applications=apps, audit=au, id_factory=idf),
        synthesis_service=EvidenceSynthesisService(applications=apps, job_definitions=defs,
                                                   evidence_intake=intake, packages=pkgs, audit=au, id_factory=idf),
        generation_service=RecommendationGenerationService(applications=apps, recommendations=recs, claims=claims,
                                                           bindings=binds, dispositions=disps, audit=au, id_factory=idf),
        reconstruction_service=RecommendationReconstructionService(recommendations=recs, claims=claims,
                                                                   bindings=binds, dispositions=disps, audit_repository=ar),
    )


def sysctx(tenant="t1", actor="ai-gen") -> ActorContext:
    return ActorContext(tenant_id=tenant, actor_id=actor, actor_type=ActorType.SYSTEM)


def humanctx(tenant="t1", actor="reviewer1") -> ActorContext:
    return ActorContext(tenant_id=tenant, actor_id=actor, actor_type=ActorType.HUMAN)


def provider(coverage=AssertionCoverage.SUPPORTED, *, timeout=False, malformed=False):
    return DeterministicAssertionProvider(coverage=coverage, timeout=timeout, malformed=malformed)


def evaluator(prov):
    return ClaimAssertionEvaluator(AssertionAssessmentIntegration(prov), provider_id=prov.descriptor().provider_id)


def generator(*, timeout=False, malformed=False):
    return DeterministicRecommendationGenerator(timeout=timeout, malformed=malformed)


def application_in_assessment(env: H2Env, c: ActorContext, *,
                              required=("resume", "code_sample"), provided=("resume", "code_sample")):
    """Drive an application to ASSESSMENT with the given evidence collected."""
    env.requisition_service.create_requisition(c, title="Eng", requisition_id="req1")
    env.requisition_service.open_requisition(c, "req1")
    env.requisition_service.draft_job_definition(
        c, requisition_id="req1", rubric_id="rb1", rubric_version=1,
        required_evidence_types=tuple(required), job_definition_id="jd1")
    env.requisition_service.publish_job_definition(c, "jd1")
    env.candidate_service.register_candidate(c, subject_id="subj1", candidate_id="c1")
    env.application_service.submit_application(
        c, candidate_id="c1", requisition_id="req1", job_definition_id="jd1", application_id="a1")
    env.application_service.start_screening(c, "a1")
    for i, et in enumerate(provided):
        env.intake_service.intake_evidence(
            c, application_id="a1", evidence_type=et, content_hash=f"hash_{et}",
            provenance=EvidenceProvenance(source=IntakeSource.CANDIDATE_SUBMISSION, collected_by="r"),
            intake_id=f"intk_{et}")
    # advance only if evidence complete; otherwise leave in SCREENING for the caller
    if set(required).issubset(set(provided)):
        env.application_service.advance_to_assessment(c, "a1")
