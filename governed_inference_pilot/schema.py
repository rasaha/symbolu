"""Canonical governed request + response envelope (Phase 2). Deterministic, stdlib-only. The request
carries everything the stages need; the envelope carries the unified shadow outcome WITHOUT erasing
stage-local outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "gip_request_v1"
ENVELOPE_VERSION = "gip_envelope_v1"


@dataclass
class GovernedRequest:
    request_id: str
    user_prompt: str
    tenant_id: str = "synthetic-tenant"
    session_id: str = ""
    user_role: str = "analyst"
    task_type: str = "qa"
    domain: str = "enterprise_policy"
    risk_tier: str = "medium"                 # low | medium | high | critical
    jurisdiction: str = ""
    system_constraints: List[str] = field(default_factory=list)
    enterprise_policy_refs: List[str] = field(default_factory=list)
    acceptable_quality_threshold: float = 0.6
    cost_constraint_usd: Optional[float] = None
    latency_constraint_ms: Optional[float] = None
    data_sensitivity: str = "internal"
    provider_restrictions: List[str] = field(default_factory=list)
    allowed_models: List[str] = field(default_factory=list)
    prohibited_models: List[str] = field(default_factory=list)
    evidence_requirements: List[str] = field(default_factory=list)
    citation_requirements: bool = False
    action_permissions: List[str] = field(default_factory=list)
    human_review_required: bool = False
    requested_output_form: str = "text"
    timestamp: float = 0.0                     # fixed; determinism (no wall-clock)
    policy_version: str = "gip_policy_v1"
    execution_mode: str = "fixture"            # fixture | recorded | opt_in_local
    source_artifact_ref: str = ""
    expected_labels: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StageEvent:
    stage: str
    component_version: str
    disposition: str
    reason_codes: List[str] = field(default_factory=list)
    source_repr: Dict[str, Any] = field(default_factory=dict)
    transformed_repr: Dict[str, Any] = field(default_factory=dict)
    semantic_loss: List[str] = field(default_factory=list)
    latency_units: int = 0
    error: str = ""


@dataclass
class ResponseEnvelope:
    request_id: str
    final_shadow_disposition: str              # one of dispositions.SHADOW_OUTCOMES
    stage_events: List[Dict[str, Any]] = field(default_factory=list)
    stage_dispositions: Dict[str, str] = field(default_factory=dict)
    reason_codes: List[str] = field(default_factory=list)
    claims: List[str] = field(default_factory=list)
    evidence_states: List[str] = field(default_factory=list)
    action_disposition: str = ""
    human_review_state: str = "not_required"
    uncertainties: List[str] = field(default_factory=list)
    total_latency_units: int = 0
    estimated_cost_usd: float = 0.0
    replay_signature: str = ""
    envelope_version: str = ENVELOPE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
