"""H3 — governance integration: case binding, human decision, override, supersede."""

from __future__ import annotations

import pytest
from ugence_governance_provider_framework.contracts import AssertionCoverage

from ugence_ai_hiring.errors import (
    CrossTenantHiringAccessError,
    RecommendationGenerationError,
    ReviewerAuthorityError,
)
from ugence_ai_hiring.governance.binding import GovernanceBindingStatus
from ugence_ai_hiring.governance.outcomes import HiringDecisionIntent
from .h3_helpers import ai_ctx, build_h3_env, human_ctx, ready_recommendation


def test_open_case_binds_recommendation_to_dgm_case():
    env = build_h3_env()
    rec = ready_recommendation(env)
    binding = env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    assert binding.status == GovernanceBindingStatus.OPEN
    assert binding.decision_case_id and binding.kernel_recommendation_id
    # a kernel case + recommendation now exist
    case = env.cases.get_case(binding.decision_case_id)
    assert case.tenant_id == "t1"
    recs = env.case_recs.list_recommendations(binding.decision_case_id)
    assert len(recs) == 1


def test_open_case_is_duplicate_safe():
    env = build_h3_env()
    rec = ready_recommendation(env)
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    with pytest.raises(RecommendationGenerationError):
        env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)


def test_open_case_requires_review_bound_recommendation():
    env = build_h3_env()
    # EVIDENCE_INCOMPLETE recommendation is not review-bound
    from ugence_ai_hiring.synthesis import MinimizationPolicy
    from .h2_helpers import application_in_assessment, evaluator, generator, provider
    gen = ai_ctx()
    application_in_assessment(env.h2, gen)
    pkg = env.h2.synthesis_service.synthesize(
        gen, application_id="a1", rubric_version=1,
        policy=MinimizationPolicy(quarantined_hashes=("hash_code_sample",)))
    rec = env.h2.generation_service.generate(
        gen, application_id="a1", package=pkg, generator=generator(),
        evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)))
    assert rec.status.value == "EVIDENCE_INCOMPLETE"
    with pytest.raises(RecommendationGenerationError):
        env.governance.open_case(gen, recommendation_id=rec.recommendation_id)


def test_human_decision_recorded_and_binding_updated():
    env = build_h3_env()
    rec = ready_recommendation(env)
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    decision = env.governance.record_human_decision(
        human_ctx(), recommendation_id=rec.recommendation_id, intent=HiringDecisionIntent.ADVANCE)
    assert decision.outcome.value == "ADVANCE"
    assert decision.authority_type.value == "HUMAN_APPROVER"
    binding = env.bindings.for_recommendation(rec.recommendation_id)
    assert binding.status == GovernanceBindingStatus.DECIDED and binding.decision_id


def test_ai_or_system_cannot_record_decision():
    env = build_h3_env()
    rec = ready_recommendation(env)
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    with pytest.raises(ReviewerAuthorityError):
        env.governance.record_human_decision(
            ai_ctx(), recommendation_id=rec.recommendation_id, intent=HiringDecisionIntent.ADVANCE)
    denials = [e for e in env.h2.audit_repo.events_for("recommendation", rec.recommendation_id)
               if e.event_type.value == "DOMAIN_ACCESS_DENIED"]
    assert denials


def test_decision_diverging_from_recommendation_records_override():
    env = build_h3_env()
    rec = ready_recommendation(env)  # proposes ADVANCE
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    decision = env.governance.record_human_decision(
        human_ctx(), recommendation_id=rec.recommendation_id, intent=HiringDecisionIntent.REJECT,
        override_notes="panel disagreed")
    assert decision.override_record_id
    overrides = env.case_decs.list_overrides(
        env.bindings.for_recommendation(rec.recommendation_id).decision_case_id)
    assert overrides
    kinds = [e.event_type.value for e in env.h2.audit_repo.events_for("recommendation", rec.recommendation_id)]
    assert "GOVERNANCE_DECISION_OVERRIDE_RECORDED" in kinds


def test_human_can_reject_recommendation():
    env = build_h3_env()
    rec = ready_recommendation(env)
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    env.governance.reject_recommendation(human_ctx(), recommendation_id=rec.recommendation_id)
    assert env.bindings.for_recommendation(rec.recommendation_id).status == GovernanceBindingStatus.REJECTED


def test_supersede_case_after_decision():
    env = build_h3_env()
    rec = ready_recommendation(env)
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    env.governance.record_human_decision(
        human_ctx(), recommendation_id=rec.recommendation_id, intent=HiringDecisionIntent.HOLD)
    updated = env.governance.supersede_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    assert updated.status == GovernanceBindingStatus.SUPERSEDED
    # the kernel reopens a DECIDED case for a superseding revision (append-only history)
    assert len(env.cases.get_case_history(updated.decision_case_id)) >= 2


def test_supersede_undecided_case_cancels_it():
    env = build_h3_env()
    rec = ready_recommendation(env)
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    updated = env.governance.supersede_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    assert updated.status == GovernanceBindingStatus.SUPERSEDED
    assert env.cases.get_case(updated.decision_case_id).status.value == "CANCELLED"


def test_assign_and_complete_review():
    env = build_h3_env()
    rec = ready_recommendation(env)
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    task = env.governance.assign_review(ai_ctx(), recommendation_id=rec.recommendation_id,
                                        assigned_to="reviewer1")
    completed = env.governance.complete_review(human_ctx(), recommendation_id=rec.recommendation_id,
                                               task_id=task.task_id)
    assert completed.status.value == "COMPLETED"


def test_tenant_isolation_on_open_and_decision():
    env = build_h3_env()
    rec = ready_recommendation(env)  # tenant t1
    env.governance.open_case(ai_ctx(), recommendation_id=rec.recommendation_id)
    with pytest.raises(CrossTenantHiringAccessError):
        env.governance.record_human_decision(
            human_ctx(tenant="t2", actor="human-t2"), recommendation_id=rec.recommendation_id,
            intent=HiringDecisionIntent.ADVANCE)


def test_governance_service_exposes_no_action_or_execution_method():
    """Invariant: Recommendation -> Human Decision -> (H4) Action. No action here."""
    from ugence_ai_hiring.services.governance_integration_service import GovernanceIntegrationService
    banned = {"authorize", "execute", "dispatch", "create_action", "create_action_request",
              "offer", "reconcile", "actiongate"}
    methods = {m for m in dir(GovernanceIntegrationService) if not m.startswith("_")}
    assert not (methods & banned), methods & banned
