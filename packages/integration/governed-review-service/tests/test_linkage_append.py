"""HE-1 and HE-5 at unit level: the appender over a real control-plane ledger, with the
real SQLite approval ledger and static event and journal inputs. Idempotency per
linkage digest, the read-only index over the ledger file, the non-blocking NOT_YET,
and the run-detail exposure."""

from __future__ import annotations

import os
from datetime import timedelta

import pytest

from ugence_approval_workflow import ConsumptionResult, ReviewDecision
from ugence_control_plane_root import STORE_REF, AuditLedger
from ugence_governance_contracts.api import AuditReference
from ugence_governed_review import ProposalIdentity, subject_for

from ugence_governed_review_service import (
    LINKAGE_KIND,
    ContractViolation,
    InMemoryLinkageIndex,
    LedgerLinkageIndex,
    LinkageAppender,
    LinkageState,
    StaticRunReader,
)

import _service_fixtures as S

F = S.F
FP = "d" * 64
SIGNAL = "EXTERNAL_SIGNAL:review_decision"


def _disp(seq, disposition, digest):
    return {"seq": seq, "event_type": "", "attempt_token": "a", "body": {
        "seq": seq, "type": "GOVERNANCE_DISPOSITION_RECEIVED",
        "detail": {"task_id": "t1", "disposition": disposition, "execution_state_digest": digest}}}


def _events(approval_id):
    return [
        _disp(1, "ESCALATE", "a" * 64),
        {"seq": 2, "event_type": "", "attempt_token": "a", "body": {"seq": 2, "type": "WORKFLOW_PAUSED", "detail": {}}},
        {"seq": 3, "event_type": SIGNAL, "attempt_token": None,
         "body": {"signal": "review_decision", "payload": {"approval_id": approval_id, "task_id": "t1"}}},
        {"seq": 4, "event_type": "", "attempt_token": "b", "body": {"seq": 4, "type": "WORKFLOW_RESUMED", "detail": {}}},
        _disp(5, "CLEAR", "b" * 64),
    ]


def _journal():
    def snap(d, disposition, status, ref):
        return {"state_digest": d, "task_id": "t1", "proposal_fingerprint": FP,
                "governance_disposition": disposition, "task_status": status,
                "evaluation_reference": ref, "correlation_id": "corr-1"}
    return {"a" * 64: snap("a" * 64, "ESCALATE", "WAITING", "e1"),
            "b" * 64: snap("b" * 64, "CLEAR", "COMPLETED", "e2")}


@pytest.fixture()
def world(tmp_path):
    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    identity = ProposalIdentity(fingerprint=FP, instance_id="i1", task_id="t1")
    now = clock.datetime()
    rec = ledger.request_approval(subject_for(identity, tenant_id=F.TENANT), requested_by=F.REQUESTER,
                                  required_role=F.ROLE, validity=F.window(now, hours=48), as_of=now)
    ledger.present_for_decision(rec.approval_id, as_of=now)
    audit_path = os.path.join(str(tmp_path), "audit.sqlite3")
    audit = AuditLedger(audit_path)
    ckpt = S.parked_checkpoint("i1", "t1", FP)
    ckpt["correlation_id"] = "corr-1"
    reader = StaticRunReader({"i1": ckpt}, {"i1": _events(rec.approval_id)}, {"i1": _journal()})
    adapter = S.RecordingAdapter(known=("i1",))
    appender = LinkageAppender(ledger=audit, index=LedgerLinkageIndex(audit_path, store_ref=STORE_REF),
                               reader=reader, approvals=ledger, tenant_id=F.TENANT,
                               recorded_by="governed-review-service")
    svc = S.service(ledger, clock, adapter=adapter, reader=reader)
    svc._linker = appender  # noqa: SLF001 - the composition seam, wired directly here
    return {"clock": clock, "ledger": ledger, "audit": audit, "audit_path": audit_path,
            "reader": reader, "svc": svc, "approval_id": rec.approval_id, "appender": appender}


def _grant(world):
    return world["svc"].submit_decision(approval_id=world["approval_id"], decision=ReviewDecision.GRANT,
                                        presented_approver=F.APPROVER, justification="ok")


def test_a_grant_before_consumption_is_recorded_and_the_linkage_is_not_yet(world):
    out = _grant(world)
    assert out.result.value == "RECORDED" and out.resume_delivered
    assert out.linkage is not None and out.linkage.state is LinkageState.NOT_YET
    assert "GRANTED; no consumption" in out.linkage.reason
    assert world["audit"].entry_count() == 0, "nothing written before the round trip completes"


def test_after_consumption_the_replay_appends_once_and_a_second_replay_finds_it(world):
    _grant(world)
    world["clock"].advance(minutes=1)
    consumed = world["ledger"].consume(world["approval_id"], consumer_ref="i1:t1", subject_digest=FP,
                                       as_of=world["clock"].datetime())
    assert consumed.result is ConsumptionResult.CONSUMED_FIRST
    world["reader"]._checkpoints["i1"]["status"] = "COMPLETED"  # noqa: SLF001

    first = _grant(world)
    assert first.result.value == "REPLAYED" and not first.resume_delivered
    assert first.linkage.state is LinkageState.APPENDED
    ref = first.linkage.audit_reference
    assert isinstance(ref, AuditReference) and ref.store_ref == STORE_REF
    assert ref.entry_ref == f"{F.TENANT}/1" and ref.correlation_id == "corr-1"
    assert ref.recorded_at == world["clock"].datetime(), "recorded_at is the injected clock's instant"
    assert world["audit"].entry_count() == 1 and world["audit"].verify_chain(tenant_id=F.TENANT)

    world["clock"].advance(minutes=7)
    second = _grant(world)
    assert second.linkage.state is LinkageState.ALREADY_APPENDED
    assert second.linkage.audit_reference == ref, "the same entry, not a second one"
    assert second.linkage.linkage.digest() == first.linkage.linkage.digest()
    assert world["audit"].entry_count() == 1, "a replayed decision never writes twice"

    # The read-only index found it by digest from the ledger's own rows.
    index = LedgerLinkageIndex(world["audit_path"], store_ref=STORE_REF)
    assert index.reference_for(tenant_id=F.TENANT, linkage_digest=first.linkage.linkage.digest()) == ref
    assert index.reference_for(tenant_id=F.TENANT, linkage_digest="0" * 64) is None
    assert index.reference_for(tenant_id="tenant-b", linkage_digest=first.linkage.linkage.digest()) is None


def test_run_detail_exposes_the_linkage_and_the_reference_without_writing_twice(world):
    _grant(world)
    world["ledger"].consume(world["approval_id"], consumer_ref="i1:t1", subject_digest=FP,
                            as_of=world["clock"].datetime())
    run = world["svc"].read_run("i1")
    (link,) = run["linkages"]
    assert link["state"] == "APPENDED" and link["appended"] is True
    assert link["linkage"]["approval_id"] == world["approval_id"] and link["linkage_digest"]
    assert link["audit_reference"]["store_ref"] == STORE_REF
    again = world["svc"].read_run("i1")
    assert again["linkages"][0]["state"] == "ALREADY_APPENDED"
    assert again["linkages"][0]["audit_reference"] == link["audit_reference"]
    assert world["audit"].entry_count() == 1


def test_run_detail_reports_not_yet_and_unconfigured_honestly(world, tmp_path):
    _grant(world)
    (link,) = world["svc"].read_run("i1")["linkages"]
    assert link["state"] == "NOT_YET" and link["audit_reference"] is None
    bare = S.service(world["ledger"], world["clock"], adapter=S.RecordingAdapter(known=("i1",)),
                     reader=world["reader"])
    (link,) = bare.read_run("i1")["linkages"]
    assert link["state"] == "LEDGER_UNCONFIGURED" and "no control-plane audit ledger" in link["reason"]
    out = bare.submit_decision(approval_id=world["approval_id"], decision=ReviewDecision.GRANT,
                               presented_approver=F.APPROVER)
    assert out.recorded and out.linkage.state is LinkageState.LEDGER_UNCONFIGURED


def test_a_reject_never_links(world):
    out = world["svc"].submit_decision(approval_id=world["approval_id"], decision=ReviewDecision.REJECT,
                                       presented_approver=F.APPROVER)
    assert out.result.value == "RECORDED" and out.linkage is None
    assert world["audit"].entry_count() == 0


def test_the_ledger_entry_is_the_linkage_payload_plus_its_digest(world):
    import json
    import sqlite3

    _grant(world)
    world["ledger"].consume(world["approval_id"], consumer_ref="i1:t1", subject_digest=FP,
                            as_of=world["clock"].datetime())
    out = _grant(world)
    conn = sqlite3.connect(f"file:{world['audit_path']}?mode=ro", uri=True)
    kind, recorded_by, payload = conn.execute(
        "SELECT kind, recorded_by, payload_json FROM ledger_entries").fetchone()
    conn.close()
    assert kind == LINKAGE_KIND and recorded_by == "governed-review-service"
    body = json.loads(payload)
    assert body.pop("linkage_digest") == out.linkage.linkage.digest()
    assert body == out.linkage.linkage.to_dict()


def test_the_index_refuses_an_in_memory_ledger_and_a_foreign_schema(tmp_path):
    with pytest.raises(ContractViolation):
        LedgerLinkageIndex(":memory:", store_ref=STORE_REF)
    import sqlite3

    path = os.path.join(str(tmp_path), "other.sqlite3")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO meta VALUES ('schema_version', 'somebody.else/9.0.0')")
    conn.commit(); conn.close()
    with pytest.raises(ContractViolation, match="schema"):
        LedgerLinkageIndex(path, store_ref=STORE_REF).reference_for(tenant_id=F.TENANT, linkage_digest="0" * 64)


def test_the_in_memory_index_is_a_reference_implementation_of_the_same_port(world):
    index = InMemoryLinkageIndex()
    appender = LinkageAppender(ledger=world["audit"], index=index, reader=world["reader"],
                               approvals=world["ledger"], tenant_id=F.TENANT, recorded_by="svc")
    _grant(world)
    world["ledger"].consume(world["approval_id"], consumer_ref="i1:t1", subject_digest=FP,
                            as_of=world["clock"].datetime())
    now = world["clock"].datetime() + timedelta(minutes=1)
    first = appender.link(instance_id="i1", task_id="t1", approval_id=world["approval_id"], recorded_at=now)
    second = appender.link(instance_id="i1", task_id="t1", approval_id=world["approval_id"], recorded_at=now)
    assert first.state is LinkageState.APPENDED and second.state is LinkageState.ALREADY_APPENDED
    assert world["audit"].entry_count() == 1
