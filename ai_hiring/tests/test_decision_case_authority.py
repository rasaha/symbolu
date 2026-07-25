"""Authority model: humans and bounded delegated policy decide; AI never does."""

from __future__ import annotations

import pytest

from ai_hiring.decision_cases import (
    AuthorityContext,
    AuthorityType,
    DecisionOutcome,
    GeneratorType,
    ProposedOutcome,
    VersionedRef,
)
from ai_hiring.errors import (
    AIDecisionAuthorityError,
    DecisionAuthorityError,
    SegregationOfDutiesError,
    UnauthorizedOverrideError,
)
from ai_hiring.ontology.taxonomy import ReasonCode

from .conftest import (
    AI_ACTOR,
    ASSESSOR,
    DECISION_MAKER,
    POLICY_ENGINE,
    SUBJECT,
    TENANT,
    finalized_assessment,
)


def _ready_case(platform):
    assessment = finalized_assessment(platform)
    case = platform.decision_case_service.create_case(
        tenant_id=TENANT, decision_type="hire", subject_ids=(SUBJECT,),
        created_by=ASSESSOR)
    platform.decision_case_service.link_assessment(
        case_id=case.decision_case_id, assessment_id=assessment.assessment_id,
        version=assessment.version, actor=ASSESSOR)
    return case, assessment


def test_valid_human_decision(case_platform):
    case, _ = _ready_case(case_platform)
    auth = AuthorityContext(authority_id=DECISION_MAKER,
                            authority_type=AuthorityType.HUMAN_APPROVER,
                            decision_scope="hire")
    decision = case_platform.case_decision_service.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=auth, decided_by=DECISION_MAKER,
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    assert decision.authority_type is AuthorityType.HUMAN_APPROVER


def test_valid_delegated_policy_decision(case_platform):
    """A bounded, published policy (a SERVICE principal) may decide within scope."""
    case, _ = _ready_case(case_platform)
    auth = AuthorityContext(
        authority_id=POLICY_ENGINE, authority_type=AuthorityType.DELEGATED_POLICY,
        decision_scope="auto-advance-screening",
        granting_policy_ref=VersionedRef(ref_id="pol.autoscreen", version=1),
        limits=("outcome:ADVANCE",))
    decision = case_platform.case_decision_service.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=auth, decided_by=POLICY_ENGINE,
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    assert decision.authority_type is AuthorityType.DELEGATED_POLICY


def test_ai_model_cannot_decide(case_platform):
    """An AI principal is refused as a binding decision authority."""
    case, _ = _ready_case(case_platform)
    auth = AuthorityContext(authority_id=AI_ACTOR,
                            authority_type=AuthorityType.HUMAN_APPROVER,
                            decision_scope="hire")
    with pytest.raises(AIDecisionAuthorityError):
        case_platform.case_decision_service.record_decision(
            case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
            authority=auth, decided_by=AI_ACTOR,
            reason_codes=(ReasonCode.NOT_APPLICABLE,))


def test_human_authority_requires_human_actor(case_platform):
    """A SERVICE principal cannot claim HUMAN_APPROVER authority."""
    case, _ = _ready_case(case_platform)
    auth = AuthorityContext(authority_id=POLICY_ENGINE,
                            authority_type=AuthorityType.HUMAN_APPROVER,
                            decision_scope="hire")
    with pytest.raises(DecisionAuthorityError):
        case_platform.case_decision_service.record_decision(
            case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
            authority=auth, decided_by=POLICY_ENGINE,
            reason_codes=(ReasonCode.NOT_APPLICABLE,))


def test_unauthorized_actor_cannot_decide(case_platform):
    """An unregistered principal (no grant) is refused before any authority check."""
    from ai_hiring.errors import DecisionCaseAuthorizationError
    case, _ = _ready_case(case_platform)
    auth = AuthorityContext(authority_id="stranger",
                            authority_type=AuthorityType.HUMAN_APPROVER,
                            decision_scope="hire")
    with pytest.raises(DecisionCaseAuthorizationError):
        case_platform.case_decision_service.record_decision(
            case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
            authority=auth, decided_by="stranger",
            reason_codes=(ReasonCode.NOT_APPLICABLE,))


def test_segregation_of_duties_blocks_self_approval(case_platform):
    """When SoD is required, the recommendation author cannot also decide."""
    case, assessment = _ready_case(case_platform)
    rec = case_platform.case_recommendation_service.submit_recommendation(
        case_id=case.decision_case_id, recommendation_type="screen",
        proposed_outcome=ProposedOutcome.ADVANCE, generated_by=DECISION_MAKER,
        generator_type=GeneratorType.HUMAN,
        assessment_refs=(VersionedRef(ref_id=assessment.assessment_id,
                                      version=assessment.version, kind="assessment"),),
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    auth = AuthorityContext(authority_id=DECISION_MAKER,
                            authority_type=AuthorityType.HUMAN_APPROVER,
                            decision_scope="hire", segregation_of_duties=True)
    with pytest.raises(SegregationOfDutiesError):
        case_platform.case_decision_service.record_decision(
            case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
            authority=auth, decided_by=DECISION_MAKER,
            reason_codes=(ReasonCode.NOT_APPLICABLE,),
            recommendation_refs=(VersionedRef(ref_id=rec.recommendation_id, version=1),))


def test_override_requires_reason_codes(case_platform):
    """A decision that departs from the recommendation needs override reasons."""
    case, assessment = _ready_case(case_platform)
    rec = case_platform.case_recommendation_service.submit_recommendation(
        case_id=case.decision_case_id, recommendation_type="screen",
        proposed_outcome=ProposedOutcome.ADVANCE, generated_by=ASSESSOR,
        generator_type=GeneratorType.HUMAN,
        assessment_refs=(VersionedRef(ref_id=assessment.assessment_id,
                                      version=assessment.version, kind="assessment"),),
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    auth = AuthorityContext(authority_id=DECISION_MAKER,
                            authority_type=AuthorityType.HUMAN_APPROVER,
                            decision_scope="hire")
    # Decide REJECT against an ADVANCE recommendation, with NO override reasons.
    with pytest.raises(UnauthorizedOverrideError):
        case_platform.case_decision_service.record_decision(
            case_id=case.decision_case_id, outcome=DecisionOutcome.REJECT,
            authority=auth, decided_by=DECISION_MAKER, reason_codes=(),
            recommendation_refs=(VersionedRef(ref_id=rec.recommendation_id, version=1),))


def test_override_preserves_recommendation(case_platform):
    case, assessment = _ready_case(case_platform)
    rec = case_platform.case_recommendation_service.submit_recommendation(
        case_id=case.decision_case_id, recommendation_type="screen",
        proposed_outcome=ProposedOutcome.ADVANCE, generated_by=ASSESSOR,
        generator_type=GeneratorType.HUMAN,
        assessment_refs=(VersionedRef(ref_id=assessment.assessment_id,
                                      version=assessment.version, kind="assessment"),),
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    auth = AuthorityContext(authority_id=DECISION_MAKER,
                            authority_type=AuthorityType.HUMAN_APPROVER,
                            decision_scope="hire")
    decision = case_platform.case_decision_service.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.REJECT,
        authority=auth, decided_by=DECISION_MAKER,
        reason_codes=(ReasonCode.CONFLICTING_EVIDENCE,),
        override_reason_codes=(ReasonCode.CONFLICTING_EVIDENCE,),
        recommendation_refs=(VersionedRef(ref_id=rec.recommendation_id, version=1),))
    assert decision.override_record_id is not None
    overrides = case_platform.case_decision_service.list_overrides(case.decision_case_id)
    assert len(overrides) == 1
    ovr = overrides[0]
    assert ovr.original_recommendation_id == rec.recommendation_id
    assert ovr.original_proposed_outcome is ProposedOutcome.ADVANCE
    assert ovr.final_outcome is DecisionOutcome.REJECT
    # The recommendation itself is untouched.
    assert case_platform.case_recommendation_service.get_recommendation(
        rec.recommendation_id).proposed_outcome is ProposedOutcome.ADVANCE
