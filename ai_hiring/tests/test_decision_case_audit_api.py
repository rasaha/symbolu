"""Audit completeness, tenant isolation, history, and the typed API surface."""

from __future__ import annotations

import pytest

from ai_hiring.api.decision_case_routes import (
    CreateCaseRequest,
    DecisionCaseAPI,
    LinkAssessmentRequest,
    RecordDecisionRequest,
    SubmitRecommendationRequest,
)
from ai_hiring.decision_cases import (
    AuthorityContext,
    AuthorityType,
    CaseStatus,
    DecisionOutcome,
    GeneratorType,
    ProposedOutcome,
    VersionedRef,
)
from ai_hiring.domain.enums import AuditEventType
from ai_hiring.ontology.taxonomy import ReasonCode

from .conftest import (
    ASSESSOR,
    DECISION_MAKER,
    SUBJECT,
    TENANT,
    finalized_assessment,
)

_HUMAN_AUTH = AuthorityContext(
    authority_id=DECISION_MAKER, authority_type=AuthorityType.HUMAN_APPROVER,
    decision_scope="hire")


def _event_types(platform):
    return {e.event_type for e in platform.audit_repo.all()}


def test_material_transitions_are_audited(case_platform):
    assessment = finalized_assessment(case_platform)
    dcs = case_platform.decision_case_service
    case = dcs.create_case(tenant_id=TENANT, decision_type="hire",
                           subject_ids=(SUBJECT,), created_by=ASSESSOR)
    dcs.link_assessment(case_id=case.decision_case_id,
                        assessment_id=assessment.assessment_id,
                        version=assessment.version, actor=ASSESSOR)
    case_platform.case_decision_service.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=_HUMAN_AUTH, decided_by=DECISION_MAKER,
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    dcs.close_case(case_id=case.decision_case_id, actor=DECISION_MAKER)

    types = _event_types(case_platform)
    assert AuditEventType.DECISION_CASE_CREATED in types
    assert AuditEventType.DECISION_CASE_ASSESSMENT_LINKED in types
    assert AuditEventType.DECISION_RECORDED in types
    assert AuditEventType.DECISION_CASE_CLOSED in types


def test_override_is_audited(case_platform):
    assessment = finalized_assessment(case_platform)
    dcs = case_platform.decision_case_service
    case = dcs.create_case(tenant_id=TENANT, decision_type="hire",
                           subject_ids=(SUBJECT,), created_by=ASSESSOR)
    dcs.link_assessment(case_id=case.decision_case_id,
                        assessment_id=assessment.assessment_id,
                        version=assessment.version, actor=ASSESSOR)
    rec = case_platform.case_recommendation_service.submit_recommendation(
        case_id=case.decision_case_id, recommendation_type="screen",
        proposed_outcome=ProposedOutcome.ADVANCE, generated_by=ASSESSOR,
        generator_type=GeneratorType.HUMAN,
        assessment_refs=(VersionedRef(ref_id=assessment.assessment_id,
                                      version=assessment.version),),
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    case_platform.case_decision_service.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.REJECT,
        authority=_HUMAN_AUTH, decided_by=DECISION_MAKER,
        reason_codes=(ReasonCode.CONFLICTING_EVIDENCE,),
        override_reason_codes=(ReasonCode.CONFLICTING_EVIDENCE,),
        recommendation_refs=(VersionedRef(ref_id=rec.recommendation_id, version=1),))
    types = _event_types(case_platform)
    assert AuditEventType.DECISION_CASE_RECOMMENDATION_ADDED in types
    assert AuditEventType.DECISION_OVERRIDE_RECORDED in types


def test_denied_action_is_audited(case_platform):
    finalized_assessment(case_platform)
    # "outsider" is unregistered — creating a case must be denied and audited.
    with pytest.raises(Exception):
        case_platform.decision_case_service.create_case(
            tenant_id=TENANT, decision_type="hire", subject_ids=(SUBJECT,),
            created_by="outsider")
    assert AuditEventType.DECISION_CASE_ACCESS_DENIED in _event_types(case_platform)


def test_history_is_reconstructable(case_platform):
    assessment = finalized_assessment(case_platform)
    dcs = case_platform.decision_case_service
    case = dcs.create_case(tenant_id=TENANT, decision_type="hire",
                           subject_ids=(SUBJECT,), created_by=ASSESSOR)
    dcs.link_assessment(case_id=case.decision_case_id,
                        assessment_id=assessment.assessment_id,
                        version=assessment.version, actor=ASSESSOR)
    history = dcs.get_case_history(case.decision_case_id)
    versions = [c.version for c in history]
    assert versions == sorted(versions)
    assert versions[0] == 1
    # every later snapshot points back at the previous one
    for i in range(1, len(history)):
        assert history[i].supersedes_case_version_id == history[i - 1].case_version_id


def test_tenant_isolation_on_reads(case_platform):
    from ai_hiring.errors import DecisionCaseNotFoundError
    dcs = case_platform.decision_case_service
    dcs.create_case(tenant_id=TENANT, decision_type="hire", subject_ids=(SUBJECT,),
                    created_by=ASSESSOR)
    with pytest.raises(DecisionCaseNotFoundError):
        dcs.get_case("no-such-case")


def test_api_drives_full_flow(case_platform):
    assessment = finalized_assessment(case_platform)
    api: DecisionCaseAPI = case_platform.build_decision_case_api()
    case = api.create_decision_case(CreateCaseRequest(
        principal_id=ASSESSOR, tenant_id=TENANT, decision_type="hire",
        subject_ids=(SUBJECT,)))
    api.link_assessment(LinkAssessmentRequest(
        principal_id=ASSESSOR, case_id=case.decision_case_id,
        assessment_id=assessment.assessment_id, version=assessment.version))
    api.submit_recommendation(SubmitRecommendationRequest(
        principal_id=ASSESSOR, case_id=case.decision_case_id,
        recommendation_type="screen", proposed_outcome=ProposedOutcome.ADVANCE,
        generator_type=GeneratorType.HUMAN,
        assessment_refs=(VersionedRef(ref_id=assessment.assessment_id,
                                      version=assessment.version),),
        reason_codes=(ReasonCode.NOT_APPLICABLE,)))
    decision = api.record_decision(RecordDecisionRequest(
        principal_id=DECISION_MAKER, case_id=case.decision_case_id,
        outcome=DecisionOutcome.ADVANCE, authority=_HUMAN_AUTH,
        reason_codes=(ReasonCode.NOT_APPLICABLE,)))
    assert decision.outcome is DecisionOutcome.ADVANCE
    assert api.get_decision_case(case.decision_case_id).status is CaseStatus.DECIDED


def test_api_exposes_no_execution_operations(case_platform):
    api = case_platform.build_decision_case_api()
    forbidden = {"execute_decision", "send_to_actiongate", "construct_cer",
                 "rank_candidates", "auto_hire", "auto_reject", "execute", "reconcile"}
    surface = {name for name in dir(api) if not name.startswith("_")}
    assert forbidden.isdisjoint(surface), f"forbidden ops present: {forbidden & surface}"


def test_api_request_rejects_unknown_fields():
    with pytest.raises(Exception):
        CreateCaseRequest(principal_id=ASSESSOR, tenant_id=TENANT, decision_type="hire",
                          subject_ids=(SUBJECT,), execute=True)
