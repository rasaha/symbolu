"""
Tests for H11 — Cumulative Run Budget Enforcement.

Covers the success criteria:
- One RunBudget shared across the whole workflow.
- Iterations / handoffs never reset the budget.
- All accounting is cumulative and monotonic.
- Budget violations stop execution BEFORE the operation begins.
- Traces (snapshots) reconstruct complete resource consumption.
- Deterministic termination status + reason for every failure mode.
"""

import json

import pytest

from agentic.agentic_framework import (
    build_agent,
    MockLLMAdapter,
    ToolSpec,
    ToolRiskLevel,
    IterativeAgentRunner,
    PredicateCompletionChecker,
    KeywordCompletionChecker,
    AgentRegistry,
    KeywordRouter,
    MultiAgentOrchestrator,
    RunBudget,
    RunBudgetLimits,
    RunBudgetStatus,
    TerminationReason,
    BudgetDimension,
    BudgetExhausted,
    attach_run_budget,
    format_run_budget,
)
from agentic.agentic_framework.safety_contract import (
    SafetyGate,
    SafetyContractEvaluator,
)


def _open_gate():
    return SafetyGate(
        SafetyContractEvaluator(
            consistency_threshold=0.0,
            alignment_threshold=0.0,
            reversal_risk_threshold=1.0,
            stability_threshold=0.0,
        )
    )


def _minimal_agent(response="ok"):
    """One model call per run_with_trace (no LLM decomposition, no revisions)."""
    agent = build_agent(
        adapter=MockLLMAdapter(default_response=response),
        use_llm_for_decomposition=False,
        max_revisions=0,
    )
    agent.safety_gate = _open_gate()
    return agent


SEARCH_DECOMP = json.dumps(
    {
        "purpose": "r",
        "purpose_type": "task",
        "reasoning_strategy": "s",
        "agency_level": "FULL",
        "actions": [
            {"description": "look it up", "type": "search", "parameters": {"query": "x"}}
        ],
    }
)


def _tool_agent(response="done"):
    agent = build_agent(
        adapter=MockLLMAdapter(
            responses={"extract structured goal information": SEARCH_DECOMP},
            default_response=response,
        ),
        tools={
            "search": ToolSpec(
                handler=lambda p: {"ok": True},
                description="search",
                risk_level=ToolRiskLevel.READ_ONLY,
            )
        },
        max_revisions=0,
    )
    agent.safety_gate = _open_gate()
    return agent


# ---------------------------------------------------------------------------
# Core RunBudget unit behaviour
# ---------------------------------------------------------------------------
class TestRunBudgetCore:
    def test_reserve_before_execute_no_mutation_on_reject(self):
        b = RunBudget(RunBudgetLimits(max_model_calls=2)).start()
        assert b.reserve(model_calls=1).ok
        assert b.reserve(model_calls=1).ok
        rej = b.reserve(model_calls=1)
        assert rej.ok is False
        assert rej.reason == TerminationReason.MODEL_CALL_LIMIT
        # Rejected reservation must NOT have incremented the counter.
        assert b.usage.model_calls == 2
        assert b.status == RunBudgetStatus.BUDGET_EXHAUSTED

    def test_counters_are_monotonic_and_never_reset(self):
        b = RunBudget(RunBudgetLimits()).start()
        for _ in range(5):
            b.reserve(model_calls=1)
            b.record_usage(prompt_tokens=3, completion_tokens=2)
        assert b.usage.model_calls == 5
        assert b.usage.prompt_tokens == 15
        assert b.usage.completion_tokens == 10
        assert b.usage.total_tokens == 25

    def test_token_gate_blocks_next_operation(self):
        b = RunBudget(RunBudgetLimits(max_total_tokens=10)).start()
        b.record_usage(prompt_tokens=8, completion_tokens=8)  # 16 > 10
        assert b.is_exhausted()
        rej = b.reserve(model_calls=1)
        assert rej.ok is False
        assert rej.reason == TerminationReason.TOKEN_LIMIT

    def test_deterministic_reason_priority(self):
        # Both model_calls and total_tokens over limit -> model_calls wins
        # (earlier in the fixed evaluation order).
        b = RunBudget(RunBudgetLimits(max_model_calls=1, max_total_tokens=1)).start()
        b.reserve(model_calls=1)
        b.record_usage(prompt_tokens=5, completion_tokens=5)
        rej = b.reserve(model_calls=1)
        assert rej.reason == TerminationReason.MODEL_CALL_LIMIT

    def test_snapshot_reconstructs_state(self):
        b = RunBudget(RunBudgetLimits(max_model_calls=5, max_total_tokens=100)).start()
        b.reserve(model_calls=2)
        b.record_usage(prompt_tokens=10, completion_tokens=5, tool_calls=1)
        snap = b.snapshot()
        assert snap["consumed"]["model_calls"] == 2
        assert snap["consumed"]["total_tokens"] == 15
        assert snap["consumed"]["tool_calls"] == 1
        assert snap["remaining"][BudgetDimension.MODEL_CALLS] == 3
        assert snap["status"] == RunBudgetStatus.ACTIVE

    def test_time_exhaustion(self):
        clock = {"t": 0.0}
        b = RunBudget(RunBudgetLimits(max_elapsed_s=1.0), clock=lambda: clock["t"]).start()
        assert b.reserve(model_calls=1).ok
        clock["t"] = 2.0  # advance past the limit
        rej = b.reserve(model_calls=1)
        assert rej.ok is False
        assert rej.reason == TerminationReason.TIME_LIMIT


# ---------------------------------------------------------------------------
# Adapter wrapper
# ---------------------------------------------------------------------------
class TestBudgetedAdapter:
    def test_model_call_counted_and_reserved_before_execute(self):
        agent = _minimal_agent()  # wants 1 model call
        b = RunBudget(RunBudgetLimits(max_model_calls=1)).start()
        attach_run_budget(agent, b)
        agent.new_session()
        agent.run_with_trace("hi")  # exactly 1 call -> ok
        assert b.usage.model_calls == 1
        # Next run would need a 2nd call, which is rejected BEFORE executing.
        with pytest.raises(BudgetExhausted) as ei:
            agent.run_with_trace("again")
        assert ei.value.reason == TerminationReason.MODEL_CALL_LIMIT
        # The rejected call never ran the model, so it stays at the limit.
        assert b.usage.model_calls == 1

    def test_attach_is_idempotent(self):
        agent = _minimal_agent()
        b = RunBudget(RunBudgetLimits()).start()
        attach_run_budget(agent, b)
        first = agent.llm
        attach_run_budget(agent, b)  # same budget -> no re-wrap
        assert agent.llm is first
        assert getattr(agent.llm, "IS_BUDGETED", False) is True

    def test_tokens_recorded_from_estimation(self):
        agent = _minimal_agent(response="hello world")
        b = RunBudget(RunBudgetLimits()).start()
        attach_run_budget(agent, b)
        agent.new_session()
        agent.run_with_trace("some prompt text")
        assert b.usage.total_tokens > 0
        assert b.usage.prompt_tokens > 0


# ---------------------------------------------------------------------------
# Iteration accounting
# ---------------------------------------------------------------------------
class TestIterationAccounting:
    def test_every_iteration_increments_cumulatively(self):
        agent = _minimal_agent()
        b = RunBudget(RunBudgetLimits()).start()
        runner = IterativeAgentRunner(
            agent,
            checker=PredicateCompletionChecker(lambda h: len(h.steps) >= 3),
            max_iterations=5,
            run_budget=b,
        )
        result = runner.run("go")
        assert result.iterations == 3
        assert b.usage.iterations == 3
        assert b.usage.model_calls == 3  # 1 per iteration
        assert b.status == RunBudgetStatus.COMPLETED

    def test_iteration_limit_blocks_before_execution(self):
        agent = _minimal_agent()
        b = RunBudget(RunBudgetLimits(max_iterations=2)).start()
        runner = IterativeAgentRunner(
            agent,
            checker=PredicateCompletionChecker(lambda h: False),  # never done
            max_iterations=10,
            run_budget=b,
        )
        result = runner.run("go")
        assert result.stop_reason == "budget_exhausted"
        assert result.termination_reason == TerminationReason.ITERATION_LIMIT
        # The 3rd iteration was blocked before running -> only 2 executed.
        assert result.iterations == 2
        assert b.usage.iterations == 2

    def test_model_call_limit_stops_loop_exactly(self):
        agent = _minimal_agent()
        b = RunBudget(RunBudgetLimits(max_model_calls=3)).start()
        runner = IterativeAgentRunner(
            agent,
            checker=PredicateCompletionChecker(lambda h: False),
            max_iterations=10,
            run_budget=b,
        )
        result = runner.run("go")
        assert result.stop_reason == "budget_exhausted"
        assert result.termination_reason == TerminationReason.MODEL_CALL_LIMIT
        assert b.usage.model_calls == 3


# ---------------------------------------------------------------------------
# No reset across invocations
# ---------------------------------------------------------------------------
class TestNoReset:
    def test_repeated_run_with_trace_never_resets(self):
        agent = _minimal_agent()
        b = RunBudget(RunBudgetLimits()).start()
        attach_run_budget(agent, b)
        agent.new_session()
        agent.run_with_trace("one")
        agent.run_with_trace("two")
        agent.run_with_trace("three")
        assert b.usage.model_calls == 3  # cumulative, not reset per call

    def test_budget_survives_multiple_runner_invocations(self):
        agent = _minimal_agent()
        b = RunBudget(RunBudgetLimits()).start()
        # Two separate runner.run() calls sharing ONE budget.
        r = IterativeAgentRunner(
            agent, checker=PredicateCompletionChecker(lambda h: len(h.steps) >= 2),
            max_iterations=5, run_budget=b,
        )
        r.run("first")
        assert b.usage.model_calls == 2
        r.run("second")
        # Still cumulative across the second invocation.
        assert b.usage.model_calls == 4


# ---------------------------------------------------------------------------
# Agent accounting / handoff sharing
# ---------------------------------------------------------------------------
class TestAgentAccounting:
    def _team(self):
        a = _minimal_agent("handing to b: write draft")
        bb = _minimal_agent("handing to a: research find")
        reg = AgentRegistry()
        reg.register("a", a, "A")
        reg.register("b", bb, "B")
        router = KeywordRouter(
            routes={"a": ["research", "find"], "b": ["write", "draft"]},
            default="a",
            done_markers=["__never__"],
        )
        return reg, router

    def test_agents_share_one_budget(self):
        reg, router = self._team()
        b = RunBudget(RunBudgetLimits(max_model_calls=3)).start()
        team = MultiAgentOrchestrator(reg, router, max_handoffs=10, run_budget=b)
        result = team.run("research this")
        assert result.stop_reason == "budget_exhausted"
        assert result.termination_reason == TerminationReason.MODEL_CALL_LIMIT
        # 3 model calls consumed across BOTH agents (1 per turn) -> 3 turns.
        assert b.usage.model_calls == 3
        assert len(result.turns) == 3

    def test_handoff_limit_blocks_before_switch(self):
        reg, router = self._team()
        # Plenty of model calls, but only 1 handoff allowed.
        b = RunBudget(RunBudgetLimits(max_handoffs=1)).start()
        team = MultiAgentOrchestrator(reg, router, max_handoffs=10, run_budget=b)
        result = team.run("research this")
        assert result.stop_reason == "budget_exhausted"
        assert result.termination_reason == TerminationReason.HANDOFF_LIMIT
        # 1 handoff reserved, the 2nd blocked before switching agents.
        assert b.usage.handoffs == 1
        assert len(result.handoffs) == 1


# ---------------------------------------------------------------------------
# Trace / snapshot validation
# ---------------------------------------------------------------------------
class TestTraceValidation:
    def test_remaining_decreases_across_timeline(self):
        agent = _minimal_agent()
        b = RunBudget(RunBudgetLimits(max_model_calls=10)).start()
        runner = IterativeAgentRunner(
            agent,
            checker=PredicateCompletionChecker(lambda h: len(h.steps) >= 3),
            max_iterations=5,
            run_budget=b,
        )
        result = runner.run("go")
        # One snapshot per executed iteration.
        assert len(result.budget_timeline) == 3
        remaining = [s["remaining"][BudgetDimension.MODEL_CALLS] for s in result.budget_timeline]
        assert remaining == sorted(remaining, reverse=True)  # monotonically decreasing
        assert remaining[-1] == 7  # 10 - 3

    def test_format_run_budget_renders(self):
        b = RunBudget(RunBudgetLimits(max_model_calls=2)).start()
        b.reserve(model_calls=1)
        text = format_run_budget(b)
        assert "RunBudget" in text
        assert "model_calls" in text


# ---------------------------------------------------------------------------
# Mixed workflow — the full spec scenario
# ---------------------------------------------------------------------------
class TestMixedWorkflow:
    def test_cumulative_across_iteration_tool_and_handoff(self):
        # Agent A iterates with a tool, then hands off to B which also runs.
        a = _tool_agent("collected facts; please write and draft summary")
        bb = _minimal_agent("final summary [final]")
        reg = AgentRegistry()
        reg.register("a", a, "researcher")
        reg.register("b", bb, "writer")
        router = KeywordRouter(
            routes={"a": ["research", "find"], "b": ["write", "draft"]},
            default="a",
            done_markers=["[final]"],
        )
        b = RunBudget(RunBudgetLimits(max_model_calls=50, max_tool_calls=50)).start()
        team = MultiAgentOrchestrator(reg, router, max_handoffs=4, run_budget=b)
        result = team.run("research renewable energy then write it up")

        # Cumulative accounting across the whole workflow.
        assert b.usage.model_calls >= 2          # at least one call per agent turn
        assert b.usage.tool_calls >= 1           # researcher executed its search
        assert b.usage.handoffs == len(result.handoffs)
        assert result.stop_reason in {"completed", "budget_exhausted"}
        # The budget object is the SAME one throughout (shared).
        assert result.run_budget is b

    def test_tool_call_limit_terminates(self):
        agent = _tool_agent()
        # Each iteration executes 1 governed action; cap tool calls at 2.
        b = RunBudget(RunBudgetLimits(max_tool_calls=2)).start()
        runner = IterativeAgentRunner(
            agent,
            checker=PredicateCompletionChecker(lambda h: False),
            max_iterations=10,
            run_budget=b,
        )
        result = runner.run("do work")
        assert result.stop_reason == "budget_exhausted"
        assert result.termination_reason == TerminationReason.TOOL_CALL_LIMIT
