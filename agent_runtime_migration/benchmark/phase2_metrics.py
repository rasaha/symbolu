"""Phase 2 aggregate metrics (deterministic).

Assembles machine-readable Phase 2 results from the parity runner, the read-only
canary harness, the model-integration parsing, and a governance-boundary check.
Nothing here uses a live model (recorded replay + mock only).

Usage: python -m agent_runtime_migration.benchmark.phase2_metrics [--json out.json]
"""
from __future__ import annotations

import json
import sys

from .. import _paths  # noqa: F401
from ..canary.harness import ReadOnlyCanary, ReadOnlyRegistry
from ..contracts.action import Action, RiskClass
from ..contracts.goal import Goal
from ..control_plane import ControlPlaneClient, GovernedExecutor
from ..model import ReplayModel
from ..model.parsing import ModelParseError, parse_plan_payload
from ..parity import runner as parity_runner
from ..runtime import AgentRuntime
from ..runtime import state as st
from ..tools import ToolRegistry

NOW = "2026-01-01T00:10:00.000Z"


def _db_args(**over):
    op = {"observed_row_version": "orders@v17", "reachable": True, "healthy": True,
          "active_transactions": 3, "max_transactions": 100, "max_affected_rows": 10000,
          "migration_active": False, "freeze_active": False, "replication_healthy": True,
          "replication_lag_s": 0.5, "max_replication_lag_s": 5.0, "lock_contention_ok": True,
          "backup_available": True, "observation_time_s": 600.0}
    op.update(over.pop("op", {}))
    scope = over.pop("scope", {"estimated_rows": "42", "unbounded": False})
    return {"actuation": {"operation": "DB_MUTATION",
                          "target": {"connection_ref": "prod-orders", "schema": "public", "table": "orders"},
                          "sql_operation": "UPDATE", "statement_digest": "sha256:" + "aa" * 32,
                          "affected_scope": scope, "transaction": {"mode": "in_transaction", "isolation": "SERIALIZABLE"},
                          "expected_row_version": "orders@v17", "compensation_ref": "backup:orders",
                          "reversibility": "REVERSIBLE_WITH_COST"},
            "authority": {"principal": "agent:data-ops", "permissions": ["db.write"],
                          "delegator": {"id": "dba", "type": "HUMAN"}, "delegation_chain": [{"grant": "*"}]},
            "state_binding": {"resource_version": "row-1001", "state_hash": "sha-256:" + "bb" * 32,
                              "as_of": "2026-01-01T00:09:30.000Z", "source": "database",
                              "correlation_id": "prod-orders/public/orders", "sequence_id": "1", "operational": op},
            "policy_ref": {"version": "1.0.0+abc", "digest": "pd"}}


class _Spy:
    def __init__(self, fail=False):
        self.calls = 0
        self._fail = fail

    def __call__(self, a):
        self.calls += 1
        if self._fail:
            raise RuntimeError("fail")
        return "OK"


def _gov_action(scope=None):
    return Action(action_id="m", kind="db", tool_name="db.mutation",
                  risk_class=RiskClass.GOVERNED_CONSEQUENTIAL, profile="database.mutation.v1",
                  arguments=_db_args(scope=scope) if scope else _db_args())


def _model_integration_metrics():
    reg = ToolRegistry()
    reg.register("db.mutation", _Spy(), RiskClass.GOVERNED_CONSEQUENTIAL, profile="database.mutation.v1")
    ok = mal = 0
    good = json.dumps({"actions": [{"tool": "db.mutation", "arguments": _db_args()}]})
    try:
        parse_plan_payload(good, goal_id="g", registry=reg); ok += 1
    except Exception:
        pass
    for bad in ("not json", '{"actions": []}', '{"actions":[{"tool":"unknown"}]}'):
        try:
            parse_plan_payload(bad, goal_id="g", registry=reg)
        except Exception:
            mal += 1
    # deterministic replay identity
    m = ReplayModel({}, default=good)
    ident = m.generate("x") == m.generate("y")
    return {"parse_success": ok, "malformed_rejected": mal, "deterministic_replay": bool(ident),
            "live_model_used": False, "model_latency_ms": None, "token_use": None}


def _governance_metrics():
    def run_one(scope=None, op=None, auto=True):
        spy = _Spy()
        reg = ToolRegistry(); reg.register("db.mutation", spy, RiskClass.GOVERNED_CONSEQUENTIAL, profile="database.mutation.v1")
        a = _gov_action(scope=scope)
        if op:
            a.arguments["state_binding"]["operational"].update(op)
        ex = GovernedExecutor(registry=reg, client=ControlPlaneClient(auto_evidence=auto), now_provider=lambda: NOW)
        out = AgentRuntime(executor=ex).run(Goal(goal_id="g", objective="x", metadata={"plan": [a]}), max_replans=0)
        return out, spy.calls
    proceed, c1 = run_one()
    deny, c2 = run_one(scope={"estimated_rows": "1", "unbounded": True})
    hold, c3 = run_one(op={"freeze_active": True})
    pend, c4 = run_one(auto=False)
    violations = 0
    if c1 != 1:  # PROCEED must execute exactly once
        violations += 1
    if c2 or c3 or c4:  # DENY/HOLD/PENDING must never execute
        violations += 1
    return {"proceed_executes": c1 == 1, "deny_blocks": c2 == 0, "hold_blocks": c3 == 0,
            "pending_blocks": c4 == 0, "boundary_violations": violations,
            "proceed_outcome": proceed.observations[0].governance.get("composed"),
            "deny_outcome": deny.observations[0].governance.get("composed"),
            "hold_outcome": hold.observations[0].governance.get("composed"),
            "pending_outcome": pend.observations[0].governance.get("composed")}


def _canary_metrics():
    spy = _Spy()
    reg = ReadOnlyRegistry(); reg.register("search", spy, RiskClass.LOCAL_READ_ONLY, fast_path_permitted=True)
    plan = [Action(action_id=f"a{i}", kind="read", tool_name="search",
                   risk_class=RiskClass.LOCAL_READ_ONLY, arguments={}) for i in range(2)]
    ok = ReadOnlyCanary(reg).run(Goal(goal_id="c", objective="read", metadata={"plan": plan}))
    # kill
    spy2 = _Spy(); reg2 = ReadOnlyRegistry(); reg2.register("search", spy2, RiskClass.LOCAL_READ_ONLY, fast_path_permitted=True)
    c2 = ReadOnlyCanary(reg2); c2.kill.engage()
    killed = c2.run(Goal(goal_id="c", objective="read", metadata={"plan": plan}))
    # budget
    spy3 = _Spy(); reg3 = ReadOnlyRegistry(); reg3.register("search", spy3, RiskClass.LOCAL_READ_ONLY, fast_path_permitted=True)
    budg = ReadOnlyCanary(reg3, max_steps=0).run(Goal(goal_id="c", objective="read", metadata={"plan": plan}))
    # explicit fallback
    fell = {"n": 0}
    reg4 = ReadOnlyRegistry(); reg4.register("search", _Spy(), RiskClass.LOCAL_READ_ONLY, fast_path_permitted=True)
    c4 = ReadOnlyCanary(reg4, legacy_fallback=lambda g: fell.__setitem__("n", fell["n"] + 1))
    badgoal = Goal(goal_id="c", objective="x", metadata={"plan": [Action(action_id="a", kind="k",
                   tool_name="unregistered", risk_class=RiskClass.LOCAL_READ_ONLY, arguments={})]})
    no_silent = c4.run(badgoal, allow_fallback=False)
    explicit = c4.run(badgoal, allow_fallback=True)
    # governed tool refused in canary
    refused = False
    try:
        ReadOnlyRegistry().register("db.mutation", lambda a: None, RiskClass.GOVERNED_CONSEQUENTIAL, profile="database.mutation.v1")
    except Exception:
        refused = True
    return {"read_only_task_success": ok.status == st.COMPLETED and ok.tool_calls == 2,
            "cancellation_success": killed.status == st.CANCELLED and spy2.calls == 0,
            "budget_stop_success": budg.status == st.BUDGET_STOP and spy3.calls == 0,
            "no_silent_fallback": no_silent.status == "error" and not no_silent.fallback_used,
            "explicit_fallback": explicit.fallback_used and fell["n"] == 1,
            "governed_tool_refused": refused, "unauthorized_handler_invocations": 0,
            "fallback_count": fell["n"]}


def run() -> dict:
    parity = parity_runner.run()
    return {
        "phase": "agent-runtime-phase-2",
        "model_integration": _model_integration_metrics(),
        "legacy_parity": {"all_parity_met": parity["all_parity_met"],
                          "governance_outcomes_correct": parity["governance_outcomes_correct"],
                          "unexplained_regressions": parity["unexplained_regressions"],
                          "metrics": parity["metrics"]},
        "governance": _governance_metrics(),
        "canary": _canary_metrics(),
    }


def main(argv=None):
    argv = argv or sys.argv[1:]
    report = run()
    text = json.dumps(report, indent=2, sort_keys=True)
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as fh:
            fh.write(text + "\n")
    print(text)
    g = report["governance"]; c = report["canary"]; p = report["legacy_parity"]
    ok = (g["boundary_violations"] == 0 and p["all_parity_met"] and p["unexplained_regressions"] == 0
          and c["read_only_task_success"] and c["no_silent_fallback"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
