"""
Governed Working Memory & State Continuity (H14)
================================================

Run-scoped governed working memory that lets an autonomous workflow retain,
update, retrieve, and expire execution state across iterations, replanning,
and agent handoffs.  This is **state continuity, not long-term learning** —
memory lives only for the lifetime of one workflow.

```
Goal → Working Memory → Plan → Observation → Memory Update
    → Validity → Decision → Execution
```

Memory becomes the shared execution context.  Records are **append-only**
and **versioned**: an update never overwrites — it creates a new version and
supersedes the prior one, so history is never lost.  Retrieval is fully
**deterministic** (ACTIVE → highest version → highest confidence → most
recent) — no embeddings, no semantic search, no probabilistic ranking.

Integration is additive and strategy-agnostic.  This module does **not**
modify RunBudget, replanning, plan validity, governance, authorization,
ActionGate, TAP, routing, tool execution, or LLM providers.  It plugs into
the runtime through the observation-builder seam that ``ReplanningRunner``
already exposes (:class:`MemoryAwareObservationBuilder`) and links to H13
assumptions through their public API only (:class:`MemoryAssumptionBridge`).

Excluded by design: vector databases, semantic search, embeddings, long-term
memory, learning, reinforcement, user profiling, external storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol

from agentic.agentic_framework.replanning import PlanObservation, ObservationStatus

__all__ = [
    "MemoryState",
    "ExpirationKind",
    "ExpirationPolicy",
    "MemoryStatusTransition",
    "MemoryRecord",
    "MemoryVersion",
    "MemoryAccess",
    "MemorySelectionPolicy",
    "MemoryLifecycle",
    "MemoryOperation",
    "MemoryTrace",
    "WorkingMemory",
    "MemoryWrite",
    "MemoryObservation",
    "MemoryAwareObservationBuilder",
    "MemoryAssumptionBridge",
    "format_working_memory",
    "format_memory_trace",
]


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
class MemoryState:
    """Lifecycle state of a memory record version."""

    ACTIVE = "ACTIVE"            # current, selectable
    SUPERSEDED = "SUPERSEDED"    # replaced by a newer version
    EXPIRED = "EXPIRED"          # TTL / step / workflow expiry
    INVALIDATED = "INVALIDATED"  # explicitly invalidated
    ARCHIVED = "ARCHIVED"        # retained for history, not selectable


#: Only ACTIVE records are ever selected.
_SELECTABLE = {MemoryState.ACTIVE}


class ExpirationKind:
    """How a record expires."""

    NEVER = "never"
    TTL = "ttl"
    ON_STEP = "on_step"            # expire when a named step completes
    ON_ASSUMPTION = "on_assumption"  # expire when a named assumption fails
    WORKFLOW_END = "workflow_end"
    EXPLICIT = "explicit"


@dataclass
class ExpirationPolicy:
    """Deterministic expiration policy for a record."""

    kind: str = ExpirationKind.NEVER
    ttl: Optional[float] = None
    step_id: Optional[str] = None
    assumption_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "ttl": self.ttl,
            "step_id": self.step_id,
            "assumption_id": self.assumption_id,
        }


# ---------------------------------------------------------------------------
# Record + versioning
# ---------------------------------------------------------------------------
@dataclass
class MemoryStatusTransition:
    """One append-only status change of a record version."""

    from_state: str
    to_state: str
    reason: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_state": self.from_state,
            "to_state": self.to_state,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class MemoryRecord:
    """One immutable versioned snapshot of a memory key.

    The ``value`` and ``version`` are immutable; only ``status`` transitions
    over the version's lifecycle (append-only ``status_history``), and
    ``consuming_steps`` grows as the record is read.  A new value is always a
    new :class:`MemoryRecord` (a new version).
    """

    record_id: str          # unique per version, e.g. "customer_profile#v2"
    key: str                # logical key
    category: str
    value: Any
    version: int
    provenance: str = ""
    confidence: float = 1.0
    status: str = MemoryState.ACTIVE
    created_at: float = 0.0
    updated_at: float = 0.0
    expiration: ExpirationPolicy = field(default_factory=ExpirationPolicy)
    producing_step: Optional[str] = None
    consuming_steps: List[str] = field(default_factory=list)
    status_history: List[MemoryStatusTransition] = field(default_factory=list)

    def set_status(self, new_state: str, *, reason: str = "", timestamp: float = 0.0) -> None:
        """Record an append-only status transition."""
        if new_state == self.status:
            return
        self.status_history.append(
            MemoryStatusTransition(self.status, new_state, reason, timestamp)
        )
        self.status = new_state
        self.updated_at = timestamp

    def record_consumption(self, step_id: Optional[str]) -> None:
        if step_id and step_id not in self.consuming_steps:
            self.consuming_steps.append(step_id)

    @property
    def selectable(self) -> bool:
        return self.status in _SELECTABLE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "key": self.key,
            "category": self.category,
            "value": self.value,
            "version": self.version,
            "provenance": self.provenance,
            "confidence": self.confidence,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expiration": self.expiration.to_dict(),
            "producing_step": self.producing_step,
            "consuming_steps": list(self.consuming_steps),
            "status_history": [t.to_dict() for t in self.status_history],
        }


@dataclass
class MemoryVersion:
    """A lightweight view of one record version (for history listings)."""

    key: str
    version: int
    record_id: str
    status: str
    confidence: float
    value: Any
    created_at: float

    @classmethod
    def from_record(cls, rec: MemoryRecord) -> "MemoryVersion":
        return cls(
            key=rec.key, version=rec.version, record_id=rec.record_id,
            status=rec.status, confidence=rec.confidence, value=rec.value,
            created_at=rec.created_at,
        )


# ---------------------------------------------------------------------------
# Step memory access declaration
# ---------------------------------------------------------------------------
@dataclass
class MemoryAccess:
    """What memory a step requires / produces / may optionally use."""

    requires: List[str] = field(default_factory=list)
    produces: List[str] = field(default_factory=list)
    optional: List[str] = field(default_factory=list)

    @classmethod
    def from_step(cls, step: Any) -> "MemoryAccess":
        meta = getattr(step, "metadata", {}) or {}
        m = meta.get("memory", {}) or {}
        return cls(
            requires=list(m.get("requires", [])),
            produces=list(m.get("produces", [])),
            optional=list(m.get("optional", [])),
        )


# ---------------------------------------------------------------------------
# Selection policy — deterministic retrieval
# ---------------------------------------------------------------------------
class MemorySelectionPolicy(Protocol):
    def select(self, records: List[MemoryRecord]) -> Optional[MemoryRecord]:
        ...


class DeterministicSelectionPolicy:
    """Deterministic selection: ACTIVE → highest version → highest confidence
    → most recent timestamp.  No probabilistic retrieval."""

    def select(self, records: List[MemoryRecord]) -> Optional[MemoryRecord]:
        candidates = [r for r in records if r.selectable]
        if not candidates:
            return None
        # Sort deterministically; last wins.
        candidates.sort(key=lambda r: (r.version, r.confidence, r.created_at, r.record_id))
        return candidates[-1]


# ---------------------------------------------------------------------------
# Lifecycle helper — expiration rules
# ---------------------------------------------------------------------------
class MemoryLifecycle:
    """Deterministic expiration evaluation for records."""

    @staticmethod
    def is_ttl_expired(record: MemoryRecord, now: float) -> bool:
        exp = record.expiration
        return (
            exp.kind == ExpirationKind.TTL
            and exp.ttl is not None
            and (now - record.created_at) >= exp.ttl
        )

    @staticmethod
    def expires_on_step(record: MemoryRecord, step_id: str) -> bool:
        exp = record.expiration
        return exp.kind == ExpirationKind.ON_STEP and exp.step_id == step_id

    @staticmethod
    def expires_on_assumption(record: MemoryRecord, assumption_id: str) -> bool:
        exp = record.expiration
        return exp.kind == ExpirationKind.ON_ASSUMPTION and exp.assumption_id == assumption_id


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------
@dataclass
class MemoryOperation:
    """One recorded working-memory operation."""

    seq: int
    op: str          # CREATE | UPDATE | SUPERSEDE | READ | INVALIDATE | EXPIRE | ARCHIVE
    key: str
    version: Optional[int] = None
    record_id: Optional[str] = None
    step: Optional[str] = None
    timestamp: float = 0.0
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "op": self.op,
            "key": self.key,
            "version": self.version,
            "record_id": self.record_id,
            "step": self.step,
            "timestamp": self.timestamp,
            "detail": self.detail,
        }


class MemoryTrace:
    """Append-only log of every memory operation."""

    def __init__(self) -> None:
        self.operations: List[MemoryOperation] = []
        self._seq = 0

    def record(self, op: str, key: str, **kw: Any) -> MemoryOperation:
        entry = MemoryOperation(seq=self._seq, op=op, key=key, **kw)
        self.operations.append(entry)
        self._seq += 1
        return entry

    def for_step(self, step_id: str) -> List[MemoryOperation]:
        return [o for o in self.operations if o.step == step_id]

    def to_list(self) -> List[Dict[str, Any]]:
        return [o.to_dict() for o in self.operations]


# ---------------------------------------------------------------------------
# Working memory store
# ---------------------------------------------------------------------------
class WorkingMemory:
    """Run-scoped, governed, append-only, versioned working memory.

    Exists only for the lifetime of one workflow.  Every operation is
    deterministic and traceable.  Sequential agents share ONE instance —
    there are no copies and no independent stores.
    """

    def __init__(
        self,
        *,
        selection_policy: Optional[MemorySelectionPolicy] = None,
    ) -> None:
        self._versions: Dict[str, List[MemoryRecord]] = {}
        self.selection_policy = selection_policy or DeterministicSelectionPolicy()
        self.trace = MemoryTrace()
        #: Listeners notified on invalidate/expire: fn(key, state, timestamp).
        self._listeners: List[Callable[[str, str, float], None]] = []

    # ----- listeners (for the assumption bridge; additive) -----
    def add_listener(self, listener: Callable[[str, str, float], None]) -> None:
        self._listeners.append(listener)

    def _notify(self, key: str, state: str, timestamp: float) -> None:
        for fn in self._listeners:
            fn(key, state, timestamp)

    # ----- write path (append-only, versioned) -----
    def create(
        self,
        key: str,
        value: Any,
        *,
        category: str = "general",
        provenance: str = "",
        confidence: float = 1.0,
        producing_step: Optional[str] = None,
        expiration: Optional[ExpirationPolicy] = None,
        timestamp: float = 0.0,
    ) -> MemoryRecord:
        """Create version 1 of *key* (or a new version if it already exists)."""
        return self.write(
            key, value, category=category, provenance=provenance,
            confidence=confidence, producing_step=producing_step,
            expiration=expiration, timestamp=timestamp,
        )

    def update(
        self,
        key: str,
        value: Any,
        *,
        category: Optional[str] = None,
        provenance: str = "",
        confidence: float = 1.0,
        producing_step: Optional[str] = None,
        expiration: Optional[ExpirationPolicy] = None,
        timestamp: float = 0.0,
    ) -> MemoryRecord:
        """Create a NEW version of *key*; the prior ACTIVE version is
        superseded.  Never overwrites."""
        if key not in self._versions:
            raise KeyError(f"cannot update unknown memory key '{key}'")
        return self.write(
            key, value, category=category, provenance=provenance,
            confidence=confidence, producing_step=producing_step,
            expiration=expiration, timestamp=timestamp,
        )

    def write(
        self,
        key: str,
        value: Any,
        *,
        category: Optional[str] = None,
        provenance: str = "",
        confidence: float = 1.0,
        producing_step: Optional[str] = None,
        expiration: Optional[ExpirationPolicy] = None,
        timestamp: float = 0.0,
    ) -> MemoryRecord:
        """Create-or-update: append a new immutable version."""
        versions = self._versions.setdefault(key, [])
        is_update = bool(versions)

        # Supersede the current ACTIVE version (append-only status change).
        for rec in versions:
            if rec.status == MemoryState.ACTIVE:
                rec.set_status(MemoryState.SUPERSEDED, reason="new version", timestamp=timestamp)
                self.trace.record("SUPERSEDE", key, version=rec.version,
                                  record_id=rec.record_id, timestamp=timestamp)

        version = len(versions) + 1
        record = MemoryRecord(
            record_id=f"{key}#v{version}",
            key=key,
            category=category or (versions[-1].category if versions else "general"),
            value=value,
            version=version,
            provenance=provenance,
            confidence=confidence,
            status=MemoryState.ACTIVE,
            created_at=timestamp,
            updated_at=timestamp,
            expiration=expiration or ExpirationPolicy(),
            producing_step=producing_step,
        )
        versions.append(record)
        self.trace.record(
            "UPDATE" if is_update else "CREATE", key, version=version,
            record_id=record.record_id, step=producing_step, timestamp=timestamp,
        )
        return record

    # ----- read path (deterministic) -----
    def retrieve(
        self,
        key: str,
        *,
        consuming_step: Optional[str] = None,
        now: Optional[float] = None,
    ) -> Optional[MemoryRecord]:
        """Deterministically select the current ACTIVE record for *key*.

        TTL-expired records are expired in-place first (so they are never
        selected), then the selection policy chooses among ACTIVE versions.
        """
        versions = self._versions.get(key, [])
        if now is not None:
            self._expire_ttl(key, now)
        record = self.selection_policy.select(versions)
        if record is not None:
            record.record_consumption(consuming_step)
            self.trace.record("READ", key, version=record.version,
                              record_id=record.record_id, step=consuming_step,
                              timestamp=now or 0.0)
        return record

    def peek(self, key: str) -> Optional[MemoryRecord]:
        """Select the ACTIVE record without recording a consumption."""
        return self.selection_policy.select(self._versions.get(key, []))

    def versions(self, key: str) -> List[MemoryVersion]:
        return [MemoryVersion.from_record(r) for r in self._versions.get(key, [])]

    def records(self, key: str) -> List[MemoryRecord]:
        return list(self._versions.get(key, []))

    def keys(self) -> List[str]:
        return list(self._versions)

    def all_records(self) -> List[MemoryRecord]:
        out: List[MemoryRecord] = []
        for recs in self._versions.values():
            out.extend(recs)
        return out

    # ----- lifecycle transitions -----
    def invalidate(self, key: str, *, reason: str = "", timestamp: float = 0.0) -> List[MemoryRecord]:
        """Invalidate the ACTIVE version(s) of *key* (history preserved)."""
        changed = self._transition_active(key, MemoryState.INVALIDATED, reason, timestamp, "INVALIDATE")
        if changed:
            self._notify(key, MemoryState.INVALIDATED, timestamp)
        return changed

    def expire(self, key: str, *, reason: str = "ttl", timestamp: float = 0.0) -> List[MemoryRecord]:
        changed = self._transition_active(key, MemoryState.EXPIRED, reason, timestamp, "EXPIRE")
        if changed:
            self._notify(key, MemoryState.EXPIRED, timestamp)
        return changed

    def archive(self, key: str, *, reason: str = "", timestamp: float = 0.0) -> List[MemoryRecord]:
        return self._transition_active(key, MemoryState.ARCHIVED, reason, timestamp, "ARCHIVE")

    def _transition_active(
        self, key: str, new_state: str, reason: str, timestamp: float, op: str
    ) -> List[MemoryRecord]:
        changed: List[MemoryRecord] = []
        for rec in self._versions.get(key, []):
            if rec.status == MemoryState.ACTIVE:
                rec.set_status(new_state, reason=reason, timestamp=timestamp)
                self.trace.record(op, key, version=rec.version, record_id=rec.record_id,
                                  timestamp=timestamp, detail=reason)
                changed.append(rec)
        return changed

    # ----- expiration drivers -----
    def _expire_ttl(self, key: str, now: float) -> None:
        for rec in self._versions.get(key, []):
            if rec.status == MemoryState.ACTIVE and MemoryLifecycle.is_ttl_expired(rec, now):
                rec.set_status(MemoryState.EXPIRED, reason="ttl", timestamp=now)
                self.trace.record("EXPIRE", key, version=rec.version,
                                  record_id=rec.record_id, timestamp=now, detail="ttl")
                self._notify(key, MemoryState.EXPIRED, now)

    def expire_due(self, now: float) -> None:
        """Expire every TTL-expired ACTIVE record across all keys."""
        for key in list(self._versions):
            self._expire_ttl(key, now)

    def expire_on_step(self, step_id: str, *, timestamp: float = 0.0) -> None:
        """Expire records whose policy is ``ON_STEP`` for *step_id*."""
        for key, recs in self._versions.items():
            for rec in recs:
                if rec.status == MemoryState.ACTIVE and MemoryLifecycle.expires_on_step(rec, step_id):
                    rec.set_status(MemoryState.EXPIRED, reason=f"step {step_id} completed", timestamp=timestamp)
                    self.trace.record("EXPIRE", key, version=rec.version, record_id=rec.record_id,
                                      step=step_id, timestamp=timestamp, detail="on_step")
                    self._notify(key, MemoryState.EXPIRED, timestamp)

    def expire_on_assumption(self, assumption_id: str, *, timestamp: float = 0.0) -> None:
        for key, recs in self._versions.items():
            for rec in recs:
                if rec.status == MemoryState.ACTIVE and MemoryLifecycle.expires_on_assumption(rec, assumption_id):
                    rec.set_status(MemoryState.EXPIRED, reason=f"assumption {assumption_id} failed", timestamp=timestamp)
                    self.trace.record("EXPIRE", key, version=rec.version, record_id=rec.record_id,
                                      timestamp=timestamp, detail="on_assumption")
                    self._notify(key, MemoryState.EXPIRED, timestamp)

    # ----- reporting -----
    def snapshot(self) -> Dict[str, Any]:
        return {
            "keys": {
                key: {
                    "active": (self.peek(key).record_id if self.peek(key) else None),
                    "versions": [MemoryVersion.from_record(r).__dict__ for r in recs],
                }
                for key, recs in self._versions.items()
            },
            "operations": self.trace.to_list(),
        }


# ---------------------------------------------------------------------------
# Memory-carrying observation + builder
# ---------------------------------------------------------------------------
@dataclass
class MemoryWrite:
    """A value a step produced, to be written into working memory."""

    key: str
    value: Any
    category: str = "general"
    confidence: float = 1.0
    expiration: Optional[ExpirationPolicy] = None


@dataclass
class MemoryObservation(PlanObservation):
    """A :class:`PlanObservation` that also carries memory effects.

    ``memory_writes`` are values the step produced; ``memory_invalidations``
    are keys the observation renders invalid.  ``memory_reads`` is filled in
    by :class:`MemoryAwareObservationBuilder` so every decision trace can
    identify the records that influenced it.
    """

    memory_writes: List[MemoryWrite] = field(default_factory=list)
    memory_invalidations: List[str] = field(default_factory=list)
    memory_reads: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["memory_reads"] = list(self.memory_reads)
        d["memory_writes"] = [w.key for w in self.memory_writes]
        d["memory_invalidations"] = list(self.memory_invalidations)
        return d


class MemoryAwareObservationBuilder:
    """Wraps a base observation builder to make each step memory-aware.

    Per step it:

    1. reads the step's required + optional memory (recording consumption),
       attaching the read record ids to the observation;
    2. delegates to the base builder for the observation itself;
    3. writes the values the step produced as new memory versions;
    4. applies any memory invalidations the observation reported;
    5. expires records whose policy fires on this step's completion.

    Being an ``ObservationBuilder`` it drops straight into
    ``ReplanningRunner`` / ``build_assumption_aware_runner`` — no runner
    changes.
    """

    def __init__(self, memory: WorkingMemory, base: Any) -> None:
        self.memory = memory
        self.base = base

    def build(self, goal, step, trace, agent, iteration) -> PlanObservation:
        now = float(iteration)
        access = MemoryAccess.from_step(step)

        # 1. Read required + optional memory (deterministic).
        reads: List[str] = []
        for key in access.requires + access.optional:
            rec = self.memory.retrieve(key, consuming_step=step.step_id, now=now)
            if rec is not None:
                reads.append(rec.record_id)

        # 2. Base observation (e.g. scripted MemoryObservation).
        observation = self.base.build(goal, step, trace, agent, iteration)

        # 3. Writes the step produced (new immutable versions).
        for w in getattr(observation, "memory_writes", []) or []:
            self.memory.write(
                w.key, w.value, category=w.category, confidence=w.confidence,
                producing_step=step.step_id, expiration=w.expiration, timestamp=now,
            )

        # 4. Invalidations reported by the observation.
        for key in getattr(observation, "memory_invalidations", []) or []:
            self.memory.invalidate(key, reason=f"observation at {step.step_id}", timestamp=now)

        # 5. Step-completion expiries.
        self.memory.expire_on_step(step.step_id, timestamp=now)

        # 6. Attach reads so the decision trace identifies influencing records.
        if hasattr(observation, "memory_reads"):
            observation.memory_reads = reads
        return observation


# ---------------------------------------------------------------------------
# Memory ↔ assumption bridge (uses H13 public API only)
# ---------------------------------------------------------------------------
class MemoryAssumptionBridge:
    """Propagates memory invalidation to dependent H13 assumptions.

    When a linked memory record is invalidated (or expired), the assumptions
    that depend on it are transitioned to ``INVALID`` via the assumption's
    own append-only ``transition()`` — H13's public API.  H13's existing
    validity evaluation then picks the change up on its next ``decide()``.
    The H13 architecture is not modified.
    """

    def __init__(
        self,
        memory: WorkingMemory,
        assumption_context: Any,
        links: Dict[str, List[str]],
    ) -> None:
        """*links* maps a memory key → the assumption ids it supports."""
        self.memory = memory
        self.context = assumption_context
        self.links = {k: list(v) for k, v in links.items()}
        memory.add_listener(self._on_memory_change)

    def _on_memory_change(self, key: str, state: str, timestamp: float) -> None:
        # Deferred import to avoid a hard dependency / import cycle.
        from agentic.agentic_framework.plan_validity import AssumptionState

        for aid in self.links.get(key, []):
            assumption = self.context.registry.get(aid)
            if assumption is not None and assumption.state != AssumptionState.INVALID:
                assumption.transition(
                    AssumptionState.INVALID,
                    reason=f"supporting memory '{key}' {state}",
                    timestamp=timestamp,
                )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def format_working_memory(memory: WorkingMemory) -> str:
    lines = ["Working memory", "-" * 52]
    for key in memory.keys():
        active = memory.peek(key)
        lines.append(f"  {key}: active={active.record_id if active else '(none)'}")
        for r in memory.records(key):
            lines.append(
                f"      v{r.version} [{r.status:<11}] conf={r.confidence:.2f} "
                f"by={r.producing_step} value={r.value!r}"
            )
    return "\n".join(lines)


def format_memory_trace(memory: WorkingMemory) -> str:
    lines = ["Memory trace", "=" * 52]
    for op in memory.trace.operations:
        lines.append(
            f"  {op.seq:>3} {op.op:<10} {op.key}"
            + (f" v{op.version}" if op.version is not None else "")
            + (f" step={op.step}" if op.step else "")
            + (f"  {op.detail}" if op.detail else "")
        )
    return "\n".join(lines)
