#!/usr/bin/env python3
"""
Adoption Validation: Governed Alert Triage Assistant
====================================================

Written as a "second developer" exercise — following only the public
docs (QUICKSTART.md, FIRST_GOVERNED_AGENT.md, minimal_governed_agent.py)
without relying on internal project history.

Use case:
    An on-call engineer asks the agent to check current alerts, triage
    them, and optionally acknowledge or escalate.  The governance layer
    ensures:
    - read-only alert checks execute freely
    - acknowledge/escalate require human approval
    - budget caps prevent runaway token usage
    - every step is traced

What this exercises:
    - build_agent() with multiple tools at different risk levels
    - ApprovalPolicy + ApprovalController (selective approval)
    - BudgetPolicy (token cap)
    - run_stream() with TraceCollector
    - format_trace() for human-readable output
    - Streaming event handling (generation, safety, action, approval)

Friction log:
    Every point where the author had to look beyond the docs is noted
    with a "# FRICTION:" comment.

Run:
    python examples/adoption_validation_alert_triage.py
"""

from __future__ import annotations

# --- Imports ---
# The quickstart shows imports from submodules. The __init__.py also
# exports most of these at the top level. I'll use the top-level path
# where possible, falling back to submodules only when needed.

from agentic.agentic_framework import (
    build_agent,
    ToolSpec,
    ToolRiskLevel,
    ApprovalController,
    ApprovalPolicy,
    ApprovalResponse,
    BudgetPolicy,
    TraceCollector,
    format_trace,
)

# FRICTION: MockLLMAdapter is NOT in __init__.py top-level exports.
# Every example imports it from the submodule. A new developer would
# naturally try `from agentic.agentic_framework import MockLLMAdapter`
# first and get an ImportError.
from agentic.agentic_framework.llm_adapters import MockLLMAdapter

# FRICTION: SequentialMockAdapter is also not in top-level exports.
# Discovered it exists only by reading pilot_internal_copilot.py source.
# The quickstart/first-governed-agent docs don't mention it at all.
from agentic.agentic_framework.llm_adapters import SequentialMockAdapter

# Streaming event types — needed for run_stream() event handling.
# These ARE in __init__.py, which is good.
from agentic.agentic_framework import (
    GENERATION_COMPLETED,
    SAFETY_GATE_RESULT,
    ACTION_STARTED,
    ACTION_COMPLETED,
    APPROVAL_REQUESTED,
    APPROVAL_RESOLVED,
    USAGE_UPDATED,
    RUN_COMPLETED,
    RUN_ERROR,
)


# --- Tool handlers ---

def check_alerts(params):
    """Simulate fetching current alerts from a monitoring system."""
    return {
        "alerts": [
            {"id": "ALT-001", "severity": "critical", "service": "payment-api",
             "message": "P95 latency > 500ms for 10 minutes"},
            {"id": "ALT-002", "severity": "warning", "service": "auth-service",
             "message": "Error rate 2.1% (threshold 2%)"},
            {"id": "ALT-003", "severity": "info", "service": "cdn-edge",
             "message": "Cache hit rate dropped to 89%"},
        ],
        "total": 3,
    }


def acknowledge_alert(params):
    """Simulate acknowledging an alert."""
    alert_id = params.get("alert_id", "unknown")
    return {"acknowledged": True, "alert_id": alert_id, "by": "on-call-engineer"}


def escalate_alert(params):
    """Simulate escalating an alert to the on-call team."""
    alert_id = params.get("alert_id", "unknown")
    severity = params.get("severity", "unknown")
    return {"escalated": True, "alert_id": alert_id, "severity": severity,
            "paged": "sre-oncall@company.com"}


# --- Tool definitions ---

TOOLS = {
    "check_alerts": ToolSpec(
        handler=check_alerts,
        description="Check current monitoring alerts",
        risk_level=ToolRiskLevel.READ_ONLY,
        capabilities=["monitoring"],
    ),
    "acknowledge_alert": ToolSpec(
        handler=acknowledge_alert,
        description="Acknowledge an alert (marks it as seen)",
        risk_level=ToolRiskLevel.WRITE,
        capabilities=["monitoring", "write"],
    ),
    "escalate_alert": ToolSpec(
        handler=escalate_alert,
        description="Escalate an alert to the on-call team",
        risk_level=ToolRiskLevel.WRITE,
        capabilities=["monitoring", "escalation"],
    ),
}

# FRICTION: The action_type_to_tool mapping is confusing for new devs.
# build_agent() docs say it defaults to identity mapping from tool keys,
# which means the LLM's decomposed action types must exactly match tool
# names. But real LLMs produce generic types like "search", "execute",
# "generate" — not "check_alerts" or "escalate_alert".
#
# The QUICKSTART.md doesn't explain this mapping at all.
# FIRST_GOVERNED_AGENT.md doesn't mention it.
# I only understood it by reading build_agent() source and the
# pilot_internal_copilot.py example.
#
# For this example with MockLLMAdapter, the decomposition falls back to
# _simple_extraction() which produces "generate" as the action type.
# With the identity mapping, "generate" won't match any tool name.
# So I need to either:
#   a) Provide an explicit action_type_to_tool mapping
#   b) Use SequentialMockAdapter that returns JSON with matching types
#
# I'll use SequentialMockAdapter to control the LLM output.

# --- Approval callback ---

def triage_approval_callback(pending):
    """Auto-approve acknowledges, auto-deny escalations for this demo."""
    action = pending.action_type
    desc = pending.description

    if action in ("acknowledge_alert", "acknowledge"):
        print(f"    [approval] AUTO-APPROVED: {action} — {desc}")
        return ApprovalResponse(approved=True, reason="Acknowledges are pre-approved")

    if action in ("escalate_alert", "escalate"):
        print(f"    [approval] DENIED: {action} — requires incident commander sign-off")
        return ApprovalResponse(approved=False, reason="Escalations need IC approval")

    # Default: approve
    print(f"    [approval] DEFAULT-APPROVED: {action}")
    return ApprovalResponse(approved=True, reason="Default policy")


# --- Mock LLM responses ---

# FRICTION: Getting SequentialMockAdapter to produce the right JSON
# format requires understanding the DECOMPOSITION_PROMPT template in
# goal_decomposition.py. The docs don't explain this format anywhere.
# A new developer must read the source to understand what JSON shape
# the framework expects from the LLM.
#
# The response needs to be valid JSON matching the decomposition prompt's
# expected output format. I figured this out by reading
# goal_decomposition.py:DECOMPOSITION_PROMPT.

import json

PHASE_1_RESPONSE = json.dumps({
    "purpose": "Check current monitoring alerts and triage them",
    "purpose_type": "task",
    "reasoning_strategy": "Fetch alerts, assess severity, recommend actions",
    "reasoning_steps": [
        "Check current alerts",
        "Assess severity of each alert",
        "Recommend triage actions",
    ],
    "agency_level": "CONFIRM",
    "actions": [
        {
            "description": "Check current monitoring alerts",
            "type": "check_alerts",
            "parameters": {},
        },
    ],
    "dependencies": {},
    "complexity": 0.3,
})

PHASE_2_RESPONSE = json.dumps({
    "purpose": "Acknowledge the warning-level alert for auth-service",
    "purpose_type": "task",
    "reasoning_strategy": "Acknowledge non-critical alert to clear noise",
    "reasoning_steps": [
        "Identify the alert to acknowledge",
        "Submit acknowledgement",
    ],
    "agency_level": "CONFIRM",
    "actions": [
        {
            "description": "Acknowledge auth-service warning alert ALT-002",
            "type": "acknowledge_alert",
            "parameters": {"alert_id": "ALT-002"},
        },
    ],
    "dependencies": {},
    "complexity": 0.2,
})

PHASE_3_RESPONSE = json.dumps({
    "purpose": "Escalate the critical payment-api alert to the on-call team",
    "purpose_type": "task",
    "reasoning_strategy": "Critical alert requires immediate human attention",
    "reasoning_steps": [
        "Identify critical alert",
        "Escalate to on-call team",
    ],
    "agency_level": "CONFIRM",
    "actions": [
        {
            "description": "Escalate critical payment-api alert ALT-001",
            "type": "escalate_alert",
            "parameters": {"alert_id": "ALT-001", "severity": "critical"},
        },
    ],
    "dependencies": {},
    "complexity": 0.2,
})


def run_phase(label, adapter, prompt, approval_ctrl, budget):
    """Run one phase of the triage workflow."""
    collector = TraceCollector()

    agent = build_agent(
        adapter=adapter,
        tools=TOOLS,
        allow_stub=True,
        # FRICTION: Must provide action_type_to_tool to map action types
        # to tool names. Without this, the identity mapping from tool keys
        # is used, which only works if the LLM produces exact tool names
        # as action types.
        action_type_to_tool={
            "check_alerts": "check_alerts",
            "acknowledge_alert": "acknowledge_alert",
            "escalate_alert": "escalate_alert",
            # Also map generic types that a real LLM might produce
            "search": "check_alerts",
            "execute": "acknowledge_alert",
            "generate": "check_alerts",
        },
    )
    agent.new_session()

    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"  Prompt: {prompt}")
    print("-" * 60)

    for event in agent.run_stream(
        prompt,
        approval_controller=approval_ctrl,
        budget_policy=budget,
        trace_collector=collector,
    ):
        et = event.event_type

        if et == GENERATION_COMPLETED:
            score = event.payload.get("quality_score", 0)
            print(f"  [gen]      quality={score:.2f}")

        elif et == SAFETY_GATE_RESULT:
            eligible = event.payload.get("eligible", False)
            reasons = event.payload.get("blocking_reasons", [])
            tag = "PASSED" if eligible else f"BLOCKED: {reasons}"
            print(f"  [safety]   {tag}")

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
            print(f"  [approval] requesting: {atype}")

        elif et == APPROVAL_RESOLVED:
            approved = event.payload.get("approved", False)
            reason = event.payload.get("reason", "")
            tag = "APPROVED" if approved else "DENIED"
            print(f"  [approval] {tag}: {reason}")

        elif et == USAGE_UPDATED:
            tokens = event.payload.get("total_tokens", 0)
            mode = event.payload.get("accounting_mode", "?")
            print(f"  [usage]    {tokens} tokens ({mode})")

        elif et == RUN_COMPLETED:
            print(f"  [run]      completed")

        elif et == RUN_ERROR:
            print(f"  [error]    {event.payload.get('error', '')}")

    trace = collector.build_trace()
    print()
    print(format_trace(trace))
    return trace


def main():
    print("=" * 60)
    print("  ADOPTION VALIDATION: Governed Alert Triage Assistant")
    print("=" * 60)
    print()
    print("  Validation mode: Simulated second-developer")
    print("  Author followed: QUICKSTART.md, FIRST_GOVERNED_AGENT.md,")
    print("                   minimal_governed_agent.py, pilot examples")
    print("  Tools: check_alerts (read), acknowledge_alert (write),")
    print("         escalate_alert (write)")
    print()

    # --- Approval setup ---
    policy = ApprovalPolicy(
        require_approval_for=frozenset({"acknowledge_alert", "escalate_alert"}),
    )
    ctrl = ApprovalController(policy=policy, callback=triage_approval_callback)
    budget = BudgetPolicy(max_total_tokens=5000, max_cost=0.50)

    traces = []

    # Phase 1: Read path — check alerts (no approval needed)
    adapter1 = MockLLMAdapter(default_response=PHASE_1_RESPONSE)
    t1 = run_phase(
        "Phase 1: Check alerts (read — no approval)",
        adapter1,
        "Check the current monitoring alerts and summarize severity",
        ctrl, budget,
    )
    traces.append(("Phase 1: Check alerts", t1))

    # Phase 2: Write path — acknowledge (approval expected → approved)
    adapter2 = MockLLMAdapter(default_response=PHASE_2_RESPONSE)
    t2 = run_phase(
        "Phase 2: Acknowledge alert (write — approval → approved)",
        adapter2,
        "Acknowledge the auth-service warning alert ALT-002",
        ctrl, budget,
    )
    traces.append(("Phase 2: Acknowledge alert", t2))

    # Phase 3: Write path — escalate (approval expected → denied)
    adapter3 = MockLLMAdapter(default_response=PHASE_3_RESPONSE)
    t3 = run_phase(
        "Phase 3: Escalate alert (write — approval → denied)",
        adapter3,
        "Escalate the critical payment-api alert ALT-001 to the on-call team",
        ctrl, budget,
    )
    traces.append(("Phase 3: Escalate alert", t3))

    # --- Summary ---
    print()
    print("=" * 60)
    print("  VALIDATION SUMMARY")
    print("=" * 60)

    all_ok = True
    for label, trace in traces:
        status = trace.status
        actions = trace.actions_executed
        approvals_req = trace.approvals_requested
        approvals_denied = trace.approvals_denied
        tokens = trace.total_tokens
        ok = status == "completed"
        if not ok:
            all_ok = False
        print(f"  {label}")
        print(f"    Status:    {status}")
        print(f"    Actions:   {actions}")
        print(f"    Approvals: {approvals_req} requested, {approvals_denied} denied")
        print(f"    Tokens:    {tokens}")
        print()

    # Verify expected behavior
    checks = []

    # Phase 1: read path should complete with 1 action, no approvals
    checks.append(("P1: completed", traces[0][1].status == "completed"))
    checks.append(("P1: 1 action", traces[0][1].actions_executed >= 1))
    checks.append(("P1: no approvals", traces[0][1].approvals_requested == 0))

    # Phase 2: write path should trigger approval → approved → execute
    checks.append(("P2: completed", traces[1][1].status == "completed"))
    checks.append(("P2: approval requested", traces[1][1].approvals_requested >= 1))
    checks.append(("P2: approval granted", traces[1][1].approvals_denied == 0))

    # Phase 3: write path should trigger approval → denied → skip
    checks.append(("P3: completed", traces[2][1].status == "completed"))
    checks.append(("P3: approval requested", traces[2][1].approvals_requested >= 1))
    checks.append(("P3: approval denied", traces[2][1].approvals_denied >= 1))

    print("  Validation checks:")
    passed = 0
    for label, result in checks:
        tag = "PASS" if result else "FAIL"
        if result:
            passed += 1
        print(f"    [{tag}] {label}")

    print()
    print(f"  Result: {passed}/{len(checks)} checks passed")
    print()

    if all_ok and passed == len(checks):
        print("  VERDICT: A second developer CAN build a governed agent")
        print("  from the current docs and examples, but with friction.")
        print()
        print("  Key friction points (see FRICTION comments in source):")
        print("    1. MockLLMAdapter not in top-level exports")
        print("    2. action_type_to_tool mapping not explained in quickstart")
        print("    3. LLM response JSON format undocumented for new devs")
        print("    4. SequentialMockAdapter only discoverable from pilot source")
    else:
        print("  VERDICT: FAILED — see errors above")

    return 0 if (all_ok and passed == len(checks)) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
