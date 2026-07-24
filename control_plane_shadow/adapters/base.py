"""Shared adapter result + discipline for the shadow pilot (Phase 5).

Every adapter: wraps a real (or replay) component, PRESERVES the original output verbatim,
emits the canonical contract payload, records information loss, normalizes reason codes,
attaches source + adapter versions, exposes health/capability metadata, and causes NO side
effects. Adapters never invent evidence, never upgrade INDETERMINATE to approval, never call a
live provider, never execute a real action, never mutate the wrapped component.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ADAPTER_FRAMEWORK_VERSION = "shadow_adapter_v1"


@dataclass
class ShadowAdapterResult:
    component: str
    tier: str                                   # evidence tier for THIS invocation (e.g. "TIER3")
    canonical: Dict[str, Any]                   # the canonical contract payload
    source_output: Any = None                   # ORIGINAL component output, preserved verbatim
    reason_codes: List[str] = field(default_factory=list)   # namespaced (EXEC./MODEL./ASSERT./ACTION./...)
    information_loss: List[str] = field(default_factory=list)  # fields present in source, absent in canonical
    derived_fields: List[str] = field(default_factory=list)    # canonical fields not 1:1 from source (rule-backed)
    provenance: List[Dict[str, Any]] = field(default_factory=list)
    source_version: str = ""
    adapter_version: str = ""
    health: str = "OK"                          # OK | DEGRADED | UNAVAILABLE
    error: Optional[str] = None


@dataclass
class AdapterHealth:
    component: str
    available: bool
    determinism: str                            # "deterministic" | "replay" | "nondeterministic"
    live_call_risk: bool
    real_action_risk: bool
    source_version: str
    adapter_version: str
    capabilities: List[str] = field(default_factory=list)


class ShadowAdapter:
    """Base class. Subclasses set component/source_version/adapter_version and implement health()."""
    component = "base"
    source_version = ""
    adapter_version = ADAPTER_FRAMEWORK_VERSION

    def health(self) -> AdapterHealth:          # pragma: no cover - overridden
        raise NotImplementedError

    def _result(self, **kw) -> ShadowAdapterResult:
        kw.setdefault("component", self.component)
        kw.setdefault("source_version", self.source_version)
        kw.setdefault("adapter_version", self.adapter_version)
        return ShadowAdapterResult(**kw)
