"""Deterministic, typed validation of links, recommendations, and readiness."""

from __future__ import annotations

import pytest

from ai_hiring.decision_cases import (
    GeneratorType,
    ProposedOutcome,
    VersionedRef,
)
from ai_hiring.decision_cases.validation import DecisionReadinessResult
from ai_hiring.errors import (
    AssessmentNotLinkableError,
    RecommendationValidationError,
)
from ai_hiring.ontology.taxonomy import ReasonCode
from ai_hiring.policies.evidence_access_policy import AccessGrant, Permission

from .conftest import (
    ASSESSOR,
    SUBJECT,
    TENANT,
    finalized_assessment,
)


def _case(platform, *, tenant_id=TENANT, subject_id=SUBJECT):
    return platform.decision_case_service.create_case(
        tenant_id=tenant_id, decision_type="hire", subject_ids=(subject_id,),
        created_by=ASSESSOR)


def test_cross_tenant_assessment_link_is_refused(case_platform):
    assessment = finalized_assessment(case_platform)  # tenant t1
    case_platform.access_grants.add(
        AccessGrant(ASSESSOR, "t2", frozenset(Permission)))
    case = _case(case_platform, tenant_id="t2")
    with pytest.raises(AssessmentNotLinkableError):
        case_platform.decision_case_service.link_assessment(
            case_id=case.decision_case_id, assessment_id=assessment.assessment_id,
            version=assessment.version, actor=ASSESSOR)


def test_subject_mismatch_link_is_refused(case_platform):
    assessment = finalized_assessment(case_platform)  # subject cand-1
    case = _case(case_platform, subject_id="someone-else")
    with pytest.raises(AssessmentNotLinkableError):
        case_platform.decision_case_service.link_assessment(
            case_id=case.decision_case_id, assessment_id=assessment.assessment_id,
            version=assessment.version, actor=ASSESSOR)


def test_wrong_version_link_is_refused(case_platform):
    assessment = finalized_assessment(case_platform)
    case = _case(case_platform)
    with pytest.raises(AssessmentNotLinkableError):
        case_platform.decision_case_service.link_assessment(
            case_id=case.decision_case_id, assessment_id=assessment.assessment_id,
            version=assessment.version + 5, actor=ASSESSOR)


def test_link_validation_returns_typed_result(case_platform):
    assessment = finalized_assessment(case_platform)
    case = _case(case_platform)
    result = case_platform.case_validation_service.validate_assessment_link(
        case_platform.decision_case_service.get_case(case.decision_case_id),
        assessment_id=assessment.assessment_id, version=assessment.version)
    assert result.valid is True
    assert result.error_codes == ()
    assert result.referenced_versions


def test_recommendation_referencing_unlinked_assessment_is_refused(case_platform):
    finalized_assessment(case_platform)
    case = _case(case_platform)  # no assessment linked
    with pytest.raises(RecommendationValidationError):
        case_platform.case_recommendation_service.submit_recommendation(
            case_id=case.decision_case_id, recommendation_type="screen",
            proposed_outcome=ProposedOutcome.ADVANCE, generated_by=ASSESSOR,
            generator_type=GeneratorType.HUMAN,
            assessment_refs=(VersionedRef(ref_id="a-not-linked", version=1),),
            reason_codes=(ReasonCode.NOT_APPLICABLE,))


def test_readiness_result_is_deterministic_and_typed(case_platform):
    assessment = finalized_assessment(case_platform)
    svc = case_platform.decision_case_service
    case = _case(case_platform)
    svc.link_assessment(case_id=case.decision_case_id,
                        assessment_id=assessment.assessment_id,
                        version=assessment.version, actor=ASSESSOR)
    r1 = svc.validate_decision_readiness(case_id=case.decision_case_id, actor=ASSESSOR)
    r2 = svc.validate_decision_readiness(case_id=case.decision_case_id, actor=ASSESSOR)
    assert isinstance(r1, DecisionReadinessResult)
    assert r1.ready == r2.ready == True
    assert r1.blocker_codes == r2.blocker_codes == ()


def test_reason_code_catalog_is_closed(case_platform):
    """Reason codes are a closed, approved vocabulary — unknown codes are impossible."""
    from ai_hiring.ontology.taxonomy import is_known_reason_code
    assert is_known_reason_code(ReasonCode.CONFLICTING_EVIDENCE.value)
    assert not is_known_reason_code("MADE_UP_CODE")
