"""H1 — candidate identity & profile tests."""

from __future__ import annotations

import pytest

from ai_hiring.candidates.candidate import CandidateProfile, CandidateStatus
from ai_hiring.errors import (
    CandidateNotFoundError,
    CrossTenantHiringAccessError,
    IllegalCandidateTransitionError,
)
from ai_hiring.tests.h1_helpers import build_env, ctx


def test_register_candidate_maps_to_subject():
    env = build_env(); c = ctx()
    cand = env.candidate_service.register_candidate(c, subject_id="subj1", candidate_id="c1")
    assert cand.subject_id == "subj1" and cand.status == CandidateStatus.ACTIVE
    assert cand.tenant_id == "t1"


def test_revise_profile_creates_new_version():
    env = build_env(); c = ctx()
    env.candidate_service.register_candidate(c, subject_id="subj1", candidate_id="c1")
    updated = env.candidate_service.revise_profile(c, "c1", CandidateProfile(display_name="Alex"))
    assert updated.version == 2 and updated.profile.display_name == "Alex"
    assert [r.version for r in env.cands.history("c1")] == [1, 2]


def test_withdraw_candidate_and_block_further_revision():
    env = build_env(); c = ctx()
    env.candidate_service.register_candidate(c, subject_id="subj1", candidate_id="c1")
    wd = env.candidate_service.withdraw_candidate(c, "c1")
    assert wd.status == CandidateStatus.WITHDRAWN
    with pytest.raises(IllegalCandidateTransitionError):
        env.candidate_service.revise_profile(c, "c1", CandidateProfile(display_name="X"))
    with pytest.raises(IllegalCandidateTransitionError):
        env.candidate_service.withdraw_candidate(c, "c1")  # already withdrawn


def test_candidate_not_found():
    env = build_env(); c = ctx()
    with pytest.raises(CandidateNotFoundError):
        env.candidate_service.revise_profile(c, "missing", CandidateProfile())


def test_cross_tenant_candidate_access_denied():
    env = build_env()
    owner, intruder = ctx(tenant="t1"), ctx(tenant="t2")
    env.candidate_service.register_candidate(owner, subject_id="subj1", candidate_id="c1")
    with pytest.raises(CrossTenantHiringAccessError):
        env.candidate_service.withdraw_candidate(intruder, "c1")


def test_duplicate_profile_attribute_key_rejected():
    from ai_hiring.errors import DomainValidationError
    with pytest.raises(DomainValidationError):
        CandidateProfile(attributes=(("k", "1"), ("k", "2")))
