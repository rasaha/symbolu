"""Commit D tests: trusted registry, governed executor (no bypass), fast path, workflow."""
from __future__ import annotations

import pytest

from agent_runtime_migration.contracts import Action, Goal, GovernanceBoundaryError, RiskClass, ToolPolicyError
from agent_runtime_migration.control_plane import ControlPlaneClient, GovernedExecutor
from agent_runtime_migration.runtime import AgentRuntime
from agent_runtime_migration.runtime import state as st
from agent_runtime_migration.tools import ToolRegistry
from agent_runtime_migration.workflow import Step, Workflow, WorkflowScheduler

NOW = "2026-01-01T00:10:00.000Z"


def _db_actuation(**over):
    a = {"operation": "DB_MUTATION",
         "target": {"connection_ref": "prod-orders", "schema": "public", "table": "orders"},
         "sql_operation": "UPDATE", "statement_digest": "sha256:" + "aa" * 32,
         "affected_scope": {"estimated_rows": "42", "unbounded": False},
         "transaction": {"mode": "in_transaction", "isolation": "SERIALIZABLE"},
         "expected_row_version": "orders@v17", "compensation_ref": "backup:orders",
         "reversibility": "REVERSIBLE_WITH_COST"}
    a.update(over)
    return a


def _envelope_sections(**op_over):
    op = {"observed_row_version": "orders@v17", "reachable": True, "healthy": True,
          "active_transactions": 3, "max_transactions": 100, "max_affected_rows": 10000,
          "migration_active": False, "freeze_active": False, "replication_healthy": True,
          "replication_lag_s": 0.5, "max_replication_lag_s": 5.0, "lock_contention_ok": True,
          "backup_available": True, "observation_time_s": 600.0}
    op.update(op_over)
    return {
        "authority": {"principal": "agent:data-ops", "permissions": ["db.write"],
                      "delegator": {"id": "dba", "type": "HUMAN"}, "delegation_chain": [{"grant": "*"}]},
        "state_binding": {"resource_version": "row-1001", "state_hash": "sha-256:" + "bb" * 32,
                          "as_of": "2026-01-01T00:09:30.000Z", "source": "database",
                          "correlation_id": "prod-orders/public/orders", "sequence_id": "1",
                          "operational": op},
        "policy_ref": {"version": "1.0.0+abc", "digest": "pd"}}


def _governed_action(action_id="a", op_over=None, **actover):
    args = {"actuation": _db_actuation(**actover)}
    args.update(_envelope_sections(**(op_over or {})))
    return Action(action_id=action_id, kind="database.mutation", tool_name="db.mutation",
                  risk_class=RiskClass.GOVERNED_CONSEQUENTIAL, profile="database.mutation.v1",
                  arguments=args)


class _Spy:
    def __init__(self):
        self.calls = 0

    def __call__(self, args):
        self.calls += 1
        return "DB_APPLIED"


def _registry(spy):
    reg = ToolRegistry()
    reg.register("db.mutation", spy, RiskClass.GOVERNED_CONSEQUENTIAL, profile="database.mutation.v1")
    reg.register("read.doc", lambda a: "DOC", RiskClass.LOCAL_READ_ONLY, fast_path_permitted=True)
    reg.register("delete.local", lambda a: "X", RiskClass.LOCAL_READ_ONLY)  # not fast-path permitted
    return reg


def _executor(spy, client=None):
    return GovernedExecutor(registry=_registry(spy), client=client or ControlPlaneClient(),
                            now_provider=lambda: NOW)


# --- governed execution boundary ---
def test_governed_proceed_runs_tool():
    spy = _Spy()
    res = _executor(spy).execute(_governed_action())
    assert res.executed and res.combined_outcome == "PROCEED"
    assert res.execution_reference and spy.calls == 1


def test_governed_deny_does_not_run_tool():
    spy = _Spy()
    res = _executor(spy).execute(_governed_action(affected_scope={"estimated_rows": "42", "unbounded": True}))
    assert not res.executed and res.combined_outcome == "BLOCKED_BY_AUTHORIZATION"
    assert spy.calls == 0                       # the tool NEVER ran


def test_governed_hold_does_not_run_tool():
    spy = _Spy()
    res = _executor(spy).execute(_governed_action(op_over={"freeze_active": True}))
    assert not res.executed and res.combined_outcome == "HELD_BY_ACP"
    assert spy.calls == 0


def test_pending_does_not_run_tool():
    spy = _Spy()
    ex = GovernedExecutor(registry=_registry(spy),
                          client=ControlPlaneClient(auto_evidence=False), now_provider=lambda: NOW)
    res = ex.execute(_governed_action())
    assert not res.executed and res.combined_outcome == "PENDING_AUTHORIZATION"
    assert spy.calls == 0


# --- fast path + risk-class integrity ---
def test_local_fast_path_runs():
    spy = _Spy()
    a = Action(action_id="r", kind="read", tool_name="read.doc",
               risk_class=RiskClass.LOCAL_READ_ONLY, arguments={})
    res = _executor(spy).execute(a)
    assert res.executed and res.combined_outcome is None    # local, no CER


def test_non_permitted_local_tool_refused():
    spy = _Spy()
    a = Action(action_id="d", kind="x", tool_name="delete.local",
               risk_class=RiskClass.LOCAL_READ_ONLY, arguments={})
    with pytest.raises(ToolPolicyError):
        _executor(spy).execute(a)


def test_model_cannot_reclassify_governed_tool_as_local():
    spy = _Spy()
    # action claims LOCAL_READ_ONLY but the trusted registry says GOVERNED
    a = Action(action_id="c", kind="db", tool_name="db.mutation",
               risk_class=RiskClass.LOCAL_READ_ONLY, arguments={})
    with pytest.raises(GovernanceBoundaryError):
        _executor(spy).execute(a)


# --- loop end-to-end with the real governed executor ---
def test_runtime_loop_governed_proceed_end_to_end():
    spy = _Spy()
    goal = Goal(goal_id="g", objective="apply db update",
                metadata={"plan": [_governed_action("a")]})
    out = AgentRuntime(executor=_executor(spy)).run(goal)
    assert out.status == st.COMPLETED and spy.calls == 1
    assert out.observations[0].outcome == "executed"
    assert out.observations[0].cer_digest


def test_runtime_loop_governed_denied_end_to_end():
    spy = _Spy()
    goal = Goal(goal_id="g", objective="unbounded update",
                metadata={"plan": [_governed_action("a", affected_scope={"estimated_rows": "1", "unbounded": True})]})
    out = AgentRuntime(executor=_executor(spy)).run(goal, max_replans=0)
    assert spy.calls == 0 and out.observations[0].outcome == "blocked"


# --- workflow ---
def test_workflow_scheduler_orders_and_checkpoints():
    spy = _Spy()
    ex = _executor(spy)
    wf = Workflow(workflow_id="w", steps=[Step(_governed_action("a")), Step(_governed_action("b"))],
                  dependencies={"b": ("a",)})
    results = WorkflowScheduler(ex).run(wf)
    assert [r.action_id for r in results] == ["a", "b"]
    cp = wf.checkpoint()
    assert cp.completed == ["a", "b"]
    # restore into a fresh workflow
    wf2 = Workflow(workflow_id="w", steps=[Step(_governed_action("a")), Step(_governed_action("b"))])
    wf2.restore(cp)
    assert wf2.next_step() is None
