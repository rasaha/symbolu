"""Uncertainty is recorded per the published rule — required when the rule says so."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.assessments.status import CompletenessStatus, SupplierType
from ugence_ai_hiring.errors import RequiredUncertaintyMissingError
from ugence_ai_hiring.ontology import EvidenceType
from ugence_ai_hiring.rubrics.scoring_scale import ScaleType
from ugence_ai_hiring.rubrics.uncertainty import UncertaintyLevel, UncertaintyRule

from .conftest import (
    ASSESSOR,
    SUBJECT,
    TENANT,
    ingest_evidence,
    make_assessment_rubric,
)

_REQUIRES_UNCERTAINTY = UncertaintyRule(
    capability_id="cap.python", requires_uncertainty=True,
    default_level=UncertaintyLevel.MEDIUM,
    allowed_levels=(UncertaintyLevel.LOW, UncertaintyLevel.MEDIUM, UncertaintyLevel.HIGH))


def _bound_workspace(platform, *, uncertainty_rule=None):
    make_assessment_rubric(platform, uncertainty_rule=uncertainty_rule)
    ws = platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    evidence = ingest_evidence(platform)
    binding = platform.assessment_service.bind_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        evidence_id=evidence.evidence_id, evidence_type=EvidenceType.CODING_TEST,
        bound_by=ASSESSOR).binding
    return ws, (binding.binding_id,)


def test_required_uncertainty_missing_is_rejected(assessment_platform):
    ws, bindings = _bound_workspace(
        assessment_platform, uncertainty_rule=_REQUIRES_UNCERTAINTY)
    with pytest.raises(RequiredUncertaintyMissingError):
        assessment_platform.assessment_service.submit_observation(
            workspace_id=ws.workspace_id, criterion_id="cap.python", value="4",
            scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.HUMAN_ASSESSOR,
            supplied_by=ASSESSOR, evidence_binding_ids=bindings, uncertainty=None)


def test_uncertainty_level_outside_allowed_set_is_rejected(assessment_platform):
    rule = UncertaintyRule(
        capability_id="cap.python", requires_uncertainty=True,
        default_level=UncertaintyLevel.LOW, allowed_levels=(UncertaintyLevel.LOW,))
    ws, bindings = _bound_workspace(assessment_platform, uncertainty_rule=rule)
    with pytest.raises(RequiredUncertaintyMissingError):
        assessment_platform.assessment_service.submit_observation(
            workspace_id=ws.workspace_id, criterion_id="cap.python", value="4",
            scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.HUMAN_ASSESSOR,
            supplied_by=ASSESSOR, evidence_binding_ids=bindings,
            uncertainty=UncertaintyLevel.HIGH)


def test_uncertainty_recorded_yields_complete_with_uncertainty(assessment_platform):
    ws, bindings = _bound_workspace(
        assessment_platform, uncertainty_rule=_REQUIRES_UNCERTAINTY)
    assessment_platform.assessment_service.submit_observation(
        workspace_id=ws.workspace_id, criterion_id="cap.python", value="4",
        scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.HUMAN_ASSESSOR,
        supplied_by=ASSESSOR, evidence_binding_ids=bindings,
        uncertainty=UncertaintyLevel.MEDIUM)
    assessment = assessment_platform.assessment_service.finalize_assessment(
        workspace_id=ws.workspace_id, actor=ASSESSOR)
    assert assessment.completeness.status is CompletenessStatus.COMPLETE_WITH_UNCERTAINTY
    assert assessment.completeness.has_uncertainty is True


def test_uncertainty_is_carried_onto_the_capability_assessment(assessment_platform):
    ws, bindings = _bound_workspace(
        assessment_platform, uncertainty_rule=_REQUIRES_UNCERTAINTY)
    assessment_platform.assessment_service.submit_observation(
        workspace_id=ws.workspace_id, criterion_id="cap.python", value="4",
        scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.HUMAN_ASSESSOR,
        supplied_by=ASSESSOR, evidence_binding_ids=bindings,
        uncertainty=UncertaintyLevel.HIGH)
    assessment = assessment_platform.assessment_service.finalize_assessment(
        workspace_id=ws.workspace_id, actor=ASSESSOR)
    ca = assessment.capability_assessments[0]
    assert ca.uncertainty is UncertaintyLevel.HIGH
