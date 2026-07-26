"""H1 — application lifecycle, eligibility, duplicate prevention, readiness."""

from __future__ import annotations

import pytest

from ai_hiring.errors import (
    ApplicationNotFoundError,
    CrossTenantHiringAccessError,
    DuplicateApplicationError,
    IllegalApplicationTransitionError,
    IneligibleApplicationError,
    NotReadyForAssessmentError,
)
from ai_hiring.hiring_applications.status import ApplicationStatus
from ai_hiring.intake.intake import EvidenceProvenance, IntakeSource
from ai_hiring.tests.h1_helpers import build_env, ctx, open_requisition_with_published_def


def _prov(collected_by="recruiter1"):
    return EvidenceProvenance(source=IntakeSource.CANDIDATE_SUBMISSION, collected_by=collected_by)


def _ready_application(env, c, evidence=("resume", "code_sample")):
    open_requisition_with_published_def(env, c, required_evidence_types=evidence)
    env.candidate_service.register_candidate(c, subject_id="subj1", candidate_id="c1")
    app = env.application_service.submit_application(
        c, candidate_id="c1", requisition_id="req1", job_definition_id="jd1", application_id="a1")
    env.application_service.start_screening(c, "a1")
    for et in evidence:
        env.intake_service.intake_evidence(c, application_id="a1", evidence_type=et,
                                            content_hash=f"h_{et}", provenance=_prov())
    return app


def test_submit_valid_application():
    env = build_env(); c = ctx()
    open_requisition_with_published_def(env, c)
    env.candidate_service.register_candidate(c, subject_id="subj1", candidate_id="c1")
    app = env.application_service.submit_application(
        c, candidate_id="c1", requisition_id="req1", job_definition_id="jd1", application_id="a1")
    assert app.status == ApplicationStatus.RECEIVED
    assert app.job_definition_version >= 1


def test_ineligible_when_requisition_not_open():
    env = build_env(); c = ctx()
    # create + draft/publish but DO NOT open the requisition
    env.requisition_service.create_requisition(c, title="E", requisition_id="req1")
    env.requisition_service.draft_job_definition(
        c, requisition_id="req1", rubric_id="rb1", rubric_version=1,
        required_evidence_types=("resume",), job_definition_id="jd1")
    env.requisition_service.publish_job_definition(c, "jd1")
    env.candidate_service.register_candidate(c, subject_id="s1", candidate_id="c1")
    with pytest.raises(IneligibleApplicationError) as ei:
        env.application_service.submit_application(
            c, candidate_id="c1", requisition_id="req1", job_definition_id="jd1")
    assert "requisition_not_open" in str(ei.value)


def test_ineligible_when_job_definition_unpublished():
    env = build_env(); c = ctx()
    env.requisition_service.create_requisition(c, title="E", requisition_id="req1")
    env.requisition_service.open_requisition(c, "req1")
    env.requisition_service.draft_job_definition(
        c, requisition_id="req1", rubric_id="rb1", rubric_version=1, job_definition_id="jd1")
    env.candidate_service.register_candidate(c, subject_id="s1", candidate_id="c1")
    with pytest.raises(IneligibleApplicationError):
        env.application_service.submit_application(
            c, candidate_id="c1", requisition_id="req1", job_definition_id="jd1")


def test_ineligible_when_candidate_withdrawn():
    env = build_env(); c = ctx()
    open_requisition_with_published_def(env, c)
    env.candidate_service.register_candidate(c, subject_id="s1", candidate_id="c1")
    env.candidate_service.withdraw_candidate(c, "c1")
    with pytest.raises(IneligibleApplicationError):
        env.application_service.submit_application(
            c, candidate_id="c1", requisition_id="req1", job_definition_id="jd1")


def test_duplicate_active_application_prevented():
    env = build_env(); c = ctx()
    open_requisition_with_published_def(env, c)
    env.candidate_service.register_candidate(c, subject_id="s1", candidate_id="c1")
    env.application_service.submit_application(
        c, candidate_id="c1", requisition_id="req1", job_definition_id="jd1", application_id="a1")
    with pytest.raises(DuplicateApplicationError):
        env.application_service.submit_application(
            c, candidate_id="c1", requisition_id="req1", job_definition_id="jd1")


def test_reapplication_allowed_after_prior_terminal():
    env = build_env(); c = ctx()
    open_requisition_with_published_def(env, c)
    env.candidate_service.register_candidate(c, subject_id="s1", candidate_id="c1")
    env.application_service.submit_application(
        c, candidate_id="c1", requisition_id="req1", job_definition_id="jd1", application_id="a1")
    env.application_service.withdraw_application(c, "a1")  # terminal
    # a new application is now allowed (no active duplicate)
    app2 = env.application_service.submit_application(
        c, candidate_id="c1", requisition_id="req1", job_definition_id="jd1", application_id="a2")
    assert app2.application_id == "a2"


def test_incomplete_evidence_blocks_assessment():
    env = build_env(); c = ctx()
    open_requisition_with_published_def(env, c, required_evidence_types=("resume", "code_sample"))
    env.candidate_service.register_candidate(c, subject_id="s1", candidate_id="c1")
    env.application_service.submit_application(
        c, candidate_id="c1", requisition_id="req1", job_definition_id="jd1", application_id="a1")
    env.application_service.start_screening(c, "a1")
    env.intake_service.intake_evidence(c, application_id="a1", evidence_type="resume",
                                       content_hash="h1", provenance=_prov())
    readiness = env.application_service.check_readiness(c, "a1")
    assert not readiness.ready and readiness.missing_evidence_types == ("code_sample",)
    with pytest.raises(NotReadyForAssessmentError):
        env.application_service.advance_to_assessment(c, "a1")


def test_full_lifecycle_when_ready():
    env = build_env(); c = ctx()
    _ready_application(env, c)
    env.application_service.advance_to_assessment(c, "a1")
    env.application_service.advance_to_review(c, "a1")
    closed = env.application_service.close_application(c, "a1")
    assert closed.status == ApplicationStatus.CLOSED
    assert [a.status for a in env.apps.history("a1")] == [
        ApplicationStatus.RECEIVED, ApplicationStatus.SCREENING, ApplicationStatus.ASSESSMENT,
        ApplicationStatus.IN_REVIEW, ApplicationStatus.CLOSED,
    ]


def test_invalid_application_transition_rejected():
    env = build_env(); c = ctx()
    _ready_application(env, c)
    # RECEIVED already advanced to SCREENING in helper; jumping SCREENING->IN_REVIEW is illegal
    with pytest.raises(IllegalApplicationTransitionError):
        env.application_service.advance_to_review(c, "a1")


def test_withdraw_from_any_active_state():
    env = build_env(); c = ctx()
    _ready_application(env, c)
    wd = env.application_service.withdraw_application(c, "a1")
    assert wd.status == ApplicationStatus.WITHDRAWN
    with pytest.raises(IllegalApplicationTransitionError):
        env.application_service.close_application(c, "a1")  # terminal


def test_application_not_found():
    env = build_env(); c = ctx()
    with pytest.raises(ApplicationNotFoundError):
        env.application_service.close_application(c, "missing")


def test_cross_tenant_application_isolation():
    env = build_env()
    owner, intruder = ctx(tenant="t1"), ctx(tenant="t2")
    open_requisition_with_published_def(env, owner)
    env.candidate_service.register_candidate(owner, subject_id="s1", candidate_id="c1")
    env.application_service.submit_application(
        owner, candidate_id="c1", requisition_id="req1", job_definition_id="jd1", application_id="a1")
    with pytest.raises(CrossTenantHiringAccessError):
        env.application_service.start_screening(intruder, "a1")
    with pytest.raises(CrossTenantHiringAccessError):
        env.application_service.check_readiness(intruder, "a1")
