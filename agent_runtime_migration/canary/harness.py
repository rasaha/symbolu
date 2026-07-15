"""Read-only canary harness (Phase 2 §6).

A narrowly scoped runner limited to TRUSTED read-only tools. It cannot register or
run a write/delete/execute/privileged tool (a governed tool is rejected at
registration). Consequential tools remain shadow-only through CER → ActionGate → ACP
elsewhere; they are simply not part of the canary.

Guarantees:
* risk class comes from the trusted registry;
* kill switch (cancels the run);
* bounded runtime (step + iteration budget);
* cancellation;
* full trace + observation return;
* EXPLICIT, auditable fallback to the legacy runtime — never a silent fallback after a
  new-runtime failure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from ..contracts.action import RiskClass
from ..contracts.errors import ToolPolicyError
from ..contracts.goal import Goal
from ..control_plane import ControlPlaneClient, GovernedExecutor
from ..runtime import AgentRuntime, BudgetAccountant, CancellationToken
from ..runtime.resolution import ResolutionBudget
from ..tools import ToolRegistry


class ReadOnlyRegistry(ToolRegistry):
    """A registry that REFUSES anything that is not a policy-permitted read-only tool."""

    def register(self, name, handler, risk_class, *, profile=None, fast_path_permitted=False):
        if risk_class is not RiskClass.LOCAL_READ_ONLY:
            raise ToolPolicyError(
                f"canary refuses non-read-only tool {name!r} ({risk_class}); consequential "
                "tools remain shadow-only via CER -> ActionGate -> ACP, not in the canary")
        if not fast_path_permitted:
            raise ToolPolicyError(f"canary tool {name!r} must be fast_path_permitted read-only")
        super().register(name, handler, risk_class, profile=None, fast_path_permitted=True)


@dataclass
class CanaryResult:
    status: str
    observations: List[Any] = field(default_factory=list)
    trace_types: List[str] = field(default_factory=list)
    tool_calls: int = 0
    kill_switch_triggered: bool = False
    fallback_used: bool = False
    fallback_reason: str = ""
    error: Optional[str] = None


class KillSwitch:
    def __init__(self) -> None:
        self._token = CancellationToken()

    def engage(self) -> None:
        self._token.cancel()

    @property
    def engaged(self) -> bool:
        return self._token.cancelled

    @property
    def token(self) -> CancellationToken:
        return self._token


class ReadOnlyCanary:
    def __init__(self, registry: ReadOnlyRegistry, *, max_steps: int = 16,
                 legacy_fallback: Optional[Callable[[Goal], Any]] = None):
        if not isinstance(registry, ReadOnlyRegistry):
            raise ToolPolicyError("canary requires a ReadOnlyRegistry")
        self._registry = registry
        self._max_steps = max_steps
        self._legacy_fallback = legacy_fallback
        self.kill = KillSwitch()

    def run(self, goal: Goal, *, planner=None, allow_fallback: bool = False) -> CanaryResult:
        executor = GovernedExecutor(registry=self._registry, client=ControlPlaneClient(),
                                    now_provider=lambda: "2026-01-01T00:10:00.000Z")
        runtime = AgentRuntime(executor=executor, planner=planner,
                               budget=BudgetAccountant(max_steps=self._max_steps))
        try:
            out = runtime.run(goal, run_id=f"canary:{goal.goal_id}", cancellation=self.kill.token,
                              resolution_budget=ResolutionBudget(max_iterations=max(8, self._max_steps * 2)))
        except Exception as exc:  # noqa: BLE001 - new-runtime failure
            # NO silent fallback: a fallback is used only if explicitly allowed, and is audited.
            if allow_fallback and self._legacy_fallback is not None:
                self._legacy_fallback(goal)
                return CanaryResult(status="fallback", fallback_used=True,
                                    fallback_reason=f"new-runtime error: {type(exc).__name__}: {exc}",
                                    error=str(exc))
            return CanaryResult(status="error", error=f"{type(exc).__name__}: {exc}")

        tool_calls = sum(1 for o in out.observations if o.outcome == "local")
        return CanaryResult(status=out.status, observations=out.observations,
                            trace_types=out.trace.types(), tool_calls=tool_calls,
                            kill_switch_triggered=self.kill.engaged)
