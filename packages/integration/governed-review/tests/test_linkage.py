"""The receipt linkage (HR-E), contract only.

Two layers. At unit level, over the real SQLite ledger and synthetic event and journal
inputs, every refusal the join can make. Against the real stores, one instance that
parks on ESCALATE, is decided, signalled, resumed and run, reconstructed by id join
from the approval ledger, the DBOS event log and the checkpoint's execution-state
journal on a real PostgreSQL — and the digest that comes back is the same digest a
second reconstruction produces.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
import sqlalchemy as sa

import _hooks
from _dbos_harness import DEFINITION_DIGEST, WORKFLOW_ID, RecordingProvider, wire
from _hooks import EVAL_LOG_DDL
from conftest import requires_postgres

from ugence_agent_runtime_governance import GovernedExecutionHook
from ugence_approval_workflow import ApprovalState, ConsumptionResult, ReviewDecision
from ugence_governance_contracts.api import AuditReference, EvidenceReference

from ugence_governed_review import (
    EVIDENCE_KIND,
    LINKAGE_VERSION,
    SIGNAL_EVENT_TYPE,
    STORE_APPROVAL_LEDGER,
    STORE_EXECUTION_JOURNAL,
    STORE_RUNTIME_EVENTS,
    LinkageError,
    ProposalIdentity,
    ReviewLinkage,
    expected_consumption_id,
    reconstruct,
    subject_for,
)

import _fixtures as F

FP = "c" * 64


# --------------------------------------------------------------------------- #
# synthetic inputs, real ledger
# --------------------------------------------------------------------------- #
def _consumed_approval(ledger, clock, instance_id="i1", task_id="t1", fingerprint=FP,
                       authentication_reference=""):
    identity = ProposalIdentity(fingerprint=fingerprint, instance_id=instance_id, task_id=task_id)
    now = clock.datetime()
    rec = ledger.request_approval(
        subject_for(identity, tenant_id=F.TENANT), requested_by=F.REQUESTER, required_role=F.ROLE,
        validity=F.window(now, hours=48), as_of=now)
    ledger.present_for_decision(rec.approval_id, as_of=now)
    clock.advance(minutes=5)
    F.decide(ledger, rec.approval_id, as_of=clock.datetime(),
             authentication_reference=authentication_reference)
    clock.advance(minutes=1)
    out = ledger.consume(rec.approval_id, consumer_ref=f"{instance_id}:{task_id}",
                         subject_digest=fingerprint, as_of=clock.datetime())
    assert out.result is ConsumptionResult.CONSUMED_FIRST
    return rec.approval_id, identity


def _snapshot(digest, *, task_id="t1", fingerprint=FP, disposition, task_status, ref):
    return {"state_digest": digest, "task_id": task_id, "proposal_fingerprint": fingerprint,
            "governance_disposition": disposition, "task_status": task_status,
            "evaluation_reference": ref, "correlation_id": "corr-1"}


def _disp(seq, disposition, digest, task_id="t1"):
    return {"seq": seq, "event_type": "", "body": {"seq": seq, "type": "GOVERNANCE_DISPOSITION_RECEIVED",
            "detail": {"task_id": task_id, "disposition": disposition, "execution_state_digest": digest}}}


def _events(approval_id="", with_signal=True, parked_digest="a" * 64, resumed_digest="b" * 64,
            resumed_disposition="CLEAR"):
    events = [
        _disp(1, "ESCALATE", parked_digest),
        {"seq": 2, "event_type": "", "body": {"seq": 2, "type": "TASK_WAITING", "detail": {}}},
        {"seq": 3, "event_type": "", "body": {"seq": 3, "type": "WORKFLOW_PAUSED", "detail": {"reason": "governance_escalate"}}},
    ]
    if with_signal:
        events.append({"seq": 4, "event_type": SIGNAL_EVENT_TYPE,
                       "body": {"signal": "review_decision", "payload": {"approval_id": approval_id}}})
    events.append({"seq": 5, "event_type": "", "body": {"seq": 5, "type": "WORKFLOW_RESUMED", "detail": {}}})
    events.append(_disp(6, resumed_disposition, resumed_digest))
    return events


def _journal():
    return {
        "a" * 64: _snapshot("a" * 64, disposition="ESCALATE", task_status="WAITING", ref="eval-1"),
        "b" * 64: _snapshot("b" * 64, disposition="CLEAR", task_status="COMPLETED", ref="eval-2"),
    }


@pytest.fixture()
def world(tmp_path):
    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    approval_id, identity = _consumed_approval(ledger, clock)
    return {"clock": clock, "ledger": ledger, "approval_id": approval_id, "identity": identity}


def _reconstruct(world, **over):
    kwargs = dict(tenant_id=F.TENANT, instance_id="i1", task_id="t1",
                  approval_id=world["approval_id"], events=_events(world["approval_id"]),
                  journal=_journal())
    kwargs.update(over)
    return reconstruct(world["ledger"], **kwargs)


def test_the_linkage_joins_the_three_stores_and_digests_deterministically(world):
    r = _reconstruct(world)
    link = r.linkage
    assert link.linkage_version == LINKAGE_VERSION
    assert (link.instance_id, link.task_id, link.consumer_ref) == ("i1", "t1", "i1:t1")
    assert link.proposal_fingerprint == FP and link.approval_state == "CONSUMED"
    assert link.decided_by == F.APPROVER.approver_id and link.decided_role == F.ROLE
    assert link.authentication_reference == "", "decided without a proof: none recorded"
    assert "authentication_reference" in link.to_dict()
    assert link.consumption_id == expected_consumption_id(world["identity"], tenant_id=F.TENANT,
                                                          approval_id=world["approval_id"])
    assert (link.parked_disposition_event_seq, link.paused_event_seq, link.signal_event_seq,
            link.resumed_event_seq, link.resumed_disposition_event_seq) == (1, 3, 4, 5, 6)
    assert (link.parked_state_digest, link.resumed_state_digest) == ("a" * 64, "b" * 64)
    assert (link.parked_evaluation_reference, link.resumed_evaluation_reference) == ("eval-1", "eval-2")
    assert (link.parked_disposition, link.resumed_disposition) == ("ESCALATE", "CLEAR")
    assert link.correlation_id == "corr-1"
    assert link.decided_at is not None and link.consumed_at is not None
    assert link.consumed_at > link.decided_at

    again = _reconstruct(world)
    assert again.linkage == link and again.linkage.digest() == link.digest()
    assert len(link.digest()) == 64
    assert json.loads(json.dumps(link.to_dict()))["decided_at"].endswith("+00:00")


def test_the_linkage_carries_the_authentication_reference_and_digests_it(tmp_path):
    """AI-D, row 9: the reference travels from the record into the linkage, and a
    linkage with a different reference has a different digest."""

    reference = "authn:sha256:" + "ab" * 32
    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    approval_id, _identity = _consumed_approval(ledger, clock, authentication_reference=reference)
    link = reconstruct(ledger, tenant_id=F.TENANT, instance_id="i1", task_id="t1",
                       approval_id=approval_id, events=_events(approval_id),
                       journal=_journal()).linkage
    assert link.authentication_reference == reference
    assert link.to_dict()["authentication_reference"] == reference
    assert link.linkage_version == "governed_review.linkage.v2"
    other = ReviewLinkage(**{**link.to_dict(), "decided_at": link.decided_at,
                             "consumed_at": link.consumed_at,
                             "authentication_reference": "authn:sha256:" + "cd" * 32})
    assert other.digest() != link.digest()
    blank = ReviewLinkage(**{**link.to_dict(), "decided_at": link.decided_at,
                             "consumed_at": link.consumed_at, "authentication_reference": ""})
    assert blank.digest() != link.digest()


def test_the_projections_are_valid_g4_references(world):
    r = _reconstruct(world)
    ev = r.linkage.to_evidence_reference()
    assert isinstance(ev, EvidenceReference)
    assert ev.evidence_kind == EVIDENCE_KIND and ev.subject_id == "i1:t1"
    assert ev.content_digest == r.linkage.digest() and ev.tenant_id == F.TENANT
    refs = r.audit_references()
    assert all(isinstance(a, AuditReference) for a in refs)
    assert [a.store_ref for a in refs] == [
        STORE_RUNTIME_EVENTS, STORE_EXECUTION_JOURNAL, STORE_RUNTIME_EVENTS, STORE_APPROVAL_LEDGER,
        STORE_RUNTIME_EVENTS, STORE_RUNTIME_EVENTS, STORE_RUNTIME_EVENTS, STORE_EXECUTION_JOURNAL,
    ]
    assert [a.entry_ref for a in refs] == [
        "i1:1", "a" * 64, "i1:3", f"{world['approval_id']}:{r.linkage.consumed_event_sequence}",
        "i1:4", "i1:5", "i1:6", "b" * 64,
    ]
    assert refs[1].entry_digest == "a" * 64 and refs[7].entry_digest == "b" * 64
    assert all(a.correlation_id == "corr-1" for a in refs)


def test_a_decision_recorded_without_the_review_service_has_no_signal(world):
    r = _reconstruct(world, events=_events(with_signal=False))
    assert r.linkage.signal_event_seq is None and r.linkage.resumed_event_seq == 5
    assert len(r.audit_references()) == 7


def test_a_changed_event_changes_its_reference_but_not_the_linkage(world):
    r1 = _reconstruct(world)
    events = _events(world["approval_id"])
    events[4]["body"]["detail"] = {"tampered": True}  # the WORKFLOW_RESUMED row
    r2 = _reconstruct(world, events=events)
    assert r1.linkage == r2.linkage
    assert r1.audit_references()[5].entry_digest != r2.audit_references()[5].entry_digest


# --------------------------------------------------------------------------- #
# every refusal
# --------------------------------------------------------------------------- #
def test_unknown_or_foreign_approvals_are_refused(world):
    with pytest.raises(LinkageError, match="unknown"):
        _reconstruct(world, approval_id="nope")
    with pytest.raises(LinkageError, match="another tenant"):
        _reconstruct(world, tenant_id="tenant-b")
    with pytest.raises(LinkageError, match="binds 'i1:t1', not 'i1:t9'"):
        _reconstruct(world, task_id="t9")


def test_an_unconsumed_approval_has_nothing_to_link(tmp_path):
    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    identity = ProposalIdentity(fingerprint=FP, instance_id="i1", task_id="t1")
    now = clock.datetime()
    rec = ledger.request_approval(subject_for(identity, tenant_id=F.TENANT), requested_by=F.REQUESTER,
                                  required_role=F.ROLE, validity=F.window(now, hours=1), as_of=now)
    ledger.present_for_decision(rec.approval_id, as_of=now)
    F.decide(ledger, rec.approval_id, as_of=now)
    assert ledger.get_approval(rec.approval_id).state is ApprovalState.GRANTED
    with pytest.raises(LinkageError, match="is GRANTED; no consumption"):
        reconstruct(ledger, tenant_id=F.TENANT, instance_id="i1", task_id="t1",
                    approval_id=rec.approval_id, events=_events(rec.approval_id), journal=_journal())


def test_a_consumption_held_by_another_instance_is_refused(tmp_path):
    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    identity = ProposalIdentity(fingerprint=FP, instance_id="i1", task_id="t1")
    now = clock.datetime()
    rec = ledger.request_approval(subject_for(identity, tenant_id=F.TENANT), requested_by=F.REQUESTER,
                                  required_role=F.ROLE, validity=F.window(now, hours=1), as_of=now)
    ledger.present_for_decision(rec.approval_id, as_of=now)
    F.decide(ledger, rec.approval_id, as_of=now)
    out = ledger.consume(rec.approval_id, consumer_ref="i2:t1", subject_digest=FP, as_of=now)
    assert out.result is ConsumptionResult.CONSUMED_FIRST
    with pytest.raises(LinkageError, match="consumed by 'i2:t1'"):
        reconstruct(ledger, tenant_id=F.TENANT, instance_id="i1", task_id="t1",
                    approval_id=rec.approval_id, events=_events(rec.approval_id), journal=_journal())


def test_event_order_is_enforced(world):
    aid = world["approval_id"]
    with pytest.raises(LinkageError, match="never parked"):
        _reconstruct(world, events=[e for e in _events(aid) if e["seq"] != 3])
    with pytest.raises(LinkageError, match="no WORKFLOW_RESUMED event after the park and the decision signal"):
        _reconstruct(world, events=[e for e in _events(aid) if e["seq"] != 5])
    with pytest.raises(LinkageError, match="no governance disposition was recorded for this task before"):
        _reconstruct(world, events=[e for e in _events(aid) if e["seq"] != 1])
    with pytest.raises(LinkageError, match="has not happened"):
        _reconstruct(world, events=[e for e in _events(aid) if e["seq"] != 6])
    # A resume recorded BEFORE the decision signal does not count as the decision's resume.
    early = [
        _disp(1, "ESCALATE", "a" * 64),
        {"seq": 2, "event_type": "", "body": {"seq": 2, "type": "WORKFLOW_PAUSED", "detail": {}}},
        {"seq": 3, "event_type": "", "body": {"seq": 3, "type": "WORKFLOW_RESUMED", "detail": {}}},
        {"seq": 4, "event_type": SIGNAL_EVENT_TYPE, "body": {"payload": {"approval_id": aid}}},
    ]
    with pytest.raises(LinkageError, match="no WORKFLOW_RESUMED"):
        _reconstruct(world, events=early)
    # A signal for a different approval is not this decision's signal.
    r = _reconstruct(world, events=_events("apr-other"))
    assert r.linkage.signal_event_seq is None


def test_a_park_on_hold_or_a_resumed_evaluation_that_is_not_clear_is_refused(world):
    aid = world["approval_id"]
    hold = _events(aid)
    hold[0]["body"]["detail"]["disposition"] = "HOLD"
    with pytest.raises(LinkageError, match="parked on 'HOLD'"):
        _reconstruct(world, events=hold)
    with pytest.raises(LinkageError, match="resumed evaluation was 'ESCALATE'"):
        _reconstruct(world, events=_events(aid, resumed_disposition="ESCALATE"))


def test_the_journal_must_hold_the_snapshots_the_events_name(world):
    aid = world["approval_id"]
    j = _journal()
    j.pop("a" * 64)
    with pytest.raises(LinkageError, match="which the journal does not hold"):
        _reconstruct(world, journal=j)
    j = _journal()
    j["b" * 64]["state_digest"] = "f" * 64
    with pytest.raises(LinkageError, match="does not carry its own state digest"):
        _reconstruct(world, journal=j)
    j = _journal()
    j["b" * 64]["proposal_fingerprint"] = "9" * 64
    with pytest.raises(LinkageError, match="decided about a different action"):
        _reconstruct(world, journal=j)
    j = _journal()
    j["b" * 64]["governance_disposition"] = "ESCALATE"
    with pytest.raises(LinkageError, match="disagrees with its event"):
        _reconstruct(world, journal=j)
    j = _journal()
    j["a" * 64]["task_id"] = "t2"
    with pytest.raises(LinkageError, match="belongs to task 't2'"):
        _reconstruct(world, journal=j)
    assert _reconstruct(world, events=_events(aid)).linkage.resumed_state_digest == "b" * 64


# --------------------------------------------------------------------------- #
# the real stores
# --------------------------------------------------------------------------- #
class RecordingHook:
    def __init__(self, url, source):
        self._engine = sa.create_engine(url)
        self._hook = GovernedExecutionHook(source=source)
        with self._engine.begin() as c:
            c.execute(sa.text(EVAL_LOG_DDL))

    def evaluate(self, proposal, evaluation_time):
        result = self._hook.evaluate(proposal, evaluation_time)
        with self._engine.begin() as c:
            c.execute(sa.text("INSERT INTO governance_evaluations (instance_id, task_id, fingerprint, "
                              "disposition, process_tag) VALUES (:i, :t, :f, :d, :p)"),
                      {"i": proposal.instance_id, "t": proposal.task_id, "f": proposal.fingerprint,
                       "d": result.disposition.value, "p": "linkage"})
        return result

    def envelope_for(self, proposal):
        return self._hook.envelope_for(proposal)

    def consume_envelope(self, proposal):
        return self._hook.consume_envelope(proposal)


def _read_events(ds, instance_id):
    def _q():
        rows = ds.sql_session().execute(sa.text(
            "SELECT seq, event_type, body FROM ugence_art.runtime_events WHERE instance_id=:i ORDER BY seq"),
            {"i": instance_id}).all()
        return [{"seq": int(s), "event_type": str(t or ""), "body": (json.loads(b) if isinstance(b, str) else dict(b))}
                for s, t, b in rows]
    return ds.run_tx_step(None, _q)


def _read_journal(ds, bundle, instance_id):
    def _q():
        ckpt = bundle.state_store.load(instance_id)
        return {k: dict(v) for k, v in ckpt.execution_state_journal.items()}, ckpt.correlation_id
    return ds.run_tx_step(None, _q)


@requires_postgres
@pytest.mark.matrix
def test_one_parked_approved_resumed_instance_reconstructs_from_the_real_stores(pg_databases, tmp_path):
    from dbos import DBOS

    app, sysdb = pg_databases
    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    src = F.source(ledger, clock)
    ds, dbos, adapter, bundle = wire(app_url=app, sys_url=sysdb, provider=RecordingProvider(app),
                                     hook=RecordingHook(app, src), clock=clock.epoch)
    try:
        adapter.start(workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
                      instance_id="lk1", correlation_id="corr-lk1", inputs={})
        parked = adapter.advance(instance_id="lk1", attempt_token="a1")
        assert parked.awaiting_external
        (approval_id,) = [r.approval_id for r in ledger.list_open(tenant_id=F.TENANT, as_of=clock.datetime())]
        fingerprint = ledger.get_approval(approval_id).subject_digest

        clock.advance(minutes=5)
        F.decide(ledger, approval_id, as_of=clock.datetime())
        adapter.signal(instance_id="lk1", signal_name="review_decision",
                       payload={"approval_id": approval_id, "decision": "GRANT"})
        adapter.resume(instance_id="lk1")
        clock.advance(minutes=1)
        ran = adapter.advance(instance_id="lk1", attempt_token="a2")
        assert ran.progressed and _hooks.provider_calls(app) == ["lk1:t1"]
        adapter.advance(instance_id="lk1", attempt_token="a3")  # finalise
        assert ledger.get_approval(approval_id).state is ApprovalState.CONSUMED

        events = _read_events(ds, "lk1")
        journal, correlation_id = _read_journal(ds, bundle, "lk1")
        r = reconstruct(ledger, tenant_id=F.TENANT, instance_id="lk1", task_id="t1",
                        approval_id=approval_id, events=events, journal=journal,
                        correlation_id=correlation_id or "")
        link = r.linkage
        assert link.proposal_fingerprint == fingerprint
        assert link.correlation_id == "corr-lk1"
        assert link.parked_disposition_event_seq < link.paused_event_seq < link.signal_event_seq \
            < link.resumed_event_seq < link.resumed_disposition_event_seq
        assert link.parked_disposition == "ESCALATE" and link.resumed_disposition == "CLEAR"
        assert link.parked_state_digest != link.resumed_state_digest, "the resumed evaluation is fresh"
        assert journal[link.parked_state_digest]["proposal_fingerprint"] == fingerprint
        assert journal[link.resumed_state_digest]["proposal_fingerprint"] == fingerprint
        assert link.consumption_id == expected_consumption_id(
            ProposalIdentity(fingerprint=fingerprint, instance_id="lk1", task_id="t1"),
            tenant_id=F.TENANT, approval_id=approval_id)
        # The evaluation log the hook kept agrees with what the journal says.
        assert [d for (_f, d, _p) in _hooks.evaluations(app, "lk1")] == ["ESCALATE", "CLEAR"]

        again = reconstruct(ledger, tenant_id=F.TENANT, instance_id="lk1", task_id="t1",
                            approval_id=approval_id, events=_read_events(ds, "lk1"),
                            journal=_read_journal(ds, bundle, "lk1")[0], correlation_id="corr-lk1")
        assert again.linkage.digest() == link.digest()
        refs = r.audit_references()
        assert len(refs) == 8 and all(isinstance(a, AuditReference) for a in refs)
        assert isinstance(link.to_evidence_reference(), EvidenceReference)
        assert ledger.verify_chain()
    finally:
        try:
            DBOS.destroy()
        except Exception:
            pass
