#!/usr/bin/env python3
"""
Cumulative Run Budget (H11)
===========================

A single ``RunBudget`` created ONCE at the start of a workflow and shared,
unchanged, across everything the workflow does — iterations and agent
handoffs alike. Every model call, tool call, token and handoff is counted
cumulatively; nothing resets until the workflow completes.

This example shows both enforcement seams:

  1. An iterate-until-done loop bounded to N model calls — the loop stops
     the instant the shared budget is spent, before the next call runs.
  2. A multi-agent team sharing ONE budget — Agent A and Agent B draw from
     the same pool, so a handoff never buys fresh budget.

Deterministic status on exhaustion:  status = BUDGET_EXHAUSTED,
reason = MODEL_CALL_LIMIT (or ITERATION_LIMIT / HANDOFF_LIMIT / ...).

No API key, no GPU — mock adapters drive it deterministically.

Run:
    python examples/run_budget_workflow.py
"""

from agentic.agentic_framework import (
    build_agent,
    MockLLMAdapter,
    IterativeAgentRunner,
    PredicateCompletionChecker,
    AgentRegistry,
    KeywordRouter,
    MultiAgentOrchestrator,
    RunBudget,
    RunBudgetLimits,
    format_run_budget,
)
from agentic.agentic_framework.safety_contract import (
    SafetyGate,
    SafetyContractEvaluator,
)


def _open_gate():
    """Demo gate: always eligible (governance still runs each turn)."""
    return SafetyGate(SafetyContractEvaluator(0.0, 0.0, 1.0, 0.0))


def _agent(response):
    # Minimal config -> exactly ONE model call per governed turn, so the
    # budget arithmetic in this demo is easy to follow.
    agent = build_agent(
        adapter=MockLLMAdapter(default_response=response),
        use_llm_for_decomposition=False,
        max_revisions=0,
    )
    agent.safety_gate = _open_gate()
    return agent


def demo_iteration_budget():
    print("=" * 60)
    print("1. Iterate-until-done loop under a shared model-call budget")
    print("=" * 60)

    agent = _agent("working on it")
    # ONE budget for the whole loop: at most 3 model calls.
    budget = RunBudget(RunBudgetLimits(max_model_calls=3))

    runner = IterativeAgentRunner(
        agent,
        # A checker that never says "done" — only the budget can stop it.
        checker=PredicateCompletionChecker(lambda history: False),
        max_iterations=10,
        run_budget=budget,
    )
    result = runner.run("Keep researching indefinitely")

    print(f"\n  stop_reason:        {result.stop_reason}")
    print(f"  termination_reason: {result.termination_reason}")
    print(f"  iterations run:     {result.iterations}  (4th blocked before executing)")
    print(f"  model calls used:   {budget.usage.model_calls} / 3")
    print("\n  Per-iteration remaining model-call budget (executed steps):")
    for i, snap in enumerate(result.budget_timeline):
        print(f"    iter {i}: remaining = {snap['remaining']['model_calls']}")


def demo_handoff_budget():
    print("\n" + "=" * 60)
    print("2. Multi-agent handoff sharing ONE budget")
    print("=" * 60)

    # Two agents that keep bouncing to each other; only the shared budget
    # terminates the exchange.
    a = _agent("handing to b: please write the draft")
    b = _agent("handing to a: please research and find more")
    registry = AgentRegistry()
    registry.register("a", a, "Researcher")
    registry.register("b", b, "Writer")

    router = KeywordRouter(
        routes={"a": ["research", "find"], "b": ["write", "draft"]},
        default="a",
        done_markers=["__never__"],  # never self-complete; budget decides
    )

    # 5 model calls total, shared across A and B (1 call per turn here).
    budget = RunBudget(RunBudgetLimits(max_model_calls=5))
    team = MultiAgentOrchestrator(registry, router, max_handoffs=20, run_budget=budget)
    result = team.run("research this topic")

    print(f"\n  stop_reason:        {result.stop_reason}")
    print(f"  termination_reason: {result.termination_reason}")
    print(f"  handoff path:       {result.handoff_path()}")
    print(f"  turns taken:        {len(result.turns)}  (shared across both agents)")
    print(f"  model calls used:   {budget.usage.model_calls} / 5")
    print(f"  handoffs used:      {budget.usage.handoffs}")
    print("\n" + format_run_budget(budget))


def main():
    demo_iteration_budget()
    demo_handoff_budget()
    print(
        "\nKey property: in BOTH cases exactly one RunBudget existed for the\n"
        "entire workflow. Iterations and handoffs consumed from it "
        "cumulatively\nand never reset it — the run stops the moment the "
        "envelope is spent."
    )


if __name__ == "__main__":
    main()
