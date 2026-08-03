"""Rubric approval-workflow tests."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.domain.enums import AuditEventType
from ugence_ai_hiring.errors import (
    ApprovalError,
    InvalidLifecycleTransitionError,
    RubricValidationError,
)
from ugence_ai_hiring.rubrics import RubricStatus

from .conftest import (
    APPROVER,
    AUTHOR,
    PUBLISHER,
    make_rubric,
    publish_capability,
    publish_rubric,
)


def test_full_lifecycle(platform):
    publish_capability(platform, "cap.python")
    published = publish_rubric(platform, make_rubric("cap.python"))
    assert published.status is RubricStatus.PUBLISHED
    # author, submit, approve, publish -> 4 approval records
    actions = [a.action.value for a in published.approvals]
    assert actions == ["CREATE", "SUBMIT", "APPROVE", "PUBLISH"]


def test_only_published_is_evaluation_usable(platform):
    publish_capability(platform, "cap.python")
    platform.rubric_service.create(make_rubric("cap.python"), author_id=AUTHOR)
    assert platform.rubric_service.get_published("rub.be") is None
    publish_rubric(platform, make_rubric("cap.python", rubric_id="rub.be2"))
    assert platform.rubric_service.get_published("rub.be2") is not None


def test_segregation_of_duties_approver(platform):
    publish_capability(platform, "cap.python")
    platform.rubric_service.create(make_rubric("cap.python"), author_id=AUTHOR)
    platform.rubric_service.submit("rub.be", author_id=AUTHOR)
    with pytest.raises(ApprovalError):
        platform.rubric_service.approve("rub.be", approver_id=AUTHOR)  # author == approver


def test_invalid_transition_rejected(platform):
    publish_capability(platform, "cap.python")
    platform.rubric_service.create(make_rubric("cap.python"), author_id=AUTHOR)
    # cannot publish straight from DRAFT
    with pytest.raises(InvalidLifecycleTransitionError):
        platform.rubric_service.publish("rub.be", publisher_id=PUBLISHER)


def test_publish_requires_valid_contract(platform):
    # capability never published -> validation fails at publish
    platform.rubric_service.create(make_rubric("cap.ghost"), author_id=AUTHOR)
    platform.rubric_service.submit("rub.be", author_id=AUTHOR)
    platform.rubric_service.approve("rub.be", approver_id=APPROVER)
    with pytest.raises(RubricValidationError):
        platform.rubric_service.publish("rub.be", publisher_id=PUBLISHER)
    assert any(e.event_type is AuditEventType.RUBRIC_VALIDATION_FAILED
               for e in platform.audit_repo.all())


def test_reject_sends_back_to_draft(platform):
    publish_capability(platform, "cap.python")
    platform.rubric_service.create(make_rubric("cap.python"), author_id=AUTHOR)
    platform.rubric_service.submit("rub.be", author_id=AUTHOR)
    back = platform.rubric_service.reject("rub.be", reviewer_id=APPROVER, note="needs work")
    assert back.status is RubricStatus.DRAFT


def test_deprecate_and_retire(platform):
    publish_capability(platform, "cap.python")
    publish_rubric(platform, make_rubric("cap.python"))
    dep = platform.rubric_service.deprecate("rub.be", publisher_id=PUBLISHER)
    assert dep.status is RubricStatus.DEPRECATED
    ret = platform.rubric_service.retire("rub.be", publisher_id=PUBLISHER)
    assert ret.status is RubricStatus.RETIRED


def test_revision_creates_new_version(platform):
    publish_capability(platform, "cap.python")
    publish_rubric(platform, make_rubric("cap.python"))
    revised = platform.rubric_service.create_revision(
        "rub.be", make_rubric("cap.python", rubric_id="rub.be"), author_id=AUTHOR)
    assert revised.version == 2 and revised.status is RubricStatus.DRAFT
    assert revised.supersedes == "rub.be"


def test_workflow_audit_events(platform):
    publish_capability(platform, "cap.python")
    publish_rubric(platform, make_rubric("cap.python"))
    types = {e.event_type for e in platform.audit_repo.all()}
    for required in (AuditEventType.RUBRIC_CREATED, AuditEventType.RUBRIC_SUBMITTED,
                     AuditEventType.RUBRIC_APPROVED, AuditEventType.RUBRIC_PUBLISHED):
        assert required in types


def test_history_is_append_only(platform):
    publish_capability(platform, "cap.python")
    publish_rubric(platform, make_rubric("cap.python"))
    history = platform.rubric_service.history("rub.be")
    statuses = [r.status for r in history]
    assert statuses == [RubricStatus.DRAFT, RubricStatus.UNDER_REVIEW,
                        RubricStatus.APPROVED, RubricStatus.PUBLISHED]
