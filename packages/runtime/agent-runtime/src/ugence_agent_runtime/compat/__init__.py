"""Migration guidance from the legacy proposer to the coordination kernel.

**This is NOT a runtime-compatibility shim.** The legacy runtime
``agent_runtime_migration.runtime.runtime.AgentRuntime`` is a *different
implementation* with an incompatible API: it is a Goal→Plan→Action→Reflect proposer
constructed as ``AgentRuntime(*, executor, planner=..., reflector=..., memory=...)``
and driven by ``run(goal)``. The kernel ``ugence_agent_runtime.api.AgentRuntime`` is a
workflow/task coordinator constructed as ``AgentRuntime(config)`` and driven by
``start_workflow(definition)``. Neither can substitute for the other.

Accordingly, this module offers **migration pointers and an honest classification**,
not aliases that pretend the two are the same object. See
``docs/AGENT_RUNTIME_COMPATIBILITY.md`` and
``artifacts/agent_runtime_fidelity_matrix.json``.
"""
from __future__ import annotations

from typing import Dict

# Legacy import path -> {new target or classification}. Classifications match the
# fidelity matrix. A ``new`` value of None means "no kernel equivalent — remains a
# legacy concern" (planning/memory/reflection/CER integration).
MIGRATION_MAP: Dict[str, Dict[str, object]] = {
    "agent_runtime_migration.runtime.runtime.AgentRuntime": {
        "new": None,
        "classification": "PRESENT_CHANGED",
        "note": "Legacy proposer loop; the kernel AgentRuntime is a different, "
                "workflow/task implementation. Not API-compatible.",
    },
    "agent_runtime_migration.workflow.Workflow": {
        "new": "ugence_agent_runtime.api.WorkflowDefinition",
        "classification": "PRESENT_CHANGED",
        "note": "Remodeled; different fields and status vocabulary.",
    },
    "agent_runtime_migration.workflow.Checkpoint": {
        "new": "ugence_agent_runtime.api.Checkpoint",
        "classification": "PRESENT_CHANGED",
        "note": "Remodeled with a content digest; different serialized shape.",
    },
    "agent_runtime_migration.tools.registry": {
        "new": "ugence_agent_runtime.api.ProviderRegistry",
        "classification": "PRESENT_CHANGED",
        "note": "Tool registry replaced by a neutral provider registry.",
    },
    "agent_runtime_migration.tracing.events.RuntimeEvent": {
        "new": "ugence_agent_runtime.models.events.RuntimeEvent",
        "classification": "PRESENT_CHANGED",
        "note": "Event vocabulary changed to coordination events.",
    },
    "agent_runtime_migration.planning": {
        "new": None,
        "classification": "INTENTIONALLY_EXCLUDED",
        "note": "Planning is not a coordination-kernel concern.",
    },
    "agent_runtime_migration.reasoning": {
        "new": None,
        "classification": "INTENTIONALLY_EXCLUDED",
    },
    "agent_runtime_migration.memory": {
        "new": None,
        "classification": "INTENTIONALLY_EXCLUDED",
    },
    "agent_runtime_migration.control_plane": {
        "new": None,
        "classification": "LEGACY_INTEGRATION_ONLY",
        "note": "Concrete cer_v0_3 control-plane integration; kernel uses a neutral hook.",
    },
    "agent_runtime_migration.proposal": {
        "new": None,
        "classification": "LEGACY_INTEGRATION_ONLY",
        "note": "Concrete CER construction; stays legacy.",
    },
}


def classify(legacy_path: str) -> str:
    """Return the fidelity classification for a legacy import path.

    Raises ``KeyError`` if the path is not a recognized legacy subsystem.
    """
    return str(MIGRATION_MAP[legacy_path]["classification"])


def new_target(legacy_path: str):
    """Return the kernel import path that supersedes a legacy path, or None when the
    legacy concern has no kernel equivalent (excluded or legacy-integration-only)."""
    return MIGRATION_MAP[legacy_path]["new"]


__all__ = ["MIGRATION_MAP", "classify", "new_target"]
