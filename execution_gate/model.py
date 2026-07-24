"""Runtime data types: Request, Candidate, Signal, GateConfig."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from execution_gate.states import Evidence


@dataclass
class Signal:
    """One observed operational fact about a candidate, with its evidence.
    value == None means UNKNOWN (never silently treated as a pass)."""
    value: Any
    evidence: Evidence
    reason_hint: Optional[str] = None   # e.g. 'DNS_FAILURE' to disambiguate a False reachable


@dataclass
class Request:
    """The task's execution requirements (governance + technical + operational)."""
    request_id: str
    context_tokens: int = 1000
    features_required: Set[str] = field(default_factory=set)   # {'structured_output','tool_use'}
    approved_providers: Optional[Set[str]] = None              # None => no enterprise allowlist
    region_allowed: Optional[Set[str]] = None                  # None => any region
    residency_required: Optional[str] = None                   # e.g. 'eu' / 'us'
    latency_limit_ms: Optional[float] = None
    cost_cap_usd: Optional[float] = None
    est_output_tokens: int = 200


@dataclass
class Candidate:
    """A provider/model with declared metadata and observed signals."""
    provider: str            # serving provider (e.g. 'anthropic', 'google', 'alibaba_modelstudio')
    model_id: str            # exact provider model ID
    family: str              # 'claude' | 'gemma' | 'gemini' | 'qwen' | ...
    developer: str = ""      # model developer (may differ from serving provider)
    region: str = "global"
    context_limit: int = 8000
    structured_output: bool = False
    tool_use: bool = False
    price_in_per_mtok: float = 0.0
    price_out_per_mtok: float = 0.0
    signals: Dict[str, Signal] = field(default_factory=dict)


@dataclass
class GateConfig:
    allow_conditional: bool = True
    require_billing: bool = False           # True => unknown billing is INELIGIBLE, not INDETERMINATE
    reliability_floor: float = 0.90
    default_latency_limit_ms: float = 60000.0
    # CRITICAL-OP conditions whose UNKNOWN is INDETERMINATE rather than fail-closed:
    indeterminate_on_unknown: Set[str] = field(
        default_factory=lambda: {"billing_active", "credential_expiry_valid"})
    policy_version: str = "exec_gate_v1"
