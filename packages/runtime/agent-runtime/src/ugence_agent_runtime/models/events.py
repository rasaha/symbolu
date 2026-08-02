"""Neutral runtime event model (deterministic; no wall clock).

Events describe coordination facts only. They never carry credentials, raw prompts,
secret tool arguments, private customer evidence, or full provider responses by
default. The event ``seq`` is a monotonic counter owned by the emitting trace, not
a timestamp, so event streams are deterministic and replayable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

# Canonical neutral event types (see docs/AGENT_RUNTIME_STATE_MODEL.md).
RUNTIME_CREATED = "RUNTIME_CREATED"
WORKFLOW_CREATED = "WORKFLOW_CREATED"
WORKFLOW_STARTED = "WORKFLOW_STARTED"
TASK_READY = "TASK_READY"
TASK_STARTED = "TASK_STARTED"
GOVERNANCE_EVALUATION_REQUESTED = "GOVERNANCE_EVALUATION_REQUESTED"
GOVERNANCE_DISPOSITION_RECEIVED = "GOVERNANCE_DISPOSITION_RECEIVED"
PROVIDER_INVOKED = "PROVIDER_INVOKED"
PROVIDER_COMPLETED = "PROVIDER_COMPLETED"
TASK_COMPLETED = "TASK_COMPLETED"
TASK_FAILED = "TASK_FAILED"
TASK_WAITING = "TASK_WAITING"
WORKFLOW_PAUSED = "WORKFLOW_PAUSED"
WORKFLOW_RESUMED = "WORKFLOW_RESUMED"
WORKFLOW_WAITING = "WORKFLOW_WAITING"
WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
WORKFLOW_FAILED = "WORKFLOW_FAILED"
WORKFLOW_CANCELLED = "WORKFLOW_CANCELLED"
CHECKPOINT_COMMITTED = "CHECKPOINT_COMMITTED"
RECOVERY_PERFORMED = "RECOVERY_PERFORMED"

EVENT_TYPES = (
    RUNTIME_CREATED,
    WORKFLOW_CREATED,
    WORKFLOW_STARTED,
    TASK_READY,
    TASK_STARTED,
    GOVERNANCE_EVALUATION_REQUESTED,
    GOVERNANCE_DISPOSITION_RECEIVED,
    PROVIDER_INVOKED,
    PROVIDER_COMPLETED,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_WAITING,
    WORKFLOW_PAUSED,
    WORKFLOW_RESUMED,
    WORKFLOW_WAITING,
    WORKFLOW_COMPLETED,
    WORKFLOW_FAILED,
    WORKFLOW_CANCELLED,
    CHECKPOINT_COMMITTED,
    RECOVERY_PERFORMED,
)


@dataclass(frozen=True)
class RuntimeEvent:
    seq: int
    type: str
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"seq": self.seq, "type": self.type, "detail": dict(self.detail)}
