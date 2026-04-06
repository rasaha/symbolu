#!/usr/bin/env python3
"""
Minimal Governed Agent
======================

The smallest useful example of the Agentic Framework.
Five lines to a governed agent with a custom tool.

What this shows:
    - build_agent() composes the full governed stack in one call
    - ToolSpec bundles a handler with its governance metadata
    - run_with_trace() returns a complete execution summary
    - No API key, no GPU, no configuration files

Run:
    python examples/minimal_governed_agent.py
"""

from agentic.agentic_framework.agent_builder import build_agent
from agentic.agentic_framework.llm_adapters import MockLLMAdapter
from agentic.agentic_framework.mcp_gateway import ToolSpec, ToolRiskLevel


def main():
    # A custom tool — any callable that takes a dict and returns a result
    def my_search(params):
        query = params.get("query", "")
        return {"results": [f"Top result for: {query}"], "count": 1}

    # Build a governed agent with one tool, in one call
    agent = build_agent(
        adapter=MockLLMAdapter(default_response="Python is a versatile programming language."),
        tools={
            "search": ToolSpec(
                handler=my_search,
                description="Search for information",
                risk_level=ToolRiskLevel.READ_ONLY,
            ),
        },
    )
    agent.new_session()

    # Run and get a full trace
    trace = agent.run_with_trace("Tell me about Python")

    print(f"Status:  {trace.status}")
    print(f"Events:  {trace.event_count}")
    print(f"Actions: {trace.actions_executed}")
    print(f"Tokens:  {trace.total_tokens} ({trace.accounting_mode})")


if __name__ == "__main__":
    main()
