"""Phase 3B contract invariants.

These tests pin the *shape* of the deterministic assessment runtime's data
contracts: they are frozen, advisory-only, and carry no scoring, ranking, or
decision semantics. If a future change tried to smuggle a score or a
recommendation into an assessment, these tests fail.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_hiring.assessments.assessment import Assessment, CapabilityAssessment
from ai_hiring.assessments.completeness import CompletenessResult
from ai_hiring.assessments.observation import Observation
from ai_hiring.assessments.status import (
    AssessmentStatus,
    CompletenessStatus,
    ObservationValidationStatus,
    PERMITTED_SUPPLIERS,
    SupplierType,
    WorkspaceStatus,
)
from ai_hiring.assessments.workspace import AssessmentWorkspace, CapabilityBinding
from ai_hiring.rubrics.evidence_rules import EvidenceRule
from ai_hiring.rubrics.scoring_scale import ScaleType


def _capability_assessment() -> CapabilityAssessment:
    return CapabilityAssessment(
        capability_id="cap.x", capability_version=1, criterion_id="cap.x",
        validation_status=ObservationValidationStatus.VALID)


def _binding() -> CapabilityBinding:
    return CapabilityBinding(
        criterion_id="cap.x", capability_id="cap.x", capability_version=1,
        scoring_scale_id="scale.1_5",
        evidence_rule=EvidenceRule(capability_id="cap.x", minimum_count=1))


def _minimal_assessment(**overrides) -> Assessment:
    completeness = CompletenessResult(
        status=CompletenessStatus.COMPLETE, required_criteria_total=0,
        satisfied_criteria=0, criteria_with_observations=0)
    kwargs = dict(
        assessment_id="asmt-1", workspace_id="ws-1", tenant_id="t1", subject_id="c1",
        rubric_id="rub-1", rubric_version=1,
        capability_assessments=(_capability_assessment(),),
        completeness=completeness, status=AssessmentStatus.FINALIZED_ADVISORY,
        created_by="assessor-1")
    kwargs.update(overrides)
    return Assessment(**kwargs)


def test_assessment_is_advisory_only_by_construction():
    assessment = _minimal_assessment()
    assert assessment.advisory_only is True


def test_assessment_advisory_only_cannot_be_falsified():
    with pytest.raises(ValidationError):
        _minimal_assessment(advisory_only=False)


def test_assessment_carries_no_decision_or_score_fields():
    """The runtime must never expose a score, rank, recommendation, or decision."""
    forbidden = {
        "score", "scores", "rank", "ranking", "recommendation", "recommended",
        "decision", "hire", "reject", "verdict", "overall_score", "weighted_score",
    }
    assert forbidden.isdisjoint(Assessment.model_fields.keys())
    assert forbidden.isdisjoint(CapabilityAssessment.model_fields.keys())


def test_assessment_is_frozen():
    assessment = _minimal_assessment()
    with pytest.raises(ValidationError):
        assessment.status = AssessmentStatus.CANCELLED


def test_observation_value_is_an_opaque_token_not_a_score():
    """The observation value is a canonical string token, never a numeric score."""
    obs = Observation(
        observation_id="obs-1", workspace_id="ws-1", criterion_id="cap.x",
        capability_id="cap.x", capability_version=1, value="4",
        scale_type=ScaleType.ONE_TO_FIVE, supplied_by="assessor-1",
        supplier_type=SupplierType.HUMAN_ASSESSOR)
    assert isinstance(obs.value, str)
    with pytest.raises(ValidationError):
        obs.value = "5"


def test_ai_model_is_never_a_permitted_supplier():
    assert SupplierType.AI_MODEL not in PERMITTED_SUPPLIERS
    assert SupplierType.HUMAN_ASSESSOR in PERMITTED_SUPPLIERS


def test_workspace_is_frozen_and_versioned():
    ws = AssessmentWorkspace(
        workspace_id="ws-1", tenant_id="t1", subject_id="c1", decision_type="hire",
        rubric_id="rub-1", rubric_version=1, capability_bindings=(_binding(),),
        uncertainty_rules=(), created_by="assessor-1",
        status=WorkspaceStatus.EVIDENCE_BINDING)
    with pytest.raises(ValidationError):
        ws.status = WorkspaceStatus.CANCELLED
    reopened = ws.with_status(WorkspaceStatus.IN_PROGRESS)
    assert reopened.version == ws.version + 1
    assert reopened.status is WorkspaceStatus.IN_PROGRESS
    assert ws.status is WorkspaceStatus.EVIDENCE_BINDING  # original untouched


def test_capability_assessment_validation_status_is_structural():
    assert set(ObservationValidationStatus) == {
        ObservationValidationStatus.VALID, ObservationValidationStatus.INVALID}
