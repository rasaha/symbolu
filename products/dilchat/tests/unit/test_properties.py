"""Property-based tests (Hypothesis) for calculation and authorization invariants."""

from __future__ import annotations

import uuid

from hypothesis import given
from hypothesis import strategies as st

from ugence_dilchat.astrology.derivation import derive_moon, normalize_longitude
from ugence_dilchat.domain.enums import MembershipStatus, Scope
from ugence_dilchat.security.scope import Decision, MembershipFact, authorize

_lon = st.floats(min_value=-10_000, max_value=10_000, allow_nan=False, allow_infinity=False)


@given(_lon)
def test_normalized_longitude_always_in_range(x):
    v = normalize_longitude(x)
    assert 0.0 <= v < 360.0


@given(_lon)
def test_derivation_indices_always_in_range(x):
    d = derive_moon(x)
    assert 0 <= d.rashi_index <= 11
    assert 0 <= d.nakshatra_index <= 26
    assert 1 <= d.pada <= 4
    assert 0.0 <= d.longitude < 360.0


@given(st.floats(min_value=0.0, max_value=359.999999, allow_nan=False))
def test_derivation_is_deterministic(x):
    assert derive_moon(x) == derive_moon(x)


@given(st.uuids(), st.uuids())
def test_private_cross_access_is_never_allowed_for_non_owner(a, b):
    if a == b:
        return
    r = authorize(a, Scope.PRIVATE_A, resource_owner_user_id=b)
    assert r.decision is Decision.DENY_NOT_FOUND
    assert not r.allowed


@given(st.sampled_from(list(MembershipStatus) + [None]))
def test_shared_allowed_iff_active(status):
    couple = uuid.uuid4()
    fact = None if status is None else MembershipFact(couple, status)
    r = authorize(uuid.uuid4(), Scope.SHARED, membership=fact)
    assert r.allowed == (status is MembershipStatus.ACTIVE)
