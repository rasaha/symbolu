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
from typing import Any, Dict, List, Optional, Tuple

from ..models.execution_state import (
    SUPPORTED_STATE_VERSIONS,
    CanonicalExecutionState,
    ExecutionLineage,
)
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
    # Additive (v1): the full trajectory journal, keyed by state_digest, so an event that
    # references a historical snapshot digest stays resolvable after restart (not only the
    # latest per task). Each entry is a self-verifying CanonicalExecutionState.to_dict().
    execution_state_journal: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Additive (v1): the typed lineage *source* (workflow-common + per-task), preserved
    # separately from historical snapshots so future snapshots after recovery keep the same
    # agent/artifact/causation references — including for tasks that had not yet run when
    # the checkpoint was written. Neutral references only; never authority.
    workflow_lineage: Optional[Dict[str, Any]] = None
    task_lineage: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def of(
        cls,
        instance: WorkflowInstance,
        runtime_id: str,
        runtime_version: str,
        execution_states: Optional[Dict[str, CanonicalExecutionState]] = None,
        execution_state_journal: Optional[Dict[str, CanonicalExecutionState]] = None,
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
        serialized_journal = {
            digest: state.to_dict()
            for digest, state in (execution_state_journal or {}).items()
        }
        return cls(
            digest=_digest(payload),
            checkpoint_version=CHECKPOINT_VERSION,
            execution_states=serialized_states,
            execution_state_journal=serialized_journal,
            workflow_lineage=(
                instance.lineage.to_dict() if instance.lineage is not None else None
            ),
            task_lineage={
                tid: ti.lineage.to_dict()
                for tid, ti in instance.tasks.items()
                if ti.lineage is not None
            },
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
        """True when every persisted canonical execution state is digest-intact.

        Empty (legacy or no-lineage) checkpoints are vacuously intact. A tampered state
        — fields changed without recomputing its ``state_digest``, or vice versa — fails
        closed. This is the digest-only self-check; :meth:`validate_execution_states` also
        enforces cross-object binding to this checkpoint."""
        ok, _ = self.validate_execution_states()
        return ok

    def _bind_errors(self, key: str, snap: Dict[str, Any], *, journal: bool) -> List[str]:
        """Cross-object binding + integrity checks for one persisted snapshot. Returns a
        list of human-readable reasons (empty when the snapshot is fully consistent)."""
        where = "journal" if journal else "execution_states"
        errs: List[str] = []
        # Version first, so an unknown schema version yields a precise reason rather than a
        # generic construction failure.
        version = snap.get("state_version")
        if version not in SUPPORTED_STATE_VERSIONS:
            return [f"{where}[{key!r}] unsupported state_version {version!r}"]
        try:
            state = CanonicalExecutionState.from_dict(snap)
        except Exception as exc:  # malformed persisted snapshot
            return [f"{where}[{key!r}] is not a valid canonical execution state: {exc}"]
        if not state.is_intact():
            errs.append(f"{where}[{key!r}] failed digest integrity")
        # The dictionary key must match the field it is keyed by (task_id for the latest
        # map, state_digest for the journal) — a mismatch is a swapped/relabeled snapshot.
        if journal:
            if key != state.state_digest:
                errs.append(f"journal key {key!r} != state_digest {state.state_digest!r}")
        else:
            if key != state.task_id:
                errs.append(f"execution_states key {key!r} != task_id {state.task_id!r}")
        # Bind identity to THIS checkpoint.
        if state.instance_id != self.instance_id:
            errs.append(f"{where}[{key!r}] instance_id {state.instance_id!r} != {self.instance_id!r}")
        if state.workflow_id != self.workflow_id:
            errs.append(f"{where}[{key!r}] workflow_id {state.workflow_id!r} != {self.workflow_id!r}")
        if state.runtime_id != self.runtime_id:
            errs.append(f"{where}[{key!r}] runtime_id {state.runtime_id!r} != {self.runtime_id!r}")
        if state.runtime_version != self.runtime_version:
            errs.append(f"{where}[{key!r}] runtime_version {state.runtime_version!r} != {self.runtime_version!r}")
        if state.correlation_id != self.correlation_id:
            errs.append(f"{where}[{key!r}] correlation_id {state.correlation_id!r} != {self.correlation_id!r}")
        if state.task_id is None or state.task_id not in self.tasks:
            errs.append(f"{where}[{key!r}] task_id {state.task_id!r} not present in checkpoint tasks")
        return errs

    def validate_execution_states(self) -> Tuple[bool, Optional[str]]:
        """Strictly validate the canonical execution-state lineage against THIS checkpoint.

        Beyond each snapshot's own digest, this enforces cross-object binding: the map key
        equals the snapshot's own key field; instance/workflow/runtime/correlation identity
        match the checkpoint; the referenced task exists; the schema version is supported.
        Returns ``(ok, reason)`` — a precise reason on the first failure. An inconsistent
        canonical state is never silently accepted or discarded.
        """
        reasons: List[str] = []
        for key, snap in self.execution_states.items():
            reasons += self._bind_errors(key, snap, journal=False)
        for key, snap in self.execution_state_journal.items():
            reasons += self._bind_errors(key, snap, journal=True)
        if reasons:
            return False, reasons[0]
        return True, None

    def canonical_execution_states(self) -> Dict[str, CanonicalExecutionState]:
        """Reconstruct the per-task (latest) canonical execution states (unverified —
        callers should have already run :meth:`validate_execution_states`)."""
        return {
            tid: CanonicalExecutionState.from_dict(snap)
            for tid, snap in self.execution_states.items()
        }

    def canonical_execution_journal(self) -> Dict[str, CanonicalExecutionState]:
        """Reconstruct the digest-keyed trajectory journal (unverified)."""
        return {
            digest: CanonicalExecutionState.from_dict(snap)
            for digest, snap in self.execution_state_journal.items()
        }

    def workflow_execution_lineage(self) -> Optional[ExecutionLineage]:
        """Reconstruct the workflow-common lineage source, if any was persisted."""
        if self.workflow_lineage is None:
            return None
        return ExecutionLineage.from_dict(self.workflow_lineage)

    def task_execution_lineage(self) -> Dict[str, ExecutionLineage]:
        """Reconstruct the per-task lineage source, keyed by task id."""
        return {
            tid: ExecutionLineage.from_dict(d) for tid, d in self.task_lineage.items()
        }

    def to_dict(self) -> Dict[str, Any]:
        d = self.payload()
        d["digest"] = self.digest
        d["checkpoint_version"] = self.checkpoint_version
        d["execution_states"] = self.execution_states
        d["execution_state_journal"] = self.execution_state_journal
        d["workflow_lineage"] = self.workflow_lineage
        d["task_lineage"] = self.task_lineage
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
            execution_state_journal=dict(d.get("execution_state_journal", {})),
            workflow_lineage=d.get("workflow_lineage"),
            task_lineage=dict(d.get("task_lineage", {})),
        )
