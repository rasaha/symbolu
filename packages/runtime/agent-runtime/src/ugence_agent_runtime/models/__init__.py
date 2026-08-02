"""Domain-neutral runtime models."""
from __future__ import annotations

from .agent import AgentDescriptor
from .events import EVENT_TYPES, RuntimeEvent
from .proposal import TransitionProposal, compute_fingerprint
from .results import FailureCategory, RuntimeFailure, RuntimeResult
from .task import (
    TERMINAL_TASK_STATUSES,
    TaskDefinition,
    TaskInstance,
    TaskStatus,
)
from .transitions import (
    RuntimeTransition,
    check_task_transition,
    check_workflow_transition,
    is_valid_task_transition,
    is_valid_workflow_transition,
)
from .workflow import (
    TERMINAL_WORKFLOW_STATUSES,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)

__all__ = [
    "AgentDescriptor",
    "RuntimeEvent",
    "EVENT_TYPES",
    "TransitionProposal",
    "compute_fingerprint",
    "FailureCategory",
    "RuntimeFailure",
    "RuntimeResult",
    "TaskDefinition",
    "TaskInstance",
    "TaskStatus",
    "TERMINAL_TASK_STATUSES",
    "WorkflowDefinition",
    "WorkflowInstance",
    "WorkflowStatus",
    "TERMINAL_WORKFLOW_STATUSES",
    "RuntimeTransition",
    "check_task_transition",
    "check_workflow_transition",
    "is_valid_task_transition",
    "is_valid_workflow_transition",
]
