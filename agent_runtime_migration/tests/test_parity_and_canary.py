"""Phase 2 Commit C tests: legacy-vs-new parity + read-only canary."""
from __future__ import annotations

import pytest

from agent_runtime_migration.contracts import Action, Goal, RiskClass, ToolPolicyError
from agent_runtime_migration.canary.harness import ReadOnlyCanary, ReadOnlyRegistry
from agent_runtime_migration.parity import runner as parity_runner
from agent_runtime_migration.runtime import state as st


# ---------------- parity ----------------
def test_parity_all_met_and_governance_correct():
    r = parity_runner.run()
    assert r["all_parity_met"] is True
    assert r["governance_outcomes_correct"] is True
    assert r["unexplained_regressions"] == 0
    m = r["metrics"]
    assert m["plan_agreement"] == m["scenarios"]        # both decompose the shared model identically
    assert m["tool_agreement"] == m["scenarios"]
    assert m["new_governance_outcome_correct"] == m["governed_scenarios"] > 0


def test_parity_labels_present():
    r = parity_runner.run()
    labels = {rec["label"] for rec in r["scenarios"]}
    assert "PARITY" in labels and "INTENTIONAL_DIFFERENCE" in labels


# ---------------- canary ----------------
class _Spy:
    def __init__(self):
        self.calls = 0

    def __call__(self, a):
        self.calls += 1
        return "DOC"


def _read_only_registry(spy):
    reg = ReadOnlyRegistry()
    reg.register("search", spy, RiskClass.LOCAL_READ_ONLY, fast_path_permitted=True)
    return reg


def _read_goal(tool="search", n=2):
    plan = [Action(action_id=f"a{i}", kind="read", tool_name=tool,
                   risk_class=RiskClass.LOCAL_READ_ONLY, arguments={}) for i in range(n)]
    return Goal(goal_id="canary", objective="read only", metadata={"plan": plan})


def test_canary_refuses_governed_tool():
    reg = ReadOnlyRegistry()
    with pytest.raises(ToolPolicyError):
        reg.register("db.mutation", lambda a: None, RiskClass.GOVERNED_CONSEQUENTIAL,
                     profile="database.mutation.v1")


def test_canary_runs_read_only_task():
    spy = _Spy()
    res = ReadOnlyCanary(_read_only_registry(spy)).run(_read_goal(n=2))
    assert res.status == st.COMPLETED and spy.calls == 2 and res.tool_calls == 2
    assert "OBSERVED" in res.trace_types and len(res.observations) == 2


def test_canary_kill_switch():
    spy = _Spy()
    canary = ReadOnlyCanary(_read_only_registry(spy))
    canary.kill.engage()
    res = canary.run(_read_goal())
    assert res.status == st.CANCELLED and spy.calls == 0 and res.kill_switch_triggered


def test_canary_budget_bound():
    spy = _Spy()
    res = ReadOnlyCanary(_read_only_registry(spy), max_steps=0).run(_read_goal(n=3))
    assert res.status == st.BUDGET_STOP and spy.calls == 0


def test_canary_cannot_invoke_write_handler():
    # a write-capable handler cannot even be registered in the canary
    reg = ReadOnlyRegistry()
    with pytest.raises(ToolPolicyError):
        reg.register("write.file", lambda a: None, RiskClass.GOVERNED_CONSEQUENTIAL,
                     profile="database.mutation.v1")


def test_canary_explicit_fallback_only():
    spy = _Spy()
    fell_back = {"n": 0}

    def legacy_fallback(goal):
        fell_back["n"] += 1

    reg = _read_only_registry(spy)
    canary = ReadOnlyCanary(reg, legacy_fallback=legacy_fallback)
    # a plan referencing an unregistered tool -> new-runtime raises
    bad_goal = Goal(goal_id="c", objective="x", metadata={"plan": [
        Action(action_id="a", kind="k", tool_name="unregistered",
               risk_class=RiskClass.LOCAL_READ_ONLY, arguments={})]})

    # without allow_fallback: NO silent fallback -> explicit error, legacy NOT called
    res = canary.run(bad_goal, allow_fallback=False)
    assert res.status == "error" and fell_back["n"] == 0 and not res.fallback_used

    # with allow_fallback: explicit, audited fallback
    res2 = canary.run(bad_goal, allow_fallback=True)
    assert res2.status == "fallback" and res2.fallback_used and fell_back["n"] == 1
    assert "new-runtime error" in res2.fallback_reason
