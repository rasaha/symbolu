"""The service core over a real SQLite ledger and an adapter double: rows 1 and 5 of
the human-review ADR's failure matrix, the refusals, HR-5 filtering and run detail."""

from __future__ import annotations

import pytest

from ugence_approval_workflow import (
    ApprovalState,
    ApproverKind,
    ApproverRef,
    ReviewDecision,
    StaticApproverEligibility,
)

from ugence_governed_review_service import (
    IDENTITY_PROOF,
    SIGNAL_NAME,
    ClockDisciplineError,
    ContractViolation,
    DecisionResult,
    ReviewService,
    StaticRunReader,
)

import _service_fixtures as S

F = S.F
FP = "a" * 64


@pytest.fixture()
def world(tmp_path):
    clock = F.Clock()
    ledger = F.sqlite_ledger(tmp_path)
    adapter = S.RecordingAdapter(known=("i1",))
    reader = StaticRunReader({"i1": S.parked_checkpoint("i1", "t1", FP)})
    svc = S.service(ledger, clock, adapter=adapter, reader=reader,
                    eligibility=StaticApproverEligibility((F.APPROVER,)))
    record = S.request_for(ledger, clock, "i1", fingerprint=FP)
    return {"clock": clock, "ledger": ledger, "adapter": adapter, "svc": svc,
            "approval_id": record.approval_id}


# --------------------------------------------------------------------------- #
# the happy path
# --------------------------------------------------------------------------- #
def test_a_grant_is_recorded_then_signal_and_bounded_resume_are_delivered(world):
    out = world["svc"].submit_decision(approval_id=world["approval_id"],
                                       decision=ReviewDecision.GRANT,
                                       presented_approver=F.APPROVER, justification="ok")
    assert out.result is DecisionResult.RECORDED and out.recorded
    assert out.instance_id == "i1" and out.task_id == "t1"
    assert out.identity_proof == IDENTITY_PROOF == "PRESENTED_UNPROVEN"
    assert out.approval.state is ApprovalState.GRANTED
    assert out.approval.decided_by == F.APPROVER.approver_id
    assert world["adapter"].signals == [("i1", SIGNAL_NAME, world["adapter"].signals[0][2])]
    payload = world["adapter"].signals[0][2]
    assert payload["approval_id"] == world["approval_id"] and payload["decision"] == "GRANT"
    assert payload["subject_digest"] == FP and payload["identity_proof"] == IDENTITY_PROOF
    assert world["adapter"].resumes == ["i1"] and out.resume_delivered


def test_a_reject_is_recorded_signalled_and_leaves_the_instance_parked(world):
    out = world["svc"].submit_decision(approval_id=world["approval_id"],
                                       decision=ReviewDecision.REJECT,
                                       presented_approver=F.APPROVER)
    assert out.result is DecisionResult.RECORDED
    assert out.approval.state is ApprovalState.REJECTED
    assert [s[1] for s in world["adapter"].signals] == [SIGNAL_NAME]
    assert world["adapter"].resumes == [] and not out.resume_delivered
    assert "parked" in out.resume_skipped_reason


# --------------------------------------------------------------------------- #
# Row 1 — duplicate decision
# --------------------------------------------------------------------------- #
def test_row_01_an_identical_resubmission_replays_and_a_different_one_is_refused(world):
    svc, ledger, aid = world["svc"], world["ledger"], world["approval_id"]
    first = svc.submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                                presented_approver=F.APPROVER)
    assert first.result is DecisionResult.RECORDED

    again = svc.submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                                presented_approver=F.APPROVER)
    assert again.result is DecisionResult.REPLAYED and again.recorded
    assert again.approval.decided_at == first.approval.decided_at, "nothing re-decided"

    reject = svc.submit_decision(approval_id=aid, decision=ReviewDecision.REJECT,
                                 presented_approver=F.APPROVER)
    assert reject.result is DecisionResult.REFUSED_ALREADY_DECIDED and not reject.recorded
    other = ApproverRef(approver_id="approver-2", approver_kind=ApproverKind.HUMAN, role=F.ROLE)
    by_other = svc.submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                                   presented_approver=other)
    assert by_other.result is DecisionResult.REFUSED_ALREADY_DECIDED

    assert ledger.get_approval(aid).state is ApprovalState.GRANTED, "the first stands"
    events = [e.event_type for e in ledger.approval_events(aid)]
    assert events.count(ApprovalState.GRANTED) == 1 and ApprovalState.REJECTED not in events


def test_row_01_a_replay_re_signals_but_never_re_arms_a_running_instance(tmp_path):
    """Row 9's shape at the service: the second delivery is recorded, changes nothing."""

    clock = F.Clock()
    ledger = F.sqlite_ledger(tmp_path)
    adapter = S.RecordingAdapter(known=("i1",))
    reader = StaticRunReader({"i1": S.parked_checkpoint("i1", "t1", FP)})
    svc = S.service(ledger, clock, adapter=adapter, reader=reader)
    aid = S.request_for(ledger, clock, "i1", fingerprint=FP).approval_id
    first = svc.submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                                presented_approver=F.APPROVER)
    assert first.resume_delivered
    # The instance is now armed (RUNNING) in durable state.
    reader._checkpoints["i1"]["status"] = "RUNNING"
    again = svc.submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                                presented_approver=F.APPROVER)
    assert again.result is DecisionResult.REPLAYED
    assert again.signal_delivered and not again.resume_delivered
    assert "RUNNING" in again.resume_skipped_reason
    assert len(adapter.signals) == 2 and adapter.resumes == ["i1"]


# --------------------------------------------------------------------------- #
# Row 5 — wrong approver
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("approver", [
    ApproverRef(approver_id="nobody", approver_kind=ApproverKind.HUMAN, role=F.ROLE),
    F.OTHER_ROLE_APPROVER,
    ApproverRef(approver_id=F.REQUESTER, approver_kind=ApproverKind.HUMAN, role=F.ROLE),
    ApproverRef(approver_id="svc", approver_kind=ApproverKind.SERVICE, role=F.ROLE),
])
def test_row_05_an_ineligible_presented_approver_is_refused_before_any_record_changes(world, approver):
    out = world["svc"].submit_decision(approval_id=world["approval_id"],
                                       decision=ReviewDecision.GRANT,
                                       presented_approver=approver)
    assert out.result is DecisionResult.REFUSED_INELIGIBLE and not out.recorded
    assert out.reason
    record = world["ledger"].get_approval(world["approval_id"])
    assert record.state is ApprovalState.PENDING and record.decided_by == ""
    assert world["adapter"].signals == [] and world["adapter"].resumes == []
    events = [e.event_type for e in world["ledger"].approval_events(world["approval_id"])]
    assert ApprovalState.GRANTED not in events


# --------------------------------------------------------------------------- #
# the other refusals
# --------------------------------------------------------------------------- #
def test_unknown_approval_is_refused(world):
    out = world["svc"].submit_decision(approval_id="nope", decision=ReviewDecision.GRANT,
                                       presented_approver=F.APPROVER)
    assert out.result is DecisionResult.REFUSED_UNKNOWN_APPROVAL and world["adapter"].signals == []


def test_request_changes_is_not_a_decision_on_this_path(world):
    out = world["svc"].submit_decision(approval_id=world["approval_id"],
                                       decision=ReviewDecision.REQUEST_CHANGES,
                                       presented_approver=F.APPROVER)
    assert out.result is DecisionResult.REFUSED_INVALID_DECISION
    assert world["ledger"].get_approval(world["approval_id"]).state is ApprovalState.PENDING


def test_an_approval_that_is_not_a_governed_proposal_is_not_reviewable_here(tmp_path):
    from datetime import timedelta

    from ugence_approval_workflow import ApprovalSubject
    from ugence_governance_contracts.api import Validity

    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    now = clock.datetime()
    rec = ledger.request_approval(
        ApprovalSubject(tenant_id=F.TENANT, subject_kind="policy_bundle", subject_digest="b" * 64,
                        subject_ref="bundle-1"),
        requested_by="someone", required_role=F.ROLE,
        validity=Validity(issued_at=now, expires_at=now + timedelta(days=1)), as_of=now)
    adapter = S.RecordingAdapter()
    svc = S.service(ledger, clock, adapter=adapter)
    out = svc.submit_decision(approval_id=rec.approval_id, decision=ReviewDecision.GRANT,
                              presented_approver=F.APPROVER)
    assert out.result is DecisionResult.REFUSED_NOT_REVIEWABLE and adapter.signals == []
    assert svc.list_queue() == (), "not a proposal, not this queue's"


def test_an_expired_request_is_not_open(world):
    world["clock"].advance(days=8)
    out = world["svc"].submit_decision(approval_id=world["approval_id"],
                                       decision=ReviewDecision.GRANT,
                                       presented_approver=F.APPROVER)
    assert out.result is DecisionResult.REFUSED_NOT_OPEN and not out.recorded
    assert world["adapter"].signals == []


def test_a_requested_but_unpresented_approval_is_presented_then_decided(tmp_path):
    from datetime import timedelta

    from ugence_governed_review import ProposalIdentity, subject_for
    from ugence_governance_contracts.api import Validity

    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    now = clock.datetime()
    rec = ledger.request_approval(
        subject_for(ProposalIdentity(fingerprint=FP, instance_id="i1", task_id="t1"),
                    tenant_id=F.TENANT),
        requested_by=F.REQUESTER, required_role=F.ROLE,
        validity=Validity(issued_at=now, expires_at=now + timedelta(days=1)), as_of=now)
    assert rec.state is ApprovalState.REQUESTED
    svc = S.service(ledger, clock, reader=StaticRunReader({"i1": S.parked_checkpoint("i1", "t1", FP)}))
    out = svc.submit_decision(approval_id=rec.approval_id, decision=ReviewDecision.GRANT,
                              presented_approver=F.APPROVER)
    assert out.result is DecisionResult.RECORDED
    events = [e.event_type for e in ledger.approval_events(rec.approval_id)]
    assert events == [ApprovalState.REQUESTED, ApprovalState.PENDING, ApprovalState.GRANTED]


# --------------------------------------------------------------------------- #
# the queue (HR-5) and run detail
# --------------------------------------------------------------------------- #
def test_the_queue_lists_parked_escalate_instances_with_their_approval_identity(world):
    (entry,) = world["svc"].list_queue()
    assert entry.approval_id == world["approval_id"]
    assert entry.approval_state is ApprovalState.PENDING
    assert (entry.instance_id, entry.task_id, entry.fingerprint) == ("i1", "t1", FP)
    assert entry.governance_disposition == "ESCALATE" and entry.workflow_status == "PAUSED"
    assert entry.task_status == "WAITING" and entry.instance_known
    assert entry.provider_id == "p" and entry.operation == "op"
    assert [a.approver_id for a in entry.eligible_approvers] == [F.APPROVER.approver_id]
    assert world["svc"].list_queue(required_role="auditor") == ()


def test_the_queue_never_lists_a_hold_even_if_a_request_exists_for_it(tmp_path):
    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    reader = StaticRunReader({
        "esc": S.parked_checkpoint("esc", "t1", "e" * 64, disposition="ESCALATE"),
        "hold": S.parked_checkpoint("hold", "t1", "h" * 64, disposition="HOLD", status="WAITING"),
    })
    svc = S.service(ledger, clock, reader=reader)
    S.request_for(ledger, clock, "esc", fingerprint="e" * 64)
    S.request_for(ledger, clock, "hold", fingerprint="h" * 64)
    assert [e.instance_id for e in svc.list_queue()] == ["esc"]


def test_the_queue_drops_a_decided_approval_and_keeps_an_unknown_instance_visible(world):
    world["svc"].submit_decision(approval_id=world["approval_id"], decision=ReviewDecision.GRANT,
                                 presented_approver=F.APPROVER)
    assert world["svc"].list_queue() == ()
    # A request whose instance the durable store does not know is still shown, flagged.
    S.request_for(world["ledger"], world["clock"], "ghost", fingerprint="9" * 64)
    (entry,) = world["svc"].list_queue()
    assert entry.instance_id == "ghost" and not entry.instance_known
    assert entry.workflow_status == "" and entry.governance_disposition == ""


def test_run_detail_and_events_and_approval_reads(world):
    run = world["svc"].read_run("i1")
    assert run["instance"]["status"] == "PAUSED" and run["engine"]["known"]
    assert [a["approval_id"] for a in run["open_approvals"]] == [world["approval_id"]]
    assert run["open_approvals"][0]["instance_id"] == "i1"
    assert run["identity_proof"] == IDENTITY_PROOF
    assert world["svc"].read_run("nope") is None
    assert world["svc"].read_run_events("i1") == () and world["svc"].read_run_events("nope") is None
    view = world["svc"].read_approval(world["approval_id"])
    assert view["state_at"] == "PENDING" and [e["event_type"] for e in view["events"]] == \
        ["REQUESTED", "PENDING"]
    assert world["svc"].read_approval("nope") is None


# --------------------------------------------------------------------------- #
# construction and clock discipline
# --------------------------------------------------------------------------- #
def test_construction_refuses_the_wrong_seams(tmp_path):
    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    with pytest.raises(ContractViolation):
        ReviewService(ledger=object(), adapter=S.RecordingAdapter(), reader=StaticRunReader(),
                      tenant_id=F.TENANT, clock=clock.datetime)
    with pytest.raises(ContractViolation):
        ReviewService(ledger=ledger, adapter=object(), reader=StaticRunReader(),
                      tenant_id=F.TENANT, clock=clock.datetime)
    with pytest.raises(ContractViolation):
        ReviewService(ledger=ledger, adapter=S.RecordingAdapter(), reader=object(),
                      tenant_id=F.TENANT, clock=clock.datetime)
    with pytest.raises(ContractViolation):
        ReviewService(ledger=ledger, adapter=S.RecordingAdapter(), reader=StaticRunReader(),
                      tenant_id=" ", clock=clock.datetime)


def test_a_naive_clock_is_refused(tmp_path):
    from datetime import datetime

    ledger = F.sqlite_ledger(tmp_path)
    svc = ReviewService(ledger=ledger, adapter=S.RecordingAdapter(), reader=StaticRunReader(),
                        tenant_id=F.TENANT, clock=lambda: datetime(2026, 1, 1))
    with pytest.raises(ClockDisciplineError):
        svc.list_queue()
