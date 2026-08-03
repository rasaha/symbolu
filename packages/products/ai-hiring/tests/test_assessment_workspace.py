"""Workspace creation resolves and pins the published evaluation constitution."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.assessments.status import WorkspaceStatus
from ugence_ai_hiring.errors import (
    CapabilityVersionMismatchError,
    PublishedRubricRequiredError,
)

from .conftest import ASSESSOR, SUBJECT, TENANT, make_assessment_rubric


def test_create_workspace_resolves_published_rubric(assessment_platform):
    make_assessment_rubric(assessment_platform)
    ws = assessment_platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    assert ws.status is WorkspaceStatus.EVIDENCE_BINDING
    assert ws.rubric_version == 1
    assert [b.criterion_id for b in ws.capability_bindings] == ["cap.python"]


def test_create_workspace_pins_capability_version(assessment_platform):
    make_assessment_rubric(assessment_platform)
    ws = assessment_platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    binding = ws.binding_for("cap.python")
    assert binding is not None
    assert binding.capability_version == 1
    assert binding.scoring_scale_id == "scale.1_5"
    assert binding.required is True  # minimum_count >= 1


def test_create_workspace_requires_a_published_rubric(assessment_platform):
    with pytest.raises(PublishedRubricRequiredError):
        assessment_platform.assessment_service.create_workspace(
            tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
            rubric_id="does-not-exist", created_by=ASSESSOR)


def test_create_workspace_rejects_unpublished_draft_rubric(assessment_platform):
    """A rubric that exists only as a draft must not be usable for assessment."""
    from .conftest import AUTHOR
    from ugence_ai_hiring.ontology import Capability, EvidenceType
    from ugence_ai_hiring.rubrics import EvidenceRule, Rubric, RubricCapability

    cap = Capability(
        capability_id="cap.python", name="Python", category="Programming",
        allowed_evidence_types=(EvidenceType.CODING_TEST,),
        required_evidence_types=(EvidenceType.CODING_TEST,), minimum_evidence_count=1)
    published = assessment_platform.ontology_service.publish(cap, actor_id=AUTHOR)
    rule = EvidenceRule(capability_id="cap.python",
                        allowed_types=(EvidenceType.CODING_TEST,), minimum_count=1)
    rc = RubricCapability(capability_id="cap.python",
                          capability_version=published.version, weight=1.0,
                          scoring_scale_id="scale.1_5", evidence_rule=rule)
    draft = Rubric(rubric_id="rub.draft", role="Backend", version=1,
                   capabilities=(rc,), default_scoring_scale_id="scale.1_5")
    assessment_platform.rubric_service.create(draft, author_id=AUTHOR)  # not published

    with pytest.raises(PublishedRubricRequiredError):
        assessment_platform.assessment_service.create_workspace(
            tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
            rubric_id="rub.draft", created_by=ASSESSOR)


def test_optional_criterion_is_not_required(assessment_platform):
    """minimum_count == 0 with no required types yields an optional criterion."""
    make_assessment_rubric(
        assessment_platform, minimum_count=0, required_types=())
    ws = assessment_platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    assert ws.binding_for("cap.python").required is False


def test_workspace_is_persisted_and_retrievable(assessment_platform):
    make_assessment_rubric(assessment_platform)
    ws = assessment_platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by=ASSESSOR)
    fetched = assessment_platform.assessment_service.get_workspace(ws.workspace_id)
    assert fetched.workspace_id == ws.workspace_id
    history = assessment_platform.assessment_workspace_repo.history(ws.workspace_id)
    assert len(history) == 1
