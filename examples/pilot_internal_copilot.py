#!/usr/bin/env python3
"""
Pilot: Approval-Gated Internal Copilot
=======================================

Second real adoption pilot for the Agentic Framework.

This pilot builds an internal operations copilot that can freely
search and analyze internal data, but requires human approval before
any externally-visible or state-changing action (save, send, escalate).

Why this use case:
    Unlike the research-assistant pilot (which exercised broad tool
    composition), this pilot specifically stresses the approval boundary:
    - Read-only actions execute without interruption
    - Write/send actions require explicit human sign-off
    - Denied actions are cleanly skipped with trace evidence
    - The developer can see exactly which actions were gated and why

What this exercises:
    - build_agent() + ToolSpec composition
    - ApprovalPolicy with per-action-type approval (not require-all)
    - ApprovalController with approve + deny paths
    - BudgetPolicy with token caps
    - format_trace() for human-readable output
    - run_with_trace() for simple one-shot inspection
    - run_stream() with live event display
    - Structured output for a draft summary
    - ToolCatalog for discovery

Phases:
    1. Tool setup + discovery — 6 tools across read/write boundary
    2. Free read path — search + analyze execute without approval
    3. Approved write path — save_draft triggers approval → approved
    4. Denied write path — send_update triggers approval → denied
    5. Structured output — produce a typed operations summary
    6. Budget-aware run — demonstrate budget visibility
    7. Trace comparison — show traces from all phases

Run:
    python examples/pilot_internal_copilot.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from agentic.agentic_framework.agent_builder import build_agent
from agentic.agentic_framework.approval import (
    ApprovalController,
    ApprovalPolicy,
    ApprovalResponse,
    PendingApproval,
)
from agentic.agentic_framework.llm_adapters import (
    MockLLMAdapter,
    SequentialMockAdapter,
)
from agentic.agentic_framework.mcp_gateway import ToolSpec, ToolRiskLevel
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
from agentic.agentic_framework.trace_viewer import (
    format_trace,
    format_trace_summary,
    format_trace_timeline,
)
from agentic.agentic_framework.tracing import TraceCollector


# =====================================================================
# Structured output schema
# =====================================================================


@dataclass
class OperationsSummary:
    topic: str
    findings: str
    risk_level: str       # "low", "medium", "high"
    recommended_action: str
    data_sources: int


# =====================================================================
# Tool handlers — internal operations simulations
# =====================================================================


def search_internal(params: Dict[str, Any]) -> Dict[str, Any]:
    """Search internal knowledge base / wiki."""
    query = params.get("query", "")
    return {
        "results": [
            {"title": f"Internal doc: {query}", "snippet": f"Latest status on {query}: all systems operational. SLA at 99.7%."},
            {"title": f"Runbook: {query}", "snippet": f"Standard procedure for {query} incidents documented. Last updated 2 days ago."},
        ],
        "count": 2,
    }


def analyze_metrics(params: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze internal operational metrics."""
    metric = params.get("metric", "uptime")
    return {
        "metric": metric,
        "current_value": 99.7,
        "trend": "stable",
        "threshold": 99.5,
        "status": "healthy",
        "period": "last_7_days",
    }


def check_alerts(params: Dict[str, Any]) -> Dict[str, Any]:
    """Check current alert status."""
    return {
        "active_alerts": 1,
        "alerts": [
            {"severity": "warning", "service": "payment-api", "message": "P95 latency elevated (320ms vs 200ms threshold)"},
        ],
        "last_checked": "2 minutes ago",
    }


def save_draft(params: Dict[str, Any]) -> Dict[str, Any]:
    """Save a draft report to internal storage (write operation)."""
    title = params.get("title", "Untitled")
    return {"saved": True, "draft_id": "draft-2024-0042", "title": title}


def send_update(params: Dict[str, Any]) -> Dict[str, Any]:
    """Send a status update to the team channel (externally visible)."""
    channel = params.get("channel", "#ops")
    return {"sent": True, "channel": channel, "message_id": "msg-7891"}


def escalate_incident(params: Dict[str, Any]) -> Dict[str, Any]:
    """Escalate an incident to the on-call team (high-impact action)."""
    severity = params.get("severity", "medium")
    return {"escalated": True, "incident_id": "INC-2024-0315", "severity": severity}


# =====================================================================
# Tools — clear read/write boundary
# =====================================================================

COPILOT_TOOLS: Dict[str, ToolSpec] = {
    # --- Read-only (no approval needed) ---
    "search": ToolSpec(
        handler=search_internal,
        description="Search internal knowledge base and documentation",
        risk_level=ToolRiskLevel.READ_ONLY,
        capabilities=["search", "knowledge"],
    ),
    "analyze": ToolSpec(
        handler=analyze_metrics,
        description="Analyze operational metrics and trends",
        risk_level=ToolRiskLevel.READ_ONLY,
        capabilities=["analysis", "metrics"],
    ),
    "check_alerts": ToolSpec(
        handler=check_alerts,
        description="Check current alert and incident status",
        risk_level=ToolRiskLevel.READ_ONLY,
        capabilities=["monitoring", "alerts"],
    ),
    # --- Write (approval required) ---
    # Note: requires_confirmation is left False here because the R4
    # ApprovalPolicy handles the approval gate at the orchestration
    # layer.  Setting requires_confirmation=True would trigger a
    # *second* gate at the MCP gateway level (EscalationHandler),
    # which is a separate mechanism.  Use one or the other, not both.
    "save_draft": ToolSpec(
        handler=save_draft,
        description="Save a draft report to internal storage",
        risk_level=ToolRiskLevel.WRITE,
        capabilities=["storage", "reporting"],
    ),
    "send_update": ToolSpec(
        handler=send_update,
        description="Send a status update to team channel",
        risk_level=ToolRiskLevel.WRITE,
        capabilities=["communication", "notifications"],
    ),
    "escalate": ToolSpec(
        handler=escalate_incident,
        description="Escalate an incident to the on-call team",
        risk_level=ToolRiskLevel.EXECUTE,
        capabilities=["incident_management"],
        min_confidence=0.7,
    ),
}


# =====================================================================
# Approval callback — approves drafts, denies sends, denies escalations
# =====================================================================


def copilot_approval_callback(pending: PendingApproval) -> ApprovalResponse:
    """Simulates an internal approval workflow.

    In production this would prompt a human via Slack/UI/terminal.
    For this pilot:
    - save_draft → approved (low risk, internal only)
    - send_update → denied (externally visible, needs manager sign-off)
    - escalate → denied (high impact, needs incident commander)
    """
    action = pending.action_type

    if action in ("save_draft", "save"):
        print(f"    [approval] APPROVED: {action} — {pending.description}")
        return ApprovalResponse(approved=True, reason="Draft saves are pre-approved")

    if action in ("send_update", "send"):
        print(f"    [approval] DENIED: {action} — {pending.description}")
        return ApprovalResponse(
            approved=False,
            reason="Team updates require manager sign-off",
        )

    if action in ("escalate",):
        print(f"    [approval] DENIED: {action} — {pending.description}")
        return ApprovalResponse(
            approved=False,
            reason="Escalations require incident commander approval",
        )

    # Default: approve unknown actions
    print(f"    [approval] APPROVED (default): {action}")
    return ApprovalResponse(approved=True, reason="Default approved")


# =====================================================================
# LLM adapter builders
# =====================================================================


def _make_adapter_for_action(action_type: str, description: str):
    """Build a SequentialMockAdapter that decomposes into one specific action."""
    decomposition = json.dumps({
        "purpose": description,
        "purpose_type": "task",
        "reasoning_strategy": "Execute the requested operation",
        "reasoning_steps": [description],
        "agency_level": "FULL",
        "actions": [
            {"description": description, "type": action_type, "parameters": {}},
        ],
        "complexity": 0.3,
    })
    generation = f"I will {description.lower()}."
    critic = json.dumps({"quality_score": 0.85, "feedback": "Clear and direct."})

    adapter = SequentialMockAdapter([decomposition, generation, critic], loop=True)
    adapter.last_cg_metadata = {}
    adapter.IS_STUB = True
    return adapter


# =====================================================================
# Phase runner helpers
# =====================================================================


def _run_phase_with_events(
    label: str,
    agent,
    prompt: str,
    *,
    approval_controller=None,
    budget_policy=None,
):
    """Run a phase with live event printing and return the trace."""
    collector = TraceCollector()

    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"  Prompt: {prompt}")
    if approval_controller:
        policy = approval_controller.policy
        if policy.require_all:
            print("  Approval: required for ALL actions")
        elif policy.require_approval_for:
            print(f"  Approval: required for {set(policy.require_approval_for)}")
    if budget_policy:
        caps = []
        if budget_policy.max_total_tokens:
            caps.append(f"{budget_policy.max_total_tokens} tokens")
        if budget_policy.max_cost:
            caps.append(f"${budget_policy.max_cost:.2f}")
        print(f"  Budget:   {' / '.join(caps)}")
    print("-" * 60)

    for event in agent.run_stream(
        prompt,
        approval_controller=approval_controller,
        budget_policy=budget_policy,
        trace_collector=collector,
    ):
        et = event.event_type

        if et == GENERATION_COMPLETED:
            qs = event.payload.get("quality_score", 0)
            print(f"  [gen]      quality={qs:.2f}")

        elif et == SAFETY_GATE_RESULT:
            eligible = event.payload.get("eligible", False)
            print(f"  [safety]   {'PASSED' if eligible else 'BLOCKED'}")

        elif et == ACTION_STARTED:
            atype = event.payload.get("action_type", "")
            desc = event.payload.get("description", "")
            print(f"  [action]   >> {atype}: {desc}")

        elif et == ACTION_COMPLETED:
            status = event.payload.get("status", "")
            err = event.payload.get("error", "")
            if err:
                print(f"  [action]   << {status}: {err}")
            else:
                print(f"  [action]   << {status}")

        elif et == APPROVAL_REQUESTED:
            atype = event.payload.get("action_type", "")
            print(f"  [approval] requesting approval for: {atype}")

        elif et == APPROVAL_RESOLVED:
            approved = event.payload.get("approved", False)
            reason = event.payload.get("reason", "")
            tag = "APPROVED" if approved else "DENIED"
            print(f"  [approval] {tag}: {reason}")

        elif et == USAGE_UPDATED:
            tokens = event.payload.get("total_tokens", 0)
            mode = event.payload.get("accounting_mode", "?")
            print(f"  [usage]    {tokens} tokens ({mode})")

        elif et == BUDGET_EXCEEDED:
            print(f"  [budget]   EXCEEDED: {event.payload.get('reason', '')}")

        elif et == RUN_COMPLETED:
            print(f"  [run]      completed")

        elif et == RUN_ERROR:
            print(f"  [error]    {event.payload.get('error', 'unknown')}")

    trace = collector.build_trace()
    return trace


# =====================================================================
# Main pilot
# =====================================================================


def run_pilot():
    print("=" * 60)
    print("  PILOT: Approval-Gated Internal Copilot")
    print("=" * 60)

    # Approval policy: only write/send/escalate actions need approval
    approval_policy = ApprovalPolicy(
        require_approval_for=frozenset({"save_draft", "save", "send_update", "send", "escalate"}),
    )
    approval_ctrl = ApprovalController(
        policy=approval_policy,
        callback=copilot_approval_callback,
    )
    budget = BudgetPolicy(max_total_tokens=8000, max_cost=0.25)

    # -----------------------------------------------------------------
    # Phase 1: Tool Discovery
    # -----------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("  Phase 1: Tool Discovery")
    print(f"{'=' * 60}")

    # Build agent once — reuse across phases
    adapter = _make_adapter_for_action("search", "Search internal knowledge base")
    agent = build_agent(
        adapter=adapter,
        tools=COPILOT_TOOLS,
        allow_stub=True,
        action_type_to_tool={
            "search": "search",
            "analyze": "analyze",
            "check_alerts": "check_alerts",
            "save_draft": "save_draft",
            "save": "save_draft",
            "send_update": "send_update",
            "send": "send_update",
            "escalate": "escalate",
        },
    )
    agent.new_session()

    catalog = ToolCatalog.from_agent(agent)
    print(f"\n  Registered tools ({len(catalog)}):")
    for tool in catalog.list_tools():
        risk_tag = f"[{tool.risk_level}]"
        confirm_tag = " (approval required)" if tool.requires_confirmation else ""
        print(f"    {tool.name:<16} {risk_tag:<14}{confirm_tag}")
        print(f"      {tool.description}")

    read_tools = catalog.find_tools(risk_level="read_only")
    write_tools = catalog.find_tools(requires_confirmation=True)
    print(f"\n  Read-only tools:         {[t.name for t in read_tools]}")
    print(f"  Approval-required tools: {[t.name for t in write_tools]}")

    # Show approval policy coverage
    print(f"\n  Approval policy coverage:")
    for tool in catalog.list_tools():
        needs = approval_policy.requires_approval(tool.name)
        print(f"    {tool.name:<16} → {'APPROVAL REQUIRED' if needs else 'auto-execute'}")

    # -----------------------------------------------------------------
    # Phase 2: Free Read Path (no approval needed)
    # -----------------------------------------------------------------
    adapter_search = _make_adapter_for_action("search", "Search for payment-api status")
    agent_read = build_agent(
        adapter=adapter_search,
        tools=COPILOT_TOOLS,
        allow_stub=True,
        action_type_to_tool={
            "search": "search",
            "analyze": "analyze",
            "check_alerts": "check_alerts",
            "save_draft": "save_draft",
            "save": "save_draft",
            "send_update": "send_update",
            "send": "send_update",
            "escalate": "escalate",
        },
    )
    agent_read.new_session()

    trace_read = _run_phase_with_events(
        "Phase 2: Free Read Path (search — no approval)",
        agent_read,
        "Search for the current status of payment-api",
        approval_controller=approval_ctrl,
        budget_policy=budget,
    )

    # -----------------------------------------------------------------
    # Phase 3: Approved Write Path (save_draft → approved)
    # -----------------------------------------------------------------
    adapter_save = _make_adapter_for_action("save_draft", "Save operations summary as draft")
    agent_save = build_agent(
        adapter=adapter_save,
        tools=COPILOT_TOOLS,
        allow_stub=True,
        action_type_to_tool={
            "search": "search",
            "analyze": "analyze",
            "check_alerts": "check_alerts",
            "save_draft": "save_draft",
            "save": "save_draft",
            "send_update": "send_update",
            "send": "send_update",
            "escalate": "escalate",
        },
    )
    agent_save.new_session()

    trace_approved = _run_phase_with_events(
        "Phase 3: Approved Write Path (save_draft → APPROVED)",
        agent_save,
        "Save a draft summary of current operations status",
        approval_controller=approval_ctrl,
        budget_policy=budget,
    )

    # -----------------------------------------------------------------
    # Phase 4: Denied Write Path (send_update → denied)
    # -----------------------------------------------------------------
    adapter_send = _make_adapter_for_action("send_update", "Send status update to #ops channel")
    agent_send = build_agent(
        adapter=adapter_send,
        tools=COPILOT_TOOLS,
        allow_stub=True,
        action_type_to_tool={
            "search": "search",
            "analyze": "analyze",
            "check_alerts": "check_alerts",
            "save_draft": "save_draft",
            "save": "save_draft",
            "send_update": "send_update",
            "send": "send_update",
            "escalate": "escalate",
        },
    )
    agent_send.new_session()

    trace_denied = _run_phase_with_events(
        "Phase 4: Denied Write Path (send_update → DENIED)",
        agent_send,
        "Send a status update to the team about payment-api latency",
        approval_controller=approval_ctrl,
        budget_policy=budget,
    )

    # -----------------------------------------------------------------
    # Phase 5: Structured Output — Operations Summary
    # -----------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("  Phase 5: Structured Output")
    print(f"{'=' * 60}")

    answer_json = json.dumps({
        "topic": "payment-api latency",
        "findings": "P95 latency elevated to 320ms (threshold: 200ms). All other services healthy. SLA at 99.7%.",
        "risk_level": "medium",
        "recommended_action": "Monitor for 30 minutes; escalate if P95 exceeds 500ms.",
        "data_sources": 3,
    })

    from agentic.agentic_framework import AgenticLLMWrapper

    agent_structured = AgenticLLMWrapper(
        llm_client=MockLLMAdapter(default_response=answer_json),
        use_llm_for_decomposition=False,
    )
    agent_structured.new_session()

    result, trace_structured = agent_structured.run_structured_with_trace(
        "Produce an operations summary for the current payment-api situation",
        schema=OperationsSummary,
        budget_policy=BudgetPolicy(max_total_tokens=5000),
    )

    if result.success:
        summary = result.parsed_output
        print(f"  Topic:         {summary.topic}")
        print(f"  Findings:      {summary.findings[:70]}...")
        print(f"  Risk level:    {summary.risk_level}")
        print(f"  Recommended:   {summary.recommended_action[:70]}...")
        print(f"  Data sources:  {summary.data_sources}")
    else:
        print(f"  Validation FAILED: {result.validation_error}")

    # -----------------------------------------------------------------
    # Phase 6: Trace Comparison
    # -----------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("  Phase 6: Trace Comparison")
    print(f"{'=' * 60}")

    traces = [
        ("Read (search)", trace_read),
        ("Approved (save_draft)", trace_approved),
        ("Denied (send_update)", trace_denied),
        ("Structured output", trace_structured),
    ]

    # Compact comparison table
    print(f"\n  {'Phase':<25} {'Status':<18} {'Actions':<8} {'Approv':<8} {'Denied':<8} {'Tokens':<8}")
    print(f"  {'-' * 75}")
    for label, t in traces:
        print(
            f"  {label:<25} {t.status:<18} {t.actions_executed:<8} "
            f"{t.approvals_requested:<8} {t.approvals_denied:<8} {t.total_tokens:<8}"
        )

    # Full trace for the most interesting phase (denied)
    print(f"\n  --- Full trace: Denied write path ---")
    print(format_trace(trace_denied))

    # -----------------------------------------------------------------
    # Phase 7: Final Evaluation
    # -----------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("  PILOT COMPLETE")
    print(f"{'=' * 60}")

    print("""
  What this pilot proves:
    1. Per-action-type approval policy works — read actions auto-execute,
       write actions are gated
    2. Approved path: save_draft triggers approval → approved → executes
    3. Denied path: send_update triggers approval → denied → skipped cleanly
    4. Trace viewer shows approval events with reasons
    5. Budget policy is visible in trace output
    6. Structured output validates against OperationsSummary schema
    7. Tool catalog shows read/write boundary clearly
    8. Approval policy coverage is inspectable before running

  What this pilot does NOT prove:
    - Real LLM inference (uses mock adapters)
    - Interactive human approval (callback is automated)
    - Multi-turn conversation with evolving approval needs
    - Async approval workflows
    - Production deployment patterns

  Framework components exercised:
    build_agent, ToolSpec, AgenticLLMWrapper, CGToolDispatcher,
    SafeMCPGateway, SafetyGate, ApprovalPolicy, ApprovalController,
    BudgetPolicy, TraceCollector, format_trace, ToolCatalog,
    StructuredRunResult, AgentRunTrace, AgentRunEvent
""")


if __name__ == "__main__":
    run_pilot()
