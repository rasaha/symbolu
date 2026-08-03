"""Phase 4A contract invariants: immutable, separate, versioned records."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ugence_ai_hiring.errors import DomainValidationError

#: Invalid construction may fail at the field level (pydantic) or in a
#: domain ``model_validator`` (DomainValidationError). Accept either.
INVALID = (ValidationError, DomainValidationError)

from ugence_ai_hiring.decision_cases import (
    AuthorityContext,
    AuthorityType,
    DecisionCase,
    DecisionOutcome,
    DecisionRecord,
    GeneratorType,
    OverrideRecord,
    ProposedOutcome,
    RecommendationRecord,
    ReviewTask,
    ReviewTaskType,
    SubjectRef,
    VersionedRef,
)
from ugence_ai_hiring.ontology.taxonomy import ReasonCode


def _case(**kw) -> DecisionCase:
    base = dict(decision_case_id="dc1", tenant_id="t1", decision_type="hire",
                subject_refs=(SubjectRef(subject_id="c1"),), created_by="u1",
                case_version_id="v1")
    base.update(kw)
    return DecisionCase(**base)


def test_case_requires_a_subject():
    with pytest.raises(INVALID):
        DecisionCase(decision_case_id="dc1", tenant_id="t1", decision_type="hire",
                     subject_refs=(), created_by="u1")


def test_case_is_frozen_and_versioned():
    case = _case()
    with pytest.raises(ValidationError):
        case.status = None  # frozen
    evolved = case.with_added_ref(
        "assessment_refs", VersionedRef(ref_id="a1", version=1), case_version_id="v2")
    assert evolved.version == 2
    assert evolved.supersedes_case_version_id == "v1"
    assert case.version == 1  # original untouched


def test_case_holds_no_execution_state():
    forbidden = {"execution", "execution_refs", "cer", "action", "action_refs",
                 "executed", "actiongate"}
    assert forbidden.isdisjoint(DecisionCase.model_fields.keys())


def test_versioned_ref_requires_positive_version():
    with pytest.raises(INVALID):
        VersionedRef(ref_id="a1", version=0)


def test_recommendation_is_advisory_only():
    rec = RecommendationRecord(
        recommendation_id="r1", decision_case_id="dc1", tenant_id="t1",
        recommendation_type="screen", proposed_outcome=ProposedOutcome.ADVANCE,
        generated_by="u1", generator_type=GeneratorType.HUMAN)
    assert rec.advisory_only is True
    with pytest.raises(ValidationError):
        RecommendationRecord(
            recommendation_id="r1", decision_case_id="dc1", tenant_id="t1",
            recommendation_type="screen", proposed_outcome=ProposedOutcome.ADVANCE,
            generated_by="u1", generator_type=GeneratorType.HUMAN, advisory_only=False)


def test_ai_assisted_recommendation_requires_model_provenance():
    with pytest.raises(INVALID):
        RecommendationRecord(
            recommendation_id="r1", decision_case_id="dc1", tenant_id="t1",
            recommendation_type="screen", proposed_outcome=ProposedOutcome.ADVANCE,
            generated_by="ai-1", generator_type=GeneratorType.AI_ASSISTED)
    ok = RecommendationRecord(
        recommendation_id="r1", decision_case_id="dc1", tenant_id="t1",
        recommendation_type="screen", proposed_outcome=ProposedOutcome.ADVANCE,
        generated_by="ai-1", generator_type=GeneratorType.AI_ASSISTED,
        model_provenance="model-x@1.0")
    assert ok.model_provenance == "model-x@1.0"


def test_recommendation_carries_no_binding_decision_fields():
    forbidden = {"outcome", "authority_type", "decided_by", "effective_status",
                 "binding"}
    assert forbidden.isdisjoint(RecommendationRecord.model_fields.keys())


def test_decision_requires_explicit_reason_codes():
    with pytest.raises(INVALID):
        DecisionRecord(
            decision_id="d1", decision_case_id="dc1", tenant_id="t1",
            decision_type="hire", outcome=DecisionOutcome.ADVANCE,
            authority_type=AuthorityType.HUMAN_APPROVER, decided_by="u1",
            reason_codes=())


def test_decision_authority_type_cannot_be_ai_structurally():
    # AuthorityType has no AI member; there is no way to name AI as authority.
    assert "AI_MODEL" not in {a.value for a in AuthorityType}
    assert "AI" not in {a.value for a in AuthorityType}


def test_decision_carries_no_execution_state():
    forbidden = {"execution", "executed", "cer", "action", "actiongate",
                 "execution_status"}
    assert forbidden.isdisjoint(DecisionRecord.model_fields.keys())


def test_override_preserves_original_and_requires_reasons():
    with pytest.raises(INVALID):  # needs reason codes
        OverrideRecord(
            override_id="o1", decision_case_id="dc1", tenant_id="t1",
            final_outcome=DecisionOutcome.REJECT, authorized_by="u1",
            reason_codes=(), original_recommendation_id="r1")
    with pytest.raises(INVALID):  # needs something it departs from
        OverrideRecord(
            override_id="o1", decision_case_id="dc1", tenant_id="t1",
            final_outcome=DecisionOutcome.REJECT, authorized_by="u1",
            reason_codes=(ReasonCode.CONFLICTING_EVIDENCE,))
    ok = OverrideRecord(
        override_id="o1", decision_case_id="dc1", tenant_id="t1",
        final_outcome=DecisionOutcome.REJECT, authorized_by="u1",
        reason_codes=(ReasonCode.CONFLICTING_EVIDENCE,),
        original_recommendation_id="r1",
        original_proposed_outcome=ProposedOutcome.ADVANCE)
    assert ok.original_recommendation_id == "r1"


def test_delegated_policy_authority_must_be_bounded():
    with pytest.raises(INVALID):  # no granting policy / scope
        AuthorityContext(authority_id="p1", authority_type=AuthorityType.DELEGATED_POLICY)
    ok = AuthorityContext(
        authority_id="p1", authority_type=AuthorityType.DELEGATED_POLICY,
        decision_scope="auto-advance-screening",
        granting_policy_ref=VersionedRef(ref_id="pol1", version=1))
    assert ok.authority_type is AuthorityType.DELEGATED_POLICY


def test_review_task_completion_is_a_new_immutable_revision():
    from ugence_ai_hiring.common import utc_now
    task = ReviewTask(task_id="rt1", decision_case_id="dc1", tenant_id="t1",
                      task_type=ReviewTaskType.REQUIRED_REVIEW)
    done = task.completed(by="reviewer-1", at=utc_now())
    assert done.revision == 2 and done.completed_by == "reviewer-1"
    assert task.revision == 1 and task.completed_by is None  # original untouched


def test_records_have_distinct_identity_fields():
    assert "recommendation_id" in RecommendationRecord.model_fields
    assert "decision_id" in DecisionRecord.model_fields
    assert "override_id" in OverrideRecord.model_fields
    assert "task_id" in ReviewTask.model_fields
    assert "decision_case_id" in DecisionCase.model_fields


def test_serialization_roundtrip():
    case = _case()
    data = case.model_dump()
    assert DecisionCase(**data) == case
