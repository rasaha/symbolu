"""Workflow model — an ordered set of tasks with dependencies.

Deterministic ordering is preserved: a task becomes READY only when every task it
depends on has COMPLETED, and among ready tasks the runtime picks in registration
order. This mirrors the established runtime's deterministic dependency scheduling.

A workflow instance carries only runtime coordination state. It does not own policy,
authorization, or governance authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .task import TaskDefinition, TaskInstance, TaskStatus


class WorkflowStatus(str, Enum):
    """The runtime-owned lifecycle of a workflow.

    WAITING reflects a governance HOLD on a task (external resolution required, no
    authority created). PAUSED reflects either an explicit pause or a governance
    ESCALATE (external authority/review required). Neither is a terminal state.
    """

    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_WORKFLOW_STATUSES = frozenset(
    {WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED}
)


@dataclass(frozen=True)
class WorkflowDefinition:
    """Immutable declaration of a single workflow (one dependency graph of tasks).

    This is intentionally a *single* workflow. Multi-workflow orchestration
    (dependency graphs across workflows, cross-workflow aggregation) is explicitly
    out of scope for this package and is a future H22 feature phase.
    """

    workflow_id: str
    tasks: Tuple[TaskDefinition, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.workflow_id or not isinstance(self.workflow_id, str):
            raise ValueError("WorkflowDefinition.workflow_id required")
        ids = [t.task_id for t in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("WorkflowDefinition task ids must be unique")
        known = set(ids)
        for t in self.tasks:
            for dep in t.depends_on:
                if dep not in known:
                    raise ValueError(
                        f"task {t.task_id!r} depends on unknown task {dep!r}"
                    )


@dataclass
class WorkflowInstance:
    """Mutable runtime state for one running workflow."""

    instance_id: str
    definition: WorkflowDefinition
    status: WorkflowStatus = WorkflowStatus.CREATED
    tasks: Dict[str, TaskInstance] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        instance_id: str,
        definition: WorkflowDefinition,
        correlation_id: Optional[str] = None,
    ) -> "WorkflowInstance":
        tasks = {t.task_id: TaskInstance(definition=t) for t in definition.tasks}
        return cls(
            instance_id=instance_id,
            definition=definition,
            status=WorkflowStatus.CREATED,
            tasks=tasks,
            correlation_id=correlation_id,
        )

    @property
    def workflow_id(self) -> str:
        return self.definition.workflow_id

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_WORKFLOW_STATUSES

    def task(self, task_id: str) -> TaskInstance:
        return self.tasks[task_id]

    def ready_task(self) -> Optional[TaskInstance]:
        """Return the next task whose dependencies are all COMPLETED, in
        deterministic registration order, or None if none is currently runnable."""
        completed = {
            tid for tid, ti in self.tasks.items() if ti.status is TaskStatus.COMPLETED
        }
        for definition in self.definition.tasks:
            ti = self.tasks[definition.task_id]
            if ti.status not in (TaskStatus.PENDING, TaskStatus.READY):
                continue
            if all(dep in completed for dep in definition.depends_on):
                return ti
        return None

    def remaining_tasks(self) -> List[TaskInstance]:
        return [ti for ti in self.tasks.values() if not ti.is_terminal]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "correlation_id": self.correlation_id,
            "tasks": {tid: ti.to_dict() for tid, ti in self.tasks.items()},
            "metadata": dict(self.metadata),
        }
