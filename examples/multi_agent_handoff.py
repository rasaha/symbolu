#!/usr/bin/env python3
"""
Multi-Agent Handoff
===================

The base framework governs a SINGLE agent — no agent-to-agent handoff.

This example composes three governed agents into a team and lets a router
hand control from one specialist to the next:

    researcher (has a search tool)  ->  writer  ->  reviewer

Each agent keeps its OWN governed pipeline (its own tools, safety gate,
memory and trace). The ``MultiAgentOrchestrator`` only decides who runs
next and threads context across the handoffs — it never bypasses any
agent's governance. ``max_handoffs`` bounds the whole run.

Routing here is a deterministic ``KeywordRouter`` (no API key needed): an
agent "requests" the next specialist by mentioning its keywords, and the
final agent ends with a ``[final]`` marker. Swap in ``LLMRouter`` to let a
supervisor model orchestrate instead.

Run:
    python examples/multi_agent_handoff.py
"""

import json

from agentic.agentic_framework import (
    build_agent,
    MockLLMAdapter,
    ToolSpec,
    ToolRiskLevel,
    AgentRegistry,
    KeywordRouter,
    MultiAgentOrchestrator,
)
from agentic.agentic_framework.safety_contract import (
    SafetyGate,
    SafetyContractEvaluator,
)

SEARCH_DECOMPOSITION = json.dumps(
    {
        "purpose": "gather facts",
        "purpose_type": "task",
        "reasoning_strategy": "search",
        "agency_level": "FULL",
        "actions": [
            {
                "description": "search the knowledge base",
                "type": "search",
                "parameters": {"query": "renewable energy"},
            }
        ],
    }
)


def _open_gate():
    """Demo gate: always eligible (governance still runs each turn)."""
    return SafetyGate(
        SafetyContractEvaluator(
            consistency_threshold=0.0,
            alignment_threshold=0.0,
            reversal_risk_threshold=1.0,
            stability_threshold=0.0,
        )
    )


def _make_agent(default_response, responses=None, tools=None):
    agent = build_agent(
        adapter=MockLLMAdapter(responses=responses or {}, default_response=default_response),
        tools=tools or {},
    )
    agent.safety_gate = _open_gate()
    return agent


def build_team():
    # 1. Researcher — has a governed search tool, then asks the writer to
    #    draft (its response mentions the writer's keywords -> handoff).
    researcher = _make_agent(
        default_response=(
            "I gathered the key facts on solar, wind and storage. "
            "Please write and draft a summary from them."
        ),
        responses={"extract structured goal information": SEARCH_DECOMPOSITION},
        tools={
            "search": ToolSpec(
                handler=lambda p: {"facts": ["solar", "wind", "storage"]},
                description="Search the knowledge base",
                risk_level=ToolRiskLevel.READ_ONLY,
            )
        },
    )

    # 2. Writer — drafts prose, then asks the reviewer to check it.
    writer = _make_agent(
        default_response=(
            "Draft: Renewable energy is led by solar and wind, backed by "
            "cheap storage. Please review and check this for accuracy."
        ),
    )

    # 3. Reviewer — signs off with the [final] completion marker.
    reviewer = _make_agent(
        default_response="Reviewed — accurate and clear. Approved. [final]",
    )

    registry = AgentRegistry()
    registry.register("researcher", researcher, "Finds facts with a search tool")
    registry.register("writer", writer, "Writes a prose summary from facts")
    registry.register("reviewer", reviewer, "Reviews and approves the summary")
    return registry


def main():
    registry = build_team()

    # An agent triggers the next by mentioning its keywords; the reviewer
    # ends with [final]. Deterministic, no API key.
    router = KeywordRouter(
        routes={
            "researcher": ["research", "find", "gather facts"],
            "writer": ["write", "draft"],
            "reviewer": ["review", "check", "approve"],
        },
        default="researcher",
        done_markers=["[final]"],
    )

    team = MultiAgentOrchestrator(registry, router, max_handoffs=4)

    query = "Research renewable energy and produce a reviewed summary"
    print(f"Query: {query}\n")
    result = team.run(query)

    print("--- Orchestration transcript ---")
    for i, turn in enumerate(result.turns):
        print(f"  [{i}] {turn.agent_name} (actions_executed={turn.actions_executed})")
        print(f"      {turn.response}")

    print("\n--- Handoffs ---")
    for h in result.handoffs:
        print(f"  {h.from_agent} -> {h.to_agent}  ({h.reason})")

    print("\n--- Result ---")
    print(f"  path:        {result.handoff_path()}")
    print(f"  final agent: {result.final_agent}")
    print(f"  stop reason: {result.stop_reason}")
    print(f"  final:       {result.final_response}")


if __name__ == "__main__":
    main()
