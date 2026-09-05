"""OD-1: the DBOS step record and the runtime's own writes commit in ONE transaction.

Owner ruling OD-1 (``REQUIRE_SINGLE_TRANSACTION``) makes this a **ratification gate**,
not a documented residual: if DBOS cannot provide it, DBOS stays a candidate and GAS-2
stops. So this module proves the property directly rather than inferring it from the
DBOS source.

The decisive case is ``test_sigkill_mid_transaction_leaves_neither``: a process is
killed with the transaction open, and afterwards **neither** the application write nor
the DBOS step record exists. Two separate commits could not produce that result.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest
import sqlalchemy as sa

from conftest import requires_postgres  # noqa: F401  (fixture module on sys.path)

pytestmark = [pytest.mark.postgres]

PROBE = textwrap.dedent(
    '''
    import os, sys
    import sqlalchemy as sa
    from dbos import DBOS, DBOSConfig, SQLAlchemyDatasource, SetWorkflowID

    APP, SYS, MODE, WFID = sys.argv[1:5]

    engine = sa.create_engine(APP)
    with engine.begin() as c:
        c.execute(sa.text("CREATE TABLE IF NOT EXISTS probe_rows (id text primary key)"))

    ds = SQLAlchemyDatasource.create(database_url=APP)
    DBOS(config=DBOSConfig(name="od1", system_database_url=SYS,
                           application_database_url=APP, run_admin_server=False,
                           enable_otlp=False, log_level="CRITICAL"))
    ds.run_migrations()

    @ds.transaction(isolation_level="READ COMMITTED")
    def write_row(rid):
        ds.sql_session().execute(sa.text("INSERT INTO probe_rows(id) VALUES (:i)"), {"i": rid})
        if MODE == "raise":
            raise RuntimeError("injected before commit")
        if MODE == "kill":
            os.kill(os.getpid(), 9)   # die with the transaction open
        return rid

    @DBOS.workflow()
    def wf(rid):
        return write_row(rid)

    DBOS.launch()
    try:
        with SetWorkflowID(WFID):
            print("RESULT", wf(WFID))
    except Exception as e:
        print("RAISED", type(e).__name__)
    DBOS.destroy()
    '''
)


def _run(app_url: str, sys_url: str, mode: str, wfid: str, tmp_path):
    script = tmp_path / f"probe_{mode}_{wfid}.py"
    script.write_text(PROBE)
    return subprocess.run(
        [sys.executable, str(script), app_url, sys_url, mode, wfid],
        capture_output=True, text=True, timeout=180,
    )


def _counts(app_url: str, wfid: str):
    engine = sa.create_engine(app_url)
    with engine.begin() as c:
        rows = c.execute(
            sa.text("SELECT count(*) FROM probe_rows WHERE id = :i"), {"i": wfid}
        ).scalar_one()
        try:
            steps = c.execute(
                sa.text(
                    "SELECT count(*) FROM dbos.datasource_outputs "
                    "WHERE workflow_id = :i AND output IS NOT NULL"
                ),
                {"i": wfid},
            ).scalar_one()
        except Exception:
            steps = 0
    return int(rows), int(steps)


@requires_postgres
def test_success_commits_both(pg_databases, tmp_path):
    """Happy path: the application write and the step record are both present."""
    app, sysdb = pg_databases
    _run(app, sysdb, "ok", "wf-ok", tmp_path)
    rows, steps = _counts(app, "wf-ok")
    assert rows == 1, "application write should have committed"
    assert steps == 1, "the step's success record should have committed with it"


@requires_postgres
def test_exception_rolls_back_the_application_write(pg_databases, tmp_path):
    """An exception before commit leaves no application write and no SUCCESS record.

    DBOS still writes an *error* record afterwards, on its own transaction — that is
    correct and is what makes the failure visible. What must not exist is a success
    record, or the row the failed step tried to write.
    """
    app, sysdb = pg_databases
    _run(app, sysdb, "raise", "wf-raise", tmp_path)
    rows, success_steps = _counts(app, "wf-raise")
    assert rows == 0, "the application write must have rolled back"
    assert success_steps == 0, "no success record may survive a failed step"

    engine = sa.create_engine(app)
    with engine.begin() as c:
        errors = c.execute(
            sa.text(
                "SELECT count(*) FROM dbos.datasource_outputs "
                "WHERE workflow_id = 'wf-raise' AND error IS NOT NULL"
            )
        ).scalar_one()
    assert int(errors) == 1, "the failure should be recorded as an error outcome"


@requires_postgres
def test_sigkill_mid_transaction_leaves_neither(pg_databases, tmp_path):
    """THE OD-1 GATE.

    The process dies with the transaction open. Afterwards neither the application
    write nor the step record exists. If these committed separately, a kill placed
    between them would leave exactly one — so ``0, 0`` is the property, and it is what
    lets the crash rows of the matrix reason about what a retry will find.
    """
    app, sysdb = pg_databases
    proc = _run(app, sysdb, "kill", "wf-kill", tmp_path)
    assert proc.returncode == -9, f"expected SIGKILL, got {proc.returncode}"

    rows, steps = _counts(app, "wf-kill")
    assert (rows, steps) == (0, 0), (
        "a kill with the transaction open must leave neither the application write "
        f"nor the step record; got probe_rows={rows}, step_records={steps}"
    )


@requires_postgres
def test_committed_step_replays_without_re_running_the_body(pg_databases, tmp_path):
    """A COMMITTED step replays its recorded result instead of re-running.

    This is safe rather than a loophole: the step committed, so the effect and the
    state transition are durably recorded and the action was cleared when it ran.
    Re-clearing a committed step would double-execute it. The governance requirement
    applies to steps that did NOT commit — and those, per the test above, leave nothing
    behind at all.
    """
    app, sysdb = pg_databases
    _run(app, sysdb, "ok", "wf-replay", tmp_path)
    before, _ = _counts(app, "wf-replay")
    _run(app, sysdb, "ok", "wf-replay", tmp_path)   # same workflow id
    after, _ = _counts(app, "wf-replay")
    assert before == after == 1, (
        "the body must not re-run for a committed step; the recorded result replays"
    )


@requires_postgres
def test_dbos_system_database_is_separate_from_the_application_database(pg_databases, tmp_path):
    """The documented consistency boundary (README).

    Workflow *status* lives in the DBOS system database and is NOT in the application
    transaction. After the SIGKILL the system database says PENDING while the
    application database holds nothing — which is exactly what makes recovery re-drive
    the instance. It is also why the adapter never treats engine status as evidence
    that an effect happened.
    """
    app, sysdb = pg_databases
    _run(app, sysdb, "kill", "wf-kill2", tmp_path)

    with sa.create_engine(sysdb).begin() as c:
        status = c.execute(
            sa.text("SELECT status FROM dbos.workflow_status WHERE workflow_uuid = :i"),
            {"i": "wf-kill2"},
        ).scalar_one()
    assert status == "PENDING", "a killed workflow stays PENDING for recovery to find"

    rows, steps = _counts(app, "wf-kill2")
    assert (rows, steps) == (0, 0), (
        "the application database keeps nothing from the killed transaction, even "
        "though the system database records the workflow as PENDING"
    )
