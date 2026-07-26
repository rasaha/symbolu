"""H1 — evidence-collection intake & provenance binding tests."""

from __future__ import annotations

import pytest

from ai_hiring.errors import ApplicationNotFoundError, CrossTenantHiringAccessError
from ai_hiring.intake.intake import EvidenceProvenance, IntakeSource
from ai_hiring.tests.h1_helpers import build_env, ctx, open_requisition_with_published_def


def _prov():
    return EvidenceProvenance(source=IntakeSource.RECRUITER_UPLOAD, collected_by="recruiter1",
                              source_ref="ats://123")


def _application(env, c):
    open_requisition_with_published_def(env, c, required_evidence_types=("resume",))
    env.candidate_service.register_candidate(c, subject_id="s1", candidate_id="c1")
    env.application_service.submit_application(
        c, candidate_id="c1", requisition_id="req1", job_definition_id="jd1", application_id="a1")


def test_intake_binds_provenance_and_application_context():
    env = build_env(); c = ctx()
    _application(env, c)
    item = env.intake_service.intake_evidence(
        c, application_id="a1", evidence_type="resume", content_hash="deadbeef",
        provenance=_prov(), intake_id="i1")
    assert item.application_id == "a1" and item.candidate_id == "c1" and item.requisition_id == "req1"
    assert item.provenance.source == IntakeSource.RECRUITER_UPLOAD
    assert item.content_hash == "deadbeef"
    # coverage index reflects the collected type
    assert env.intake.evidence_types_for_application("a1") == frozenset({"resume"})


def test_intake_records_two_audit_events_received_and_provenance_bound():
    env = build_env(); c = ctx()
    _application(env, c)
    env.intake_service.intake_evidence(c, application_id="a1", evidence_type="resume",
                                       content_hash="h", provenance=_prov(), intake_id="i1")
    kinds = [e.event_type.value for e in env.audit_repo.events_for("evidence_intake", "i1")]
    assert kinds == ["EVIDENCE_INTAKE_RECEIVED", "EVIDENCE_INTAKE_PROVENANCE_BOUND"]


def test_intake_requires_existing_application():
    env = build_env(); c = ctx()
    with pytest.raises(ApplicationNotFoundError):
        env.intake_service.intake_evidence(c, application_id="missing", evidence_type="resume",
                                           content_hash="h", provenance=_prov())


def test_intake_cross_tenant_denied():
    env = build_env()
    owner, intruder = ctx(tenant="t1"), ctx(tenant="t2")
    _application(env, owner)
    with pytest.raises(CrossTenantHiringAccessError):
        env.intake_service.intake_evidence(intruder, application_id="a1", evidence_type="resume",
                                           content_hash="h", provenance=_prov())


def test_provenance_requires_collector():
    from ai_hiring.errors import DomainValidationError
    with pytest.raises(DomainValidationError):
        EvidenceProvenance(source=IntakeSource.SYSTEM_COLLECTED, collected_by="")
