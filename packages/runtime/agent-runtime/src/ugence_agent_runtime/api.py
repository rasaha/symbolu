"""Curated public API for the Agent Runtime.

This module is the single supported entry point. Everything exported from the
top-level package is re-exported from here. Internal implementation details are not
exported by default, and no product-specific class is exposed through the core API.

Importing this module performs no I/O and starts nothing (see docs/AGENT_RUNTIME_SECURITY.md).
"""
from __future__ import annotations

from typing import Optional

from .config import AgentRuntimeConfig
from .governance.decisions import validate_clearance
from .governance.hooks import (
    AllowAllGovernanceHook,
    NoopGovernanceHook,
    UnconfiguredGovernanceHook,
)
from .governance.interfaces import (
    CorrelationContext,
    ExecutionContext,
    GovernanceDisposition,
    GovernanceEvaluation,
    GovernanceHook,
)
from .models.agent import AgentDescriptor
from .models.events import RuntimeEvent
from .models.execution_state import CanonicalExecutionState, ExecutionLineage
from .models.proposal import TransitionProposal
from .models.results import (
    FailureCategory,
    RuntimeFailure,
    RuntimeResult,
    WorkflowAdvanceOutcome,
    WorkflowAdvanceStop,
)
from .models.task import TaskDefinition, TaskInstance, TaskStatus
from .models.transitions import RuntimeTransition
from .models.workflow import WorkflowDefinition, WorkflowInstance, WorkflowStatus
from .orchestration import (
    CancellationScope,
    DependencyGraph,
    DependencyState,
    DependencyType,
    InMemoryPortfolioCheckpointStore,
    InMemoryPortfolioEventStore,
    PortfolioCancellationResult,
    PortfolioCheckpoint,
    PortfolioCheckpointConflict,
    PortfolioCheckpointStore,
    PortfolioController,
    PortfolioEventStore,
    PortfolioEventType,
    PortfolioFailurePolicy,
    PortfolioRecoveryResult,
    PortfolioScheduler,
    PortfolioStatus,
    PortfolioStepReason,
    PortfolioStepResult,
    PortfolioTrace,
    PortfolioTraceEncodingError,
    PortfolioTraceEntry,
    PortfolioTraceSequenceError,
    PortfolioWorkflowEntry,
    SchedulingPolicy,
    SelectionReason,
    WorkflowCheckpointRef,
    WorkflowDependency,
    WorkflowEligibility,
    WorkflowPortfolio,
    WorkflowPriority,
    priority_rank,
    recover_portfolio,
)
from .persistence.checkpoints import Checkpoint
from .persistence.interfaces import CheckpointStore, RuntimeEventStore, RuntimeStateStore
from .persistence.recovery import RuntimeRecoveryResult
from .providers.interfaces import Provider, ToolInvocation, ToolResult
from .providers.registry import ProviderRegistry
from .runtime.engine import AgentRuntime
from .runtime.errors import (
    AgentRuntimeError,
    CancellationError,
    CheckpointError,
    IntegrityError,
    InvalidTransitionError,
    ProposalError,
    ProviderExecutionError,
    ProviderNotFoundError,
    RecoveryError,
    RuntimeConfigurationError,
    RuntimeTimeoutError,
)
from .runtime.retry import RetryPolicy


# --- convenience constructors ------------------------------------------------
def create_runtime(config: Optional[AgentRuntimeConfig] = None) -> AgentRuntime:
    """Create a runtime from a config (or defaults). No I/O; nothing is started."""
    return AgentRuntime(config or AgentRuntimeConfig())


def open_runtime(config: Optional[AgentRuntimeConfig] = None) -> AgentRuntime:
    """Alias for :func:`create_runtime` for callers that prefer open/close phrasing."""
    return create_runtime(config)


def start_workflow(
    runtime: AgentRuntime,
    definition: WorkflowDefinition,
    correlation_id: Optional[str] = None,
    lineage: Optional[ExecutionLineage] = None,
    task_lineage: Optional[dict] = None,
) -> WorkflowInstance:
    return runtime.start_workflow(definition, correlation_id, lineage, task_lineage)


def prepare_workflow(
    runtime: AgentRuntime,
    definition: WorkflowDefinition,
    correlation_id: Optional[str] = None,
    lineage: Optional[ExecutionLineage] = None,
    task_lineage: Optional[dict] = None,
) -> WorkflowInstance:
    """Create and register a workflow WITHOUT draining it to completion (H22-A).

    The returned instance is RUNNING with no task advanced; advance it one bounded
    quantum at a time with :func:`advance_workflow`. See
    ``AgentRuntime.prepare_workflow``."""
    return runtime.prepare_workflow(definition, correlation_id, lineage, task_lineage)


def advance_workflow(runtime: AgentRuntime, instance_id: str) -> WorkflowAdvanceOutcome:
    """Advance a prepared/running workflow by one bounded execution quantum (H22-A).

    Returns a :class:`WorkflowAdvanceOutcome` describing exactly what happened and the
    stable boundary the quantum stopped at. See ``AgentRuntime.advance_workflow``."""
    return runtime.advance_workflow(instance_id)


def execution_state(
    runtime: AgentRuntime,
    instance_id: str,
    task_id: Optional[str] = None,
) -> Optional[CanonicalExecutionState]:
    """Return the latest canonical execution-state snapshot for a task (or a
    workflow-level snapshot when ``task_id`` is None). Read-only; there is no API to
    overwrite runtime-owned execution truth."""
    return runtime.execution_state(instance_id, task_id)


def execution_state_by_digest(
    runtime: AgentRuntime,
    instance_id: str,
    state_digest: str,
) -> Optional[CanonicalExecutionState]:
    """Resolve a historical canonical execution-state snapshot by its digest, so an
    ``execution_state_digest`` anchored on any earlier event stays reconstructable."""
    return runtime.execution_state_by_digest(instance_id, state_digest)


def resume_workflow(runtime: AgentRuntime, instance_id: str) -> WorkflowInstance:
    return runtime.resume_workflow(instance_id)


def continue_workflow(runtime: AgentRuntime, instance_id: str) -> WorkflowInstance:
    """Re-arm a WAITING/PAUSED workflow for bounded advancement WITHOUT draining it.

    The bounded analogue of :func:`resume_workflow`: it returns the workflow RUNNING so an
    orchestrator can advance it one quantum at a time — the explicit continuation seam a
    portfolio scheduler uses to continue a recovered workflow. See
    ``AgentRuntime.continue_workflow``."""
    return runtime.continue_workflow(instance_id)


def pause_workflow(runtime: AgentRuntime, instance_id: str) -> WorkflowInstance:
    return runtime.pause_workflow(instance_id)


def cancel_workflow(runtime: AgentRuntime, instance_id: str) -> WorkflowInstance:
    return runtime.cancel_workflow(instance_id)


def recover_runtime(
    runtime: AgentRuntime,
    instance_id: str,
    definition: WorkflowDefinition,
) -> RuntimeRecoveryResult:
    return runtime.recover_runtime(instance_id, definition)


def register_provider(runtime: AgentRuntime, provider: Provider) -> None:
    runtime.config.provider_registry.register(provider)


def register_governance_hook(config: AgentRuntimeConfig, hook: GovernanceHook) -> AgentRuntimeConfig:
    """Return a new config with ``hook`` as its governance boundary.

    Config is immutable; this returns a copy rather than mutating in place, so
    binding a governance hook is always explicit."""
    import dataclasses

    return dataclasses.replace(config, governance_hook=hook)


# --- H22-B multi-workflow coordination constructors --------------------------
def create_portfolio(portfolio_id: str) -> WorkflowPortfolio:
    """Create an empty workflow portfolio (H22-B). No I/O; registers nothing.

    Register already-prepared workflow instances with ``portfolio.register(instance_id,
    runtime=…)`` and declare cross-workflow prerequisites with
    ``portfolio.add_dependency(...)``. The portfolio holds orchestration state only and
    never duplicates runtime-owned workflow state."""
    return WorkflowPortfolio(portfolio_id)


def create_portfolio_scheduler(
    runtime: AgentRuntime, policy: Optional[SchedulingPolicy] = None
) -> PortfolioScheduler:
    """Create a deterministic portfolio scheduler bound to ``runtime`` (H22-B).

    ``scheduler.step(portfolio)`` grants at most one bounded H22-A quantum per round to the
    eligible workflow chosen by priority/fairness/aging; ``scheduler.run(portfolio)`` loops
    that bounded step until the portfolio is quiescent or complete. The scheduler selects a
    workflow; it never authorizes its task — governance stays entirely below H22-B."""
    return PortfolioScheduler(runtime, policy)


# --- H22-C durable portfolio recovery / control constructors -----------------
def create_portfolio_controller(
    runtime: AgentRuntime,
    portfolio: WorkflowPortfolio,
    *,
    policy: PortfolioFailurePolicy = PortfolioFailurePolicy.ISOLATE_WORKFLOW,
    scheduling_policy: Optional[SchedulingPolicy] = None,
    trace: Optional[PortfolioTrace] = None,
    event_store: Optional[PortfolioEventStore] = None,
    checkpoint_store: Optional[PortfolioCheckpointStore] = None,
    emit_created: bool = False,
) -> PortfolioController:
    """Create an H22-C portfolio controller over ``runtime`` and ``portfolio``.

    The controller drives the H22-B scheduler, records an append-only orchestration audit
    trace (durable when an ``event_store`` is supplied), applies the bounded failure ``policy``
    when it observes a terminal workflow failure, performs cooperative cancellation by scope, and
    commits durable portfolio checkpoints that satisfy the self-recoverability invariant. It
    reaches execution only through the unchanged ``advance_workflow`` seam and never authorizes a
    task."""
    return PortfolioController(
        runtime,
        portfolio,
        policy=policy,
        scheduling_policy=scheduling_policy,
        trace=trace,
        event_store=event_store,
        checkpoint_store=checkpoint_store,
        emit_created=emit_created,
    )


__all__ = [
    # runtime
    "AgentRuntime",
    "AgentRuntimeConfig",
    "AgentDescriptor",
    # workflow / task
    "WorkflowDefinition",
    "WorkflowInstance",
    "WorkflowStatus",
    "TaskDefinition",
    "TaskInstance",
    "TaskStatus",
    "RuntimeTransition",
    "RuntimeEvent",
    "RuntimeResult",
    "RuntimeFailure",
    "FailureCategory",
    "WorkflowAdvanceOutcome",
    "WorkflowAdvanceStop",
    # H22-B multi-workflow coordination
    "WorkflowPortfolio",
    "PortfolioWorkflowEntry",
    "PortfolioStatus",
    "WorkflowPriority",
    "priority_rank",
    "DependencyGraph",
    "DependencyType",
    "DependencyState",
    "WorkflowDependency",
    "PortfolioScheduler",
    "SchedulingPolicy",
    "PortfolioStepResult",
    "PortfolioStepReason",
    "SelectionReason",
    "WorkflowEligibility",
    # H22-C durable portfolio orchestration (checkpoint / recovery / trace / control)
    "PortfolioCheckpoint",
    "WorkflowCheckpointRef",
    "PortfolioCheckpointStore",
    "InMemoryPortfolioCheckpointStore",
    "PortfolioCheckpointConflict",
    "PortfolioRecoveryResult",
    "recover_portfolio",
    "PortfolioTrace",
    "PortfolioTraceEntry",
    "PortfolioEventType",
    "PortfolioEventStore",
    "InMemoryPortfolioEventStore",
    "PortfolioTraceSequenceError",
    "PortfolioTraceEncodingError",
    "PortfolioController",
    "PortfolioFailurePolicy",
    "CancellationScope",
    "PortfolioCancellationResult",
    # providers
    "Provider",
    "ProviderRegistry",
    "ToolInvocation",
    "ToolResult",
    # persistence
    "Checkpoint",
    "CheckpointStore",
    "RuntimeEventStore",
    "RuntimeStateStore",
    "RuntimeRecoveryResult",
    # governance
    "GovernanceHook",
    "GovernanceEvaluation",
    "GovernanceDisposition",
    "TransitionProposal",
    "ProposalError",
    # canonical execution state
    "CanonicalExecutionState",
    "ExecutionLineage",
    "UnconfiguredGovernanceHook",
    "AllowAllGovernanceHook",
    "NoopGovernanceHook",
    "validate_clearance",
    "ExecutionContext",
    "CorrelationContext",
    # retry
    "RetryPolicy",
    # errors
    "AgentRuntimeError",
    "RuntimeConfigurationError",
    "InvalidTransitionError",
    "ProviderNotFoundError",
    "ProviderExecutionError",
    "CheckpointError",
    "RecoveryError",
    "RuntimeTimeoutError",
    "CancellationError",
    "IntegrityError",
    # functions
    "create_runtime",
    "open_runtime",
    "start_workflow",
    "prepare_workflow",
    "advance_workflow",
    "execution_state",
    "execution_state_by_digest",
    "resume_workflow",
    "continue_workflow",
    "pause_workflow",
    "cancel_workflow",
    "recover_runtime",
    "register_provider",
    "register_governance_hook",
    "create_portfolio",
    "create_portfolio_scheduler",
    "create_portfolio_controller",
]
