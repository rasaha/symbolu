"""H2 — recommendation generation + TAP evaluation tests."""

from __future__ import annotations

import pytest
from governance_providers.contracts import AssertionCoverage

from ai_hiring.errors import (
    CrossTenantHiringAccessError,
    GeneratorOutputInvalidError,
    RecommendationGenerationError,
)
from ai_hiring.recommendations import RecommendationStatus
from ai_hiring.recommendations.claim import AssertionOutcome
from ai_hiring.tests.h2_helpers import (
    application_in_assessment,
    build_h2_env,
    evaluator,
    generator,
    provider,
    sysctx,
)


def _synth(env, c):
    return env.synthesis_service.synthesize(c, application_id="a1", rubric_version=1)


def test_supported_recommendation_is_review_ready():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    pkg = _synth(env, c)
    rec = env.generation_service.generate(
        c, application_id="a1", package=pkg, generator=generator(),
        evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)))
    assert rec.status == RecommendationStatus.READY_FOR_HUMAN_REVIEW
    assert rec.advisory is True
    # every material claim evaluated as supported
    claims = env.claims.claims_for(rec.recommendation_id, 1)
    assert claims and all(cl.assertion_outcome == AssertionOutcome.SUPPORTED for cl in claims)


def test_insufficient_evidence_is_not_review_ready():
    env = build_h2_env(); c = sysctx()
    # provide only resume; advance manually to ASSESSMENT via full evidence then drop? Instead
    # generate on a package with a missing required type.
    application_in_assessment(env, c, required=("resume", "code_sample"), provided=("resume", "code_sample"))
    # re-synthesize against a stricter (unmet) requirement by quarantining one type
    from ai_hiring.synthesis import MinimizationPolicy
    pkg = env.synthesis_service.synthesize(
        c, application_id="a1", rubric_version=1, policy=MinimizationPolicy(quarantined_hashes=("hash_code_sample",)))
    rec = env.generation_service.generate(
        c, application_id="a1", package=pkg, generator=generator(),
        evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)))
    assert rec.status == RecommendationStatus.EVIDENCE_INCOMPLETE
    assert "code_sample" in rec.evidence_gaps


def test_unsupported_material_claim_blocks_review_ready():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    pkg = _synth(env, c)
    rec = env.generation_service.generate(
        c, application_id="a1", package=pkg, generator=generator(),
        evaluator=evaluator(provider(AssertionCoverage.UNSUPPORTED)))
    assert rec.status == RecommendationStatus.ASSERTION_REVIEW_REQUIRED
    assert rec.unsupported_claim_ids


def test_indeterminate_claim_blocks_review_ready():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    pkg = _synth(env, c)
    rec = env.generation_service.generate(
        c, application_id="a1", package=pkg, generator=generator(),
        evaluator=evaluator(provider(AssertionCoverage.INDETERMINATE)))
    assert rec.status == RecommendationStatus.ASSERTION_REVIEW_REQUIRED


def test_tap_provider_failure_is_fail_safe():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    pkg = _synth(env, c)
    rec = env.generation_service.generate(
        c, application_id="a1", package=pkg, generator=generator(),
        evaluator=evaluator(provider(timeout=True)))  # provider raises
    assert rec.status == RecommendationStatus.ASSERTION_REVIEW_REQUIRED
    # binding recorded the provider error and did not pass
    bindings = env.bindings.bindings_for(rec.recommendation_id, 1)
    assert bindings and any(not b.evaluated for b in bindings)


def test_malformed_generator_output_raises_and_creates_no_recommendation():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    pkg = _synth(env, c)
    with pytest.raises(GeneratorOutputInvalidError):
        env.generation_service.generate(
            c, application_id="a1", package=pkg, generator=generator(malformed=True),
            evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)))
    assert env.recs.list_for_application("a1") == ()


def test_generator_timeout_records_failure_event():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    pkg = _synth(env, c)
    with pytest.raises(RecommendationGenerationError):
        env.generation_service.generate(
            c, application_id="a1", package=pkg, generator=generator(timeout=True),
            evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)))
    fails = [e for e in env.audit_repo.all_events()
             if e.event_type.value == "RECOMMENDATION_GENERATION_FAILED"]
    assert fails


def test_generation_requires_h2_eligible_application_state():
    env = build_h2_env(); c = sysctx()
    # incomplete evidence keeps the application in SCREENING (not H2-eligible)
    application_in_assessment(env, c, required=("resume", "code_sample"), provided=("resume",))
    pkg = env.synthesis_service.synthesize(c, application_id="a1", rubric_version=1)
    with pytest.raises(RecommendationGenerationError):
        env.generation_service.generate(
            c, application_id="a1", package=pkg, generator=generator(),
            evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)))


def test_duplicate_recommendation_generation_prevented():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    pkg = _synth(env, c)
    env.generation_service.generate(c, application_id="a1", package=pkg, generator=generator(),
                                    evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)))
    with pytest.raises(RecommendationGenerationError):
        env.generation_service.generate(c, application_id="a1", package=pkg, generator=generator(),
                                        evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)))


def test_recommendation_supersession():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    pkg = _synth(env, c)
    r1 = env.generation_service.generate(c, application_id="a1", package=pkg, generator=generator(),
                                         evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)))
    r2 = env.generation_service.generate(c, application_id="a1", package=pkg, generator=generator(),
                                         evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)),
                                         supersede_existing=True)
    prior_latest = env.recs.get(r1.recommendation_id)
    assert prior_latest.status == RecommendationStatus.SUPERSEDED
    assert prior_latest.superseded_by == r2.recommendation_id


def test_wrong_application_evidence_package_rejected():
    env = build_h2_env(); c = sysctx()
    application_in_assessment(env, c)
    pkg = _synth(env, c)
    # a second application in the same tenant
    env.candidate_service.register_candidate(c, subject_id="subj2", candidate_id="c2")
    env.application_service.submit_application(c, candidate_id="c2", requisition_id="req1",
                                               job_definition_id="jd1", application_id="a2")
    env.application_service.start_screening(c, "a2")
    with pytest.raises(RecommendationGenerationError):
        # package belongs to a1, not a2
        env.generation_service.generate(c, application_id="a2", package=pkg, generator=generator(),
                                        evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)))


def test_generation_tenant_isolation():
    env = build_h2_env()
    owner, intruder = sysctx(tenant="t1"), sysctx(tenant="t2")
    application_in_assessment(env, owner)
    pkg = env.synthesis_service.synthesize(owner, application_id="a1", rubric_version=1)
    with pytest.raises(CrossTenantHiringAccessError):
        env.generation_service.generate(intruder, application_id="a1", package=pkg, generator=generator(),
                                        evaluator=evaluator(provider(AssertionCoverage.SUPPORTED)))
