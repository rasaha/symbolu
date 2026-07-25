"""Evidence binding is deterministic, fail-closed, and criterion-specific.

Binding never *infers* relevance: the evidence type is declared by an authorized
caller and admissibility is decided by the published Phase-3A policy. Evidence
that is cross-tenant, off-subject, quarantined, or ineligible is refused; evidence
whose declared type is prohibited or unrecognized is recorded as excluded, not
bound.
"""

from __future__ import annotations

import pytest

from ai_hiring.ontology import EvidenceType
from ai_hiring.rubrics.evidence_rules import EvidenceAdmissibility
from ai_hiring.errors import (
    CrossTenantAssessmentAccessError,
    EvidenceNotEligibleForAssessmentError,
    QuarantinedEvidenceBindingError,
)

from .conftest import (
    ASSESSOR,
    SUBJECT,
    TENANT,
    ingest_evidence,
    make_assessment_rubric,
)


def _workspace(platform, **rubric_kw):
    make_assessment_rubric(platform, **rubric_kw)
    return platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)


def test_admissible_evidence_binds(assessment_platform):
    ws = _workspace(assessment_platform)
    evidence = ingest_evidence(assessment_platform)
    result = assessment_platform.assessment_service.bind_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        evidence_id=evidence.evidence_id, evidence_type=EvidenceType.CODING_TEST,
        bound_by=ASSESSOR)
    assert result.admissible is True
    assert result.binding.evidence_id == evidence.evidence_id
    assert result.binding.admissibility_outcome is EvidenceAdmissibility.ADMISSIBLE
    stored = assessment_platform.assessment_workspace_repo.list_bindings(ws.workspace_id)
    assert len(stored) == 1


def test_prohibited_declared_type_is_excluded_not_bound(assessment_platform):
    ws = _workspace(assessment_platform, prohibited_types=(EvidenceType.PHOTO,))
    evidence = ingest_evidence(assessment_platform)
    result = assessment_platform.assessment_service.bind_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        evidence_id=evidence.evidence_id, evidence_type=EvidenceType.PHOTO,
        bound_by=ASSESSOR)
    assert result.admissible is False
    assert result.exclusion.admissibility_outcome is EvidenceAdmissibility.PROHIBITED
    assert not assessment_platform.assessment_workspace_repo.list_bindings(ws.workspace_id)
    excluded = assessment_platform.assessment_workspace_repo.list_excluded(ws.workspace_id)
    assert len(excluded) == 1


def test_unrecognized_declared_type_is_excluded(assessment_platform):
    ws = _workspace(assessment_platform)  # allowed only CODING_TEST
    evidence = ingest_evidence(assessment_platform)
    result = assessment_platform.assessment_service.bind_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        evidence_id=evidence.evidence_id, evidence_type=EvidenceType.GITHUB,
        bound_by=ASSESSOR)
    assert result.admissible is False
    assert result.exclusion.admissibility_outcome is EvidenceAdmissibility.UNKNOWN


def test_cross_tenant_evidence_is_refused(assessment_platform):
    ws = _workspace(assessment_platform)
    foreign = ingest_evidence(assessment_platform, tenant_id="other-tenant")
    with pytest.raises(CrossTenantAssessmentAccessError):
        assessment_platform.assessment_service.bind_evidence(
            workspace_id=ws.workspace_id, criterion_id="cap.python",
            evidence_id=foreign.evidence_id, evidence_type=EvidenceType.CODING_TEST,
            bound_by=ASSESSOR)


def test_off_subject_evidence_is_refused(assessment_platform):
    ws = _workspace(assessment_platform)
    other = ingest_evidence(assessment_platform, candidate_id="someone-else")
    with pytest.raises(EvidenceNotEligibleForAssessmentError):
        assessment_platform.assessment_service.bind_evidence(
            workspace_id=ws.workspace_id, criterion_id="cap.python",
            evidence_id=other.evidence_id, evidence_type=EvidenceType.CODING_TEST,
            bound_by=ASSESSOR)


def test_unknown_evidence_is_refused(assessment_platform):
    ws = _workspace(assessment_platform)
    with pytest.raises(EvidenceNotEligibleForAssessmentError):
        assessment_platform.assessment_service.bind_evidence(
            workspace_id=ws.workspace_id, criterion_id="cap.python",
            evidence_id="ev-does-not-exist", evidence_type=EvidenceType.CODING_TEST,
            bound_by=ASSESSOR)


def test_non_job_relevant_evidence_is_refused(assessment_platform):
    """Quarantined / non-job-relevant evidence is a hard boundary, never bound."""
    from ai_hiring.domain.evidence import NormalizedEvidence

    ws = _workspace(assessment_platform)
    quarantined = NormalizedEvidence(
        evidence_id="ev-quarantined", candidate_id=SUBJECT, role_id="role-1",
        content_hash="h", job_relevant=False, tenant_id=TENANT)
    assessment_platform.evidence_repo.add(quarantined)
    with pytest.raises(QuarantinedEvidenceBindingError):
        assessment_platform.assessment_service.bind_evidence(
            workspace_id=ws.workspace_id, criterion_id="cap.python",
            evidence_id="ev-quarantined", evidence_type=EvidenceType.CODING_TEST,
            bound_by=ASSESSOR)


def test_binding_records_provenance_and_pins_versions(assessment_platform):
    ws = _workspace(assessment_platform)
    evidence = ingest_evidence(assessment_platform)
    result = assessment_platform.assessment_service.bind_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        evidence_id=evidence.evidence_id, evidence_type=EvidenceType.CODING_TEST,
        bound_by=ASSESSOR)
    binding = result.binding
    assert binding.capability_version == 1
    assert binding.evidence_version == evidence.version
    assert binding.bound_by == ASSESSOR
