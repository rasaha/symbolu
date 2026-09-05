"""Delegation stops after one hop and may only narrow; a committee is reported as a
quorum plus its currently-valid members, and never as a decision."""

from __future__ import annotations

import pytest

from ugence_authority_directory import (
    MAX_DELEGATION_HOPS,
    CommitteeReport,
    DelegationRefused,
    delegation_refusals,
)

from _fixtures import (
    AFTER_WINDOW,
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


def _delegated(delegator, *, to: str = "deputy-1", scope: str = SCOPE, role: str = ROLE,
               tenant: str = TENANT, validity=None):
    return grant(human(to), role=role, scope=scope, tenant=tenant, validity=validity,
                 delegation_ref=delegator.grant_id, delegated_from=delegator.principal_id)


# --------------------------------------------------------------------------- #
# Delegation
# --------------------------------------------------------------------------- #
def test_a_delegation_that_narrows_is_admitted(directory):
    boss = directory.put_grant(grant(human("boss"), scope=PARENT_SCOPE), as_of=T0)
    deputy = directory.put_grant(_delegated(boss, scope=SCOPE), as_of=T1)

    assert deputy.is_delegated and deputy.delegated_from == "boss"
    holders = directory.holders_of(tenant_id=TENANT, role=ROLE, scope=SCOPE, as_of=T2)
    assert {g.principal_id for g in holders} == {"boss", "deputy-1"}


def test_a_delegation_may_never_widen_or_move_sideways(directory):
    boss = directory.put_grant(grant(human("boss"), scope=SCOPE), as_of=T0)
    for scope in (PARENT_SCOPE, SIBLING_SCOPE):
        with pytest.raises(DelegationRefused, match="may only narrow"):
            directory.put_grant(_delegated(boss, scope=scope), as_of=T1)


def test_a_delegation_needs_a_delegator_valid_at_the_same_instant(directory):
    boss = directory.put_grant(grant(human("boss"), scope=PARENT_SCOPE), as_of=T0)
    with pytest.raises(DelegationRefused, match="not valid at this instant"):
        directory.put_grant(_delegated(boss), as_of=AFTER_WINDOW)

    directory.revoke_grant(boss.grant_id, as_of=T1)
    with pytest.raises(DelegationRefused, match="not valid at this instant"):
        directory.put_grant(_delegated(boss), as_of=T2)


def test_a_delegation_from_a_grant_that_does_not_exist_is_refused(directory):
    phantom = grant(human("boss"), scope=PARENT_SCOPE)
    with pytest.raises(DelegationRefused, match="does not exist"):
        directory.put_grant(_delegated(phantom), as_of=T1)


def test_delegation_stops_after_one_hop(directory):
    assert MAX_DELEGATION_HOPS == 1
    boss = directory.put_grant(grant(human("boss"), scope=PARENT_SCOPE), as_of=T0)
    deputy = directory.put_grant(_delegated(boss, scope=PARENT_SCOPE), as_of=T1)
    with pytest.raises(DelegationRefused, match="stops after 1 hop"):
        directory.put_grant(_delegated(deputy, to="sub-deputy", scope=SCOPE), as_of=T2)


def test_a_delegation_may_not_change_the_role_or_cross_a_tenant(directory):
    boss = directory.put_grant(grant(human("boss"), scope=PARENT_SCOPE), as_of=T0)
    with pytest.raises(DelegationRefused, match="may not change the role"):
        directory.put_grant(_delegated(boss, role="finance-approver", scope=SCOPE), as_of=T1)
    with pytest.raises(DelegationRefused, match="cross tenants"):
        directory.put_grant(_delegated(boss, tenant="tenant-b"), as_of=T1)


def test_a_principal_may_not_delegate_to_itself(directory):
    boss = directory.put_grant(grant(human("boss"), scope=PARENT_SCOPE), as_of=T0)
    with pytest.raises(DelegationRefused, match="delegate to itself"):
        directory.put_grant(_delegated(boss, to="boss", scope=SCOPE), as_of=T1)


def test_the_rules_are_pure_and_report_every_reason_at_once():
    boss = grant(human("boss"), scope=SCOPE)
    bad = grant(human("deputy"), role="other", scope=SIBLING_SCOPE, tenant="tenant-b",
                delegation_ref=boss.grant_id, delegated_from="boss")
    reasons = delegation_refusals(bad, boss, T1)
    assert len(reasons) >= 3
    assert delegation_refusals(grant(), None, T1) == ()  # an ordinary grant delegates nothing


# --------------------------------------------------------------------------- #
# Committees
# --------------------------------------------------------------------------- #
def _committee_world(directory, *, quorum: int = 2):
    board = directory.put_grant(grant(committee(quorum=quorum), scope=PARENT_SCOPE), as_of=T0)
    members = [
        directory.put_grant(grant(human(f"member-{i}"), scope=SCOPE,
                                  member_of="risk-committee"), as_of=T0)
        for i in (1, 2, 3)
    ]
    return board, members


def test_a_committee_is_reported_as_quorum_plus_currently_valid_members(directory):
    _committee_world(directory)
    report = directory.committee_report(tenant_id=TENANT, committee_id="risk-committee",
                                        role=ROLE, scope=SCOPE, as_of=T1)
    assert isinstance(report, CommitteeReport)
    assert report.quorum == 2
    assert report.member_ids == ("member-1", "member-2", "member-3")


def test_a_lapsed_member_simply_stops_being_reported(directory):
    _, members = _committee_world(directory)
    directory.revoke_grant(members[0].grant_id, as_of=T1, reason="left the committee")

    report = directory.committee_report(tenant_id=TENANT, committee_id="risk-committee",
                                        role=ROLE, scope=SCOPE, as_of=T2)
    assert report.member_ids == ("member-2", "member-3")
    # Below quorum is still merely a report: the directory says nothing about it.
    directory.revoke_grant(members[1].grant_id, as_of=T1)
    thin = directory.committee_report(tenant_id=TENANT, committee_id="risk-committee",
                                      role=ROLE, scope=SCOPE, as_of=T2)
    assert thin.quorum == 2 and thin.member_ids == ("member-3",)


def test_the_report_never_says_whether_a_quorum_was_met(directory):
    _committee_world(directory)
    report = directory.committee_report(tenant_id=TENANT, committee_id="risk-committee",
                                        role=ROLE, scope=SCOPE, as_of=T1)
    names = {n for n in dir(report) if not n.startswith("_")}
    assert not names & {"quorum_met", "has_quorum", "met", "approved", "decision", "vote",
                        "votes", "tally", "count_votes"}
    assert set(names) == {"committee", "role", "scope", "quorum", "members", "member_ids"}


def test_a_committee_absent_at_the_instant_yields_no_report(directory):
    board, _ = _committee_world(directory)
    assert directory.committee_report(tenant_id=TENANT, committee_id="risk-committee",
                                      role=ROLE, scope=SCOPE, as_of=AFTER_WINDOW) is None
    directory.revoke_grant(board.grant_id, as_of=T1)
    assert directory.committee_report(tenant_id=TENANT, committee_id="risk-committee",
                                      role=ROLE, scope=SCOPE, as_of=T2) is None


def test_membership_outside_the_committee_scope_is_not_reported(directory):
    directory.put_grant(grant(committee(), scope=SCOPE), as_of=T0)
    directory.put_grant(grant(human("outsider"), scope=SIBLING_SCOPE,
                              member_of="risk-committee"), as_of=T0)
    report = directory.committee_report(tenant_id=TENANT, committee_id="risk-committee",
                                        role=ROLE, scope=SCOPE, as_of=T1)
    assert report.member_ids == ()
