"""Case lifecycle orchestration: create → link → review → decide → supersede/close."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.decision_cases import (
    AuthorityContext,
    AuthorityType,
    CaseStatus,
    DecisionOutcome,
    ProposedOutcome,
    GeneratorType,
    ReviewTaskType,
    VersionedRef,
)
from ugence_ai_hiring.errors import (
    AssessmentNotLinkableError,
    CaseFinalizedError,
    InvalidCaseTransitionError,
)
from ugence_ai_hiring.ontology.taxonomy import ReasonCode

from .conftest import (
    ASSESSOR,
    DECISION_MAKER,
    REVIEWER,
    SUBJECT,
    TENANT,
    finalized_assessment,
)

_HUMAN_AUTH = AuthorityContext(
    authority_id=DECISION_MAKER, authority_type=AuthorityType.HUMAN_APPROVER,
    decision_scope="hire")


def _new_case(platform):
    return platform.decision_case_service.create_case(
        tenant_id=TENANT, decision_type="hire", subject_ids=(SUBJECT,),
        created_by=ASSESSOR)


def test_create_case_does_not_require_a_recommendation(case_platform):
    case = _new_case(case_platform)
    assert case.status is CaseStatus.CREATED
    assert case.recommendation_refs == ()


def test_link_finalized_assessment(case_platform):
    assessment = finalized_assessment(case_platform)
    case = _new_case(case_platform)
    linked = case_platform.decision_case_service.link_assessment(
        case_id=case.decision_case_id, assessment_id=assessment.assessment_id,
        version=assessment.version, actor=ASSESSOR)
    assert linked.status is CaseStatus.ASSESSMENT_IN_PROGRESS
    assert linked.assessment_refs[0].ref_id == assessment.assessment_id


def test_link_unknown_assessment_is_refused(case_platform):
    case = _new_case(case_platform)
    with pytest.raises(AssessmentNotLinkableError):
        case_platform.decision_case_service.link_assessment(
            case_id=case.decision_case_id, assessment_id="nope", version=1,
            actor=ASSESSOR)


def test_decision_without_recommendation_is_supported(case_platform):
    """A case may reach a decision with no recommendation and no AI involvement."""
    assessment = finalized_assessment(case_platform)
    case = _new_case(case_platform)
    case_platform.decision_case_service.link_assessment(
        case_id=case.decision_case_id, assessment_id=assessment.assessment_id,
        version=assessment.version, actor=ASSESSOR)
    decision = case_platform.case_decision_service.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=_HUMAN_AUTH, decided_by=DECISION_MAKER,
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    assert decision.outcome is DecisionOutcome.ADVANCE
    assert decision.recommendation_refs == ()
    assert case_platform.decision_case_service.get_case(
        case.decision_case_id).status is CaseStatus.DECIDED


def test_review_assignment_and_completion_gate_readiness(case_platform):
    assessment = finalized_assessment(case_platform)
    svc = case_platform.decision_case_service
    case = _new_case(case_platform)
    svc.link_assessment(case_id=case.decision_case_id,
                        assessment_id=assessment.assessment_id,
                        version=assessment.version, actor=ASSESSOR)
    task = svc.assign_review(
        case_id=case.decision_case_id, task_type=ReviewTaskType.REQUIRED_REVIEW,
        assigned_to=REVIEWER, actor=ASSESSOR)
    # Outstanding review blocks readiness.
    readiness = svc.validate_decision_readiness(case_id=case.decision_case_id, actor=ASSESSOR)
    assert readiness.ready is False
    assert task.task_id in readiness.required_reviews_outstanding
    # Completing it clears the blocker.
    svc.complete_review(case_id=case.decision_case_id, task_id=task.task_id, actor=REVIEWER)
    readiness = svc.validate_decision_readiness(case_id=case.decision_case_id, actor=ASSESSOR)
    assert readiness.ready is True


def test_decision_blocked_while_required_review_outstanding(case_platform):
    from ugence_ai_hiring.errors import DecisionReadinessError
    assessment = finalized_assessment(case_platform)
    svc = case_platform.decision_case_service
    case = _new_case(case_platform)
    svc.link_assessment(case_id=case.decision_case_id,
                        assessment_id=assessment.assessment_id,
                        version=assessment.version, actor=ASSESSOR)
    svc.assign_review(case_id=case.decision_case_id,
                      task_type=ReviewTaskType.SECONDARY_APPROVAL,
                      assigned_to=REVIEWER, actor=ASSESSOR)
    with pytest.raises(DecisionReadinessError):
        case_platform.case_decision_service.record_decision(
            case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
            authority=_HUMAN_AUTH, decided_by=DECISION_MAKER,
            reason_codes=(ReasonCode.NOT_APPLICABLE,))


def test_required_recommendation_policy_blocks_decision(case_platform):
    from ugence_ai_hiring.errors import DecisionReadinessError
    assessment = finalized_assessment(case_platform)
    case = case_platform.decision_case_service.create_case(
        tenant_id=TENANT, decision_type="hire", subject_ids=(SUBJECT,),
        created_by=ASSESSOR, require_recommendation=True)
    case_platform.decision_case_service.link_assessment(
        case_id=case.decision_case_id, assessment_id=assessment.assessment_id,
        version=assessment.version, actor=ASSESSOR)
    with pytest.raises(DecisionReadinessError):
        case_platform.case_decision_service.record_decision(
            case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
            authority=_HUMAN_AUTH, decided_by=DECISION_MAKER,
            reason_codes=(ReasonCode.NOT_APPLICABLE,))


def test_supersession_preserves_prior_snapshot(case_platform):
    assessment = finalized_assessment(case_platform)
    svc = case_platform.decision_case_service
    case = _new_case(case_platform)
    svc.link_assessment(case_id=case.decision_case_id,
                        assessment_id=assessment.assessment_id,
                        version=assessment.version, actor=ASSESSOR)
    case_platform.case_decision_service.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=_HUMAN_AUTH, decided_by=DECISION_MAKER,
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    reopened = svc.supersede_case(case_id=case.decision_case_id, actor=DECISION_MAKER)
    assert reopened.status is CaseStatus.READY_FOR_DECISION
    history = svc.get_case_history(case.decision_case_id)
    statuses = [c.status for c in history]
    assert CaseStatus.DECIDED in statuses
    assert CaseStatus.SUPERSEDED in statuses  # prior snapshot preserved
    assert all(history[i].version < history[i + 1].version
               for i in range(len(history) - 1))


def test_cancel_preserves_history_and_freezes_case(case_platform):
    case = _new_case(case_platform)
    cancelled = case_platform.decision_case_service.cancel_case(
        case_id=case.decision_case_id, actor=DECISION_MAKER)
    assert cancelled.status is CaseStatus.CANCELLED
    with pytest.raises(CaseFinalizedError):
        case_platform.decision_case_service.link_assessment(
            case_id=case.decision_case_id, assessment_id="x", version=1, actor=ASSESSOR)


def test_illegal_transition_is_refused(case_platform):
    case = _new_case(case_platform)
    # CREATED cannot jump straight to CLOSED.
    with pytest.raises(InvalidCaseTransitionError):
        case_platform.decision_case_service.close_case(
            case_id=case.decision_case_id, actor=DECISION_MAKER)


def test_decision_on_closed_case_is_refused(case_platform):
    assessment = finalized_assessment(case_platform)
    svc = case_platform.decision_case_service
    case = _new_case(case_platform)
    svc.link_assessment(case_id=case.decision_case_id,
                        assessment_id=assessment.assessment_id,
                        version=assessment.version, actor=ASSESSOR)
    case_platform.case_decision_service.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=_HUMAN_AUTH, decided_by=DECISION_MAKER,
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    svc.close_case(case_id=case.decision_case_id, actor=DECISION_MAKER)
    with pytest.raises(CaseFinalizedError):
        case_platform.case_decision_service.record_decision(
            case_id=case.decision_case_id, outcome=DecisionOutcome.REJECT,
            authority=_HUMAN_AUTH, decided_by=DECISION_MAKER,
            reason_codes=(ReasonCode.NOT_APPLICABLE,))
