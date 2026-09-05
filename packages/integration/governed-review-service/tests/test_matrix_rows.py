"""Failure-matrix rows 7, 8 and 9 of the human-review ADR (§4) as the review service
owns them, run against the real DBOS adapter on a real PostgreSQL, with the real
SQLite approval ledger and the real approval-bound input source inside the hook.

Row 7 and the service's half of row 8 kill a real process: a subprocess opens the same
ledger file, runs the same service, and is SIGKILLed at a named fault point. The parent
then asserts on what the ledger and PostgreSQL actually kept.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, List

import pytest
import sqlalchemy as sa

import _hooks
from _dbos_harness import DEFINITION_DIGEST, WORKFLOW_ID, RecordingProvider, wire
from _hooks import EVAL_LOG_DDL
from conftest import requires_postgres

from ugence_agent_runtime_governance import GovernedExecutionHook
from ugence_approval_workflow import ApprovalState, ReviewDecision

from ugence_control_plane_root import STORE_REF, AuditLedger
from ugence_governed_review_service import (
    SIGNAL_NAME,
    DbosRunReader,
    DecisionResult,
    LedgerLinkageIndex,
    LinkageAppender,
    LinkageState,
    ReviewService,
)

import _fixtures as F

pytestmark = [pytest.mark.matrix]


class RecordingHook:
    """The real GovernedExecutionHook over the approval-bound source, every evaluation
    recorded durably so a row can read dispositions and fingerprints back."""

    def __init__(self, url: str, source: Any) -> None:
        self._engine = sa.create_engine(url)
        self._hook = GovernedExecutionHook(source=source)
        with self._engine.begin() as c:
            c.execute(sa.text(EVAL_LOG_DDL))

    def evaluate(self, proposal, evaluation_time):
        result = self._hook.evaluate(proposal, evaluation_time)
        with self._engine.begin() as c:
            c.execute(
                sa.text("INSERT INTO governance_evaluations "
                        "(instance_id, task_id, fingerprint, disposition, process_tag) "
                        "VALUES (:i, :t, :f, :d, :p)"),
                {"i": proposal.instance_id, "t": proposal.task_id, "f": proposal.fingerprint,
                 "d": result.disposition.value, "p": "review-service"},
            )
        return result

    def envelope_for(self, proposal):
        return self._hook.envelope_for(proposal)

    def consume_envelope(self, proposal):
        return self._hook.consume_envelope(proposal)


def _dispositions(app: str, instance_id: str) -> List[str]:
    return [d for (_f, d, _p) in _hooks.evaluations(app, instance_id)]


def _signal_rows(app: str, instance_id: str) -> int:
    with sa.create_engine(app).begin() as c:
        return int(c.execute(sa.text(
            "SELECT count(*) FROM ugence_art.runtime_events WHERE instance_id=:i "
            "AND event_type=:t"), {"i": instance_id, "t": f"EXTERNAL_SIGNAL:{SIGNAL_NAME}"}
        ).scalar_one())


def _resumed_rows(app: str, instance_id: str) -> int:
    with sa.create_engine(app).begin() as c:
        return int(c.execute(sa.text(
            "SELECT count(*) FROM ugence_art.runtime_events WHERE instance_id=:i "
            "AND body->>'type' = 'WORKFLOW_RESUMED'"), {"i": instance_id}).scalar_one())


@pytest.fixture()
def review(pg_databases, tmp_path):
    """A launched DBOS + adapter whose hook binds approvals from a SQLite ledger, and a
    review service over that same ledger and adapter."""
    from dbos import DBOS

    app, sysdb = pg_databases
    clock = F.Clock()
    ledger = F.sqlite_ledger(tmp_path)
    state: dict = {"clock": clock, "ledger": ledger, "app": app, "sysdb": sysdb,
                   "ledger_path": os.path.join(str(tmp_path), "approvals.sqlite3")}

    src = F.source(ledger, clock)
    hook = RecordingHook(app, src)
    ds, dbos, adapter, bundle = wire(app_url=app, sys_url=sysdb, provider=RecordingProvider(app),
                                     hook=hook, clock=clock.epoch)
    reader = DbosRunReader(datasource=ds, bundle=bundle)
    audit_path = os.path.join(str(tmp_path), "audit.sqlite3")
    audit = AuditLedger(audit_path)
    appender = LinkageAppender(ledger=audit, index=LedgerLinkageIndex(audit_path, store_ref=STORE_REF),
                               reader=reader, approvals=ledger, tenant_id=F.TENANT,
                               recorded_by="governed-review-service")
    svc = ReviewService(ledger=ledger, adapter=adapter, reader=reader,
                        tenant_id=F.TENANT, clock=clock.datetime, linkage_appender=appender)
    state.update(adapter=adapter, source=src, service=svc, ds=ds, bundle=bundle, audit=audit)
    try:
        yield state
    finally:
        try:
            DBOS.destroy()
        except Exception:
            pass


def _park(review, instance_id: str) -> str:
    adapter = review["adapter"]
    adapter.start(workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
                  instance_id=instance_id, correlation_id=f"c-{instance_id}", inputs={})
    outcome = adapter.advance(instance_id=instance_id, attempt_token="a1")
    assert outcome.awaiting_external and not outcome.terminal
    assert _dispositions(review["app"], instance_id) == ["ESCALATE"]
    assert _hooks.provider_calls(review["app"]) == []
    (entry,) = [e for e in review["service"].list_queue() if e.instance_id == instance_id]
    assert entry.governance_disposition == "ESCALATE" and entry.workflow_status == "PAUSED"
    assert entry.instance_known and entry.task_id == "t1"
    return entry.approval_id


# --------------------------------------------------------------------------- #
# the happy path the rows are measured against
# --------------------------------------------------------------------------- #
@requires_postgres
def test_a_recorded_grant_re_arms_and_the_next_quantum_consumes_and_runs_once(review):
    aid = _park(review, "ok")
    review["clock"].advance(minutes=5)
    out = review["service"].submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                                            presented_approver=F.APPROVER, justification="ok")
    assert out.result is DecisionResult.RECORDED and out.signal_delivered and out.resume_delivered
    assert _hooks.provider_calls(review["app"]) == [], "recording and re-arming run nothing"
    assert _signal_rows(review["app"], "ok") == 1 and _resumed_rows(review["app"], "ok") == 1
    assert review["service"].read_run("ok")["instance"]["status"] == "RUNNING"
    assert review["service"].list_queue() == ()

    outcome = review["adapter"].advance(instance_id="ok", attempt_token="a2")
    assert outcome.progressed and not outcome.awaiting_external
    assert _hooks.provider_calls(review["app"]) == ["ok:t1"], "one invocation, after the decision"
    assert _dispositions(review["app"], "ok") == ["ESCALATE", "CLEAR"]
    assert review["ledger"].get_approval(aid).state is ApprovalState.CONSUMED
    assert review["ledger"].get_approval(aid).consumer_ref == "ok:t1"
    events = review["service"].read_run_events("ok")
    assert [e["event_type"] for e in events if e["event_type"].startswith("EXTERNAL")] == \
        [f"EXTERNAL_SIGNAL:{SIGNAL_NAME}"]
    # HE-1 / HE-5: at decision time the linkage was NOT_YET; after the consuming quantum the
    # run-detail read appends it once and exposes the reference.
    assert out.linkage is not None and out.linkage.state is LinkageState.NOT_YET
    assert review["audit"].entry_count() == 0
    (link,) = review["service"].read_run("ok")["linkages"]
    assert link["state"] == "APPENDED" and link["audit_reference"]["store_ref"] == STORE_REF
    assert link["linkage"]["proposal_fingerprint"] == review["ledger"].get_approval(aid).subject_digest
    assert review["service"].read_run("ok")["linkages"][0]["state"] == "ALREADY_APPENDED"
    assert review["audit"].entry_count() == 1 and review["audit"].verify_chain(tenant_id=F.TENANT)


@requires_postgres
def test_a_recorded_reject_leaves_the_instance_parked_and_nothing_runs(review):
    aid = _park(review, "no")
    out = review["service"].submit_decision(approval_id=aid, decision=ReviewDecision.REJECT,
                                            presented_approver=F.APPROVER)
    assert out.result is DecisionResult.RECORDED and out.signal_delivered
    assert not out.resume_delivered
    assert review["service"].read_run("no")["instance"]["status"] == "PAUSED"
    outcome = review["adapter"].advance(instance_id="no", attempt_token="a2")
    assert not outcome.progressed and outcome.awaiting_external
    assert _hooks.provider_calls(review["app"]) == []
    assert review["ledger"].get_approval(aid).state is ApprovalState.REJECTED


# --------------------------------------------------------------------------- #
# Rows 7 and 8 — a killed process
# --------------------------------------------------------------------------- #
_DECIDE_AND_DIE = r"""
import os, sys
sys.path[:0] = {paths!r}
from datetime import datetime
from ugence_approval_workflow import ReviewDecision, SqliteApprovalWorkflowStore, StaticApproverEligibility
from ugence_governed_review_service import ReviewService, StaticRunReader
import _fixtures as F

ledger = SqliteApprovalWorkflowStore({ledger_path!r}, StaticApproverEligibility((F.APPROVER,)))
now = datetime.fromisoformat({now!r})

class Dead:
    def signal(self, **kw): raise AssertionError("never reached")
    def resume(self, **kw): raise AssertionError("never reached")
    def status(self, **kw): return {{"known": False}}

def die(point):
    if point == {fault!r}:
        sys.stdout.write("DYING " + point + "\n"); sys.stdout.flush()
        os.kill(os.getpid(), 9)

svc = ReviewService(ledger=ledger, adapter=Dead(), reader=StaticRunReader(), tenant_id=F.TENANT,
                    clock=lambda: now, fault_injector=die)
svc.submit_decision(approval_id={approval_id!r}, decision=ReviewDecision.GRANT,
                    presented_approver=F.APPROVER, justification="from child")
print("SURVIVED")
"""


def _run_child(review, aid: str, fault: str) -> subprocess.CompletedProcess:
    script = _DECIDE_AND_DIE.format(
        paths=[p for p in sys.path if p], ledger_path=review["ledger_path"],
        now=review["clock"].datetime().isoformat(), fault=fault, approval_id=aid,
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode == -9, proc.stderr
    assert proc.stdout.startswith(f"DYING {fault}"), proc.stdout
    return proc


@requires_postgres
def test_row_07_a_crash_before_decision_persistence_records_nothing(review):
    aid = _park(review, "r7")
    _run_child(review, aid, "before_persist")
    record = review["ledger"].get_approval(aid)
    assert record.state is ApprovalState.PENDING and record.decided_by == ""
    events = [e.event_type for e in review["ledger"].approval_events(aid)]
    assert events == [ApprovalState.REQUESTED, ApprovalState.PENDING], "no decision event"
    assert [e.approval_id for e in review["service"].list_queue()] == [aid], "queue unchanged"
    assert _signal_rows(review["app"], "r7") == 0 and _resumed_rows(review["app"], "r7") == 0
    assert review["service"].read_run("r7")["instance"]["status"] == "PAUSED"
    assert _hooks.provider_calls(review["app"]) == []


@requires_postgres
def test_row_08_a_crash_after_decision_persistence_is_replayed_and_resumes_exactly_once(review):
    aid = _park(review, "r8")
    _run_child(review, aid, "after_persist")
    record = review["ledger"].get_approval(aid)
    assert record.state is ApprovalState.GRANTED and record.decided_by == F.APPROVER.approver_id
    assert _signal_rows(review["app"], "r8") == 0, "the child died before delivering anything"
    assert review["service"].read_run("r8")["instance"]["status"] == "PAUSED"

    # The relay retries the identical submission: replayed, then delivered.
    out = review["service"].submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                                            presented_approver=F.APPROVER, justification="retry")
    assert out.result is DecisionResult.REPLAYED and out.signal_delivered and out.resume_delivered
    assert record.decided_at == review["ledger"].get_approval(aid).decided_at, "not re-decided"
    assert _signal_rows(review["app"], "r8") == 1 and _resumed_rows(review["app"], "r8") == 1

    outcome = review["adapter"].advance(instance_id="r8", attempt_token="a2")
    assert outcome.progressed
    assert _hooks.provider_calls(review["app"]) == ["r8:t1"], "exactly one run"
    events = [e.event_type for e in review["ledger"].approval_events(aid)]
    assert events.count(ApprovalState.GRANTED) == 1 and events.count(ApprovalState.CONSUMED) == 1
    # With the ledger in the loop: the retry that followed the crash appended nothing (NOT_YET),
    # a replay after the consuming quantum appends the linkage exactly once.
    assert out.linkage.state is LinkageState.NOT_YET and review["audit"].entry_count() == 0
    later = review["service"].submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                                              presented_approver=F.APPROVER, justification="retry-2")
    assert later.result is DecisionResult.REPLAYED and later.linkage.state is LinkageState.APPENDED
    assert later.linkage.linkage.consumption_id and later.linkage.linkage.signal_event_seq is not None
    assert review["audit"].entry_count() == 1 and review["audit"].verify_chain(tenant_id=F.TENANT)


# --------------------------------------------------------------------------- #
# Row 9 — duplicate resume signals
# --------------------------------------------------------------------------- #
@requires_postgres
def test_row_09_two_submissions_for_one_decision_record_two_signals_and_resume_once(review):
    aid = _park(review, "r9")
    first = review["service"].submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                                              presented_approver=F.APPROVER)
    second = review["service"].submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                                               presented_approver=F.APPROVER)
    assert first.result is DecisionResult.RECORDED and first.resume_delivered
    assert second.result is DecisionResult.REPLAYED and second.signal_delivered
    assert not second.resume_delivered and "RUNNING" in second.resume_skipped_reason
    assert _signal_rows(review["app"], "r9") == 2, "duplicates are recorded, never suppressed"
    assert _resumed_rows(review["app"], "r9") == 1, "one resume"
    assert _hooks.provider_calls(review["app"]) == []

    outcome = review["adapter"].advance(instance_id="r9", attempt_token="a2")
    assert outcome.progressed
    assert _dispositions(review["app"], "r9") == ["ESCALATE", "CLEAR"], "one resumed evaluation"
    assert _hooks.provider_calls(review["app"]) == ["r9:t1"], "one invocation"
    # A third submission after consumption is still a replay of the same decision.
    third = review["service"].submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                                              presented_approver=F.APPROVER)
    assert third.result is DecisionResult.REPLAYED and not third.resume_delivered
    assert _hooks.provider_calls(review["app"]) == ["r9:t1"]
    # With the ledger in the loop: two signals, one resume, one linkage. The first two
    # submissions were NOT_YET; the third appends; a fourth finds the same entry.
    assert first.linkage.state is LinkageState.NOT_YET and second.linkage.state is LinkageState.NOT_YET
    assert third.linkage.state is LinkageState.APPENDED
    assert third.linkage.linkage.signal_event_seq is not None, "the first decision signal is the one linked"
    fourth = review["service"].submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                                               presented_approver=F.APPROVER)
    assert fourth.linkage.state is LinkageState.ALREADY_APPENDED
    assert fourth.linkage.audit_reference == third.linkage.audit_reference
    assert review["audit"].entry_count() == 1, "duplicates are recorded as signals, never as linkages"
    assert _signal_rows(review["app"], "r9") == 4, "every replay re-delivers the signal; none re-links"


@requires_postgres
def test_row_05_in_the_real_composition_an_ineligible_approver_changes_nothing(review):
    aid = _park(review, "r5")
    out = review["service"].submit_decision(approval_id=aid, decision=ReviewDecision.GRANT,
                                            presented_approver=F.OTHER_ROLE_APPROVER)
    assert out.result is DecisionResult.REFUSED_INELIGIBLE
    assert _signal_rows(review["app"], "r5") == 0
    assert review["service"].read_run("r5")["instance"]["status"] == "PAUSED"
    outcome = review["adapter"].advance(instance_id="r5", attempt_token="a2")
    assert not outcome.progressed and _hooks.provider_calls(review["app"]) == []
    assert [e.approval_id for e in review["service"].list_queue()] == [aid]
