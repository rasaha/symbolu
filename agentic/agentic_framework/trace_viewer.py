"""
Trace Viewer — Developer-Friendly Trace Formatting (R11)

Compact, readable formatting of ``AgentRunTrace`` for terminal output.
Two views: **summary** (key counters at a glance) and **timeline**
(chronological event list with payload highlights).

Usage::

    from agentic.agentic_framework.trace_viewer import format_trace

    result, trace = agent.run_with_trace("Hello")
    print(format_trace(trace))

Or separately::

    from agentic.agentic_framework.trace_viewer import (
        format_trace_summary,
        format_trace_timeline,
    )
    print(format_trace_summary(trace))
    print(format_trace_timeline(trace))
"""

from __future__ import annotations

from typing import List, Optional

from agentic.agentic_framework.streaming_events import (
    AgentRunEvent,
    RUN_STARTED,
    GENERATION_STARTED,
    TEXT_CHUNK,
    GENERATION_COMPLETED,
    SAFETY_GATE_RESULT,
    ACTION_STARTED,
    ACTION_COMPLETED,
    RUN_COMPLETED,
    RUN_ERROR,
    RUN_CANCELLED,
    REVISION_STARTED,
    REVISION_COMPLETED,
    STRUCTURED_VALIDATION,
    APPROVAL_REQUESTED,
    APPROVAL_RESOLVED,
    USAGE_UPDATED,
    BUDGET_EXCEEDED,
)
from agentic.agentic_framework.tracing import AgentRunTrace


# -----------------------------------------------------------------------
# Status badges
# -----------------------------------------------------------------------

_STATUS_BADGE = {
    "completed": "[COMPLETED]",
    "cancelled": "[CANCELLED]",
    "error": "[ERROR]",
    "budget_exceeded": "[BUDGET EXCEEDED]",
    "unknown": "[UNKNOWN]",
}


def _badge(status: str) -> str:
    return _STATUS_BADGE.get(status, f"[{status.upper()}]")


# -----------------------------------------------------------------------
# Summary view
# -----------------------------------------------------------------------


def format_trace_summary(trace: AgentRunTrace) -> str:
    """Format a compact summary of the trace.

    Returns a multi-line string showing status, counters, usage,
    and governance outcomes — everything from ``trace.summary``
    in a human-readable layout.
    """
    lines: List[str] = []
    lines.append("Trace Summary")
    lines.append("=" * 40)

    # Status + identifiers
    lines.append(f"  Status:             {_badge(trace.status)}")
    if trace.session_id:
        lines.append(f"  Session:            {trace.session_id}")
    if trace.turn_id >= 0:
        lines.append(f"  Turn:               {trace.turn_id}")

    # Timing
    if trace.started_at:
        lines.append(f"  Started:            {trace.started_at}")
    if trace.ended_at:
        lines.append(f"  Ended:              {trace.ended_at}")

    lines.append("")

    # Counters
    lines.append(f"  Events:             {trace.event_count}")
    lines.append(f"  Actions executed:   {trace.actions_executed}")
    lines.append(f"  Text chunks:        {trace.text_chunks}")

    # Safety
    lines.append(f"  Safety blocked:     {'yes' if trace.safety_blocked else 'no'}")

    # Approvals
    if trace.approvals_requested > 0 or trace.approvals_denied > 0:
        lines.append("")
        lines.append(f"  Approvals requested: {trace.approvals_requested}")
        lines.append(f"  Approvals denied:    {trace.approvals_denied}")

    # Usage
    lines.append("")
    lines.append(f"  Total tokens:       {trace.total_tokens}")
    if trace.input_tokens or trace.output_tokens:
        lines.append(f"    Input tokens:     {trace.input_tokens}")
        lines.append(f"    Output tokens:    {trace.output_tokens}")
    lines.append(f"  Estimated cost:     ${trace.estimated_cost:.4f}")
    lines.append(f"  Accounting mode:    {trace.accounting_mode}")
    lines.append(f"  Budget exceeded:    {'yes' if trace.budget_exceeded else 'no'}")

    # Error
    if trace.error_occurred and trace.error_message:
        lines.append("")
        lines.append(f"  Error:              {trace.error_message}")

    return "\n".join(lines)


# -----------------------------------------------------------------------
# Event timeline helpers
# -----------------------------------------------------------------------

_EVENT_LABELS = {
    RUN_STARTED: "RUN START",
    GENERATION_STARTED: "GEN START",
    TEXT_CHUNK: "TEXT",
    GENERATION_COMPLETED: "GEN DONE",
    SAFETY_GATE_RESULT: "SAFETY",
    ACTION_STARTED: "ACTION >>",
    ACTION_COMPLETED: "ACTION <<",
    RUN_COMPLETED: "RUN DONE",
    RUN_ERROR: "RUN ERR",
    RUN_CANCELLED: "CANCELLED",
    REVISION_STARTED: "REVISE >>",
    REVISION_COMPLETED: "REVISE <<",
    STRUCTURED_VALIDATION: "VALIDATE",
    APPROVAL_REQUESTED: "APPROVE?",
    APPROVAL_RESOLVED: "APPROVE:",
    USAGE_UPDATED: "USAGE",
    BUDGET_EXCEEDED: "BUDGET!",
}


def _event_label(event_type: str) -> str:
    return _EVENT_LABELS.get(event_type, event_type.upper())


def _format_event_detail(event: AgentRunEvent) -> str:
    """Extract the most useful payload detail for a single event."""
    p = event.payload
    et = event.event_type

    if et == RUN_STARTED:
        return ""

    if et == GENERATION_COMPLETED:
        resp = p.get("response", "")
        qs = p.get("quality_score")
        parts = []
        if resp:
            truncated = resp[:60].replace("\n", " ")
            if len(resp) > 60:
                truncated += "..."
            parts.append(f'"{truncated}"')
        if qs is not None:
            parts.append(f"quality={qs:.2f}")
        return " ".join(parts)

    if et == TEXT_CHUNK:
        chunk = p.get("chunk", p.get("text", ""))
        if chunk:
            return chunk[:40].replace("\n", " ")
        return ""

    if et == SAFETY_GATE_RESULT:
        eligible = p.get("eligible", None)
        if eligible is not None:
            label = "eligible" if eligible else "BLOCKED"
            reasons = p.get("blocking_reasons", [])
            if reasons:
                return f"{label} ({', '.join(reasons)})"
            return label
        return ""

    if et == ACTION_STARTED:
        atype = p.get("action_type", "")
        desc = p.get("description", "")
        if desc:
            return f"{atype}: {desc[:50]}"
        return atype

    if et == ACTION_COMPLETED:
        atype = p.get("action_type", "")
        status = p.get("status", "")
        err = p.get("error", "")
        if err:
            return f"{atype}: {status} — {err[:50]}"
        return f"{atype}: {status}"

    if et == APPROVAL_REQUESTED:
        atype = p.get("action_type", "")
        desc = p.get("description", "")
        if desc:
            return f"{atype}: {desc[:50]}"
        return atype

    if et == APPROVAL_RESOLVED:
        approved = p.get("approved", None)
        reason = p.get("reason", "")
        label = "approved" if approved else "DENIED"
        if reason:
            return f"{label} ({reason[:40]})"
        return label

    if et == USAGE_UPDATED:
        total = p.get("total_tokens", 0)
        mode = p.get("accounting_mode", "")
        return f"{total} tokens ({mode})"

    if et == BUDGET_EXCEEDED:
        reason = p.get("reason", "")
        return reason[:60] if reason else "limit reached"

    if et == STRUCTURED_VALIDATION:
        success = p.get("success", None)
        err = p.get("validation_error", "")
        if success is True:
            return "passed"
        elif success is False:
            return f"FAILED: {err[:50]}" if err else "FAILED"
        return ""

    if et == RUN_ERROR:
        return p.get("error", "")[:60]

    if et == RUN_CANCELLED:
        return p.get("reason", "")[:60]

    if et == REVISION_STARTED:
        num = p.get("revision_number", "")
        return f"revision #{num}" if num else ""

    if et == REVISION_COMPLETED:
        qs = p.get("quality_score")
        return f"quality={qs:.2f}" if qs is not None else ""

    return ""


# -----------------------------------------------------------------------
# Timeline view
# -----------------------------------------------------------------------


def format_trace_timeline(trace: AgentRunTrace) -> str:
    """Format a chronological event timeline.

    Returns a multi-line string with one row per event, showing
    the event label and key payload details.
    """
    if not trace.events:
        return "Timeline: (no events)"

    lines: List[str] = []
    lines.append("Event Timeline")
    lines.append("-" * 60)

    # Compute relative timestamps if possible
    base_ts = trace.events[0].timestamp

    for i, event in enumerate(trace.events):
        label = _event_label(event.event_type)
        detail = _format_event_detail(event)

        # Format: index | label | detail
        idx = f"{i + 1:>3}"
        label_col = f"{label:<12}"
        if detail:
            lines.append(f"  {idx}. {label_col} {detail}")
        else:
            lines.append(f"  {idx}. {label_col}")

    lines.append("-" * 60)
    lines.append(f"  {len(trace.events)} events total")

    return "\n".join(lines)


# -----------------------------------------------------------------------
# Combined view
# -----------------------------------------------------------------------


def format_trace(trace: AgentRunTrace) -> str:
    """Format the full trace: summary + timeline.

    This is the primary entry point for trace inspection.
    """
    parts = [
        format_trace_summary(trace),
        "",
        format_trace_timeline(trace),
    ]
    return "\n".join(parts)
