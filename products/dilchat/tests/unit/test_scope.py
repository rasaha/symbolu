"""Unit tests for the pure three-scope authorization decision function."""

from __future__ import annotations

import uuid

from ugence_dilchat.domain.enums import MembershipStatus, Scope
from ugence_dilchat.security.scope import (
    Decision,
    MembershipFact,
    authorize,
    authorize_job_write,
    authorize_private,
    authorize_shared,
)

A = uuid.uuid4()
B = uuid.uuid4()
COUPLE = uuid.uuid4()


def test_owner_can_access_own_private():
    assert authorize_private(A, A).decision is Decision.ALLOW


def test_cross_private_is_not_found_not_forbidden():
    r = authorize_private(A, B)
    assert r.decision is Decision.DENY_NOT_FOUND  # existence non-disclosure
    assert not r.allowed


def test_shared_requires_active_membership():
    active = MembershipFact(COUPLE, MembershipStatus.ACTIVE)
    assert authorize_shared(active).decision is Decision.ALLOW


def test_shared_non_member_is_not_found():
    assert authorize_shared(None).decision is Decision.DENY_NOT_FOUND
    assert authorize_shared(MembershipFact(COUPLE, None)).decision is Decision.DENY_NOT_FOUND


def test_shared_revoked_member_is_forbidden():
    revoked = MembershipFact(COUPLE, MembershipStatus.REVOKED)
    r = authorize_shared(revoked)
    assert r.decision is Decision.DENY_FORBIDDEN
    assert r.reason_code == "COUPLE_NOT_ACTIVE"


def test_unified_authorize_default_deny_on_missing_owner():
    r = authorize(A, Scope.PRIVATE_A, resource_owner_user_id=None)
    assert r.decision is Decision.DENY_NOT_FOUND


def test_job_write_revoked_scope_denied_with_distinct_reason():
    revoked = MembershipFact(COUPLE, MembershipStatus.REVOKED)
    r = authorize_job_write(revoked)
    assert not r.allowed
    assert r.reason_code == "JOB_WRITE_SCOPE_REVOKED"


def test_job_write_active_allowed():
    active = MembershipFact(COUPLE, MembershipStatus.ACTIVE)
    assert authorize_job_write(active).allowed
