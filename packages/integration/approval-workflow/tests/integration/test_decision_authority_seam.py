"""The wave 2 seam, end to end, with Decision Authority 1.0.0 unamended.

A composition root — not this package, and not the kernel — joins the two: it carries
the approval as ``VersionedRef(kind="approval")`` on the case, and it clears the
kernel's ``SECONDARY_APPROVAL`` review task **only** when ``consume`` returns
``CONSUMED_FIRST``. Everything the kernel does here it already did at 1.0.0; nothing
in `ugence_decision_authority` is imported by the package under test, extended, or
subclassed.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

pytest.importorskip("pydantic", reason="the Decision Authority kernel requires pydantic")

from ugence_decision_authority.api.audit import AuditService, InMemoryAuditRepository
from ugence_decision_authority.api.identity import StaticIdentityProvider
from ugence_decision_authority.api.policy import (
    AccessGrant,
    EvidenceAccessPolicy,
    GrantStore,
    Permission,
)
from ugence_decision_authority.api.repositories import InMemoryDecisionCaseRepository
from ugence_decision_authority.api.services import CaseValidationService, DecisionCaseService
from ugence_decision_authority.decisions.status import ReviewTaskStatus, ReviewTaskType
from ugence_decision_authority.decisions.subject import VersionedRef
from ugence_decision_authority.version import __version__ as DA_VERSION

from ugence_approval_workflow import ConsumptionResult

from _fixtures import (
    AFTER_WINDOW,
    APPROVER,
    OTHER_DIGEST,
    REQUESTER,
    ROLE,
    T0,
    T1,
    T2,
    granted,
    sqlite_store,
    subject,
    window,
)

TENANT = "tenant-a"
ACTOR = "case-owner"
SUBJECT_ID = "subject-1"


# --------------------------------------------------------------------------- #
# The composition root
# --------------------------------------------------------------------------- #
class _NoLinkedRecords:
    """The kernel's linked-record port. This seam links no assessment, so it
    resolves nothing; the kernel's own fail-closed reads are unchanged."""

    def get_record(self, *, tenant_id, record_type, record_id, version=None):
        return None


class _CountingCases:
    """The kernel service, wrapped only to count ``complete_review`` calls.

    It delegates every call unchanged — the point is to prove that a refused
    consumption produces **no** call at all, not to alter kernel behaviour.
    """

    def __init__(self, inner: DecisionCaseService, repo: InMemoryDecisionCaseRepository) -> None:
        self._inner = inner
        self.repo = repo
        self.complete_review_calls: list[tuple[str, str]] = []

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def complete_review(self, *, case_id: str, task_id: str, actor: str):
        self.complete_review_calls.append((case_id, task_id))
        return self._inner.complete_review(case_id=case_id, task_id=task_id, actor=actor)


def _kernel() -> _CountingCases:
    idp = StaticIdentityProvider()
    idp.register_human(ACTOR)
    idp.register_human(APPROVER.approver_id)
    grants = GrantStore()
    for principal in (ACTOR, APPROVER.approver_id):
        grants.add(AccessGrant(principal, TENANT, frozenset(Permission)))
    repo = InMemoryDecisionCaseRepository()
    return _CountingCases(DecisionCaseService(
        repo, CaseValidationService(_NoLinkedRecords()),
        AuditService(InMemoryAuditRepository()), idp, EvidenceAccessPolicy(grants)), repo)


def _case_carrying(approval_id: str, cases) -> str:
    """Create a case that carries the approval as an uninterpreted ``policy_ref``."""

    case = cases.create_case(
        tenant_id=TENANT, decision_type="vendor_onboarding", subject_ids=(SUBJECT_ID,),
        created_by=ACTOR,
        policy_refs=(VersionedRef(ref_id=approval_id, version=1, kind="approval"),))
    return case.decision_case_id


def clear_review_when_consumed(store, cases, *, approval_id, subject_digest,
                               case_id, task_id, actor, as_of):
    """**The seam.** Consume once; clear the kernel's review task only if we won.

    This is composition-root code: the approval package never imports the kernel, and
    the kernel never learns that an approval workflow exists.
    """

    outcome = store.consume(
        approval_id, consumer_ref=f"decision_case:{case_id}/review_task:{task_id}",
        subject_digest=subject_digest, as_of=as_of)
    if outcome.is_consumed:
        cases.complete_review(case_id=case_id, task_id=task_id, actor=actor)
    return outcome


def _blockers(result) -> set[str]:
    return {issue.code for issue in result.blockers}


# --------------------------------------------------------------------------- #
# The kernel is frozen
# --------------------------------------------------------------------------- #
def test_the_kernel_is_1_0_0_and_this_branch_changed_none_of_it():
    assert DA_VERSION == "1.0.0"

    repo = pathlib.Path(__file__).resolve().parents[5]
    da = "packages/capabilities/decision-authority"

    def git(*args) -> str:
        return subprocess.run(("git", "-C", str(repo)) + args, capture_output=True,
                              text=True, check=True).stdout.strip()

    # Nothing uncommitted under the kernel.
    assert git("status", "--porcelain", "--", da) == ""

    # And no commit on this branch touches it. The base is the one other remote
    # branch; when it cannot be resolved, this half of the check is skipped rather
    # than asserted against a guess.
    here = git("rev-parse", "--abbrev-ref", "HEAD")
    others = [b.strip() for b in git("branch", "-r", "--format=%(refname:short)").splitlines()
              if b.strip() and not b.strip().endswith(f"/{here}") and "->" not in b]
    if len(others) != 1:
        pytest.skip(f"cannot unambiguously resolve the base branch: {others}")
    assert git("diff", "--name-only", f"{others[0]}...HEAD", "--", da) == ""


# --------------------------------------------------------------------------- #
# The happy path
# --------------------------------------------------------------------------- #
def test_a_consumed_approval_clears_the_secondary_approval_task(tmp_path):
    store, cases = sqlite_store(tmp_path), _kernel()
    approval = granted(store)
    case_id = _case_carrying(approval.approval_id, cases)

    task = cases.assign_review(case_id=case_id, task_type=ReviewTaskType.SECONDARY_APPROVAL,
                               assigned_to=APPROVER.approver_id, required_role=ROLE, actor=ACTOR)
    assert task.status is ReviewTaskStatus.PENDING

    blocked = cases.validate_decision_readiness(case_id=case_id, actor=ACTOR)
    assert not blocked.ready
    assert _blockers(blocked) == {"REQUIRED_REVIEW_OUTSTANDING"}
    assert blocked.required_reviews_outstanding == (task.task_id,)

    outcome = clear_review_when_consumed(
        store, cases, approval_id=approval.approval_id,
        subject_digest=approval.subject_digest, case_id=case_id, task_id=task.task_id,
        actor=APPROVER.approver_id, as_of=T2)
    assert outcome.result is ConsumptionResult.CONSUMED_FIRST
    assert cases.complete_review_calls == [(case_id, task.task_id)]

    ready = cases.validate_decision_readiness(case_id=case_id, actor=ACTOR)
    assert ready.ready and ready.blockers == () and ready.required_reviews_outstanding == ()
    store.close()


def test_the_case_carries_the_approval_as_an_uninterpreted_policy_ref(tmp_path):
    store, cases = sqlite_store(tmp_path), _kernel()
    approval = granted(store)
    case_id = _case_carrying(approval.approval_id, cases)

    case = cases.get_case(case_id)
    ref, = case.policy_refs
    assert ref == VersionedRef(ref_id=approval.approval_id, version=1, kind="approval")
    # The kernel records the reference and interprets nothing about it.
    assert case.assessment_refs == () and case.recommendation_refs == ()
    store.close()


def test_the_binding_lives_in_the_approval_ledger_not_in_the_kernel(tmp_path):
    """``ReviewTask`` has no metadata field, so the join lives on our side."""

    store, cases = sqlite_store(tmp_path), _kernel()
    approval = granted(store)
    case_id = _case_carrying(approval.approval_id, cases)
    task = cases.assign_review(case_id=case_id, task_type=ReviewTaskType.SECONDARY_APPROVAL,
                               assigned_to=APPROVER.approver_id, required_role=ROLE, actor=ACTOR)
    clear_review_when_consumed(store, cases, approval_id=approval.approval_id,
                               subject_digest=approval.subject_digest, case_id=case_id,
                               task_id=task.task_id, actor=APPROVER.approver_id, as_of=T2)

    consumed = store.get_approval(approval.approval_id)
    assert consumed.consumer_ref == f"decision_case:{case_id}/review_task:{task.task_id}"
    assert not hasattr(cases.repo.get_review_task(task.task_id), "metadata")
    store.close()


# --------------------------------------------------------------------------- #
# The negatives — no consumption, no call, still blocked
# --------------------------------------------------------------------------- #
def test_a_lapsed_approval_clears_nothing(tmp_path):
    store, cases = sqlite_store(tmp_path), _kernel()
    approval = granted(store)
    case_id = _case_carrying(approval.approval_id, cases)
    task = cases.assign_review(case_id=case_id, task_type=ReviewTaskType.SECONDARY_APPROVAL,
                               assigned_to=APPROVER.approver_id, required_role=ROLE, actor=ACTOR)

    outcome = clear_review_when_consumed(
        store, cases, approval_id=approval.approval_id,
        subject_digest=approval.subject_digest, case_id=case_id, task_id=task.task_id,
        actor=APPROVER.approver_id, as_of=AFTER_WINDOW)
    assert outcome.result is ConsumptionResult.EXPIRED_APPROVAL and outcome.resolution is None
    assert cases.complete_review_calls == []

    still = cases.validate_decision_readiness(case_id=case_id, actor=ACTOR)
    assert not still.ready and _blockers(still) == {"REQUIRED_REVIEW_OUTSTANDING"}
    assert cases.repo.get_review_task(task.task_id).status is ReviewTaskStatus.PENDING
    store.close()


def test_an_already_consumed_approval_cannot_clear_a_second_case(tmp_path):
    store, cases = sqlite_store(tmp_path), _kernel()
    approval = granted(store)

    first_case = _case_carrying(approval.approval_id, cases)
    first_task = cases.assign_review(case_id=first_case, task_type=ReviewTaskType.SECONDARY_APPROVAL,
                                     assigned_to=APPROVER.approver_id, required_role=ROLE,
                                     actor=ACTOR)
    assert clear_review_when_consumed(
        store, cases, approval_id=approval.approval_id, subject_digest=approval.subject_digest,
        case_id=first_case, task_id=first_task.task_id, actor=APPROVER.approver_id,
        as_of=T2).is_consumed

    second_case = _case_carrying(approval.approval_id, cases)
    second_task = cases.assign_review(case_id=second_case,
                                      task_type=ReviewTaskType.SECONDARY_APPROVAL,
                                      assigned_to=APPROVER.approver_id, required_role=ROLE,
                                      actor=ACTOR)
    outcome = clear_review_when_consumed(
        store, cases, approval_id=approval.approval_id, subject_digest=approval.subject_digest,
        case_id=second_case, task_id=second_task.task_id, actor=APPROVER.approver_id, as_of=T2)
    assert outcome.result is ConsumptionResult.ALREADY_CONSUMED and not outcome.is_consumed
    assert cases.complete_review_calls == [(first_case, first_task.task_id)]

    still = cases.validate_decision_readiness(case_id=second_case, actor=ACTOR)
    assert not still.ready and _blockers(still) == {"REQUIRED_REVIEW_OUTSTANDING"}
    assert cases.repo.get_review_task(second_task.task_id).status is ReviewTaskStatus.PENDING
    store.close()


def test_an_ungranted_approval_clears_nothing(tmp_path):
    store, cases = sqlite_store(tmp_path), _kernel()
    approval = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                      validity=window(), as_of=T0)
    store.present_for_decision(approval.approval_id, as_of=T0)
    case_id = _case_carrying(approval.approval_id, cases)
    task = cases.assign_review(case_id=case_id, task_type=ReviewTaskType.SECONDARY_APPROVAL,
                               assigned_to=APPROVER.approver_id, required_role=ROLE, actor=ACTOR)

    outcome = clear_review_when_consumed(
        store, cases, approval_id=approval.approval_id, subject_digest=approval.subject_digest,
        case_id=case_id, task_id=task.task_id, actor=APPROVER.approver_id, as_of=T1)
    assert outcome.result is ConsumptionResult.NOT_GRANTED
    assert cases.complete_review_calls == []
    assert not cases.validate_decision_readiness(case_id=case_id, actor=ACTOR).ready
    store.close()


def test_a_changed_subject_clears_nothing(tmp_path):
    """The case moved on since approval: the digest no longer matches, so nothing clears."""

    store, cases = sqlite_store(tmp_path), _kernel()
    approval = granted(store)
    case_id = _case_carrying(approval.approval_id, cases)
    task = cases.assign_review(case_id=case_id, task_type=ReviewTaskType.SECONDARY_APPROVAL,
                               assigned_to=APPROVER.approver_id, required_role=ROLE, actor=ACTOR)

    outcome = clear_review_when_consumed(
        store, cases, approval_id=approval.approval_id, subject_digest=OTHER_DIGEST,
        case_id=case_id, task_id=task.task_id, actor=APPROVER.approver_id, as_of=T2)
    assert outcome.result is ConsumptionResult.SUBJECT_MISMATCH
    assert cases.complete_review_calls == []
    assert cases.repo.get_review_task(task.task_id).status is ReviewTaskStatus.PENDING
    store.close()
