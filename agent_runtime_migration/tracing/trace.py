"""In-memory, replayable run trace (deterministic)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List
from .events import RuntimeEvent


@dataclass
class RunTrace:
    run_id: str
    events: List[RuntimeEvent] = field(default_factory=list)
    _seq: int = 0

    def emit(self, type: str, **detail: Any) -> RuntimeEvent:
        ev = RuntimeEvent(seq=self._seq, type=type, detail=detail)
        self._seq += 1
        self.events.append(ev)
        return ev

    def types(self) -> List[str]:
        return [e.type for e in self.events]

    def to_dict(self) -> Dict[str, Any]:
        return {"run_id": self.run_id, "events": [e.to_dict() for e in self.events]}
