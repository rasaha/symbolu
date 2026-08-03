"""Observations are validated against the published scale — never interpreted.

The runtime accepts an *externally supplied* observation value and checks that it
conforms to the published contract (scale membership, declared-scale match,
authorized supplier, evidence sufficiency, permitted reason codes). It never
computes, infers, or adjusts the value. AI-supplied observations are prohibited
in Phase 3B.
"""

from __future__ import annotations

import pytest

from ugence_ai_hiring.assessments.status import SupplierType
from ugence_ai_hiring.errors import (
    AIObservationNotAllowedError,
    ObservationScaleMismatchError,
    ObservationValidationError,
    ObservationValueOutOfRangeError,
)
from ugence_ai_hiring.ontology import EvidenceType
from ugence_ai_hiring.rubrics.scoring_scale import ScaleType

from .conftest import (
    ASSESSOR,
    SUBJECT,
    TENANT,
    ingest_evidence,
    make_assessment_rubric,
)


def _bound_workspace(platform, **rubric_kw):
    """A workspace with one admissible binding on cap.python, returned with its id."""
    make_assessment_rubric(platform, **rubric_kw)
    ws = platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    evidence = ingest_evidence(platform)
    result = platform.assessment_service.bind_evidence(
        workspace_id=ws.workspace_id, criterion_id="cap.python",
        evidence_id=evidence.evidence_id, evidence_type=EvidenceType.CODING_TEST,
        bound_by=ASSESSOR)
    return ws, (result.binding.binding_id,)


def test_valid_observation_is_accepted(assessment_platform):
    ws, bindings = _bound_workspace(assessment_platform)
    obs = assessment_platform.assessment_service.submit_observation(
        workspace_id=ws.workspace_id, criterion_id="cap.python", value="4",
        scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.HUMAN_ASSESSOR,
        supplied_by=ASSESSOR, evidence_binding_ids=bindings)
    assert obs.value == "4"
    assert obs.supplier_type is SupplierType.HUMAN_ASSESSOR


def test_out_of_range_value_is_rejected(assessment_platform):
    ws, bindings = _bound_workspace(assessment_platform)
    with pytest.raises(ObservationValueOutOfRangeError):
        assessment_platform.assessment_service.submit_observation(
            workspace_id=ws.workspace_id, criterion_id="cap.python", value="9",
            scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.HUMAN_ASSESSOR,
            supplied_by=ASSESSOR, evidence_binding_ids=bindings)


def test_non_integer_value_is_rejected(assessment_platform):
    ws, bindings = _bound_workspace(assessment_platform)
    with pytest.raises(ObservationValueOutOfRangeError):
        assessment_platform.assessment_service.submit_observation(
            workspace_id=ws.workspace_id, criterion_id="cap.python", value="3.5",
            scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.HUMAN_ASSESSOR,
            supplied_by=ASSESSOR, evidence_binding_ids=bindings)


def test_declared_scale_must_match_published_scale(assessment_platform):
    ws, bindings = _bound_workspace(assessment_platform)
    with pytest.raises(ObservationScaleMismatchError):
        assessment_platform.assessment_service.submit_observation(
            workspace_id=ws.workspace_id, criterion_id="cap.python", value="PASS",
            scale_type=ScaleType.PASS_FAIL, supplier_type=SupplierType.HUMAN_ASSESSOR,
            supplied_by=ASSESSOR, evidence_binding_ids=bindings)


def test_ai_supplied_observation_is_prohibited(assessment_platform):
    """The core Phase-3B boundary: no AI system may supply an observation."""
    ws, bindings = _bound_workspace(assessment_platform)
    # An AI principal that somehow held a grant still cannot supply — the supplier
    # *type* is rejected deterministically before the value is even considered.
    from ugence_ai_hiring.policies.evidence_access_policy import AccessGrant, Permission
    assessment_platform.access_grants.add(
        AccessGrant("ai-observer", TENANT, frozenset(Permission)))
    with pytest.raises(AIObservationNotAllowedError):
        assessment_platform.assessment_service.submit_observation(
            workspace_id=ws.workspace_id, criterion_id="cap.python", value="4",
            scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.AI_MODEL,
            supplied_by="ai-observer", evidence_binding_ids=bindings)


def test_missing_required_evidence_blocks_observation(assessment_platform):
    """Even a well-formed value fails if the required evidence isn't bound."""
    make_assessment_rubric(assessment_platform, minimum_count=1)
    ws = assessment_platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    with pytest.raises(ObservationValidationError):
        assessment_platform.assessment_service.submit_observation(
            workspace_id=ws.workspace_id, criterion_id="cap.python", value="4",
            scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.HUMAN_ASSESSOR,
            supplied_by=ASSESSOR, evidence_binding_ids=())


def test_explanation_reference_does_not_substitute_for_evidence(assessment_platform):
    make_assessment_rubric(assessment_platform, minimum_count=1)
    ws = assessment_platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    with pytest.raises(ObservationValidationError):
        assessment_platform.assessment_service.submit_observation(
            workspace_id=ws.workspace_id, criterion_id="cap.python", value="4",
            scale_type=ScaleType.ONE_TO_FIVE, supplier_type=SupplierType.HUMAN_ASSESSOR,
            supplied_by=ASSESSOR, evidence_binding_ids=(),
            explanation_reference="see my notes")


def test_deterministic_system_may_supply_observation(assessment_platform):
    """A deterministic scoring system is a permitted supplier (unlike an AI model)."""
    ws, bindings = _bound_workspace(assessment_platform)
    obs = assessment_platform.assessment_service.submit_observation(
        workspace_id=ws.workspace_id, criterion_id="cap.python", value="5",
        scale_type=ScaleType.ONE_TO_FIVE,
        supplier_type=SupplierType.DETERMINISTIC_SYSTEM, supplied_by=ASSESSOR,
        evidence_binding_ids=bindings)
    assert obs.supplier_type is SupplierType.DETERMINISTIC_SYSTEM
