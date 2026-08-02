"""In-memory, replayable run trace (deterministic).

The trace owns a monotonic ``seq`` counter (not a wall clock), so an event stream is
fully deterministic and replayable. Emitting an event optionally forwards it to an
injected event sink; the trace never performs I/O itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..models.events import RuntimeEvent

EventSink = Callable[[RuntimeEvent], None]


@dataclass
class RunTrace:
    instance_id: str
    events: List[RuntimeEvent] = field(default_factory=list)
    _seq: int = 0
    sink: Optional[EventSink] = None

    def emit(self, type: str, **detail: Any) -> RuntimeEvent:
        event = RuntimeEvent(seq=self._seq, type=type, detail=detail)
        self._seq += 1
        self.events.append(event)
        if self.sink is not None:
            self.sink(event)
        return event

    def types(self) -> List[str]:
        return [e.type for e in self.events]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "events": [e.to_dict() for e in self.events],
        }


def format_trace(trace: RunTrace) -> str:
    lines = [f"instance {trace.instance_id}"]
    for e in trace.events:
        lines.append(f"  [{e.seq:02d}] {e.type} {e.detail}")
    return "\n".join(lines)
