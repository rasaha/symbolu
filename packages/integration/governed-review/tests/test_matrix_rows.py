"""Failure-matrix rows 2, 3, 6, 8 and 10 of the human-review ADR (§4), run inside the
real DBOS adapter against a real PostgreSQL, with the real SQLite approval ledger.

Nothing is mocked on the path that matters: the runtime parks the instance, the source
raises the request in the ledger, a human decision is recorded through the ledger's
own transitions, the source consumes it inside the next evaluation, composition and
projection run through the ratified engine, and the provider is a real (fixture) call
recorded on its own connection.
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
from _production import EVAL_LOG_DDL, ENVELOPE_ID  # noqa: F401 - the log DDL is reused
from conftest import requires_postgres

from ugence_agent_runtime.governance.decisions import CLEAR_REJECTED_AUTHORITY_STALE  # noqa: F401
from ugence_agent_runtime_governance import GovernedExecutionHook
from ugence_approval_workflow import ApprovalState, ReviewDecision

from ugence_governed_review import BindingState, ProposalIdentity

import _fixtures as F

pytestmark = [pytest.mark.matrix]


class RecordingHook:
    """The real GovernedExecutionHook over the approval-bound source, with every
    evaluation recorded durably so a row can read dispositions and fingerprints back."""

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
                 "d": result.disposition.value, "p": "review"},
            )
        return result

    def envelope_for(self, proposal):
        return self._hook.envelope_for(proposal)

    def consume_envelope(self, proposal):
        return self._hook.consume_envelope(proposal)


def _dispositions(app: str, instance_id: str) -> List[str]:
    return [d for (_f, d, _p) in _hooks.evaluations(app, instance_id)]


def _fingerprint(app: str, instance_id: str) -> str:
    fps = {f for (f, _d, _p) in _hooks.evaluations(app, instance_id)}
    assert len(fps) == 1, f"the parked proposal must be stable; saw {fps}"
    return fps.pop()


@pytest.fixture()
def review(pg_databases, tmp_path):
    """A launched DBOS + adapter whose hook binds approvals from a SQLite ledger."""
    from dbos import DBOS

    app, sysdb = pg_databases
    clock = F.Clock()
    ledger = F.sqlite_ledger(tmp_path)
    state: dict = {"clock": clock, "ledger": ledger, "app": app, "sysdb": sysdb}

    def _make(*, authority_recheck=None, upstream=None):
        src = F.source(ledger, clock, upstream)
        hook = RecordingHook(app, src)
        ds, dbos, adapter, bundle = wire(
            app_url=app, sys_url=sysdb, provider=RecordingProvider(app), hook=hook,
            clock=clock.epoch, authority_recheck=authority_recheck,
        )
        state.update(adapter=adapter, source=src)
        return adapter, src

    state["make"] = _make
    try:
        yield state
    finally:
        try:
            DBOS.destroy()
        except Exception:
            pass


def _park(review, instance_id: str, *, make_kwargs=None):
    adapter, src = review["make"](**(make_kwargs or {}))
    adapter.start(workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
                  instance_id=instance_id, correlation_id=f"c-{instance_id}", inputs={})
    outcome = adapter.advance(instance_id=instance_id, attempt_token="a1")
    # Parking IS a state change, so the adapter reports it as progress; what matters is
    # that the instance awaits something external and nothing was invoked.
    assert outcome.awaiting_external and not outcome.terminal
    assert _dispositions(review["app"], instance_id) == ["ESCALATE"]
    assert _hooks.provider_calls(review["app"]) == []
    open_ = review["ledger"].list_open(tenant_id=F.TENANT, as_of=review["clock"].datetime())
    ids = [r.approval_id for r in open_ if r.subject_ref == f"{instance_id}:t1"]
    assert len(ids) == 1, "parking raised exactly one request"
    return adapter, src, ids[0]


def _resume_and_advance(adapter, instance_id: str, token: str):
    adapter.resume(instance_id=instance_id)
    return adapter.advance(instance_id=instance_id, attempt_token=token)


# --------------------------------------------------------------------------- #
# the happy path the rows are measured against
# --------------------------------------------------------------------------- #
@requires_postgres
def test_a_granted_approval_resumes_exactly_once(review):
    adapter, src, approval_id = _park(review, "ok")
    review["clock"].advance(minutes=5)
    F.decide(review["ledger"], approval_id, as_of=review["clock"].datetime())

    outcome = _resume_and_advance(adapter, "ok", "a2")
    assert _hooks.provider_calls(review["app"]) == ["ok:t1"], "one invocation, after approval"
    assert _dispositions(review["app"], "ok")[-1] == "CLEAR"
    assert review["ledger"].state_at(approval_id, as_of=review["clock"].datetime()) \
        is ApprovalState.CONSUMED
    assert review["ledger"].get_approval(approval_id).consumer_ref == "ok:t1"


# --------------------------------------------------------------------------- #
# Row 2 — stale approval: the subject changed after the grant
# --------------------------------------------------------------------------- #
@requires_postgres
def test_row_02_a_changed_subject_never_reuses_a_standing_decision(review):
    adapter, src, approval_id = _park(review, "r2")
    fingerprint = _fingerprint(review["app"], "r2")
    F.decide(review["ledger"], approval_id, as_of=review["clock"].datetime())

    # The approval binds to the fingerprint. A proposal that differs in any way names a
    # different approval and finds none; presenting the granted digest from a different
    # identity is refused as a mismatch by the ledger.
    changed = ProposalIdentity(fingerprint[:-1] + ("0" if fingerprint[-1] != "0" else "1"),
                               "r2", "t1")
    assert src.bind(changed).state in (BindingState.REQUESTED, BindingState.PENDING), (
        "a changed subject is a new request, never the standing decision"
    )
    assert review["ledger"].get_approval(approval_id).consumer_ref == "", "unconsumed"
    assert _hooks.provider_calls(review["app"]) == []

    # The genuine proposal still resumes exactly once.
    _resume_and_advance(adapter, "r2", "a2")
    assert _hooks.provider_calls(review["app"]) == ["r2:t1"]


# --------------------------------------------------------------------------- #
# Row 3 — approval expiry
# --------------------------------------------------------------------------- #
@requires_postgres
def test_row_03_an_expired_approval_is_refused_and_the_instance_stays_parked(review):
    adapter, src, approval_id = _park(review, "r3")
    F.decide(review["ledger"], approval_id, as_of=review["clock"].datetime())
    review["clock"].advance(days=8)  # past the request window, same clock for both stores

    outcome = _resume_and_advance(adapter, "r3", "a2")
    assert outcome.awaiting_external and not outcome.terminal
    assert _hooks.provider_calls(review["app"]) == []
    assert _dispositions(review["app"], "r3") == ["ESCALATE", "ESCALATE"]
    assert review["ledger"].get_approval(approval_id).consumer_ref == "", "not consumed"
    assert review["ledger"].state_at(approval_id, as_of=review["clock"].datetime()) \
        is ApprovalState.EXPIRED


# --------------------------------------------------------------------------- #
# Row 6 — correlation mismatch: an approval for one instance cannot resume another
# --------------------------------------------------------------------------- #
@requires_postgres
def test_row_06_an_approval_for_one_instance_does_not_resume_another(review):
    adapter, src, approval_a = _park(review, "r6a")
    adapter.start(workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
                  instance_id="r6b", correlation_id="c-r6b", inputs={})
    adapter.advance(instance_id="r6b", attempt_token="b1")
    open_ = review["ledger"].list_open(tenant_id=F.TENANT, as_of=review["clock"].datetime())
    assert len(open_) == 2, "identical actions on two instances are two requests"
    assert _fingerprint(review["app"], "r6a") != _fingerprint(review["app"], "r6b")

    F.decide(review["ledger"], approval_a, as_of=review["clock"].datetime())
    outcome_b = _resume_and_advance(adapter, "r6b", "b2")
    assert outcome_b.awaiting_external and not outcome_b.terminal
    assert _hooks.provider_calls(review["app"]) == [], "B stays parked"
    assert _dispositions(review["app"], "r6b") == ["ESCALATE", "ESCALATE"]

    _resume_and_advance(adapter, "r6a", "a2")
    assert _hooks.provider_calls(review["app"]) == ["r6a:t1"]
    assert review["ledger"].get_approval(approval_a).consumer_ref == "r6a:t1"


# --------------------------------------------------------------------------- #
# Row 8 — crash after decision persistence, before resume
# --------------------------------------------------------------------------- #
_CONSUME_AND_DIE = """
import os, sys
from datetime import datetime, timezone
sys.path[:0] = {paths!r}
import _fixtures as F
from ugence_governed_review import ProposalIdentity
ledger = F.sqlite_ledger({ledger_dir!r})
clock = F.Clock(datetime.fromisoformat({now!r}))
src = F.source(ledger, clock)
out = src.bind(ProposalIdentity({fingerprint!r}, {instance!r}, "t1"))
assert out.satisfied, out
sys.stdout.write("CONSUMED " + out.holder + "\\n"); sys.stdout.flush()
os.kill(os.getpid(), 9)
"""


@requires_postgres
def test_row_08_crash_after_consumption_before_advance_resumes_exactly_once(review, tmp_path):
    adapter, src, approval_id = _park(review, "r8")
    fingerprint = _fingerprint(review["app"], "r8")
    F.decide(review["ledger"], approval_id, as_of=review["clock"].datetime())

    # A separate process consumes the approval for this instance and task, then dies
    # before anything advances. Only the SQLite ledger has changed.
    script = _CONSUME_AND_DIE.format(
        paths=[p for p in sys.path if p],
        ledger_dir=str(tmp_path), now=review["clock"].datetime().isoformat(),
        fingerprint=fingerprint, instance="r8",
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode == -9, proc.stderr
    assert proc.stdout.startswith("CONSUMED "), proc.stdout
    assert review["ledger"].get_approval(approval_id).consumer_ref == "r8:t1"
    assert _hooks.provider_calls(review["app"]) == [], "nothing ran before the crash"

    # The re-drive: ALREADY_CONSUMED by this instance and task is satisfied; one run.
    # (The adapter's resume drains the workflow inside its own step, so the following
    # advance sees a terminal instance — the bounded-resume change is HR-B, not here.)
    outcome = _resume_and_advance(adapter, "r8", "a2")
    assert outcome.terminal
    assert _hooks.provider_calls(review["app"]) == ["r8:t1"]
    events = [e.event_type for e in review["ledger"].approval_events(approval_id)]
    assert events.count(ApprovalState.CONSUMED) == 1, "consumed exactly once across the crash"


# --------------------------------------------------------------------------- #
# Row 10 — clearance changes before resumed execution
# --------------------------------------------------------------------------- #
@requires_postgres
def test_row_10_a_revocation_after_approval_still_blocks_at_the_last_mile(review):
    adapter, src, approval_id = _park(review, "r10",
                                      make_kwargs={"authority_recheck": _hooks.revoking_recheck})
    F.decide(review["ledger"], approval_id, as_of=review["clock"].datetime())

    outcome = _resume_and_advance(adapter, "r10", "a2")
    assert _dispositions(review["app"], "r10")[-1] == "CLEAR", (
        "composition genuinely cleared once the approval was consumed"
    )
    assert _hooks.provider_calls(review["app"]) == [], (
        "the last-mile recheck refuses a clearance the authority no longer backs"
    )
    assert review["ledger"].state_at(approval_id, as_of=review["clock"].datetime()) \
        is ApprovalState.CONSUMED, "the approval was used; it does not survive the refusal"


# --------------------------------------------------------------------------- #
# HR-5 inside the runtime: a HOLD without labels is never requested
# --------------------------------------------------------------------------- #
@requires_postgres
def test_a_plain_hold_raises_no_request_inside_the_runtime(review):
    from ugence_risk_authority_runtime.contracts import VetoDisposition

    adapter, src = review["make"](upstream=F.UpstreamSource(
        clock=review["clock"], da=VetoDisposition.HOLD, required_approvals=frozenset()))
    adapter.start(workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
                  instance_id="hold", correlation_id="c-hold", inputs={})
    outcome = adapter.advance(instance_id="hold", attempt_token="a1")
    assert outcome.awaiting_external
    assert _dispositions(review["app"], "hold") == ["HOLD"]
    assert review["ledger"].list_open(tenant_id=F.TENANT, as_of=review["clock"].datetime()) == ()
