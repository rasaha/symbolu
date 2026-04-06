"""
Runtime Tracing — In-Memory Trace Capture (R11)

Captures ``AgentRunEvent`` instances from a streaming run into a
structured ``AgentRunTrace`` for post-run inspection.

No external backend, no OpenTelemetry — just an in-process trace
object that can be serialised to dict/JSON for logging or debugging.

Usage (one-shot)::

    result, trace = agent.run_with_trace("Hello")
    print(trace.summary)

Usage (manual collector)::

    collector = TraceCollector()
    for evt in agent.run_stream("Hello", trace_collector=collector):
        ...  # consume events
    trace = collector.build_trace()
    print(trace.event_count)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agentic.agentic_framework.streaming_events import (
    AgentRunEvent,
    RUN_STARTED,
    RUN_COMPLETED,
    RUN_ERROR,
    RUN_CANCELLED,
    SAFETY_GATE_RESULT,
    ACTION_COMPLETED,
    TEXT_CHUNK,
    APPROVAL_REQUESTED,
    APPROVAL_RESOLVED,
    USAGE_UPDATED,
    BUDGET_EXCEEDED,
)


# ---------------------------------------------------------------------------
# Trace model
# ---------------------------------------------------------------------------


@dataclass
class AgentRunTrace:
    """Immutable trace of a single agent run.

    Built from an ordered list of ``AgentRunEvent`` instances.
    Summary fields are derived from the events — no separate
    bookkeeping is needed.
    """

    events: List[AgentRunEvent] = field(default_factory=list)

    # Identifiers (populated from events if available)
    session_id: str = ""
    turn_id: int = -1

    # --- derived summary (populated by _compute_summary) ---
    status: str = "unknown"          # completed | cancelled | error | unknown
    event_count: int = 0
    started_at: str = ""
    ended_at: str = ""
    cancelled: bool = False
    error_occurred: bool = False
    error_message: str = ""
    safety_blocked: bool = False
    actions_executed: int = 0
    text_chunks: int = 0
    approvals_requested: int = 0
    approvals_denied: int = 0

    # --- usage / budget (R9) ---
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    budget_exceeded: bool = False
    accounting_mode: str = "none"

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-safe dict."""
        return {
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "status": self.status,
            "event_count": self.event_count,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "cancelled": self.cancelled,
            "error_occurred": self.error_occurred,
            "error_message": self.error_message,
            "safety_blocked": self.safety_blocked,
            "actions_executed": self.actions_executed,
            "text_chunks": self.text_chunks,
            "approvals_requested": self.approvals_requested,
            "approvals_denied": self.approvals_denied,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": self.estimated_cost,
            "budget_exceeded": self.budget_exceeded,
            "accounting_mode": self.accounting_mode,
            "events": [e.to_dict() for e in self.events],
        }

    @property
    def summary(self) -> Dict[str, Any]:
        """Return only the summary fields (no raw events)."""
        d = self.to_dict()
        d.pop("events", None)
        return d

    def has_event_type(self, event_type: str) -> bool:
        """Check whether the trace contains at least one event of *event_type*."""
        return any(e.event_type == event_type for e in self.events)

    def get_events(self, event_type: str) -> List[AgentRunEvent]:
        """Return all events matching *event_type*."""
        return [e for e in self.events if e.event_type == event_type]


def _build_trace(events: List[AgentRunEvent]) -> AgentRunTrace:
    """Construct an ``AgentRunTrace`` from a list of events."""
    trace = AgentRunTrace(events=list(events))
    trace.event_count = len(events)

    if events:
        trace.session_id = events[0].session_id
        trace.turn_id = events[0].turn_id
        trace.started_at = events[0].timestamp
        trace.ended_at = events[-1].timestamp

    # Derive status from terminal event
    if events:
        last = events[-1].event_type
        if last == RUN_COMPLETED:
            trace.status = "completed"
        elif last == RUN_CANCELLED:
            trace.status = "cancelled"
            trace.cancelled = True
        elif last == RUN_ERROR:
            trace.status = "error"
            trace.error_occurred = True
            trace.error_message = events[-1].payload.get("error", "")
        else:
            trace.status = "unknown"

    # Safety blocked?
    for evt in events:
        if evt.event_type == SAFETY_GATE_RESULT:
            if not evt.payload.get("eligible", True):
                trace.safety_blocked = True
            break

    # Count actions completed and text chunks
    trace.actions_executed = sum(
        1 for e in events
        if e.event_type == ACTION_COMPLETED
        and e.payload.get("status") == "completed"
    )
    trace.text_chunks = sum(1 for e in events if e.event_type == TEXT_CHUNK)

    # Count approval events (R4)
    trace.approvals_requested = sum(
        1 for e in events if e.event_type == APPROVAL_REQUESTED
    )
    trace.approvals_denied = sum(
        1 for e in events
        if e.event_type == APPROVAL_RESOLVED
        and not e.payload.get("approved", True)
    )

    # Usage / budget (R9) — take values from last USAGE_UPDATED event
    for evt in reversed(events):
        if evt.event_type == USAGE_UPDATED:
            trace.input_tokens = evt.payload.get("input_tokens", 0)
            trace.output_tokens = evt.payload.get("output_tokens", 0)
            trace.total_tokens = evt.payload.get("total_tokens", 0)
            trace.estimated_cost = evt.payload.get("estimated_cost", 0.0)
            trace.accounting_mode = evt.payload.get("accounting_mode", "none")
            break

    trace.budget_exceeded = any(
        e.event_type == BUDGET_EXCEEDED for e in events
    )
    if trace.budget_exceeded and trace.status == "unknown":
        trace.status = "budget_exceeded"

    return trace


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------


class TraceCollector:
    """Mutable event sink passed into ``run_stream`` / ``run_stream_async``.

    Events are appended as they are yielded.  After the run finishes,
    call :meth:`build_trace` to get the immutable ``AgentRunTrace``.
    """

    def __init__(self) -> None:
        self._events: List[AgentRunEvent] = []

    def record(self, event: AgentRunEvent) -> None:
        """Append an event to the collector."""
        self._events.append(event)

    @property
    def events(self) -> List[AgentRunEvent]:
        """Events collected so far (mutable reference)."""
        return self._events

    def build_trace(self) -> AgentRunTrace:
        """Build an ``AgentRunTrace`` from collected events."""
        return _build_trace(self._events)

    def __len__(self) -> int:
        return len(self._events)
