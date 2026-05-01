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
    ACTION_STARTED,
    ACTION_COMPLETED,
    TEXT_CHUNK,
    APPROVAL_REQUESTED,
    APPROVAL_RESOLVED,
    USAGE_UPDATED,
    BUDGET_EXCEEDED,
    DEADLINE_EXCEEDED,
    ACTION_TIMEOUT,
    APPROVAL_EXPIRED,
    SESSION_EXPIRED,
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

    # --- duration ---
    deadline_exceeded: bool = False
    action_timeouts: int = 0
    elapsed_s: float = 0.0
    max_run_duration_s: Optional[float] = None
    max_action_duration_s: Optional[float] = None

    # --- duration v2: approval expiry ---
    approvals_expired: int = 0
    max_approval_ttl_s: Optional[float] = None

    # --- duration v2: observability metrics ---
    time_to_first_action_s: Optional[float] = None
    time_to_first_approval_s: Optional[float] = None

    # --- duration v2: session TTL ---
    sessions_expired: int = 0
    session_expired_reason: Optional[str] = None

    # --- memory v2.5: retention counter ---
    memory_evictions: int = 0

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
            "deadline_exceeded": self.deadline_exceeded,
            "action_timeouts": self.action_timeouts,
            "elapsed_s": self.elapsed_s,
            "max_run_duration_s": self.max_run_duration_s,
            "max_action_duration_s": self.max_action_duration_s,
            "approvals_expired": self.approvals_expired,
            "max_approval_ttl_s": self.max_approval_ttl_s,
            "time_to_first_action_s": self.time_to_first_action_s,
            "time_to_first_approval_s": self.time_to_first_approval_s,
            "sessions_expired": self.sessions_expired,
            "session_expired_reason": self.session_expired_reason,
            "memory_evictions": self.memory_evictions,
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

    # Derive status from terminal event.  Scan backwards because
    # post-run events (e.g. STRUCTURED_VALIDATION) may be appended
    # after the terminal lifecycle event.
    if events:
        for _te in reversed(events):
            if _te.event_type == RUN_COMPLETED:
                trace.status = "completed"
                break
            elif _te.event_type == RUN_CANCELLED:
                trace.status = "cancelled"
                trace.cancelled = True
                break
            elif _te.event_type == RUN_ERROR:
                trace.status = "error"
                trace.error_occurred = True
                trace.error_message = _te.payload.get("error", "")
                break
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

    # Duration: deadline / action timeouts
    deadline_evts = [e for e in events if e.event_type == DEADLINE_EXCEEDED]
    timeout_evts = [e for e in events if e.event_type == ACTION_TIMEOUT]
    trace.deadline_exceeded = bool(deadline_evts)
    trace.action_timeouts = len(timeout_evts)

    # max_run_duration_s — taken from any DEADLINE_EXCEEDED payload that
    # carries it (the policy is otherwise opaque to the trace).
    for evt in deadline_evts:
        mrd = evt.payload.get("max_run_duration_s")
        if mrd is not None:
            trace.max_run_duration_s = mrd
            break

    # max_action_duration_s — taken from any ACTION_TIMEOUT payload.
    for evt in timeout_evts:
        mad = evt.payload.get("max_action_duration_s")
        if mad is not None:
            trace.max_action_duration_s = mad
            break

    # elapsed_s — prefer monotonic-precise value from a DEADLINE_EXCEEDED
    # event when present; otherwise fall back to a wall-clock derivation
    # from the first/last event ISO timestamps.
    if deadline_evts:
        trace.elapsed_s = float(deadline_evts[-1].payload.get("elapsed_s", 0.0))
    elif trace.started_at and trace.ended_at:
        try:
            from datetime import datetime
            _s = datetime.fromisoformat(trace.started_at)
            _e = datetime.fromisoformat(trace.ended_at)
            trace.elapsed_s = (_e - _s).total_seconds()
        except (ValueError, TypeError):
            trace.elapsed_s = 0.0

    if trace.deadline_exceeded and trace.status == "unknown":
        trace.status = "deadline_exceeded"

    # Memory v2.5 (M4) — read the per-run eviction counter from the
    # RUN_COMPLETED payload.  No new event is introduced; the agent
    # injects the value into the existing terminal payload.  Runs
    # that do not reach RUN_COMPLETED leave the field at its default
    # (0), which is the right answer for terminated runs where the
    # eviction count is not surfaced.
    for evt in events:
        if evt.event_type == RUN_COMPLETED:
            trace.memory_evictions = int(
                evt.payload.get("memory_evictions", 0) or 0
            )
            break

    # Duration v2: approval expiry
    expired_evts = [e for e in events if e.event_type == APPROVAL_EXPIRED]
    trace.approvals_expired = len(expired_evts)
    for evt in expired_evts:
        ttl = evt.payload.get("approval_ttl_s")
        if ttl is not None:
            trace.max_approval_ttl_s = ttl
            break

    # Duration v2: session TTL
    expired_session_evts = [
        e for e in events if e.event_type == SESSION_EXPIRED
    ]
    trace.sessions_expired = len(expired_session_evts)
    if expired_session_evts:
        trace.session_expired_reason = expired_session_evts[0].payload.get(
            "reason"
        )
        if trace.status == "unknown":
            trace.status = "session_expired"

    # Duration v2: observability metrics — wall-clock deltas from
    # RUN_STARTED to the first ACTION_STARTED / APPROVAL_REQUESTED.
    # Returns None when either anchor is missing. Negative values
    # (malformed event ordering) are clamped to 0.0 rather than swallowed
    # so the field still surfaces in dashboards; the caller can spot the
    # clamp by comparing event timestamps directly.
    trace.time_to_first_action_s = _first_event_delta_s(
        events, RUN_STARTED, ACTION_STARTED,
    )
    trace.time_to_first_approval_s = _first_event_delta_s(
        events, RUN_STARTED, APPROVAL_REQUESTED,
    )

    return trace


def _first_event_delta_s(
    events: List[AgentRunEvent],
    anchor_type: str,
    target_type: str,
) -> Optional[float]:
    """Return seconds from the first ``anchor_type`` event to the first
    ``target_type`` event, or ``None`` if either is absent.

    Negative deltas (target stamped before anchor — possible only via
    malformed event ordering) are clamped to 0.0. Unparseable ISO
    timestamps return ``None``.
    """
    anchor = next((e for e in events if e.event_type == anchor_type), None)
    target = next((e for e in events if e.event_type == target_type), None)
    if anchor is None or target is None:
        return None
    try:
        from datetime import datetime
        a = datetime.fromisoformat(anchor.timestamp)
        t = datetime.fromisoformat(target.timestamp)
    except (ValueError, TypeError):
        return None
    delta = (t - a).total_seconds()
    return delta if delta >= 0.0 else 0.0


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
