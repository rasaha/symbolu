"""Typed error taxonomy for the Agent Runtime migration package.

Every failure mode is explicit. Nothing here authorizes execution; these signal
runtime-local rejection (fail closed) or a governance-boundary violation.
"""
from __future__ import annotations


class AgentRuntimeError(Exception):
    """Base class for all runtime errors."""


class ContractError(AgentRuntimeError):
    """A typed contract (Goal/Plan/Action/Observation/Result) is malformed."""


class ProposalError(AgentRuntimeError):
    """A CER proposal is incomplete or invalid and must not be submitted (fail closed)."""


class GovernanceBoundaryError(AgentRuntimeError):
    """An attempt to cross the ownership boundary (e.g. execute a governed action
    without an eligible control-plane decision, or mint authorization in the runtime)."""


class ToolPolicyError(AgentRuntimeError):
    """A tool's risk class is unknown or the requested fast path is not policy-permitted."""


class RetryExhaustedError(AgentRuntimeError):
    """Retries exhausted for a step."""


class CancelledError(AgentRuntimeError):
    """The run was cancelled at a checkpoint."""


class BudgetExceededError(AgentRuntimeError):
    """A runtime-local budget/deadline safeguard stopped the run (not an authorization)."""
