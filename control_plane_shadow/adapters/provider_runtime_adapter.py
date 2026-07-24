"""Provider runtime adapter (Phase 5) — REPLAY/MOCK only. NO live provider call is ever made
(task constraint). Provider outcomes come from the trace's synthetic fixture or a recorded
failure artifact. Any raw provider error is normalized to RUNTIME.* here and never leaks
downstream (the only boundary permitted to read raw provider errors).
"""
from __future__ import annotations

from typing import Any, Optional

from control_plane_shadow.adapters.base import AdapterHealth, ShadowAdapter
from control_plane_shadow.vocabulary import ExecOutcome


class ProviderRuntimeAdapter(ShadowAdapter):
    component = "ProviderAdapter"
    source_version = "replay_v1"

    def health(self) -> AdapterHealth:
        return AdapterHealth(self.component, available=True, determinism="replay",
                             live_call_risk=False, real_action_risk=False,
                             source_version=self.source_version, adapter_version=self.adapter_version,
                             capabilities=["replay_outcome", "error_normalization", "no_live_call"])

    def call(self, selected_candidate: str, *, outcome: str = "SUCCESS",
             raw_error: Optional[str] = None) -> Any:
        """outcome in {SUCCESS, FAILURE, DISAPPEARED}. No network. Deterministic replay."""
        if outcome == "SUCCESS":
            canonical = {"execution_outcome": ExecOutcome.SUCCESS.value,
                         "executed_candidate": selected_candidate,
                         "model_output_ref": f"replay:{selected_candidate}", "state": "OUTPUT_PRODUCED"}
            return self._result(tier="TIER2", canonical=canonical, source_output={"replay": "success"},
                                reason_codes=[])
        # FAILURE / DISAPPEARED — normalize raw error to RUNTIME.* (never leak raw)
        code = "RUNTIME.PROVIDER_EXECUTION_FAILED" if outcome == "FAILURE" else "RUNTIME.PROVIDER_EXECUTION_FAILED"
        canonical = {"execution_outcome": ExecOutcome.FAILURE.value,
                     "executed_candidate": selected_candidate, "state": "PROVIDER_EXECUTION_FAILED",
                     "normalized_from_raw": bool(raw_error)}
        return self._result(tier="TIER2", canonical=canonical,
                            source_output={"replay": outcome, "raw_present": bool(raw_error)},
                            reason_codes=[code],
                            information_loss=["raw provider error normalized; raw text not propagated"])
