"""Deterministic runtime checkpoints.

A checkpoint is a serializable snapshot of runtime coordination state for one
workflow instance: task statuses, attempt counts, correlation, and the runtime
identity that produced it. It carries a content digest so a corrupted or tampered
checkpoint can be detected and rejected (fail closed) on recovery.

Checkpoints hold no credentials, no provider outputs, and no governance authority —
only coordination state needed to resume.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..models.task import TaskStatus
from ..models.workflow import WorkflowInstance, WorkflowStatus


def _digest(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class Checkpoint:
    instance_id: str
    workflow_id: str
    runtime_id: str
    runtime_version: str
    status: str
    tasks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    digest: str = ""

    @classmethod
    def of(
        cls,
        instance: WorkflowInstance,
        runtime_id: str,
        runtime_version: str,
    ) -> "Checkpoint":
        tasks = {
            tid: {"status": ti.status.value, "attempts": ti.attempts}
            for tid, ti in instance.tasks.items()
        }
        payload = {
            "instance_id": instance.instance_id,
            "workflow_id": instance.workflow_id,
            "runtime_id": runtime_id,
            "runtime_version": runtime_version,
            "status": instance.status.value,
            "tasks": tasks,
            "correlation_id": instance.correlation_id,
        }
        return cls(digest=_digest(payload), **payload)

    def payload(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "workflow_id": self.workflow_id,
            "runtime_id": self.runtime_id,
            "runtime_version": self.runtime_version,
            "status": self.status,
            "tasks": self.tasks,
            "correlation_id": self.correlation_id,
        }

    def verify(self) -> bool:
        return self.digest == _digest(self.payload())

    def to_dict(self) -> Dict[str, Any]:
        d = self.payload()
        d["digest"] = self.digest
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Checkpoint":
        return cls(
            instance_id=d["instance_id"],
            workflow_id=d["workflow_id"],
            runtime_id=d["runtime_id"],
            runtime_version=d["runtime_version"],
            status=d["status"],
            tasks=dict(d.get("tasks", {})),
            correlation_id=d.get("correlation_id"),
            digest=d.get("digest", ""),
        )
