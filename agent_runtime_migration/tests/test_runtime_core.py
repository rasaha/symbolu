"""Commit C tests: runtime loop, planning, memory, reflection, observation return."""
from __future__ import annotations

from agent_runtime_migration.contracts import Action, ExecutionResult, Goal, RiskClass
from agent_runtime_migration.runtime import AgentRuntime, BudgetAccountant, CancellationToken
from agent_runtime_migration.runtime import state as st
from agent_runtime_migration.planning import Planner
from agent_runtime_migration.reasoning import Reflector


def _local(action_id):
    return Action(action_id=action_id, kind="respond", tool_name="respond",
                  risk_class=RiskClass.LOCAL_READ_ONLY, arguments={})


class _StubExecutor:
    """Returns a canned ExecutionResult per action_id (drives loop branches)."""
    def __init__(self, results):
        self._results = results
        self.calls = []

    def execute(self, action):
        self.calls.append(action.action_id)
        return self._results[action.action_id]


def _res(action_id, composed="PROCEED", executed=True, eligible=True):
    return ExecutionResult(action_id=action_id, executed=executed, eligible=eligible,
                           combined_outcome=composed, execution_reference=("ref" if eligible else None),
                           output=f"out:{action_id}")


def _goal(plan, deps=None):
    return Goal(goal_id="g", objective="do it",
                metadata={"plan": plan, "dependencies": deps or {}})


def test_multi_step_local_workflow_completes():
    plan = [_local("a"), _local("b"), _local("c")]
    ex = _StubExecutor({"a": _res("a", None), "b": _res("b", None), "c": _res("c", None)})
    out = AgentRuntime(executor=ex).run(_goal(plan))
    assert out.status == st.COMPLETED
    assert ex.calls == ["a", "b", "c"]
    # observation return: memory received each observation
    assert out.observations and all(o.succeeded for o in out.observations)
    assert len(out.observations) == 3


def test_memory_and_reflection_receive_observations():
    plan = [_local("a")]
    ex = _StubExecutor({"a": _res("a", None)})
    rt = AgentRuntime(executor=ex)
    out = rt.run(_goal(plan))
    assert rt.memory.snapshot()["count"] == 1
    assert "REFLECTED" in out.trace.types()
    assert "OBSERVED" in out.trace.types()


def test_denied_action_triggers_replan_then_stop():
    plan = [_local("a")]
    ex = _StubExecutor({"a": _res("a", "BLOCKED_BY_AUTHORIZATION", executed=False, eligible=False)})
    out = AgentRuntime(executor=ex).run(_goal(plan), max_replans=0)
    assert out.status == st.STOPPED
    assert out.observations[0].outcome == "blocked"


def test_held_action_awaits_human():
    plan = [_local("a")]
    ex = _StubExecutor({"a": _res("a", "HELD_BY_ACP", executed=False, eligible=False)})
    out = AgentRuntime(executor=ex).run(_goal(plan))
    assert out.status == st.AWAITING_HUMAN
    assert "HUMAN_REQUESTED" in out.trace.types()


def test_pending_action_awaits_human():
    plan = [_local("a")]
    ex = _StubExecutor({"a": _res("a", "PENDING_AUTHORIZATION", executed=False, eligible=False)})
    out = AgentRuntime(executor=ex).run(_goal(plan))
    assert out.status == st.AWAITING_HUMAN


def test_cancellation_stops_loop():
    plan = [_local("a"), _local("b")]
    ex = _StubExecutor({"a": _res("a", None), "b": _res("b", None)})
    tok = CancellationToken()
    tok.cancel()
    out = AgentRuntime(executor=ex).run(_goal(plan), cancellation=tok)
    assert out.status == st.CANCELLED
    assert ex.calls == []


def test_budget_stops_loop():
    plan = [_local("a"), _local("b"), _local("c")]
    ex = _StubExecutor({k: _res(k, None) for k in ("a", "b", "c")})
    out = AgentRuntime(executor=ex, budget=BudgetAccountant(max_steps=1)).run(_goal(plan))
    assert out.status == st.BUDGET_STOP
    assert len(ex.calls) <= 2


def test_planner_respects_dependencies():
    plan = [_local("a"), _local("b")]
    ex = _StubExecutor({"a": _res("a", None), "b": _res("b", None)})
    out = AgentRuntime(executor=ex).run(_goal(plan, deps={"b": ["a"]}))
    assert ex.calls == ["a", "b"] and out.status == st.COMPLETED


def test_default_planner_single_respond_action():
    plan = Planner().plan(Goal(goal_id="g", objective="hello"))
    assert len(plan.steps) == 1 and plan.steps[0].kind == "respond"
