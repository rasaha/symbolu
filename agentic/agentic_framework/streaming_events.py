"""
Streaming Events — Runtime Event Model (R1/R2/R4/R6/R9)

Lightweight structured events emitted by ``AgenticLLMWrapper.run_stream()``
and ``run_stream_async()`` to surface agent lifecycle progress to callers
without breaking the existing ``run()`` contract.

Event categories:
    Lifecycle (R1):  run_started, generation_started, text_chunk,
        generation_completed, safety_gate_result, action_started,
        action_completed, run_completed, run_error
    Revision (R1):   revision_started, revision_completed
    Cancellation (R2): run_cancelled
    Approval (R4):   approval_requested, approval_resolved
    Structured (R6): structured_validation
    Budget (R9):     usage_updated, budget_exceeded
    Duration:        deadline_exceeded, action_timeout
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional


# ---------------------------------------------------------------------------
# Event type literals
# ---------------------------------------------------------------------------

RUN_STARTED = "run_started"
GENERATION_STARTED = "generation_started"
TEXT_CHUNK = "text_chunk"
GENERATION_COMPLETED = "generation_completed"
SAFETY_GATE_RESULT = "safety_gate_result"
ACTION_STARTED = "action_started"
ACTION_COMPLETED = "action_completed"
RUN_COMPLETED = "run_completed"
RUN_ERROR = "run_error"
RUN_CANCELLED = "run_cancelled"
REVISION_STARTED = "revision_started"
REVISION_COMPLETED = "revision_completed"
STRUCTURED_VALIDATION = "structured_validation"
APPROVAL_REQUESTED = "approval_requested"
APPROVAL_RESOLVED = "approval_resolved"
USAGE_UPDATED = "usage_updated"
BUDGET_EXCEEDED = "budget_exceeded"
DEADLINE_EXCEEDED = "deadline_exceeded"
ACTION_TIMEOUT = "action_timeout"
APPROVAL_EXPIRED = "approval_expired"


# ---------------------------------------------------------------------------
# Core event model
# ---------------------------------------------------------------------------


@dataclass
class AgentRunEvent:
    """Single structured event emitted during a streaming agent run.

    Fields:
        event_type: One of the event-type constants above.
        timestamp: ISO-8601 UTC string.
        turn_id: Turn index within the session (matches ``AgentResult.turn_id``).
        session_id: Session identifier (matches ``AgentResult.session_id``).
        payload: Arbitrary serialisable dict carrying event-specific data.
    """

    event_type: str
    timestamp: str
    turn_id: int
    session_id: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (JSON-safe)."""
        return asdict(self)


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def make_event(
    event_type: str,
    turn_id: int,
    session_id: str,
    payload: Optional[Dict[str, Any]] = None,
) -> AgentRunEvent:
    """Convenience factory for ``AgentRunEvent``."""
    return AgentRunEvent(
        event_type=event_type,
        timestamp=_now_iso(),
        turn_id=turn_id,
        session_id=session_id,
        payload=payload or {},
    )
