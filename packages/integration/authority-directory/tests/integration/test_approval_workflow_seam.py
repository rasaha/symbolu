"""The directory drives a real approval to ``GRANTED``, with neither package amended.

A composition root wires this package's :class:`DirectoryApproverEligibility` into the
approval workflow's ``SqliteApprovalWorkflowStore`` as its ``ApproverEligibilityPort``.
Nothing in ``ugence_approval_workflow`` is imported by the directory, extended, or
subclassed — the seam is structural, and this is where that claim is tested against
the real thing.
"""

from __future__ import annotations

import pytest

pytest.importorskip("ugence_approval_workflow",
                    reason="the approval workflow package is not on the path")

from ugence_approval_workflow import (  # noqa: E402
    ApprovalState,
    ApprovalSubject,
    ApproverEligibilityPort,
    ELIGIBLE_APPROVER_KINDS,
    EligibilityRefused,
    ReviewDecision,
    SqliteApprovalWorkflowStore,
    structural_refusals,
)

from ugence_authority_directory import (  # noqa: E402
    DirectoryApproverEligibility,
    PrincipalKind,
    SqliteAuthorityDirectory,
    projection_of,
)

from _fixtures import (  # noqa: E402
    AFTER_WINDOW,
    DIGEST,
    ROLE,
    SUBJECT_KIND,
    T0,
    T1,
    T2,
    TENANT,
    committee,
    grant,
    human,
    window,
)

REQUESTER = "requester-1"


def _wire(tmp_path, *holders):
    """The composition root: a directory, its eligibility adapter, and the workflow."""

    directory = SqliteAuthorityDirectory(str(tmp_path / "directory.sqlite3"))
    for who in holders or (human("approver-1"),):
        directory.put_grant(grant(who), as_of=T0, loaded_by="admin-1")
    eligibility = DirectoryApproverEligibility(directory)
    store = SqliteApprovalWorkflowStore(str(tmp_path / "approvals.sqlite3"), eligibility)
    return directory, eligibility, store


def _subject() -> ApprovalSubject:
    return ApprovalSubject(tenant_id=TENANT, subject_kind=SUBJECT_KIND,
                           subject_digest=DIGEST, subject_ref="case_1")


# --------------------------------------------------------------------------- #
def test_the_adapter_satisfies_the_consumers_port_structurally(tmp_path):
    directory, eligibility, store = _wire(tmp_path)
    assert isinstance(eligibility, ApproverEligibilityPort)
    store.close()
    directory.close()


def test_a_directory_grant_drives_one_approval_to_granted(tmp_path):
    directory, eligibility, store = _wire(tmp_path)

    record = store.request_approval(_subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    assert record.state is ApprovalState.REQUESTED

    presented = store.present_for_decision(record.approval_id, as_of=T1)
    assert presented.state is ApprovalState.PENDING

    # The approver the directory reported is handed straight to decide().
    approver, = eligibility.eligible_approvers(
        tenant_id=TENANT, subject_kind=SUBJECT_KIND, subject_digest=DIGEST,
        required_role=ROLE, as_of=T1)
    decided = store.decide(record.approval_id, approver=approver,
                           decision=ReviewDecision.GRANT, as_of=T2)

    assert decided.state is ApprovalState.GRANTED
    assert decided.decided_by == "approver-1" and decided.decided_role == ROLE
    assert decided.decided_authority_reference == "directory://roles/risk-approver"
    store.close()
    directory.close()


def test_the_projection_passes_the_consumers_own_structural_rules(tmp_path):
    directory, eligibility, store = _wire(tmp_path)
    approver, = eligibility.eligible_approvers(
        tenant_id=TENANT, subject_kind=SUBJECT_KIND, subject_digest=DIGEST,
        required_role=ROLE, as_of=T1)

    # The consumer's own enum set accepts the directory's kind, by value.
    assert approver.approver_kind in ELIGIBLE_APPROVER_KINDS
    answer = eligibility.is_eligible(tenant_id=TENANT, approver=approver, required_role=ROLE,
                                     scope=f"{SUBJECT_KIND}:{DIGEST}", as_of=T1)
    assert structural_refusals(approver=approver, requested_by=REQUESTER,
                               required_role=ROLE, decision=answer) == ()
    store.close()
    directory.close()


def test_a_lapsed_grant_leaves_the_approval_undecidable(tmp_path):
    directory, eligibility, store = _wire(tmp_path)
    record = store.request_approval(_subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(days=30), as_of=T0)
    store.present_for_decision(record.approval_id, as_of=T1)
    approver = projection_of(grant(human("approver-1")))

    # The approval window is still open; the *grant* is not.
    with pytest.raises(EligibilityRefused):
        store.decide(record.approval_id, approver=approver, decision=ReviewDecision.GRANT,
                     as_of=AFTER_WINDOW)
    assert store.get_approval(record.approval_id).state is ApprovalState.PENDING
    store.close()
    directory.close()


def test_a_revoked_grant_stops_the_approver_at_the_next_decision(tmp_path):
    directory, eligibility, store = _wire(tmp_path)
    held, = directory.grants_for(tenant_id=TENANT, principal_id="approver-1", as_of=T0)
    record = store.request_approval(_subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    store.present_for_decision(record.approval_id, as_of=T0)
    directory.revoke_grant(held.grant_id, as_of=T1, reason="left the team")

    with pytest.raises(EligibilityRefused, match="no valid grant"):
        store.decide(record.approval_id, approver=projection_of(held),
                     decision=ReviewDecision.GRANT, as_of=T2)
    assert store.get_approval(record.approval_id).state is ApprovalState.PENDING
    store.close()
    directory.close()


def test_an_approval_nobody_holds_a_role_for_is_never_presented(tmp_path):
    directory = SqliteAuthorityDirectory(str(tmp_path / "directory.sqlite3"))
    store = SqliteApprovalWorkflowStore(str(tmp_path / "approvals.sqlite3"),
                                        DirectoryApproverEligibility(directory))
    record = store.request_approval(_subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    with pytest.raises(EligibilityRefused):
        store.present_for_decision(record.approval_id, as_of=T1)
    store.close()
    directory.close()


def test_a_committee_holder_is_admitted_by_the_consumer_too(tmp_path):
    directory, eligibility, store = _wire(tmp_path, committee())
    record = store.request_approval(_subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    store.present_for_decision(record.approval_id, as_of=T1)
    approver, = eligibility.eligible_approvers(
        tenant_id=TENANT, subject_kind=SUBJECT_KIND, subject_digest=DIGEST,
        required_role=ROLE, as_of=T1)
    assert approver.approver_kind is PrincipalKind.COMMITTEE

    decided = store.decide(record.approval_id, approver=approver,
                           decision=ReviewDecision.GRANT, as_of=T2)
    assert decided.state is ApprovalState.GRANTED and decided.decided_by == "risk-committee"
    # The directory reported the quorum; nobody counted a vote.
    report = eligibility.committee_for(tenant_id=TENANT, committee_id="risk-committee",
                                       required_role=ROLE, subject_kind=SUBJECT_KIND,
                                       subject_digest=DIGEST, as_of=T2)
    assert report.quorum == 2
    store.close()
    directory.close()


def test_neither_package_imports_the_other(tmp_path):
    import ugence_approval_workflow
    import ugence_authority_directory

    consumer = pytest.importorskip("ugence_approval_workflow").__file__
    assert "ugence_authority_directory" not in open(consumer, encoding="utf-8").read()
    directory_init = ugence_authority_directory.__file__
    assert "ugence_approval_workflow" not in open(directory_init, encoding="utf-8").read()
