"""The state machine: shape, forward-only transitions, the exception branch,
derived expiry, and the refusal to re-review a subject that did not change.

Every case runs against **both** adapters, so the durable store and the reference
store cannot drift apart.
"""

from __future__ import annotations

import pytest

from ugence_governance_contracts.api import Validity, ValidityStatus

from ugence_approval_workflow import (
    LEGAL_TRANSITIONS,
    OPEN_STATES,
    STATE_RANK,
    TERMINAL_STATES,
    ApprovalState,
    ContractViolation,
    EligibilityRefused,
    IllegalTransitionError,
    ReviewDecision,
    StaticApproverEligibility,
    is_legal_transition,
)

from _fixtures import (
    AFTER_WINDOW,
    AI_APPROVER,
    APPROVER,
    OTHER_DIGEST,
    REQUESTER,
    ROLE,
    SECOND_APPROVER,
    T0,
    T1,
    T2,
    granted,
    memory_store,
    sqlite_store,
    subject,
    window,
)


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    s = memory_store() if request.param == "memory" else sqlite_store(tmp_path)
    yield s
    s.close()


# --------------------------------------------------------------------------- #
# The machine itself
# --------------------------------------------------------------------------- #
def test_every_legal_transition_is_forward_only():
    for current, targets in LEGAL_TRANSITIONS.items():
        for target in targets:
            assert STATE_RANK[target] > STATE_RANK[current], (current, target)


def test_the_ratified_shape_is_exactly_what_ships():
    assert LEGAL_TRANSITIONS[ApprovalState.REQUESTED] == frozenset(
        {ApprovalState.PENDING, ApprovalState.WITHDRAWN, ApprovalState.EXPIRED})
    assert LEGAL_TRANSITIONS[ApprovalState.PENDING] == frozenset(
        {ApprovalState.GRANTED, ApprovalState.REJECTED, ApprovalState.CHANGES_REQUIRED,
         ApprovalState.WITHDRAWN, ApprovalState.EXPIRED, ApprovalState.EXCEPTION_REQUESTED})
    assert LEGAL_TRANSITIONS[ApprovalState.EXCEPTION_REQUESTED] == frozenset(
        {ApprovalState.EXCEPTION_GRANTED, ApprovalState.EXCEPTION_DENIED,
         ApprovalState.WITHDRAWN, ApprovalState.EXPIRED})
    # Only a granted approval — ordinary or by exception — is ever consumed.
    assert {s for s, nxt in LEGAL_TRANSITIONS.items() if ApprovalState.CONSUMED in nxt} == {
        ApprovalState.GRANTED, ApprovalState.EXCEPTION_GRANTED}
    assert TERMINAL_STATES == frozenset(
        {ApprovalState.REJECTED, ApprovalState.CHANGES_REQUIRED, ApprovalState.EXPIRED,
         ApprovalState.WITHDRAWN, ApprovalState.EXCEPTION_DENIED, ApprovalState.CONSUMED})
    assert not is_legal_transition(ApprovalState.CHANGES_REQUIRED, ApprovalState.REQUESTED)
    assert not is_legal_transition(ApprovalState.REQUESTED, ApprovalState.GRANTED)


# --------------------------------------------------------------------------- #
# The happy path
# --------------------------------------------------------------------------- #
def test_request_present_grant(store):
    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    assert record.state is ApprovalState.REQUESTED and record.approval_id.startswith("apr_")
    assert store.list_open(tenant_id=record.tenant_id, as_of=T0) == (record,)

    presented = store.present_for_decision(record.approval_id, as_of=T0)
    assert presented.state is ApprovalState.PENDING

    decided = store.decide(record.approval_id, approver=APPROVER,
                           decision=ReviewDecision.GRANT, as_of=T1,
                           justification="within the risk envelope",
                           accepted_finding_ids=("gap-2",))
    assert decided.state is ApprovalState.GRANTED
    assert decided.decided_by == APPROVER.approver_id and decided.decided_role == ROLE
    assert decided.decided_authority_reference == APPROVER.authority_reference
    assert decided.decided_at == T1 and decided.accepted_finding_ids == ("gap-2",)
    assert store.list_open(tenant_id=record.tenant_id, as_of=T1) == ()
    assert [e.event_type for e in store.approval_events(record.approval_id)] == [
        ApprovalState.REQUESTED, ApprovalState.PENDING, ApprovalState.GRANTED]


def test_the_id_is_derived_and_a_repeat_request_is_refused(store):
    from ugence_approval_workflow import ApprovalAlreadyExistsError, approval_id_for

    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    assert record.approval_id == approval_id_for(subject(), REQUESTER, 1)
    with pytest.raises(ApprovalAlreadyExistsError):
        store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                               validity=window(), as_of=T0)
    # A genuinely new request for the same subject needs a new ordinal.
    again = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                   validity=window(), as_of=T0, request_ordinal=2)
    assert again.approval_id != record.approval_id


def test_a_terminal_decision_is_never_walked_back(store):
    record = granted(store)
    for decision in ReviewDecision:
        with pytest.raises(IllegalTransitionError):
            store.decide(record.approval_id, approver=SECOND_APPROVER, decision=decision, as_of=T2)
    with pytest.raises(IllegalTransitionError):
        store.withdraw(record.approval_id, by=REQUESTER, as_of=T2)


def test_changes_required_is_terminal_and_re_review_needs_a_new_digest(store):
    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    store.present_for_decision(record.approval_id, as_of=T0)
    changed = store.decide(record.approval_id, approver=APPROVER,
                           decision=ReviewDecision.REQUEST_CHANGES, as_of=T1)
    assert changed.state is ApprovalState.CHANGES_REQUIRED
    assert changed.state not in OPEN_STATES

    # Resubmitting the same subject would inherit a standing decision: refused.
    with pytest.raises(ContractViolation):
        store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                               validity=window(), as_of=T2, request_ordinal=2,
                               supersedes=record.approval_id)
    fresh = store.request_approval(subject(OTHER_DIGEST), requested_by=REQUESTER,
                                   required_role=ROLE, validity=window(), as_of=T2,
                                   supersedes=record.approval_id)
    assert fresh.state is ApprovalState.REQUESTED and fresh.supersedes == record.approval_id


# --------------------------------------------------------------------------- #
# Expiry — derived, never swept
# --------------------------------------------------------------------------- #
def test_expiry_is_derived_at_read_time_and_never_written(store):
    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    store.present_for_decision(record.approval_id, as_of=T0)

    assert store.state_at(record.approval_id, as_of=T1) is ApprovalState.PENDING
    assert store.state_at(record.approval_id, as_of=AFTER_WINDOW) is ApprovalState.EXPIRED
    # Nothing swept: the stored state is still PENDING, and an earlier read still says so.
    assert store.get_approval(record.approval_id).state is ApprovalState.PENDING
    assert store.state_at(record.approval_id, as_of=T1) is ApprovalState.PENDING
    assert store.list_open(tenant_id=record.tenant_id, as_of=AFTER_WINDOW) == ()


def test_a_lapsed_request_can_no_longer_be_decided(store):
    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    store.present_for_decision(record.approval_id, as_of=T0)
    with pytest.raises(IllegalTransitionError):
        store.decide(record.approval_id, approver=APPROVER, decision=ReviewDecision.GRANT,
                     as_of=AFTER_WINDOW)


def test_the_validity_boundary_is_half_open(store):
    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    expires = record.validity.expires_at
    assert record.validity_status_at(expires) is ValidityStatus.EXPIRED
    assert record.state_at(expires) is ApprovalState.EXPIRED
    assert record.state_at(T0) is ApprovalState.REQUESTED


def test_a_naive_instant_is_refused_rather_than_assumed_utc(store):
    import datetime as dt

    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    with pytest.raises(ContractViolation):
        store.state_at(record.approval_id, as_of=dt.datetime(2026, 3, 1, 9, 0))


# --------------------------------------------------------------------------- #
# The exception branch
# --------------------------------------------------------------------------- #
def test_a_granted_exception_is_time_boxed_and_consumable(store):
    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    store.present_for_decision(record.approval_id, as_of=T0)
    requested = store.request_exception(
        record.approval_id, requested_by=REQUESTER, justification="regulator deadline",
        exception_validity=window(T1, days=1), as_of=T1)
    assert requested.state is ApprovalState.EXCEPTION_REQUESTED
    assert requested.state in OPEN_STATES

    decided = store.decide_exception(record.approval_id, approver=APPROVER, granted=True, as_of=T2)
    assert decided.state is ApprovalState.EXCEPTION_GRANTED
    assert decided.effective_validity() == window(T1, days=1)
    outcome = store.consume(record.approval_id, consumer_ref="decision_case:case_1/review_task:rev_1",
                            subject_digest=decided.subject_digest, as_of=T2)
    assert outcome.is_consumed


def test_an_unbounded_exception_is_refused(store):
    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    store.present_for_decision(record.approval_id, as_of=T0)
    with pytest.raises(ContractViolation):
        store.request_exception(record.approval_id, requested_by=REQUESTER,
                                justification="indefinite", as_of=T1,
                                exception_validity=Validity(issued_at=T1))


def test_an_exception_is_not_a_second_route_around_the_rules(store):
    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    store.present_for_decision(record.approval_id, as_of=T0)
    store.request_exception(record.approval_id, requested_by=REQUESTER, justification="deadline",
                            exception_validity=window(T1, days=1), as_of=T1)
    with pytest.raises(EligibilityRefused):
        store.decide_exception(record.approval_id, approver=AI_APPROVER, granted=True, as_of=T2)
    # And an exception was never requested on a fresh approval.
    other = store.request_approval(subject(OTHER_DIGEST), requested_by=REQUESTER,
                                   required_role=ROLE, validity=window(), as_of=T0)
    with pytest.raises(IllegalTransitionError):
        store.decide_exception(other.approval_id, approver=APPROVER, granted=True, as_of=T2)


def test_a_lapsed_exception_expires_by_its_own_window(store):
    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(days=30), as_of=T0)
    store.present_for_decision(record.approval_id, as_of=T0)
    store.request_exception(record.approval_id, requested_by=REQUESTER, justification="deadline",
                            exception_validity=window(T1, days=1), as_of=T1)
    store.decide_exception(record.approval_id, approver=APPROVER, granted=True, as_of=T2)
    # The approval window is still open; the exception's own window is not.
    lapsed = T1.replace(day=3)
    assert store.state_at(record.approval_id, as_of=lapsed) is ApprovalState.EXPIRED


# --------------------------------------------------------------------------- #
# Presentation
# --------------------------------------------------------------------------- #
def test_an_approval_nobody_can_decide_is_never_presented(tmp_path):
    empty = StaticApproverEligibility(())
    from ugence_approval_workflow import InMemoryApprovalWorkflowStore

    store = InMemoryApprovalWorkflowStore(empty)
    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    with pytest.raises(EligibilityRefused):
        store.present_for_decision(record.approval_id, as_of=T0)
    store.close()
