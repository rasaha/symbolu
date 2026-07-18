"""Runtime event model (deterministic; no wall clock)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict

RUN_STARTED = "RUN_STARTED"
PLANNED = "PLANNED"
ACTION_SELECTED = "ACTION_SELECTED"
CER_PROPOSED = "CER_PROPOSED"
GOVERNANCE_DECISION = "GOVERNANCE_DECISION"
ACTION_EXECUTED = "ACTION_EXECUTED"
ACTION_BLOCKED = "ACTION_BLOCKED"
OBSERVED = "OBSERVED"
REFLECTED = "REFLECTED"
HUMAN_REQUESTED = "HUMAN_REQUESTED"
RUN_COMPLETED = "RUN_COMPLETED"
RUN_CANCELLED = "RUN_CANCELLED"
BUDGET_EXCEEDED = "BUDGET_EXCEEDED"


@dataclass(frozen=True)
class RuntimeEvent:
    seq: int
    type: str
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"seq": self.seq, "type": self.type, "detail": self.detail}
