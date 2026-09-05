"""The whole wave 2 chain, once, end to end — with no package amended.

Directory grant -> eligibility -> approval -> once-only consumption -> the kernel's
review task cleared. Three packages meet here and none imports another: the directory
satisfies the approval workflow's port structurally, the approval workflow reaches
Decision Authority only through the kernel's existing 1.0.0 surface, and the wiring
below is composition-root code that lives in this test and nowhere else.

The directory's ``src`` is put on the path here rather than in ``conftest.py`` so this
walkthrough stays a single added file. It skips when either dependency is missing.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[5]
_DIRECTORY_SRC = _REPO / "packages" / "integration" / "authority-directory" / "src"
if _DIRECTORY_SRC.is_dir() and str(_DIRECTORY_SRC) not in sys.path:
    sys.path.insert(0, str(_DIRECTORY_SRC))

pytest.importorskip("pydantic", reason="the Decision Authority kernel requires pydantic")
pytest.importorskip("ugence_authority_directory",
                    reason="the authority directory package is not on the path")

from ugence_authority_directory import (  # noqa: E402
    DirectoryApproverEligibility,
    PrincipalKind,
    PrincipalRef,
    RoleGrant,
    SqliteAuthorityDirectory,
    grant_id_for,
    projection_of,
)
from ugence_decision_authority.api.audit import (  # noqa: E402
    AuditService,
    InMemoryAuditRepository,
)
from ugence_decision_authority.api.identity import StaticIdentityProvider  # noqa: E402
from ugence_decision_authority.api.policy import (  # noqa: E402
    AccessGrant,
    EvidenceAccessPolicy,
    GrantStore,
    Permission,
)
from ugence_decision_authority.api.repositories import (  # noqa: E402
    InMemoryDecisionCaseRepository,
)
from ugence_decision_authority.api.services import (  # noqa: E402
    CaseValidationService,
    DecisionCaseService,
)
from ugence_decision_authority.decisions.status import (  # noqa: E402
    ReviewTaskStatus,
    ReviewTaskType,
)
from ugence_decision_authority.decisions.subject import VersionedRef  # noqa: E402
from ugence_decision_authority.version import __version__ as DA_VERSION  # noqa: E402

from ugence_approval_workflow import (  # noqa: E402
    ApprovalState,
    ApprovalSubject,
    ConsumptionResult,
    EligibilityRefused,
    ReviewDecision,
    SqliteApprovalWorkflowStore,
)

from _fixtures import (  # noqa: E402
    AFTER_WINDOW,
    DIGEST,
    REQUESTER,
    ROLE,
    SUBJECT_KIND,
    T0,
    T1,
    T2,
    window,
)

TENANT = "tenant-a"
ACTOR = "case-owner"
APPROVER_ID = "approver-1"
SUBJECT_ID = "subject-1"
AUTHORITY_REF = "directory://roles/risk-approver"
#: The scope convention the shipped eligibility adapter derives.
SCOPE = f"approval/{SUBJECT_KIND}/{DIGEST}"


# --------------------------------------------------------------------------- #
# The composition root — the only place the three packages meet
# --------------------------------------------------------------------------- #
class _NoLinkedRecords:
    """The kernel's linked-record port. This chain links no assessment."""

    def get_record(self, *, tenant_id, record_type, record_id, version=None):
        return None


class _CountingCases:
    """The kernel service, wrapped only to count ``complete_review`` calls."""

    def __init__(self, inner, repo) -> None:
        self._inner = inner
        self.repo = repo
        self.complete_review_calls: list[tuple[str, str]] = []

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def complete_review(self, *, case_id: str, task_id: str, actor: str):
        self.complete_review_calls.append((case_id, task_id))
        return self._inner.complete_review(case_id=case_id, task_id=task_id, actor=actor)


def _role_grant(validity=None) -> RoleGrant:
    who = PrincipalRef(principal_id=APPROVER_ID, principal_kind=PrincipalKind.HUMAN,
                       display_ref=f"directory://people/{APPROVER_ID}")
    win = validity or window()
    return RoleGrant(grant_id=grant_id_for(TENANT, APPROVER_ID, ROLE, SCOPE, win),
                     tenant_id=TENANT, principal=who, role=ROLE, scope=SCOPE, validity=win,
                     authority_reference=AUTHORITY_REF)


def _wire(tmp_path, *, load_grant: bool = True):
    """Directory -> eligibility -> approval store, plus the frozen kernel."""

    directory = SqliteAuthorityDirectory(os.path.join(str(tmp_path), "directory.sqlite3"))
    if load_grant:
        directory.put_grant(_role_grant(), as_of=T0, loaded_by="admin-1")
    store = SqliteApprovalWorkflowStore(os.path.join(str(tmp_path), "approvals.sqlite3"),
                                        DirectoryApproverEligibility(directory))

    idp = StaticIdentityProvider()
    idp.register_human(ACTOR)
    idp.register_human(APPROVER_ID)
    grants = GrantStore()
    for principal in (ACTOR, APPROVER_ID):
        grants.add(AccessGrant(principal, TENANT, frozenset(Permission)))
    repo = InMemoryDecisionCaseRepository()
    cases = _CountingCases(DecisionCaseService(
        repo, CaseValidationService(_NoLinkedRecords()),
        AuditService(InMemoryAuditRepository()), idp, EvidenceAccessPolicy(grants)), repo)
    return directory, store, cases


def _subject() -> ApprovalSubject:
    return ApprovalSubject(tenant_id=TENANT, subject_kind=SUBJECT_KIND, subject_digest=DIGEST,
                           subject_ref="case_1")


def _case_with_task(cases, approval_id: str):
    case = cases.create_case(
        tenant_id=TENANT, decision_type="vendor_onboarding", subject_ids=(SUBJECT_ID,),
        created_by=ACTOR,
        policy_refs=(VersionedRef(ref_id=approval_id, version=1, kind="approval"),))
    task = cases.assign_review(case_id=case.decision_case_id,
                               task_type=ReviewTaskType.SECONDARY_APPROVAL,
                               assigned_to=APPROVER_ID, required_role=ROLE, actor=ACTOR)
    return case.decision_case_id, task


def _clear_review_when_consumed(store, cases, *, approval_id, subject_digest, case_id,
                                task_id, as_of):
    """**The seam.** Consume once; clear the kernel's review task only if we won."""

    outcome = store.consume(
        approval_id, consumer_ref=f"decision_case:{case_id}/review_task:{task_id}",
        subject_digest=subject_digest, as_of=as_of)
    if outcome.is_consumed:
        cases.complete_review(case_id=case_id, task_id=task_id, actor=APPROVER_ID)
    return outcome


def _blockers(result) -> set[str]:
    return {issue.code for issue in result.blockers}


def _granted(store, directory, *, as_of=T2):
    """Request, present and decide — with the approver the directory reported."""

    record = store.request_approval(_subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    store.present_for_decision(record.approval_id, as_of=T1)
    approver, = DirectoryApproverEligibility(directory).eligible_approvers(
        tenant_id=TENANT, subject_kind=SUBJECT_KIND, subject_digest=DIGEST,
        required_role=ROLE, as_of=T1)
    return store.decide(record.approval_id, approver=approver,
                        decision=ReviewDecision.GRANT, as_of=as_of)


# --------------------------------------------------------------------------- #
# The kernel is frozen
# --------------------------------------------------------------------------- #
def test_the_kernel_is_1_0_0_and_this_branch_changed_none_of_it():
    assert DA_VERSION == "1.0.0"
    da = "packages/capabilities/decision-authority"

    def git(*args) -> str:
        return subprocess.run(("git", "-C", str(_REPO)) + args, capture_output=True,
                              text=True, check=True).stdout.strip()

    assert git("status", "--porcelain", "--", da) == ""
    here = git("rev-parse", "--abbrev-ref", "HEAD")
    others = [b.strip() for b in git("branch", "-r", "--format=%(refname:short)").splitlines()
              if b.strip() and not b.strip().endswith(f"/{here}") and "->" not in b]
    if len(others) != 1:
        pytest.skip(f"cannot unambiguously resolve the base branch: {others}")
    assert git("diff", "--name-only", f"{others[0]}...HEAD", "--", da) == ""


# --------------------------------------------------------------------------- #
# The chain
# --------------------------------------------------------------------------- #
def test_one_role_grant_carries_a_decision_case_all_the_way_to_ready(tmp_path):
    directory, store, cases = _wire(tmp_path)

    approval = _granted(store, directory)
    assert approval.state is ApprovalState.GRANTED
    assert approval.decided_by == APPROVER_ID
    assert approval.decided_authority_reference == AUTHORITY_REF

    case_id, task = _case_with_task(cases, approval.approval_id)
    assert task.status is ReviewTaskStatus.PENDING
    blocked = cases.validate_decision_readiness(case_id=case_id, actor=ACTOR)
    assert not blocked.ready and _blockers(blocked) == {"REQUIRED_REVIEW_OUTSTANDING"}

    outcome = _clear_review_when_consumed(
        store, cases, approval_id=approval.approval_id,
        subject_digest=approval.subject_digest, case_id=case_id, task_id=task.task_id,
        as_of=T2)
    assert outcome.result is ConsumptionResult.CONSUMED_FIRST
    assert cases.complete_review_calls == [(case_id, task.task_id)]

    ready = cases.validate_decision_readiness(case_id=case_id, actor=ACTOR)
    assert ready.ready and ready.blockers == () and ready.required_reviews_outstanding == ()

    # The whole chain is reconstructible from the two ledgers plus the case.
    case = cases.get_case(case_id)
    assert case.policy_refs == (
        VersionedRef(ref_id=approval.approval_id, version=1, kind="approval"),)
    assert store.get_approval(approval.approval_id).consumer_ref == (
        f"decision_case:{case_id}/review_task:{task.task_id}")
    assert directory.grants_for(tenant_id=TENANT, principal_id=APPROVER_ID,
                                as_of=T2)[0].authority_reference == AUTHORITY_REF
    store.close()
    directory.close()


# --------------------------------------------------------------------------- #
# Three ways the same chain fails, each leaving the case blocked
# --------------------------------------------------------------------------- #
def test_a_revoked_role_grant_stops_the_chain_before_an_approval_exists(tmp_path):
    directory, store, cases = _wire(tmp_path)
    held, = directory.grants_for(tenant_id=TENANT, principal_id=APPROVER_ID, as_of=T0)

    record = store.request_approval(_subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    store.present_for_decision(record.approval_id, as_of=T0)
    directory.revoke_grant(held.grant_id, as_of=T1, reason="left the team")

    with pytest.raises(EligibilityRefused, match="no valid grant"):
        store.decide(record.approval_id, approver=projection_of(held),
                     decision=ReviewDecision.GRANT, as_of=T2)

    case_id, task = _case_with_task(cases, record.approval_id)
    outcome = _clear_review_when_consumed(
        store, cases, approval_id=record.approval_id, subject_digest=record.subject_digest,
        case_id=case_id, task_id=task.task_id, as_of=T2)

    assert outcome.result is ConsumptionResult.NOT_GRANTED and outcome.resolution is None
    assert cases.complete_review_calls == []
    still = cases.validate_decision_readiness(case_id=case_id, actor=ACTOR)
    assert not still.ready and _blockers(still) == {"REQUIRED_REVIEW_OUTSTANDING"}
    assert cases.repo.get_review_task(task.task_id).status is ReviewTaskStatus.PENDING
    store.close()
    directory.close()


def test_a_lapsed_approval_clears_nothing(tmp_path):
    directory, store, cases = _wire(tmp_path)
    approval = _granted(store, directory)
    case_id, task = _case_with_task(cases, approval.approval_id)

    outcome = _clear_review_when_consumed(
        store, cases, approval_id=approval.approval_id,
        subject_digest=approval.subject_digest, case_id=case_id, task_id=task.task_id,
        as_of=AFTER_WINDOW)

    assert outcome.result is ConsumptionResult.EXPIRED_APPROVAL and outcome.resolution is None
    assert cases.complete_review_calls == []
    still = cases.validate_decision_readiness(case_id=case_id, actor=ACTOR)
    assert not still.ready and _blockers(still) == {"REQUIRED_REVIEW_OUTSTANDING"}
    assert store.get_approval(approval.approval_id).state is ApprovalState.GRANTED
    store.close()
    directory.close()


def test_a_second_case_cannot_reuse_the_consumed_approval(tmp_path):
    directory, store, cases = _wire(tmp_path)
    approval = _granted(store, directory)

    first_case, first_task = _case_with_task(cases, approval.approval_id)
    assert _clear_review_when_consumed(
        store, cases, approval_id=approval.approval_id,
        subject_digest=approval.subject_digest, case_id=first_case,
        task_id=first_task.task_id, as_of=T2).is_consumed

    second_case, second_task = _case_with_task(cases, approval.approval_id)
    outcome = _clear_review_when_consumed(
        store, cases, approval_id=approval.approval_id,
        subject_digest=approval.subject_digest, case_id=second_case,
        task_id=second_task.task_id, as_of=T2)

    assert outcome.result is ConsumptionResult.ALREADY_CONSUMED and not outcome.is_consumed
    assert cases.complete_review_calls == [(first_case, first_task.task_id)]
    still = cases.validate_decision_readiness(case_id=second_case, actor=ACTOR)
    assert not still.ready and _blockers(still) == {"REQUIRED_REVIEW_OUTSTANDING"}
    assert cases.repo.get_review_task(second_task.task_id).status is ReviewTaskStatus.PENDING
    store.close()
    directory.close()
