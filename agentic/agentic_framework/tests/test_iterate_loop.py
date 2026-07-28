"""
Tests for the iterate-until-done loop (governed re-planning).

Covers:
- Loop iterates and feeds tool observations back into the next step.
- Completion checkers (predicate, keyword, LLM) stop the loop.
- max_iterations is a hard, terminal bound.
- A shared budget across iterations terminates the loop.
- Observations are extracted from the governed action results.
"""

import json

import pytest

from agentic.agentic_framework import (
    build_agent,
    MockLLMAdapter,
    SequentialMockAdapter,
    ToolSpec,
    ToolRiskLevel,
    IterativeAgentRunner,
    run_until_done,
    LLMCompletionChecker,
    PredicateCompletionChecker,
    KeywordCompletionChecker,
    LoopHistory,
    Observation,
    BudgetPolicy,
)
from agentic.agentic_framework.safety_contract import (
    SafetyGate,
    SafetyContractEvaluator,
)


def _open_gate():
    """A gate whose evaluator always returns eligible.

    Governance still runs on every turn; the thresholds are simply set
    so the coherence-based pre-gate never blocks — keeps tool execution
    deterministic regardless of the mock's terse responses.
    """
    return SafetyGate(
        SafetyContractEvaluator(
            consistency_threshold=0.0,
            alignment_threshold=0.0,
            reversal_risk_threshold=1.0,
            stability_threshold=0.0,
        )
    )

# A decomposition JSON that maps to a single governed `search` tool call.
SEARCH_DECOMP = json.dumps(
    {
        "purpose": "research",
        "purpose_type": "task",
        "reasoning_strategy": "search then answer",
        "agency_level": "FULL",
        "actions": [
            {"description": "look it up", "type": "search", "parameters": {"query": "x"}}
        ],
    }
)


def _make_search_agent(default_response="Found it.", counter=None):
    """A governed agent whose decomposition triggers a `search` tool."""

    def search_tool(params):
        if counter is not None:
            counter["n"] += 1
        n = counter["n"] if counter is not None else 1
        return {"answer": f"fact #{n}"}

    agent = build_agent(
        adapter=MockLLMAdapter(
            responses={"extract structured goal information": SEARCH_DECOMP},
            default_response=default_response,
        ),
        tools={
            "search": ToolSpec(
                handler=search_tool,
                description="search",
                risk_level=ToolRiskLevel.READ_ONLY,
            )
        },
    )
    # Open turn-level gate so the read-only tool is eligible to run.
    agent.safety_gate = _open_gate()
    return agent


class TestLoopIteration:
    def test_loop_feeds_observations_and_completes(self):
        counter = {"n": 0}
        agent = _make_search_agent(counter=counter)
        # Controller: two CONTINUE decisions, then DONE.
        controller = SequentialMockAdapter(["CONTINUE: dig deeper", "CONTINUE: more", "DONE"])
        runner = IterativeAgentRunner(
            agent, checker=LLMCompletionChecker(controller), max_iterations=6
        )
        result = runner.run("Research topic")

        assert result.done is True
        assert result.stop_reason == "completed"
        assert result.iterations == 3
        # The tool was invoked once per iteration (results fed back each step).
        assert counter["n"] == 3
        # Each step captured a governed observation.
        for step in result.history.steps:
            assert step.observations
            assert step.observations[0].action_type == "search"
            assert step.observations[0].status == "completed"

    def test_continue_instruction_is_threaded_into_next_step(self):
        agent = _make_search_agent(counter={"n": 0})
        controller = SequentialMockAdapter(["CONTINUE: look at the population", "DONE"])
        runner = IterativeAgentRunner(
            agent, checker=LLMCompletionChecker(controller), max_iterations=4
        )
        result = runner.run("Research France")
        # Second step's instruction is the controller's CONTINUE remainder.
        assert result.history.steps[1].instruction == "look at the population"


class TestCompletionCheckers:
    def test_predicate_checker_stops_on_condition(self):
        counter = {"n": 0}
        agent = _make_search_agent(counter=counter)

        # Stop once two observations have been collected.
        checker = PredicateCompletionChecker(
            lambda hist: len(hist.all_observations()) >= 2
        )
        result = run_until_done(agent, "Research topic", checker=checker, max_iterations=6)
        assert result.done is True
        assert result.iterations == 2

    def test_keyword_checker_stops_on_marker(self):
        # Agent response itself signals completion with a [DONE] marker.
        agent = _make_search_agent(default_response="All set here [DONE]")
        checker = KeywordCompletionChecker(done_markers=["[done]"])
        result = run_until_done(agent, "Research topic", checker=checker, max_iterations=5)
        assert result.done is True
        assert result.iterations == 1


class TestBounds:
    def test_max_iterations_is_terminal(self):
        agent = _make_search_agent(counter={"n": 0})
        # Controller never says DONE.
        controller = SequentialMockAdapter(["CONTINUE: keep going"] * 50)
        runner = IterativeAgentRunner(
            agent, checker=LLMCompletionChecker(controller), max_iterations=3
        )
        result = runner.run("Endless task")
        assert result.done is False
        assert result.stop_reason == "max_iterations"
        assert result.iterations == 3

    def test_invalid_max_iterations_rejected(self):
        agent = _make_search_agent()
        with pytest.raises(ValueError):
            IterativeAgentRunner(agent, max_iterations=0)

    def test_shared_budget_terminates_loop(self):
        agent = _make_search_agent(counter={"n": 0})
        controller = SequentialMockAdapter(["CONTINUE: again"] * 50)
        # A tiny token budget should trip BUDGET_EXCEEDED within a couple steps.
        budget = BudgetPolicy(max_total_tokens=1)
        runner = IterativeAgentRunner(
            agent,
            checker=LLMCompletionChecker(controller),
            max_iterations=10,
            budget_policy=budget,
        )
        result = runner.run("Costly task")
        assert result.stop_reason == "budget_exceeded"
        assert result.done is False
        # Terminated well before the iteration cap.
        assert result.iterations < 10


class TestObservationRendering:
    def test_history_renders_observations(self):
        hist = LoopHistory(goal="g")
        assert hist.render_observations() == "(no tool results yet)"

    def test_observation_render_completed_and_blocked(self):
        ok = Observation("search", "find x", "completed", result={"a": 1})
        bad = Observation("write", "save", "blocked", error="denied")
        assert "->" in ok.render()
        assert "blocked" in bad.render()
