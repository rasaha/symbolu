"""
Governance API Request / Response Models

Pydantic models for the external authorization service.

SCHEMA MAPPING:
    External API Request → Internal Governance Inputs:
        - action_type, tool_name, capabilities → ToolRiskClassifier + SafetyContract
        - quality_score, coherence_score, etc. → ConfidenceSignals → ConfidenceGate
        - agency_level → SafetyContract precondition 6
        - actor_id, session_id, request_id → Audit metadata
        - readiness_level, blocking_factors → P52/P53 pipeline compatibility

    Internal Governance Outputs → External API Response:
        - SafetyContract.eligible → eligible
        - ConfidenceGate.execution.mode → execution_mode
        - ConfidenceGate.escalation.level → escalation_level
        - ToolRiskClassifier.classify() → risk_level
        - P52 GovernanceDecision mapping → decision (ALLOW/DENY/DEFER)

    P52/P53 COMPATIBILITY:
        - Response includes governance_decision matching GovernanceDecision Literal
        - Response includes rationale_codes matching P53 GovernanceBindingEnvelope
        - Response includes audit_reference for P54 compatibility

FUTURE WORK:
    - dry_run: Field present but service always operates in decision-only mode
    - tenant_id / org_id: Fields present for future per-tenant policy store
    - persistent audit backend: Structured audit events ready for external storage
"""

from __future__ import annotations

import time
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from agentic.entropy.types import EntropyResult


# =============================================================================
# Enums (mirror internal enums for API stability)
# =============================================================================


class APIGovernanceDecision(str, Enum):
    """Top-level governance decision. Mirrors P52 GovernanceDecision."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    DEFER = "DEFER"


class APIExecutionMode(str, Enum):
    """Execution permission mode. Mirrors confidence_gate.ExecutionMode."""
    FULL = "full"
    CAUTIOUS = "cautious"
    CONFIRM_REQUIRED = "confirm"
    BLOCKED = "blocked"


class APIEscalationLevel(str, Enum):
    """Escalation level. Mirrors confidence_gate.EscalationLevel."""
    NONE = "none"
    NOTIFY = "notify"
    CONFIRM = "confirm"
    HALT = "halt"


class APIToolRiskLevel(str, Enum):
    """Tool risk classification. Mirrors mcp_gateway.ToolRiskLevel."""
    READ_ONLY = "read_only"
    WRITE = "write"
    EXECUTE = "execute"
    DESTRUCTIVE = "destructive"
    PRIVILEGED = "privileged"


# =============================================================================
# Request Model
# =============================================================================


class AuthorizationRequest(BaseModel):
    """
    External authorization request from any agent.

    Maps to internal governance constructs:
        - action_type + tool_name → ToolRiskClassifier
        - confidence signals → ConfidenceGate
        - agency_level → SafetyContract precondition 6
        - capabilities → forbidden capability check
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Identity / traceability
    actor_id: str = Field(
        ..., description="Identifier for the requesting agent or user",
        min_length=1, max_length=256,
    )
    session_id: Optional[str] = Field(
        None, description="Session identifier for context tracking",
        max_length=256,
    )
    request_id: Optional[str] = Field(
        None, description="Caller-provided request ID for correlation",
        max_length=256,
    )

    # Action being proposed
    action_type: str = Field(
        ..., description="Type of action proposed (e.g. 'file_read', 'database_modify', 'send_email')",
        min_length=1, max_length=256,
    )
    tool_name: Optional[str] = Field(
        None, description="MCP tool name if applicable",
        max_length=256,
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="Declared capabilities the action requires",
    )
    parameters_summary: Optional[Dict[str, Any]] = Field(
        None, description="Summary of action parameters (do NOT include secrets)",
    )

    # Agency / intent
    agency_level: str = Field(
        "INFORM",
        description="Declared agency level: FULL, CONFIRM, or INFORM",
    )

    # Confidence / quality signals (optional — defaults are conservative)
    quality_score: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Quality score from agent's self-assessment [0.0, 1.0]",
    )
    coherence_score: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Coherence score from agent's state [0.0, 1.0]",
    )
    internal_consistency: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Internal reasoning consistency [0.0, 1.0]",
    )
    goal_alignment: float = Field(
        0.5, ge=0.0, le=1.0,
        description="How well action aligns with stated goal [0.0, 1.0]",
    )
    trajectory_confidence: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Session trajectory confidence [0.0, 1.0]",
    )

    # Pipeline compatibility (optional)
    readiness_level: Optional[str] = Field(
        None, description="P51 readiness level: READY, CONDITIONAL, NOT_READY",
    )
    blocking_factors: List[str] = Field(
        default_factory=list,
        description="P51-style blocking factors",
    )

    # Tenant / org (future per-tenant policy)
    tenant_id: Optional[str] = Field(
        None, description="Tenant identifier for future policy scoping",
        max_length=256,
    )
    org_id: Optional[str] = Field(
        None, description="Organization identifier for future policy scoping",
        max_length=256,
    )

    # Control flags
    dry_run: bool = Field(
        False,
        description="If true, evaluate but mark response as dry_run. "
                    "Note: this service never executes actions regardless.",
    )

    # Sovereign projection metadata (optional — from inference bridge)
    sovereign_projection_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Optional sovereign inference bridge projection metadata. "
            "When present, carries reasoning diagnostics, guna anomalies, "
            "and governor telemetry for S3/S4 governance signals."
        ),
    )

    # Entropy signal (optional — canonical producer: agentic/entropy/EntropyEngine)
    entropy_result: Optional[Any] = Field(
        None,
        exclude=True,
        description=(
            "Optional entropy result from agentic.entropy.EntropyEngine. "
            "When present, provides structural coherence metrics (guna, kosha, "
            "cross-domain entropy) for governance confidence penalty computation. "
            "Duck-typed: must expose .combined_entropy, .guna_entropy, "
            ".kosha_entropy, .cross_domain_entropy, .gate attributes. "
            "Absent entropy does NOT weaken governance posture (fail-closed). "
            "Excluded from model_dump(); entropy data is captured separately "
            "via adapter output in audit events."
        ),
    )

    # Metadata
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata for traceability",
    )

    @field_validator("agency_level")
    @classmethod
    def validate_agency_level(cls, v: str) -> str:
        allowed = {"FULL", "CONFIRM", "INFORM"}
        if v not in allowed:
            raise ValueError(f"agency_level must be one of {sorted(allowed)}, got '{v}'")
        return v

    @field_validator("readiness_level")
    @classmethod
    def validate_readiness_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed = {"READY", "CONDITIONAL", "NOT_READY"}
            if v not in allowed:
                raise ValueError(f"readiness_level must be one of {sorted(allowed)}, got '{v}'")
        return v


# =============================================================================
# Response Model
# =============================================================================


class SafetyContractSummary(BaseModel):
    """Summary of SafetyContract evaluation."""
    eligible: bool
    satisfied_preconditions: List[str]
    violated_preconditions: List[str]
    blocking_reasons: List[str]
    internal_consistency: float
    goal_alignment: float
    prediction_reversal_risk: float
    identity_stability: float


class ConfidenceGateSummary(BaseModel):
    """Summary of ConfidenceGate evaluation."""
    overall_confidence: float
    quality_component: float
    coherence_component: float
    stability_component: float
    action_component: float
    execution_mode: APIExecutionMode
    escalation_level: APIEscalationLevel
    requires_human: bool
    revision_budget: int
    reasoning: List[str]


class AuditEvent(BaseModel):
    """Structured audit event for the authorization decision."""
    decision_id: str
    timestamp: str
    actor_id: str
    action_type: str
    tool_name: Optional[str]
    decision: APIGovernanceDecision
    risk_level: APIToolRiskLevel
    eligible: bool
    confidence: float
    execution_mode: APIExecutionMode
    escalation_level: APIEscalationLevel
    blocked_reasons: List[str]
    request_snapshot: Dict[str, Any]

    # Shadow AI Control Layer fields (populated when shadow policy runs)
    shadow_assessment: Optional[Dict[str, Any]] = Field(
        None, description="Full shadow AI assessment (serialized ShadowAssessment)",
    )

    # Phase S1: Sovereign telemetry snapshot at decision time
    sovereign_telemetry: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Sovereign state snapshot at decision time: nexus routing, "
            "dominant ontological layer, cognitive mode. "
            "Populated when JEPA assessment includes ontology signals."
        ),
    )

    # Phase S2: Sovereign health and insight gate signals
    sovereign_health: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Sovereign health state at decision time: alert state, "
            "entropy classification, inertial brake status."
        ),
    )
    sovereign_insight: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Sovereign insight gate evaluation at decision time: "
            "eligibility, release status, stability/risk scores."
        ),
    )

    # Phase S3: Reasoning kernel diagnostics
    sovereign_diagnostics: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Sovereign reasoning-kernel diagnostics at decision time: "
            "mauna/silence state, active intervention, logic template, "
            "OPB lock state, vritti rejection, entropy delta."
        ),
    )

    # Phase S4: Guna anomaly signals + advanced sovereign metadata
    sovereign_guna_anomalies: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Guna anomaly state at decision time: collapse, oscillation, "
            "stagnation detection, dominant guna, statistics."
        ),
    )
    sovereign_bhava_transition: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Bhava transition audit at decision time: from/to bhava, "
            "transition probability/penalty, unusual flag."
        ),
    )
    sovereign_governor_telemetry: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "VrittiGovernor telemetry summary at decision time: "
            "s_drift, coupling, tamas_ratio, brake_reason."
        ),
    )

    # Phase C2: Core pipeline coherence state signals
    core_coherence: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Core pipeline CoherenceState signal view at decision time: "
            "coherence, drift, UCF, continuity, identity, predictive signals. "
            "Bridged via coherence_state_adapter (Phase C2)."
        ),
    )

    # Phase C3: UCF consciousness stability signal
    ucf_signal: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Unified Consciousness Formula signal at decision time: "
            "ucf_score, stability_band, contributing_factors, confidence. "
            "Bridged via ucf_adapter (Phase C3)."
        ),
    )

    # Phase C3: Generation gate state at decision time
    generation_gate: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Generation gate state at decision time: gate_status, "
            "generation_mode, gate_affected_decision. "
            "Integrated via generation gate check (Phase C3)."
        ),
    )

    # Phase C4: Predictive signals (P35 drift + P36 identity + P37 continuity)
    predictive_signals: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Predictive pipeline signals at decision time: P35 persona drift "
            "(predicted_drift_score, drift_risk_band, trend), P36 identity "
            "resonance (resonance_index, stability_band), P37 adaptive "
            "continuity (continuity_score, mode, pressure, oscillation). "
            "Bridged via predictive_signals_adapter (Phase C4)."
        ),
    )

    # Phase O4: Ontology balance signal
    ontology_balance: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Ontology 10D mirror-pair balance signal at decision time: "
            "balance_score, confidence_penalty, escalation_bias, "
            "dominant_state, propagation_needed. "
            "Bridged via ontology_adapter (Phase O4)."
        ),
    )

    # Phase S2-safety: Plasticity gate signal
    plasticity_gate: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Plasticity gate signal at decision time: sigmoid "
            "permission-to-act value, resistance/misalignment inputs, "
            "confidence_penalty, escalation_bias. "
            "Bridged via plasticity_adapter (Phase S2)."
        ),
    )

    # Phase S3-safety: Readiness checker signal
    readiness_check: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Readiness checker signal at decision time: multi-criterion "
            "readiness status (READY/NOT_READY/DEGRADED), plasticity, "
            "stability, pending escalations, confidence_penalty, "
            "escalation_bias. Bridged via readiness_adapter (Phase S3)."
        ),
    )

    # Phase S4-safety: Agent policy engine signal
    agent_policy: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Agent policy engine evaluation at decision time: "
            "allowed/denied status, violations, agent_id, action_type. "
            "Bridged via policy_engine_adapter (Phase S4)."
        ),
    )

    # Phase S5-safety: Rollback monitor pre-action snapshot
    rollback_watch: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Rollback monitor pre-action signal snapshot at decision time: "
            "watch_started, pre_action_signals, watch_id. "
            "Lifecycle-preparatory: post-action check() requires external "
            "caller. Bridged via rollback_adapter (Phase S5)."
        ),
    )

    # Phase C4: Counterfactual sandbox (replay/simulation only, not live).
    # NOTE: This field is INTENTIONALLY never populated by
    # GovernanceService.authorize(). It exists for downstream replay,
    # approval-workflow what-if analysis, and audit simulation tools
    # that attach counterfactual results to audit events after the fact.
    # The counterfactual bridge (signal_adapters/counterfactual_bridge.py)
    # is NOT imported or called on the live authorize path.
    counterfactual: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Counterfactual sandbox simulation results (replay/simulation "
            "only — NOT populated by GovernanceService.authorize()). "
            "Reserved for approval workflows and audit replay tools that "
            "attach what-if analysis to audit events post-hoc (Phase C4)."
        ),
    )


class AuthorizationResponse(BaseModel):
    """
    Governance authorization decision.

    Returned by POST /authorize. Contains the full decision with
    rationale, risk assessment, and audit metadata.

    P52/P53 COMPATIBILITY:
        - governance_decision maps to GovernanceDecision (ALLOW/DENY/DEFER)
        - rationale_codes maps to GovernanceBindingEnvelope.rationale_codes
        - audit_reference maps to GovernanceBindingEnvelope.audit_reference
    """

    # Top-level decision (P52/P53 compatible)
    governance_decision: APIGovernanceDecision = Field(
        ..., description="Top-level decision: ALLOW, DENY, or DEFER",
    )

    # Detailed eligibility
    eligible: bool = Field(
        ..., description="Whether the action passed all safety preconditions",
    )

    # Execution posture
    execution_mode: APIExecutionMode = Field(
        ..., description="Execution permission mode from confidence gating",
    )
    escalation_level: APIEscalationLevel = Field(
        ..., description="Human escalation level",
    )
    requires_human_approval: bool = Field(
        ..., description="Whether human confirmation is required before proceeding",
    )

    # Risk assessment
    risk_level: APIToolRiskLevel = Field(
        ..., description="Classified risk level of the proposed action",
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Unified confidence score [0.0, 1.0]",
    )

    # Scope
    allowed_actions: List[str] = Field(
        default_factory=list,
        description="Action types permitted at this confidence level",
    )
    blocked_reasons: List[str] = Field(
        default_factory=list,
        description="Reasons for denial or restriction",
    )

    # P52/P53 compatible fields
    rationale_codes: List[str] = Field(
        default_factory=list,
        description="Machine-readable rationale codes (P53 compatible)",
    )
    audit_reference: Optional[str] = Field(
        None, description="Audit trail reference ID (P54 compatible)",
    )

    # Human-readable rationale
    rationale: str = Field(
        ..., description="Human-readable explanation of the decision",
    )

    # Detailed breakdowns
    safety_contract: SafetyContractSummary
    confidence_gate: ConfidenceGateSummary

    # Audit
    audit_event: AuditEvent

    # Shadow AI Control Layer
    shadow_assessment: Optional[Dict[str, Any]] = Field(
        None,
        description="Shadow AI assessment (serialized ShadowAssessment). "
                    "Present when shadow policy evaluation ran.",
    )

    # Approval Workflow Layer
    approval_required: bool = Field(
        False,
        description="Whether a durable approval request was created for this decision. "
                    "True only when an ApprovalRequest was successfully persisted. "
                    "When True, approval_id will be non-None.",
    )
    approval_id: Optional[str] = Field(
        None,
        description="ID of the created ApprovalRequest, if approval_required is True.",
    )
    approval_summary: Optional[Dict[str, Any]] = Field(
        None,
        description="Summary of the approval request (status, level, expiry).",
    )

    # Control flags
    dry_run: bool = Field(
        False, description="Whether this was a dry-run evaluation",
    )

    # Metadata
    service_version: str = Field(
        ..., description="Governance service version",
    )
    decision_timestamp: str = Field(
        ..., description="ISO timestamp of the decision",
    )
