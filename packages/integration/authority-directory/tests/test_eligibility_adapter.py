"""The ``ApproverEligibilityPort`` adapter, tested without importing the consumer.

The consumer's package is not on the path here on purpose: the adapter must satisfy a
*structural* seam. ``tests/integration`` then proves the same objects work against the
real package.
"""

from __future__ import annotations

import pytest

from ugence_authority_directory import (
    ContractViolation,
    DirectoryApproverEligibility,
    DirectoryApproverRef,
    EligibilityAnswer,
    PrincipalKind,
    projection_of,
)

from _fixtures import (
    AFTER_WINDOW,
    DIGEST,
    OTHER_DIGEST,
    PARENT_SCOPE,
    ROLE,
    SCOPE,
    SUBJECT_KIND,
    T0,
    T1,
    TENANT,
    committee,
    grant,
    human,
    memory_directory,
    sqlite_directory,
)


@pytest.fixture(params=["memory", "sqlite"])
def directory(request, tmp_path):
    d = memory_directory() if request.param == "memory" else sqlite_directory(tmp_path)
    yield d
    d.close()


@pytest.fixture
def adapter(directory):
    return DirectoryApproverEligibility(directory)


def _scope_arg(digest: str = DIGEST) -> str:
    """What the consumer passes as ``scope``: ``<subject_kind>:<subject_digest>``."""

    return f"{SUBJECT_KIND}:{digest}"


# --------------------------------------------------------------------------- #
def test_the_adapter_answers_the_ports_two_questions(directory, adapter):
    directory.put_grant(grant(human("approver-1")), as_of=T0)
    directory.put_grant(grant(human("approver-2"), scope=PARENT_SCOPE), as_of=T0)

    eligible = adapter.eligible_approvers(tenant_id=TENANT, subject_kind=SUBJECT_KIND,
                                          subject_digest=DIGEST, required_role=ROLE, as_of=T1)
    assert [a.approver_id for a in eligible] == ["approver-1", "approver-2"]
    assert all(isinstance(a, DirectoryApproverRef) for a in eligible)

    answer = adapter.is_eligible(tenant_id=TENANT, approver=eligible[0], required_role=ROLE,
                                 scope=_scope_arg(), as_of=T1)
    assert isinstance(answer, EligibilityAnswer) and answer.eligible and answer.reasons == ()


def test_the_projection_carries_the_ports_four_attributes_and_no_secret():
    ref = projection_of(grant(human("approver-1")))
    assert (ref.approver_id, ref.role) == ("approver-1", ROLE)
    assert ref.approver_kind is PrincipalKind.HUMAN
    assert ref.authority_reference == "directory://roles/risk-approver"
    fields = {f for f in dir(ref) if not f.startswith("_")}
    assert fields == {"approver_id", "approver_kind", "role", "authority_reference"}


def test_the_kind_values_match_the_consumers_enum_by_value():
    """Structural compatibility: both are ``str`` enums, so members compare and hash
    equal to the same plain strings — which is how a projection crosses the seam."""

    assert PrincipalKind.HUMAN == "HUMAN" and PrincipalKind.COMMITTEE == "COMMITTEE"
    assert {PrincipalKind.HUMAN, PrincipalKind.COMMITTEE} == {"HUMAN", "COMMITTEE"}
    assert PrincipalKind.HUMAN in frozenset({"HUMAN", "COMMITTEE"})
    assert PrincipalKind.AI not in frozenset({"HUMAN", "COMMITTEE"})


# --------------------------------------------------------------------------- #
# Refusals
# --------------------------------------------------------------------------- #
def test_a_lapsed_grant_makes_a_principal_ineligible(directory, adapter):
    directory.put_grant(grant(human("approver-1")), as_of=T0)
    ref = projection_of(grant(human("approver-1")))
    assert adapter.is_eligible(tenant_id=TENANT, approver=ref, required_role=ROLE,
                               scope=_scope_arg(), as_of=T1).eligible
    later = adapter.is_eligible(tenant_id=TENANT, approver=ref, required_role=ROLE,
                                scope=_scope_arg(), as_of=AFTER_WINDOW)
    assert not later.eligible and "no valid grant" in later.reasons[0]
    assert adapter.eligible_approvers(tenant_id=TENANT, subject_kind=SUBJECT_KIND,
                                      subject_digest=DIGEST, required_role=ROLE,
                                      as_of=AFTER_WINDOW) == ()


def test_a_grant_over_another_subject_does_not_travel(directory, adapter):
    directory.put_grant(grant(human("approver-1")), as_of=T0)
    ref = projection_of(grant(human("approver-1")))
    answer = adapter.is_eligible(tenant_id=TENANT, approver=ref, required_role=ROLE,
                                 scope=_scope_arg(OTHER_DIGEST), as_of=T1)
    assert not answer.eligible


def test_an_unknown_principal_and_a_wrong_role_are_refused_with_reasons(directory, adapter):
    directory.put_grant(grant(human("approver-1")), as_of=T0)
    stranger = DirectoryApproverRef(approver_id="nobody", approver_kind=PrincipalKind.HUMAN,
                                    role=ROLE)
    refused = adapter.is_eligible(tenant_id=TENANT, approver=stranger, required_role=ROLE,
                                  scope=_scope_arg(), as_of=T1)
    assert not refused.eligible and "no valid grant" in refused.reasons[0]

    wrong_role = adapter.is_eligible(tenant_id=TENANT, approver=projection_of(grant()),
                                     required_role="finance-approver", scope=_scope_arg(),
                                     as_of=T1)
    assert not wrong_role.eligible


def test_a_presented_kind_that_differs_from_the_record_is_refused(directory, adapter):
    directory.put_grant(grant(human("approver-1")), as_of=T0)
    lying = DirectoryApproverRef(approver_id="approver-1",
                                 approver_kind=PrincipalKind.COMMITTEE, role=ROLE)
    answer = adapter.is_eligible(tenant_id=TENANT, approver=lying, required_role=ROLE,
                                 scope=_scope_arg(), as_of=T1)
    assert not answer.eligible and "differs from the directory record" in answer.reasons[0]


def test_a_committee_holding_the_role_is_reported_as_eligible(directory, adapter):
    directory.put_grant(grant(committee()), as_of=T0)
    eligible = adapter.eligible_approvers(tenant_id=TENANT, subject_kind=SUBJECT_KIND,
                                          subject_digest=DIGEST, required_role=ROLE, as_of=T1)
    assert [(a.approver_id, a.approver_kind) for a in eligible] == [
        ("risk-committee", PrincipalKind.COMMITTEE)]
    report = adapter.committee_for(tenant_id=TENANT, committee_id="risk-committee",
                                   required_role=ROLE, subject_kind=SUBJECT_KIND,
                                   subject_digest=DIGEST, as_of=T1)
    assert report.quorum == 2 and report.member_ids == ()


def test_an_answer_is_typed_not_a_bare_boolean():
    with pytest.raises(ContractViolation):
        EligibilityAnswer(True, ("but also a reason",))
    with pytest.raises(ContractViolation):
        EligibilityAnswer(False)


def test_the_directory_is_required_at_construction():
    with pytest.raises(ContractViolation):
        DirectoryApproverEligibility(object())  # type: ignore[arg-type]


def test_the_adapter_derives_one_deterministic_scope(adapter):
    assert adapter.scope_for(SUBJECT_KIND, DIGEST) == SCOPE
    with pytest.raises(ContractViolation):
        adapter.scope_for("", DIGEST)
