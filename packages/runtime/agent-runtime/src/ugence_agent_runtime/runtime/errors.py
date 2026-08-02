"""Stable, curated error taxonomy for the Agent Runtime.

Expected runtime outcomes (provider failure, governance HOLD/BLOCK, timeout) are
reported as result/failure *objects*, not exceptions. These exceptions signal
programming or integrity errors — misconfiguration, illegal transitions, corrupt
checkpoints. Raw backend exceptions are never exposed as the public contract; they
are wrapped in one of these.
"""
from __future__ import annotations


class AgentRuntimeError(Exception):
    """Base class for all Agent Runtime errors."""


class RuntimeConfigurationError(AgentRuntimeError):
    """The runtime configuration is invalid or internally inconsistent."""


class InvalidTransitionError(AgentRuntimeError):
    """An attempted task/workflow state change is not permitted by the state machine."""


class ProposalError(AgentRuntimeError):
    """A transition proposal is malformed — e.g. it carries an argument value that is
    not a supported, deterministically canonicalizable type. Fails closed rather than
    relying on unstable ``repr()`` output for identity."""


class ProviderNotFoundError(AgentRuntimeError):
    """A task references a provider id that is not registered."""


class ProviderExecutionError(AgentRuntimeError):
    """A provider raised or reported an execution error. Retriable unless marked
    otherwise via ``retriable=False``."""

    def __init__(self, message: str, *, retriable: bool = True) -> None:
        super().__init__(message)
        self.retriable = retriable


class CheckpointError(AgentRuntimeError):
    """A checkpoint could not be committed, is malformed, or is corrupt."""


class RecoveryError(AgentRuntimeError):
    """Recovery could not reconstruct a consistent runtime state (fail closed)."""


class RuntimeTimeoutError(AgentRuntimeError):
    """A task exceeded its runtime-local timeout budget."""


class CancellationError(AgentRuntimeError):
    """The run was cancelled cooperatively."""


class IntegrityError(AgentRuntimeError):
    """A persisted record failed an integrity/consistency check (fail closed)."""
