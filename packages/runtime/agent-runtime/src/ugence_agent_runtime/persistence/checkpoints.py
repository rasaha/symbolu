"""Deterministic runtime checkpoints.

A checkpoint is a serializable snapshot of runtime coordination state for one
workflow instance: task statuses, attempt counts, correlation, and the runtime
identity that produced it. It carries a content digest so a corrupted or tampered
checkpoint can be detected and rejected (fail closed) on recovery.

Checkpoints hold no credentials, no provider outputs, and no governance authority —
only coordination state needed to resume.

## Compatibility discipline for canonical execution-state lineage

Canonical execution-state lineage (``execution_states``) is an **additive** section
introduced with ``checkpoint_version`` ``"1"``. The base ``digest`` continues to be
computed over exactly the original coordination payload (instance/workflow/runtime
identity, status, tasks, correlation) and **only** that payload — so checkpoints
written before this field existed verify byte-identically and their digest semantics
are unchanged. A checkpoint deserialized without ``checkpoint_version`` is treated as
legacy version ``"0"`` and simply carries no execution-state lineage (unavailable,
never fabricated). Each persisted execution state is *self-verifying* via its own
``state_digest``; :meth:`verify_execution_states` fails closed on any tampering.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..models.execution_state import CanonicalExecutionState
from ..models.task import TaskStatus
from ..models.workflow import WorkflowInstance, WorkflowStatus

# Current checkpoint schema version. "0" denotes a legacy checkpoint deserialized
# without a version tag (no execution-state lineage).
CHECKPOINT_VERSION = "1"
LEGACY_CHECKPOINT_VERSION = "0"


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
    # Additive (v1): per-task canonical execution-state lineage, each entry a
    # self-verifying CanonicalExecutionState.to_dict(). Intentionally EXCLUDED from the
    # base ``digest`` so legacy digest semantics are preserved; integrity of this section
    # is checked separately via each state's own state_digest.
    checkpoint_version: str = CHECKPOINT_VERSION
    execution_states: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def of(
        cls,
        instance: WorkflowInstance,
        runtime_id: str,
        runtime_version: str,
        execution_states: Optional[Dict[str, CanonicalExecutionState]] = None,
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
        serialized_states = {
            tid: state.to_dict()
            for tid, state in (execution_states or {}).items()
        }
        return cls(
            digest=_digest(payload),
            checkpoint_version=CHECKPOINT_VERSION,
            execution_states=serialized_states,
            **payload,
        )

    def payload(self) -> Dict[str, Any]:
        # The base digest payload — unchanged across the v1 addition on purpose.
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

    def verify_execution_states(self) -> bool:
        """True when every persisted canonical execution state is intact.

        Empty (legacy or no-lineage) checkpoints are vacuously intact. A tampered state
        — fields changed without recomputing its ``state_digest``, or vice versa — fails
        closed."""
        for snap in self.execution_states.values():
            if not CanonicalExecutionState.from_dict(snap).is_intact():
                return False
        return True

    def canonical_execution_states(self) -> Dict[str, CanonicalExecutionState]:
        """Reconstruct the per-task canonical execution states (unverified — callers
        should have already run :meth:`verify_execution_states`)."""
        return {
            tid: CanonicalExecutionState.from_dict(snap)
            for tid, snap in self.execution_states.items()
        }

    def to_dict(self) -> Dict[str, Any]:
        d = self.payload()
        d["digest"] = self.digest
        d["checkpoint_version"] = self.checkpoint_version
        d["execution_states"] = self.execution_states
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
            # Absent version tag => legacy checkpoint with no execution-state lineage.
            checkpoint_version=d.get("checkpoint_version", LEGACY_CHECKPOINT_VERSION),
            execution_states=dict(d.get("execution_states", {})),
        )
