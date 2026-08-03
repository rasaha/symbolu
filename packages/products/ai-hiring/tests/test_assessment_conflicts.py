"""Conflicts are recorded, never auto-resolved. HIGH/CRITICAL block finalization.

The runtime records contradictions between sources deterministically. It has no
authority to resolve them — a HIGH or CRITICAL conflict blocks advisory
finalization and requires a later authorized disposition (out of Phase-3B scope).
LOW/MEDIUM conflicts are recorded and surface as COMPLETE_WITH_CONFLICTS.
"""

from __future__ import annotations

import pytest

from ugence_ai_hiring.assessments.status import CompletenessStatus, SupplierType
from ugence_ai_hiring.errors import BlockingConflictError
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

_SOURCES = (
    ConflictSource(source_ref="assessor-1", claim="meets"),
    ConflictSource(source_ref="assessor-2", claim="does not meet"),
)


def _complete_workspace(platform):
    """A workspace with a satisfied required criterion (binding + observation)."""
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
        workspace_id=ws.workspace_id, criterion_id="cap.python", value="4",
        scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.HUMAN_ASSESSOR,
        supplied_by=ASSESSOR, evidence_binding_ids=(binding.binding_id,))
    return ws


def test_record_conflict(assessment_platform):
    ws = _complete_workspace(assessment_platform)
    conflict = assessment_platform.assessment_service.record_conflict(
        workspace_id=ws.workspace_id, criterion_id="cap.python", sources=_SOURCES,
        severity=ConflictSeverity.LOW, reason="disagreement", actor=ASSESSOR)
    assert conflict.severity is ConflictSeverity.LOW
    stored = assessment_platform.assessment_workspace_repo.list_conflicts(ws.workspace_id)
    assert len(stored) == 1


def test_low_conflict_yields_complete_with_conflicts(assessment_platform):
    ws = _complete_workspace(assessment_platform)
    assessment_platform.assessment_service.record_conflict(
        workspace_id=ws.workspace_id, criterion_id="cap.python", sources=_SOURCES,
        severity=ConflictSeverity.MEDIUM, reason="disagreement", actor=ASSESSOR)
    assessment = assessment_platform.assessment_service.finalize_assessment(
        workspace_id=ws.workspace_id, actor=ASSESSOR)
    assert assessment.completeness.status is CompletenessStatus.COMPLETE_WITH_CONFLICTS
    assert assessment.completeness.has_conflicts is True


@pytest.mark.parametrize("severity", [ConflictSeverity.HIGH, ConflictSeverity.CRITICAL])
def test_high_severity_conflict_blocks_finalization(assessment_platform, severity):
    ws = _complete_workspace(assessment_platform)
    assessment_platform.assessment_service.record_conflict(
        workspace_id=ws.workspace_id, criterion_id="cap.python", sources=_SOURCES,
        severity=severity, reason="material contradiction", actor=ASSESSOR)
    completeness = assessment_platform.assessment_service._compute_completeness(
        assessment_platform.assessment_service.get_workspace(ws.workspace_id))
    assert completeness.status is CompletenessStatus.BLOCKED
    with pytest.raises(BlockingConflictError):
        assessment_platform.assessment_service.finalize_assessment(
            workspace_id=ws.workspace_id, actor=ASSESSOR)


def test_conflict_is_not_resolved_by_the_runtime(assessment_platform):
    """Recording a conflict never changes its status; the runtime cannot dispose it."""
    ws = _complete_workspace(assessment_platform)
    conflict = assessment_platform.assessment_service.record_conflict(
        workspace_id=ws.workspace_id, criterion_id="cap.python", sources=_SOURCES,
        severity=ConflictSeverity.HIGH, reason="contradiction", actor=ASSESSOR)
    from ugence_ai_hiring.rubrics.conflicts import ConflictStatus
    assert conflict.status is ConflictStatus.OPEN
