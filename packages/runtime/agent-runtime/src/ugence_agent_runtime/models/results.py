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
