"""Binding an ActionRequest to an effective Phase-4A DecisionRecord."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.action_requests import ActionRequestStatus
from ugence_ai_hiring.decision_cases import (
    AuthorityContext,
    AuthorityType,
    DecisionOutcome,
    ProposedOutcome,
    GeneratorType,
    VersionedRef,
)
from ugence_ai_hiring.errors import (
    DecisionNotActionableError,
    DecisionSupersededError,
)
from ugence_ai_hiring.ontology.taxonomy import ReasonCode

from .conftest import (
    ASSESSOR,
    DECISION_MAKER,
    OPS,
    SUBJECT,
    TENANT,
    decided_case,
    finalized_assessment,
    published_mapping,
)


def test_effective_decision_creates_request(action_platform):
    _, decision = decided_case(action_platform)
    published_mapping(action_platform)
    req = action_platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "interview"})
    assert req.status is ActionRequestStatus.DRAFT
    assert req.decision_id == decision.decision_id
    assert req.decision_case_version >= 1
    assert req.action_type == "ADVANCE_WORKFLOW_STAGE"


def test_superseded_decision_is_rejected(action_platform):
    """A decision superseded by a later decision cannot produce an action."""
    case, first = decided_case(action_platform)
    published_mapping(action_platform)
    # Reopen and record a superseding decision on the same case.
    action_platform.decision_case_service.supersede_case(
        case_id=case.decision_case_id, actor=DECISION_MAKER)
    authority = AuthorityContext(authority_id=DECISION_MAKER,
                                 authority_type=AuthorityType.HUMAN_APPROVER,
                                 decision_scope="hire")
    action_platform.case_decision_service.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=authority, decided_by=DECISION_MAKER,
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    with pytest.raises(DecisionSupersededError):
        action_platform.action_request_service.create_action_request(
            decision_id=first.decision_id, mapping_id="map.advance",
            target_system="ATS", created_by=OPS, requested_parameters={"stage": "x"})


def test_cancelled_case_is_rejected(action_platform):
    case, decision = decided_case(action_platform)
    published_mapping(action_platform)
    # Close the case (DECIDED -> CLOSED); a closed case is not actionable.
    action_platform.decision_case_service.close_case(
        case_id=case.decision_case_id, actor=DECISION_MAKER)
    with pytest.raises(DecisionNotActionableError):
        action_platform.action_request_service.create_action_request(
            decision_id=decision.decision_id, mapping_id="map.advance",
            target_system="ATS", created_by=OPS, requested_parameters={"stage": "x"})


def test_non_action_producing_outcome_is_rejected(action_platform):
    _, decision = decided_case(action_platform, outcome=DecisionOutcome.HOLD)
    published_mapping(action_platform)  # only ADVANCE is mapped
    with pytest.raises(DecisionNotActionableError):
        action_platform.action_request_service.create_action_request(
            decision_id=decision.decision_id, mapping_id="map.advance",
            target_system="ATS", created_by=OPS, requested_parameters={"stage": "x"})


def test_cross_tenant_decision_is_rejected(action_platform):
    """OPS is granted only in TENANT; a decision in another tenant is refused."""
    from ugence_ai_hiring.errors import ActionRequestAuthorizationError
    from ugence_ai_hiring.policies.evidence_access_policy import AccessGrant, Permission
    # Build a decided case in a different tenant with its own assessor grant.
    for actor in (ASSESSOR, DECISION_MAKER):
        action_platform.access_grants.add(
            AccessGrant(actor, "t2", frozenset(Permission)))
    _, decision = decided_case(action_platform, subject_id="cand-2", tenant_id="t2")
    published_mapping(action_platform)
    # OPS holds no grant in t2 → authorization denied.
    with pytest.raises(ActionRequestAuthorizationError):
        action_platform.action_request_service.create_action_request(
            decision_id=decision.decision_id, mapping_id="map.advance",
            target_system="ATS", created_by=OPS, requested_parameters={"stage": "x"})


def test_override_context_is_preserved_on_the_decision(action_platform):
    """A decision that overrode a recommendation still binds; override id is present."""
    assessment = finalized_assessment(action_platform)
    case = action_platform.decision_case_service.create_case(
        tenant_id=TENANT, decision_type="hire", subject_ids=(SUBJECT,),
        created_by=ASSESSOR)
    action_platform.decision_case_service.link_assessment(
        case_id=case.decision_case_id, assessment_id=assessment.assessment_id,
        version=assessment.version, actor=ASSESSOR)
    rec = action_platform.case_recommendation_service.submit_recommendation(
        case_id=case.decision_case_id, recommendation_type="screen",
        proposed_outcome=ProposedOutcome.REJECT, generated_by=ASSESSOR,
        generator_type=GeneratorType.HUMAN,
        assessment_refs=(VersionedRef(ref_id=assessment.assessment_id,
                                      version=assessment.version),),
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    authority = AuthorityContext(authority_id=DECISION_MAKER,
                                 authority_type=AuthorityType.HUMAN_APPROVER,
                                 decision_scope="hire")
    decision = action_platform.case_decision_service.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=authority, decided_by=DECISION_MAKER,
        reason_codes=(ReasonCode.CONFLICTING_EVIDENCE,),
        override_reason_codes=(ReasonCode.CONFLICTING_EVIDENCE,),
        recommendation_refs=(VersionedRef(ref_id=rec.recommendation_id, version=1),))
    assert decision.override_record_id is not None
    published_mapping(action_platform)
    req = action_platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "interview"})
    # Bind the CER and confirm the override id flows into the decision context.
    action_platform.action_request_service.validate_action_request(
        request_id=req.action_request_id, actor=OPS)
    cer = action_platform.cer_binding_service.bind_cer(
        request_id=req.action_request_id, actor=OPS)
    assert cer.decision_context.override_record_id == decision.override_record_id


def test_request_creation_does_not_touch_assessment(action_platform):
    """Creating a request must not reinterpret or mutate the assessment."""
    case, decision = decided_case(action_platform)
    published_mapping(action_platform)
    before = {e.event_type for e in action_platform.audit_repo.all()}
    action_platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "x"})
    after = {e.event_type for e in action_platform.audit_repo.all()}
    from ugence_ai_hiring.domain.enums import AuditEventType
    new_events = after - before
    # No assessment observation/finalization events were emitted by Phase 4B.
    assert AuditEventType.ASSESSMENT_OBSERVATION_SUBMITTED not in new_events
    assert AuditEventType.ASSESSMENT_FINALIZED_ADVISORY not in new_events
