"""Shadow-pilot configuration and hard safety guards (Phase 13).

Defaults are safe: live provider calls DISABLED, synthetic-only, empty allowlist.
Any real call requires an explicit flag AND passing every guard.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set


class SafetyError(RuntimeError):
    """Raised when a hard safety guard is violated. Aborts the run."""


@dataclass
class ShadowConfig:
    # --- live-call gating (all default to the safe value) ---
    live_calls_enabled: bool = False          # must be explicitly True for ANY real provider call
    synthetic_probes_only: bool = True         # counterfactual probes use synthetic content only
    approved_providers: Set[str] = field(default_factory=set)   # explicit allowlist (empty => none)
    approved_models: Set[str] = field(default_factory=set)      # explicit model allowlist

    # --- resource caps ---
    spend_cap_usd: float = 0.0                 # 0 => no spend permitted
    request_cap: int = 0                       # 0 => no live requests permitted
    quota_cap: int = 0                         # max probe/live calls against provider quota

    max_added_latency_ms: float = 5000.0

    # --- protocol/version guards ---
    protocol_version: Optional[str] = None     # must be set (non-None) to run
    manifest_required: bool = True

    # --- privacy ---
    persist_raw_content: bool = False          # never persist raw prompt/response by default

    def assert_runnable(self):
        if self.manifest_required and not self.protocol_version:
            raise SafetyError("protocol_version missing; refusing to run without a protocol/manifest")

    def assert_live_allowed(self, provider: str, model_id: str, est_cost: Optional[float]):
        """Every condition must pass before a REAL provider call is permitted."""
        if not self.live_calls_enabled:
            raise SafetyError("live calls disabled by default; explicit enable required")
        if provider not in self.approved_providers:
            raise SafetyError(f"provider '{provider}' not on approved allowlist")
        if model_id not in self.approved_models:
            raise SafetyError(f"model '{model_id}' not on approved allowlist")
        if est_cost is None:
            raise SafetyError("cost could not be estimated; refusing live call")
        if self.spend_cap_usd <= 0 or self.request_cap <= 0:
            raise SafetyError("spend_cap/request_cap not configured for live calls")
