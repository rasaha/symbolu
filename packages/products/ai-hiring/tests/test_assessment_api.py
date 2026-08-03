"""The assessment API facade exposes the runtime — and nothing beyond it.

The surface deliberately has no scoring, ranking, recommendation, approval, or
hiring operation. These tests exercise the happy path through the typed facade
and assert the forbidden operations simply do not exist.
"""

from __future__ import annotations

import pytest

from ugence_ai_hiring.api.assessment_routes import (
    AssessmentAPI,
    BindEvidenceRequest,
    CreateWorkspaceRequest,
    RecordConflictRequest,
    SubmitObservationRequest,
    WorkspaceActionRequest,
)
from ugence_ai_hiring.assessments.status import AssessmentStatus, SupplierType
from ugence_ai_hiring.ontology import EvidenceType
from ugence_ai_hiring.rubrics.conflicts import ConflictSeverity, ConflictSource
from ugence_ai_hiring.rubrics.scoring_scale import ScaleType

from .conftest import (
    ASSESSOR,
    SUBJECT,
    TENANT,
    ingest_evidence,
    make_assessment_rubric,
)


@pytest.fixture
def api(assessment_platform) -> AssessmentAPI:
    return assessment_platform.build_assessment_api()


def test_api_drives_the_full_lifecycle(assessment_platform, api):
    make_assessment_rubric(assessment_platform)
    ws = api.create_workspace(CreateWorkspaceRequest(
        principal_id=ASSESSOR, tenant_id=TENANT, subject_id=SUBJECT,
        decision_type="hire", rubric_id="rub.assess"))
    evidence = ingest_evidence(assessment_platform)
    bind = api.bind_evidence(BindEvidenceRequest(
        principal_id=ASSESSOR, workspace_id=ws.workspace_id, criterion_id="cap.python",
        evidence_id=evidence.evidence_id, evidence_type=EvidenceType.CODING_TEST))
    assert bind.admissible is True
    api.submit_observation(SubmitObservationRequest(
        principal_id=ASSESSOR, workspace_id=ws.workspace_id, criterion_id="cap.python",
        value="4", scale_type=ScaleType.ONE_TO_FIVE,
        supplier_type=SupplierType.HUMAN_ASSESSOR,
        evidence_binding_ids=(bind.binding.binding_id,)))
    result = api.validate_assessment(WorkspaceActionRequest(
        principal_id=ASSESSOR, workspace_id=ws.workspace_id))
    assert result.valid is True
    assessment = api.finalize_assessment(WorkspaceActionRequest(
        principal_id=ASSESSOR, workspace_id=ws.workspace_id))
    assert assessment.status is AssessmentStatus.FINALIZED_ADVISORY
    assert assessment.advisory_only is True

    fetched = api.get_assessment(assessment.assessment_id)
    assert fetched.assessment_id == assessment.assessment_id
    history = api.get_assessment_history(ws.workspace_id)
    assert len(history) == 1


def test_api_records_conflict(assessment_platform, api):
    make_assessment_rubric(assessment_platform)
    ws = api.create_workspace(CreateWorkspaceRequest(
        principal_id=ASSESSOR, tenant_id=TENANT, subject_id=SUBJECT,
        decision_type="hire", rubric_id="rub.assess"))
    conflict = api.record_conflict(RecordConflictRequest(
        principal_id=ASSESSOR, workspace_id=ws.workspace_id, criterion_id="cap.python",
        sources=(ConflictSource(source_ref="a", claim="x"),
                 ConflictSource(source_ref="b", claim="y")),
        severity=ConflictSeverity.LOW, reason="disagreement"))
    assert conflict.severity is ConflictSeverity.LOW


def test_api_exposes_no_scoring_or_decision_operations(api):
    forbidden = {
        "score", "rank", "compare", "recommend", "recommendation", "approve",
        "reject", "hire", "decide", "decision", "make_decision",
    }
    surface = {name for name in dir(api) if not name.startswith("_")}
    assert forbidden.isdisjoint(surface), (
        f"assessment API must not expose decision operations: "
        f"{forbidden & surface}")


def test_request_schemas_reject_unknown_fields():
    with pytest.raises(Exception):
        CreateWorkspaceRequest(
            principal_id=ASSESSOR, tenant_id=TENANT, subject_id=SUBJECT,
            decision_type="hire", rubric_id="rub.assess", score=5)
