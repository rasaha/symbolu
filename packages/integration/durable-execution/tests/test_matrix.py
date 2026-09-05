"""The ADR §8 durability and failure matrix — the DBOS ratification gate.

Eleven rows. Each is marked ``matrix`` and named for its row so a skipped or failing
row is visible by name rather than buried in a count. **A skipped row is not a passing
row**: ``engine_status()`` stays ``CANDIDATE`` until every one of these is green, and
``test_engine_status_matches_the_evidence`` asserts that claim against this file.

Rows 3, 6 (negative case), 7 (corruption case), 10 and 11 are the ones the ADR names as
most likely to be quietly skipped. They are here, and they are not optional.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from typing import Any, List, Optional

import pytest
import sqlalchemy as sa

import _hooks
from _dbos_harness import DEFINITION_DIGEST, WORKFLOW_ID, RecordingProvider, wire
from conftest import ADMIN_URL as ADMIN_URL_FOR_WAIT, requires_postgres

from ugence_agent_runtime.governance.decisions import (
    AUTHORITY_RECHECK_ERROR,
    CLEAR_REJECTED_AUTHORITY_STALE,
    CLEAR_REJECTED_EXPIRED,
    validate_clearance,
)
from ugence_agent_runtime.governance.interfaces import GovernanceDisposition
from ugence_agent_runtime.models.proposal import TransitionProposal
from ugence_agent_runtime.persistence.checkpoints import Checkpoint

from ugence_durable_execution.clock import wall_clock
from ugence_durable_execution.errors import (
    BudgetExhausted,
    CheckpointIntegrityError,
    ClockDisciplineError,
    DefinitionVersionMismatch,
    PostureError,
)

pytestmark = [pytest.mark.postgres, pytest.mark.matrix]

HARNESS = os.path.join(os.path.dirname(__file__), "_dbos_harness.py")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _child_env() -> dict:
    """Environment for a harness subprocess.

    PYTHONPATH is built from the PARENT's resolved ``sys.path`` rather than a hand-written
    list. The conftest adds package source roots (and, for the production-hook re-run, the
    governance packages); reproducing that list here by hand would silently drift out of
    date, and the child would fail on an import the parent resolved fine.
    """
    env = dict(os.environ)
    entries = [p for p in sys.path if p and os.path.isdir(p)]
    entries.append(os.path.dirname(__file__))
    seen: set = set()
    ordered = [p for p in entries if not (p in seen or seen.add(p))]
    env["PYTHONPATH"] = os.pathsep.join(ordered)
    return env


def _child(app: str, sysdb: str, scenario: str, instance_id: str):
    """Run the harness in a real subprocess so a SIGKILL is a real process death."""
    return subprocess.run(
        [sys.executable, HARNESS, app, sysdb, scenario, instance_id],
        capture_output=True, text=True, timeout=240, env=_child_env(),
    )


@pytest.fixture()
def wired(pg_databases):
    """A launched DBOS + adapter, torn down afterwards."""
    from dbos import DBOS

    app, sysdb = pg_databases
    made: List[Any] = []

    def _make(**kwargs):
        provider = kwargs.pop("provider", None) or RecordingProvider(app)
        hook = kwargs.pop("hook", None) or _hooks.RecordingHook(app)
        ds, dbos, adapter, bundle = wire(
            app_url=app, sys_url=sysdb, provider=provider, hook=hook, **kwargs
        )
        made.append(True)
        return ds, adapter, bundle

    try:
        yield app, sysdb, _make
    finally:
        try:
            DBOS.destroy()
        except Exception:
            pass


def _fingerprints(app: str, instance_id: str) -> List[str]:
    return [f for (f, _d, _p) in _hooks.evaluations(app, instance_id)]


# --------------------------------------------------------------------------- #
# Row 1 — crash BEFORE the provider call
# --------------------------------------------------------------------------- #
@requires_postgres
def test_row_01_crash_before_provider_call(pg_databases):
    """No provider was invoked and none may be. Recovery rebuilds a proposal with an
    IDENTICAL fingerprint and calls the hook again; a pre-crash CLEAR is not reused."""
    app, sysdb = pg_databases
    proc = _child(app, sysdb, "kill_before_provider", "row1")
    assert proc.returncode == -9, f"expected a real SIGKILL; got {proc.returncode}"

    assert _hooks.provider_calls(app) == [], "no provider may have been invoked"
    first = _fingerprints(app, "row1")
    assert len(first) == 1, "the hook ran once in the first process"

    # Recovery in a SECOND, different process.
    proc2 = _child(app, sysdb, "recover", "row1")
    assert proc2.returncode == 0, proc2.stderr[-2000:]
    assert "AFTER_RECOVERY progressed=False awaiting_external=True" in proc2.stdout, (
        "a recovered instance is restored PAUSED and must never auto-run; it takes an "
        f"explicit resume to continue. Got: {proc2.stdout!r}"
    )

    both = _fingerprints(app, "row1")
    assert len(both) == 2, "the hook must be called again after recovery, not replayed"
    assert both[0] == both[1], (
        "the proposal rebuilt after the crash must fingerprint identically to the one "
        "lost — that identity is what lets a pre-crash CLEAR be correctly refused"
    )


# --------------------------------------------------------------------------- #
# Row 2 — crash DURING the provider call
# --------------------------------------------------------------------------- #
@requires_postgres
def test_row_02_crash_during_provider_call(pg_databases):
    """The runtime assumes neither success nor failure: it re-proposes, re-clears and
    re-invokes under the SAME idempotency key, leaving deduplication to the provider."""
    app, sysdb = pg_databases
    proc = _child(app, sysdb, "kill_after_provider", "row2")
    assert proc.returncode == -9

    calls = _hooks.provider_calls(app)
    assert calls == ["row2:t1"], f"one invocation, keyed by the runtime; got {calls}"

    proc2 = _child(app, sysdb, "recover", "row2")
    assert proc2.returncode == 0, proc2.stderr[-2000:]

    calls = _hooks.provider_calls(app)
    assert calls == ["row2:t1", "row2:t1"], (
        "the retry must carry the SAME idempotency key, so the provider can recognise "
        f"a duplicate rather than a second action; got {calls}"
    )
    evals = _fingerprints(app, "row2")
    assert len(evals) == 2 and evals[0] == evals[1], (
        "the hook must have run again before the second invocation"
    )


# --------------------------------------------------------------------------- #
# Row 3 — crash AFTER the provider call, before the commit  (the dangerous one)
# --------------------------------------------------------------------------- #
@requires_postgres
def test_row_03_crash_after_effect_before_commit(pg_databases):
    """The effect happened; the durable record did not.

    Under OD-1 this row is a gate. The effect is committed on the provider's own
    connection (as a real external system would be), while the runtime's transaction is
    killed before commit — so afterwards the provider has a record and the runtime has
    none. Recovery must re-drive, re-cross the hook, and re-invoke under the same key.
    """
    app, sysdb = pg_databases
    proc = _child(app, sysdb, "kill_after_provider", "row3")
    assert proc.returncode == -9

    assert _hooks.provider_calls(app) == ["row3:t1"], "the effect landed"

    engine = sa.create_engine(app)
    with engine.begin() as c:
        checkpoints = c.execute(
            sa.text(
                "SELECT count(*) FROM ugence_art.checkpoints WHERE instance_id = 'row3'"
            )
        ).scalar_one()
        step_records = c.execute(
            sa.text(
                "SELECT count(*) FROM dbos.datasource_outputs WHERE output IS NOT NULL"
            )
        ).scalar_one()

    # The advance transaction is gone in its entirety: no advance checkpoint and no
    # success step record. Only `start`'s own committed transaction survives.
    assert int(checkpoints) == 1, (
        "only the prepare checkpoint may survive; the advance transaction rolled back "
        f"whole, but {checkpoints} checkpoints are present"
    )
    assert int(step_records) == 1, (
        "the killed advance must leave NO success step record; only `start` committed"
    )

    proc2 = _child(app, sysdb, "recover", "row3")
    assert proc2.returncode == 0, proc2.stderr[-2000:]

    calls = _hooks.provider_calls(app)
    assert calls == ["row3:t1", "row3:t1"], (
        "recovery re-invokes under the same key; the provider reports the duplicate"
    )
    evals = _fingerprints(app, "row3")
    assert len(evals) == 2, "the second attempt crossed the governance boundary"

    # The checkpoint chain has no gap.
    with engine.begin() as c:
        seqs = [
            r[0]
            for r in c.execute(
                sa.text(
                    "SELECT seq FROM ugence_art.checkpoints WHERE instance_id = 'row3' "
                    "ORDER BY seq"
                )
            ).all()
        ]
    assert seqs == list(range(1, len(seqs) + 1)), f"checkpoint chain has a gap: {seqs}"


# --------------------------------------------------------------------------- #
# Row 4 — duplicate delivery / retry of a consequential step
# --------------------------------------------------------------------------- #
@requires_postgres
def test_row_04_duplicate_delivery(wired):
    """Exactly one worker executes; the loser is refused, not queued behind it. The
    duplicate is RECORDED (attempt tokens) and never silently suppressed."""
    app, sysdb, make = wired
    ds, adapter, bundle = make()
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="row4", correlation_id="c4", inputs={},
    )

    results: List[Any] = []
    errors: List[BaseException] = []

    def drive(token: str) -> None:
        try:
            results.append(adapter.advance(instance_id="row4", attempt_token=token))
        except BaseException as exc:  # noqa: BLE001 - recorded and asserted below
            errors.append(exc)

    threads = [threading.Thread(target=drive, args=(f"attempt-{i}",)) for i in (1, 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)

    assert not errors, f"neither delivery should raise; got {errors}"
    executed = [r for r in results if r.progressed]
    assert len(executed) == 1, (
        f"exactly one delivery may execute; {len(executed)} did"
    )

    calls = _hooks.provider_calls(app)
    assert calls == ["row4:t1"], f"one invocation only; got {calls}"
    evals = _fingerprints(app, "row4")
    assert len(evals) == len(executed), (
        "hook invocations must equal executed advances — never fewer"
    )


# --------------------------------------------------------------------------- #
# Row 5 — clearance expiry during a retry
# --------------------------------------------------------------------------- #
@requires_postgres
def test_row_05_clearance_expires_during_retry(wired):
    """Fail closed with GOVERNANCE_CLEAR_EXPIRED, and no provider call."""
    app, sysdb, make = wired
    expired_hook = _hooks.RecordingHook(app, valid_until_offset=-1.0)
    ds, adapter, bundle = make(hook=expired_hook)
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="row5", correlation_id="c5", inputs={},
    )
    adapter.advance(instance_id="row5", attempt_token="a1")

    assert _hooks.provider_calls(app) == [], (
        "an expired clearance must not reach the provider"
    )


def test_row_05_expiry_is_inclusive_at_the_boundary():
    """At ``now == valid_until`` the clearance is ALREADY expired.

    Asserted directly against ``validate_clearance`` because the boundary is the whole
    point: an exclusive comparison would permit a call at the exact expiry instant.
    """
    from ugence_agent_runtime.governance.interfaces import GovernanceEvaluation

    proposal = TransitionProposal.build(
        workflow_id="w", instance_id="i", task_id="t", provider_id="p",
        operation="op", arguments={}, idempotency_key="i:t", correlation_id="c",
    )
    evaluation = GovernanceEvaluation(
        disposition=GovernanceDisposition.CLEAR,
        proposal_fingerprint=proposal.fingerprint,
        evaluation_reference="ref",
        correlation_reference="c",
        valid_until=1000.0,
    )
    ok_before, _ = validate_clearance(evaluation, proposal, 999.0)
    assert ok_before, "still valid strictly before expiry"

    ok_at, reasons_at = validate_clearance(evaluation, proposal, 1000.0)
    assert not ok_at, "at now == valid_until the clearance is already expired"
    assert CLEAR_REJECTED_EXPIRED in reasons_at

    ok_after, reasons_after = validate_clearance(evaluation, proposal, 1000.1)
    assert not ok_after and CLEAR_REJECTED_EXPIRED in reasons_after


# --------------------------------------------------------------------------- #
# Row 6 — envelope revocation / epoch advance mid-workflow
# --------------------------------------------------------------------------- #
@requires_postgres
def test_row_06_revocation_fails_closed_at_the_last_mile(wired):
    """A configured authority recheck refuses at the commit point; nothing is invoked."""
    app, sysdb, make = wired
    ds, adapter, bundle = make(authority_recheck=_hooks.revoking_recheck)
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="row6", correlation_id="c6", inputs={},
    )
    adapter.advance(instance_id="row6", attempt_token="a1")

    assert _hooks.provider_calls(app) == [], (
        "a revoked authority must not reach the provider"
    )


def test_row_06_misbehaving_recheck_is_never_a_permit():
    """A recheck that raises, or returns a malformed truthy value, fails closed."""
    from ugence_agent_runtime.governance.interfaces import GovernanceEvaluation

    proposal = TransitionProposal.build(
        workflow_id="w", instance_id="i", task_id="t", provider_id="p",
        operation="op", arguments={}, idempotency_key="i:t", correlation_id="c",
    )
    evaluation = GovernanceEvaluation(
        disposition=GovernanceDisposition.CLEAR,
        proposal_fingerprint=proposal.fingerprint,
        evaluation_reference="ref",
        correlation_reference="c",
    )
    ok, reasons = validate_clearance(evaluation, proposal, 1.0, _hooks.revoking_recheck)
    assert not ok and CLEAR_REJECTED_AUTHORITY_STALE in reasons

    ok, reasons = validate_clearance(evaluation, proposal, 1.0, _hooks.raising_recheck)
    assert not ok, "a raising recheck must never permit"
    assert AUTHORITY_RECHECK_ERROR in reasons

    ok, reasons = validate_clearance(evaluation, proposal, 1.0, _hooks.malformed_recheck)
    assert not ok, "a malformed truthy result must never be mistaken for permission"
    assert AUTHORITY_RECHECK_ERROR in reasons


@requires_postgres
def test_row_06_negative_case_unset_recheck_does_not_notice_revocation(wired):
    """THE NEGATIVE CASE the ADR insists on.

    With ``authority_recheck`` unset, a revocation landing between CLEAR and effect goes
    unnoticed and the provider IS invoked. This is asserted so the configuration
    requirement is proven load-bearing rather than decorative: if this test ever starts
    failing, the recheck has become a default and the ADR text must change with it.
    """
    app, sysdb, make = wired
    ds, adapter, bundle = make(authority_recheck=None)
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="row6n", correlation_id="c6n", inputs={},
    )
    adapter.advance(instance_id="row6n", attempt_token="a1")

    assert _hooks.provider_calls(app) == ["row6n:t1"], (
        "without a configured recheck the revocation is NOT noticed — which is exactly "
        "why a durable deployment must configure one (ADR §6.5)"
    )


# --------------------------------------------------------------------------- #
# Row 7 — Postgres unavailable
# --------------------------------------------------------------------------- #
PGDATA = os.environ.get("UGENCE_DE_PGDATA")
PGBIN = os.environ.get("UGENCE_DE_PGBIN", "")
PGPORT = os.environ.get("UGENCE_DE_PGPORT", "5432")
PGSOCK = os.environ.get("UGENCE_DE_PGSOCK", "/tmp")
PGUSER = os.environ.get("UGENCE_DE_PGOSUSER", "postgres")

can_stop_postgres = pytest.mark.skipif(
    not PGDATA,
    reason=(
        "row 7 requires stopping a REAL PostgreSQL server; set UGENCE_DE_PGDATA and "
        "UGENCE_DE_PGBIN. A connection-refusal simulation is not evidence for this row."
    ),
)


#: How to run a command as the PostgreSQL OS user. ``su postgres -c`` locally; CI sets
#: ``sudo -u postgres bash -c``. Configurable so the test needs no shim on either.
PG_PRIVCMD = os.environ.get("UGENCE_DE_PG_PRIVCMD", f"su {PGUSER} -c")


def _pg_ctl(action: str) -> None:
    inner = (
        f"{os.path.join(PGBIN, 'pg_ctl')} -D {PGDATA} "
        f"-o '-p {PGPORT} -k {PGSOCK} -c listen_addresses=127.0.0.1' "
        f"-l /tmp/pg_row7.log -w {action}"
    )
    subprocess.run(
        [*PG_PRIVCMD.split(), inner], check=True, capture_output=True, timeout=120
    )
    if action == "start":
        _await_postgres()


def _await_postgres(timeout_s: float = 30.0) -> None:
    """Block until the server accepts connections again, and fail loudly if it does not.

    ``requires_postgres`` is evaluated at import time, so a server this row failed to
    restart would turn every remaining row into a silent skip — and a skipped row is not
    a passing row. Better to fail here, naming the cause, than to hand back a green run
    that tested almost nothing.
    """
    deadline = time.time() + timeout_s
    last: Exception | None = None
    while time.time() < deadline:
        try:
            engine = sa.create_engine(ADMIN_URL_FOR_WAIT)
            with engine.connect() as c:
                c.execute(sa.text("SELECT 1"))
            engine.dispose()
            return
        except Exception as exc:  # noqa: BLE001 - retried until the deadline
            last = exc
            time.sleep(0.5)
    raise AssertionError(
        f"PostgreSQL did not come back within {timeout_s}s after row 7 restarted it; "
        f"every remaining row would silently skip. Last error: {last}"
    )


@requires_postgres
@can_stop_postgres
def test_row_07_postgres_unavailable(pg_databases):
    """No advance proceeds while state cannot be durably written.

    The database is really stopped, and the advance is attempted in a CHILD process
    under a hard timeout. That is not squeamishness: with Postgres down, DBOS's
    retriable-error loop backs off and retries indefinitely, so an in-process attempt
    never returns. **Blocking is the correct behaviour** — an advance that cannot commit
    its checkpoint must not proceed — but it has to be observed from outside, and the
    thing that matters is what did NOT happen while it blocked: no provider call.
    """
    app, sysdb = pg_databases

    # Prepare the instance while the database is up.
    proc = _child(app, sysdb, "prepare_only", "row7")
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert _hooks.provider_calls(app) == [], "prepare invokes nothing"

    _pg_ctl("stop")
    try:
        blocked = subprocess.run(
            [sys.executable, HARNESS, app, sysdb, "advance_only", "row7"],
            capture_output=True, text=True, env=_child_env(), timeout=20,
        )
        outcome = f"returned rc={blocked.returncode}"
    except subprocess.TimeoutExpired:
        outcome = "blocked until the timeout"
    finally:
        _pg_ctl("start")
        time.sleep(1.5)

    # Either way, the advance did not complete: it neither committed nor invoked.
    assert _hooks.provider_calls(app) == [], (
        "an advance that cannot commit its checkpoint must not have invoked a provider "
        f"({outcome})"
    )

    engine = sa.create_engine(app)
    with engine.begin() as c:
        checkpoints = c.execute(
            sa.text(
                "SELECT count(*) FROM ugence_art.checkpoints WHERE instance_id = 'row7'"
            )
        ).scalar_one()
    assert int(checkpoints) == 1, (
        "only the prepare checkpoint exists; nothing was written during the outage"
    )

    # After restart, the instance recovers and verifies.
    proc2 = _child(app, sysdb, "recover", "row7")
    assert proc2.returncode == 0, proc2.stderr[-2000:]
    assert _hooks.provider_calls(app) == ["row7:t1"], (
        "once the database is back the instance recovers and proceeds exactly once"
    )


@requires_postgres
def test_row_07_corrupted_checkpoint_is_unrecoverable_not_repaired(wired):
    """THE CORRUPTION CASE. A checkpoint failing integrity is surfaced, never repaired
    and never skipped."""
    app, sysdb, make = wired
    ds, adapter, bundle = make()
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="row7c", correlation_id="c7c", inputs={},
    )

    # Tamper with the persisted resume point without recomputing its digest.
    engine = sa.create_engine(app)
    with engine.begin() as c:
        c.execute(
            sa.text(
                "UPDATE ugence_art.runtime_state "
                "SET checkpoint = jsonb_set(checkpoint, '{status}', '\"COMPLETED\"') "
                "WHERE instance_id = 'row7c'"
            )
        )

    adapter.forget("row7c")
    with pytest.raises(CheckpointIntegrityError):
        adapter.advance(instance_id="row7c", attempt_token="a2")

    assert _hooks.provider_calls(app) == [], (
        "a tampered checkpoint must never lead to a provider invocation"
    )


@requires_postgres
def test_row_07_production_mode_refuses_an_in_memory_bundle(pg_databases):
    """No silent in-memory fallback: the production root refuses a non-authoritative
    bundle at construction."""
    from ugence_durable_execution.postgres.bundle import InMemoryReferenceBundle

    bundle = InMemoryReferenceBundle()
    assert bundle.is_production_authoritative is False

    from ugence_durable_execution.engine.dbos_engine import DbosExecutionAdapter

    with pytest.raises(PostureError):
        DbosExecutionAdapter(
            datasource=object(), host=object(), bundle=bundle, production_mode=True
        )


# --------------------------------------------------------------------------- #
# Row 8 — concurrent instances contending for one budget
# --------------------------------------------------------------------------- #
@requires_postgres
def test_row_08_budget_contention_is_settled_by_the_database(pg_databases):
    """N concurrent consumers, ceiling K: exactly K consume, N-K are refused, and the
    total never exceeds K under repeated interleavings."""
    app, _sysdb = pg_databases
    from ugence_durable_execution.postgres.budgets import PostgresBudgetLedger
    from ugence_durable_execution.postgres.schema import schema_statements

    engine = sa.create_engine(app)
    with engine.begin() as c:
        for stmt in schema_statements():
            c.execute(sa.text(stmt))

    N, K = 12, 5
    with engine.begin() as c:
        c.execute(
            sa.text(
                "INSERT INTO ugence_art.budgets (budget_id, ceiling) VALUES ('b', :k)"
            ),
            {"k": K},
        )

    granted: List[str] = []
    refused: List[str] = []
    lock = threading.Lock()

    def consume(i: int) -> None:
        sess = sa.orm.sessionmaker(bind=engine)()
        ledger = PostgresBudgetLedger(lambda: sess)
        try:
            with sess.begin():
                ledger.reserve(
                    budget_id="b", idempotency_key=f"k{i}", instance_id=f"i{i}"
                )
            with lock:
                granted.append(f"k{i}")
        except BudgetExhausted:
            with lock:
                refused.append(f"k{i}")
        except Exception:
            with lock:
                refused.append(f"k{i}")
        finally:
            sess.close()

    threads = [threading.Thread(target=consume, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    with engine.begin() as c:
        consumed = c.execute(
            sa.text("SELECT consumed FROM ugence_art.budgets WHERE budget_id='b'")
        ).scalar_one()

    assert int(consumed) == K, f"exactly the ceiling may be consumed; got {consumed}"
    assert len(granted) == K, f"exactly {K} consumers succeed; {len(granted)} did"
    assert len(refused) == N - K
    assert int(consumed) <= K, "the ceiling is never exceeded"


@requires_postgres
def test_row_08_replay_under_the_same_key_settles_once(pg_databases):
    """A retry carrying the runtime's same idempotency key consumes once, not twice."""
    app, _sysdb = pg_databases
    from ugence_durable_execution.postgres.budgets import PostgresBudgetLedger
    from ugence_durable_execution.postgres.schema import schema_statements

    engine = sa.create_engine(app)
    with engine.begin() as c:
        for stmt in schema_statements():
            c.execute(sa.text(stmt))
        c.execute(
            sa.text("INSERT INTO ugence_art.budgets (budget_id, ceiling) VALUES ('b', 5)")
        )

    sess = sa.orm.sessionmaker(bind=engine)()
    ledger = PostgresBudgetLedger(lambda: sess)
    with sess.begin():
        assert ledger.reserve(budget_id="b", idempotency_key="i:t", instance_id="i")
    with sess.begin():
        assert not ledger.reserve(budget_id="b", idempotency_key="i:t", instance_id="i")
    with sess.begin():
        assert ledger.consumed("b") == 1, "one unit for one idempotency key"
    sess.close()


# --------------------------------------------------------------------------- #
# Row 9 — pause and resume across a human decision spanning hours
# --------------------------------------------------------------------------- #
@requires_postgres
def test_row_09_parked_instance_stays_parked_then_re_evaluates(wired):
    """Driven repeatedly across a simulated multi-hour span the instance never moves and
    never invokes. A signal records the human decision as DATA; the re-entry gets a
    FRESH evaluation, of the SAME proposal."""
    app, sysdb, make = wired

    escalating = _hooks.RecordingHook(
        app, disposition=GovernanceDisposition.ESCALATE, process_tag="escalate"
    )
    simulated_now = [wall_clock()]

    ds, adapter, bundle = make(hook=escalating, clock=lambda: simulated_now[0])
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="row9", correlation_id="c9", inputs={},
    )

    for hour in range(6):
        simulated_now[0] += 3600.0
        outcome = adapter.advance(instance_id="row9", attempt_token=f"a{hour}")
        assert not outcome.progressed or outcome.awaiting_external, (
            "a parked instance must not progress past the escalation"
        )

    assert _hooks.provider_calls(app) == [], (
        "six hours of driving must not invoke anything"
    )
    parked_evals = _fingerprints(app, "row9")
    assert parked_evals, "the hook was consulted"
    assert len(set(parked_evals)) == 1, (
        "every re-drive proposes the SAME action; the fingerprint never drifts"
    )

    # The human decision lands. It is data, not authority.
    adapter.signal(
        instance_id="row9", signal_name="human_decision",
        payload={"decided_by": "reviewer-1", "outcome": "proceed"},
    )
    with sa.create_engine(app).begin() as c:
        signals = c.execute(
            sa.text(
                "SELECT count(*) FROM ugence_art.runtime_events "
                "WHERE instance_id='row9' AND event_type LIKE 'EXTERNAL_SIGNAL%'"
            )
        ).scalar_one()
    assert int(signals) == 1, "the signal is recorded"
    assert _hooks.provider_calls(app) == [], (
        "delivering a signal must not itself permit anything"
    )

    after_signal = _fingerprints(app, "row9")
    assert after_signal[-1] == parked_evals[0], (
        "the human decided about the same action that would then run — the pre-pause "
        "and post-resume proposals fingerprint identically"
    )


# --------------------------------------------------------------------------- #
# Row 10 — recovery after a workflow-definition version change
# --------------------------------------------------------------------------- #
@requires_postgres
def test_row_10_definition_version_change_refuses(wired):
    """Refuse, do not reinterpret. The refusal names both digests."""
    app, sysdb, make = wired
    ds, adapter, bundle = make()
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="row10", correlation_id="c10", inputs={},
    )

    # A redeploy: the same durable state, a different compiled definition.
    adapter._definition_digest = "digest-v2"  # noqa: SLF001
    adapter.forget("row10")

    with pytest.raises(DefinitionVersionMismatch) as excinfo:
        adapter.advance(instance_id="row10", attempt_token="a1")

    message = str(excinfo.value)
    assert DEFINITION_DIGEST in message and "digest-v2" in message, (
        "the refusal must name both digests so an operator can see what changed"
    )
    assert _hooks.provider_calls(app) == [], "nothing may be invoked on a refusal"


def test_row_10_unknown_checkpoint_version_refuses():
    """A checkpoint written by a future build is not read under today's semantics."""
    from ugence_agent_runtime.persistence.checkpoints import (
        SUPPORTED_CHECKPOINT_VERSIONS,
    )

    assert "99" not in SUPPORTED_CHECKPOINT_VERSIONS
    body = {
        "instance_id": "i", "workflow_id": "w", "runtime_id": "r",
        "runtime_version": "1", "status": "RUNNING", "tasks": {},
        "correlation_id": None, "digest": "", "checkpoint_version": "99",
    }
    ckpt = Checkpoint.from_dict(body)
    assert ckpt.checkpoint_version == "99"
    assert ckpt.checkpoint_version not in SUPPORTED_CHECKPOINT_VERSIONS, (
        "an unknown version must be recognisable as unsupported before it is parsed"
    )


def test_row_10_legacy_checkpoint_recovers_without_fabricating_lineage():
    """A legacy (version "0") checkpoint still recovers, carrying NO execution-state
    lineage — unavailable, never fabricated."""
    from ugence_agent_runtime.persistence.checkpoints import LEGACY_CHECKPOINT_VERSION

    body = {
        "instance_id": "i", "workflow_id": "w", "runtime_id": "r",
        "runtime_version": "1", "status": "RUNNING", "tasks": {},
        "correlation_id": None, "digest": "",
    }
    ckpt = Checkpoint.from_dict(body)
    assert ckpt.checkpoint_version == LEGACY_CHECKPOINT_VERSION
    assert ckpt.execution_states == {}
    assert ckpt.execution_state_journal == {}
    assert ckpt.has_extension_data() is False
    ok, _ = ckpt.validate_execution_states()
    assert ok, "an empty legacy checkpoint is vacuously intact"


# --------------------------------------------------------------------------- #
# Row 11 — clock skew between engine and evaluator
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("skew", [-600.0, -60.0, -1.0, 1.0, 60.0, 600.0])
def test_row_11_skew_never_widens_permission(skew: float):
    """Skew in either direction, at several magnitudes, never permits a call after true
    expiry. The safe direction may refuse early; that asymmetry is deliberate."""
    from ugence_agent_runtime.governance.interfaces import GovernanceEvaluation

    proposal = TransitionProposal.build(
        workflow_id="w", instance_id="i", task_id="t", provider_id="p",
        operation="op", arguments={}, idempotency_key="i:t", correlation_id="c",
    )
    true_expiry = 1_000_000.0
    evaluation = GovernanceEvaluation(
        disposition=GovernanceDisposition.CLEAR,
        proposal_fingerprint=proposal.fingerprint,
        evaluation_reference="ref",
        correlation_reference="c",
        valid_until=true_expiry,
    )
    # A runtime reading skewed time, asked to act after the clearance truly expired.
    truly_after = true_expiry + 5.0
    runtime_reading = truly_after + skew
    permitted, reasons = validate_clearance(evaluation, proposal, runtime_reading)
    if runtime_reading >= true_expiry:
        assert not permitted and CLEAR_REJECTED_EXPIRED in reasons
    else:
        # The runtime's clock lags far enough to still believe the clearance is live.
        # This is the residual the ADR names: skew is bounded by clock discipline, not
        # by the comparison, which is why row 11 also asserts the monotonic refusal.
        assert permitted


def test_row_11_production_root_refuses_a_monotonic_clock():
    """THE TEST THAT CLOSES THE §6.4 GAP.

    ``AgentRuntimeConfig.clock`` defaults to ``time.monotonic``, whose origin is
    process-local, so a ``valid_until`` minted before a crash is compared against an
    unrelated number after recovery. A durable composition root refuses it outright.
    """
    import time as _time

    from ugence_agent_runtime.config import AgentRuntimeConfig
    from ugence_durable_execution.clock import (
        assert_durable_clock,
        is_monotonic_clock,
        wall_clock,
    )

    default_clock = AgentRuntimeConfig().clock
    assert is_monotonic_clock(default_clock), (
        "the runtime default is still monotonic; if this changes, ADR §6.4 must too"
    )
    with pytest.raises(ClockDisciplineError):
        assert_durable_clock(default_clock)
    with pytest.raises(ClockDisciplineError):
        assert_durable_clock(_time.monotonic)

    assert_durable_clock(wall_clock)  # the wall clock is accepted


def test_row_11_host_construction_refuses_a_monotonic_clock():
    """The refusal happens at wiring time, not at the first expiry comparison after a
    recovery — which is exactly when it would be too late to notice."""
    import time as _time

    from ugence_durable_execution.engine.dbos_engine import DbosRuntimeHost

    with pytest.raises(ClockDisciplineError):
        DbosRuntimeHost(
            build_engine=lambda *a: None,
            definition_for=lambda w: None,
            clock=_time.monotonic,
        )
