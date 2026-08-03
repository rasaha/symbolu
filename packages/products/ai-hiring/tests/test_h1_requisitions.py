"""H1 — requisition & job-definition lifecycle tests."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.errors import (
    CrossTenantHiringAccessError,
    IllegalJobDefinitionTransitionError,
    IllegalRequisitionTransitionError,
    RequisitionNotFoundError,
    VersionConflictError,
)
from ugence_ai_hiring.requisitions.status import JobDefinitionStatus, RequisitionStatus
from .h1_helpers import build_env, ctx


def test_create_and_open_requisition_valid_flow():
    env = build_env()
    c = ctx()
    req = env.requisition_service.create_requisition(c, title="Engineer", requisition_id="req1")
    assert req.status == RequisitionStatus.DRAFT and req.version == 1
    opened = env.requisition_service.open_requisition(c, "req1")
    assert opened.status == RequisitionStatus.OPEN and opened.version == 2
    # persisted history reflects both versions immutably
    hist = env.reqs.history("req1")
    assert [r.version for r in hist] == [1, 2]
    assert [r.status for r in hist] == [RequisitionStatus.DRAFT, RequisitionStatus.OPEN]


def test_full_requisition_lifecycle_open_hold_resume_fill():
    env = build_env(); c = ctx()
    env.requisition_service.create_requisition(c, title="E", requisition_id="req1")
    env.requisition_service.open_requisition(c, "req1")
    env.requisition_service.hold_requisition(c, "req1")
    env.requisition_service.resume_requisition(c, "req1")
    filled = env.requisition_service.fill_requisition(c, "req1")
    assert filled.status == RequisitionStatus.FILLED


def test_invalid_requisition_transition_rejected():
    env = build_env(); c = ctx()
    env.requisition_service.create_requisition(c, title="E", requisition_id="req1")
    # DRAFT -> FILLED is illegal
    with pytest.raises(IllegalRequisitionTransitionError):
        env.requisition_service.fill_requisition(c, "req1")


def test_terminal_requisition_admits_no_transition():
    env = build_env(); c = ctx()
    env.requisition_service.create_requisition(c, title="E", requisition_id="req1")
    env.requisition_service.open_requisition(c, "req1")
    env.requisition_service.cancel_requisition(c, "req1")
    with pytest.raises(IllegalRequisitionTransitionError):
        env.requisition_service.open_requisition(c, "req1")


def test_requisition_not_found():
    env = build_env(); c = ctx()
    with pytest.raises(RequisitionNotFoundError):
        env.requisition_service.open_requisition(c, "missing")


def test_cross_tenant_requisition_access_denied_and_audited():
    env = build_env()
    owner, intruder = ctx(tenant="t1"), ctx(tenant="t2", actor="mallory")
    env.requisition_service.create_requisition(owner, title="E", requisition_id="req1")
    with pytest.raises(CrossTenantHiringAccessError):
        env.requisition_service.open_requisition(intruder, "req1")
    # the denial is recorded on the domain audit trail
    denials = [e for e in env.audit_repo.all_events()
               if e.event_type.value == "DOMAIN_ACCESS_DENIED" and e.entity_id == "req1"]
    assert denials and denials[0].tenant_id == "t2"


def test_job_definition_publish_and_retire():
    env = build_env(); c = ctx()
    env.requisition_service.create_requisition(c, title="E", requisition_id="req1")
    env.requisition_service.open_requisition(c, "req1")
    jd = env.requisition_service.draft_job_definition(
        c, requisition_id="req1", rubric_id="rb1", rubric_version=1,
        required_evidence_types=("resume",), job_definition_id="jd1")
    assert jd.status == JobDefinitionStatus.DRAFT
    pub = env.requisition_service.publish_job_definition(c, "jd1")
    assert pub.is_published
    ret = env.requisition_service.retire_job_definition(c, "jd1")
    assert ret.status == JobDefinitionStatus.RETIRED
    with pytest.raises(IllegalJobDefinitionTransitionError):
        env.requisition_service.publish_job_definition(c, "jd1")  # RETIRED -> PUBLISHED illegal


def test_immutability_version_conflict_on_readd():
    env = build_env(); c = ctx()
    req = env.requisition_service.create_requisition(c, title="E", requisition_id="req1")
    with pytest.raises(VersionConflictError):
        env.reqs.add(req)  # re-adding (id, version) must not overwrite
