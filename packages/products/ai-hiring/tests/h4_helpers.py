"""Shared harness for H4 action/execution/reconciliation tests."""

from __future__ import annotations

from dataclasses import dataclass

from ugence_governance_provider_framework.reference.action import DeterministicActionGovernanceProvider

from ugence_ai_hiring.actions.action_types import HiringActionType
from ugence_ai_hiring.actions.actiongate_integration import ActionAuthorizationIntegration
from ugence_ai_hiring.actions.execution_port import DeterministicHiringExecutionAdapter
from ugence_ai_hiring.actions.read_models import ActionReadModelService
from ugence_ai_hiring.governance.outcomes import HiringDecisionIntent
from ugence_ai_hiring.repositories.action_repositories import (
    InMemoryActionAuthorizationRepository,
    InMemoryCompensationRepository,
    InMemoryExecutionAttemptRepository,
    InMemoryHiringActionProposalRepository,
    InMemoryReconciliationRepository,
)
from ugence_ai_hiring.services.hiring_action_authorization_service import HiringActionAuthorizationService
from ugence_ai_hiring.services.hiring_action_execution_service import HiringActionExecutionService
from ugence_ai_hiring.services.hiring_action_proposal_service import HiringActionProposalService
from ugence_ai_hiring.services.hiring_action_reconstruction_service import HiringActionReconstructionService
from ugence_ai_hiring.services.hiring_compensation_service import HiringCompensationService
from ugence_ai_hiring.services.hiring_reconciliation_service import HiringReconciliationService
from .h3_helpers import ai_ctx, build_h3_env, human_ctx, ready_recommendation


@dataclass
class H4Env:
    h3: object
    proposals: InMemoryHiringActionProposalRepository
    authorizations: InMemoryActionAuthorizationRepository
    attempts: InMemoryExecutionAttemptRepository
    reconciliations: InMemoryReconciliationRepository
    compensations: InMemoryCompensationRepository
    proposal_service: HiringActionProposalService
    authorization_service: HiringActionAuthorizationService
    execution_service: HiringActionExecutionService
    reconciliation_service: HiringReconciliationService
    compensation_service: HiringCompensationService
    reconstruction_service: HiringActionReconstructionService
    read_models: ActionReadModelService


def build_h4_env(*, max_retries: int = 2) -> H4Env:
    env = build_h3_env()
    h2 = env.h2
    idf = h2.audit._new_id
    proposals = InMemoryHiringActionProposalRepository()
    auths = InMemoryActionAuthorizationRepository()
    attempts = InMemoryExecutionAttemptRepository()
    recons = InMemoryReconciliationRepository()
    comps = InMemoryCompensationRepository()
    return H4Env(
        h3=env, proposals=proposals, authorizations=auths, attempts=attempts,
        reconciliations=recons, compensations=comps,
        proposal_service=HiringActionProposalService(
            recommendations=h2.recs, bindings=env.bindings, applications=h2.apps, proposals=proposals,
            case_decisions=env.case_decs, audit=h2.audit, id_factory=idf),
        authorization_service=HiringActionAuthorizationService(
            proposals=proposals, authorizations=auths, audit=h2.audit, id_factory=idf),
        execution_service=HiringActionExecutionService(
            proposals=proposals, authorizations=auths, attempts=attempts, audit=h2.audit,
            id_factory=idf, max_retries=max_retries),
        reconciliation_service=HiringReconciliationService(
            proposals=proposals, authorizations=auths, attempts=attempts, reconciliations=recons,
            audit=h2.audit, id_factory=idf),
        compensation_service=HiringCompensationService(
            proposals=proposals, compensations=comps, audit=h2.audit, id_factory=idf),
        reconstruction_service=HiringActionReconstructionService(
            proposals=proposals, recommendations=h2.recs, claims=h2.claims, provider_bindings=h2.bindings,
            governance_bindings=env.bindings, case_decisions=env.case_decs, authorizations=auths,
            attempts=attempts, reconciliations=recons, compensations=comps,
            hiring_audit_repository=h2.audit_repo, kernel_audit_repository=env.kernel_audit_repo),
        read_models=ActionReadModelService(
            proposals=proposals, authorizations=auths, attempts=attempts, reconciliations=recons,
            compensations=comps))


def decided_recommendation(env: H4Env, *, intent=HiringDecisionIntent.ADVANCE):
    """Open a governance case for a READY recommendation and record a human decision."""
    g = env.h3
    rec = ready_recommendation(g)
    g.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    g.governance.record_human_decision(human_ctx(), recommendation_id=rec.recommendation_id, intent=intent)
    return rec


def action_integration(**flags):
    return ActionAuthorizationIntegration(DeterministicActionGovernanceProvider(**flags))


def exec_adapter(**flags):
    return DeterministicHiringExecutionAdapter(**flags)


def propose_and_authorize(env: H4Env, rec, *, action_type=HiringActionType.ADVANCE_STAGE,
                          parameters=(("stage", "onsite"),), integration=None, ctx=None):
    ctx = ctx or ai_ctx()
    prop = env.proposal_service.propose(ctx, recommendation_id=rec.recommendation_id,
                                        action_type=action_type, target_system="ats",
                                        parameters=parameters)
    env.proposal_service.mark_ready(ctx, prop.action_proposal_id)
    auth = env.authorization_service.authorize(
        ctx, proposal_id=prop.action_proposal_id, integration=integration or action_integration())
    return prop, auth
