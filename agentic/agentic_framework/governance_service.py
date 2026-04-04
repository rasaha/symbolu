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
from agentic.agentic_framework.signal_adapters.vritti_adapter import (
    resolve_vritti_signal,
    VrittiResolution,
    VrittiSignalSource,
)
from agentic.agentic_framework.signal_adapters.entropy_adapter import (
    resolve_entropy_signal,
    EntropyResolution,
)
from agentic.agentic_framework.signal_adapters.insight_adapter import (
    resolve_insight_signal,
    InsightResolution,
)
from agentic.agentic_framework.signal_adapters.sovereign_health_adapter import (
    resolve_sovereign_health,
    SovereignHealthResolution,
)
from agentic.agentic_framework.sovereign_bridge import (
    SovereignDiagnosticContext,
    diagnostics_from_projection,
    GunaAnomalyContext,
    guna_anomalies_from_projection,
    bhava_transition_from_diagnostics,
    governor_telemetry_from_projection,
)
from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
    resolve_guna_anomaly,
    GunaAnomalyResolution,
)
from agentic.agentic_framework.signal_adapters.session_enrichment_adapter import (
    resolve_session_enrichment,
    SessionEnrichmentResolution,
)
from agentic.agentic_framework.signal_adapters.coherence_state_adapter import (
    resolve_core_coherence,
    CoreCoherenceResolution,
)
from agentic.agentic_framework.signal_adapters.ucf_adapter import (
    resolve_ucf_signal,
    UCFResolution,
)
from agentic.agentic_framework.signal_adapters.predictive_signals_adapter import (
    resolve_predictive_signals,
    PredictiveSignalsResolution,
)
from agentic.agentic_framework.signal_adapters.ontology_adapter import (
    resolve_ontology_balance,
    OntologyBalanceResolution,
)
from agentic.agentic_framework.signal_adapters.plasticity_adapter import (
    resolve_plasticity_signal,
    PlasticityResolution,
)
from agentic.agentic_framework.signal_adapters.readiness_adapter import (
    resolve_readiness_signal,
    ReadinessResolution,
)
from agentic.agentic_framework.signal_adapters.policy_engine_adapter import (
    resolve_policy_check,
    AgentPolicyResolution,
)
from agentic.safety.governance_patterns.policy_engine import (
    PolicyEngine,
    PolicyConfig,
)
from agentic.safety.governance_patterns.rollback_monitor import (
    RollbackMonitor,
)
from agentic.agentic_framework.signal_adapters.rollback_adapter import (
    resolve_rollback_snapshot,
    RollbackSnapshotResolution,
)
from agentic.core.generation_gate import (
    GenerationGate,
    GenerationMode,
    GateStatus,
    GateViolation,
)
from agentic.core.ledger_generation_attest import attest_generation_attempt
from agentic.agentic_framework.domain_policy import (
    DomainActionMode,
    DomainPolicyResult,
    DomainRegistry,
    resolve_domain_policy,
    fail_closed_result,
)
from agentic.agentic_framework.shadow_ai import (
    ShadowAssessment,
    ShadowContainmentMode,
    ShadowRegistry,
    is_memory_write_intent,
    resolve_shadow_asset_id,
    safe_resolve_shadow_policy,
    shadow_containment_to_governance,
)
from agentic.agentic_framework.policy_bundle import (
    PolicyResolution,
)
from agentic.agentic_framework.approval_workflow import (
    ApprovalContext,
    ApprovalLevel,
    ApprovalStore,
    ApprovalStoreError,
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


def _check_forbidden_capabilities(
    capabilities: List[str],
    forbidden: Optional[frozenset] = None,
) -> Optional[str]:
    """Check if any capability is forbidden. Returns first match or None."""
    effective = forbidden if forbidden is not None else FORBIDDEN_CAPABILITIES
    for cap in capabilities:
        if cap in effective:
            return cap
    return None


def _build_confidence_signals(
    request: AuthorizationRequest,
    risk_level: ToolRiskLevel,
    policy_resolution: Optional[PolicyResolution] = None,
    session_enrichment: Optional[SessionEnrichmentResolution] = None,
) -> ConfidenceSignals:
    """Build ConfidenceSignals from external request + risk classification."""
    if policy_resolution is not None:
        risk_policy = policy_resolution.effective_policy.risk
        # Map ToolRiskLevel enum names to policy risk keys
        _level_to_key = {
            ToolRiskLevel.READ_ONLY: "read_only",
            ToolRiskLevel.WRITE: "write",
            ToolRiskLevel.EXECUTE: "execute",
            ToolRiskLevel.DESTRUCTIVE: "destructive",
            ToolRiskLevel.PRIVILEGED: "privileged",
        }
        complexity_map = {
            lvl: risk_policy.complexity_map.get(key, 0.5)
            for lvl, key in _level_to_key.items()
        }
        reversibility_map = {
            lvl: risk_policy.reversibility_map.get(key, 0.5)
            for lvl, key in _level_to_key.items()
        }
    else:
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

    # Phase 3: Compute session enrichment fields
    identity_stability = 0.5
    motivation_stability = 0.5
    temporal_stability = 0.5
    enrichment_adj = 0.0
    if session_enrichment is not None:
        # Identity: unstable → lower stability score
        if session_enrichment.identity_unstable:
            identity_stability = max(0.0, 1.0 - (session_enrichment.identity_confidence or 0.5))
        elif session_enrichment.identity_type is not None:
            identity_stability = min(1.0, 0.5 + (session_enrichment.identity_confidence or 0.0) * 0.5)
        # Motivation: risk-relevant → lower stability score
        if session_enrichment.motivation_risk_relevant:
            motivation_stability = max(0.0, 1.0 - (session_enrichment.motivation_confidence or 0.5))
        elif session_enrichment.motivation_type is not None:
            motivation_stability = min(1.0, 0.5 + (session_enrichment.motivation_confidence or 0.0) * 0.5)
        # Temporal: tense → lower stability score
        if session_enrichment.temporal_tense:
            ti = session_enrichment.temporal_tension_index
            temporal_stability = max(0.0, 1.0 - (ti if ti is not None else 0.5))
        elif session_enrichment.temporal_state is not None:
            temporal_stability = 0.7  # non-tense known state
        enrichment_adj = session_enrichment.confidence_adjustment

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
        identity_stability=identity_stability,
        motivation_stability=motivation_stability,
        temporal_stability=temporal_stability,
        session_enrichment_adjustment=enrichment_adj,
    )


def _build_safety_contract_summary(
    request: AuthorizationRequest,
    risk_level: ToolRiskLevel,
    forbidden_cap: Optional[str],
    gate_decision: ConfidenceGateDecision,
    policy_resolution: Optional[PolicyResolution] = None,
) -> Tuple[SafetyContractSummary, bool]:
    """
    Evaluate safety contract preconditions.

    Replicates SafetyContractEvaluator logic without requiring
    CoherenceState/GoalState objects. Uses request signals directly.

    When policy_resolution is provided, thresholds are sourced from the
    resolved SafetyPolicy section. Otherwise uses hardcoded defaults.

    Returns (summary, eligible).
    """
    satisfied: List[str] = []
    violated: List[str] = []
    blocking_reasons: List[str] = []

    # Thresholds — from resolved policy or hardcoded defaults
    if policy_resolution is not None:
        sp = policy_resolution.effective_policy.safety
        consistency_threshold = sp.internal_consistency_threshold
        alignment_threshold = sp.goal_alignment_threshold
        reversal_risk_threshold = sp.reversal_risk_threshold
        stability_threshold = sp.identity_stability_threshold
    else:
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


def _resolve_vritti(
    request: AuthorizationRequest,
    gate_decision: ConfidenceGateDecision,
    vritti_result: Any = None,
) -> VrittiResolution:
    """Resolve vritti signal: prefer real chitta_vritti, fall back to approx.

    Phase 1: Uses the vritti signal adapter to prefer real ChittaVrittiResult
    when available on the request, otherwise falls back to the canonical
    approximate_vritti() heuristic.

    Args:
        request: Authorization request (may carry .vritti_result).
        gate_decision: Confidence gate output (provides overall confidence).
        vritti_result: Optional explicit ChittaVrittiResult override.

    Returns:
        VrittiResolution with distribution, provenance, and degradation flag.
    """
    cv_result = vritti_result or getattr(request, "vritti_result", None)
    return resolve_vritti_signal(
        vritti_result=cv_result,
        quality=getattr(request, "quality_score", 0.5),
        coherence=getattr(request, "coherence_score", 0.5),
        overall_confidence=gate_decision.confidence.overall,
    )


def _resolve_entropy(
    request: AuthorizationRequest,
    entropy_result: object = None,
) -> EntropyResolution:
    """Resolve entropy signal for governance use.

    Phase 1: Wires entropy into the governance decision context.
    If no entropy data is available, returns a non-influential placeholder.

    Args:
        request: Authorization request (may carry .entropy_result or
            .combined_entropy).
        entropy_result: Optional explicit EntropyResult override.

    Returns:
        EntropyResolution with metrics and bounded confidence penalty.
    """
    ent_result = entropy_result or getattr(request, "entropy_result", None)
    combined = getattr(request, "combined_entropy", None)
    return resolve_entropy_signal(
        entropy_result=ent_result,
        combined_entropy=combined,
    )


def _resolve_session_enrichment(
    request: AuthorizationRequest,
) -> SessionEnrichmentResolution:
    """Resolve session enrichment signals for governance use.

    Phase 3: Brings identity, motivation, and temporal signals into
    the governance decision context as bounded confidence adjustments.

    Signals are extracted from request.metadata with well-known keys.
    Missing signals contribute zero penalty (fail-closed).

    BRIDGE STATUS: The mechanical pipeline produces identity_signature,
    motivation_profile, and temporal data on ctx, but no pipeline →
    AuthorizationRequest bridge exists yet. These metadata keys are
    currently only populated if an external caller explicitly provides
    them. See AGENTIC_ARCHITECTURE.md §Pipeline ↔ Governance for details.

    Args:
        request: Authorization request (may carry session signals in .metadata).

    Returns:
        SessionEnrichmentResolution with all resolved signals.
    """
    metadata = getattr(request, "metadata", None) or {}
    return resolve_session_enrichment(
        identity_signature=metadata.get("identity_signature"),
        identity_resonance_state=metadata.get("identity_resonance_state"),
        motivation_profile=metadata.get("motivation_profile"),
        temporal_summary=metadata.get("temporal_summary"),
        coherence_state=metadata.get("coherence_state"),
    )


def _build_sovereign_telemetry(
    jepa_assessment: "JEPAGovernanceAssessment",
    vritti_resolution: Any,
) -> Optional[Dict[str, Any]]:
    """Build a sovereign telemetry snapshot from JEPA/Vritti signals.

    Phase S1: Extracts sovereign-relevant metadata from JEPA assessment
    and formats it as a StateSnapshot-compatible dict. This runs entirely
    in pure Python — no tensor or PyTorch dependency.

    Returns None if the JEPA assessment lacks ontology signals.
    """
    try:
        from agentic.sovereign.telemetry import StateSnapshot
        from agentic.sovereign_constants import (
            ONTOLOGY_TO_NEXUS,
            NEXUS_MODE_DESCRIPTIONS,
        )

        ontology = jepa_assessment.jepa_composite.ontology
        vritti = jepa_assessment.jepa_composite.vritti
        primary_layer = ontology.primary_layer
        nexus_pos = ONTOLOGY_TO_NEXUS.get(primary_layer, 6)

        snapshot = StateSnapshot.from_runtime_signals(
            authority=jepa_assessment.jepa_composite.integrated_confidence,
            dominant_bhava=primary_layer,
            bhava_confidence=ontology.confidence,
            vritti=vritti.primary_vritti,
            nexus_position=nexus_pos,
            nexus_mode=NEXUS_MODE_DESCRIPTIONS.get(nexus_pos, "unknown"),
        )
        return snapshot.to_audit_dict()
    except Exception:
        # Fail-open: if telemetry construction fails, governance continues.
        return None


def _resolve_sovereign_health_signal(
    jepa_assessment: "JEPAGovernanceAssessment",
    entropy_resolution: EntropyResolution,
) -> SovereignHealthResolution:
    """Resolve sovereign health signals from JEPA and entropy data.

    Phase S2: Extracts health context from existing governance signals.
    Returns a safe fallback if signals are insufficient.
    """
    try:
        entropy_val = entropy_resolution.combined_entropy
        gc = jepa_assessment.jepa_composite.ontology.confidence
        return resolve_sovereign_health(
            entropy=entropy_val,
            guna_coherence=gc,
        )
    except Exception:
        return resolve_sovereign_health()


def _resolve_diagnostic_context(
    jepa_assessment: "JEPAGovernanceAssessment",
) -> SovereignDiagnosticContext:
    """Resolve sovereign reasoning diagnostics from JEPA assessment.

    Phase S3: Extracts diagnostic context from JEPA composite metadata.
    Returns a safe fallback if diagnostics are unavailable.
    """
    try:
        composite = jepa_assessment.jepa_composite
        # JEPA composite may carry projection metadata with diagnostics
        metadata = getattr(composite, "projection_metadata", None)
        if metadata is not None:
            meta_dict = metadata.to_dict() if hasattr(metadata, "to_dict") else metadata
            return diagnostics_from_projection(projection_metadata=meta_dict)
        return SovereignDiagnosticContext()
    except Exception:
        return SovereignDiagnosticContext()


def _resolve_guna_anomaly_signal(
    jepa_assessment: "JEPAGovernanceAssessment",
) -> GunaAnomalyResolution:
    """Resolve Guna anomaly signals from JEPA assessment.

    Phase S4: Extracts Guna anomaly data from JEPA composite metadata.
    Returns safe fallback if data unavailable.
    """
    try:
        composite = jepa_assessment.jepa_composite
        metadata = getattr(composite, "projection_metadata", None)
        if metadata is not None:
            meta_dict = metadata.to_dict() if hasattr(metadata, "to_dict") else metadata
            guna_ctx = guna_anomalies_from_projection(projection_metadata=meta_dict)
            if guna_ctx.available:
                return resolve_guna_anomaly(guna_ctx.to_audit_dict())
        return GunaAnomalyResolution()
    except Exception:
        return GunaAnomalyResolution()


def _resolve_core_coherence_state(
    request: Any,
) -> CoreCoherenceResolution:
    """Resolve core pipeline CoherenceState from request metadata.

    Phase C2: Extracts pipeline-level coherence, drift, UCF, continuity,
    and identity signals from the core CoherenceState object passed via
    request.metadata["core_coherence_state"]. Returns a safe fallback
    if the signal is absent or malformed.
    """
    try:
        metadata = getattr(request, "metadata", None) or {}
        core_state = metadata.get("core_coherence_state")
        return resolve_core_coherence(core_coherence_state=core_state)
    except Exception:
        return resolve_core_coherence()


def _resolve_ucf_signal(
    request: Any,
    core_coherence_resolution: CoreCoherenceResolution,
) -> UCFResolution:
    """Resolve UCF consciousness stability signal for governance.

    Phase C3: Tries pre-computed UCF state from metadata first,
    then falls back to computing UCF from C2 coherence adapter signals.
    """
    try:
        metadata = getattr(request, "metadata", None) or {}
        ucf_state = metadata.get("ucf_state")

        # If no pre-computed state, try computing from C2 signals
        if ucf_state is None and core_coherence_resolution.available:
            return resolve_ucf_signal(
                coherence_v3_quality=core_coherence_resolution.coherence_v3_quality,
                drift_fusion_index=core_coherence_resolution.drift_fusion_index,
                entropy_volatility=core_coherence_resolution.temporal_entropy_vol,
            )
        return resolve_ucf_signal(ucf_state=ucf_state)
    except Exception:
        return resolve_ucf_signal()


# Generative action patterns for generation gate classification.
_GENERATIVE_ACTION_PATTERNS = frozenset({
    "generate", "create_text", "write_content", "synthesis",
    "compose", "draft", "render", "produce_output",
    "llm_generate", "text_generation",
})

_GENERATIVE_TOOL_PATTERNS = frozenset({
    "generate", "synthesis", "compose", "draft", "render",
    "create_content", "write_text", "produce",
})


def _is_generative_action(request: Any) -> bool:
    """Determine if the request involves generative output.

    Uses action_type and tool_name pattern matching.
    Conservative: only matches explicitly generative patterns.
    """
    action = (getattr(request, "action_type", None) or "").lower()
    tool = (getattr(request, "tool_name", None) or "").lower()

    for pattern in _GENERATIVE_ACTION_PATTERNS:
        if pattern in action:
            return True
    for pattern in _GENERATIVE_TOOL_PATTERNS:
        if pattern in tool:
            return True

    # Check explicit metadata flag if provided
    metadata = getattr(request, "metadata", None) or {}
    if metadata.get("is_generative"):
        return True

    return False


def _check_generation_gate(
    request: Any,
) -> Dict[str, Any]:
    """Check generation gate status for governance.

    Phase C3: Queries the GenerationGate singleton safely.
    Returns a dict with gate state and whether it affected the decision.

    Fail-closed: If the gate is UNSEALED or SEALED_DISABLED and the
    action is generative, this signals that the action should be blocked.
    Non-generative actions are never affected.
    """
    is_gen = _is_generative_action(request)
    try:
        status = GenerationGate.gate_status()
    except Exception:
        status = GateStatus.UNSEALED

    status_str = status.value if hasattr(status, "value") else str(status)

    try:
        mode_str = GenerationGate.mode().value
    except (GateViolation, Exception):
        mode_str = "UNSEALED"

    # Determine if gate blocks this action
    gate_blocks = False
    block_reason = None
    if is_gen:
        if status == GateStatus.UNSEALED:
            gate_blocks = True
            block_reason = "generation_gate_unsealed"
        elif status == GateStatus.SEALED_DISABLED:
            gate_blocks = True
            block_reason = "generation_disabled"

    # Create attestation for generative actions
    attestation = None
    if is_gen:
        try:
            attestation = dict(attest_generation_attempt(
                render_attempted=not gate_blocks,
                render_outcome="blocked_by_governance" if gate_blocks else "permitted",
            ))
        except Exception:
            pass

    return {
        "is_generative": is_gen,
        "gate_status": status_str,
        "generation_mode": mode_str,
        "gate_blocks": gate_blocks,
        "block_reason": block_reason,
        "attestation": attestation,
    }


def _resolve_predictive_signals(
    request: Any,
) -> PredictiveSignalsResolution:
    """Resolve P35+P36+P37 predictive signals from request metadata.

    Phase C4: Extracts pre-computed drift report (P35), identity state (P36),
    and continuity report (P37) from request.metadata. Returns a safe
    fallback if signals are absent or malformed.
    """
    try:
        metadata = getattr(request, "metadata", None) or {}
        drift_report = metadata.get("predictive_drift_report")
        identity_state = metadata.get("identity_resonance_state_p36")
        continuity_report = metadata.get("continuity_report")
        return resolve_predictive_signals(
            drift_report=drift_report,
            identity_state=identity_state,
            continuity_report=continuity_report,
        )
    except Exception:
        return resolve_predictive_signals()


def _resolve_s4_audit_metadata(
    jepa_assessment: "JEPAGovernanceAssessment",
    diagnostic_context: SovereignDiagnosticContext,
    previous_bhava: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Resolve Phase S4 audit-only metadata.

    Returns:
        (bhava_transition_dict, governor_telemetry_dict) — both may be None.
    """
    # Bhava transition audit (uses previous + current dominant_bhava)
    current_bhava = diagnostic_context.dominant_bhava if diagnostic_context.available else None
    bhava_transition = None
    try:
        bhava_transition = bhava_transition_from_diagnostics(previous_bhava, current_bhava)
    except Exception:
        pass

    # Governor telemetry (from projection metadata)
    gov_telemetry = None
    try:
        composite = jepa_assessment.jepa_composite
        metadata = getattr(composite, "projection_metadata", None)
        if metadata is not None:
            meta_dict = metadata.to_dict() if hasattr(metadata, "to_dict") else metadata
            gov_telemetry = governor_telemetry_from_projection(meta_dict)
    except Exception:
        pass

    return bhava_transition, gov_telemetry


def _resolve_insight_signal(
    jepa_assessment: "JEPAGovernanceAssessment",
) -> InsightResolution:
    """Resolve insight gate signals from JEPA assessment data.

    Phase S2: Extracts insight-relevant metrics from existing JEPA signals.
    Returns a safe fallback if signals are insufficient.
    """
    try:
        ontology = jepa_assessment.jepa_composite.ontology
        vritti = jepa_assessment.jepa_composite.vritti
        # Map vritti name to index for insight gate
        _VRITTI_NAME_TO_IDX = {
            "pramana": 0, "viparyaya": 1, "vikalpa": 2,
            "smrti": 3, "nidra": 4,
        }
        vritti_idx = _VRITTI_NAME_TO_IDX.get(
            vritti.primary_vritti.lower() if vritti.primary_vritti else "", 0
        )
        return resolve_insight_signal(
            r_acc=ontology.confidence,
            s_acc=ontology.confidence * 0.95,  # approximate S-acc from ontology
            guna_coherence=ontology.confidence,
            authority=jepa_assessment.jepa_composite.integrated_confidence,
            vritti=vritti_idx,
        )
    except Exception:
        return resolve_insight_signal()


# =========================================================================
# Phase O4: Ontology balance signal resolution
# =========================================================================

# Ontology balance penalty constants
_ONTOLOGY_BALANCE_LOW_THRESHOLD = 0.35
_ONTOLOGY_BALANCE_CRITICAL_THRESHOLD = 0.20
_ONTOLOGY_BALANCE_MAX_PENALTY = 0.05


@dataclass(frozen=True)
class OntologyBalanceGovernanceSignal:
    """
    Governance-safe view of ontology balance for confidence/escalation.

    Derived from OntologyBalanceResolution. Provides:
    - bounded confidence_penalty [0.0, 0.05]
    - escalation_bias when balance is critically low
    - audit metadata

    Fail-closed: available=False → zero penalty, no escalation.
    """
    available: bool
    balance_score: float = 0.0
    confidence_penalty: float = 0.0
    escalation_bias: bool = False
    dominant_state: str = ""
    propagation_needed: int = 0
    source_detail: str = "ontology_balance_governance"

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "balance_score": round(self.balance_score, 4),
            "confidence_penalty": round(self.confidence_penalty, 4),
            "escalation_bias": self.escalation_bias,
            "dominant_state": self.dominant_state,
            "propagation_needed": self.propagation_needed,
            "source_detail": self.source_detail,
        }


_ONTOLOGY_BALANCE_UNAVAILABLE = OntologyBalanceGovernanceSignal(
    available=False,
    source_detail="ontology_balance_governance:unavailable",
)


def _resolve_ontology_balance_signal(
    request: AuthorizationRequest,
) -> OntologyBalanceGovernanceSignal:
    """Resolve ontology balance signal from the authorization request.

    Phase O4: Encodes the action description into a 10D ontological vector
    and computes mirror-pair balance. Low structural balance indicates
    the action context has high dimensional skew, warranting reduced
    confidence.

    Penalty logic:
        - balance_score >= 0.35 → 0.0 penalty (normal)
        - balance_score < 0.35  → linear penalty up to 0.05
        - balance_score < 0.20  → escalation bias (bump one level)

    Fail-closed: any error → available=False, zero penalty, no escalation.
    """
    try:
        # Build content string from action description.
        # This is the structural characterization of what governance is
        # deciding about — deterministic, bounded, and always available.
        action_type = getattr(request, "action_type", "") or ""
        tool_name = getattr(request, "tool_name", "") or ""
        content = f"{action_type} {tool_name}".strip()

        if not content:
            return _ONTOLOGY_BALANCE_UNAVAILABLE

        resolution = resolve_ontology_balance(content)

        if not resolution.available:
            return _ONTOLOGY_BALANCE_UNAVAILABLE

        balance = resolution.balance_score

        # Compute bounded confidence penalty
        if balance >= _ONTOLOGY_BALANCE_LOW_THRESHOLD:
            penalty = 0.0
        else:
            # Linear interpolation: 0.35→0.0 penalty, 0.0→0.05 penalty
            ratio = 1.0 - (balance / _ONTOLOGY_BALANCE_LOW_THRESHOLD)
            penalty = min(_ONTOLOGY_BALANCE_MAX_PENALTY,
                          _ONTOLOGY_BALANCE_MAX_PENALTY * ratio)

        # Escalation bias for critically low balance
        escalation_bias = balance < _ONTOLOGY_BALANCE_CRITICAL_THRESHOLD

        return OntologyBalanceGovernanceSignal(
            available=True,
            balance_score=balance,
            confidence_penalty=penalty,
            escalation_bias=escalation_bias,
            dominant_state=resolution.dominant_state,
            propagation_needed=len(resolution.propagation_needed),
        )

    except Exception:
        return _ONTOLOGY_BALANCE_UNAVAILABLE


# =============================================================================
# Plasticity gate resolution (Phase S2-safety)
# =============================================================================

def _resolve_plasticity_gate_signal(
    core_coherence_resolution: CoreCoherenceResolution,
) -> PlasticityResolution:
    """Resolve plasticity gate signal from already-resolved coherence state.

    Phase S2-safety: Feeds the PlasticityGate with coherence/drift signals
    already available from core_coherence_resolution (Step 5c4). No new
    upstream dependencies.

    Inputs:
        resistance ← semantic_stability ?? coherence_score (from C2)
        misalignment ← persona_drift (from C2)

    Fail-closed: if core coherence is unavailable or computation fails,
    returns available=False with zero penalty and no escalation bias.
    """
    try:
        if not core_coherence_resolution.available:
            return resolve_plasticity_signal()  # no inputs → unavailable

        return resolve_plasticity_signal(
            coherence_score=core_coherence_resolution.coherence_score,
            semantic_stability=core_coherence_resolution.semantic_stability,
            persona_drift=core_coherence_resolution.persona_drift,
        )

    except Exception:
        return resolve_plasticity_signal()  # fail-closed


# =============================================================================
# Readiness checker resolution (Phase S3-safety)
# =============================================================================

def _resolve_readiness_check_signal(
    plasticity_resolution: PlasticityResolution,
    core_coherence_resolution: CoreCoherenceResolution,
    effective_esc_level_value: str,
) -> ReadinessResolution:
    """Resolve readiness signal from already-resolved S2/C2 signals.

    Phase S3-safety: Evaluates multi-criterion readiness using:
    - plasticity from S2 (primary gate criterion)
    - stability from C2 core coherence
    - escalation level as proxy for pending escalations

    Fail-closed: if plasticity is unavailable, readiness cannot be
    assessed → returns available=False with zero penalty.
    """
    try:
        return resolve_readiness_signal(
            plasticity=plasticity_resolution.plasticity,
            coherence_score=core_coherence_resolution.coherence_score,
            semantic_stability=core_coherence_resolution.semantic_stability,
            escalation_level=effective_esc_level_value,
        )

    except Exception:
        return resolve_readiness_signal()  # fail-closed


def _build_rationale_codes(
    safety_summary: SafetyContractSummary,
    gate_decision: ConfidenceGateDecision,
    risk_level: ToolRiskLevel,
    forbidden_cap: Optional[str],
    governance_decision: APIGovernanceDecision,
    jepa_assessment: Optional["JEPAGovernanceAssessment"] = None,
    jepa_overrode: bool = False,
    domain_result: Optional["DomainPolicyResult"] = None,
    session_enrichment: Optional[SessionEnrichmentResolution] = None,
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

    # Domain policy rationale codes
    if domain_result is not None:
        codes.append(f"DOMAIN:{domain_result.domain_id}:{domain_result.mode.value}")
        for rc in domain_result.reason_codes:
            codes.append(f"DOMAIN_DETAIL:{rc}")

    # Phase 3: Session enrichment reason codes
    if session_enrichment is not None:
        for rc in session_enrichment.reason_codes:
            codes.append(rc)

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
    domain_result: Optional["DomainPolicyResult"] = None,
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

    # Domain policy rationale
    if domain_result is not None and domain_result.mode != DomainActionMode.ALLOW:
        parts.append(
            f"Domain policy '{domain_result.domain_id}': "
            f"mode={domain_result.mode.value}. {domain_result.rationale}"
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
        shadow_registry: Optional[ShadowRegistry] = None,
        policy_resolution: Optional[PolicyResolution] = None,
        approval_store: Optional[ApprovalStore] = None,
        agent_policy_engine: Optional[PolicyEngine] = None,
        rollback_monitor: Optional[RollbackMonitor] = None,
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
            shadow_registry: Optional ShadowRegistry for shadow AI control.
                When provided, the Shadow AI Control Layer evaluates asset
                provenance and sanctionedness before final enforcement.
            policy_resolution: Resolved policy bundle from the Policy
                Externalization Layer.  When provided, safety thresholds,
                forbidden capabilities, and risk mappings are sourced from
                the resolved policy instead of hardcoded defaults.
            approval_store: Optional ApprovalStore for durable approval workflow.
                When provided, DEFER+requires_human decisions create persistent
                approval requests with auditable state transitions.
            agent_policy_engine: Optional PolicyEngine for per-agent action
                policy (Phase S4-safety). When provided, allow/deny/blackout/
                rate-limit rules are evaluated before the governance decision.
                Fail-safe: if not provided, all actions are allowed by default.
            rollback_monitor: Optional RollbackMonitor for pre-action signal
                snapshot capture (Phase S5-safety). When provided, a pre-action
                signal snapshot is captured at authorize-time and a watch is
                started. Post-action check() must be called by external caller.
                Fail-safe: if not provided, no snapshot is captured.
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

        # Shadow AI Control Layer
        self._shadow_registry: Optional[ShadowRegistry] = shadow_registry

        # Policy Externalization Layer
        self._policy_resolution: Optional[PolicyResolution] = policy_resolution

        # Approval Workflow Layer
        self._approval_store: Optional[ApprovalStore] = approval_store

        # Agent Policy Engine (Phase S4-safety)
        self._agent_policy_engine: Optional[PolicyEngine] = agent_policy_engine

        # Rollback Monitor (Phase S5-safety)
        self._rollback_monitor: Optional[RollbackMonitor] = rollback_monitor

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

        # Step 2: Check forbidden capabilities (from policy or hardcoded)
        policy_forbidden = None
        if self._policy_resolution is not None:
            policy_forbidden = frozenset(
                self._policy_resolution.effective_policy.safety.forbidden_capabilities
            )
        forbidden_cap = _check_forbidden_capabilities(
            request.capabilities, forbidden=policy_forbidden,
        )

        # Step 2a: Agent policy engine check (Phase S4-safety).
        #   Evaluates per-agent allow/deny, blackout windows, and rate
        #   limits. Policy violations produce hard deny.
        #   Fail-safe: if no engine configured, all actions are allowed.
        agent_policy_resolution = resolve_policy_check(
            engine=self._agent_policy_engine,
            agent_id=request.actor_id,
            action_type=request.action_type,
        )

        # Step 2b: Resolve session enrichment signals (Phase 3)
        session_enrichment = _resolve_session_enrichment(request)

        # Step 3: Build confidence signals and evaluate gate
        signals = _build_confidence_signals(
            request, risk_level, policy_resolution=self._policy_resolution,
            session_enrichment=session_enrichment,
        )
        gate_decision = self.gate.evaluate(signals, tool_name)

        # Step 4: Evaluate safety contract preconditions
        safety_summary, eligible = _build_safety_contract_summary(
            request, risk_level, forbidden_cap, gate_decision,
            policy_resolution=self._policy_resolution,
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
        jepa_assessment, vritti_resolution, entropy_resolution = self._run_jepa_check(
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

        # Step 5c: Resolve Phase S2 sovereign signals (health + insight).
        #   These are resolved from existing JEPA/entropy data — no new
        #   external inputs needed. Fail-safe: if resolution fails,
        #   governance continues with zero penalty/zero bias.
        sovereign_health_resolution = _resolve_sovereign_health_signal(
            jepa_assessment, entropy_resolution,
        )
        insight_resolution = _resolve_insight_signal(jepa_assessment)

        # Step 5c2: Resolve Phase S3 reasoning diagnostics.
        diagnostic_context = _resolve_diagnostic_context(jepa_assessment)

        # Step 5c3: Resolve Phase S4 Guna anomaly signals.
        guna_anomaly_resolution = _resolve_guna_anomaly_signal(jepa_assessment)

        # Step 5c4: Resolve Phase C2 core pipeline coherence state.
        #   Bridges the pipeline's rich CoherenceState (241+ fields) into
        #   a bounded governance signal view. Fail-safe: if absent,
        #   zero penalty and no escalation bias.
        core_coherence_resolution = _resolve_core_coherence_state(request)

        # Step 5c5: Resolve Phase C3 UCF consciousness stability signal.
        #   Computes or reads the Unified Consciousness Formula as a
        #   governance-consumable stability metric. Uses pre-computed
        #   pipeline state or computes from C2 coherence signals.
        ucf_resolution = _resolve_ucf_signal(request, core_coherence_resolution)

        # Step 5c6: Check Phase C3 generation gate status.
        #   Queries the GenerationGate singleton to determine if
        #   generative actions are permitted. Non-generative actions
        #   are never affected. Fail-closed: unsealed or disabled = deny.
        generation_gate_result = _check_generation_gate(request)

        # Step 5c7: Resolve Phase C4 predictive signals (P35+P36+P37).
        #   P35 drift is behavior-affecting (max 0.03 penalty + escalation).
        #   P37 continuity is light behavior (max 0.02 penalty).
        #   P36 identity is audit-only (no penalty).
        predictive_resolution = _resolve_predictive_signals(request)

        # Step 5c8: Resolve Phase O4 ontology balance signal.
        #   Encodes the action context into a 10D ontological vector and
        #   computes mirror-pair balance. Low structural balance indicates
        #   dimensional skew in the action context, warranting reduced
        #   confidence. Max penalty: 0.05. Escalation bias below 0.20.
        #   Fail-closed: if resolution fails, zero penalty and no bias.
        ontology_balance_signal = _resolve_ontology_balance_signal(request)

        # Step 5c9: Resolve Phase S2-safety plasticity gate signal.
        #   Computes a sigmoid permission-to-act value from core coherence
        #   signals (stability → resistance, drift → misalignment).
        #   Low plasticity = gate closing = system not ready to act.
        #   Max penalty: 0.04. Escalation bias below 0.35.
        #   Fail-closed: if coherence unavailable, zero penalty and no bias.
        plasticity_resolution = _resolve_plasticity_gate_signal(
            core_coherence_resolution,
        )

        # Step 5d: Apply JEPA override fields to confidence, execution
        # mode, and escalation level. These modify the gate decision's
        # effective output — JEPA can only make things stricter.
        #
        # Phase 1: bounded entropy confidence penalty.
        # Phase S2: bounded insight confidence penalty + health awareness.
        # Phase S4 + C2 + C3 + C4: aggregate sovereign penalty cap (0.20)
        # prevents entropy + insight + guna + core coherence + UCF +
        # predictive signals from stacking beyond 0.20.
        # All penalties are non-positive (stricter-only).
        #
        # DRIFT OVERLAP NOTE (C2 + C4):
        # C2 (core_coherence) penalizes on current/stateful drift posture
        # from CoherenceState (persona_drift, drift_risk_band).
        # C4 (predictive) penalizes on predictive/forecast drift risk
        # from PredictivePersonaDriftReport (predicted_drift_score).
        # Both may contribute simultaneously when both signals are present.
        # This is intentional: current drift and predicted drift are
        # complementary signals, not duplicates. The aggregate cap (0.20)
        # bounds the combined effect and prevents runaway stacking.
        #
        # PLASTICITY NOTE (S2-safety):
        # Plasticity is derived FROM core_coherence (C2) inputs but is a
        # distinct signal: it captures the sigmoid permission-to-act state,
        # not the raw coherence/drift values. Its penalty (max 0.04) is
        # additive and bounded within the aggregate cap.
        sovereign_penalty = min(
            0.20,
            entropy_resolution.confidence_penalty
            + insight_resolution.confidence_penalty
            + guna_anomaly_resolution.confidence_penalty
            + core_coherence_resolution.confidence_penalty
            + ucf_resolution.confidence_penalty
            + predictive_resolution.confidence_penalty
            + ontology_balance_signal.confidence_penalty
            + plasticity_resolution.confidence_penalty,
        )
        effective_confidence = max(
            0.0,
            gate_decision.confidence.overall
            + jepa_assessment.confidence_adjustment
            - sovereign_penalty,
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

        # Phase S2: Sovereign health escalation bias (stricter-only).
        # If sovereign alert is LOCKDOWN_ACTIVE, bump escalation by one level.
        if sovereign_health_resolution.escalation_bias:
            _ESC_SEVERITY = {"none": 0, "notify": 1, "confirm": 2, "halt": 3}
            _ESC_FROM_SEVERITY = {0: "none", 1: "notify", 2: "confirm", 3: "halt"}
            current_severity = _ESC_SEVERITY.get(effective_esc_level.value, 0)
            bumped = min(current_severity + 1, 3)
            if bumped > current_severity:
                effective_esc_level = EscalationLevel(_ESC_FROM_SEVERITY[bumped])

        # Phase S2: Insight confirmation pressure (stricter-only).
        # If insight gate is eligible but release blocked, bump escalation.
        if insight_resolution.confirmation_pressure:
            _ESC_SEVERITY = {"none": 0, "notify": 1, "confirm": 2, "halt": 3}
            _ESC_FROM_SEVERITY = {0: "none", 1: "notify", 2: "confirm", 3: "halt"}
            current_severity = _ESC_SEVERITY.get(effective_esc_level.value, 0)
            bumped = min(current_severity + 1, 2)  # cap at confirm, not halt
            if bumped > current_severity:
                effective_esc_level = EscalationLevel(_ESC_FROM_SEVERITY[bumped])

        # Phase S3: Mauna (silence) protocol confirmation pressure (stricter-only).
        # If the model is in a withholding state, bump escalation by one level.
        if diagnostic_context.available and diagnostic_context.mauna_active:
            _ESC_SEVERITY = {"none": 0, "notify": 1, "confirm": 2, "halt": 3}
            _ESC_FROM_SEVERITY = {0: "none", 1: "notify", 2: "confirm", 3: "halt"}
            current_severity = _ESC_SEVERITY.get(effective_esc_level.value, 0)
            bumped = min(current_severity + 1, 2)  # cap at confirm, not halt
            if bumped > current_severity:
                effective_esc_level = EscalationLevel(_ESC_FROM_SEVERITY[bumped])

        # Phase S4: Guna collapse escalation bias (stricter-only).
        # If Guna collapse detected, bump escalation by one level.
        if guna_anomaly_resolution.escalation_bias:
            _ESC_SEVERITY = {"none": 0, "notify": 1, "confirm": 2, "halt": 3}
            _ESC_FROM_SEVERITY = {0: "none", 1: "notify", 2: "confirm", 3: "halt"}
            current_severity = _ESC_SEVERITY.get(effective_esc_level.value, 0)
            bumped = min(current_severity + 1, 2)  # cap at confirm, not halt
            if bumped > current_severity:
                effective_esc_level = EscalationLevel(_ESC_FROM_SEVERITY[bumped])

        # Phase C2: Core coherence drift escalation bias (stricter-only).
        # If critical/severe drift detected in pipeline CoherenceState,
        # bump escalation by one level (cap at confirm, not halt).
        if core_coherence_resolution.escalation_bias:
            _ESC_SEVERITY = {"none": 0, "notify": 1, "confirm": 2, "halt": 3}
            _ESC_FROM_SEVERITY = {0: "none", 1: "notify", 2: "confirm", 3: "halt"}
            current_severity = _ESC_SEVERITY.get(effective_esc_level.value, 0)
            bumped = min(current_severity + 1, 2)  # cap at confirm, not halt
            if bumped > current_severity:
                effective_esc_level = EscalationLevel(_ESC_FROM_SEVERITY[bumped])

        # Phase C3: UCF instability escalation bias (stricter-only).
        # If consciousness is in unstable band, bump escalation by one level.
        if ucf_resolution.escalation_bias:
            _ESC_SEVERITY = {"none": 0, "notify": 1, "confirm": 2, "halt": 3}
            _ESC_FROM_SEVERITY = {0: "none", 1: "notify", 2: "confirm", 3: "halt"}
            current_severity = _ESC_SEVERITY.get(effective_esc_level.value, 0)
            bumped = min(current_severity + 1, 2)  # cap at confirm, not halt
            if bumped > current_severity:
                effective_esc_level = EscalationLevel(_ESC_FROM_SEVERITY[bumped])

        # Phase C4: Predictive drift escalation bias (stricter-only).
        # If P35 predicts HIGH drift risk, bump escalation by one level.
        if predictive_resolution.escalation_bias:
            _ESC_SEVERITY = {"none": 0, "notify": 1, "confirm": 2, "halt": 3}
            _ESC_FROM_SEVERITY = {0: "none", 1: "notify", 2: "confirm", 3: "halt"}
            current_severity = _ESC_SEVERITY.get(effective_esc_level.value, 0)
            bumped = min(current_severity + 1, 2)  # cap at confirm, not halt
            if bumped > current_severity:
                effective_esc_level = EscalationLevel(_ESC_FROM_SEVERITY[bumped])

        # Phase O4: Ontology balance escalation bias (stricter-only).
        # If structural balance is critically low (< 0.20), bump escalation.
        if ontology_balance_signal.escalation_bias:
            _ESC_SEVERITY = {"none": 0, "notify": 1, "confirm": 2, "halt": 3}
            _ESC_FROM_SEVERITY = {0: "none", 1: "notify", 2: "confirm", 3: "halt"}
            current_severity = _ESC_SEVERITY.get(effective_esc_level.value, 0)
            bumped = min(current_severity + 1, 2)  # cap at confirm, not halt
            if bumped > current_severity:
                effective_esc_level = EscalationLevel(_ESC_FROM_SEVERITY[bumped])

        # Phase S2-safety: Plasticity gate escalation bias (stricter-only).
        # If plasticity gate is nearly closed (< 0.35), bump escalation.
        if plasticity_resolution.escalation_bias:
            _ESC_SEVERITY = {"none": 0, "notify": 1, "confirm": 2, "halt": 3}
            _ESC_FROM_SEVERITY = {0: "none", 1: "notify", 2: "confirm", 3: "halt"}
            current_severity = _ESC_SEVERITY.get(effective_esc_level.value, 0)
            bumped = min(current_severity + 1, 2)  # cap at confirm, not halt
            if bumped > current_severity:
                effective_esc_level = EscalationLevel(_ESC_FROM_SEVERITY[bumped])

        # Phase S3-safety: Readiness checker — multi-criterion readiness gate.
        #   Evaluates whether the system is ready to act based on:
        #   - Plasticity (from S2) — is the gate open enough?
        #   - Stability (from C2) — is the system coherent?
        #   - Pending escalations — are there blocking escalations?
        #   NOT_READY → penalty 0.03 + escalation bias.
        #   DEGRADED → penalty 0.02, no escalation.
        #   READY → zero penalty.
        #   Fail-closed: if plasticity unavailable, zero penalty.
        readiness_resolution = _resolve_readiness_check_signal(
            plasticity_resolution,
            core_coherence_resolution,
            effective_esc_level.value,
        )

        # Apply readiness penalty to sovereign aggregate
        # (additive, bounded within existing 0.20 cap via re-capping)
        if readiness_resolution.confidence_penalty > 0:
            sovereign_penalty = min(
                0.20,
                sovereign_penalty + readiness_resolution.confidence_penalty,
            )
            effective_confidence = max(
                0.0,
                gate_decision.confidence.overall
                + jepa_assessment.confidence_adjustment
                - sovereign_penalty,
            )

        # Phase S3-safety: Readiness escalation bias (stricter-only).
        # If NOT_READY, bump escalation by one level (cap at confirm).
        if readiness_resolution.escalation_bias:
            _ESC_SEVERITY = {"none": 0, "notify": 1, "confirm": 2, "halt": 3}
            _ESC_FROM_SEVERITY = {0: "none", 1: "notify", 2: "confirm", 3: "halt"}
            current_severity = _ESC_SEVERITY.get(effective_esc_level.value, 0)
            bumped = min(current_severity + 1, 2)  # cap at confirm, not halt
            if bumped > current_severity:
                effective_esc_level = EscalationLevel(_ESC_FROM_SEVERITY[bumped])

        # Phase C3: Generation gate enforcement (fail-closed).
        # If the action is generative and the gate blocks it, override
        # the governance decision to DENY. Non-generative actions are
        # never affected. This is the canonical governance-facing
        # integration of the generation gate.
        if generation_gate_result["gate_blocks"]:
            governance_decision = APIGovernanceDecision.DENY
            eligible = False

        # Phase S4-safety: Agent policy engine hard deny.
        # If the policy engine explicitly denies the action, override
        # the governance decision to DENY. This is a hard block,
        # similar to forbidden capabilities.
        if agent_policy_resolution.hard_deny:
            governance_decision = APIGovernanceDecision.DENY
            eligible = False

        effective_requires_human = (
            gate_decision.escalation.requires_human
            or effective_esc_level in (EscalationLevel.CONFIRM, EscalationLevel.HALT)
        )

        # Step 5e: Domain Semantic Policy Layer
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
                # Only set requires_human when the decision is not already
                # DENY — a denied request needs no human confirmation.
                if governance_decision != APIGovernanceDecision.DENY:
                    effective_requires_human = True
            elif domain_result.mode in (
                DomainActionMode.READ_ONLY,
                DomainActionMode.DRAFT_ONLY,
            ):
                if governance_decision == APIGovernanceDecision.ALLOW:
                    governance_decision = APIGovernanceDecision.DEFER
                    eligible = False

        # Step 5e: Shadow AI Control Layer
        #   Evaluates asset provenance, sanctionedness, and containment.
        #   Shadow policy can only make things STRICTER, never relax.
        #   Runs after domain policy so both signals are available.
        shadow_assessment: Optional[ShadowAssessment] = None
        shadow_audit: Optional[Dict[str, Any]] = None
        if self._shadow_registry is not None:
            # Determine action category from risk level
            _risk_to_action = {
                ToolRiskLevel.READ_ONLY: "read_only",
                ToolRiskLevel.WRITE: "mutating",
                ToolRiskLevel.EXECUTE: "mutating",
                ToolRiskLevel.DESTRUCTIVE: "destructive",
                ToolRiskLevel.PRIVILEGED: "privileged",
            }
            action_cat = _risk_to_action.get(risk_level, "unknown")
            mutation = action_cat in ("mutating", "destructive", "privileged")

            # Compute semantic mismatch from JEPA
            _sem_mismatch = 0.0
            if jepa_assessment.regime.value in ("process_drift", "semantic_shift"):
                _sem_mismatch = 0.5
            elif jepa_assessment.regime.value in ("dual_anomaly", "unknown"):
                _sem_mismatch = 0.8

            # Domain policy mismatch
            _dom_mismatch = 0.0
            if domain_result is not None and domain_result.mode != DomainActionMode.ALLOW:
                _dom_mismatch = domain_result.mode.severity / 6.0

            _shadow_asset_id = resolve_shadow_asset_id(
                tool_name=request.tool_name or "",
                actor_id=request.actor_id,
            )
            shadow_assessment = safe_resolve_shadow_policy(
                asset_id=_shadow_asset_id,
                tool_name=request.tool_name or "",
                provider=getattr(request, "provider", ""),
                registry=self._shadow_registry,
                action_category=action_cat,
                risk_level=risk_level.value,
                domain_id=self._domain_id or "",
                memory_write_intent=is_memory_write_intent(
                    action_type=request.action_type or "",
                    tool_name=request.tool_name or "",
                ),
                mutation_intent=mutation,
                jepa_regime=jepa_assessment.regime.value,
                semantic_mismatch=_sem_mismatch,
                domain_policy_mismatch=_dom_mismatch,
                confidence=effective_confidence,
            )
            shadow_audit = shadow_assessment.to_audit_dict()

            # Apply shadow containment as stricter-only override
            shadow_gov = shadow_containment_to_governance(
                shadow_assessment.containment_mode,
            )
            if shadow_gov == "DENY":
                governance_decision = APIGovernanceDecision.DENY
                eligible = False
            elif shadow_gov == "DEFER":
                if governance_decision == APIGovernanceDecision.ALLOW:
                    governance_decision = APIGovernanceDecision.DEFER
                    eligible = False
                if governance_decision != APIGovernanceDecision.DENY:
                    effective_requires_human = True

        # Step 6: Build rationale (includes JEPA and domain information)
        rationale_codes = _build_rationale_codes(
            safety_summary, gate_decision, risk_level, forbidden_cap,
            governance_decision, jepa_assessment, jepa_overrode,
            domain_result, session_enrichment,
        )
        # Add shadow reason codes
        if shadow_assessment is not None:
            for rc in shadow_assessment.reason_codes:
                rationale_codes.append(f"SHADOW:{rc}")
        rationale = _build_rationale_string(
            governance_decision, safety_summary, gate_decision, risk_level,
            forbidden_cap, jepa_assessment, jepa_overrode,
            domain_result,
        )
        if shadow_assessment is not None and shadow_assessment.shadow_overrode_baseline:
            rationale += (
                f" Shadow AI policy: {shadow_assessment.containment_mode.value}. "
                f"{shadow_assessment.rationale}"
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

        # Step 7b: Build sovereign telemetry snapshot (Phase S1)
        #   Derives a lightweight state snapshot from JEPA assessment signals.
        #   No tensor/PyTorch dependency — uses only float data from JEPA.
        sovereign_telemetry_dict = _build_sovereign_telemetry(
            jepa_assessment, vritti_resolution,
        )

        # Step 7c: Build Phase S2 audit dicts (health + insight)
        sovereign_health_dict = (
            {
                "alert_state": sovereign_health_resolution.alert_state,
                "lockdown_count": sovereign_health_resolution.lockdown_count,
                "entropy_status": sovereign_health_resolution.entropy_status,
                "inertial_brake_active": sovereign_health_resolution.inertial_brake_active,
                "escalation_bias": sovereign_health_resolution.escalation_bias,
                "caution_bias": sovereign_health_resolution.caution_bias,
                "reason_codes": list(sovereign_health_resolution.reason_codes),
                "source_detail": sovereign_health_resolution.source_detail,
            }
            if sovereign_health_resolution.available else None
        )
        sovereign_insight_dict = (
            {
                "eligible": insight_resolution.eligible,
                "can_release": insight_resolution.can_release,
                "stab_score": round(insight_resolution.stab_score, 4),
                "risk_score": round(insight_resolution.risk_score, 4),
                "confidence_penalty": insight_resolution.confidence_penalty,
                "confirmation_pressure": insight_resolution.confirmation_pressure,
                "reason_codes": list(insight_resolution.reason_codes),
                "source_detail": insight_resolution.source_detail,
            }
            if insight_resolution.available else None
        )

        # Step 7d: Build Phase S3 diagnostic audit dict
        sovereign_diagnostics_dict = (
            diagnostic_context.to_audit_dict()
            if diagnostic_context.available else None
        )

        # Step 7e: Build Phase S4 audit dicts (guna anomalies + bhava + governor)
        sovereign_guna_anomalies_dict = (
            guna_anomaly_resolution.to_audit_dict()
            if guna_anomaly_resolution.available else None
        )
        bhava_transition_dict, governor_telemetry_dict = _resolve_s4_audit_metadata(
            jepa_assessment, diagnostic_context,
            previous_bhava=None,  # Cross-call tracking not yet implemented
        )

        # Step 7f: Build Phase C2 core coherence audit dict
        core_coherence_dict = (
            core_coherence_resolution.to_audit_dict()
            if core_coherence_resolution.available else None
        )

        # Step 7g: Build Phase C3 UCF audit dict
        ucf_signal_dict = (
            ucf_resolution.to_audit_dict()
            if ucf_resolution.available else None
        )

        # Step 7h: Build Phase C3 generation gate audit dict
        generation_gate_dict = (
            generation_gate_result if generation_gate_result["is_generative"] else None
        )

        # Step 7i: Build Phase C4 predictive signals audit dict
        predictive_signals_dict = (
            predictive_resolution.to_audit_dict()
            if predictive_resolution.available else None
        )

        # Step 7j: Build Phase O4 ontology balance audit dict
        ontology_balance_dict = (
            ontology_balance_signal.to_audit_dict()
            if ontology_balance_signal.available else None
        )

        # Step 7k: Build Phase S2-safety plasticity gate audit dict
        plasticity_gate_dict = (
            plasticity_resolution.to_audit_dict()
            if plasticity_resolution.available else None
        )

        # Step 7l: Build Phase S3-safety readiness check audit dict
        readiness_check_dict = (
            readiness_resolution.to_audit_dict()
            if readiness_resolution.available else None
        )

        # Step 7m: Build Phase S4-safety agent policy audit dict
        agent_policy_dict = (
            agent_policy_resolution.to_audit_dict()
            if agent_policy_resolution.available else None
        )

        # Step 7n: Phase S5-safety — Rollback monitor pre-action snapshot.
        #   Captures governance signal values at decision time and registers
        #   a RollbackWatch with the monitor. The watch can later be checked
        #   by an external caller with post-action signals.
        #   No confidence penalty, no escalation bias — purely observational.
        #   Fail-safe: no monitor → no snapshot, no effect.
        rollback_resolution = resolve_rollback_snapshot(
            monitor=self._rollback_monitor,
            decision_id=decision_id,
            agent_id=request.actor_id,
            action_type=request.action_type,
            confidence=effective_confidence,
            plasticity=plasticity_resolution.plasticity,
            coherence=core_coherence_resolution.coherence_score,
        )
        rollback_watch_dict = (
            rollback_resolution.to_audit_dict()
            if rollback_resolution.available else None
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
                "internal_consistency": request.internal_consistency,
                "goal_alignment": request.goal_alignment,
                "trajectory_confidence": request.trajectory_confidence,
                "blocking_factors": request.blocking_factors,
                "jepa_regime": jepa_assessment.regime.value,
                "jepa_reason_codes": list(jepa_assessment.reason_codes),
                "jepa_overrode_baseline": jepa_overrode,
                "jepa_baseline_decision": baseline_decision.value,
                "jepa_confidence_adjustment": jepa_assessment.confidence_adjustment,
                "jepa_recommended_action": jepa_assessment.recommended_action,
                "jepa_execution_mode_override": jepa_assessment.execution_mode_override,
                "jepa_escalation_override": jepa_assessment.escalation_override,
                # Phase 1: Signal source provenance
                "vritti_signal_source": vritti_resolution.source.value,
                "vritti_signal_degraded": vritti_resolution.degraded,
                "vritti_signal_detail": vritti_resolution.source_detail,
                "entropy_available": entropy_resolution.available,
                "entropy_combined": entropy_resolution.combined_entropy,
                "entropy_confidence_penalty": entropy_resolution.confidence_penalty,
                "entropy_gate": entropy_resolution.gate,
                "entropy_detail": entropy_resolution.source_detail,
                "domain_policy": (
                    domain_result.to_audit_dict() if domain_result else None
                ),
                "policy_bundle": (
                    self._policy_resolution.effective_policy.to_audit_dict()
                    if self._policy_resolution is not None else None
                ),
                # Phase 3: Session enrichment provenance
                "session_identity_type": session_enrichment.identity_type,
                "session_identity_unstable": session_enrichment.identity_unstable,
                "session_motivation_type": session_enrichment.motivation_type,
                "session_motivation_risk": session_enrichment.motivation_risk_relevant,
                "session_temporal_state": session_enrichment.temporal_state,
                "session_temporal_tense": session_enrichment.temporal_tense,
                "session_confidence_adjustment": session_enrichment.confidence_adjustment,
                "session_enrichment_detail": session_enrichment.source_detail,
                # Phase S2: Sovereign health + insight provenance
                "sovereign_health_available": sovereign_health_resolution.available,
                "sovereign_health_alert": sovereign_health_resolution.alert_state,
                "sovereign_health_escalation_bias": sovereign_health_resolution.escalation_bias,
                "sovereign_insight_available": insight_resolution.available,
                "sovereign_insight_eligible": insight_resolution.eligible,
                "sovereign_insight_can_release": insight_resolution.can_release,
                "sovereign_insight_confidence_penalty": insight_resolution.confidence_penalty,
                "sovereign_insight_confirmation_pressure": insight_resolution.confirmation_pressure,
                # Phase S3: Reasoning diagnostics provenance
                "sovereign_diagnostics_available": diagnostic_context.available,
                "sovereign_diagnostics_mauna_active": diagnostic_context.mauna_active,
                "sovereign_diagnostics_source": diagnostic_context.source,
                # Phase S4: Guna anomaly provenance
                "sovereign_guna_anomaly_available": guna_anomaly_resolution.available,
                "sovereign_guna_collapse": guna_anomaly_resolution.collapse,
                "sovereign_guna_oscillation": guna_anomaly_resolution.oscillation,
                "sovereign_guna_stagnation": guna_anomaly_resolution.stagnation,
                "sovereign_guna_confidence_penalty": guna_anomaly_resolution.confidence_penalty,
                "sovereign_guna_escalation_bias": guna_anomaly_resolution.escalation_bias,
                # Phase C2: Core pipeline coherence state provenance
                "core_coherence_available": core_coherence_resolution.available,
                "core_coherence_score": core_coherence_resolution.coherence_score,
                "core_coherence_persona_drift": core_coherence_resolution.persona_drift,
                "core_coherence_drift_risk_band": core_coherence_resolution.drift_risk_band,
                "core_coherence_confidence_penalty": core_coherence_resolution.confidence_penalty,
                "core_coherence_escalation_bias": core_coherence_resolution.escalation_bias,
                # Phase C3: UCF consciousness stability provenance
                "ucf_available": ucf_resolution.available,
                "ucf_score": ucf_resolution.ucf_score,
                "ucf_stability_band": ucf_resolution.stability_band,
                "ucf_confidence_penalty": ucf_resolution.confidence_penalty,
                "ucf_escalation_bias": ucf_resolution.escalation_bias,
                "ucf_computation_source": ucf_resolution.computation_source,
                # Phase C3: Generation gate provenance
                "generation_gate_is_generative": generation_gate_result["is_generative"],
                "generation_gate_status": generation_gate_result["gate_status"],
                "generation_gate_mode": generation_gate_result["generation_mode"],
                "generation_gate_blocks": generation_gate_result["gate_blocks"],
                "generation_gate_block_reason": generation_gate_result["block_reason"],
                # Phase C4: Predictive signals provenance
                "predictive_available": predictive_resolution.available,
                "predictive_drift_score": predictive_resolution.predicted_drift_score,
                "predictive_drift_risk_band": predictive_resolution.drift_risk_band,
                "predictive_drift_trend": predictive_resolution.drift_trend,
                "predictive_continuity_score": predictive_resolution.continuity_score,
                "predictive_continuity_mode": predictive_resolution.continuity_mode,
                "predictive_identity_resonance": predictive_resolution.identity_resonance_index,
                "predictive_identity_band": predictive_resolution.identity_stability_band,
                "predictive_confidence_penalty": predictive_resolution.confidence_penalty,
                "predictive_escalation_bias": predictive_resolution.escalation_bias,
                # Phase O4: Ontology balance signal provenance
                "ontology_balance_available": ontology_balance_signal.available,
                "ontology_balance_score": ontology_balance_signal.balance_score,
                "ontology_balance_confidence_penalty": ontology_balance_signal.confidence_penalty,
                "ontology_balance_escalation_bias": ontology_balance_signal.escalation_bias,
                "ontology_balance_dominant_state": ontology_balance_signal.dominant_state,
                # Phase S2-safety: Plasticity gate provenance
                "plasticity_available": plasticity_resolution.available,
                "plasticity_value": plasticity_resolution.plasticity,
                "plasticity_confidence_penalty": plasticity_resolution.confidence_penalty,
                "plasticity_escalation_bias": plasticity_resolution.escalation_bias,
                # Phase S3-safety: Readiness checker provenance
                "readiness_available": readiness_resolution.available,
                "readiness_status": readiness_resolution.status,
                "readiness_ready": readiness_resolution.ready,
                "readiness_confidence_penalty": readiness_resolution.confidence_penalty,
                "readiness_escalation_bias": readiness_resolution.escalation_bias,
                # Phase S4-safety: Agent policy engine provenance
                "agent_policy_available": agent_policy_resolution.available,
                "agent_policy_allowed": agent_policy_resolution.allowed,
                "agent_policy_hard_deny": agent_policy_resolution.hard_deny,
                "agent_policy_violations": list(agent_policy_resolution.violations),
                # Phase S5-safety: Rollback monitor provenance
                "rollback_available": rollback_resolution.available,
                "rollback_watch_started": rollback_resolution.watch_started,
                "rollback_watch_id": rollback_resolution.watch_id,
            },
            shadow_assessment=shadow_audit,
            sovereign_telemetry=sovereign_telemetry_dict,
            sovereign_health=sovereign_health_dict,
            sovereign_insight=sovereign_insight_dict,
            sovereign_diagnostics=sovereign_diagnostics_dict,
            sovereign_guna_anomalies=sovereign_guna_anomalies_dict,
            sovereign_bhava_transition=bhava_transition_dict,
            sovereign_governor_telemetry=governor_telemetry_dict,
            core_coherence=core_coherence_dict,
            ucf_signal=ucf_signal_dict,
            generation_gate=generation_gate_dict,
            predictive_signals=predictive_signals_dict,
            ontology_balance=ontology_balance_dict,
            plasticity_gate=plasticity_gate_dict,
            readiness_check=readiness_check_dict,
            agent_policy=agent_policy_dict,
            rollback_watch=rollback_watch_dict,
        )
        self._persist_audit_event(audit_event)

        # Step 9: Create approval request if needed
        #   approval_required is only True when an approval object is actually
        #   created.  If no store is configured, the response signals
        #   requires_human_approval but does not claim a durable approval exists.
        approval_required = False
        approval_id = None
        approval_summary = None

        _needs_approval = (
            effective_requires_human
            and governance_decision in (
                APIGovernanceDecision.DEFER,
                APIGovernanceDecision.DENY,
            )
        )

        if _needs_approval and self._approval_store is not None:
            # Map escalation level to approval level
            _esc_to_approval = {
                "halt": ApprovalLevel.HALT,
                "confirm": ApprovalLevel.CONFIRM,
            }
            approval_level = _esc_to_approval.get(
                effective_esc_level.value, ApprovalLevel.CONFIRM,
            )

            approval_context = ApprovalContext(
                governance_decision_id=decision_id,
                action_type=request.action_type,
                tool_name=request.tool_name or "",
                actor_id=request.actor_id,
                risk_level=risk_level.value,
                confidence_score=effective_confidence,
                escalation_level=effective_esc_level.value,
                execution_mode=effective_exec_mode.value,
                reason_codes=tuple(rationale_codes),
                policy_id=(
                    self._policy_resolution.effective_policy.metadata.policy_id
                    if self._policy_resolution else None
                ),
                policy_version=(
                    self._policy_resolution.effective_policy.metadata.version
                    if self._policy_resolution else None
                ),
                domain_id=self._domain_id,
                tenant_id=getattr(request, "tenant_id", None),
                session_id=getattr(request, "session_id", None),
                # Phase 3: Session enrichment context
                session_identity_type=session_enrichment.identity_type,
                session_identity_unstable=session_enrichment.identity_unstable,
                session_motivation_type=session_enrichment.motivation_type,
                session_motivation_risk=session_enrichment.motivation_risk_relevant,
                session_temporal_state=session_enrichment.temporal_state,
                session_temporal_tense=session_enrichment.temporal_tense,
                session_confidence_adjustment=session_enrichment.confidence_adjustment,
            )

            try:
                approval_req = self._approval_store.create_request(
                    context=approval_context,
                    approval_level=approval_level,
                )
                approval_id = approval_req.approval_id
                approval_summary = approval_req.to_summary_dict()
                approval_required = True
            except ApprovalStoreError:
                # FAIL-CLOSED: approval creation failed → DENY
                # approval_required stays False — no durable approval exists
                _logger.error(
                    "APPROVAL STORE FAILURE for decision %s — "
                    "failing closed to DENY",
                    decision_id,
                    exc_info=True,
                )
                governance_decision = APIGovernanceDecision.DENY
                eligible = False
                rationale_codes.append("APPROVAL_STORE_FAILURE")

        # Step 9b: Record approval_id in the in-memory audit event snapshot.
        # The durable audit store was written before approval creation (it
        # provides the decision_id that the approval context references).
        # Bidirectional linkage: audit→approval via this snapshot field,
        # approval→audit via ApprovalContext.governance_decision_id.
        if approval_id is not None:
            audit_event.request_snapshot["approval_id"] = approval_id

        # Step 10: Assemble response (uses JEPA-adjusted fields)
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
            shadow_assessment=shadow_audit,
            approval_required=approval_required,
            approval_id=approval_id,
            approval_summary=approval_summary,
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
                shadow_assessment=audit_event.shadow_assessment,
                shadow_overrode=bool(audit_event.shadow_assessment),
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
    ) -> Tuple[JEPAGovernanceAssessment, VrittiResolution, EntropyResolution]:
        """Run JEPA residual governance check. Always returns an assessment.

        Uses safe_jepa_governance_check which catches internal errors
        and returns an explicit UNKNOWN-regime assessment. Never returns
        None — JEPA failure is itself a governance condition.

        Phase 1: Now uses vritti signal adapter (prefers real chitta_vritti)
        and resolves entropy for governance context.

        Returns:
            Tuple of (JEPAGovernanceAssessment, VrittiResolution, EntropyResolution).
        """
        layer_weights = _approximate_layer_weights(request, gate_decision)

        # Phase 1: Resolve vritti via adapter (real > approximation)
        vritti_resolution = _resolve_vritti(request, gate_decision)
        vritti_dist = vritti_resolution.distribution

        # Phase 1: Resolve entropy for governance context
        entropy_resolution = _resolve_entropy(request)

        assessment = safe_jepa_governance_check(
            layer_weights=layer_weights,
            vritti_distribution=vritti_dist,
            coherence=vritti_resolution.coherence,
            score=vritti_resolution.score,
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
            projection_metadata=getattr(request, "sovereign_projection_metadata", None),
        )

        return assessment, vritti_resolution, entropy_resolution

    # =====================================================================
    # Layer Visibility / RBAC — Policy Phase P0
    # =====================================================================

    def check_layer_visibility(
        self,
        role_id: str,
        artifact_id: str,
        span_id: str,
        projected_layers: Tuple[Any, ...],
        requested_layers: Optional[Tuple[Any, ...]] = None,
    ) -> Dict[str, Any]:
        """
        Check which ontological layers are visible to a role.

        Uses the ExposureGate from agentic.policy.layer_visibility_policy
        to enforce fail-closed RBAC on layer visibility.

        This is the canonical governance-facing entry point for layer
        visibility checks. It wraps the ExposureGate with:
        - Role string → RoleId enum resolution
        - Audit logging
        - Fail-closed error handling
        - Serialized result for API/dashboard consumption

        Args:
            role_id: Role identifier ("end_user", "developer", "auditor", "system")
            artifact_id: Identifier of the artifact being accessed
            span_id: Identifier of the ledger span
            projected_layers: Tuple of OntologicalLayer values from projection
            requested_layers: Optional specific layers to request (None = all allowed)

        Returns:
            Dict with:
                allowed_layers: list of allowed layer names
                denied_layers: list of denied layer names
                effective_layers: list of effective (visible) layer names
                decision_hash: deterministic hash of the decision
                decision: "allowed" or "denied"
                error: error message if evaluation failed (fail-closed)

        Fail-Closed:
            Any error during evaluation returns an empty-allowed result.
        """
        try:
            from agentic.policy.layer_visibility_policy import (
                ExposureGate,
                ExposureRequest,
                RoleId,
                DEFAULT_POLICY,
            )
            from agentic.ontology.contracts.projection_contract import (
                ProjectionResponse,
            )

            # Resolve role string to RoleId enum
            role_enum = self._resolve_role_id(role_id)

            # Build projection response (structural wrapper for the gate)
            projection_response = ProjectionResponse(
                layers=tuple(projected_layers),
            )

            # Build exposure request
            exposure_request = ExposureRequest(
                artifact_id=artifact_id,
                span_id=span_id,
                role_id=role_enum,
                requested_layers=requested_layers,
            )

            # Evaluate through ExposureGate (fail-closed internally)
            gate = ExposureGate(policy=DEFAULT_POLICY)
            response = gate.evaluate(projection_response, exposure_request)

            result = {
                "allowed_layers": [l.name for l in response.allowed_layers],
                "denied_layers": [l.name for l in response.denied_layers],
                "effective_layers": [l.name for l in response.effective_layers],
                "decision_hash": response.decision_hash,
                "decision": "allowed" if len(response.effective_layers) > 0 else "denied",
                "error": None,
            }

            # Audit logging (best-effort, must not break main flow)
            try:
                self._log_layer_visibility_check(
                    role_id=role_id,
                    artifact_id=artifact_id,
                    result=result,
                )
            except Exception:
                pass  # Audit failure must not affect the decision

            return result

        except Exception as e:
            # Fail-closed: any error → deny all
            result = {
                "allowed_layers": [],
                "denied_layers": [],
                "effective_layers": [],
                "decision_hash": "",
                "decision": "denied",
                "error": f"Layer visibility check failed: {str(e)}",
            }
            return result

    @staticmethod
    def _resolve_role_id(role_str: str) -> Any:
        """
        Resolve a role string to RoleId enum.

        Args:
            role_str: Role identifier string

        Returns:
            RoleId enum value

        Raises:
            ValueError: If role_str is not a recognized role
        """
        from agentic.policy.layer_visibility_policy import RoleId

        _ROLE_MAP = {
            "end_user": RoleId.END_USER,
            "developer": RoleId.DEVELOPER,
            "auditor": RoleId.AUDITOR,
            "system": RoleId.SYSTEM,
        }
        normalized = role_str.lower().strip()
        if normalized not in _ROLE_MAP:
            raise ValueError(
                f"Unknown role '{role_str}'. "
                f"Valid roles: {list(_ROLE_MAP.keys())}"
            )
        return _ROLE_MAP[normalized]

    def _log_layer_visibility_check(
        self,
        role_id: str,
        artifact_id: str,
        result: Dict[str, Any],
    ) -> None:
        """Log a layer visibility check to the audit trail.

        Uses a lightweight dict entry instead of the full AuditEvent
        model, since layer visibility checks have a different shape
        than authorization decisions.
        """
        entry = {
            "event_type": "layer_visibility_check",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision_id": f"lvp-{hashlib.sha256(f'{role_id}:{artifact_id}'.encode()).hexdigest()[:12]}",
            "role_id": role_id,
            "artifact_id": artifact_id,
            "decision": result["decision"],
            "effective_layers": result["effective_layers"],
            "decision_hash": result["decision_hash"],
        }
        # Store in a separate visibility log (lightweight)
        if not hasattr(self, "_visibility_log"):
            self._visibility_log: List[Dict[str, Any]] = []
        self._visibility_log.append(entry)

    # =====================================================================
    # Policy Service Integration — Policy Phase P1
    # =====================================================================

    def get_policy_service(self) -> Any:
        """
        Get a PolicyService instance attached to this GovernanceService.

        Returns a lazily-created PolicyService whose audit log can be
        retrieved alongside the governance audit log.

        Returns:
            PolicyService instance (from agentic.policy.policy_service)
        """
        if not hasattr(self, "_policy_service"):
            from agentic.policy.policy_service import PolicyService
            self._policy_service = PolicyService()
        return self._policy_service

    def get_policy_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent policy audit entries from the attached PolicyService.

        Returns an empty list if no PolicyService has been used yet.
        """
        if not hasattr(self, "_policy_service"):
            return []
        return self._policy_service.get_policy_audit_log(limit=limit)

    def get_audit_log(self, limit: int = 100) -> List[AuditEvent]:
        """Get recent audit events (from in-memory cache)."""
        return self._audit_log[-limit:]

    def get_audit_count(self) -> int:
        """Get total number of audit events."""
        if self._audit_store is not None:
            return self._audit_store.count()
        return len(self._audit_log)
