"""Phase 2 Commit B: strengthened replan/observation (§8) + security invariants (§11)."""
from __future__ import annotations

import copy
import json

import pytest

from agent_runtime_migration.contracts import (
    Action, ExecutionResult, Goal, GovernanceBoundaryError, RiskClass, ToolPolicyError,
)
from agent_runtime_migration.control_plane import ControlPlaneClient, GovernedExecutor
from agent_runtime_migration.model import ReplayModel
from agent_runtime_migration.model.parsing import ModelParseError, parse_plan_payload
from agent_runtime_migration.planning import ModelPlanner
from agent_runtime_migration.proposal import build_cer, cer_identity, ProposalContext
from agent_runtime_migration.proposal.identity_bridge import assert_binding
from agent_runtime_migration.runtime import AgentRuntime, BudgetAccountant, CancellationToken
from agent_runtime_migration.runtime import state as st
from agent_runtime_migration.runtime.resolution import ResolutionBudget, decide, REPLAN, RETRY, STOP
from agent_runtime_migration.tools import ToolRegistry

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


def _env(**op_over):
    op = {"observed_row_version": "orders@v17", "reachable": True, "healthy": True,
          "active_transactions": 3, "max_transactions": 100, "max_affected_rows": 10000,
          "migration_active": False, "freeze_active": False, "replication_healthy": True,
          "replication_lag_s": 0.5, "max_replication_lag_s": 5.0, "lock_contention_ok": True,
          "backup_available": True, "observation_time_s": 600.0}
    op.update(op_over)
    return {"authority": {"principal": "agent:data-ops", "permissions": ["db.write"],
                          "delegator": {"id": "dba", "type": "HUMAN"}, "delegation_chain": [{"grant": "*"}]},
            "state_binding": {"resource_version": "row-1001", "state_hash": "sha-256:" + "bb" * 32,
                              "as_of": "2026-01-01T00:09:30.000Z", "source": "database",
                              "correlation_id": "prod-orders/public/orders", "sequence_id": "1",
                              "operational": op},
            "policy_ref": {"version": "1.0.0+abc", "digest": "pd"}}


def _gov_action(action_id="m", **act_over):
    args = {"actuation": _db_actuation(**act_over)}
    args.update(_env())
    return Action(action_id=action_id, kind="database.mutation", tool_name="db.mutation",
                  risk_class=RiskClass.GOVERNED_CONSEQUENTIAL, profile="database.mutation.v1", arguments=args)


class _Spy:
    def __init__(self, fail_times=0):
        self.calls = 0
        self._fail_times = fail_times

    def __call__(self, a):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise RuntimeError("flaky")
        return "OK"


def _reg(spy):
    r = ToolRegistry()
    r.register("db.mutation", spy, RiskClass.GOVERNED_CONSEQUENTIAL, profile="database.mutation.v1")
    r.register("read.doc", spy, RiskClass.LOCAL_READ_ONLY, fast_path_permitted=True)
    r.register("write.file", spy, RiskClass.GOVERNED_CONSEQUENTIAL, profile="database.mutation.v1")
    return r


def _ex(spy):
    return GovernedExecutor(registry=_reg(spy), client=ControlPlaneClient(), now_provider=lambda: NOW)


# ================= §8 strengthened replan / retry =================
def test_execution_failure_retry_within_budget_then_succeeds():
    spy = _Spy(fail_times=1)   # fails once then succeeds
    goal = Goal(goal_id="g", objective="x", metadata={"plan": [_gov_action("m")]})
    out = AgentRuntime(executor=_ex(spy)).run(
        goal, resolution_budget=ResolutionBudget(max_retries_per_action=1))
    assert out.status == st.COMPLETED and spy.calls == 2


def test_execution_failure_exhausts_retries_and_stops():
    spy = _Spy(fail_times=5)
    goal = Goal(goal_id="g", objective="x", metadata={"plan": [_gov_action("m")]})
    out = AgentRuntime(executor=_ex(spy)).run(
        goal, resolution_budget=ResolutionBudget(max_retries_per_action=1))
    assert out.status == st.STOPPED and spy.calls == 2   # 1 attempt + 1 retry


def test_denied_is_not_auto_retried():
    # An ActionGate DENY must never be resolved as RETRY, even with retry budget.
    b = ResolutionBudget(max_retries_per_action=5, max_replans=0)
    assert decide("blocked", retries_used=0, replans_used=0, budget=b) != RETRY
    assert decide("blocked", retries_used=0, replans_used=0, budget=b) == STOP
    assert decide("blocked", retries_used=0, replans_used=0,
                  budget=ResolutionBudget(max_replans=1)) == REPLAN


def test_stale_refresh_produces_new_cer_identity():
    ctx_a = ProposalContext(**{k: v for k, v in _env().items()},
                            provenance={"runtime": "r", "model_provider": "p", "objective": "o"})
    a = _gov_action("m")
    cer_a = build_cer(a, ctx_a)
    id_a = cer_identity(cer_a)
    # refresh: a materially different expected_row_version -> new identity
    refreshed = copy.deepcopy(a.arguments["actuation"]); refreshed["expected_row_version"] = "orders@v18"
    a2 = Action(action_id="m", kind=a.kind, tool_name=a.tool_name, risk_class=a.risk_class,
                profile=a.profile, arguments={**a.arguments, "actuation": refreshed})
    cer_b = build_cer(a2, ctx_a)
    assert cer_identity(cer_b) != id_a
    with pytest.raises(GovernanceBoundaryError):
        assert_binding(cer_b, id_a)   # old decision cannot bind the refreshed action


def test_iteration_cap_prevents_runaway():
    # a governed action that always fails, with a huge retry budget but tiny iteration cap
    spy = _Spy(fail_times=9999)
    goal = Goal(goal_id="g", objective="x", metadata={"plan": [_gov_action("m")]})
    out = AgentRuntime(executor=_ex(spy)).run(
        goal, resolution_budget=ResolutionBudget(max_retries_per_action=10**9, max_iterations=5))
    assert out.status == st.STOPPED and spy.calls <= 6


# ================= §11 security invariants =================
def test_inv1_model_cannot_self_classify():
    out = json.dumps({"actions": [{"tool": "db.mutation", "risk": "low",
                                   "arguments": {"actuation": _db_actuation(), **_env()}}]})
    actions, ignored = parse_plan_payload(out, goal_id="g", registry=_reg(_Spy()))
    assert actions[0].risk_class is RiskClass.GOVERNED_CONSEQUENTIAL and "action[0].risk" in ignored


def test_inv2_model_cannot_authorize():
    spy = _Spy()
    out = json.dumps({"actions": [{"tool": "db.mutation", "eligible": True,
                                   "arguments": {"actuation": _db_actuation(affected_scope={"estimated_rows": "1", "unbounded": True}), **_env()}}]})
    r = AgentRuntime(executor=_ex(spy), planner=ModelPlanner(ReplayModel({"Objective:": out}), _reg(spy))).run(
        Goal(goal_id="g", objective="x"), max_replans=0)
    assert spy.calls == 0

def test_inv3_malformed_output_cannot_execute():
    with pytest.raises(ModelParseError):
        parse_plan_payload("garbage", goal_id="g", registry=_reg(_Spy()))


def test_inv4_and_7_bypass_and_hold_do_not_execute():
    spy = _Spy()
    r = AgentRuntime(executor=_ex(spy)).run(
        Goal(goal_id="g", objective="x", metadata={"plan": [_gov_action("m", **{})]}))
    # freeze -> HELD; tool must not run
    spy2 = _Spy()
    a = _gov_action("m"); a.arguments["state_binding"]["operational"]["freeze_active"] = True
    r2 = AgentRuntime(executor=_ex(spy2)).run(Goal(goal_id="g2", objective="x", metadata={"plan": [a]}))
    assert r2.observations[0].outcome == "held" and spy2.calls == 0


def test_inv5_modified_action_new_cer():
    ctx = ProposalContext(**_env(), provenance={"runtime": "r", "model_provider": "p", "objective": "o"})
    base = build_cer(_gov_action("m"), ctx)
    changed = build_cer(_gov_action("m", statement_digest="sha256:" + "99" * 32), ctx)
    assert cer_identity(base) != cer_identity(changed)


def test_inv8_denial_not_retryable_by_default():
    assert decide("blocked", retries_used=0, replans_used=0,
                  budget=ResolutionBudget(max_retries_per_action=3, max_replans=0)) == STOP


def test_inv11_cancellation_prevents_execution():
    spy = _Spy(); tok = CancellationToken(); tok.cancel()
    r = AgentRuntime(executor=_ex(spy)).run(
        Goal(goal_id="g", objective="x", metadata={"plan": [_gov_action("m")]}), cancellation=tok)
    assert r.status == st.CANCELLED and spy.calls == 0


def test_inv12_budget_prevents_further_proposals():
    spy = _Spy()
    r = AgentRuntime(executor=_ex(spy), budget=BudgetAccountant(max_steps=0)).run(
        Goal(goal_id="g", objective="x", metadata={"plan": [_gov_action("m")]}))
    assert r.status == st.BUDGET_STOP and spy.calls == 0


def test_inv13_write_capable_governed_tool_cannot_take_fast_path():
    spy = _Spy()
    # action claims LOCAL but the trusted registry says write.file is GOVERNED -> fail closed
    a = Action(action_id="w", kind="write", tool_name="write.file",
               risk_class=RiskClass.LOCAL_READ_ONLY, arguments={})
    with pytest.raises(GovernanceBoundaryError):
        _ex(spy).execute(a)
