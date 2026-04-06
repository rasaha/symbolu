#!/usr/bin/env python3
"""
Governed Agent with Approvals, Budget, and Structured Output
============================================================

Demonstrates runtime primitives working together:
    1. Approval gates — require human sign-off before actions
    2. Budget policy — hard cap on token usage
    3. Structured output — schema-enforced responses
    4. Tracing — full run summary with approval/budget counters

Uses mock/stub adapters (no API key needed). All approval callbacks
are automated for demo purposes.

Run:
    python examples/governed_agent_with_approval_and_budget.py
"""

import json
from dataclasses import dataclass

from agentic.agentic_framework import AgenticLLMWrapper
from agentic.agentic_framework.approval import (
    ApprovalController,
    ApprovalPolicy,
    ApprovalResponse,
)
from agentic.agentic_framework.cg_tool_dispatcher import build_cg_mcp_agent
from agentic.agentic_framework.llm_adapters import (
    MockLLMAdapter,
    SequentialMockAdapter,
)
from agentic.agentic_framework.streaming_events import (
    ACTION_COMPLETED,
    ACTION_STARTED,
    APPROVAL_REQUESTED,
    APPROVAL_RESOLVED,
    BUDGET_EXCEEDED,
    RUN_COMPLETED,
    USAGE_UPDATED,
)
from agentic.agentic_framework.token_budget import BudgetPolicy
from agentic.agentic_framework.tracing import TraceCollector


# ---------------------------------------------------------------
# Schema for structured output
# ---------------------------------------------------------------

@dataclass
class CityInfo:
    name: str
    country: str
    population: int


# ---------------------------------------------------------------
# Approval callbacks
# ---------------------------------------------------------------

def auto_approve(pending):
    """Auto-approve and print what was requested."""
    print(f"  [approval] Requested: {pending.action_type} — {pending.description}")
    print(f"  [approval] Auto-approved")
    return ApprovalResponse(approved=True, reason="auto-approved for demo")


def auto_deny(pending):
    """Auto-deny and print what was requested."""
    print(f"  [approval] Requested: {pending.action_type} — {pending.description}")
    print(f"  [approval] DENIED")
    return ApprovalResponse(approved=False, reason="denied for demo")


def _make_search_agent():
    """Build a governed agent whose goal decomposer produces a 'search'
    action, which maps to a real MCP tool and thus triggers the approval
    gate and dispatcher."""
    # Goal decomposition JSON that produces a "search" action
    decomp_json = json.dumps({
        "purpose": "Search for quantum computing",
        "purpose_type": "informational",
        "reasoning_strategy": "Search and summarize",
        "reasoning_steps": ["Search", "Summarize"],
        "agency_level": "FULL",
        "actions": [{
            "description": "Search for quantum computing information",
            "type": "search",
            "parameters": {"query": "quantum computing"},
        }],
        "complexity": 0.3,
    })

    # Sequential responses: decomposition, generation, critic, revision...
    adapter = SequentialMockAdapter([
        decomp_json,
        "Quantum computing uses qubits for parallel computation.",
        json.dumps({"quality_score": 0.95, "feedback": "Clear and accurate."}),
    ], loop=True)

    # Make the adapter CG-compatible so build_cg_mcp_agent accepts it
    adapter.last_cg_metadata = {}
    adapter.IS_STUB = True

    agent = build_cg_mcp_agent(adapter=adapter, allow_stub=True)
    agent.new_session()
    return agent


def main():
    # ---------------------------------------------------------------
    # Part 1: Approval-gated run (approved)
    # ---------------------------------------------------------------
    print("=" * 60)
    print("Part 1: Approval Gate — Approved")
    print("=" * 60)

    agent = _make_search_agent()
    policy = ApprovalPolicy(require_all=True)
    ctrl = ApprovalController(policy=policy, callback=auto_approve)
    budget = BudgetPolicy(max_total_tokens=5000)
    collector = TraceCollector()

    print(f"\nQuery: Search for quantum computing")
    print(f"Budget: max {budget.max_total_tokens} tokens")
    print(f"Approval: required for all actions (auto-approve)")
    print("-" * 60)

    for event in agent.run_stream(
        "Search for quantum computing",
        approval_controller=ctrl,
        budget_policy=budget,
        trace_collector=collector,
    ):
        et = event.event_type
        if et == APPROVAL_RESOLVED:
            print(f"  [resolved] approved={event.payload.get('approved')}")
        elif et == ACTION_STARTED:
            print(f"  [action]   started: {event.payload.get('action_type')}")
        elif et == ACTION_COMPLETED:
            print(f"  [action]   completed: {event.payload.get('status')}")
        elif et == USAGE_UPDATED:
            print(f"  [usage]    {event.payload.get('total_tokens')} tokens")
        elif et == RUN_COMPLETED:
            print(f"  [run]      completed")

    trace = collector.build_trace()
    print(f"\nTrace:")
    print(f"  Status:              {trace.status}")
    print(f"  Approvals requested: {trace.approvals_requested}")
    print(f"  Approvals denied:    {trace.approvals_denied}")
    print(f"  Actions executed:    {trace.actions_executed}")
    print(f"  Budget exceeded:     {trace.budget_exceeded}")
    print(f"  Total tokens:        {trace.total_tokens}")

    # ---------------------------------------------------------------
    # Part 2: Approval-gated run (denied)
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Part 2: Approval Gate — Denied")
    print("=" * 60)

    agent2 = _make_search_agent()
    ctrl_deny = ApprovalController(policy=policy, callback=auto_deny)
    collector2 = TraceCollector()

    print(f"\nQuery: Search for quantum computing")
    print(f"Approval: required for all actions (auto-deny)")
    print("-" * 60)

    for event in agent2.run_stream(
        "Search for quantum computing",
        approval_controller=ctrl_deny,
        trace_collector=collector2,
    ):
        et = event.event_type
        if et == APPROVAL_RESOLVED:
            print(f"  [resolved] approved={event.payload.get('approved')}")
        elif et == ACTION_COMPLETED:
            status = event.payload.get("status")
            print(f"  [action]   {status}: {event.payload.get('error', '')}")
        elif et == RUN_COMPLETED:
            print(f"  [run]      completed")

    trace2 = collector2.build_trace()
    print(f"\nTrace:")
    print(f"  Status:              {trace2.status}")
    print(f"  Approvals requested: {trace2.approvals_requested}")
    print(f"  Approvals denied:    {trace2.approvals_denied}")
    print(f"  Actions executed:    {trace2.actions_executed}")

    # ---------------------------------------------------------------
    # Part 3: Structured output with trace
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Part 3: Structured Output + Trace")
    print("=" * 60)

    llm = MockLLMAdapter(
        default_response=(
            '```json\n'
            '{"name": "Paris", "country": "France", "population": 2161000}\n'
            '```'
        ),
    )
    agent3 = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
    agent3.new_session()

    result, trace3 = agent3.run_structured_with_trace(
        "What is the capital of France?",
        schema=CityInfo,
        budget_policy=BudgetPolicy(max_total_tokens=10000),
    )

    print(f"\nStructured result:")
    print(f"  Success:    {result.success}")
    print(f"  Schema:     {result.schema_name}")
    if result.success:
        city = result.parsed_output
        print(f"  Name:       {city.name}")
        print(f"  Country:    {city.country}")
        print(f"  Population: {city.population:,}")
    else:
        print(f"  Error:      {result.validation_error}")

    print(f"\nTrace:")
    print(f"  Status:         {trace3.status}")
    print(f"  Events:         {trace3.event_count}")
    print(f"  Total tokens:   {trace3.total_tokens}")
    print(f"  Budget exceeded:{trace3.budget_exceeded}")

    # ---------------------------------------------------------------
    # Part 4: Budget-exceeded scenario
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Part 4: Budget Exceeded")
    print("=" * 60)

    agent4 = _make_search_agent()
    trace4 = agent4.run_with_trace(
        "Search for quantum computing",
        budget_policy=BudgetPolicy(max_total_tokens=1),
    )

    print(f"\nTrace (budget=1 token):")
    print(f"  Status:         {trace4.status}")
    print(f"  Budget exceeded:{trace4.budget_exceeded}")
    print(f"  Total tokens:   {trace4.total_tokens}")
    print(f"  Actions:        {trace4.actions_executed}")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
