"""Role grants: the window, revocation, and the rule that a grant outside its
window is **absent** from every answer rather than reported with a flag.

Every case runs against both adapters, so the durable store and the reference store
cannot drift apart.
"""

from __future__ import annotations

import pytest

from ugence_governance_contracts.api import Validity, ValidityStatus

from ugence_authority_directory import (
    ContractViolation,
    GrantAlreadyExistsError,
    GrantNotFoundError,
    GrantEventType,
    PrincipalKind,
    PrincipalRef,
    RoleGrant,
    grant_id_for,
    require_scope,
    scope_covers,
)

from _fixtures import (
    AFTER_WINDOW,
    BEFORE_WINDOW,
    DIGEST,
    PARENT_SCOPE,
    ROLE,
    SCOPE,
    SIBLING_SCOPE,
    T0,
    T1,
    T2,
    TENANT,
    committee,
    grant,
    human,
    memory_directory,
    sqlite_directory,
    window,
)


@pytest.fixture(params=["memory", "sqlite"])
def directory(request, tmp_path):
    d = memory_directory() if request.param == "memory" else sqlite_directory(tmp_path)
    yield d
    d.close()


# --------------------------------------------------------------------------- #
# Scopes
# --------------------------------------------------------------------------- #
def test_a_scope_covers_itself_and_its_descendants_only():
    assert scope_covers(PARENT_SCOPE, PARENT_SCOPE)
    assert scope_covers(PARENT_SCOPE, SCOPE)
    assert not scope_covers(SCOPE, PARENT_SCOPE)      # never an ancestor
    assert not scope_covers(SCOPE, SIBLING_SCOPE)     # never a sibling
    assert not scope_covers("approval/case", "approval/casebook")  # not a prefix match


def test_a_scope_is_never_silently_unbounded():
    for bad in ("", "  ", "a//b", "a/*", "*", "a/ b"):
        with pytest.raises(ContractViolation):
            require_scope(bad, "scope")


# --------------------------------------------------------------------------- #
# The window
# --------------------------------------------------------------------------- #
def test_a_grant_outside_its_window_is_absent_not_flagged(directory):
    g = directory.put_grant(grant(), as_of=T0, loaded_by="admin-1")

    assert directory.holders_of(tenant_id=TENANT, role=ROLE, scope=SCOPE, as_of=T1) == (g,)
    assert directory.holders_of(tenant_id=TENANT, role=ROLE, scope=SCOPE, as_of=AFTER_WINDOW) == ()
    assert directory.holders_of(tenant_id=TENANT, role=ROLE, scope=SCOPE, as_of=BEFORE_WINDOW) == ()
    assert directory.grants_for(tenant_id=TENANT, principal_id=g.principal_id,
                                as_of=AFTER_WINDOW) == ()
    # The record still exists — it is the *answers* that omit it.
    assert directory.get_grant(g.grant_id) == g
    assert g.status_at(AFTER_WINDOW) is ValidityStatus.EXPIRED
    assert g.is_valid_at(T1) and not g.is_valid_at(AFTER_WINDOW)


def test_the_window_boundary_is_half_open(directory):
    g = directory.put_grant(grant(), as_of=T0)
    expires = g.validity.expires_at
    assert g.is_valid_at(g.validity.issued_at)
    assert not g.is_valid_at(expires)
    assert directory.holders_of(tenant_id=TENANT, role=ROLE, scope=SCOPE, as_of=expires) == ()


def test_a_naive_instant_is_refused_rather_than_assumed_utc(directory):
    import datetime as dt

    directory.put_grant(grant(), as_of=T0)
    with pytest.raises(ContractViolation):
        directory.holders_of(tenant_id=TENANT, role=ROLE, scope=SCOPE,
                             as_of=dt.datetime(2026, 3, 1, 9, 0))


# --------------------------------------------------------------------------- #
# Revocation
# --------------------------------------------------------------------------- #
def test_revocation_is_forward_only_and_removes_the_grant_from_answers(directory):
    g = directory.put_grant(grant(), as_of=T0)
    revoked = directory.revoke_grant(g.grant_id, as_of=T1, reason="left the team",
                                     actor="admin-1")
    assert revoked.revoked_at == T1 and revoked.revocation_reason == "left the team"

    # Absent from T1 onward; still in force before it.
    assert directory.holders_of(tenant_id=TENANT, role=ROLE, scope=SCOPE, as_of=T2) == ()
    before = directory.holders_of(tenant_id=TENANT, role=ROLE, scope=SCOPE, as_of=T0)
    assert [h.grant_id for h in before] == [g.grant_id]
    with pytest.raises(ContractViolation):
        directory.revoke_grant(g.grant_id, as_of=T2)
    assert [e.event_type for e in directory.grant_events(g.grant_id)] == [
        GrantEventType.GRANTED, GrantEventType.REVOKED]


def test_an_unknown_grant_cannot_be_revoked(directory):
    with pytest.raises(GrantNotFoundError):
        directory.revoke_grant("grant_nope", as_of=T1)


# --------------------------------------------------------------------------- #
# Identity and records
# --------------------------------------------------------------------------- #
def test_the_grant_id_is_derived_and_a_grant_is_never_overwritten(directory):
    g = grant()
    assert g.grant_id == grant_id_for(TENANT, g.principal_id, ROLE, SCOPE, g.validity)
    directory.put_grant(g, as_of=T0)
    with pytest.raises(GrantAlreadyExistsError):
        directory.put_grant(grant(), as_of=T0)
    # A different window is a different grant.
    later = directory.put_grant(grant(validity=window(T1)), as_of=T1)
    assert later.grant_id != g.grant_id


def test_holders_are_matched_by_role_and_covering_scope(directory):
    wide = directory.put_grant(grant(human("approver-wide"), scope=PARENT_SCOPE), as_of=T0)
    exact = directory.put_grant(grant(human("approver-exact"), scope=SCOPE), as_of=T0)
    directory.put_grant(grant(human("approver-sibling"), scope=SIBLING_SCOPE), as_of=T0)
    directory.put_grant(grant(human("finance"), role="finance-approver"), as_of=T0)

    holders = directory.holders_of(tenant_id=TENANT, role=ROLE, scope=SCOPE, as_of=T1)
    assert {g.principal_id for g in holders} == {wide.principal_id, exact.principal_id}


def test_a_grant_never_crosses_tenants(directory):
    directory.put_grant(grant(tenant="tenant-b"), as_of=T0)
    assert directory.holders_of(tenant_id=TENANT, role=ROLE, scope=SCOPE, as_of=T1) == ()


# --------------------------------------------------------------------------- #
# Principals
# --------------------------------------------------------------------------- #
def test_a_quorum_is_meaningful_only_for_a_committee():
    assert committee(quorum=2).quorum == 2
    with pytest.raises(ContractViolation):
        PrincipalRef(principal_id="c", principal_kind=PrincipalKind.COMMITTEE, quorum=0)
    with pytest.raises(ContractViolation):
        PrincipalRef(principal_id="p", principal_kind=PrincipalKind.HUMAN, quorum=2)


def test_a_principal_ref_carries_no_secret():
    ref = human()
    assert set(ref.to_dict()) == {"principal_id", "principal_kind", "display_ref", "quorum"}
    assert PrincipalRef.from_dict(ref.to_dict()) == ref


def test_a_grant_round_trips_and_verifies_its_own_digest():
    g = grant()
    assert RoleGrant.from_dict(g.to_dict()) == g
    g.verify(g.record_digest())
    from ugence_authority_directory import RecordIntegrityError

    with pytest.raises(RecordIntegrityError):
        g.verify("0" * 64)
