"""Runtime recovery — reconstruct coordination state from persisted records.

Invariants (preserved deliberately):
  * recovery reconstructs state ONLY from persisted runtime records;
  * recovery performs NO external provider call automatically;
  * recovery performs NO governance call automatically;
  * previously RUNNING work returns in a state requiring explicit continuation;
  * COMPLETED work does not rerun; CANCELLED work does not restart;
  * a runtime-identity / configuration mismatch is reported, not silently accepted;
  * checkpoint corruption fails closed;
  * recovery never fabricates provider success.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..models.task import TaskInstance, TaskStatus
from ..models.workflow import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)
from ..runtime.errors import RecoveryError
from .checkpoints import Checkpoint


@dataclass(frozen=True)
class RuntimeRecoveryResult:
    instance: WorkflowInstance
    resumed_from_status: str
    requires_continuation: bool
    config_mismatch: bool = False
    notes: tuple = field(default_factory=tuple)


def recover_instance(
    checkpoint: Checkpoint,
    definition: WorkflowDefinition,
    runtime_id: str,
    runtime_version: str,
) -> RuntimeRecoveryResult:
    """Rebuild a ``WorkflowInstance`` from a checkpoint and the (caller-supplied)
    original definition. No provider or governance calls are made here."""
    if checkpoint is None:
        raise RecoveryError("no checkpoint available for recovery")
    if not checkpoint.verify():
        # Corrupted / tampered checkpoint: fail closed.
        raise RecoveryError(
            f"checkpoint for instance {checkpoint.instance_id!r} failed integrity check"
        )
    if checkpoint.workflow_id != definition.workflow_id:
        raise RecoveryError(
            "checkpoint workflow_id does not match supplied definition"
        )

    notes: List[str] = []
    config_mismatch = False
    if checkpoint.runtime_id != runtime_id or checkpoint.runtime_version != runtime_version:
        config_mismatch = True
        notes.append(
            "runtime identity/version mismatch: checkpoint "
            f"{checkpoint.runtime_id}@{checkpoint.runtime_version} vs "
            f"{runtime_id}@{runtime_version}"
        )

    instance = WorkflowInstance.create(
        instance_id=checkpoint.instance_id,
        definition=definition,
        correlation_id=checkpoint.correlation_id,
    )

    requires_continuation = False
    for task_id, snap in checkpoint.tasks.items():
        if task_id not in instance.tasks:
            raise RecoveryError(
                f"checkpoint references unknown task {task_id!r} for workflow "
                f"{definition.workflow_id!r}"
            )
        ti: TaskInstance = instance.tasks[task_id]
        try:
            persisted = TaskStatus(snap["status"])
        except (KeyError, ValueError) as exc:
            raise RecoveryError(f"corrupt task status for {task_id!r}: {exc}") from exc
        ti.attempts = int(snap.get("attempts", 0))

        # RUNNING (and WAITING) work must NOT auto-resume: it returns in a state
        # that requires explicit continuation. Completed/cancelled remain terminal.
        if persisted is TaskStatus.RUNNING:
            ti.status = TaskStatus.READY
            requires_continuation = True
            notes.append(f"task {task_id} was RUNNING; re-armed to READY for explicit continuation")
        else:
            ti.status = persisted

    # Reconstruct workflow status; any non-terminal instance requires an explicit
    # continuation step rather than auto-running.
    try:
        wf_status = WorkflowStatus(checkpoint.status)
    except ValueError as exc:
        raise RecoveryError(f"corrupt workflow status: {exc}") from exc

    if wf_status in (WorkflowStatus.RUNNING, WorkflowStatus.READY):
        instance.status = WorkflowStatus.PAUSED
        requires_continuation = True
        notes.append(
            f"workflow was {wf_status.value}; recovered as PAUSED pending explicit continuation"
        )
    else:
        instance.status = wf_status
        if wf_status in (WorkflowStatus.PAUSED, WorkflowStatus.WAITING):
            requires_continuation = True

    return RuntimeRecoveryResult(
        instance=instance,
        resumed_from_status=checkpoint.status,
        requires_continuation=requires_continuation,
        config_mismatch=config_mismatch,
        notes=tuple(notes),
    )
