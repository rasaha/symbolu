"""The ADR §8 matrix, re-run with the PRODUCTION governance hook.

``tests/test_matrix.py`` proves the eleven rows with ``AllowAllGovernanceHook`` — an
explicitly unsafe helper that CLEARs everything. That isolation is deliberate: it shows
the durability properties hold independently of what governance decides.

This module answers the other half. The same rows run against the real
``GovernedExecutionHook``, composing through the ratified
``RiskAuthorityCompositionEngine``, so clearance is genuinely composed and can genuinely
be withheld. Two rows get *stronger* evidence than before rather than merely equivalent
evidence:

* **Row 5** no longer injects an expiry. A real envelope's ``expires_at`` flows through
  composition and the hook's epoch-seconds projection into ``validate_clearance``, so the
  row now also proves the projection lands on the runtime's wall-clock base.
* **Row 9** no longer injects an ESCALATE. The composition produces a HOLD carrying a
  required approval and the hook projects it, so the row proves the disposition is
  *derived* rather than asserted.

Rows 8, 10 and 11 are governance-independent by construction — the budget ledger, the
definition-digest refusal and the clock-discipline refusal do not consult a hook — and
are covered once in ``test_matrix.py``. That is stated here rather than left as a silent
gap in the count.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from typing import Any, List

import pytest
import sqlalchemy as sa

pytest.importorskip(
    "ugence_agent_runtime_governance",
    reason="the production-hook re-run needs packages/integration/agent-runtime-governance",
)

import _hooks
import _production
from _dbos_harness import DEFINITION_DIGEST, WORKFLOW_ID, RecordingProvider, wire
from conftest import requires_postgres
from test_matrix import HARNESS, _child_env

from ugence_agent_runtime.governance.interfaces import GovernanceDisposition

pytestmark = [pytest.mark.postgres, pytest.mark.matrix]


def _child(app: str, sysdb: str, scenario: str, instance_id: str):
    """Run the harness in a real subprocess, with the production hook selected."""
    env = _child_env()
    env["UDE_HOOK"] = "production"
    return subprocess.run(
        [sys.executable, HARNESS, app, sysdb, scenario, instance_id],
        capture_output=True, text=True, timeout=240, env=env,
    )


@pytest.fixture()
def wired_production(pg_databases):
    from dbos import DBOS

    app, sysdb = pg_databases

    def _make(hook=None, **kwargs):
        ds, dbos, adapter, bundle = wire(
            app_url=app, sys_url=sysdb,
            provider=RecordingProvider(app),
            hook=hook or _production.clearing_hook(app),
            **kwargs,
        )
        return ds, adapter, bundle

    try:
        yield app, sysdb, _make
    finally:
        try:
            DBOS.destroy()
        except Exception:
            pass


def _dispositions(app: str, instance_id: str) -> List[str]:
    return [d for (_f, d, _p) in _hooks.evaluations(app, instance_id)]


def _fingerprints(app: str, instance_id: str) -> List[str]:
    return [f for (f, _d, _p) in _hooks.evaluations(app, instance_id)]


# --------------------------------------------------------------------------- #
def test_the_production_hook_clears_through_real_composition(wired_production):
    """Baseline: the hook actually reaches CLEAR, so the rows below mean something.

    A re-run in which the hook silently refused everything would pass most durability
    assertions vacuously — no provider call is trivially satisfied by never clearing.
    """
    app, sysdb, make = wired_production
    ds, adapter, bundle = make()
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="p0", correlation_id="c0", inputs={},
    )
    outcome = adapter.advance(instance_id="p0", attempt_token="a1")

    assert outcome.progressed
    assert _dispositions(app, "p0") == [GovernanceDisposition.CLEAR.value]
    assert _hooks.provider_calls(app) == ["p0:t1"]


@requires_postgres
def test_row_01_crash_before_provider_call(pg_databases):
    app, sysdb = pg_databases
    proc = _child(app, sysdb, "kill_before_provider", "p1")
    assert proc.returncode == -9

    assert _hooks.provider_calls(app) == []
    proc2 = _child(app, sysdb, "recover", "p1")
    assert proc2.returncode == 0, proc2.stderr[-2000:]

    fps = _fingerprints(app, "p1")
    assert len(fps) == 2 and fps[0] == fps[1], (
        "the rebuilt proposal must fingerprint identically, and the production hook "
        "must be consulted again rather than a pre-crash CLEAR being reused"
    )
    assert _dispositions(app, "p1") == ["CLEAR", "CLEAR"]


@requires_postgres
def test_row_02_crash_during_provider_call(pg_databases):
    app, sysdb = pg_databases
    assert _child(app, sysdb, "kill_after_provider", "p2").returncode == -9
    assert _hooks.provider_calls(app) == ["p2:t1"]

    assert _child(app, sysdb, "recover", "p2").returncode == 0
    assert _hooks.provider_calls(app) == ["p2:t1", "p2:t1"], (
        "the retry re-invokes under the same idempotency key"
    )
    assert len(_fingerprints(app, "p2")) == 2


@requires_postgres
def test_row_03_crash_after_effect_before_commit(pg_databases):
    app, sysdb = pg_databases
    assert _child(app, sysdb, "kill_after_provider", "p3").returncode == -9

    engine = sa.create_engine(app)
    with engine.begin() as c:
        checkpoints = c.execute(
            sa.text(
                "SELECT count(*) FROM ugence_art.checkpoints WHERE instance_id='p3'"
            )
        ).scalar_one()
    assert int(checkpoints) == 1, "the advance transaction rolled back whole"

    assert _child(app, sysdb, "recover", "p3").returncode == 0
    assert _hooks.provider_calls(app) == ["p3:t1", "p3:t1"]
    assert len(_fingerprints(app, "p3")) == 2, (
        "the second attempt crossed the production governance boundary"
    )


@requires_postgres
def test_row_04_duplicate_delivery(wired_production):
    app, sysdb, make = wired_production
    ds, adapter, bundle = make()
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="p4", correlation_id="c4", inputs={},
    )

    results: List[Any] = []
    errors: List[BaseException] = []

    def drive(token: str) -> None:
        try:
            results.append(adapter.advance(instance_id="p4", attempt_token=token))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=drive, args=(f"a{i}",)) for i in (1, 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)

    assert not errors, errors
    assert len([r for r in results if r.progressed]) == 1
    assert _hooks.provider_calls(app) == ["p4:t1"]


@requires_postgres
def test_row_05_expiry_travels_the_real_path(wired_production):
    """Stronger than the injected version: the expiry originates on the envelope."""
    app, sysdb, make = wired_production
    ds, adapter, bundle = make(hook=_production.expiring_hook(app))
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="p5", correlation_id="c5", inputs={},
    )
    adapter.advance(instance_id="p5", attempt_token="a1")

    assert _dispositions(app, "p5") == ["CLEAR"], (
        "composition GRANTed — the refusal must come from the expiry check, not from "
        "the hook declining to clear"
    )
    assert _hooks.provider_calls(app) == [], (
        "an already-expired envelope must not reach the provider"
    )


@requires_postgres
def test_row_06_revocation_fails_closed_with_the_production_hook(wired_production):
    app, sysdb, make = wired_production
    ds, adapter, bundle = make(authority_recheck=_hooks.revoking_recheck)
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="p6", correlation_id="c6", inputs={},
    )
    adapter.advance(instance_id="p6", attempt_token="a1")

    assert _dispositions(app, "p6") == ["CLEAR"]
    assert _hooks.provider_calls(app) == [], (
        "the last-mile recheck refuses after a genuine CLEAR"
    )


@requires_postgres
def test_row_06_negative_case_still_holds(wired_production):
    """The requirement is load-bearing under the production hook too."""
    app, sysdb, make = wired_production
    ds, adapter, bundle = make(authority_recheck=None)
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="p6n", correlation_id="c6n", inputs={},
    )
    adapter.advance(instance_id="p6n", attempt_token="a1")

    assert _hooks.provider_calls(app) == ["p6n:t1"], (
        "without a configured recheck the revocation is still not noticed"
    )


@requires_postgres
def test_row_07_corrupted_checkpoint_is_unrecoverable(wired_production):
    from ugence_durable_execution.errors import CheckpointIntegrityError

    app, sysdb, make = wired_production
    ds, adapter, bundle = make()
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="p7", correlation_id="c7", inputs={},
    )
    with sa.create_engine(app).begin() as c:
        c.execute(
            sa.text(
                "UPDATE ugence_art.runtime_state "
                "SET checkpoint = jsonb_set(checkpoint, '{status}', '\"COMPLETED\"') "
                "WHERE instance_id = 'p7'"
            )
        )
    adapter.forget("p7")
    with pytest.raises(CheckpointIntegrityError):
        adapter.advance(instance_id="p7", attempt_token="a2")
    assert _hooks.provider_calls(app) == []


@requires_postgres
def test_row_09_escalation_is_derived_not_asserted(wired_production):
    """The composition produces a HOLD carrying a required approval; the hook projects
    ESCALATE. Driven repeatedly, the instance never moves and never invokes."""
    app, sysdb, make = wired_production
    ds, adapter, bundle = make(hook=_production.escalating_hook(app))
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="p9", correlation_id="c9", inputs={},
    )
    for i in range(4):
        outcome = adapter.advance(instance_id="p9", attempt_token=f"a{i}")
        assert not outcome.progressed or outcome.awaiting_external

    dispositions = set(_dispositions(app, "p9"))
    assert dispositions == {GovernanceDisposition.ESCALATE.value}, (
        f"expected a derived ESCALATE on every re-drive; got {dispositions}"
    )
    assert _hooks.provider_calls(app) == []

    fps = set(_fingerprints(app, "p9"))
    assert len(fps) == 1, "every re-drive proposes the same action"


@requires_postgres
def test_a_denying_composition_never_reaches_the_provider(wired_production):
    """Not an ADR row, but the property the whole GAS-3 projection exists for: a real
    Risk Authority DENY, composed and projected, stops the durable step."""
    app, sysdb, make = wired_production
    ds, adapter, bundle = make(hook=_production.denying_hook(app))
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id="pd", correlation_id="cd", inputs={},
    )
    adapter.advance(instance_id="pd", attempt_token="a1")

    assert _dispositions(app, "pd") == [GovernanceDisposition.BLOCK.value]
    assert _hooks.provider_calls(app) == []


def test_rows_08_10_11_are_governance_independent():
    """Stated rather than silently omitted.

    The budget ledger, the definition-digest refusal and the clock-discipline refusal
    consult no governance hook, so re-running them against a different hook would
    exercise the same code with the same inputs. They are covered once, in
    ``test_matrix.py``.
    """
    import inspect

    import test_matrix

    for name in (
        "test_row_08_budget_contention_is_settled_by_the_database",
        "test_row_10_definition_version_change_refuses",
        "test_row_11_production_root_refuses_a_monotonic_clock",
    ):
        fn = getattr(test_matrix, name)
        source = inspect.getsource(fn)
        assert "hook" not in source.replace("_hooks.provider_calls", ""), (
            f"{name} appears to depend on a governance hook after all; it would then "
            "need a production-hook re-run rather than this exemption"
        )
