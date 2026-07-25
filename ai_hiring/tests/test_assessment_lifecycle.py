"""The full deterministic lifecycle: create → bind → observe → finalize → supersede.

Assessments are append-only and advisory. Finalizing a superseding revision never
rewrites the prior record; it appends a new version that points back at it. Closed
workspaces refuse further mutation.
"""

from __future__ import annotations

import pytest

from ai_hiring.assessments.status import (
    AssessmentStatus,
    CompletenessStatus,
    SupplierType,
    WorkspaceStatus,
)
from ai_hiring.errors import (
    AssessmentAlreadyFinalizedError,
    AssessmentIncompleteError,
    AssessmentError,
)
from ai_hiring.ontology import EvidenceType
from ai_hiring.rubrics.scoring_scale import ScaleType

from .conftest import (
    ASSESSOR,
    SUBJECT,
    TENANT,
    ingest_evidence,
    make_assessment_rubric,
)


def _finalize_once(platform, *, value="4"):
    make_assessment_rubric(platform)
    ws = platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    evidence = ingest_evidence(platform)
    binding = platform.assessment_service.bind_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        evidence_id=evidence.evidence_id, evidence_type=EvidenceType.CODING_TEST,
        bound_by=ASSESSOR).binding
    platform.assessment_service.submit_observation(
        workspace_id=ws.workspace_id, criterion_id="cap.python", value=value,
        scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.HUMAN_ASSESSOR,
        supplied_by=ASSESSOR, evidence_binding_ids=(binding.binding_id,))
    assessment = platform.assessment_service.finalize_assessment(
        workspace_id=ws.workspace_id, actor=ASSESSOR)
    return ws, assessment


def test_full_happy_path_finalizes_advisory(assessment_platform):
    ws, assessment = _finalize_once(assessment_platform)
    assert assessment.status is AssessmentStatus.FINALIZED_ADVISORY
    assert assessment.advisory_only is True
    assert assessment.completeness.status is CompletenessStatus.COMPLETE
    assert assessment.version == 1
    reloaded = assessment_platform.assessment_service.get_workspace(ws.workspace_id)
    assert reloaded.status is WorkspaceStatus.FINALIZED_ADVISORY


def test_low_value_still_completes_structurally(assessment_platform):
    """Structural completeness never judges whether a value is good or bad."""
    _, assessment = _finalize_once(assessment_platform, value="1")
    assert assessment.completeness.status is CompletenessStatus.COMPLETE


def test_finalize_incomplete_workspace_is_refused(assessment_platform):
    make_assessment_rubric(assessment_platform)
    ws = assessment_platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    with pytest.raises(AssessmentIncompleteError):
        assessment_platform.assessment_service.finalize_assessment(
            workspace_id=ws.workspace_id, actor=ASSESSOR)


def test_closed_workspace_refuses_further_mutation(assessment_platform):
    ws, _ = _finalize_once(assessment_platform)
    evidence = ingest_evidence(assessment_platform, text="print('another')\n")
    with pytest.raises(AssessmentAlreadyFinalizedError):
        assessment_platform.assessment_service.bind_evidence(
            workspace_id=ws.workspace_id, criterion_id="cap.python",
            evidence_id=evidence.evidence_id, evidence_type=EvidenceType.CODING_TEST,
            bound_by=ASSESSOR)


def test_supersession_appends_a_new_version(assessment_platform):
    ws, first = _finalize_once(assessment_platform, value="3")
    # Reopen for a superseding revision.
    reopened = assessment_platform.assessment_service.supersede_assessment(
        workspace_id=ws.workspace_id, actor=ASSESSOR)
    assert reopened.status is WorkspaceStatus.IN_PROGRESS
    # Add a fresh observation and re-finalize.
    evidence = ingest_evidence(assessment_platform, text="print('revised')\n")
    binding = assessment_platform.assessment_service.bind_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        evidence_id=evidence.evidence_id, evidence_type=EvidenceType.CODING_TEST,
        bound_by=ASSESSOR).binding
    assessment_platform.assessment_service.submit_observation(
        workspace_id=ws.workspace_id, criterion_id="cap.python", value="5",
        scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.HUMAN_ASSESSOR,
        supplied_by=ASSESSOR, evidence_binding_ids=(binding.binding_id,))
    second = assessment_platform.assessment_service.finalize_assessment(
        workspace_id=ws.workspace_id, actor=ASSESSOR)

    assert second.version == 2
    assert second.supersedes_assessment_id == first.assessment_id
    # The prior record is untouched and still retrievable.
    history = assessment_platform.assessment_service.get_assessment_history(ws.workspace_id)
    assert [a.version for a in history] == [1, 2]
    assert assessment_platform.assessment_service.get_assessment(
        first.assessment_id).version == 1


def test_only_finalized_workspace_can_be_superseded(assessment_platform):
    make_assessment_rubric(assessment_platform)
    ws = assessment_platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    with pytest.raises(AssessmentError):
        assessment_platform.assessment_service.supersede_assessment(
            workspace_id=ws.workspace_id, actor=ASSESSOR)


def test_cancel_marks_workspace_cancelled(assessment_platform):
    make_assessment_rubric(assessment_platform)
    ws = assessment_platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    cancelled = assessment_platform.assessment_service.cancel_assessment(
        workspace_id=ws.workspace_id, actor=ASSESSOR)
    assert cancelled.status is WorkspaceStatus.CANCELLED
    evidence = ingest_evidence(assessment_platform)
    with pytest.raises(AssessmentAlreadyFinalizedError):
        assessment_platform.assessment_service.bind_evidence(
            workspace_id=ws.workspace_id, criterion_id="cap.python",
            evidence_id=evidence.evidence_id, evidence_type=EvidenceType.CODING_TEST,
            bound_by=ASSESSOR)
