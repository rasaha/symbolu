#!/usr/bin/env python3
"""
First Governed Agent — Canonical Starter Example
=================================================

Demonstrates the shortest path to a governed agent using the Agentic
Framework. Uses the stub CG adapter (no API key, no GPU) so it runs
anywhere.

What this shows:
    1. Composing a governed agent via build_cg_mcp_agent()
    2. Streaming lifecycle events from run_stream()
    3. Building a trace and inspecting the summary
    4. Discovering registered tools via ToolCatalog

Run:
    python examples/first_governed_agent.py
"""

from agentic.agentic_framework import (
    GENERATION_COMPLETED,
    ACTION_STARTED,
    ACTION_COMPLETED,
    RUN_COMPLETED,
    SAFETY_GATE_RESULT,
    USAGE_UPDATED,
    ToolCatalog,
    TraceCollector,
)
# CG-specific imports — not in the top-level package
from agentic.agentic_framework.cg_tool_dispatcher import build_cg_mcp_agent
from agentic.agentic_framework.llm_adapters import StubCGLLMAdapter


def main():
    # ---------------------------------------------------------------
    # 1. Compose the governed agent
    # ---------------------------------------------------------------
    # StubCGLLMAdapter generates a fixed response + deterministic 32D
    # sovereign state. build_cg_mcp_agent wires it into:
    #   adapter -> CGToolDispatcher -> SafeMCPGateway
    # with SafetyGate as the turn-level pre-gate.
    adapter = StubCGLLMAdapter(
        default_response=(
            "Quantum computing uses qubits that can exist in superposition, "
            "enabling parallel computation across exponentially many states."
        ),
    )
    agent = build_cg_mcp_agent(adapter=adapter, allow_stub=True)
    agent.new_session()

    print("=" * 60)
    print("First Governed Agent")
    print("=" * 60)

    # ---------------------------------------------------------------
    # 2. Stream events and build a trace
    # ---------------------------------------------------------------
    collector = TraceCollector()
    query = "Search for quantum computing"

    print(f"\nQuery: {query}")
    print("-" * 60)

    for event in agent.run_stream(query, trace_collector=collector):
        et = event.event_type

        if et == GENERATION_COMPLETED:
            resp = event.payload.get("response", "")
            print(f"[generation] {resp[:80]}...")

        elif et == SAFETY_GATE_RESULT:
            eligible = event.payload.get("eligible", False)
            print(f"[safety]     eligible={eligible}")

        elif et == ACTION_STARTED:
            print(f"[action]     started: {event.payload.get('action_type')}")

        elif et == ACTION_COMPLETED:
            print(f"[action]     completed: {event.payload.get('action_type')}")

        elif et == USAGE_UPDATED:
            tokens = event.payload.get("total_tokens", 0)
            mode = event.payload.get("accounting_mode", "unknown")
            print(f"[usage]      {tokens} tokens ({mode})")

        elif et == RUN_COMPLETED:
            print("[run]        completed")

    # ---------------------------------------------------------------
    # 3. Inspect the trace
    # ---------------------------------------------------------------
    trace = collector.build_trace()

    print("\n" + "-" * 60)
    print("Trace Summary")
    print("-" * 60)
    print(f"  Status:           {trace.status}")
    print(f"  Events:           {trace.event_count}")
    print(f"  Actions executed: {trace.actions_executed}")
    print(f"  Safety blocked:   {trace.safety_blocked}")
    print(f"  Total tokens:     {trace.total_tokens}")
    print(f"  Accounting mode:  {trace.accounting_mode}")

    # ---------------------------------------------------------------
    # 4. Discover registered tools
    # ---------------------------------------------------------------
    catalog = ToolCatalog.from_agent(agent)

    print(f"\nRegistered tools ({len(catalog)}):")
    for tool in catalog.list_tools():
        print(f"  - {tool.name} [{tool.risk_level}]: {tool.description}")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
