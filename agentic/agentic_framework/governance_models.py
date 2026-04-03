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
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


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
        description="Whether this decision requires an approval workflow. "
                    "True when governance_decision is DEFER and requires_human_approval.",
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
