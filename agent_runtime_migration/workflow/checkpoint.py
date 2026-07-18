"""Deterministic workflow checkpoint (serialize completed step ids + status)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Checkpoint:
    workflow_id: str
    completed: List[str] = field(default_factory=list)
    statuses: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"workflow_id": self.workflow_id, "completed": list(self.completed),
                "statuses": dict(self.statuses)}

    @classmethod
    def from_dict(cls, d: dict) -> "Checkpoint":
        return cls(workflow_id=d["workflow_id"], completed=list(d.get("completed", [])),
                   statuses=dict(d.get("statuses", {})))
