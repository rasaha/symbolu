#!/usr/bin/env python3
"""
Pilot: Governed Research Assistant
===================================

First real adoption use case for the Agentic Framework.

This pilot builds a research assistant that takes a question,
decomposes it into governed tool calls (search, compute, validate),
produces a structured answer, and reports a full execution trace —
all under budget control and with approval gates on write-risk tools.

What this exercises:
    - Custom tool handlers on MockMCPClient (not just stubs)
    - LLM-driven goal decomposition into governed actions
    - Per-tool risk classification and governance gating
    - Human-in-the-loop approval for write-risk operations
    - Budget enforcement (token + cost caps)
    - Structured output (dataclass schema)
    - Full tracing with post-run summary
    - Tool discovery / catalog inspection

What is real vs simulated:
    - The governance pipeline is real: SafetyGate, SafeMCPGateway,
      risk classification, confidence gating, audit logging.
    - Tool handlers are domain-appropriate simulations (return
      realistic research data, not "computed" stubs).
    - The LLM is a SequentialMockAdapter that returns pre-scripted
      responses matching a research workflow.
    - In production, replace the adapter with OpenAIAdapter or
      AnthropicAdapter — no other wiring changes needed.

Run:
    python examples/pilot_research_assistant.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from agentic.agentic_framework.approval import (
    ApprovalController,
    ApprovalPolicy,
    ApprovalResponse,
    PendingApproval,
)
from agentic.agentic_framework.cg_tool_dispatcher import CGToolDispatcher
from agentic.agentic_framework.llm_adapters import SequentialMockAdapter
from agentic.agentic_framework.mcp_gateway import (
    MCPToolDefinition,
    MockMCPClient,
    SafeMCPGateway,
    ToolRiskLevel,
    create_safe_mcp_gateway,
)
from agentic.agentic_framework.streaming_events import (
    ACTION_COMPLETED,
    ACTION_STARTED,
    APPROVAL_REQUESTED,
    APPROVAL_RESOLVED,
    BUDGET_EXCEEDED,
    GENERATION_COMPLETED,
    RUN_COMPLETED,
    RUN_ERROR,
    SAFETY_GATE_RESULT,
    USAGE_UPDATED,
)
from agentic.agentic_framework.token_budget import BudgetPolicy
from agentic.agentic_framework.tool_discovery import ToolCatalog
from agentic.agentic_framework.tracing import TraceCollector


# =====================================================================
# Structured output schema
# =====================================================================

@dataclass
class ResearchAnswer:
    question: str
    summary: str
    confidence: str  # "high", "medium", "low"
    sources_consulted: int
    key_finding: str


# =====================================================================
# Custom tool handlers — domain-appropriate research simulations
# =====================================================================

def research_search(params: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate a research search returning domain-relevant results."""
    query = params.get("query", "")
    return {
        "results": [
            {
                "title": f"Survey: {query}",
                "snippet": (
                    f"Recent advances in {query} show promising results "
                    "across multiple benchmarks. Key findings include "
                    "improved efficiency and novel architectural approaches."
                ),
                "source": "arxiv.org",
                "relevance": 0.92,
            },
            {
                "title": f"Applications of {query}",
                "snippet": (
                    f"Practical applications of {query} have expanded "
                    "significantly, with industry adoption growing 40% "
                    "year-over-year."
                ),
                "source": "scholar.google.com",
                "relevance": 0.87,
            },
        ],
        "total_results": 2,
        "query": query,
    }


def research_compute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate a computation (e.g., statistical analysis, aggregation)."""
    operation = params.get("operation", "analyze")
    data = params.get("data", {})
    return {
        "operation": operation,
        "result": {
            "mean_relevance": 0.895,
            "source_count": 2,
            "confidence_interval": [0.82, 0.97],
        },
        "status": "completed",
    }


def research_validate(params: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate validation of research findings."""
    claim = params.get("claim", "")
    return {
        "claim": claim,
        "valid": True,
        "consistency_score": 0.91,
        "cross_reference_count": 3,
        "notes": "Findings consistent across multiple sources.",
    }


def save_report(params: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate saving a research report (write-risk operation)."""
    path = params.get("path", "/tmp/report.json")
    return {
        "saved": True,
        "path": path,
        "size_bytes": 2048,
    }


# =====================================================================
# Gateway factory — custom tools with appropriate risk classification
# =====================================================================

def build_research_gateway() -> SafeMCPGateway:
    """Build a gateway with research-specific tools and risk levels."""
    client = MockMCPClient()

    # Read-only research tools
    client.register_tool("search", research_search, ToolRiskLevel.READ_ONLY)
    client.register_tool("compute", research_compute, ToolRiskLevel.READ_ONLY)
    client.register_tool("validate", research_validate, ToolRiskLevel.READ_ONLY)

    # Write-risk tool (will require approval)
    client.register_tool("save_report", save_report, ToolRiskLevel.WRITE)

    gateway = create_safe_mcp_gateway(mcp_client=client, audit_enabled=True)

    # Register detailed metadata for risk classification
    gateway.register_tool(MCPToolDefinition(
        name="search",
        description="Search academic databases for research papers and findings",
        risk_level=ToolRiskLevel.READ_ONLY,
        capabilities=["research", "information_retrieval"],
        min_confidence=0.3,
        requires_confirmation=False,
    ))
    gateway.register_tool(MCPToolDefinition(
        name="compute",
        description="Run statistical analysis on research data",
        risk_level=ToolRiskLevel.READ_ONLY,
        capabilities=["analysis", "computation"],
        min_confidence=0.3,
        requires_confirmation=False,
    ))
    gateway.register_tool(MCPToolDefinition(
        name="validate",
        description="Cross-reference and validate research findings",
        risk_level=ToolRiskLevel.READ_ONLY,
        capabilities=["validation", "quality_check"],
        min_confidence=0.3,
        requires_confirmation=False,
    ))
    gateway.register_tool(MCPToolDefinition(
        name="save_report",
        description="Save research report to persistent storage",
        risk_level=ToolRiskLevel.WRITE,
        capabilities=["persistence", "reporting"],
        min_confidence=0.5,
        requires_confirmation=True,
    ))

    return gateway


# =====================================================================
# LLM response scripting for a research workflow
# =====================================================================

def build_research_adapter(question: str):
    """Build a SequentialMockAdapter scripted for a research workflow.

    The adapter returns pre-scripted responses in sequence:
    1. Goal decomposition → "search" action
    2. Generation → research narrative
    3. Critic → quality assessment
    (looped for any additional calls)
    """
    # Goal decomposition: produce a "search" action
    decomposition = json.dumps({
        "purpose": f"Research: {question}",
        "purpose_type": "analysis",
        "reasoning_strategy": "Search, analyze, synthesize",
        "reasoning_steps": [
            "Search for relevant literature",
            "Analyze and cross-reference findings",
            "Synthesize into a concise answer",
        ],
        "agency_level": "FULL",
        "actions": [
            {
                "description": f"Search for {question}",
                "type": "search",
                "parameters": {"query": question},
            },
        ],
        "complexity": 0.5,
    })

    # Generation: the research assistant's narrative response
    generation = (
        f"Based on my research into {question}, recent surveys show "
        "promising advances across multiple benchmarks. Key findings "
        "include improved efficiency (40% year-over-year industry "
        "adoption growth) and novel architectural approaches. The "
        "evidence is consistent across multiple sources with a mean "
        "relevance score of 0.895 and high cross-reference consistency."
    )

    # Critic: quality assessment
    critic = json.dumps({
        "quality_score": 0.92,
        "feedback": "Well-researched response with specific data points.",
    })

    adapter = SequentialMockAdapter(
        [decomposition, generation, critic],
        loop=True,
    )

    # Make adapter CG-compatible for CGToolDispatcher
    adapter.last_cg_metadata = {}
    adapter.IS_STUB = True

    return adapter


# =====================================================================
# Approval callback
# =====================================================================

approval_log: list = []


def research_approval_callback(pending: PendingApproval) -> ApprovalResponse:
    """Approval callback that auto-approves read-only but logs all requests.

    In production, this would prompt a human. For this pilot, write-risk
    actions are auto-denied to demonstrate the denial path.
    """
    entry = {
        "action_type": pending.action_type,
        "description": pending.description,
    }

    # Deny write operations to demonstrate the denial path
    if "save" in pending.action_type or "write" in pending.action_type:
        entry["decision"] = "denied"
        approval_log.append(entry)
        print(f"    [approval] DENIED: {pending.action_type} — {pending.description}")
        return ApprovalResponse(
            approved=False,
            reason="Write operations require manager approval (denied for pilot demo)",
        )

    entry["decision"] = "approved"
    approval_log.append(entry)
    print(f"    [approval] Approved: {pending.action_type} — {pending.description}")
    return ApprovalResponse(approved=True, reason="Read-only operation approved")


# =====================================================================
# Main pilot
# =====================================================================

def run_pilot():
    question = "transformer attention mechanisms in large language models"

    print("=" * 70)
    print("PILOT: Governed Research Assistant")
    print("=" * 70)

    # -----------------------------------------------------------------
    # Phase 1: Tool Discovery
    # -----------------------------------------------------------------
    print("\n--- Phase 1: Tool Discovery ---")
    gateway = build_research_gateway()
    catalog = ToolCatalog.from_gateway(gateway)

    print(f"Available tools ({len(catalog)}):")
    for tool in catalog.list_tools():
        confirm = " [requires approval]" if tool.requires_confirmation else ""
        print(f"  {tool.name} [{tool.risk_level}]{confirm}")
        print(f"    {tool.description}")
        if tool.capabilities:
            print(f"    capabilities: {', '.join(tool.capabilities)}")

    # Show filtering
    write_tools = catalog.find_tools(risk_level="write")
    print(f"\nWrite-risk tools: {[t.name for t in write_tools]}")

    # -----------------------------------------------------------------
    # Phase 2: Governed Research Run (with approval + budget)
    # -----------------------------------------------------------------
    print("\n--- Phase 2: Governed Research Run ---")
    print(f"Question: {question}")
    print(f"Budget:   max 10,000 tokens / $0.50")
    print(f"Approval: required for all actions")

    adapter = build_research_adapter(question)
    dispatcher = CGToolDispatcher(adapter, gateway, tier="consumer")

    from agentic.agentic_framework.agent import AgenticLLMWrapper

    agent = AgenticLLMWrapper(
        llm_client=adapter,
        dispatcher=dispatcher,
        action_type_to_tool={
            "search": "search",
            "compute": "compute",
            "validate": "validate",
            "save": "save_report",
        },
    )
    agent.new_session()

    policy = ApprovalPolicy(require_all=True)
    ctrl = ApprovalController(policy=policy, callback=research_approval_callback)
    budget = BudgetPolicy(max_total_tokens=10000, max_cost=0.50)
    collector = TraceCollector()

    print("-" * 70)

    for event in agent.run_stream(
        f"Research: {question}",
        approval_controller=ctrl,
        budget_policy=budget,
        trace_collector=collector,
    ):
        et = event.event_type

        if et == GENERATION_COMPLETED:
            qs = event.payload.get("quality_score", 0)
            rev = event.payload.get("revision_count", 0)
            print(f"  [generation] quality={qs:.2f}, revisions={rev}")

        elif et == SAFETY_GATE_RESULT:
            eligible = event.payload.get("eligible", False)
            reasons = event.payload.get("blocking_reasons", [])
            if eligible:
                print(f"  [safety]     gate PASSED")
            else:
                print(f"  [safety]     gate BLOCKED: {reasons}")

        elif et == ACTION_STARTED:
            atype = event.payload.get("action_type")
            desc = event.payload.get("description", "")
            print(f"  [action]     started: {atype} — {desc}")

        elif et == ACTION_COMPLETED:
            status = event.payload.get("status")
            error = event.payload.get("error")
            if error:
                print(f"  [action]     {status}: {error}")
            else:
                print(f"  [action]     {status}")

        elif et == USAGE_UPDATED:
            tokens = event.payload.get("total_tokens", 0)
            mode = event.payload.get("accounting_mode", "?")
            print(f"  [usage]      {tokens} tokens ({mode})")

        elif et == BUDGET_EXCEEDED:
            print(f"  [budget]     EXCEEDED: {event.payload.get('reason')}")

        elif et == RUN_COMPLETED:
            print(f"  [run]        completed")

        elif et == RUN_ERROR:
            print(f"  [error]      {event.payload.get('error', 'unknown')}")

    # -----------------------------------------------------------------
    # Phase 3: Trace Summary
    # -----------------------------------------------------------------
    trace = collector.build_trace()

    print(f"\n--- Phase 3: Execution Trace ---")
    print(f"  Status:              {trace.status}")
    print(f"  Total events:        {trace.event_count}")
    print(f"  Actions executed:    {trace.actions_executed}")
    print(f"  Safety blocked:      {trace.safety_blocked}")
    print(f"  Approvals requested: {trace.approvals_requested}")
    print(f"  Approvals denied:    {trace.approvals_denied}")
    print(f"  Total tokens:        {trace.total_tokens}")
    print(f"  Accounting mode:     {trace.accounting_mode}")
    print(f"  Budget exceeded:     {trace.budget_exceeded}")

    # -----------------------------------------------------------------
    # Phase 4: Structured Answer
    # -----------------------------------------------------------------
    print(f"\n--- Phase 4: Structured Research Answer ---")

    # For structured output, use MockLLMAdapter with the answer JSON
    # as default_response.  use_llm_for_decomposition=False avoids
    # consuming responses on goal decomposition, keeping the adapter
    # simple and predictable.
    from agentic.agentic_framework.llm_adapters import MockLLMAdapter

    answer_json = json.dumps({
        "question": question,
        "summary": (
            "Transformer attention mechanisms enable LLMs to weigh "
            "input token relationships dynamically. Recent advances "
            "show 40% YoY industry adoption growth with improved "
            "efficiency across benchmarks."
        ),
        "confidence": "high",
        "sources_consulted": 2,
        "key_finding": (
            "Novel architectural approaches to attention (sparse, "
            "linear, multi-query) are reducing computational cost "
            "while maintaining quality."
        ),
    })

    agent2 = AgenticLLMWrapper(
        llm_client=MockLLMAdapter(default_response=answer_json),
        use_llm_for_decomposition=False,
    )
    agent2.new_session()

    result, trace2 = agent2.run_structured_with_trace(
        f"Answer this research question as structured JSON: {question}",
        schema=ResearchAnswer,
        budget_policy=BudgetPolicy(max_total_tokens=5000),
    )

    if result.success:
        answer = result.parsed_output
        print(f"  Question:          {answer.question}")
        print(f"  Summary:           {answer.summary[:80]}...")
        print(f"  Confidence:        {answer.confidence}")
        print(f"  Sources consulted: {answer.sources_consulted}")
        print(f"  Key finding:       {answer.key_finding[:80]}...")
    else:
        print(f"  Validation failed: {result.validation_error}")

    print(f"\n  Trace: status={trace2.status}, events={trace2.event_count}, "
          f"tokens={trace2.total_tokens}")

    # -----------------------------------------------------------------
    # Phase 5: Audit Summary
    # -----------------------------------------------------------------
    print(f"\n--- Phase 5: Governance Audit ---")
    audit = gateway.get_audit_log()
    print(f"  Audit entries: {len(audit)}")
    for entry in audit[:5]:
        print(f"    [{entry.decision.value}] {entry.tool_name}"
              f" — confidence={entry.confidence:.2f}")

    # -----------------------------------------------------------------
    # Final summary
    # -----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("PILOT COMPLETE")
    print("=" * 70)
    print(f"""
What this pilot proved:
  1. Custom tool handlers plug into the governance pipeline cleanly
  2. Approval gates fire on real tool-mapped actions
  3. Budget enforcement works across the research workflow
  4. Structured output validates against a research schema
  5. Tracing captures the full execution path
  6. Tool discovery provides accurate catalog of available tools
  7. Audit log records every governance decision

Framework components exercised:
  AgenticLLMWrapper, CGToolDispatcher, SafeMCPGateway, MockMCPClient,
  SafetyGate, ApprovalController, BudgetPolicy, TraceCollector,
  ToolCatalog, StructuredRunResult, AgentRunTrace, AgentRunEvent
""")


if __name__ == "__main__":
    run_pilot()
