"""Every state-changing assessment operation emits an append-only audit event."""

from __future__ import annotations

from ai_hiring.domain.enums import AuditEventType
from ai_hiring.assessments.status import SupplierType
from ai_hiring.ontology import EvidenceType
from ai_hiring.rubrics.conflicts import ConflictSeverity, ConflictSource
from ai_hiring.rubrics.evidence_rules import MissingEvidenceStatus
from ai_hiring.rubrics.scoring_scale import ScaleType

from .conftest import (
    ASSESSOR,
    SUBJECT,
    TENANT,
    ingest_evidence,
    make_assessment_rubric,
)


def _event_types(platform):
    return {e.event_type for e in platform.audit_repo.all()}


def test_lifecycle_emits_expected_audit_events(assessment_platform):
    svc = assessment_platform.assessment_service
    make_assessment_rubric(assessment_platform)
    ws = svc.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    evidence = ingest_evidence(assessment_platform)
    binding = svc.bind_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        evidence_id=evidence.evidence_id, evidence_type=EvidenceType.CODING_TEST,
        bound_by=ASSESSOR).binding
    svc.submit_observation(
        workspace_id=ws.workspace_id, criterion_id="cap.python", value="4",
        scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.HUMAN_ASSESSOR,
        supplied_by=ASSESSOR, evidence_binding_ids=(binding.binding_id,))
    svc.validate_assessment(workspace_id=ws.workspace_id, actor=ASSESSOR)
    svc.finalize_assessment(workspace_id=ws.workspace_id, actor=ASSESSOR)

    types = _event_types(assessment_platform)
    assert AuditEventType.ASSESSMENT_WORKSPACE_CREATED in types
    assert AuditEventType.ASSESSMENT_EVIDENCE_BOUND in types
    assert AuditEventType.ASSESSMENT_OBSERVATION_SUBMITTED in types
    assert AuditEventType.ASSESSMENT_VALIDATED in types
    assert AuditEventType.ASSESSMENT_FINALIZED_ADVISORY in types


def test_excluded_evidence_is_audited(assessment_platform):
    svc = assessment_platform.assessment_service
    make_assessment_rubric(assessment_platform, prohibited_types=(EvidenceType.PHOTO,))
    ws = svc.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    evidence = ingest_evidence(assessment_platform)
    svc.bind_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        evidence_id=evidence.evidence_id, evidence_type=EvidenceType.PHOTO,
        bound_by=ASSESSOR)
    assert AuditEventType.ASSESSMENT_EVIDENCE_EXCLUDED in _event_types(assessment_platform)


def test_rejected_observation_is_audited(assessment_platform):
    svc = assessment_platform.assessment_service
    make_assessment_rubric(assessment_platform)
    ws = svc.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    evidence = ingest_evidence(assessment_platform)
    binding = svc.bind_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        evidence_id=evidence.evidence_id, evidence_type=EvidenceType.CODING_TEST,
        bound_by=ASSESSOR).binding
    try:
        svc.submit_observation(
            workspace_id=ws.workspace_id, criterion_id="cap.python", value="99",
            scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.HUMAN_ASSESSOR,
            supplied_by=ASSESSOR, evidence_binding_ids=(binding.binding_id,))
    except Exception:
        pass
    assert AuditEventType.ASSESSMENT_OBSERVATION_REJECTED in _event_types(assessment_platform)


def test_missing_and_conflict_events_are_recorded(assessment_platform):
    svc = assessment_platform.assessment_service
    make_assessment_rubric(assessment_platform)
    ws = svc.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    svc.record_missing_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        status=MissingEvidenceStatus.NOT_SUBMITTED, actor=ASSESSOR)
    svc.record_conflict(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        sources=(ConflictSource(source_ref="a", claim="x"),
                 ConflictSource(source_ref="b", claim="y")),
        severity=ConflictSeverity.LOW, reason="disagreement", actor=ASSESSOR)
    types = _event_types(assessment_platform)
    assert AuditEventType.ASSESSMENT_MISSING_EVIDENCE_RECORDED in types
    assert AuditEventType.ASSESSMENT_CONFLICT_RECORDED in types


def test_audit_events_carry_the_workspace_correlation_id(assessment_platform):
    svc = assessment_platform.assessment_service
    make_assessment_rubric(assessment_platform)
    ws = svc.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    events = [e for e in assessment_platform.audit_repo.all()
              if e.event_type is AuditEventType.ASSESSMENT_WORKSPACE_CREATED]
    assert events and events[0].correlation_id == ws.correlation_id
