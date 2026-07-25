"""Missing evidence is recorded explicitly — absence is never inferred as a value."""

from __future__ import annotations

import pytest

from ai_hiring.assessments.status import CompletenessStatus
from ai_hiring.ontology import EvidenceType
from ai_hiring.ontology.taxonomy import ReasonCode
from ai_hiring.rubrics.evidence_rules import MissingEvidenceStatus

from .conftest import ASSESSOR, SUBJECT, TENANT, make_assessment_rubric


def _workspace(platform, **rubric_kw):
    make_assessment_rubric(platform, **rubric_kw)
    return platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)


def test_record_missing_evidence(assessment_platform):
    ws = _workspace(assessment_platform)
    record = assessment_platform.assessment_service.record_missing_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        status=MissingEvidenceStatus.NOT_SUBMITTED,
        expected_evidence_type=EvidenceType.CODING_TEST,
        reason_codes=(ReasonCode.MISSING_REQUIRED_EVIDENCE,), actor=ASSESSOR)
    assert record.status is MissingEvidenceStatus.NOT_SUBMITTED
    stored = assessment_platform.assessment_workspace_repo.list_missing(ws.workspace_id)
    assert len(stored) == 1


def test_missing_required_evidence_blocks_when_required(assessment_platform):
    ws = _workspace(assessment_platform)
    record = assessment_platform.assessment_service.record_missing_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        status=MissingEvidenceStatus.NOT_SUBMITTED, actor=ASSESSOR)
    assert record.blocks_when_required is True


def test_not_required_missing_evidence_does_not_block(assessment_platform):
    ws = _workspace(assessment_platform)
    record = assessment_platform.assessment_service.record_missing_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        status=MissingEvidenceStatus.NOT_REQUIRED, actor=ASSESSOR)
    assert record.blocks_when_required is False


def test_workspace_with_only_missing_required_evidence_is_incomplete(assessment_platform):
    ws = _workspace(assessment_platform)
    assessment_platform.assessment_service.record_missing_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        status=MissingEvidenceStatus.NOT_SUBMITTED, actor=ASSESSOR)
    completeness = assessment_platform.assessment_service._compute_completeness(
        assessment_platform.assessment_service.get_workspace(ws.workspace_id))
    assert completeness.status is CompletenessStatus.INCOMPLETE


def test_missing_evidence_for_unknown_criterion_is_refused(assessment_platform):
    from ai_hiring.errors import AssessmentError
    ws = _workspace(assessment_platform)
    with pytest.raises(AssessmentError):
        assessment_platform.assessment_service.record_missing_evidence(
            workspace_id=ws.workspace_id, criterion_id="cap.unknown",
            status=MissingEvidenceStatus.NOT_SUBMITTED, actor=ASSESSOR)
