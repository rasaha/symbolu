"""H22-B — deterministic multi-workflow coordination for the Agent Runtime.

This subpackage is the coordination layer that sits **above** the single-workflow runtime
and decides *which* prepared workflow receives the next H22-A bounded execution quantum,
and *why*. It answers exactly one question:

    Given N prepared independent workflows, which workflow is eligible to receive the next
    execution quantum, and why?

It provides a :class:`WorkflowPortfolio` (orchestration-state aggregate), a cross-workflow
:class:`DependencyGraph`, deterministic eligibility classification, and a
:class:`PortfolioScheduler` that applies explicit **priority**, bounded starvation-prevention
**aging**, and deterministic **fairness** to grant one quantum per round through the
unchanged ``advance_workflow`` seam.

**Scope (H22-B + H22-C).** Deterministic *interleaving*, NOT simultaneous execution — no
concurrency, no shared budget/resource ledger, no compensation engine, no peer-to-peer agent
messaging, no agent/model selection (those remain H22-D). H22-B decides *which* prepared
workflow receives the next quantum and *why*; **H22-C** (this release, 0.5.0) makes that
coordination durable: a versioned portfolio checkpoint that references (never copies) the
underlying runtime checkpoints, side-effect-free portfolio recovery, an append-only
orchestration audit trace, bounded failure propagation, and cooperative cancellation scopes.
Governance stays entirely below this layer: the scheduler selects a workflow, it never
authorizes that workflow's task, and recovery performs no execution.

Dependency direction is orchestration → runtime: this package imports the runtime's public
contracts; the runtime engine never imports orchestration, so the single-workflow runtime
stays usable without it.
"""
from __future__ import annotations

from .control import (
    CancellationScope,
    PortfolioCancellationResult,
    PortfolioController,
    PortfolioFailurePolicy,
)
from .dependencies import (
    DependencyGraph,
    DependencyState,
    DependencyType,
    WorkflowDependency,
)
from .persistence import (
    PORTFOLIO_CHECKPOINT_VERSION,
    InMemoryPortfolioCheckpointStore,
    PortfolioCheckpoint,
    PortfolioCheckpointConflict,
    PortfolioCheckpointStore,
    WorkflowCheckpointRef,
)
from .portfolio import (
    PortfolioStatus,
    PortfolioWorkflowEntry,
    WorkflowPortfolio,
    WorkflowPriority,
    priority_rank,
)
from .recovery import (
    PortfolioRecoveryResult,
    build_portfolio_checkpoint,
    recover_portfolio,
    validate_portfolio_checkpoint,
)
from .scheduling import (
    PortfolioScheduler,
    PortfolioStepReason,
    PortfolioStepResult,
    SchedulingPolicy,
    SelectionReason,
    WorkflowEligibility,
)
from .tracing import (
    PORTFOLIO_EVENT_TYPES,
    InMemoryPortfolioEventStore,
    PortfolioEventStore,
    PortfolioEventType,
    PortfolioTrace,
    PortfolioTraceEntry,
    PortfolioTraceSequenceError,
)

__all__ = [
    # portfolio aggregate + registration
    "WorkflowPortfolio",
    "PortfolioWorkflowEntry",
    "PortfolioStatus",
    "WorkflowPriority",
    "priority_rank",
    # dependency graph
    "DependencyGraph",
    "DependencyType",
    "DependencyState",
    "WorkflowDependency",
    # scheduling
    "PortfolioScheduler",
    "SchedulingPolicy",
    "PortfolioStepResult",
    "PortfolioStepReason",
    "SelectionReason",
    "WorkflowEligibility",
    # H22-C durability: checkpoint + store
    "PortfolioCheckpoint",
    "WorkflowCheckpointRef",
    "PortfolioCheckpointStore",
    "InMemoryPortfolioCheckpointStore",
    "PortfolioCheckpointConflict",
    "PORTFOLIO_CHECKPOINT_VERSION",
    # H22-C durability: recovery
    "PortfolioRecoveryResult",
    "recover_portfolio",
    "build_portfolio_checkpoint",
    "validate_portfolio_checkpoint",
    # H22-C audit trace + durable event store
    "PortfolioTrace",
    "PortfolioTraceEntry",
    "PortfolioEventType",
    "PORTFOLIO_EVENT_TYPES",
    "PortfolioEventStore",
    "InMemoryPortfolioEventStore",
    "PortfolioTraceSequenceError",
    # H22-C failure propagation + cancellation control
    "PortfolioController",
    "PortfolioFailurePolicy",
    "CancellationScope",
    "PortfolioCancellationResult",
]
