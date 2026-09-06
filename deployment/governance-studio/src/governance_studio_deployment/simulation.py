"""Front-door seam 3 (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md FD-7): the one pinned
simulation provider the P3E profile hands the Simulate screen.

    THIS PROVIDER ACTS ON NOTHING. It records each invocation in memory and answers
    success. It opens no socket, reads no file, spawns nothing and holds no credential.

FD-7.1 admits a run whose every provider is this one, under DRY_RUN, SIMULATION or
SHADOW, as a demonstration rather than agent execution. FD-7.3 hands the runtime the
provider registry only: ``governance_hook`` stays the runtime's fail-closed default, so
every consequential task BLOCKs with ``GOVERNANCE_NOT_CONFIGURED`` and the trace shows
it. FD-7.4 pins exactly one provider, named here, never discovered. FD-7.5 prohibits a
permissive hook: :func:`refuse_permissive_hook` runs on the composed studio context
before the port binds, and :func:`permissive_hook_source_findings` is the startup
integrity gate's static proof that nothing in this package can construct one.
"""
from __future__ import annotations

import os
from typing import Any, List, Tuple

from ugence_agent_runtime.providers.interfaces import ToolInvocation, ToolResult
from ugence_agent_runtime.providers.registry import ProviderRegistry

from .config import DeploymentConfigError

__all__ = [
    "SIMULATION_PROVIDER_ID",
    "SIMULATION_PROVIDER_VERSION",
    "SIMULATION_PROVIDER_MATURITY",
    "StudioSimulationProvider",
    "build_simulation_registry",
    "refuse_permissive_hook",
    "permissive_hook_source_findings",
]

#: The id the Simulate screen's sample workflow already names (SimulateScreen.tsx); the
#: only provider id the registry ever holds.
SIMULATION_PROVIDER_ID = "fixture"
SIMULATION_PROVIDER_VERSION = "0.1.0"
SIMULATION_PROVIDER_MATURITY = "DEMONSTRATION_ONLY"

#: Tokens whose presence in this package's source would mean a permissive hook could be
#: constructed or handed. Assembled from parts so this file cannot match itself.
_PERMISSIVE_TOKENS: Tuple[str, ...] = (
    "AllowAll" + "GovernanceHook",
    "Noop" + "GovernanceHook",
    "hook_is_permissive" + "=True",
    "governance_hook" + "=",
)


class StudioSimulationProvider:
    """Records each invocation and returns success. No external effect of any kind."""

    provider_id = SIMULATION_PROVIDER_ID
    version = SIMULATION_PROVIDER_VERSION
    maturity = SIMULATION_PROVIDER_MATURITY

    def __init__(self) -> None:
        self.calls: List[Tuple[str, str, str]] = []

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        mode = str(invocation.arguments.get("execution_mode", ""))
        self.calls.append((invocation.idempotency_key or "", invocation.operation, mode))
        return ToolResult(
            provider_id=self.provider_id, operation=invocation.operation, ok=True,
            output={"recorded": True, "simulation": True, "execution_mode": mode,
                    "provider_version": self.version, "maturity": self.maturity},
        )


def build_simulation_registry() -> ProviderRegistry:
    """A registry holding exactly the one pinned provider (FD-7.4)."""

    registry = ProviderRegistry()
    registry.register(StudioSimulationProvider())
    return registry


def refuse_permissive_hook(studio: Any) -> None:
    """FD-7.5: the composed studio context must carry no governance hook of any kind
    (FD-7.3 leaves the runtime's fail-closed default in place) and must not be labelled
    permissive. Raises before the port binds; never widens."""

    simulate = getattr(studio, "simulate", None)
    if simulate is None:
        raise DeploymentConfigError("the studio context has no Simulate service to inspect")
    if getattr(simulate, "_hook", None) is not None:
        raise DeploymentConfigError(
            "a governance hook was handed to the Simulate service; FD-7.3 leaves the "
            "runtime's fail-closed default in place and FD-7.5 prohibits a permissive one")
    if getattr(simulate, "_hook_is_permissive", False):
        raise DeploymentConfigError(
            "the Simulate service is labelled permissive; FD-7.5 prohibits that in this profile")


def permissive_hook_source_findings(package_dir: str) -> List[str]:
    """Which files under ``package_dir`` carry a token that could construct or hand a
    permissive hook. Empty means none can. Run by the startup integrity gate."""

    findings: List[str] = []
    for name in sorted(os.listdir(package_dir)):
        if not name.endswith(".py"):
            continue
        text = open(os.path.join(package_dir, name), encoding="utf-8").read()
        for token in _PERMISSIVE_TOKENS:
            if token in text:
                findings.append(f"{name}: {token}")
    return findings
