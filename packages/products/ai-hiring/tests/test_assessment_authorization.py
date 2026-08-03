"""Every assessment operation is authorized and fail-closed; denials are audited."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.domain.enums import AuditEventType
from ugence_ai_hiring.errors import AssessmentAuthorizationError
from ugence_ai_hiring.policies.evidence_access_policy import AccessGrant, Permission

from .conftest import ASSESSOR, SUBJECT, TENANT, make_assessment_rubric


def test_unauthenticated_actor_cannot_create_workspace(assessment_platform):
    make_assessment_rubric(assessment_platform)
    with pytest.raises(AssessmentAuthorizationError):
        assessment_platform.assessment_service.create_workspace(
            tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
            rubric_id="rub.assess", created_by="ghost-not-registered")


def test_authenticated_actor_without_grant_is_denied(assessment_platform):
    """assessor-2 is a registered human but holds no grant in the tenant."""
    make_assessment_rubric(assessment_platform)
    with pytest.raises(AssessmentAuthorizationError):
        assessment_platform.assessment_service.create_workspace(
            tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
            rubric_id="rub.assess", created_by="assessor-2")


def test_cross_tenant_grant_does_not_authorize(assessment_platform):
    """A grant in another tenant must not authorize actions in TENANT."""
    make_assessment_rubric(assessment_platform)
    assessment_platform.access_grants.add(
        AccessGrant("assessor-2", "other-tenant", frozenset(Permission)))
    with pytest.raises(AssessmentAuthorizationError):
        assessment_platform.assessment_service.create_workspace(
            tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
            rubric_id="rub.assess", created_by="assessor-2")


def test_missing_specific_permission_is_denied(assessment_platform):
    """A grant that lacks FINALIZE_ASSESSMENT cannot finalize."""
    make_assessment_rubric(assessment_platform)
    # assessor-2 may create workspaces but not finalize.
    assessment_platform.access_grants.add(AccessGrant(
        "assessor-2", TENANT, frozenset({Permission.CREATE_ASSESSMENT_WORKSPACE})))
    ws = assessment_platform.assessment_service.create_workspace(
        tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
        rubric_id="rub.assess", created_by="assessor-2")
    with pytest.raises(AssessmentAuthorizationError):
        assessment_platform.assessment_service.finalize_assessment(
            workspace_id=ws.workspace_id, actor="assessor-2")


def test_denied_access_is_audited(assessment_platform):
    make_assessment_rubric(assessment_platform)
    with pytest.raises(AssessmentAuthorizationError):
        assessment_platform.assessment_service.create_workspace(
            tenant_id=TENANT, subject_id=SUBJECT, decision_type="hire",
            rubric_id="rub.assess", created_by="assessor-2")
    events = [e for e in assessment_platform.audit_repo.all()
              if e.event_type is AuditEventType.ASSESSMENT_ACCESS_DENIED]
    assert events, "expected an ASSESSMENT_ACCESS_DENIED audit event"
