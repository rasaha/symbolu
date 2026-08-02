"""Deterministic runtime state transitions.

This module is the single authority on which task/workflow status changes are
legal. The engine consults it before every state change; an illegal change raises
``InvalidTransitionError``. Keeping the transition tables here (rather than inline
in the engine) makes the state machine auditable and machine-readable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet

from ..runtime.errors import InvalidTransitionError
from .task import TaskStatus
from .workflow import WorkflowStatus

# --- Task transition table -------------------------------------------------
VALID_TASK_TRANSITIONS: Dict[TaskStatus, FrozenSet[TaskStatus]] = {
    TaskStatus.PENDING: frozenset(
        {TaskStatus.READY, TaskStatus.SKIPPED, TaskStatus.CANCELLED}
    ),
    TaskStatus.READY: frozenset(
        {TaskStatus.RUNNING, TaskStatus.WAITING, TaskStatus.CANCELLED, TaskStatus.FAILED}
    ),
    TaskStatus.RUNNING: frozenset(
        {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.WAITING,
            TaskStatus.CANCELLED,
            TaskStatus.READY,  # retry re-arms the task
        }
    ),
    TaskStatus.WAITING: frozenset(
        {TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.FAILED}
    ),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
    TaskStatus.SKIPPED: frozenset(),
}

# --- Workflow transition table ---------------------------------------------
VALID_WORKFLOW_TRANSITIONS: Dict[WorkflowStatus, FrozenSet[WorkflowStatus]] = {
    WorkflowStatus.CREATED: frozenset({WorkflowStatus.READY, WorkflowStatus.CANCELLED}),
    WorkflowStatus.READY: frozenset(
        {WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED}
    ),
    WorkflowStatus.RUNNING: frozenset(
        {
            WorkflowStatus.PAUSED,
            WorkflowStatus.WAITING,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        }
    ),
    WorkflowStatus.PAUSED: frozenset(
        {WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED, WorkflowStatus.FAILED}
    ),
    WorkflowStatus.WAITING: frozenset(
        {WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED, WorkflowStatus.FAILED}
    ),
    WorkflowStatus.COMPLETED: frozenset(),
    WorkflowStatus.FAILED: frozenset(),
    WorkflowStatus.CANCELLED: frozenset(),
}


def is_valid_task_transition(src: TaskStatus, dst: TaskStatus) -> bool:
    return dst in VALID_TASK_TRANSITIONS.get(src, frozenset())


def is_valid_workflow_transition(src: WorkflowStatus, dst: WorkflowStatus) -> bool:
    return dst in VALID_WORKFLOW_TRANSITIONS.get(src, frozenset())


def check_task_transition(src: TaskStatus, dst: TaskStatus) -> None:
    if src is dst:
        return
    if not is_valid_task_transition(src, dst):
        raise InvalidTransitionError(
            f"illegal task transition {src.value} -> {dst.value}"
        )


def check_workflow_transition(src: WorkflowStatus, dst: WorkflowStatus) -> None:
    if src is dst:
        return
    if not is_valid_workflow_transition(src, dst):
        raise InvalidTransitionError(
            f"illegal workflow transition {src.value} -> {dst.value}"
        )


@dataclass(frozen=True)
class RuntimeTransition:
    """A recorded, deterministic state change for one entity (task or workflow)."""

    entity: str  # "task" | "workflow"
    entity_id: str
    from_status: str
    to_status: str
    reason: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity,
            "entity_id": self.entity_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "reason": self.reason,
            "detail": dict(self.detail),
        }
