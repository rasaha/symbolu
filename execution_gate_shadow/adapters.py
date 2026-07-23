"""Provider adapters for the shadow harness (Phase 12).

MockProviderAdapter is deterministic and needs no credentials — used for all tests and the
dry run. RealProviderAdapter is a guarded stub: it refuses unless live calls are explicitly
enabled and every safety guard passes. This task never enables live calls.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from execution_gate_shadow.config import SafetyError, ShadowConfig


class ProviderAdapter:
    provider: str = "abstract"
    is_live: bool = False

    def observe(self, model_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class MockProviderAdapter(ProviderAdapter):
    """Returns a pre-specified raw outcome per model (ground truth). No network, no creds."""
    is_live = False

    def __init__(self, provider: str, ground_truth: Dict[str, Dict[str, Any]]):
        self.provider = provider
        self._gt = ground_truth   # model_id -> raw outcome dict for outcomes.normalize()

    def observe(self, model_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        raw = dict(self._gt.get(model_id, {"attempted": False}))
        raw.setdefault("attempted", True)
        return raw


class RealProviderAdapter(ProviderAdapter):
    """Guarded real adapter. Refuses unless live is explicitly enabled and guards pass.
    Deliberately does NOT implement a network call in this track."""
    is_live = True

    def __init__(self, provider: str, config: ShadowConfig):
        self.provider = provider
        self.config = config

    def observe(self, model_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        # Guard first; even when enabled, this track does not perform real calls.
        self.config.assert_live_allowed(self.provider, model_id, request.get("est_cost"))
        raise SafetyError("real provider execution is out of scope for this track "
                          "(live calls are not performed here even when enabled)")
