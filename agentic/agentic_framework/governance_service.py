"""
Governance Service — Decision-Only Authorization Layer

Pure Python service that evaluates authorization requests using the existing
agentic framework governance stack. No HTTP, no FastAPI — just decision logic.

ARCHITECTURE:
    AuthorizationRequest (external)
        ↓
    GovernanceService.authorize()
        ├─ ToolRiskClassifier.classify()      → risk level
        ├─ Forbidden capability check          → hard block
        ├─ ConfidenceGate.evaluate()           → execution mode, escalation
        ├─ SafetyContractEvaluator.evaluate()  → eligible / denied
        ├─ Merge decisions                     → governance decision
        ├─ Build audit event                   → structured audit
        └─ Return AuthorizationResponse

FAIL-CLOSED DEFAULT:
    - Unknown tools → classified as WRITE (not READ_ONLY)
    - Missing signals → conservative defaults (0.5 or worse)
    - Malformed input → DENY
    - Any internal error → DENY with error reason

WHAT THIS MODULE DOES NOT DO:
    - Execute tools or actions
    - Call LLMs
    - Modify agent state
    - Persist data to durable audit store (GovernanceAuditStore)
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from agentic.agentic_framework.confidence_gate import (
    ConfidenceGate,
    ConfidenceGateDecision,
    ConfidenceSignals,
    EscalationLevel,
    ExecutionMode,
    create_confidence_gate,
    create_strict_confidence_gate,
)
from agentic.agentic_framework.mcp_gateway import (
    ToolRiskClassifier,
    ToolRiskLevel,
)
from agentic.agentic_framework.governance_models import (
    APIEscalationLevel,
    APIExecutionMode,
    APIGovernanceDecision,
    APIToolRiskLevel,
    AuditEvent,
    AuthorizationRequest,
    AuthorizationResponse,
    ConfidenceGateSummary,
    SafetyContractSummary,
)
from agentic.ledger.governance_audit_store import (
    GovernanceAuditStore,
    GovernanceAuditError,
    event_from_governance_decision,
)
from agentic.agentic_framework.jepa_governance import (
    JEPAGovernanceAssessment,
    GovernanceRegime,
    jepa_governance_check,
    safe_jepa_governance_check,
    apply_jepa_override,
    approximate_layer_weights,
    approximate_vritti,
)
from agentic.agentic_framework.domain_policy import (
    DomainActionMode,
    DomainPolicyResult,
    DomainRegistry,
    resolve_domain_policy,
    fail_closed_result,
)

import logging as _logging

_logger = _logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

SERVICE_VERSION = "1.0.0"

# Forbidden capabilities (mirrors SafetyContract + ToolRiskClassifier)
FORBIDDEN_CAPABILITIES = frozenset({
    "destructive_file_operations",
    "network_attacks",
    "credential_access",
    "privilege_escalation",
    "system_modification",
    "data_exfiltration",
    "malware_execution",
})


# =============================================================================
# Internal Helpers
# =============================================================================


def _map_risk_level(internal: ToolRiskLevel) -> APIToolRiskLevel:
    """Map internal ToolRiskLevel to API enum."""
    return APIToolRiskLevel(internal.value)


def _map_execution_mode(internal: ExecutionMode) -> APIExecutionMode:
    """Map internal ExecutionMode to API enum."""
    return APIExecutionMode(internal.value)


def _map_escalation_level(internal: EscalationLevel) -> APIEscalationLevel:
    """Map internal EscalationLevel to API enum."""
    return APIEscalationLevel(internal.value)


def _generate_decision_id(request: AuthorizationRequest) -> str:
    """Generate deterministic decision ID from request content."""
    content = f"{request.actor_id}:{request.action_type}:{request.tool_name}:{time.time_ns()}"
    return hashlib.sha256(content.encode()).hexdigest()[:24]


def _check_forbidden_capabilities(capabilities: List[str]) -> Optional[str]:
    """Check if any capability is forbidden. Returns first match or None."""
    for cap in capabilities:
        if cap in FORBIDDEN_CAPABILITIES:
            return cap
    return None


def _build_confidence_signals(
    request: AuthorizationRequest,
    risk_level: ToolRiskLevel,
) -> ConfidenceSignals:
    """Build ConfidenceSignals from external request + risk classification."""
    complexity_map = {
        ToolRiskLevel.READ_ONLY: 0.1,
        ToolRiskLevel.WRITE: 0.4,
        ToolRiskLevel.EXECUTE: 0.7,
        ToolRiskLevel.DESTRUCTIVE: 0.9,
        ToolRiskLevel.PRIVILEGED: 0.95,
    }
    reversibility_map = {
        ToolRiskLevel.READ_ONLY: 1.0,
        ToolRiskLevel.WRITE: 0.7,
        ToolRiskLevel.EXECUTE: 0.5,
        ToolRiskLevel.DESTRUCTIVE: 0.0,
        ToolRiskLevel.PRIVILEGED: 0.2,
    }

    return ConfidenceSignals(
        quality_score=request.quality_score,
        coherence_score=request.coherence_score,
        correctness_score=request.quality_score,
        completeness_score=0.5,
        relevance_score=0.5,
        internal_consistency=request.internal_consistency,
        goal_alignment=request.goal_alignment,
        prediction_reversal_risk=0.5,
        volatility_index=0.5,
        trajectory_confidence=request.trajectory_confidence,
        session_stability=0.5,
        action_complexity=complexity_map.get(risk_level, 0.5),
        action_reversibility=reversibility_map.get(risk_level, 0.5),
    )


def _build_safety_contract_summary(
    request: AuthorizationRequest,
    risk_level: ToolRiskLevel,
    forbidden_cap: Optional[str],
    gate_decision: ConfidenceGateDecision,
) -> Tuple[SafetyContractSummary, bool]:
    """
    Evaluate safety contract preconditions.

    Replicates SafetyContractEvaluator logic without requiring
    CoherenceState/GoalState objects. Uses request signals directly.

    Returns (summary, eligible).
    """
    satisfied: List[str] = []
    violated: List[str] = []
    blocking_reasons: List[str] = []

    # Thresholds (match SafetyContractEvaluator defaults)
    consistency_threshold = 0.60
    alignment_threshold = 0.60
    reversal_risk_threshold = 0.40
    stability_threshold = 0.60

    # Precondition 1: Internal consistency
    if request.internal_consistency >= consistency_threshold:
        satisfied.append("precondition_1_internal_consistency")
    else:
        violated.append("precondition_1_internal_consistency")
        blocking_reasons.append(
            f"internal_consistency {request.internal_consistency:.2f} < {consistency_threshold}"
        )

    # Precondition 2: Goal alignment
    if request.goal_alignment >= alignment_threshold:
        satisfied.append("precondition_2_goal_alignment")
    else:
        violated.append("precondition_2_goal_alignment")
        blocking_reasons.append(
            f"goal_alignment {request.goal_alignment:.2f} < {alignment_threshold}"
        )

    # Precondition 3: Prediction reversal risk (use confidence stability proxy)
    reversal_risk = 1.0 - gate_decision.confidence.stability_component
    if reversal_risk <= reversal_risk_threshold:
        satisfied.append("precondition_3_reversal_risk")
    else:
        violated.append("precondition_3_reversal_risk")
        blocking_reasons.append(
            f"reversal_risk {reversal_risk:.2f} > {reversal_risk_threshold}"
        )

    # Precondition 4: Identity stability (use trajectory confidence proxy)
    identity_stability = request.trajectory_confidence
    if identity_stability >= stability_threshold:
        satisfied.append("precondition_4_identity_stability")
    else:
        violated.append("precondition_4_identity_stability")
        blocking_reasons.append(
            f"identity_stability {identity_stability:.2f} < {stability_threshold}"
        )

    # Precondition 5: No blocking factors
    if not request.blocking_factors:
        satisfied.append("precondition_5_no_blocking_factors")
    else:
        violated.append("precondition_5_no_blocking_factors")
        blocking_reasons.append(
            f"blocking_factors: {', '.join(request.blocking_factors)}"
        )

    # Precondition 6: Agency level permits action
    if request.agency_level in ("FULL", "CONFIRM"):
        satisfied.append("precondition_6_agency_permits")
    else:
        violated.append("precondition_6_agency_permits")
        blocking_reasons.append(
            f"agency_level={request.agency_level} does not permit actions"
        )

    # Forbidden capability check (hard block)
    if forbidden_cap is not None:
        violated.append("precondition_7_no_forbidden_capabilities")
        blocking_reasons.append(f"forbidden_capability: {forbidden_cap}")

    eligible = len(violated) == 0

    summary = SafetyContractSummary(
        eligible=eligible,
        satisfied_preconditions=sorted(satisfied),
        violated_preconditions=sorted(violated),
        blocking_reasons=sorted(blocking_reasons),
        internal_consistency=request.internal_consistency,
        goal_alignment=request.goal_alignment,
        prediction_reversal_risk=reversal_risk,
        identity_stability=identity_stability,
    )

    return summary, eligible


def _compute_governance_decision(
    eligible: bool,
    gate_decision: ConfidenceGateDecision,
    forbidden_cap: Optional[str],
) -> APIGovernanceDecision:
    """
    Compute top-level governance decision from safety + confidence.

    Mapping:
        - Forbidden capability → DENY
        - Not eligible → DENY
        - Eligible + BLOCKED → DENY
        - Eligible + CONFIRM_REQUIRED or HALT escalation → DEFER
        - Eligible + can_execute → ALLOW
    """
    if forbidden_cap is not None:
        return APIGovernanceDecision.DENY

    if not eligible:
        return APIGovernanceDecision.DENY

    if not gate_decision.execution.can_execute:
        return APIGovernanceDecision.DENY

    if gate_decision.escalation.requires_human:
        return APIGovernanceDecision.DEFER

    return APIGovernanceDecision.ALLOW


def _approximate_layer_weights(
    request: AuthorizationRequest,
    gate_decision: ConfidenceGateDecision,
) -> Dict[str, float]:
    """Approximate OLM layer weights from available request signals.

    Delegates to the shared canonical implementation in jepa_governance
    so that GovernanceService and MCP produce identical composites.
    """
    return approximate_layer_weights(
        quality=getattr(request, "quality_score", 0.5),
        coherence=getattr(request, "coherence_score", 0.5),
        internal_consistency=getattr(request, "internal_consistency", 0.5),
        goal_alignment=getattr(request, "goal_alignment", 0.5),
        trajectory_confidence=getattr(request, "trajectory_confidence", 0.5),
        overall_confidence=gate_decision.confidence.overall,
    )


def _approximate_vritti(
    request: AuthorizationRequest,
    gate_decision: ConfidenceGateDecision,
) -> Dict[str, float]:
    """Approximate vritti distribution from available request signals.

    Delegates to the shared canonical implementation in jepa_governance.
    """
    return approximate_vritti(
        quality=getattr(request, "quality_score", 0.5),
        coherence=getattr(request, "coherence_score", 0.5),
        overall_confidence=gate_decision.confidence.overall,
    )



def _build_rationale_codes(
    safety_summary: SafetyContractSummary,
    gate_decision: ConfidenceGateDecision,
    risk_level: ToolRiskLevel,
    forbidden_cap: Optional[str],
    governance_decision: APIGovernanceDecision,
    jepa_assessment: Optional["JEPAGovernanceAssessment"] = None,
    jepa_overrode: bool = False,
) -> List[str]:
    """Build machine-readable rationale codes."""
    codes: List[str] = []

    if forbidden_cap:
        codes.append(f"FORBIDDEN_CAPABILITY:{forbidden_cap}")

    for reason in safety_summary.blocking_reasons:
        codes.append(f"SAFETY:{reason}")

    if gate_decision.escalation.requires_human:
        codes.append(f"ESCALATION:{gate_decision.escalation.level.value}")

    if not gate_decision.execution.can_execute:
        codes.append(f"EXECUTION_BLOCKED:{gate_decision.execution.mode.value}")

    # JEPA rationale codes
    if jepa_assessment is not None:
        codes.append(f"JEPA_REGIME:{jepa_assessment.regime.value}")
        if jepa_overrode:
            codes.append(f"JEPA_OVERRIDE:{jepa_assessment.recommended_action}")
        for rc in jepa_assessment.reason_codes:
            codes.append(f"JEPA:{rc}")

    codes.append(f"RISK_LEVEL:{risk_level.value}")
    codes.append(f"DECISION:{governance_decision.value}")

    return codes


def _build_rationale_string(
    governance_decision: APIGovernanceDecision,
    safety_summary: SafetyContractSummary,
    gate_decision: ConfidenceGateDecision,
    risk_level: ToolRiskLevel,
    forbidden_cap: Optional[str],
    jepa_assessment: Optional["JEPAGovernanceAssessment"] = None,
    jepa_overrode: bool = False,
) -> str:
    """Build human-readable rationale string."""
    parts: List[str] = []

    if forbidden_cap:
        return f"DENIED: Action requires forbidden capability '{forbidden_cap}'."

    if not safety_summary.eligible:
        failed = ", ".join(safety_summary.violated_preconditions)
        parts.append(f"Safety contract denied: failed preconditions [{failed}].")

    if not gate_decision.execution.can_execute:
        parts.append(
            f"Confidence gate blocked execution "
            f"(confidence={gate_decision.confidence.overall:.2f}, "
            f"mode={gate_decision.execution.mode.value})."
        )

    if gate_decision.escalation.requires_human:
        parts.append(
            f"Human approval required "
            f"(escalation={gate_decision.escalation.level.value})."
        )

    # JEPA rationale
    if jepa_assessment is not None and jepa_overrode:
        parts.append(
            f"JEPA governance override: regime={jepa_assessment.regime.value}, "
            f"action={jepa_assessment.recommended_action}, "
            f"confidence_adj={jepa_assessment.confidence_adjustment:+.2f}."
        )
    elif jepa_assessment is not None and jepa_assessment.regime.value != "normal":
        parts.append(
            f"JEPA regime: {jepa_assessment.regime.value} "
            f"(no override applied)."
        )

    if governance_decision == APIGovernanceDecision.ALLOW:
        parts.append(
            f"ALLOWED: All checks passed. Risk={risk_level.value}, "
            f"confidence={gate_decision.confidence.overall:.2f}."
        )

    return " ".join(parts) if parts else f"Decision: {governance_decision.value}"


# =============================================================================
# Governance Service
# =============================================================================


class GovernanceService:
    """
    Pure decision service for external authorization.

    Evaluates requests using the existing agentic framework governance stack:
    - ToolRiskClassifier for risk classification
    - ConfidenceGate for confidence-based execution control
    - SafetyContract-equivalent precondition checks
    - Forbidden capability blocking

    Does NOT execute actions. Does NOT call LLMs. Does NOT modify state.

    Usage:
        service = GovernanceService()
        response = service.authorize(request)
        if response.governance_decision == "ALLOW":
            # External agent may proceed
    """

    def __init__(
        self,
        confidence_gate: Optional[ConfidenceGate] = None,
        risk_classifier: Optional[ToolRiskClassifier] = None,
        strict: bool = False,
        audit_store: Optional[GovernanceAuditStore] = None,
        domain_registry: Optional[DomainRegistry] = None,
        domain_id: Optional[str] = None,
    ):
        """
        Initialize governance service.

        Args:
            confidence_gate: Custom ConfidenceGate (default: standard or strict)
            risk_classifier: Custom ToolRiskClassifier (default: standard)
            strict: Use strict thresholds if no custom gate provided
            audit_store: Durable audit store for persistence (default: None,
                         in-memory only).  When provided, every audit event is
                         persisted to the store in addition to the in-memory log.
            domain_registry: Optional DomainRegistry for domain-specific policy.
                When provided with domain_id, the Domain Semantic Policy Layer
                translates JEPA assessments into domain-specific action modes.
            domain_id: Which domain profile to use from the registry.
                Ignored if domain_registry is None.
        """
        if confidence_gate is not None:
            self.gate = confidence_gate
        elif strict:
            self.gate = create_strict_confidence_gate()
        else:
            self.gate = create_confidence_gate()

        self.classifier = risk_classifier or ToolRiskClassifier()

        # In-memory audit log (cache / view — still available for callers)
        self._audit_log: List[AuditEvent] = []

        # Durable persistent audit store (source of truth when present)
        self._audit_store: Optional[GovernanceAuditStore] = audit_store

        # Domain Semantic Policy Layer
        self._domain_registry: Optional[DomainRegistry] = domain_registry
        self._domain_id: Optional[str] = domain_id

    def authorize(self, request: AuthorizationRequest) -> AuthorizationResponse:
        """
        Evaluate an authorization request and return a governance decision.

        FAIL-CLOSED: Any error during evaluation results in DENY.

        Args:
            request: External authorization request

        Returns:
            AuthorizationResponse with full decision details
        """
        now = datetime.now(timezone.utc).isoformat()
        decision_id = _generate_decision_id(request)

        try:
            return self._evaluate(request, decision_id, now)
        except Exception as e:
            # Fail-closed: any internal error → DENY
            return self._build_error_response(request, decision_id, now, str(e))

    def _evaluate(
        self,
        request: AuthorizationRequest,
        decision_id: str,
        timestamp: str,
    ) -> AuthorizationResponse:
        """Core evaluation logic."""

        # Step 1: Classify tool risk
        tool_name = request.tool_name or request.action_type
        risk_level = self.classifier.classify(tool_name)

        # Step 2: Check forbidden capabilities
        forbidden_cap = _check_forbidden_capabilities(request.capabilities)

        # Step 3: Build confidence signals and evaluate gate
        signals = _build_confidence_signals(request, risk_level)
        gate_decision = self.gate.evaluate(signals, tool_name)

        # Step 4: Evaluate safety contract preconditions
        safety_summary, eligible = _build_safety_contract_summary(
            request, risk_level, forbidden_cap, gate_decision,
        )

        # Step 5: Compute governance decision
        governance_decision = _compute_governance_decision(
            eligible, gate_decision, forbidden_cap,
        )

        # Step 5b: JEPA residual governance check
        #   Compares the JEPA composite latent state (ontology + vritti)
        #   against the runtime process state to detect drift, anomaly,
        #   or semantic shift. May override governance decision.
        #   Uses safe_jepa_governance_check — always returns an assessment,
        #   never None. JEPA failure produces UNKNOWN regime.
        baseline_decision = governance_decision
        jepa_assessment = self._run_jepa_check(
            request, risk_level, gate_decision,
        )

        # Use the shared override function from jepa_governance
        jepa_result = apply_jepa_override(
            baseline_decision=governance_decision.value,
            baseline_eligible=eligible,
            assessment=jepa_assessment,
        )
        governance_decision = APIGovernanceDecision(jepa_result["decision"])
        eligible = jepa_result["eligible"]
        jepa_overrode = jepa_result["overrode"]

        # Step 5c: Apply JEPA override fields to confidence, execution
        # mode, and escalation level. These modify the gate decision's
        # effective output — JEPA can only make things stricter.
        effective_confidence = max(
            0.0,
            gate_decision.confidence.overall + jepa_assessment.confidence_adjustment,
        )

        effective_exec_mode = gate_decision.execution.mode
        if jepa_assessment.execution_mode_override is not None:
            jepa_exec = jepa_assessment.execution_mode_override.lower()
            gate_exec = gate_decision.execution.mode.value
            # Only apply if JEPA is stricter (BLOCKED > CONFIRM > CAUTIOUS > FULL)
            _EXEC_SEVERITY = {"full": 0, "cautious": 1, "confirm": 2,
                              "confirm_required": 2, "blocked": 3}
            if _EXEC_SEVERITY.get(jepa_exec, 0) > _EXEC_SEVERITY.get(gate_exec, 0):
                effective_exec_mode = ExecutionMode(jepa_exec
                    if jepa_exec != "confirm_required" else "confirm")

        effective_esc_level = gate_decision.escalation.level
        if jepa_assessment.escalation_override is not None:
            jepa_esc = jepa_assessment.escalation_override.lower()
            gate_esc = gate_decision.escalation.level.value
            _ESC_SEVERITY = {"none": 0, "notify": 1, "confirm": 2, "halt": 3}
            if _ESC_SEVERITY.get(jepa_esc, 0) > _ESC_SEVERITY.get(gate_esc, 0):
                effective_esc_level = EscalationLevel(jepa_esc)

        effective_requires_human = (
            gate_decision.escalation.requires_human
            or effective_esc_level in (EscalationLevel.CONFIRM, EscalationLevel.HALT)
        )

        # Step 5d: Domain Semantic Policy Layer
        #   Translates the JEPA assessment into domain-specific action mode.
        #   Domain policy can only make things STRICTER, never relax.
        #   If no domain is configured, this step is a no-op.
        domain_result: Optional[DomainPolicyResult] = None
        if self._domain_registry is not None and self._domain_id is not None:
            domain_result = resolve_domain_policy(
                jepa_assessment,
                self._domain_registry,
                self._domain_id,
                tool_name=request.tool_name or "",
            )
            # Apply domain mode as stricter-only override
            if domain_result.mode == DomainActionMode.BLOCKED:
                governance_decision = APIGovernanceDecision.DENY
                eligible = False
            elif domain_result.mode in (
                DomainActionMode.CONFIRM_REQUIRED,
                DomainActionMode.SANDBOX_ONLY,
                DomainActionMode.MEMORY_WRITE_DENIED,
            ):
                if governance_decision == APIGovernanceDecision.ALLOW:
                    governance_decision = APIGovernanceDecision.DEFER
                    eligible = False
                effective_requires_human = True
            elif domain_result.mode in (
                DomainActionMode.READ_ONLY,
                DomainActionMode.DRAFT_ONLY,
            ):
                if governance_decision == APIGovernanceDecision.ALLOW:
                    governance_decision = APIGovernanceDecision.DEFER
                    eligible = False

        # Step 6: Build rationale (includes JEPA information)
        rationale_codes = _build_rationale_codes(
            safety_summary, gate_decision, risk_level, forbidden_cap,
            governance_decision, jepa_assessment, jepa_overrode,
        )
        rationale = _build_rationale_string(
            governance_decision, safety_summary, gate_decision, risk_level,
            forbidden_cap, jepa_assessment, jepa_overrode,
        )

        # Step 7: Build confidence gate summary (with JEPA adjustments)
        confidence_summary = ConfidenceGateSummary(
            overall_confidence=effective_confidence,
            quality_component=gate_decision.confidence.quality_component,
            coherence_component=gate_decision.confidence.coherence_component,
            stability_component=gate_decision.confidence.stability_component,
            action_component=gate_decision.confidence.action_component,
            execution_mode=_map_execution_mode(effective_exec_mode),
            escalation_level=_map_escalation_level(effective_esc_level),
            requires_human=effective_requires_human,
            revision_budget=gate_decision.budget.revision_budget,
            reasoning=gate_decision.reasoning,
        )

        # Step 8: Build audit event
        audit_event = AuditEvent(
            decision_id=decision_id,
            timestamp=timestamp,
            actor_id=request.actor_id,
            action_type=request.action_type,
            tool_name=request.tool_name,
            decision=governance_decision,
            risk_level=_map_risk_level(risk_level),
            eligible=eligible,
            confidence=effective_confidence,
            execution_mode=_map_execution_mode(effective_exec_mode),
            escalation_level=_map_escalation_level(effective_esc_level),
            blocked_reasons=safety_summary.blocking_reasons,
            request_snapshot={
                "actor_id": request.actor_id,
                "action_type": request.action_type,
                "tool_name": request.tool_name,
                "agency_level": request.agency_level,
                "capabilities": request.capabilities,
                "quality_score": request.quality_score,
                "coherence_score": request.coherence_score,
                "jepa_regime": jepa_assessment.regime.value,
                "jepa_reason_codes": list(jepa_assessment.reason_codes),
                "jepa_overrode_baseline": jepa_overrode,
                "jepa_baseline_decision": baseline_decision.value,
                "jepa_confidence_adjustment": jepa_assessment.confidence_adjustment,
                "jepa_recommended_action": jepa_assessment.recommended_action,
                "jepa_execution_mode_override": jepa_assessment.execution_mode_override,
                "jepa_escalation_override": jepa_assessment.escalation_override,
                "domain_policy": (
                    domain_result.to_audit_dict() if domain_result else None
                ),
            },
        )
        self._persist_audit_event(audit_event)

        # Step 9: Assemble response (uses JEPA-adjusted fields)
        return AuthorizationResponse(
            governance_decision=governance_decision,
            eligible=eligible,
            execution_mode=_map_execution_mode(effective_exec_mode),
            escalation_level=_map_escalation_level(effective_esc_level),
            requires_human_approval=effective_requires_human,
            risk_level=_map_risk_level(risk_level),
            confidence_score=effective_confidence,
            allowed_actions=gate_decision.execution.allowed_actions,
            blocked_reasons=safety_summary.blocking_reasons,
            rationale_codes=rationale_codes,
            audit_reference=decision_id,
            rationale=rationale,
            safety_contract=safety_summary,
            confidence_gate=confidence_summary,
            audit_event=audit_event,
            dry_run=request.dry_run,
            service_version=SERVICE_VERSION,
            decision_timestamp=timestamp,
        )

    def _build_error_response(
        self,
        request: AuthorizationRequest,
        decision_id: str,
        timestamp: str,
        error: str,
    ) -> AuthorizationResponse:
        """Build a DENY response for internal errors. Fail-closed."""
        safety_summary = SafetyContractSummary(
            eligible=False,
            satisfied_preconditions=[],
            violated_preconditions=["internal_error"],
            blocking_reasons=[f"Internal evaluation error: {error}"],
            internal_consistency=0.0,
            goal_alignment=0.0,
            prediction_reversal_risk=1.0,
            identity_stability=0.0,
        )
        confidence_summary = ConfidenceGateSummary(
            overall_confidence=0.0,
            quality_component=0.0,
            coherence_component=0.0,
            stability_component=0.0,
            action_component=0.0,
            execution_mode=APIExecutionMode.BLOCKED,
            escalation_level=APIEscalationLevel.HALT,
            requires_human=True,
            revision_budget=0,
            reasoning=[f"Internal error: {error}"],
        )
        audit_event = AuditEvent(
            decision_id=decision_id,
            timestamp=timestamp,
            actor_id=request.actor_id,
            action_type=request.action_type,
            tool_name=request.tool_name,
            decision=APIGovernanceDecision.DENY,
            risk_level=APIToolRiskLevel.PRIVILEGED,
            eligible=False,
            confidence=0.0,
            execution_mode=APIExecutionMode.BLOCKED,
            escalation_level=APIEscalationLevel.HALT,
            blocked_reasons=[f"Internal error: {error}"],
            request_snapshot={"actor_id": request.actor_id, "action_type": request.action_type},
        )
        self._persist_audit_event(audit_event)

        return AuthorizationResponse(
            governance_decision=APIGovernanceDecision.DENY,
            eligible=False,
            execution_mode=APIExecutionMode.BLOCKED,
            escalation_level=APIEscalationLevel.HALT,
            requires_human_approval=True,
            risk_level=APIToolRiskLevel.PRIVILEGED,
            confidence_score=0.0,
            allowed_actions=[],
            blocked_reasons=[f"Internal evaluation error: {error}"],
            rationale_codes=["INTERNAL_ERROR"],
            audit_reference=decision_id,
            rationale=f"DENIED: Internal evaluation error. Fail-closed. Error: {error}",
            safety_contract=safety_summary,
            confidence_gate=confidence_summary,
            audit_event=audit_event,
            dry_run=request.dry_run,
            service_version=SERVICE_VERSION,
            decision_timestamp=timestamp,
        )

    def _persist_audit_event(self, audit_event: AuditEvent) -> None:
        """Append to in-memory log and persist to durable store if available.

        FAIL-CLOSED: If the durable store raises GovernanceAuditError, the
        error propagates.  The in-memory append happens first so that callers
        always see the event even if persistence fails (fail-closed decisions
        are still recorded in the response object).
        """
        self._audit_log.append(audit_event)

        if self._audit_store is not None:
            canonical_event = event_from_governance_decision(
                decision_id=audit_event.decision_id,
                timestamp=audit_event.timestamp,
                actor_id=audit_event.actor_id,
                action_type=audit_event.action_type,
                tool_name=audit_event.tool_name or "",
                decision=audit_event.decision.value
                    if hasattr(audit_event.decision, "value")
                    else str(audit_event.decision),
                risk_level=audit_event.risk_level.value
                    if hasattr(audit_event.risk_level, "value")
                    else str(audit_event.risk_level),
                eligible=audit_event.eligible,
                confidence=audit_event.confidence,
                execution_mode=audit_event.execution_mode.value
                    if hasattr(audit_event.execution_mode, "value")
                    else str(audit_event.execution_mode),
                escalation_level=audit_event.escalation_level.value
                    if hasattr(audit_event.escalation_level, "value")
                    else str(audit_event.escalation_level),
                blocked_reasons=audit_event.blocked_reasons,
                request_snapshot=audit_event.request_snapshot,
            )
            try:
                self._audit_store.append(canonical_event)
            except GovernanceAuditError:
                _logger.error(
                    "GOVERNANCE AUDIT PERSISTENCE FAILURE for decision %s — "
                    "event recorded in-memory but NOT persisted durably",
                    audit_event.decision_id,
                    exc_info=True,
                )
                raise

    def _run_jepa_check(
        self,
        request: AuthorizationRequest,
        risk_level: "ToolRiskLevel",
        gate_decision: "ConfidenceGateDecision",
    ) -> JEPAGovernanceAssessment:
        """Run JEPA residual governance check. Always returns an assessment.

        Uses safe_jepa_governance_check which catches internal errors
        and returns an explicit UNKNOWN-regime assessment. Never returns
        None — JEPA failure is itself a governance condition.
        """
        layer_weights = _approximate_layer_weights(request, gate_decision)
        vritti_dist = _approximate_vritti(request, gate_decision)

        return safe_jepa_governance_check(
            layer_weights=layer_weights,
            vritti_distribution=vritti_dist,
            coherence=getattr(request, "coherence_score", 0.5),
            score=gate_decision.confidence.overall,
            action_type=request.action_type,
            tool_name=request.tool_name or "",
            risk_level=risk_level.value if hasattr(risk_level, "value") else str(risk_level),
            confidence_score=gate_decision.confidence.overall,
            agency_level=request.agency_level or "FULL",
            execution_mode=gate_decision.execution.mode.value
                if hasattr(gate_decision.execution.mode, "value")
                else str(gate_decision.execution.mode),
            escalation_level=gate_decision.escalation.level.value
                if hasattr(gate_decision.escalation.level, "value")
                else str(gate_decision.escalation.level),
            session_id=getattr(request, "session_id", ""),
            actor_id=request.actor_id,
            capabilities=request.capabilities or [],
        )

    def get_audit_log(self, limit: int = 100) -> List[AuditEvent]:
        """Get recent audit events (from in-memory cache)."""
        return self._audit_log[-limit:]

    def get_audit_count(self) -> int:
        """Get total number of audit events."""
        if self._audit_store is not None:
            return self._audit_store.count()
        return len(self._audit_log)
