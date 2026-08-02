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
from .models.proposal import TransitionProposal
from .models.results import FailureCategory, RuntimeFailure, RuntimeResult
from .models.task import TaskDefinition, TaskInstance, TaskStatus
from .models.transitions import RuntimeTransition
from .models.workflow import WorkflowDefinition, WorkflowInstance, WorkflowStatus
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
) -> WorkflowInstance:
    return runtime.start_workflow(definition, correlation_id)


def resume_workflow(runtime: AgentRuntime, instance_id: str) -> WorkflowInstance:
    return runtime.resume_workflow(instance_id)


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
    "resume_workflow",
    "pause_workflow",
    "cancel_workflow",
    "recover_runtime",
    "register_provider",
    "register_governance_hook",
]
