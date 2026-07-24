"""Action runtime adapter (Phase 5) — SIMULATE ONLY. This adapter can NEVER execute a real
action (task constraint: no real-world actions, no enforcement). Even if handed an ALLOW
disposition, in any non-ENFORCEMENT mode (all modes reachable here) it records NOT_ATTEMPTED /
SIMULATED and performs no side effect. There is no code path to a real executor.
"""
from __future__ import annotations

from typing import Any, Optional

from control_plane_shadow.adapters.base import AdapterHealth, ShadowAdapter
from control_plane_shadow.vocabulary import ExecOutcome


class ActionRuntimeAdapter(ShadowAdapter):
    component = "ActionAdapter"
    source_version = "sim_only_v1"

    def health(self) -> AdapterHealth:
        return AdapterHealth(self.component, available=True, determinism="deterministic",
                             live_call_risk=False, real_action_risk=False,
                             source_version=self.source_version, adapter_version=self.adapter_version,
                             capabilities=["simulate_only", "no_real_execution"])

    def execute(self, authorized_action: Optional[str], mode: str = "SHADOW") -> Any:
        # No branch executes anything. ENFORCEMENT is never enabled here; even if requested,
        # this adapter refuses (there is no real executor wired).
        outcome = ExecOutcome.NOT_ATTEMPTED.value
        canonical = {"execution_outcome": outcome, "executed": False, "mode": mode,
                     "would_execute": authorized_action, "state": "SIMULATED"}
        return self._result(tier="TIER1", canonical=canonical,
                            source_output={"simulated": True, "real_action": False},
                            reason_codes=[])
