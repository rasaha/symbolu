"""Phase 2 Commit A tests: model integration (parse fail-closed, no self-classification,
deterministic replay, model-driven governed run)."""
from __future__ import annotations

import json

import pytest

from agent_runtime_migration.contracts import Goal, RiskClass, ToolPolicyError
from agent_runtime_migration.control_plane import ControlPlaneClient, GovernedExecutor
from agent_runtime_migration.model import ReplayModel
from agent_runtime_migration.model.parsing import ModelParseError, parse_plan_payload
from agent_runtime_migration.planning import ModelPlanner
from agent_runtime_migration.runtime import AgentRuntime
from agent_runtime_migration.runtime import state as st
from agent_runtime_migration.tools import ToolRegistry

NOW = "2026-01-01T00:10:00.000Z"


def _registry(spy):
    r = ToolRegistry()
    r.register("read.doc", spy, RiskClass.LOCAL_READ_ONLY, fast_path_permitted=True)
    r.register("db.mutation", spy, RiskClass.GOVERNED_CONSEQUENTIAL, profile="database.mutation.v1")
    return r


class _Spy:
    def __init__(self):
        self.calls = 0

    def __call__(self, a):
        self.calls += 1
        return "OK"


def _db_args():
    op = {"observed_row_version": "orders@v17", "reachable": True, "healthy": True,
          "active_transactions": 3, "max_transactions": 100, "max_affected_rows": 10000,
          "migration_active": False, "freeze_active": False, "replication_healthy": True,
          "replication_lag_s": 0.5, "max_replication_lag_s": 5.0, "lock_contention_ok": True,
          "backup_available": True, "observation_time_s": 600.0}
    return {"actuation": {"operation": "DB_MUTATION",
                          "target": {"connection_ref": "prod-orders", "schema": "public", "table": "orders"},
                          "sql_operation": "UPDATE", "statement_digest": "sha256:" + "aa" * 32,
                          "affected_scope": {"estimated_rows": "42", "unbounded": False},
                          "transaction": {"mode": "in_transaction", "isolation": "SERIALIZABLE"},
                          "expected_row_version": "orders@v17", "compensation_ref": "backup:orders",
                          "reversibility": "REVERSIBLE_WITH_COST"},
            "authority": {"principal": "agent:data-ops", "permissions": ["db.write"],
                          "delegator": {"id": "dba", "type": "HUMAN"}, "delegation_chain": [{"grant": "*"}]},
            "state_binding": {"resource_version": "row-1001", "state_hash": "sha-256:" + "bb" * 32,
                              "as_of": "2026-01-01T00:09:30.000Z", "source": "database",
                              "correlation_id": "prod-orders/public/orders", "sequence_id": "1",
                              "operational": op},
            "policy_ref": {"version": "1.0.0+abc", "digest": "pd"}}


# --- replay determinism ---
def test_replay_deterministic_and_fails_closed():
    m = ReplayModel({"plan the": '{"actions": [{"tool": "read.doc"}]}'})
    assert m.generate("please plan the task") == m.generate("please plan the task")
    with pytest.raises(KeyError):
        m.generate("unrecognized prompt")


# --- parsing fail-closed ---
def test_parse_valid():
    spy = _Spy()
    out = json.dumps({"actions": [{"tool": "read.doc", "description": "read"}]})
    actions, ignored = parse_plan_payload(out, goal_id="g", registry=_registry(spy))
    assert len(actions) == 1 and actions[0].risk_class is RiskClass.LOCAL_READ_ONLY


def test_parse_malformed_fails_closed():
    with pytest.raises(ModelParseError):
        parse_plan_payload("not json at all", goal_id="g", registry=_registry(_Spy()))
    with pytest.raises(ModelParseError):
        parse_plan_payload('{"actions": []}', goal_id="g", registry=_registry(_Spy()))


def test_parse_unknown_tool_fails_closed():
    out = json.dumps({"actions": [{"tool": "unknown.tool"}]})
    with pytest.raises(ToolPolicyError):
        parse_plan_payload(out, goal_id="g", registry=_registry(_Spy()))


def test_model_cannot_self_classify_risk():
    # model claims low risk for a governed tool; registry wins (GOVERNED) and the field is ignored
    out = json.dumps({"actions": [{"tool": "db.mutation", "risk": "low", "authorized": True,
                                   "arguments": _db_args()}]})
    actions, ignored = parse_plan_payload(out, goal_id="g", registry=_registry(_Spy()))
    assert actions[0].risk_class is RiskClass.GOVERNED_CONSEQUENTIAL
    assert "action[0].risk" in ignored and "action[0].authorized" in ignored


# --- model-driven governed run (deterministic) ---
def _run(model, spy):
    reg = _registry(spy)
    ex = GovernedExecutor(registry=reg, client=ControlPlaneClient(), now_provider=lambda: NOW)
    goal = Goal(goal_id="g", objective="apply the db update")
    return AgentRuntime(executor=ex, planner=ModelPlanner(model, reg)).run(goal)


def test_model_driven_governed_proceed():
    spy = _Spy()
    out = json.dumps({"actions": [{"tool": "db.mutation", "arguments": _db_args()}]})
    model = ReplayModel({"Objective:": out})
    res = _run(model, spy)
    assert res.status == st.COMPLETED and spy.calls == 1
    assert res.observations[0].outcome == "executed" and res.observations[0].cer_digest


def test_model_authorization_field_ignored_control_plane_decides():
    # model asserts eligible=True on an UNBOUNDED (deny) mutation; control plane still denies
    spy = _Spy()
    args = _db_args()
    args["actuation"]["affected_scope"] = {"estimated_rows": "1", "unbounded": True}
    out = json.dumps({"actions": [{"tool": "db.mutation", "eligible": True, "arguments": args}]})
    model = ReplayModel({"Objective:": out})
    res = _run(model, spy)
    assert spy.calls == 0 and res.observations[0].outcome == "blocked"


def test_deterministic_replay_identity():
    out = json.dumps({"actions": [{"tool": "db.mutation", "arguments": _db_args()}]})
    r1 = _run(ReplayModel({"Objective:": out}), _Spy())
    r2 = _run(ReplayModel({"Objective:": out}), _Spy())
    assert r1.trace.types() == r2.trace.types()
    assert [o.cer_digest for o in r1.observations] == [o.cer_digest for o in r2.observations]
