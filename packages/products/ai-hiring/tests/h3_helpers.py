"""Shared harness for H3 governance-integration tests (deterministic wiring)."""

from __future__ import annotations

from dataclasses import dataclass

from ugence_decision_authority.api.audit import AuditService
from ugence_decision_authority.api.identity import ActorType, StaticIdentityProvider
from ugence_decision_authority.api.policy import AccessGrant, EvidenceAccessPolicy, GrantStore, Permission
from ugence_decision_authority.api.repositories import InMemoryAuditRepository, InMemoryDecisionCaseRepository
from ugence_decision_authority.api.services import (
    CaseDecisionService,
    CaseRecommendationService,
    CaseValidationService,
    DecisionCaseService,
)
from ugence_governance_provider_framework.contracts import AssertionCoverage

from ugence_ai_hiring.governance.linked_record import HiringRecommendationLinkedRecordAdapter
from ugence_ai_hiring.governance.reconstruction import GovernanceCaseReconstructionService
from ugence_ai_hiring.governance.views import GovernanceViewService
from ugence_ai_hiring.repositories.governance_repositories import InMemoryGovernanceCaseBindingRepository
from ugence_ai_hiring.services._hiring_context import ActorContext
from ugence_ai_hiring.services.governance_integration_service import GovernanceIntegrationService
from .h2_helpers import (
    application_in_assessment,
    build_h2_env,
    evaluator,
    generator,
    provider,
)

AI_ID = "ai-gen"
HUMAN_ID = "reviewer1"


@dataclass
class H3Env:
    h2: object
    identity: StaticIdentityProvider
    grants: GrantStore
    kernel_audit_repo: InMemoryAuditRepository
    case_repo: InMemoryDecisionCaseRepository
    cases: DecisionCaseService
    case_recs: CaseRecommendationService
    case_decs: CaseDecisionService
    bindings: InMemoryGovernanceCaseBindingRepository
    governance: GovernanceIntegrationService
    reconstruction: GovernanceCaseReconstructionService
    views: GovernanceViewService


def build_h3_env(*, extra_human: str = "") -> H3Env:
    h2 = build_h2_env()
    identity = StaticIdentityProvider()
    identity.register_ai(AI_ID)
    identity.register_human(HUMAN_ID)
    grants = GrantStore()
    ai_perms = frozenset(Permission) - {Permission.MAKE_DECISION, Permission.OVERRIDE_RECOMMENDATION}
    grants.add(AccessGrant(AI_ID, "t1", ai_perms))
    grants.add(AccessGrant(HUMAN_ID, "t1", frozenset(Permission)))
    if extra_human:
        identity.register_human(extra_human)
        grants.add(AccessGrant(extra_human, "t1", frozenset(Permission)))
    # tenant t2 actors for isolation tests
    identity.register_ai("ai-t2"); identity.register_human("human-t2")
    grants.add(AccessGrant("ai-t2", "t2", ai_perms))
    grants.add(AccessGrant("human-t2", "t2", frozenset(Permission)))

    policy = EvidenceAccessPolicy(grants)
    kaudit_repo = InMemoryAuditRepository()
    kaudit = AuditService(kaudit_repo)
    case_repo = InMemoryDecisionCaseRepository()
    val = CaseValidationService(HiringRecommendationLinkedRecordAdapter(h2.recs))
    cases = DecisionCaseService(case_repo, val, kaudit, identity, policy)
    case_recs = CaseRecommendationService(case_repo, val, kaudit, identity, policy)
    case_decs = CaseDecisionService(case_repo, val, kaudit, identity, policy)
    bindings = InMemoryGovernanceCaseBindingRepository()
    governance = GovernanceIntegrationService(
        recommendations=h2.recs, bindings=bindings, cases=cases, case_recommendations=case_recs,
        case_decisions=case_decs, audit=h2.audit, id_factory=h2.audit._new_id)
    reconstruction = GovernanceCaseReconstructionService(
        recommendations=h2.recs, claims=h2.claims, provider_bindings=h2.bindings, bindings=bindings,
        cases=cases, case_recommendations=case_recs, case_decisions=case_decs,
        hiring_audit_repository=h2.audit_repo, kernel_audit_repository=kaudit_repo)
    views = GovernanceViewService(recommendations=h2.recs, claims=h2.claims, bindings=bindings,
                                  cases=cases, case_decisions=case_decs)
    return H3Env(h2=h2, identity=identity, grants=grants, kernel_audit_repo=kaudit_repo,
                 case_repo=case_repo, cases=cases, case_recs=case_recs, case_decs=case_decs,
                 bindings=bindings, governance=governance, reconstruction=reconstruction, views=views)


def ai_ctx(tenant="t1", actor=AI_ID) -> ActorContext:
    return ActorContext(tenant_id=tenant, actor_id=actor, actor_type=ActorType.SYSTEM)


def human_ctx(tenant="t1", actor=HUMAN_ID) -> ActorContext:
    return ActorContext(tenant_id=tenant, actor_id=actor, actor_type=ActorType.HUMAN)


def ready_recommendation(env: H3Env, *, coverage=AssertionCoverage.SUPPORTED,
                         tenant="t1", ai_actor=AI_ID):
    """Produce a READY (or review-required) H2 recommendation for governance binding."""
    h2 = env.h2
    gen = ai_ctx(tenant=tenant, actor=ai_actor)
    application_in_assessment(h2, gen)
    pkg = h2.synthesis_service.synthesize(gen, application_id="a1", rubric_version=1)
    return h2.generation_service.generate(
        gen, application_id="a1", package=pkg, generator=generator(),
        evaluator=evaluator(provider(coverage)))
