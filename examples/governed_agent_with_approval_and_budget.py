#!/usr/bin/env python3
"""
Governed Agent with Approvals, Budget, and Structured Output
============================================================

Demonstrates runtime primitives working together:
    1. Approval gates — require human sign-off before actions
    2. Budget policy — hard cap on token usage
    3. Structured output — schema-enforced responses
    4. Tracing — full run summary with approval/budget counters

Uses a mock adapter (no API key needed). All approval callbacks
are automated for demo purposes.

Run:
    python examples/governed_agent_with_approval_and_budget.py
"""

from dataclasses import dataclass

from agentic.agentic_framework import AgenticLLMWrapper
from agentic.agentic_framework.approval import (
    ApprovalController,
    ApprovalPolicy,
    ApprovalResponse,
)
from agentic.agentic_framework.llm_adapters import MockLLMAdapter
from agentic.agentic_framework.streaming_events import (
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
# Approval callback — auto-approve with logging
# ---------------------------------------------------------------

def approval_callback(pending):
    """In a real application, this would prompt a human.
    Here we auto-approve and print what was requested."""
    print(f"  [approval] Requested: {pending.action_type} — {pending.description}")
    print(f"  [approval] Approved automatically")
    return ApprovalResponse(approved=True, reason="auto-approved for demo")


def main():
    # ---------------------------------------------------------------
    # Setup
    # ---------------------------------------------------------------
    # Mock adapter that returns a JSON response matching CityInfo
    llm = MockLLMAdapter(
        default_response=(
            'Based on my knowledge, here is the information:\n'
            '```json\n'
            '{"name": "Paris", "country": "France", "population": 2161000}\n'
            '```'
        ),
    )
    agent = AgenticLLMWrapper(llm, use_llm_for_decomposition=False)
    agent.new_session()

    # ---------------------------------------------------------------
    # Part 1: Approval-gated run with budget
    # ---------------------------------------------------------------
    print("=" * 60)
    print("Part 1: Approval + Budget")
    print("=" * 60)

    policy = ApprovalPolicy(require_all=True)
    ctrl = ApprovalController(policy=policy, callback=approval_callback)
    budget = BudgetPolicy(max_total_tokens=5000)

    collector = TraceCollector()

    print(f"\nQuery: Search for quantum computing")
    print(f"Budget: max {budget.max_total_tokens} tokens")
    print(f"Approval: required for all actions")
    print("-" * 60)

    for event in agent.run_stream(
        "Search for quantum computing",
        approval_controller=ctrl,
        budget_policy=budget,
        trace_collector=collector,
    ):
        et = event.event_type
        if et == APPROVAL_REQUESTED:
            pass  # handled by callback print
        elif et == APPROVAL_RESOLVED:
            approved = event.payload.get("approved", False)
            print(f"  [resolved] approved={approved}")
        elif et == USAGE_UPDATED:
            print(f"  [usage]    {event.payload.get('total_tokens')} tokens")
        elif et == BUDGET_EXCEEDED:
            print(f"  [budget]   EXCEEDED: {event.payload.get('reason')}")
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
    # Part 2: Structured output with trace
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Part 2: Structured Output + Trace")
    print("=" * 60)

    result, trace2 = agent.run_structured_with_trace(
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
    print(f"  Status:         {trace2.status}")
    print(f"  Events:         {trace2.event_count}")
    print(f"  Total tokens:   {trace2.total_tokens}")
    print(f"  Budget exceeded:{trace2.budget_exceeded}")

    # ---------------------------------------------------------------
    # Part 3: Budget-exceeded scenario
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Part 3: Budget Exceeded")
    print("=" * 60)

    tiny_budget = BudgetPolicy(max_total_tokens=1)

    trace3 = agent.run_with_trace(
        "This will exceed the budget immediately",
        budget_policy=tiny_budget,
    )

    print(f"\nTrace (budget=1 token):")
    print(f"  Status:         {trace3.status}")
    print(f"  Budget exceeded:{trace3.budget_exceeded}")
    print(f"  Total tokens:   {trace3.total_tokens}")
    print(f"  Actions:        {trace3.actions_executed}")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
