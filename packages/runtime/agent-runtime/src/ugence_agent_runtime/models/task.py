"""Task model — a single unit of coordinated work within a workflow.

A task wraps an operation the runtime may request a provider to execute. Whether a
task is *consequential* (must pass the governance boundary before execution)
is declared on the definition; the runtime never re-decides that classification.

Nothing here creates authority, authorizes execution, or authors policy. The task
carries only runtime coordination state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class TaskStatus(str, Enum):
    """The runtime-owned lifecycle of a single task.

    WAITING is entered when governance returns HOLD (no authority is created); the
    task is neither complete nor failed and requires an external resolution before
    it can proceed. SKIPPED is reserved for a task whose dependencies made it
    unreachable under deterministic ordering.
    """

    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


TERMINAL_TASK_STATUSES = frozenset(
    {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.SKIPPED}
)


@dataclass(frozen=True)
class TaskDefinition:
    """Immutable declaration of one task.

    ``consequential`` marks a task whose execution is a consequential transition
    that MUST be offered to the governance boundary before a provider is invoked.
    ``provider_id`` selects a registered provider; ``operation`` is the neutral
    operation type the provider understands.
    """

    task_id: str
    operation: str
    provider_id: Optional[str] = None
    consequential: bool = True
    arguments: Dict[str, Any] = field(default_factory=dict)
    depends_on: Tuple[str, ...] = ()
    timeout: Optional[float] = None
    max_attempts: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id or not isinstance(self.task_id, str):
            raise ValueError("TaskDefinition.task_id required")
        if not self.operation or not isinstance(self.operation, str):
            raise ValueError("TaskDefinition.operation required")
        if self.max_attempts < 1:
            raise ValueError("TaskDefinition.max_attempts must be >= 1")


@dataclass
class TaskInstance:
    """Mutable runtime state for one task within a workflow instance."""

    definition: TaskDefinition
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    result: Optional[Any] = None
    failure: Optional[Any] = None
    governance_reference: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def task_id(self) -> str:
        return self.definition.task_id

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_TASK_STATUSES

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "attempts": self.attempts,
            "governance_reference": self.governance_reference,
            "metadata": dict(self.metadata),
        }
