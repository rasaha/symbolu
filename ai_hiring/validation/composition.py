"""Validation composition root (H5) — application-local, validation-only.

Wires the full H1–H4 hiring lifecycle (hiring services + the frozen kernel decision
services + reference providers) into a single in-memory environment for end-to-end
validation. No production adapters, no new architecture — this only *assembles* the
already-shipped, frozen-API-consuming services for testing and the shadow pilot.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count

from decision_governance.api.audit import AuditService
from decision_governance.api.identity import ActorType, StaticIdentityProvider
from decision_governance.api.policy import AccessGrant, EvidenceAccessPolicy, GrantStore, Permission
from decision_governance.api.repositories import InMemoryAuditRepository, InMemoryDecisionCaseRepository
from decision_governance.api.services import (
    CaseDecisionService,
    CaseRecommendationService,
    CaseValidationService,
    DecisionCaseService,
)

from ..domain_audit import HiringDomainAuditService, InMemoryHiringDomainAuditRepository
from ..governance.linked_record import HiringRecommendationLinkedRecordAdapter
from ..governance.reconstruction import GovernanceCaseReconstructionService
from ..repositories.action_repositories import (
    InMemoryActionAuthorizationRepository,
    InMemoryCompensationRepository,
    InMemoryExecutionAttemptRepository,
    InMemoryHiringActionProposalRepository,
    InMemoryReconciliationRepository,
)
from ..repositories.governance_repositories import InMemoryGovernanceCaseBindingRepository
from ..repositories.product_repositories import (
    InMemoryApplicationRepository,
    InMemoryCandidateRepository,
    InMemoryEvidenceIntakeRepository,
    InMemoryJobDefinitionRepository,
    InMemoryRequisitionRepository,
)
from ..repositories.recommendation_repositories import (
    InMemoryClaimAssertionBindingRepository,
    InMemoryClaimRepository,
    InMemoryEvidencePackageRepository,
    InMemoryRecommendationRepository,
    InMemoryReviewerDispositionRepository,
)
from ..services._hiring_context import ActorContext
from ..services.application_service import ApplicationService
from ..services.candidate_service import CandidateService
from ..services.evidence_intake_service import EvidenceIntakeService
from ..services.governance_integration_service import GovernanceIntegrationService
from ..services.hiring_action_authorization_service import HiringActionAuthorizationService
from ..services.hiring_action_execution_service import HiringActionExecutionService
from ..services.hiring_action_proposal_service import HiringActionProposalService
from ..services.hiring_action_reconstruction_service import HiringActionReconstructionService
from ..services.hiring_compensation_service import HiringCompensationService
from ..services.hiring_reconciliation_service import HiringReconciliationService
from ..services.recommendation_generation_service import RecommendationGenerationService
from ..services.requisition_service import RequisitionService
from ..synthesis import EvidenceSynthesisService

AI_ID = "ai-gen"
HUMAN_ID = "reviewer1"


def _ids():
    counters: dict[str, count] = {}

    def factory(prefix: str) -> str:
        return f"{prefix}_{next(counters.setdefault(prefix, count(1))):06d}"

    return factory


@dataclass
class ValidationEnv:
    tenant: str
    audit_repo: InMemoryHiringDomainAuditRepository
    audit: HiringDomainAuditService
    kernel_audit_repo: InMemoryAuditRepository
    # repositories
    reqs: InMemoryRequisitionRepository
    defs: InMemoryJobDefinitionRepository
    cands: InMemoryCandidateRepository
    apps: InMemoryApplicationRepository
    intake: InMemoryEvidenceIntakeRepository
    packages: InMemoryEvidencePackageRepository
    recs: InMemoryRecommendationRepository
    claims: InMemoryClaimRepository
    provider_bindings: InMemoryClaimAssertionBindingRepository
    dispositions: InMemoryReviewerDispositionRepository
    gbindings: InMemoryGovernanceCaseBindingRepository
    proposals: InMemoryHiringActionProposalRepository
    authorizations: InMemoryActionAuthorizationRepository
    attempts: InMemoryExecutionAttemptRepository
    reconciliations: InMemoryReconciliationRepository
    compensations: InMemoryCompensationRepository
    # services
    requisition_service: RequisitionService
    candidate_service: CandidateService
    application_service: ApplicationService
    intake_service: EvidenceIntakeService
    synthesis_service: EvidenceSynthesisService
    generation_service: RecommendationGenerationService
    governance: GovernanceIntegrationService
    proposal_service: HiringActionProposalService
    authorization_service: HiringActionAuthorizationService
    execution_service: HiringActionExecutionService
    reconciliation_service: HiringReconciliationService
    compensation_service: HiringCompensationService
    action_reconstruction: HiringActionReconstructionService
    governance_reconstruction: GovernanceCaseReconstructionService
    # kernel
    cases: DecisionCaseService
    case_recs: CaseRecommendationService
    case_decs: CaseDecisionService
    identity: StaticIdentityProvider
    grants: GrantStore

    def ai(self, actor=AI_ID) -> ActorContext:
        return ActorContext(tenant_id=self.tenant, actor_id=actor, actor_type=ActorType.SYSTEM)

    def human(self, actor=HUMAN_ID) -> ActorContext:
        return ActorContext(tenant_id=self.tenant, actor_id=actor, actor_type=ActorType.HUMAN)


def build_validation_env(*, tenant: str = "t1", max_retries: int = 2,
                         extra_humans: tuple[str, ...] = ()) -> ValidationEnv:
    idf = _ids()
    ar = InMemoryHiringDomainAuditRepository()
    au = HiringDomainAuditService(ar, id_factory=idf)
    reqs, defs = InMemoryRequisitionRepository(), InMemoryJobDefinitionRepository()
    cands, apps = InMemoryCandidateRepository(), InMemoryApplicationRepository()
    intake = InMemoryEvidenceIntakeRepository()
    pkgs, recs = InMemoryEvidencePackageRepository(), InMemoryRecommendationRepository()
    claims = InMemoryClaimRepository()
    pbinds, disps = InMemoryClaimAssertionBindingRepository(), InMemoryReviewerDispositionRepository()
    gbindings = InMemoryGovernanceCaseBindingRepository()
    proposals = InMemoryHiringActionProposalRepository()
    auths, attempts = InMemoryActionAuthorizationRepository(), InMemoryExecutionAttemptRepository()
    recons, comps = InMemoryReconciliationRepository(), InMemoryCompensationRepository()

    identity = StaticIdentityProvider()
    identity.register_ai(AI_ID)
    identity.register_human(HUMAN_ID)
    grants = GrantStore()
    ai_perms = frozenset(Permission) - {Permission.MAKE_DECISION, Permission.OVERRIDE_RECOMMENDATION}
    grants.add(AccessGrant(AI_ID, tenant, ai_perms))
    grants.add(AccessGrant(HUMAN_ID, tenant, frozenset(Permission)))
    for h in extra_humans:
        identity.register_human(h)
        grants.add(AccessGrant(h, tenant, frozenset(Permission)))
    policy = EvidenceAccessPolicy(grants)
    kaudit_repo = InMemoryAuditRepository()
    kaudit = AuditService(kaudit_repo)
    case_repo = InMemoryDecisionCaseRepository()
    val = CaseValidationService(HiringRecommendationLinkedRecordAdapter(recs))
    cases = DecisionCaseService(case_repo, val, kaudit, identity, policy)
    case_recs = CaseRecommendationService(case_repo, val, kaudit, identity, policy)
    case_decs = CaseDecisionService(case_repo, val, kaudit, identity, policy)

    return ValidationEnv(
        tenant=tenant, audit_repo=ar, audit=au, kernel_audit_repo=kaudit_repo,
        reqs=reqs, defs=defs, cands=cands, apps=apps, intake=intake, packages=pkgs, recs=recs,
        claims=claims, provider_bindings=pbinds, dispositions=disps, gbindings=gbindings,
        proposals=proposals, authorizations=auths, attempts=attempts, reconciliations=recons,
        compensations=comps,
        requisition_service=RequisitionService(requisitions=reqs, job_definitions=defs, audit=au, id_factory=idf),
        candidate_service=CandidateService(candidates=cands, audit=au, id_factory=idf),
        application_service=ApplicationService(applications=apps, requisitions=reqs, job_definitions=defs,
                                               candidates=cands, evidence_intake=intake, audit=au, id_factory=idf),
        intake_service=EvidenceIntakeService(evidence_intake=intake, applications=apps, audit=au, id_factory=idf),
        synthesis_service=EvidenceSynthesisService(applications=apps, job_definitions=defs,
                                                   evidence_intake=intake, packages=pkgs, audit=au, id_factory=idf),
        generation_service=RecommendationGenerationService(applications=apps, recommendations=recs, claims=claims,
                                                           bindings=pbinds, dispositions=disps, audit=au, id_factory=idf),
        governance=GovernanceIntegrationService(recommendations=recs, bindings=gbindings, cases=cases,
                                                case_recommendations=case_recs, case_decisions=case_decs,
                                                audit=au, id_factory=idf),
        proposal_service=HiringActionProposalService(recommendations=recs, bindings=gbindings, applications=apps,
                                                     proposals=proposals, case_decisions=case_decs, audit=au, id_factory=idf),
        authorization_service=HiringActionAuthorizationService(proposals=proposals, authorizations=auths,
                                                               audit=au, id_factory=idf),
        execution_service=HiringActionExecutionService(proposals=proposals, authorizations=auths, attempts=attempts,
                                                       audit=au, id_factory=idf, max_retries=max_retries),
        reconciliation_service=HiringReconciliationService(proposals=proposals, authorizations=auths, attempts=attempts,
                                                           reconciliations=recons, audit=au, id_factory=idf),
        compensation_service=HiringCompensationService(proposals=proposals, compensations=comps, audit=au, id_factory=idf),
        action_reconstruction=HiringActionReconstructionService(
            proposals=proposals, recommendations=recs, claims=claims, provider_bindings=pbinds,
            governance_bindings=gbindings, case_decisions=case_decs, authorizations=auths, attempts=attempts,
            reconciliations=recons, compensations=comps, hiring_audit_repository=ar, kernel_audit_repository=kaudit_repo),
        governance_reconstruction=GovernanceCaseReconstructionService(
            recommendations=recs, claims=claims, provider_bindings=pbinds, bindings=gbindings, cases=cases,
            case_recommendations=case_recs, case_decisions=case_decs, hiring_audit_repository=ar,
            kernel_audit_repository=kaudit_repo),
        cases=cases, case_recs=case_recs, case_decs=case_decs, identity=identity, grants=grants)
