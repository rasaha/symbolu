"""H2 — human review + reviewer authority tests."""

from __future__ import annotations

import pytest
from ugence_governance_provider_framework.contracts import AssertionCoverage

from ugence_ai_hiring.errors import RecommendationGenerationError, ReviewerAuthorityError
from ugence_ai_hiring.recommendations import RecommendationStatus, ReviewerAction
from ugence_ai_hiring.recommendations.claim import AssertionOutcome
from .h2_helpers import (
    application_in_assessment,
    build_h2_env,
    evaluator,
    generator,
    humanctx,
    provider,
    sysctx,
)


def _ready_rec(env, c):
    application_in_assessment(env, c)
    pkg = env.synthesis_service.synthesize(c, application_id="a1", rubric_version=1)
    return env.generation_service.generate(
        c, application_id="a1", package=pkg, generator=generator(),
        evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)))


def test_human_reviewer_can_reject():
    env = build_h2_env(); c = sysctx(); h = humanctx()
    rec = _ready_rec(env, c)
    env.generation_service.submit_for_review(c, rec.recommendation_id)
    env.generation_service.record_disposition(
        h, recommendation_id=rec.recommendation_id, action=ReviewerAction.REJECT_RECOMMENDATION,
        comment="not convincing")
    assert env.recs.get(rec.recommendation_id).status == RecommendationStatus.REJECTED_BY_REVIEW
    kinds = [e.event_type.value for e in env.audit_repo.events_for("recommendation", rec.recommendation_id)]
    assert "RECOMMENDATION_REJECTED_BY_REVIEWER" in kinds


def test_ai_or_system_cannot_dispose_recommendation():
    env = build_h2_env(); c = sysctx()
    rec = _ready_rec(env, c)
    with pytest.raises(ReviewerAuthorityError):
        env.generation_service.record_disposition(
            c, recommendation_id=rec.recommendation_id, action=ReviewerAction.ACCEPT_FOR_CONSIDERATION)
    # denial recorded
    denials = [e for e in env.audit_repo.events_for("recommendation", rec.recommendation_id)
               if e.event_type.value == "DOMAIN_ACCESS_DENIED"]
    assert denials


def test_accept_for_consideration_is_advisory_not_a_decision():
    env = build_h2_env(); c = sysctx(); h = humanctx()
    rec = _ready_rec(env, c)
    env.generation_service.record_disposition(
        h, recommendation_id=rec.recommendation_id, action=ReviewerAction.ACCEPT_FOR_CONSIDERATION)
    # status remains advisory-review; no binding hire/accept state exists
    after = env.recs.get(rec.recommendation_id)
    assert after.status == RecommendationStatus.READY_FOR_HUMAN_REVIEW
    assert after.advisory is True


def test_review_package_lists_claims_evidence_and_actions():
    env = build_h2_env(); c = sysctx(); h = humanctx()
    rec = _ready_rec(env, c)
    view = env.generation_service.build_review_package(h, rec.recommendation_id)
    assert view.claims and all(cl.assertion_outcome for cl in view.claims)
    assert view.available_reviewer_actions
    assert view.advisory is True
    assert view.version_history == (1,)


def test_conflicting_evidence_requires_review():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c, required=("resume", "code_sample"))
    pkg = env.synthesis_service.synthesize(
        c, application_id="a1", rubric_version=1, adverse_refs=("intk_code_sample",))
    rec = env.generation_service.generate(
        c, application_id="a1", package=pkg, generator=generator(),
        evaluator=evaluator(provider(AssertionCoverage.UNSUPPORTED)))
    assert rec.status == RecommendationStatus.ASSERTION_REVIEW_REQUIRED
    claims = env.claims.claims_for(rec.recommendation_id, 1)
    assert any(cl.assertion_outcome == AssertionOutcome.CONFLICTING for cl in claims)


def test_submit_for_review_requires_ready_status():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    pkg = env.synthesis_service.synthesize(c, application_id="a1", rubric_version=1)
    rec = env.generation_service.generate(
        c, application_id="a1", package=pkg, generator=generator(),
        evaluator=evaluator(provider(AssertionCoverage.UNSUPPORTED)))  # ASSERTION_REVIEW_REQUIRED
    with pytest.raises(RecommendationGenerationError):
        env.generation_service.submit_for_review(c, rec.recommendation_id)
