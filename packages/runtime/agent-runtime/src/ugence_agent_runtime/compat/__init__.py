"""Compatibility re-exports for callers migrating to the independent package.

Every alias exported here resolves to the SAME object as its canonical counterpart
in the curated public API — this module reimplements nothing. It exists so a
consumer that previously reached for a differently-named coordination primitive can
import it from one stable place while it migrates to ``ugence_agent_runtime.api``.

Accessing a deprecated alias emits a ``DeprecationWarning`` pointing at the canonical
import. See docs/AGENT_RUNTIME_COMPATIBILITY.md for the full map.
"""
from __future__ import annotations

import warnings

from .. import api as _api

# legacy alias -> canonical name in ugence_agent_runtime.api
_DEPRECATED = {
    "Runtime": "AgentRuntime",
    "Workflow": "WorkflowDefinition",
    "WorkflowRun": "WorkflowInstance",
    "Task": "TaskDefinition",
    "TaskRun": "TaskInstance",
    "WorkflowCheckpoint": "Checkpoint",
    "Registry": "ProviderRegistry",
    "Result": "RuntimeResult",
}

# old fully-qualified import path -> new canonical import (machine-readable artifact
# lives at artifacts/agent_runtime_compatibility_map.json).
COMPATIBILITY_MAP = {
    "agent_runtime_migration.workflow.Workflow": "ugence_agent_runtime.api.WorkflowDefinition",
    "agent_runtime_migration.workflow.Checkpoint": "ugence_agent_runtime.api.Checkpoint",
    "agent_runtime_migration.runtime.runtime.AgentRuntime": "ugence_agent_runtime.api.AgentRuntime",
    "agent_runtime_migration.tools.registry.ToolRegistry": "ugence_agent_runtime.api.ProviderRegistry",
    "agent_runtime_migration.tracing.events.RuntimeEvent": "ugence_agent_runtime.models.events.RuntimeEvent",
}


def resolve(alias: str):
    """Return the canonical object for a legacy alias without emitting a warning.

    Useful for tests and tooling that need to assert identity with the canonical
    symbol (check 48: compatibility imports reference the new implementation)."""
    if alias not in _DEPRECATED:
        raise AttributeError(alias)
    return getattr(_api, _DEPRECATED[alias])


def __getattr__(name: str):
    if name in _DEPRECATED:
        warnings.warn(
            f"ugence_agent_runtime.compat.{name} is a compatibility alias; import "
            f"{_DEPRECATED[name]} from ugence_agent_runtime.api instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(_api, _DEPRECATED[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = list(_DEPRECATED) + ["COMPATIBILITY_MAP", "resolve"]
