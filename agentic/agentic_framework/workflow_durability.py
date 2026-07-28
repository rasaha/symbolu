"""
Durable Workflow State, Checkpointing & Recovery (H18)
======================================================

Adds **deterministic, local** durability to the H17 event-driven workflow
runtime: a waiting workflow can serialize its complete recoverable state,
survive destruction of the runtime process, restore into a new runtime, reject
duplicate events, and resume from the exact prior point with an equivalent
outcome and a single reconstructable history.

```
Mission → Execute → WAIT → Checkpoint → (process destroyed) → Restore
       → Event → Resume → Complete
```

H18 owns **persistence, restoration, idempotency, and recovery only**.  It does
not modify H10–H17, RunBudget, WorkingMemory, hierarchical planning,
coordination, replanning, plan validity, governance, authorization, ActionGate,
TAP, tool execution, or model providers — it composes on their public APIs and
serializes their state through the accessors they already expose.

This is **local deterministic durability**, not a distributed workflow service.
It is not Kafka/queues/cloud databases/leader-election/consensus, and it does
not provide exactly-once external execution or production-grade fault tolerance.

Excluded by design: distributed queues, cloud databases, webhooks, leader
election, multi-node execution, consensus, cross-region replication, production
DB adapters, pickle-based persistence.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, replace as dc_replace
from typing import Any, Callable, Dict, List, Optional, Tuple

# --- H11–H17 public types (read/reconstructed, never modified) ---
from agentic.agentic_framework.run_budget import (
    RunBudget, RunBudgetLimits, RunBudgetUsage, RunBudgetStatus, BudgetViolation,
)
from agentic.agentic_framework.working_memory import (
    WorkingMemory, MemoryRecord, MemoryStatusTransition, ExpirationPolicy, MemoryOperation,
)
from agentic.agentic_framework.plan_validity import (
    PlanAssumption, AssumptionTransition, AssumptionRegistry,
    AssumptionDependencyGraph, AssumptionContext,
)
from agentic.agentic_framework.hierarchical_planning import (
    Goal, GoalNode, GoalTransition, GoalTree, MissionPlan, GoalStatus,
)
from agentic.agentic_framework.coordination import CapabilityRegistry, AuthorityModel
from agentic.agentic_framework.event_workflows import (
    WorkflowInstance, WorkflowEngine, WorkflowStatus, WaitCondition,
    WorkflowEvent, WorkflowTransition, WorkflowTraceEntry,
)

__all__ = [
    "SCHEMA_VERSION",
    "EventOutcome",
    "AssignmentRecoveryStatus",
    "TransactionState",
    "FaultPoint",
    "RecoveryError",
    "CheckpointConflict",
    "canonical_json",
    "digest_of",
    "WorkflowCheckpoint",
    "CheckpointSerializer",
    "CheckpointIntegrityValidator",
    "CheckpointStore",
    "InMemoryCheckpointStore",
    "FileCheckpointStore",
    "EventTransaction",
    "RecoveryJournal",
    "RecoveryResult",
    "WorkflowRestorer",
    "FaultInjector",
    "DurableWorkflowEngine",
    "format_recovery_trace",
]

SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
class EventOutcome:
    EVENT_APPLIED = "EVENT_APPLIED"
    DUPLICATE_EVENT_IGNORED = "DUPLICATE_EVENT_IGNORED"


class AssignmentRecoveryStatus:
    NOT_STARTED = "NOT_STARTED"
    STARTED_NO_RESULT = "STARTED_NO_RESULT"
    RESULT_RECORDED = "RESULT_RECORDED"
    OUTPUT_COMMITTED = "OUTPUT_COMMITTED"
    #: Conservative resolution when a started action has no durable result.
    REQUIRES_RECONCILIATION = "REQUIRES_RECONCILIATION"


class TransactionState:
    PREPARED = "PREPARED"
    APPLIED = "APPLIED"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class FaultPoint:
    BEFORE_SERIALIZE = "before_serialize"
    AFTER_SERIALIZE = "after_serialize"
    AFTER_EVENT_VALIDATION = "after_event_validation"
    AFTER_EVENT_EFFECTS = "after_event_effects"
    BEFORE_COMMIT = "before_commit"
    AFTER_COMMIT = "after_commit"
    DURING_RESTORE = "during_restore"
    DURING_REBIND = "during_rebind"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class RecoveryError(Exception):
    """A deterministic, fail-closed recovery error carrying a stable code."""

    CHECKPOINT_CORRUPT = "CHECKPOINT_CORRUPT"
    CHECKPOINT_SCHEMA_UNSUPPORTED = "CHECKPOINT_SCHEMA_UNSUPPORTED"
    CHECKPOINT_INVARIANT_VIOLATION = "CHECKPOINT_INVARIANT_VIOLATION"
    RECOVERY_DEPENDENCY_UNAVAILABLE = "RECOVERY_DEPENDENCY_UNAVAILABLE"

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {message}" if message else code)


class CheckpointConflict(Exception):
    """Raised by compare-and-save when a stale writer loses the race."""

    CODE = "CHECKPOINT_CONFLICT"

    def __init__(self, message: str = "") -> None:
        self.code = self.CODE
        super().__init__(f"{self.CODE}: {message}" if message else self.CODE)


# ---------------------------------------------------------------------------
# Canonical serialization
# ---------------------------------------------------------------------------
def _canonicalize(obj: Any) -> Any:
    """Recursively convert to a canonical, JSON-safe structure.

    Sets → sorted lists, tuples → lists, dict keys sorted at dump time.  No
    object addresses, no code, no pickle.
    """
    if isinstance(obj, dict):
        return {str(k): _canonicalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canonicalize(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(_canonicalize(v) for v in obj)
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    if isinstance(obj, float):
        return obj
    # Fall back to a stable string form for anything exotic (should not occur
    # for well-formed checkpoint payloads).
    return str(obj)


def canonical_json(obj: Any) -> str:
    """Deterministic canonical JSON: stable key + collection ordering."""
    return json.dumps(_canonicalize(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_of(canonical_str: str) -> str:
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Snapshot: H11–H17 live state → canonical dicts (read-only)
# ---------------------------------------------------------------------------
def _snapshot_budget(rb: Optional[RunBudget]) -> Optional[Dict[str, Any]]:
    if rb is None:
        return None
    return {
        "limits": rb.limits.to_dict(),
        "usage": rb.usage.to_dict(),
        "status": rb.status,
        "termination_reason": rb.termination_reason,
        "violations": [
            {"dimension": v.dimension, "reason": v.reason, "limit": v.limit,
             "consumed": v.consumed, "requested": v.requested,
             "usage_snapshot": v.usage_snapshot}
            for v in rb.violations
        ],
    }


def _snapshot_memory(mem: WorkingMemory) -> Dict[str, Any]:
    return {
        "records": {key: [r.to_dict() for r in mem.records(key)] for key in mem.keys()},
        "operations": mem.trace.to_list(),
        "trace_seq": mem.trace._seq,
    }


def _snapshot_assumptions(ctx: Optional[AssumptionContext]) -> Optional[Dict[str, Any]]:
    if ctx is None:
        return None
    return {
        "assumptions": {a.assumption_id: a.to_dict() for a in ctx.registry.all()},
        "graph": {sid: sorted(ctx.graph.assumptions_for_step(sid)) for sid in
                  sorted({s for s in ctx.graph._step_to_assumptions})},
        "trace": ctx.trace.to_list(),
        "iteration": ctx._iteration,
    }


def _snapshot_coordination(wf: WorkflowInstance) -> Dict[str, Any]:
    """Durable coordination state needed to continue safely.

    In-flight status per leaf: a completed goal is OUTPUT_COMMITTED; an
    EXECUTING goal captured mid-run is STARTED_NO_RESULT (unknown); everything
    else is NOT_STARTED.  Explicit markers in recovery_metadata override.
    """
    assignments = []
    for node in wf.tree.leaves():
        st = node.status
        if st == GoalStatus.COMPLETED:
            inflight = AssignmentRecoveryStatus.OUTPUT_COMMITTED
        elif st == GoalStatus.EXECUTING:
            inflight = AssignmentRecoveryStatus.STARTED_NO_RESULT
        else:
            inflight = AssignmentRecoveryStatus.NOT_STARTED
        assignments.append({
            "goal_id": node.goal.goal_id,
            "agent": node.assigned_agent,
            "goal_status": st,
            "inflight": inflight,
        })
    return {"assignments": assignments}


def _snapshot_workflow_body(wf: WorkflowInstance) -> Dict[str, Any]:
    """The full durable state of a workflow (excluding checkpoint framing)."""
    return {
        "workflow_status": wf.status,
        "current_goal": wf.current_goal,
        "mission_id": wf.plan.mission_id,
        "goal_tree": wf.tree.to_dict(),
        "working_memory": _snapshot_memory(wf.memory),
        "assumptions": _snapshot_assumptions(wf.assumption_context),
        "run_budget": _snapshot_budget(wf.run_budget),
        "coordination": _snapshot_coordination(wf),
        "wait_by_goal": [wc.to_dict() for wc in wf.wait_by_goal.values()],
        "wait_conditions_active": [wc.to_dict() for wc in wf.waiting_conditions],
        "wait_conditions_satisfied": sorted(wf.satisfied),
        "processed_event_ids": [e.event_id for e in wf.event_log],
        "workflow_history": [t.to_dict() for t in wf.history],
        "workflow_trace": wf.trace.to_list(),
        "trace_seq": wf.trace._seq,
        "wave": wf._wave,
        "created_at": wf.created_at,
        "resumed_at": wf.resumed_at,
    }


# ---------------------------------------------------------------------------
# Reconstruction: canonical dicts → H11–H17 objects
# ---------------------------------------------------------------------------
def _restore_budget(data: Optional[Dict[str, Any]]) -> Optional[RunBudget]:
    if data is None:
        return None
    limits = RunBudgetLimits(**data["limits"])
    rb = RunBudget(limits, clock=lambda: 0.0)
    rb._usage = RunBudgetUsage(**data["usage"])
    rb._status = data["status"]
    rb._termination_reason = data.get("termination_reason")
    rb._violations = [
        BudgetViolation(dimension=v["dimension"], reason=v["reason"], limit=v["limit"],
                        consumed=v["consumed"], requested=v["requested"],
                        usage_snapshot=v.get("usage_snapshot", {}))
        for v in data.get("violations", [])
    ]
    rb._start_time = None  # suspended wall-clock is not counted (see H11 semantics)
    return rb


def _restore_memory_record(d: Dict[str, Any]) -> MemoryRecord:
    exp = d.get("expiration") or {}
    rec = MemoryRecord(
        record_id=d["record_id"], key=d["key"], category=d["category"], value=d["value"],
        version=d["version"], provenance=d.get("provenance", ""), confidence=d.get("confidence", 1.0),
        status=d["status"], created_at=d.get("created_at", 0.0), updated_at=d.get("updated_at", 0.0),
        expiration=ExpirationPolicy(kind=exp.get("kind", "never"), ttl=exp.get("ttl"),
                                    step_id=exp.get("step_id"), assumption_id=exp.get("assumption_id")),
        producing_step=d.get("producing_step"),
        consuming_steps=list(d.get("consuming_steps", [])),
    )
    rec.status_history = [
        MemoryStatusTransition(t["from_state"], t["to_state"], t.get("reason", ""), t.get("timestamp", 0.0))
        for t in d.get("status_history", [])
    ]
    return rec


def _restore_memory(data: Dict[str, Any]) -> WorkingMemory:
    mem = WorkingMemory()
    for key, recs in data["records"].items():
        mem._versions[key] = [_restore_memory_record(r) for r in recs]
    # Rebuild the operation log verbatim (append-only, deterministic).
    mem.trace.operations = [
        MemoryOperation(seq=o["seq"], op=o["op"], key=o["key"], version=o.get("version"),
                        record_id=o.get("record_id"), step=o.get("step"),
                        timestamp=o.get("timestamp", 0.0), detail=o.get("detail", ""))
        for o in data.get("operations", [])
    ]
    mem.trace._seq = data.get("trace_seq", len(mem.trace.operations))
    return mem


def _restore_assumptions(data: Optional[Dict[str, Any]]) -> Optional[AssumptionContext]:
    if data is None:
        return None
    registry = AssumptionRegistry()
    for aid, d in data["assumptions"].items():
        a = PlanAssumption(
            assumption_id=d["assumption_id"], description=d["description"], category=d.get("category", "general"),
            state=d["state"], confidence=d.get("confidence", 1.0), evidence=list(d.get("evidence", [])),
            mandatory=d.get("mandatory", False), recoverable=d.get("recoverable", True),
            created_at=d.get("created_at", 0.0), last_validated_at=d.get("last_validated_at"),
            metadata=dict(d.get("metadata", {})),
        )
        a.history = [
            AssumptionTransition(t["from_state"], t["to_state"], t.get("reason", ""),
                                 list(t.get("evidence", [])), t.get("confidence", 1.0), t.get("timestamp", 0.0))
            for t in d.get("history", [])
        ]
        registry.add(a)
    graph = AssumptionDependencyGraph()
    for sid, aids in data.get("graph", {}).items():
        for aid in aids:
            graph.add(sid, aid)
    ctx = AssumptionContext(registry, graph)
    ctx._iteration = data.get("iteration", 0)
    return ctx


def _restore_goal(d: Dict[str, Any]) -> Goal:
    return Goal(
        goal_id=d["goal_id"], description=d["description"], parent=d.get("parent"),
        children=tuple(d.get("children", [])), priority=d.get("priority", 0),
        dependencies=tuple(d.get("dependencies", [])), assumptions=tuple(d.get("assumptions", [])),
        required_memory=tuple(d.get("required_memory", [])), produced_memory=tuple(d.get("produced_memory", [])),
        completion_criteria=d.get("completion_criteria", ""), mandatory=d.get("mandatory", True),
        goal_type=d.get("goal_type", ""), required_capabilities=frozenset(d.get("required_capabilities", [])),
        authority_scope=frozenset(d.get("authority_scope", [])), expected_outputs=tuple(d.get("expected_outputs", [])),
    )


def _restore_tree(data: Dict[str, Any]) -> GoalTree:
    tree = GoalTree()
    for gid, nd in data["nodes"].items():
        goal = _restore_goal(nd["goal"])
        node = GoalNode(goal=goal, status=nd["status"], assigned_agent=nd.get("assigned_agent"))
        node.history = [
            GoalTransition(t["from_status"], t["to_status"], t.get("reason", ""), t.get("timestamp", 0.0))
            for t in nd.get("history", [])
        ]
        # Restore metadata (e.g. inserted markers) onto the frozen goal.
        node.goal = dc_replace(node.goal)  # ensure a distinct instance
        tree._nodes[gid] = node
    tree.root_ids = list(data.get("root_ids", []))
    return tree


def _restore_wait(d: Dict[str, Any]) -> WaitCondition:
    return WaitCondition(
        condition_id=d["condition_id"], goal_id=d["goal_id"], kind=d.get("kind", "WAIT_FOR_EVENT"),
        event_type=d.get("event_type", ""), match=tuple(tuple(kv) for kv in d.get("match", {}).items()),
        min_confidence=d.get("min_confidence", 0.0), on_timeout=d.get("on_timeout", "satisfy"),
        description=d.get("description", ""),
    )


# ---------------------------------------------------------------------------
# WorkflowCheckpoint (immutable)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class WorkflowCheckpoint:
    """An immutable, self-describing durable snapshot of a workflow."""

    checkpoint_id: str
    workflow_id: str
    checkpoint_sequence: int
    schema_version: int
    logical_sequence: int
    created_at: float
    parent_checkpoint_id: Optional[str]
    body: Dict[str, Any]                 # the durable workflow state
    recovery_metadata: Dict[str, Any] = field(default_factory=dict)
    integrity_digest: str = ""

    def payload(self) -> Dict[str, Any]:
        """The canonical content the digest is computed over (excludes digest)."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "workflow_id": self.workflow_id,
            "checkpoint_sequence": self.checkpoint_sequence,
            "schema_version": self.schema_version,
            "logical_sequence": self.logical_sequence,
            "created_at": self.created_at,
            "parent_checkpoint_id": self.parent_checkpoint_id,
            "body": self.body,
            "recovery_metadata": self.recovery_metadata,
        }

    def compute_digest(self) -> str:
        return digest_of(canonical_json(self.payload()))

    def with_digest(self) -> "WorkflowCheckpoint":
        return dc_replace(self, integrity_digest=self.compute_digest())

    def to_dict(self) -> Dict[str, Any]:
        d = self.payload()
        d["integrity_digest"] = self.integrity_digest
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorkflowCheckpoint":
        return cls(
            checkpoint_id=d["checkpoint_id"], workflow_id=d["workflow_id"],
            checkpoint_sequence=d["checkpoint_sequence"], schema_version=d["schema_version"],
            logical_sequence=d["logical_sequence"], created_at=d["created_at"],
            parent_checkpoint_id=d.get("parent_checkpoint_id"), body=d["body"],
            recovery_metadata=d.get("recovery_metadata", {}), integrity_digest=d.get("integrity_digest", ""),
        )


class CheckpointSerializer:
    """Canonical, safe (JSON) checkpoint serialization."""

    def dumps(self, checkpoint: WorkflowCheckpoint) -> str:
        return canonical_json(checkpoint.to_dict())

    def loads(self, text: str) -> WorkflowCheckpoint:
        return WorkflowCheckpoint.from_dict(json.loads(text))


# ---------------------------------------------------------------------------
# Integrity validation
# ---------------------------------------------------------------------------
class CheckpointIntegrityValidator:
    """Fail-closed validation of a checkpoint before it is trusted."""

    REQUIRED = ("checkpoint_id", "workflow_id", "checkpoint_sequence", "schema_version",
                "logical_sequence", "body", "integrity_digest")

    def validate(self, checkpoint: WorkflowCheckpoint, *, expected_workflow_id: Optional[str] = None) -> None:
        d = checkpoint.to_dict()
        for f in self.REQUIRED:
            if f not in d or d[f] is None and f != "integrity_digest":
                raise RecoveryError(RecoveryError.CHECKPOINT_CORRUPT, f"missing field '{f}'")
        if checkpoint.schema_version != SCHEMA_VERSION:
            raise RecoveryError(RecoveryError.CHECKPOINT_SCHEMA_UNSUPPORTED,
                                f"schema {checkpoint.schema_version} != {SCHEMA_VERSION}")
        if checkpoint.compute_digest() != checkpoint.integrity_digest:
            raise RecoveryError(RecoveryError.CHECKPOINT_CORRUPT, "integrity digest mismatch")
        if expected_workflow_id is not None and checkpoint.workflow_id != expected_workflow_id:
            raise RecoveryError(RecoveryError.CHECKPOINT_INVARIANT_VIOLATION, "workflow identity mismatch")
        if checkpoint.checkpoint_sequence < 0 or checkpoint.logical_sequence < 0:
            raise RecoveryError(RecoveryError.CHECKPOINT_INVARIANT_VIOLATION, "negative sequence")
        body = checkpoint.body
        # Goal-tree acyclicity.
        try:
            tree = _restore_tree(body["goal_tree"])
            tree.validate_acyclic()
        except RecoveryError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise RecoveryError(RecoveryError.CHECKPOINT_INVARIANT_VIOLATION, f"goal tree: {exc}")
        # Budget counters nonnegative.
        rb = body.get("run_budget")
        if rb is not None:
            for k, v in rb.get("usage", {}).items():
                if isinstance(v, (int, float)) and v < 0:
                    raise RecoveryError(RecoveryError.CHECKPOINT_INVARIANT_VIOLATION, f"negative budget {k}")


# ---------------------------------------------------------------------------
# Checkpoint store
# ---------------------------------------------------------------------------
class CheckpointStore:
    """Strategy-agnostic durable checkpoint store (no workflow logic)."""

    def save(self, checkpoint: WorkflowCheckpoint) -> None:
        raise NotImplementedError

    def load(self, checkpoint_id: str) -> WorkflowCheckpoint:
        raise NotImplementedError

    def load_latest(self, workflow_id: str) -> Optional[WorkflowCheckpoint]:
        raise NotImplementedError

    def list_checkpoints(self, workflow_id: str) -> List[str]:
        raise NotImplementedError

    def latest_id(self, workflow_id: str) -> Optional[str]:
        raise NotImplementedError

    def compare_and_save(self, checkpoint: WorkflowCheckpoint, *, expected_latest_id: Optional[str]) -> None:
        """Optimistic concurrency: save only if the current latest matches."""
        current = self.latest_id(checkpoint.workflow_id)
        if current != expected_latest_id:
            raise CheckpointConflict(
                f"expected latest {expected_latest_id!r} but store has {current!r}")
        self.save(checkpoint)

    def mark_superseded(self, checkpoint_id: str) -> None:
        raise NotImplementedError

    def verify_integrity(self, checkpoint_id: str, *, validator: Optional[CheckpointIntegrityValidator] = None) -> None:
        (validator or CheckpointIntegrityValidator()).validate(self.load(checkpoint_id))


class InMemoryCheckpointStore(CheckpointStore):
    def __init__(self) -> None:
        self._by_id: Dict[str, WorkflowCheckpoint] = {}
        self._by_workflow: Dict[str, List[str]] = {}
        self._latest: Dict[str, str] = {}
        self._superseded: set = set()

    def save(self, checkpoint: WorkflowCheckpoint) -> None:
        cp = checkpoint if checkpoint.integrity_digest else checkpoint.with_digest()
        self._by_id[cp.checkpoint_id] = cp
        self._by_workflow.setdefault(cp.workflow_id, []).append(cp.checkpoint_id)
        self._latest[cp.workflow_id] = cp.checkpoint_id

    def load(self, checkpoint_id: str) -> WorkflowCheckpoint:
        if checkpoint_id not in self._by_id:
            raise RecoveryError(RecoveryError.CHECKPOINT_CORRUPT, f"no checkpoint {checkpoint_id}")
        return self._by_id[checkpoint_id]

    def load_latest(self, workflow_id: str) -> Optional[WorkflowCheckpoint]:
        cid = self._latest.get(workflow_id)
        return self._by_id[cid] if cid else None

    def list_checkpoints(self, workflow_id: str) -> List[str]:
        return list(self._by_workflow.get(workflow_id, []))

    def latest_id(self, workflow_id: str) -> Optional[str]:
        return self._latest.get(workflow_id)

    def mark_superseded(self, checkpoint_id: str) -> None:
        self._superseded.add(checkpoint_id)


class FileCheckpointStore(CheckpointStore):
    """Deterministic filesystem-backed store (canonical JSON files).

    Layout: ``<root>/<workflow_id>/<sequence>-<checkpoint_id>.json`` plus a
    ``LATEST`` pointer file.  No pickle, no executable content.
    """

    def __init__(self, root: str, *, serializer: Optional[CheckpointSerializer] = None) -> None:
        self.root = root
        self.serializer = serializer or CheckpointSerializer()
        os.makedirs(root, exist_ok=True)

    def _wf_dir(self, workflow_id: str) -> str:
        d = os.path.join(self.root, workflow_id)
        os.makedirs(d, exist_ok=True)
        return d

    def save(self, checkpoint: WorkflowCheckpoint) -> None:
        cp = checkpoint if checkpoint.integrity_digest else checkpoint.with_digest()
        wf_dir = self._wf_dir(cp.workflow_id)
        fname = f"{cp.checkpoint_sequence:08d}-{cp.checkpoint_id}.json"
        with open(os.path.join(wf_dir, fname), "w", encoding="utf-8") as fh:
            fh.write(self.serializer.dumps(cp))
        with open(os.path.join(wf_dir, "LATEST"), "w", encoding="utf-8") as fh:
            fh.write(cp.checkpoint_id)

    def _path_for(self, workflow_id: str, checkpoint_id: str) -> Optional[str]:
        wf_dir = self._wf_dir(workflow_id)
        for name in sorted(os.listdir(wf_dir)):
            if name.endswith(".json") and name.rsplit("-", 1)[-1] == f"{checkpoint_id}.json":
                return os.path.join(wf_dir, name)
        return None

    def load(self, checkpoint_id: str) -> WorkflowCheckpoint:
        for wf in sorted(os.listdir(self.root)):
            path = self._path_for(wf, checkpoint_id)
            if path:
                with open(path, encoding="utf-8") as fh:
                    return self.serializer.loads(fh.read())
        raise RecoveryError(RecoveryError.CHECKPOINT_CORRUPT, f"no checkpoint {checkpoint_id}")

    def load_latest(self, workflow_id: str) -> Optional[WorkflowCheckpoint]:
        cid = self.latest_id(workflow_id)
        return self.load(cid) if cid else None

    def latest_id(self, workflow_id: str) -> Optional[str]:
        p = os.path.join(self._wf_dir(workflow_id), "LATEST")
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as fh:
            return fh.read().strip() or None

    def list_checkpoints(self, workflow_id: str) -> List[str]:
        wf_dir = self._wf_dir(workflow_id)
        return [n.rsplit("-", 1)[-1][:-5] for n in sorted(os.listdir(wf_dir)) if n.endswith(".json")]

    def mark_superseded(self, checkpoint_id: str) -> None:
        pass  # files retained for history; LATEST pointer conveys currency


# ---------------------------------------------------------------------------
# Recovery journal (append-only event transaction record)
# ---------------------------------------------------------------------------
@dataclass
class EventTransaction:
    txn_id: str
    workflow_id: str
    event_id: str
    source_checkpoint_id: Optional[str]
    logical_sequence: int
    state: str = TransactionState.PREPARED
    target_checkpoint_id: Optional[str] = None
    memory_effects: List[str] = field(default_factory=list)
    assumption_effects: Dict[str, str] = field(default_factory=dict)
    wait_conditions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "txn_id": self.txn_id, "workflow_id": self.workflow_id, "event_id": self.event_id,
            "source_checkpoint_id": self.source_checkpoint_id, "target_checkpoint_id": self.target_checkpoint_id,
            "logical_sequence": self.logical_sequence, "state": self.state,
            "memory_effects": list(self.memory_effects), "assumption_effects": dict(self.assumption_effects),
            "wait_conditions": list(self.wait_conditions),
        }


class RecoveryJournal:
    """Append-only record of event transactions for deterministic resolution."""

    def __init__(self) -> None:
        self.transactions: List[EventTransaction] = []

    def begin(self, wf: WorkflowInstance, event: WorkflowEvent, *, source_checkpoint_id: Optional[str],
              logical_sequence: int) -> EventTransaction:
        txn = EventTransaction(
            txn_id=f"txn:{wf.workflow_id}:{event.event_id}", workflow_id=wf.workflow_id,
            event_id=event.event_id, source_checkpoint_id=source_checkpoint_id, logical_sequence=logical_sequence,
            memory_effects=[w.key for w in event.memory_writes] + list(event.memory_invalidations),
            assumption_effects=dict(event.assumption_signals),
        )
        self.transactions.append(txn)
        return txn

    def applied(self, txn: EventTransaction) -> None:
        txn.state = TransactionState.APPLIED

    def committed(self, txn: EventTransaction, target_checkpoint_id: str) -> None:
        txn.state = TransactionState.COMMITTED
        txn.target_checkpoint_id = target_checkpoint_id

    def aborted(self, txn: EventTransaction) -> None:
        txn.state = TransactionState.ABORTED

    def pending(self) -> List[EventTransaction]:
        return [t for t in self.transactions if t.state in (TransactionState.PREPARED, TransactionState.APPLIED)]

    def to_list(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self.transactions]


# ---------------------------------------------------------------------------
# Fault injection (deterministic, for tests)
# ---------------------------------------------------------------------------
class FaultInjector:
    """Arms a single deterministic fault at a named :class:`FaultPoint`."""

    class InjectedFault(Exception):
        pass

    def __init__(self, point: Optional[str] = None) -> None:
        self.point = point
        self.fired = False

    def check(self, point: str) -> None:
        if self.point == point and not self.fired:
            self.fired = True
            raise FaultInjector.InjectedFault(point)


# ---------------------------------------------------------------------------
# Recovery result
# ---------------------------------------------------------------------------
@dataclass
class RecoveryResult:
    outcome: str
    workflow: Optional[WorkflowInstance] = None
    checkpoint: Optional[WorkflowCheckpoint] = None
    reconciliation: List[str] = field(default_factory=list)   # goal ids needing reconciliation
    detail: str = ""


# ---------------------------------------------------------------------------
# Restore engine
# ---------------------------------------------------------------------------
class WorkflowRestorer:
    """Reconstructs a runnable :class:`WorkflowInstance` from a checkpoint.

    Rebinds live runtime dependencies (registry / engine / replanner) — the
    checkpoint stores durable state only.  Fails deterministically when a
    required dependency is missing (``RECOVERY_DEPENDENCY_UNAVAILABLE``) or the
    checkpoint is invalid (integrity / schema / invariant errors).
    """

    def __init__(self, validator: Optional[CheckpointIntegrityValidator] = None,
                 fault: Optional[FaultInjector] = None) -> None:
        self.validator = validator or CheckpointIntegrityValidator()
        self.fault = fault

    def restore(self, checkpoint: WorkflowCheckpoint, *, registry: CapabilityRegistry,
                subtree_replanner: Optional[Callable] = None,
                authority: Optional[AuthorityModel] = None) -> RecoveryResult:
        if registry is None:
            raise RecoveryError(RecoveryError.RECOVERY_DEPENDENCY_UNAVAILABLE, "capability registry required")
        self.validator.validate(checkpoint)
        if self.fault:
            self.fault.check(FaultPoint.DURING_RESTORE)
        body = checkpoint.body

        tree = _restore_tree(body["goal_tree"])
        plan = MissionPlan(mission_id=body["mission_id"], tree=tree)
        memory = _restore_memory(body["working_memory"])
        ctx = _restore_assumptions(body.get("assumptions"))
        budget = _restore_budget(body.get("run_budget"))

        if self.fault:
            self.fault.check(FaultPoint.DURING_REBIND)

        wait_conditions = [_restore_wait(d) for d in body.get("wait_by_goal", [])]
        wf = WorkflowInstance(
            checkpoint.workflow_id, plan, memory, assumption_context=ctx, run_budget=budget,
            wait_conditions=wait_conditions, created_at=body.get("created_at", 0.0),
        )
        wf.status = body["workflow_status"]
        wf.current_goal = body.get("current_goal")
        wf.satisfied = set(body.get("wait_conditions_satisfied", []))
        wf.waiting_conditions = [_restore_wait(d) for d in body.get("wait_conditions_active", [])]
        wf.resumed_at = body.get("resumed_at")
        wf._wave = body.get("wave", 0)
        wf.history = [
            WorkflowTransition(t["from_status"], t["to_status"], t.get("reason", ""), t.get("timestamp", 0.0))
            for t in body.get("workflow_history", [])
        ]
        wf.trace.entries = [
            WorkflowTraceEntry(e["seq"], e["kind"], e.get("detail", {}), e.get("timestamp", 0.0))
            for e in body.get("workflow_trace", [])
        ]
        wf.trace._seq = body.get("trace_seq", len(wf.trace.entries))
        # Processed-event ids survive restart for cross-restart idempotency.
        wf._processed_event_ids = set(body.get("processed_event_ids", []))  # H18 attribute (not H17)

        # Unknown in-flight work: never auto-replay a started-no-result action.
        reconciliation: List[str] = []
        for a in body.get("coordination", {}).get("assignments", []):
            if a.get("inflight") == AssignmentRecoveryStatus.STARTED_NO_RESULT:
                node = tree.lookup(a["goal_id"])
                node.transition(GoalStatus.BLOCKED,
                                reason=AssignmentRecoveryStatus.REQUIRES_RECONCILIATION)
                reconciliation.append(a["goal_id"])

        return RecoveryResult(outcome="RESTORED", workflow=wf, checkpoint=checkpoint,
                              reconciliation=reconciliation)


# ---------------------------------------------------------------------------
# Durable workflow engine (composes the unchanged H17 engine)
# ---------------------------------------------------------------------------
class DurableWorkflowEngine:
    """H17 workflow engine + durable checkpointing, idempotency, and recovery.

    Composes an unmodified :class:`WorkflowEngine` for execution and adds
    checkpoints at recovery boundaries, cross-restart event idempotency, an
    atomic (journal-backed) event transaction, and optimistic-concurrency
    saves.  The H17 engine, coordinator, and all lower layers are unchanged.
    """

    def __init__(self, registry: CapabilityRegistry, store: CheckpointStore, *,
                 subtree_replanner: Optional[Callable] = None, authority: Optional[AuthorityModel] = None,
                 fault: Optional[FaultInjector] = None) -> None:
        self.registry = registry
        self.store = store
        self.subtree_replanner = subtree_replanner
        self.authority = authority
        self.fault = fault
        self.engine = WorkflowEngine(registry, authority=authority, subtree_replanner=subtree_replanner)
        self.journal = RecoveryJournal()
        self.serializer = CheckpointSerializer()
        self._seq: Dict[str, int] = {}
        self._logical: Dict[str, int] = {}

    # ----- workflow start -----
    def create_workflow(self, workflow_id: str, plan: MissionPlan, memory: WorkingMemory, *,
                        assumption_context: Optional[AssumptionContext] = None,
                        run_budget: Optional[RunBudget] = None,
                        wait_conditions: Optional[List[WaitCondition]] = None,
                        created_at: float = 0.0) -> WorkflowInstance:
        wf = self.engine.create_workflow(workflow_id, plan, memory,
                                         assumption_context=assumption_context, run_budget=run_budget,
                                         wait_conditions=wait_conditions, created_at=created_at)
        wf._processed_event_ids = set()  # H18 dedup set (not part of H17)
        self._seq[workflow_id] = 0
        self._logical[workflow_id] = 0
        self.engine.start(wf)                       # H17: run until WAIT / terminal
        self._checkpoint(wf, reason="after_start")  # boundary: created + reached WAIT/terminal
        return wf

    # ----- durable event delivery (atomic, idempotent) -----
    def deliver(self, wf: WorkflowInstance, event: WorkflowEvent) -> RecoveryResult:
        processed = getattr(wf, "_processed_event_ids", set())
        if event.event_id in processed:
            wf.trace.record("DUPLICATE_EVENT_IGNORED", {"event_id": event.event_id}, event.timestamp)
            return RecoveryResult(outcome=EventOutcome.DUPLICATE_EVENT_IGNORED, workflow=wf,
                                  detail="event already processed")

        if self.fault:
            self.fault.check(FaultPoint.AFTER_EVENT_VALIDATION)

        source_id = self.store.latest_id(wf.workflow_id)
        self._logical[wf.workflow_id] = self._logical.get(wf.workflow_id, 0) + 1
        txn = self.journal.begin(wf, event, source_checkpoint_id=source_id,
                                 logical_sequence=self._logical[wf.workflow_id])
        try:
            # The whole H17 deliver (validate → memory → assumptions → wait →
            # resume) is the atomic effect-application unit.
            affected = self.engine.deliver(event, to=wf)
            if not affected:
                # Non-matching event: workflow stays WAITING; nothing durable to do.
                self.journal.aborted(txn)
                return RecoveryResult(outcome="NO_MATCH", workflow=wf, detail="event did not match")
            if self.fault:
                self.fault.check(FaultPoint.AFTER_EVENT_EFFECTS)
            processed.add(event.event_id)
            wf._processed_event_ids = processed
            self.journal.applied(txn)

            if self.fault:
                self.fault.check(FaultPoint.BEFORE_COMMIT)
            checkpoint = self._checkpoint(wf, reason="after_event", parent_id=source_id,
                                          expected_latest_id=source_id)
            self.journal.committed(txn, checkpoint.checkpoint_id)
            if self.fault:
                self.fault.check(FaultPoint.AFTER_COMMIT)
            return RecoveryResult(outcome=EventOutcome.EVENT_APPLIED, workflow=wf, checkpoint=checkpoint)
        except (FaultInjector.InjectedFault, Exception) as exc:
            # Durable state was NOT advanced past `source_id`; the event is not
            # in the persisted processed-set, so it is safe to retry after
            # restore.  The live (discarded) instance may be partially mutated.
            self.journal.aborted(txn)
            raise

    # ----- checkpointing -----
    def _checkpoint(self, wf: WorkflowInstance, *, reason: str, parent_id: Optional[str] = None,
                    expected_latest_id: Optional[str] = "__unset__") -> WorkflowCheckpoint:
        if self.fault:
            self.fault.check(FaultPoint.BEFORE_SERIALIZE)
        seq = self._seq.get(wf.workflow_id, 0)
        self._seq[wf.workflow_id] = seq + 1
        logical = self._logical.get(wf.workflow_id, 0)
        parent = parent_id if parent_id is not None else self.store.latest_id(wf.workflow_id)
        checkpoint = WorkflowCheckpoint(
            checkpoint_id=f"{wf.workflow_id}#c{seq}",
            workflow_id=wf.workflow_id, checkpoint_sequence=seq, schema_version=SCHEMA_VERSION,
            logical_sequence=logical, created_at=wf.resumed_at or wf.created_at,
            parent_checkpoint_id=parent, body=_snapshot_workflow_body(wf),
            recovery_metadata={"reason": reason},
        ).with_digest()
        if self.fault:
            self.fault.check(FaultPoint.AFTER_SERIALIZE)
        wf.trace.record("CHECKPOINTED", {"checkpoint_id": checkpoint.checkpoint_id, "reason": reason},
                        checkpoint.created_at)
        if expected_latest_id == "__unset__":
            self.store.save(checkpoint)
        else:
            self.store.compare_and_save(checkpoint, expected_latest_id=expected_latest_id)
        return checkpoint

    def checkpoint(self, wf: WorkflowInstance, *, reason: str = "manual") -> WorkflowCheckpoint:
        return self._checkpoint(wf, reason=reason)

    # ----- restore into this (new) runtime -----
    @classmethod
    def restore(cls, store: CheckpointStore, workflow_id: str, *, registry: CapabilityRegistry,
                subtree_replanner: Optional[Callable] = None, authority: Optional[AuthorityModel] = None,
                checkpoint_id: Optional[str] = None,
                fault: Optional[FaultInjector] = None) -> Tuple["DurableWorkflowEngine", WorkflowInstance]:
        """Restore a workflow into a brand-new durable engine (new runtime)."""
        checkpoint = store.load(checkpoint_id) if checkpoint_id else store.load_latest(workflow_id)
        if checkpoint is None:
            raise RecoveryError(RecoveryError.CHECKPOINT_CORRUPT, f"no checkpoint for {workflow_id}")
        restorer = WorkflowRestorer(fault=fault)
        result = restorer.restore(checkpoint, registry=registry, subtree_replanner=subtree_replanner,
                                  authority=authority)
        wf = result.workflow

        engine = cls(registry, store, subtree_replanner=subtree_replanner, authority=authority, fault=fault)
        engine.engine.workflows.append(wf)  # register with the H17 engine
        engine._seq[workflow_id] = checkpoint.checkpoint_sequence + 1
        engine._logical[workflow_id] = checkpoint.logical_sequence
        wf.trace.record("RESTORED", {"from_checkpoint": checkpoint.checkpoint_id,
                                     "reconciliation": result.reconciliation}, checkpoint.created_at)
        return engine, wf


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def format_recovery_trace(wf: WorkflowInstance) -> str:
    lines = [f"Recovery trace: {wf.workflow_id}  status={wf.status}", "=" * 60]
    for e in wf.trace.entries:
        lines.append(f"  {e.seq}: {e.kind} {e.detail}")
    return "\n".join(lines)
