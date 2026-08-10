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

**Scope (H22-B + H22-C + H22-D).** H22-B decides *which* prepared workflow receives the next
quantum and *why*; **H22-C** makes that coordination durable (a versioned portfolio checkpoint
that references — never copies — the underlying runtime checkpoints, side-effect-free portfolio
recovery, an append-only orchestration audit trace, bounded failure propagation, and cooperative
cancellation scopes); **H22-D** (this release, 0.6.0) adds **bounded, in-process concurrency**
over independent H22-A quanta — a fairness-preserving batch-selection seam, logical resource
claims with an atomic coordinator, a shared reserve-before-execute budget, and bounded
compensation coordination. It remains **in-process only**: no distributed cluster scheduling, no
distributed locking, no exactly-once external effects, no Runtime Assurance, and no
peer-to-peer/agent-selection. Governance stays entirely below this layer: the scheduler selects a
workflow and H22-D admits which safe quanta run concurrently, but neither ever authorizes that
workflow's task, and recovery performs no execution.

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
    PORTFOLIO_RUNTIME_CHECKPOINT_DIVERGENCE,
    PortfolioRecoveryResult,
    build_portfolio_checkpoint,
    recover_portfolio,
    validate_portfolio_checkpoint,
    validate_portfolio_checkpoint_bound,
)
from .scheduling import (
    AdmissionDecision,
    BatchPlan,
    PortfolioScheduler,
    PortfolioStepReason,
    PortfolioStepResult,
    SchedulingPolicy,
    SelectionReason,
    WorkflowEligibility,
)
from .resources import (
    ResourceClaim,
    ResourceConflict,
    ResourceCoordinator,
    ResourceMode,
    modes_conflict,
    normalize_claims,
)
from .budgets import (
    BudgetCoordinator,
    BudgetEstimateExceeded,
    BudgetRequirement,
    BudgetSettlement,
    BudgetShortfall,
    PortfolioBudget,
)
from .compensation import (
    CompensationRegistration,
    CompensationRegistry,
    CompensationSpec,
    CompensationTrigger,
)
from .concurrency import (
    ConcurrencyPolicy,
    ConcurrentPortfolioExecutor,
    ConcurrentPortfolioStepResult,
    ConcurrentStepReason,
    ExecutionBackend,
    ExecutorInfrastructureError,
    QuantumOutcome,
    SynchronousExecutionBackend,
    ThreadPoolExecutionBackend,
)
from .tracing import (
    PORTFOLIO_EVENT_TYPES,
    InMemoryPortfolioEventStore,
    PortfolioEventStore,
    PortfolioEventType,
    PortfolioTrace,
    PortfolioTraceEncodingError,
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
    "validate_portfolio_checkpoint_bound",
    "PORTFOLIO_RUNTIME_CHECKPOINT_DIVERGENCE",
    # H22-C audit trace + durable event store
    "PortfolioTrace",
    "PortfolioTraceEntry",
    "PortfolioEventType",
    "PORTFOLIO_EVENT_TYPES",
    "PortfolioEventStore",
    "InMemoryPortfolioEventStore",
    "PortfolioTraceSequenceError",
    "PortfolioTraceEncodingError",
    # H22-C failure propagation + cancellation control
    "PortfolioController",
    "PortfolioFailurePolicy",
    "CancellationScope",
    "PortfolioCancellationResult",
    # H22-D batch selection seam (fairness-preserving)
    "AdmissionDecision",
    "BatchPlan",
    # H22-D resource coordination
    "ResourceMode",
    "ResourceClaim",
    "ResourceConflict",
    "ResourceCoordinator",
    "modes_conflict",
    "normalize_claims",
    # H22-D shared budget coordination
    "PortfolioBudget",
    "BudgetRequirement",
    "BudgetShortfall",
    "BudgetSettlement",
    "BudgetCoordinator",
    "BudgetEstimateExceeded",
    # H22-D compensation coordination
    "CompensationTrigger",
    "CompensationSpec",
    "CompensationRegistration",
    "CompensationRegistry",
    # H22-D bounded concurrent execution
    "ConcurrencyPolicy",
    "ConcurrentPortfolioExecutor",
    "ConcurrentPortfolioStepResult",
    "ConcurrentStepReason",
    "QuantumOutcome",
    "ExecutionBackend",
    "SynchronousExecutionBackend",
    "ThreadPoolExecutionBackend",
    "ExecutorInfrastructureError",
]
