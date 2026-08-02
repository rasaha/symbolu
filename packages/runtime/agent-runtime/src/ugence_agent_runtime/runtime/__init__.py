"""Runtime engine, lifecycle, execution, retry/timeout/cancellation, errors.

``AgentRuntime`` is exposed lazily (via module ``__getattr__``) so that importing
``ugence_agent_runtime.runtime.errors`` — which the models layer needs — does not
eagerly pull in the engine (which depends on config, providers, persistence, and
governance) and create an import cycle.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .cancellation import CancellationToken
from .errors import (
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
from .lifecycle import is_task_terminal, is_workflow_terminal
from .retry import RetryPolicy

if TYPE_CHECKING:  # pragma: no cover
    from .engine import AgentRuntime


def __getattr__(name: str):
    if name == "AgentRuntime":
        from .engine import AgentRuntime as _AgentRuntime

        return _AgentRuntime
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AgentRuntime",
    "CancellationToken",
    "RetryPolicy",
    "is_task_terminal",
    "is_workflow_terminal",
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
]
