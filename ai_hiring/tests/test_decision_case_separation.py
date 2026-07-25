"""Four-record separation: assessment, recommendation, decision stay distinct."""

from __future__ import annotations

from ai_hiring.decision_cases import (
    AuthorityContext,
    AuthorityType,
    DecisionOutcome,
    GeneratorType,
    ProposedOutcome,
    RecommendationStatus,
    VersionedRef,
)
from ai_hiring.ontology.taxonomy import ReasonCode

from .conftest import (
    ASSESSOR,
    AI_ACTOR,
    DECISION_MAKER,
    SUBJECT,
    TENANT,
    finalized_assessment,
)

_HUMAN_AUTH = AuthorityContext(
    authority_id=DECISION_MAKER, authority_type=AuthorityType.HUMAN_APPROVER,
    decision_scope="hire")


def _linked_case(platform):
    assessment = finalized_assessment(platform)
    case = platform.decision_case_service.create_case(
        tenant_id=TENANT, decision_type="hire", subject_ids=(SUBJECT,),
        created_by=ASSESSOR)
    platform.decision_case_service.link_assessment(
        case_id=case.decision_case_id, assessment_id=assessment.assessment_id,
        version=assessment.version, actor=ASSESSOR)
    return case, assessment


def _rec(platform, case, assessment, *, outcome=ProposedOutcome.ADVANCE, by=ASSESSOR,
         gen=GeneratorType.HUMAN):
    return platform.case_recommendation_service.submit_recommendation(
        case_id=case.decision_case_id, recommendation_type="screen",
        proposed_outcome=outcome, generated_by=by, generator_type=gen,
        assessment_refs=(VersionedRef(ref_id=assessment.assessment_id,
                                      version=assessment.version, kind="assessment"),),
        reason_codes=(ReasonCode.NOT_APPLICABLE,),
        model_provenance="m@1" if gen is GeneratorType.AI_ASSISTED else None)


def test_assessment_record_has_no_recommendation_or_decision(case_platform):
    _, assessment = _linked_case(case_platform)
    fields = set(type(assessment).model_fields.keys())
    assert "recommendation" not in fields and "recommendation_id" not in fields
    assert "decision" not in fields and "outcome" not in fields


def test_recommendation_does_not_bind_the_case(case_platform):
    case, assessment = _linked_case(case_platform)
    rec = _rec(case_platform, case, assessment)
    # The recommendation is advisory and does not create a decision.
    assert rec.advisory_only is True
    assert case_platform.case_decision_service.list_decisions(
        case.decision_case_id) == ()


def test_multiple_and_conflicting_recommendations_coexist(case_platform):
    case, assessment = _linked_case(case_platform)
    r1 = _rec(case_platform, case, assessment, outcome=ProposedOutcome.ADVANCE)
    r2 = _rec(case_platform, case, assessment, outcome=ProposedOutcome.REJECT)
    recs = case_platform.case_recommendation_service.list_recommendations(
        case.decision_case_id)
    ids = {r.recommendation_id for r in recs}
    assert {r1.recommendation_id, r2.recommendation_id} <= ids
    outcomes = {r.proposed_outcome for r in recs}
    assert {ProposedOutcome.ADVANCE, ProposedOutcome.REJECT} <= outcomes


def test_rejected_recommendation_remains_visible(case_platform):
    case, assessment = _linked_case(case_platform)
    rec = _rec(case_platform, case, assessment)
    rejected = case_platform.case_recommendation_service.reject_recommendation(
        case_id=case.decision_case_id, recommendation_id=rec.recommendation_id,
        actor=DECISION_MAKER, reason_codes=(ReasonCode.CONFLICTING_EVIDENCE,))
    assert rejected.status is RecommendationStatus.REJECTED
    # The original proposed record is not deleted.
    original = case_platform.case_recommendation_service.get_recommendation(
        rec.recommendation_id)
    assert original.status is RecommendationStatus.PROPOSED
    all_recs = case_platform.case_recommendation_service.list_recommendations(
        case.decision_case_id)
    assert len(all_recs) == 2


def test_decision_record_has_no_execution_state(case_platform):
    case, assessment = _linked_case(case_platform)
    decision = case_platform.case_decision_service.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=_HUMAN_AUTH, decided_by=DECISION_MAKER,
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    fields = set(type(decision).model_fields.keys())
    assert {"execution", "executed", "cer", "actiongate"}.isdisjoint(fields)


def test_ai_assisted_recommendation_then_human_decision(case_platform):
    """AI may advise; a human decides. The two records are distinct."""
    case, assessment = _linked_case(case_platform)
    rec = _rec(case_platform, case, assessment, by=AI_ACTOR,
               gen=GeneratorType.AI_ASSISTED)
    assert rec.generator_type is GeneratorType.AI_ASSISTED
    decision = case_platform.case_decision_service.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=_HUMAN_AUTH, decided_by=DECISION_MAKER,
        reason_codes=(ReasonCode.NOT_APPLICABLE,),
        recommendation_refs=(VersionedRef(ref_id=rec.recommendation_id, version=1,
                                          kind="recommendation"),))
    assert decision.decided_by == DECISION_MAKER
    assert decision.authority_type is AuthorityType.HUMAN_APPROVER
    # decision references the recommendation but is a separate record
    assert decision.decision_id != rec.recommendation_id
