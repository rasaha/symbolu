"""Runtime result and failure value objects.

Expected runtime outcomes are represented as result objects, not exceptions, so
callers can inspect them deterministically. ``RuntimeFailure`` classifies a failure
without exposing raw backend exceptions as the public contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class FailureCategory(str, Enum):
    """Neutral, stable classification of a runtime-level failure."""

    PROVIDER_ERROR = "PROVIDER_ERROR"
    PROVIDER_NOT_FOUND = "PROVIDER_NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    GOVERNANCE_BLOCK = "GOVERNANCE_BLOCK"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    INTEGRITY = "INTEGRITY"
    CONFIGURATION = "CONFIGURATION"


@dataclass(frozen=True)
class RuntimeFailure:
    category: FailureCategory
    message: str
    task_id: Optional[str] = None
    reason_codes: tuple = ()
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "message": self.message,
            "task_id": self.task_id,
            "reason_codes": list(self.reason_codes),
            "detail": dict(self.detail),
        }


class WorkflowAdvanceStop(str, Enum):
    """Why one bounded advancement quantum stopped, at a stable runtime boundary.

    These are the ONLY places an external orchestrator may observe a workflow between
    quanta. Every value corresponds to a checkpointed or otherwise durable/stable
    runtime state — never a point inside the indivisible governance→exact-action→
    provider→transition→checkpoint chain.
    """

    #: One task advanced this quantum; the workflow is still RUNNING and MORE quanta
    #: are available (call ``advance_workflow`` again to continue).
    TASK_ADVANCED = "TASK_ADVANCED"
    #: The workflow reached COMPLETED this quantum (terminal).
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    #: The workflow reached FAILED this quantum (terminal) — provider failure or a
    #: governance BLOCK / exact-action integrity failure.
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    #: The workflow reached WAITING this quantum — a governance HOLD (no provider call,
    #: no authority created). Requires an explicit ``resume_workflow`` to re-arm.
    WORKFLOW_WAITING = "WORKFLOW_WAITING"
    #: The workflow reached PAUSED this quantum — a governance ESCALATE (no provider
    #: call). Requires an explicit ``resume_workflow`` to re-arm.
    WORKFLOW_PAUSED = "WORKFLOW_PAUSED"
    #: The workflow was cancelled this quantum (a cancellation token was observed).
    WORKFLOW_CANCELLED = "WORKFLOW_CANCELLED"
    #: No-op: the workflow was already terminal (COMPLETED / FAILED / CANCELLED). Nothing
    #: advanced.
    ALREADY_TERMINAL = "ALREADY_TERMINAL"
    #: No-op: the workflow is WAITING or PAUSED and needs an explicit ``resume_workflow``
    #: first — bounded advancement never self-resolves a restrictive governance
    #: disposition.
    REQUIRES_RESUME = "REQUIRES_RESUME"


@dataclass(frozen=True)
class WorkflowAdvanceOutcome:
    """The observable outcome of advancing a workflow by one bounded quantum.

    This is a read-only value object. It references runtime-owned canonical execution
    state by digest (``execution_state_digest``) and the emitted checkpoint by digest
    (``checkpoint_digest``) rather than duplicating either — the runtime remains the sole
    owner of execution-trajectory truth. ``stop_reason`` records the stable boundary the
    quantum stopped at (see :class:`WorkflowAdvanceStop`).
    """

    instance_id: str
    workflow_id: str
    status_before: str
    status_after: str
    stop_reason: str
    progressed: bool = False
    task_id: Optional[str] = None
    task_status: Optional[str] = None
    execution_state_digest: Optional[str] = None
    checkpoint_digest: Optional[str] = None
    terminal: bool = False
    waiting: bool = False
    paused: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "workflow_id": self.workflow_id,
            "status_before": self.status_before,
            "status_after": self.status_after,
            "stop_reason": self.stop_reason,
            "progressed": self.progressed,
            "task_id": self.task_id,
            "task_status": self.task_status,
            "execution_state_digest": self.execution_state_digest,
            "checkpoint_digest": self.checkpoint_digest,
            "terminal": self.terminal,
            "waiting": self.waiting,
            "paused": self.paused,
        }


@dataclass(frozen=True)
class RuntimeResult:
    """The outcome of a runtime coordination step or a completed workflow run.

    ``status`` is the workflow status string at the point the result was produced.
    ``failures`` lists any classified failures. ``output`` carries only what the
    caller asked the runtime to propagate (provider outputs are opaque to the
    runtime and are not reinterpreted).
    """

    instance_id: str
    workflow_id: str
    status: str
    completed_tasks: tuple = ()
    failures: tuple = ()
    output: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.failures

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "workflow_id": self.workflow_id,
            "status": self.status,
            "completed_tasks": list(self.completed_tasks),
            "failures": [f.to_dict() for f in self.failures],
            "metadata": dict(self.metadata),
        }
