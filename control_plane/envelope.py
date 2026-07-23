"""Request envelope (Phase 4) + policy context. References + metadata only; no credentials."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

ENVELOPE_VERSION = "1"
MODES = {"REPLAY", "MOCK", "SHADOW", "ADVISORY", "ENFORCEMENT"}
_CONFIDENTIAL = {"tenant_ref", "human_authority_ref", "content_ref"}


@dataclass
class RequestEnvelope:
    request_id: str
    trace_id: str
    task_type: str = "qa"
    task_risk_class: str = "informational"        # informational|advisory|decision-bearing|irreversible
    input_classification: str = "internal"
    data_sensitivity: str = "internal"
    residency_requirements: Optional[str] = None
    provider_allowlist: Optional[Set[str]] = None
    provider_denylist: Set[str] = field(default_factory=set)
    required_capabilities: Set[str] = field(default_factory=set)
    context_tokens: int = 1000
    latency_budget_ms: Optional[float] = None
    cost_budget_usd: Optional[float] = None
    quality_floor: float = 0.0
    assertion_policy: Dict[str, Any] = field(default_factory=dict)
    action_policy: Dict[str, Any] = field(default_factory=dict)   # {'permitted':[], 'require_approval':[]}
    approval_requirements: List[str] = field(default_factory=list)
    human_authority_ref: Optional[str] = None
    policy_versions: Dict[str, str] = field(default_factory=lambda: {"assertion": "v1", "action": "v1", "enterprise": "v1"})
    registry_version: str = "reg_v1"
    mode: str = "MOCK"
    content_ref: str = "sha256:none"
    redaction_state: str = "redacted"
    provenance: str = "test"
    timestamp: float = 1_000_000.0
    envelope_version: str = ENVELOPE_VERSION
    parent_trace_id: Optional[str] = None

    def compatible(self) -> bool:
        return self.envelope_version == ENVELOPE_VERSION and self.mode in MODES

    def authority(self) -> Dict[str, Any]:
        """The bound authority envelope ActionGate may never exceed."""
        return {"permitted_actions": set(self.action_policy.get("permitted", [])),
                "require_approval": set(self.action_policy.get("require_approval", [])),
                "risk_class": self.task_risk_class}


def redact_envelope(env: RequestEnvelope) -> Dict[str, Any]:
    d = {k: (sorted(v) if isinstance(v, set) else v) for k, v in env.__dict__.items()}
    for k in _CONFIDENTIAL:
        if d.get(k):
            d[k] = "<redacted>"
    return d
