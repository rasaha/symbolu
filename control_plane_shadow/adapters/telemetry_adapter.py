"""Telemetry adapter (Phase 5). Wraps the prior track's prospective Telemetry/RegistryUpdater
(control_plane.telemetry) — observations are prospective-only and never rewrite the in-flight
trace (invariants 11,12). No side effects beyond an in-memory queue.
"""
from __future__ import annotations

from typing import Any, Optional

from control_plane.telemetry import Telemetry
from control_plane_shadow.adapters.base import AdapterHealth, ShadowAdapter


class TelemetryAdapter(ShadowAdapter):
    component = "Telemetry"
    source_version = "control_plane_telemetry_v1"

    def __init__(self, available: bool = True):
        self.telemetry = Telemetry()
        self._available = available

    def health(self) -> AdapterHealth:
        return AdapterHealth(self.component, available=self._available, determinism="deterministic",
                             live_call_risk=False, real_action_risk=False,
                             source_version=self.source_version, adapter_version=self.adapter_version,
                             capabilities=["prospective_only", "observation_queue"])

    def observe(self, trace_id: str, target: str, outcome: str, now: float) -> Any:
        if not self._available:
            return self._result(tier="TIER1", canonical={"state": "TELEMETRY_UNAVAILABLE"},
                                reason_codes=["AUDIT.TELEMETRY_WRITE_FAILED"], health="UNAVAILABLE")
        obs = self.telemetry.record_outcome(trace_id, target, outcome, now)
        circ = self.telemetry.feed_forward(obs)                 # prospective; may reject circular
        canonical = {"state": "RECORDED", "prospective": True, "target": target, "outcome": outcome}
        codes = [circ.value] if circ else []
        return self._result(tier="TIER1", canonical=canonical, source_output={"prospective": True},
                            reason_codes=codes)
