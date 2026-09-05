"""The binding, unit level: what changes the composition inputs and what never does.

Every case runs against the real SQLite approval ledger with the real transitions.
The runtime is not involved here; ``test_matrix_rows.py`` proves the same properties
inside the DBOS adapter against PostgreSQL.
"""

from __future__ import annotations

import pytest

from ugence_approval_workflow import ApprovalState, ConsumptionResult, ReviewDecision
from ugence_risk_authority_runtime.contracts import RiskAuthorityDisposition, VetoDisposition

from ugence_governed_review import (
    REASON_APPROVAL_CONSUMED,
    SUBJECT_KIND,
    BindingState,
    ClockDisciplineError,
    ContractViolation,
    ProposalIdentity,
    approval_id_for_identity,
    consumer_ref_for,
    identity_of,
)

import _fixtures as F


def _bound(tmp_path, clock=None, **kw):
    clock = clock or F.Clock()
    ledger = F.sqlite_ledger(tmp_path)
    return ledger, clock, F.source(ledger, clock, **kw)


# --------------------------------------------------------------------------- #
# HR-3: the binding is the fingerprint, the instance and the task
# --------------------------------------------------------------------------- #
def test_identity_and_consumer_ref_follow_hr3():
    p = F.proposal(instance_id="inst", task_id="task")
    ident = identity_of(p)
    assert ident == ProposalIdentity(p.fingerprint, "inst", "task")
    assert consumer_ref_for(ident) == "inst:task"
    assert SUBJECT_KIND == "agent_runtime_proposal"
    same = approval_id_for_identity(ident, tenant_id="t", requester_ref="r")
    again = approval_id_for_identity(identity_of(F.proposal(instance_id="inst", task_id="task")),
                                     tenant_id="t", requester_ref="r")
    assert same == again, "the same proposal names the same approval"


def test_a_different_proposal_names_a_different_approval():
    a = identity_of(F.proposal(arguments={"a": 1}))
    b = identity_of(F.proposal(arguments={"a": 2}))
    assert a.fingerprint != b.fingerprint
    assert approval_id_for_identity(a, tenant_id="t", requester_ref="r") != \
        approval_id_for_identity(b, tenant_id="t", requester_ref="r")


def test_identity_refuses_an_ambiguous_instance_id():
    with pytest.raises(ContractViolation):
        ProposalIdentity("f" * 64, "a:b", "t1")


# --------------------------------------------------------------------------- #
# HR-5: only ESCALATE is reviewable
# --------------------------------------------------------------------------- #
def test_a_clear_composition_passes_through_untouched(tmp_path):
    ledger, clock, src = _bound(tmp_path, upstream=F.UpstreamSource(
        clock=F.Clock(), da=VetoDisposition.NO_VETO, required_approvals=frozenset()))
    p = F.proposal()
    out = src.inputs_for(p)
    assert out.decision_authority.disposition is VetoDisposition.NO_VETO
    assert ledger.list_open(tenant_id=F.TENANT, as_of=clock.datetime()) == ()


def test_a_hold_without_required_approvals_is_never_offered_to_a_human(tmp_path):
    ledger, clock, src = _bound(tmp_path, upstream=F.UpstreamSource(
        clock=F.Clock(), da=VetoDisposition.HOLD, required_approvals=frozenset()))
    out = src.inputs_for(F.proposal())
    assert out.decision_authority.disposition is VetoDisposition.HOLD
    assert ledger.list_open(tenant_id=F.TENANT, as_of=clock.datetime()) == (), (
        "a HOLD with no required approval states no human obligation; requesting one "
        "would be minting it"
    )


def test_a_deny_is_never_bound(tmp_path):
    ledger, clock, src = _bound(tmp_path, upstream=F.UpstreamSource(
        clock=F.Clock(), da=VetoDisposition.DENY, required_approvals=frozenset({F.LABEL})))
    out = src.inputs_for(F.proposal())
    assert out.decision_authority.disposition is VetoDisposition.DENY
    assert ledger.list_open(tenant_id=F.TENANT, as_of=clock.datetime()) == ()


def test_an_absent_upstream_stays_absent(tmp_path):
    ledger, clock, src = _bound(tmp_path, upstream=F.UpstreamSource(clock=F.Clock(), absent=True))
    assert src.inputs_for(F.proposal()) is None


# --------------------------------------------------------------------------- #
# request on park, then consume on grant
# --------------------------------------------------------------------------- #
def test_an_escalate_bound_proposal_raises_a_request_and_stays_parked(tmp_path):
    ledger, clock, src = _bound(tmp_path)
    p = F.proposal()
    out = src.inputs_for(p)
    assert out.decision_authority.disposition is VetoDisposition.HOLD, "not yet approved"
    open_ = ledger.list_open(tenant_id=F.TENANT, as_of=clock.datetime())
    assert len(open_) == 1
    record = open_[0]
    assert record.state is ApprovalState.PENDING
    assert record.subject_kind == SUBJECT_KIND
    assert record.subject_digest == p.fingerprint
    assert record.subject_ref == "i1:t1"
    assert record.required_role == F.ROLE


def test_a_second_evaluation_does_not_raise_a_second_request(tmp_path):
    ledger, clock, src = _bound(tmp_path)
    p = F.proposal()
    src.inputs_for(p)
    src.inputs_for(p)
    assert len(ledger.list_open(tenant_id=F.TENANT, as_of=clock.datetime())) == 1
    assert src.outcome_for(p).state is BindingState.AWAITING_DECISION


def test_a_granted_approval_is_consumed_and_releases_the_hold(tmp_path):
    ledger, clock, src = _bound(tmp_path)
    p = F.proposal()
    src.inputs_for(p)
    approval_id = ledger.list_open(tenant_id=F.TENANT, as_of=clock.datetime())[0].approval_id
    clock.advance(minutes=5)
    F.decide(ledger, approval_id, as_of=clock.datetime())

    out = src.inputs_for(p)
    da = out.decision_authority
    assert da.disposition is VetoDisposition.NO_VETO
    assert da.restrictions.required_approvals == frozenset()
    assert da.restrictions.max_amount_minor_units == 500, "other restrictions stay tightening"
    assert f"{REASON_APPROVAL_CONSUMED}:{approval_id}" in da.reason_codes
    assert ledger.state_at(approval_id, as_of=clock.datetime()) is ApprovalState.CONSUMED
    assert ledger.get_approval(approval_id).consumer_ref == "i1:t1"


def test_a_re_drive_after_consumption_is_still_satisfied(tmp_path):
    """Row 8 at unit level: consumed once, satisfied on every later evaluation."""
    ledger, clock, src = _bound(tmp_path)
    p = F.proposal()
    src.inputs_for(p)
    approval_id = ledger.list_open(tenant_id=F.TENANT, as_of=clock.datetime())[0].approval_id
    F.decide(ledger, approval_id, as_of=clock.datetime())
    first = src.bind(identity_of(p))
    again = src.bind(identity_of(p))
    assert first.consumption is ConsumptionResult.CONSUMED_FIRST
    assert again.consumption is ConsumptionResult.ALREADY_CONSUMED
    assert again.satisfied and again.holder == first.holder
    events = [e.event_type for e in ledger.approval_events(approval_id)]
    assert events.count(ApprovalState.CONSUMED) == 1, "one consumption event, not two"


def test_another_instance_cannot_use_a_consumed_approval(tmp_path):
    """Row 6 at unit level: the consumption is held by one instance and task."""
    ledger, clock, src = _bound(tmp_path)
    p = F.proposal(instance_id="i1")
    src.inputs_for(p)
    approval_id = ledger.list_open(tenant_id=F.TENANT, as_of=clock.datetime())[0].approval_id
    F.decide(ledger, approval_id, as_of=clock.datetime())
    assert src.bind(identity_of(p)).satisfied

    # A hostile identity presenting the same fingerprint from a different instance.
    intruder = ProposalIdentity(p.fingerprint, "i2", "t1")
    outcome = src.bind(intruder)
    assert outcome.state is BindingState.CONSUMED_BY_OTHER
    assert not outcome.satisfied


def test_a_rejected_approval_never_satisfies(tmp_path):
    ledger, clock, src = _bound(tmp_path)
    p = F.proposal()
    src.inputs_for(p)
    approval_id = ledger.list_open(tenant_id=F.TENANT, as_of=clock.datetime())[0].approval_id
    F.decide(ledger, approval_id, as_of=clock.datetime(), decision=ReviewDecision.REJECT)
    out = src.inputs_for(p)
    assert out.decision_authority.disposition is VetoDisposition.HOLD
    assert src.bind(identity_of(p)).state is BindingState.REFUSED


def test_an_expired_approval_is_refused_not_consumed(tmp_path):
    """Row 3 at unit level, on the ledger's own read-time expiry."""
    ledger, clock, src = _bound(tmp_path)
    p = F.proposal()
    src.inputs_for(p)
    approval_id = ledger.list_open(tenant_id=F.TENANT, as_of=clock.datetime())[0].approval_id
    F.decide(ledger, approval_id, as_of=clock.datetime())
    clock.advance(days=8)  # past DEFAULT_REQUEST_VALIDITY
    outcome = src.bind(identity_of(p))
    assert outcome.state is BindingState.REFUSED
    assert outcome.approval_state is ApprovalState.EXPIRED
    assert outcome.consumption is None, "refused on the ledger's read-time expiry; never consumed"
    assert not outcome.satisfied
    assert src.inputs_for(p).decision_authority.disposition is VetoDisposition.HOLD
    assert ledger.get_approval(approval_id).consumer_ref == "", "nothing consumed"
    # The ledger's own consume refuses too, should anything reach it.
    from ugence_governed_review import consumer_ref_for
    direct = ledger.consume(approval_id, consumer_ref=consumer_ref_for(identity_of(p)),
                            subject_digest=p.fingerprint, as_of=clock.datetime())
    assert direct.result is ConsumptionResult.EXPIRED_APPROVAL


def test_a_wrong_approver_is_refused_by_the_ledger_and_nothing_changes(tmp_path):
    from ugence_approval_workflow import EligibilityRefused

    ledger, clock, src = _bound(tmp_path)
    p = F.proposal()
    src.inputs_for(p)
    approval_id = ledger.list_open(tenant_id=F.TENANT, as_of=clock.datetime())[0].approval_id
    with pytest.raises(EligibilityRefused):
        F.decide(ledger, approval_id, as_of=clock.datetime(), approver=F.OTHER_ROLE_APPROVER)
    assert ledger.state_at(approval_id, as_of=clock.datetime()) is ApprovalState.PENDING
    assert src.inputs_for(p).decision_authority.disposition is VetoDisposition.HOLD


def test_no_eligible_approver_leaves_the_request_requested(tmp_path):
    ledger = F.sqlite_ledger(tmp_path, F.OTHER_ROLE_APPROVER)  # nobody holds the role
    clock = F.Clock()
    src = F.source(ledger, clock)
    p = F.proposal()
    src.inputs_for(p)
    outcome = src.bind(identity_of(p))
    assert outcome.state is BindingState.REQUESTED
    assert outcome.approval_state is ApprovalState.REQUESTED


# --------------------------------------------------------------------------- #
# contract and clock discipline
# --------------------------------------------------------------------------- #
def test_the_clock_must_be_timezone_aware(tmp_path):
    from datetime import datetime

    ledger = F.sqlite_ledger(tmp_path)
    src = F.source(ledger, F.Clock())
    src._clock = lambda: datetime(2026, 1, 1)  # noqa: SLF001 - simulate a bad root
    with pytest.raises(ClockDisciplineError):
        src.bind(identity_of(F.proposal()))


def test_construction_refuses_a_ledger_that_is_not_the_port(tmp_path):
    with pytest.raises(ContractViolation):
        F.source(object(), F.Clock())


def test_a_ra_deny_upstream_is_untouched_even_with_labels(tmp_path):
    ledger, clock, src = _bound(tmp_path, upstream=F.UpstreamSource(
        clock=F.Clock(), ra=RiskAuthorityDisposition.DENY))
    out = src.inputs_for(F.proposal())
    assert out.risk_authority.disposition is RiskAuthorityDisposition.DENY
