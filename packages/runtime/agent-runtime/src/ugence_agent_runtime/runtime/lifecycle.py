"""Terminal-status helpers for tasks and workflows.

Kept separate from the model modules so callers have one import surface for "is this
done?" questions without reaching into enum internals.
"""
from __future__ import annotations

from ..models.task import TERMINAL_TASK_STATUSES, TaskStatus
from ..models.workflow import TERMINAL_WORKFLOW_STATUSES, WorkflowStatus


def is_task_terminal(status: TaskStatus) -> bool:
    return status in TERMINAL_TASK_STATUSES


def is_workflow_terminal(status: WorkflowStatus) -> bool:
    return status in TERMINAL_WORKFLOW_STATUSES
