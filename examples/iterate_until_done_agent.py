#!/usr/bin/env python3
"""
Iterate-Until-Done Agent
========================

The base agent runs ONE governed turn: decompose -> generate -> gate ->
execute. It does not feed tool results back into the model to decide the
next step.

This example adds that missing **re-planning loop** with
``IterativeAgentRunner`` — while keeping governance on every step:

    observe (run a governed turn) -> decide (is the goal done?) -> act

Each iteration is a full ``run_with_trace()`` call, so safety gating,
budgets and tracing still apply. Between iterations the tool observations
are fed back and an LLM *controller* decides DONE vs CONTINUE (and what the
next step should be). Two hard bounds keep it safe:

    * max_iterations — a terminal cap
    * an optional shared BudgetPolicy across all iterations

No API key, no GPU — mock adapters drive the whole thing deterministically.

Run:
    python examples/iterate_until_done_agent.py
"""

import json

from agentic.agentic_framework import (
    build_agent,
    MockLLMAdapter,
    SequentialMockAdapter,
    ToolSpec,
    ToolRiskLevel,
    IterativeAgentRunner,
    LLMCompletionChecker,
)
from agentic.agentic_framework.safety_contract import (
    SafetyGate,
    SafetyContractEvaluator,
)

# A decomposition the mock returns whenever it is asked to decompose a
# goal. It maps to a single governed `search` tool call. (Keyed on a
# phrase unique to the decomposition prompt, so ordinary generation
# prompts fall through to the prose default_response.)
SEARCH_DECOMPOSITION = json.dumps(
    {
        "purpose": "research the question",
        "purpose_type": "task",
        "reasoning_strategy": "search, then decide if more is needed",
        "agency_level": "FULL",
        "actions": [
            {
                "description": "search for the next fact",
                "type": "search",
                "parameters": {"query": "renewable energy"},
            }
        ],
    }
)


def build_research_agent():
    """A governed agent with a search tool that returns a fresh fact each call."""
    facts = [
        "Solar and wind are the fastest-growing energy sources.",
        "Battery storage costs fell ~90% over the last decade.",
        "Grid integration is now the main bottleneck.",
    ]
    state = {"i": 0}

    def search(params):
        fact = facts[min(state["i"], len(facts) - 1)]
        state["i"] += 1
        return {"query": params.get("query"), "fact": fact}

    agent = build_agent(
        adapter=MockLLMAdapter(
            responses={"extract structured goal information": SEARCH_DECOMPOSITION},
            default_response="Here is my current understanding of the topic.",
        ),
        tools={
            "search": ToolSpec(
                handler=search,
                description="Search for one fact about the topic",
                risk_level=ToolRiskLevel.READ_ONLY,
            )
        },
    )
    # Demo configuration: an open turn-level gate so the read-only tool is
    # always eligible. Governance still runs every turn — real deployments
    # keep stricter thresholds (see create_default_evaluator()).
    agent.safety_gate = SafetyGate(
        SafetyContractEvaluator(
            consistency_threshold=0.0,
            alignment_threshold=0.0,
            reversal_risk_threshold=1.0,
            stability_threshold=0.0,
        )
    )
    return agent


def main():
    agent = build_research_agent()

    # The "controller" is what makes this autonomous: it sees the tool
    # results so far and decides whether to CONTINUE (with the next step)
    # or stop with DONE. Here a scripted mock plays that role so the demo
    # is deterministic; swap in an OpenAIAdapter/AnthropicAdapter and the
    # model makes this call for real — no other change.
    controller = SequentialMockAdapter(
        [
            "CONTINUE: find the cost trend",
            "CONTINUE: find the main obstacle",
            "DONE",
        ]
    )

    def show_step(step):
        obs = step.observations[0].render() if step.observations else "(no tool result)"
        print(f"  iter {step.iteration}: instruction={step.instruction!r}")
        print(f"          observation: {obs}")

    runner = IterativeAgentRunner(
        agent,
        checker=LLMCompletionChecker(controller),
        max_iterations=6,     # hard safety cap
        on_step=show_step,
    )

    print("Goal: Research renewable energy until the picture is complete.\n")
    result = runner.run("Research renewable energy trends")

    print("\n--- Loop result ---")
    print(f"  done:        {result.done}")
    print(f"  stop reason: {result.stop_reason}")
    print(f"  iterations:  {result.iterations}")
    print(f"  tool calls:  {sum(len(s.observations) for s in result.history.steps)}")
    print(f"  tokens used: {result.total_tokens}")
    print("\n  Facts gathered across the loop:")
    for obs in result.history.all_observations():
        fact = obs.result.get("fact") if isinstance(obs.result, dict) else obs.result
        print(f"    - {fact}")

    print("\nContrast: a single agent.run() would have made exactly ONE of "
          "these\nsearches and stopped. The loop re-planned until the "
          "controller said DONE.")


if __name__ == "__main__":
    main()
