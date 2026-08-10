"""The H22-B workflow portfolio — the orchestration-state aggregate.

A :class:`WorkflowPortfolio` is a deterministic collection of *already-prepared* Agent
Runtime workflow instances, plus the orchestration metadata a scheduler needs to decide
*which* prepared workflow should receive the next H22-A execution quantum: per-workflow
priority and fairness weight, a stable registration order, a cross-workflow dependency
graph, and the mutable per-round fairness/aging bookkeeping.

**The portfolio is orchestration state only.** It references each workflow by its
``instance_id`` and never duplicates the runtime-owned workflow/task state, canonical
execution state, or checkpoints. The Agent Runtime remains the sole authority for
execution truth; the portfolio holds nothing but scheduling metadata, so it stays
deterministic and (for a future H22-C) serializable — it holds no closures, no thread
handles, no object references into the runtime.

The portfolio decides nothing about governance. It selects a workflow; it never authorizes
that workflow's task. Every consequential action still crosses the unchanged
governance → exact-action → provider boundary *below* H22, inside ``advance_workflow``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .dependencies import DependencyGraph, DependencyType, WorkflowDependency


class WorkflowPriority(str, Enum):
    """Explicit orchestration priority. Lower rank = more preferred.

    This is *scheduling* priority only. It never creates governance authority: a
    ``CRITICAL`` workflow cannot bypass a dependency, a WAITING/PAUSED runtime state, or
    exact-action validation — it is only preferred among *eligible* workflows.
    """

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"
    BACKGROUND = "BACKGROUND"


# Numeric base ranks spaced by 100 (lower = preferred). CRITICAL is the reserved,
# non-aging class (see aging in scheduling.py): no amount of aging lets a lower class
# reach it.
_PRIORITY_RANK: Dict[WorkflowPriority, int] = {
    WorkflowPriority.CRITICAL: 0,
    WorkflowPriority.HIGH: 100,
    WorkflowPriority.NORMAL: 200,
    WorkflowPriority.LOW: 300,
    WorkflowPriority.BACKGROUND: 400,
}


def priority_rank(priority: WorkflowPriority) -> int:
    """The stable numeric base rank for a priority (lower = preferred)."""
    return _PRIORITY_RANK[priority]


class PortfolioStatus(str, Enum):
    """Minimal portfolio lifecycle.

    ``CREATED`` before scheduling has begun over any registered workflow — the ONLY state in
    which the portfolio topology (registrations and dependencies) may be mutated. ``ACTIVE``
    once a scheduling round has run over a non-empty portfolio and some workflow can still
    make progress (this includes a *quiescent* portfolio whose workflows are all
    WAITING/PAUSED/dependency-blocked — quiescent is NOT complete). ``COMPLETED`` only when
    every registered workflow is terminal. **Topology is frozen once scheduling begins:** in
    ``ACTIVE`` and ``COMPLETED`` a new registration or dependency is rejected, so the
    scheduler can never run a workflow the portfolio does not report. Stepping an *empty*
    portfolio is a no-op that leaves it ``CREATED`` (still mutable), never misleadingly
    ``ACTIVE``. Richer portfolio lifecycle (FAILED / PAUSED / cancellation scopes) is
    deliberately deferred to H22-C.
    """

    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


@dataclass
class PortfolioWorkflowEntry:
    """One workflow's registration inside a portfolio — orchestration metadata only.

    Immutable identity: ``instance_id`` (a reference to an existing Agent Runtime workflow
    instance) and ``registration_sequence`` (assigned once, stable). ``priority`` and
    ``weight`` are the declared scheduling inputs. ``age`` and ``fair_credit`` are the
    mutable per-round aging / fairness state the scheduler evolves deterministically:
    ``fair_credit`` is the smooth-weighted-round-robin current-weight counter (higher =
    more owed service). No agent/model selection, no execution payload, no runtime-owned
    state is stored here.
    """

    instance_id: str
    registration_sequence: int
    priority: WorkflowPriority = WorkflowPriority.NORMAL
    weight: float = 1.0
    # --- mutable deterministic scheduler bookkeeping (evolved by rounds only) ---
    age: int = 0
    fair_credit: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "instance_id": self.instance_id,
            "registration_sequence": self.registration_sequence,
            "priority": self.priority.value,
            "weight": self.weight,
            "age": self.age,
            "fair_credit": self.fair_credit,
        }


class WorkflowPortfolio:
    """A deterministic aggregate of prepared workflow registrations + a dependency graph.

    Registration is explicit, append-only, order-stable, and idempotent: re-registering an
    already-registered ``instance_id`` returns the existing entry unchanged (it never
    mutates the original priority/weight/sequence, so a workflow's registered identity is
    immutable). The portfolio never runs a workflow and never mutates runtime-owned state.
    """

    def __init__(self, portfolio_id: str) -> None:
        if not portfolio_id or not isinstance(portfolio_id, str):
            raise ValueError("WorkflowPortfolio.portfolio_id required")
        self._portfolio_id = portfolio_id
        # Registration order is authoritative; the dict preserves insertion order but the
        # ordered list is what every deterministic traversal uses.
        self._entries: Dict[str, PortfolioWorkflowEntry] = {}
        self._order: List[str] = []
        self._dependencies: List[WorkflowDependency] = []
        self._status = PortfolioStatus.CREATED
        self._round = 0
        # Cached dependency graph, invalidated on any registration/edge change.
        self._graph: Optional[DependencyGraph] = None

    # -- identity / lifecycle ----------------------------------------------
    @property
    def portfolio_id(self) -> str:
        return self._portfolio_id

    @property
    def status(self) -> PortfolioStatus:
        return self._status

    @property
    def round(self) -> int:
        """The number of scheduling rounds that have run against this portfolio."""
        return self._round

    # -- registration -------------------------------------------------------
    def register(
        self,
        instance_id: str,
        *,
        runtime: Optional[object] = None,
        priority: WorkflowPriority = WorkflowPriority.NORMAL,
        weight: float = 1.0,
    ) -> PortfolioWorkflowEntry:
        """Register a prepared workflow instance. Idempotent on ``instance_id``.

        If ``runtime`` is supplied, the instance must already exist in it (an unknown
        ``instance_id`` is rejected) — the runtime is used only to validate the reference
        and is never stored. ``weight`` must be a positive, finite number (NaN / ±Inf and
        non-positive weights are rejected fail-closed). Re-registering an existing
        ``instance_id`` returns the existing entry unchanged and is permitted at any time
        (it is a no-op, not a topology change). Registering a **new** workflow is permitted
        only while the portfolio is ``CREATED``; once scheduling has begun (``ACTIVE`` /
        ``COMPLETED``) the topology is frozen and a new registration is rejected.
        """
        if not instance_id or not isinstance(instance_id, str):
            raise ValueError("register requires a non-empty instance_id")
        if instance_id in self._entries:
            return self._entries[instance_id]
        if self._status is not PortfolioStatus.CREATED:
            raise ValueError(
                "cannot register a new workflow: portfolio topology is frozen once "
                f"scheduling has begun (status={self._status.value})"
            )
        if not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight <= 0:
            raise ValueError("register weight must be a positive, finite number")
        if runtime is not None and not _instance_known(runtime, instance_id):
            raise ValueError(
                f"unknown workflow instance {instance_id!r}: register a prepared instance"
            )
        entry = PortfolioWorkflowEntry(
            instance_id=instance_id,
            registration_sequence=len(self._order),
            priority=priority,
            weight=float(weight),
        )
        self._entries[instance_id] = entry
        self._order.append(instance_id)
        self._graph = None  # node set changed
        # Registration does not activate scheduling; the portfolio stays CREATED (and
        # mutable) until the first scheduling round runs over it — so "no execution occurs
        # from registration" holds and the topology can still be completed before stepping.
        return entry

    def entry(self, instance_id: str) -> PortfolioWorkflowEntry:
        return self._entries[instance_id]

    def entries(self) -> Tuple[PortfolioWorkflowEntry, ...]:
        """All registrations in stable registration order."""
        return tuple(self._entries[i] for i in self._order)

    @property
    def instance_ids(self) -> Tuple[str, ...]:
        return tuple(self._order)

    def is_registered(self, instance_id: str) -> bool:
        return instance_id in self._entries

    # -- dependencies -------------------------------------------------------
    def add_dependency(
        self,
        dependent_id: str,
        requires_id: str,
        dep_type: DependencyType = DependencyType.REQUIRES_COMPLETION,
    ) -> WorkflowDependency:
        """Declare that ``dependent_id`` requires ``requires_id`` (a predecessor).

        Both workflows must be registered. A self-dependency is rejected, and any edge that
        would introduce a cycle (direct or indirect) is rejected fail-closed — the edge is
        not added. An exact duplicate edge is idempotent; a duplicate pair with a different
        ``dep_type`` is rejected as ambiguous. Declaring a dependency is permitted only while
        the portfolio is ``CREATED``; once scheduling has begun the topology is frozen.
        """
        if self._status is not PortfolioStatus.CREATED:
            raise ValueError(
                "cannot add a dependency: portfolio topology is frozen once scheduling has "
                f"begun (status={self._status.value})"
            )
        if dependent_id not in self._entries:
            raise ValueError(f"unknown dependent workflow {dependent_id!r}")
        if requires_id not in self._entries:
            raise ValueError(f"unknown predecessor workflow {requires_id!r}")
        if dependent_id == requires_id:
            raise ValueError(f"workflow {dependent_id!r} cannot depend on itself")
        edge = WorkflowDependency(
            dependent_id=dependent_id, requires_id=requires_id, dep_type=dep_type
        )
        # Validate against a trial graph so a cycle/conflict never leaves partial state.
        trial = DependencyGraph(self._order, self._dependencies + [edge])
        # Idempotent exact-duplicate: the trial graph deduplicated it; only append if new.
        if not any(
            e.dependent_id == dependent_id and e.requires_id == requires_id
            for e in self._dependencies
        ):
            self._dependencies.append(edge)
        self._graph = trial
        return edge

    def dependency_graph(self) -> DependencyGraph:
        """The validated dependency graph over current registrations (cached)."""
        if self._graph is None:
            self._graph = DependencyGraph(self._order, self._dependencies)
        return self._graph

    # -- internal scheduler hooks (used by PortfolioScheduler only) ---------
    def _begin_round(self, activate: bool) -> int:
        """Advance the logical round counter. ``activate`` transitions CREATED → ACTIVE
        (freezing topology) only when there is a non-empty portfolio to schedule; stepping
        an empty portfolio leaves it CREATED and still mutable."""
        self._round += 1
        if activate and self._status is PortfolioStatus.CREATED:
            self._status = PortfolioStatus.ACTIVE
        return self._round

    def _mark_completed(self) -> None:
        self._status = PortfolioStatus.COMPLETED

    def to_dict(self) -> Dict[str, object]:
        """A deterministic, serializable snapshot of orchestration state (no runtime state).

        Provided so H22-C portfolio durability can build on a stable shape; H22-B itself
        implements no portfolio checkpoint/recovery."""
        return {
            "portfolio_id": self._portfolio_id,
            "status": self._status.value,
            "round": self._round,
            "entries": [self._entries[i].to_dict() for i in self._order],
            "dependencies": [
                {
                    "dependent_id": e.dependent_id,
                    "requires_id": e.requires_id,
                    "dep_type": e.dep_type.value,
                }
                for e in self._dependencies
            ],
        }


def _instance_known(runtime: object, instance_id: str) -> bool:
    """True if ``instance_id`` is a workflow the runtime already knows about.

    Uses only the runtime's public ``instance(id)`` accessor; a KeyError means unknown."""
    accessor = getattr(runtime, "instance", None)
    if accessor is None:
        return True  # cannot validate against this object; skip (validation is opt-in)
    try:
        accessor(instance_id)
    except KeyError:
        return False
    return True
