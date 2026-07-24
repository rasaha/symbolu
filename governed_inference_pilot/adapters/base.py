"""Adapter base (Phase 9). Common result type. Each adapter imports its component READ-ONLY, exposes a
stable pilot contract, preserves the original output, maps to canonical schema, emits semantic-loss
warnings, exposes versions, records a deterministic latency-unit cost, records exceptions, and FAILS
CLOSED on unknown critical states. Adapters do not duplicate component logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AdapterResult:
    stage: str
    component_version: str
    local_disposition: str
    reason_codes: List[str] = field(default_factory=list)
    source_repr: Dict[str, Any] = field(default_factory=dict)
    transformed_repr: Dict[str, Any] = field(default_factory=dict)
    semantic_loss: List[str] = field(default_factory=list)
    latency_units: int = 1
    cost_usd: float = 0.0
    error: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


def safe(fn):
    """Wrap an adapter call so a component exception becomes a fail-closed AdapterResult, never a
    silent success."""
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as e:  # noqa: BLE001 - deliberate: any component fault fails closed
            stage = getattr(fn, "_stage", "unknown")
            return AdapterResult(stage=stage, component_version="?", local_disposition="INDETERMINATE",
                                 reason_codes=["GIP.STAGE_EXCEPTION"], error=f"{type(e).__name__}: {e}")
    return wrapper
