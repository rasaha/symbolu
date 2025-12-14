"""
Action Eligibility & Commitment Boundary Engine (AECBE) — Core/Substrate Utility
==================================================================================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                         CORE/SUBSTRATE LAYER                                   ║
║                                                                                ║
║  This module is part of the Core/Substrate layer.                              ║
║  It is NOT a pipeline phase and has no authority over intent, regime,          ║
║  semantics, or delivery.                                                       ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Deterministic, zero-LLM, observation-only boundary engine that computes whether
the system's current cognitive state is eligible to transition toward action consideration.

HISTORICAL NOTE: Legacy docstrings may reference "Phase 54". This is a
historical development label, NOT an authoritative pipeline phase.

This engine does NOT perform actions, select actions, route actions, or trigger agents.
It only computes a read-only eligibility verdict.

INPUTS (READ-ONLY):
- Phase 50: Cognitive Consistency Regression
- Phase 51: RAG Coherence Validation
- Phase 52: Internal–External Reality CVE
- Phase 53: External Reality Trust Calibration
- Supporting stability signals:
  - Phase 47: Synthesis
  - Phase 48: Macro Stability
  - Phase 49: Temporal Stability

OUTPUTS (ALL ∈ [0.0, 1.0]):
- action_eligibility_score: Overall action eligibility score
- internal_stability_index: Internal cognition stability
- external_alignment_index: External reality alignment
- trust_confidence_index: External trust calibration confidence
- conflict_suppression_index: Conflict/contradiction resolution quality
- temporal_persistence_index: Temporal stability persistence

BAND CLASSIFICATION (EXACTLY ONE):
- ELIGIBLE: High stability + high trust + low conflict
- CONDITIONALLY_ELIGIBLE: Stable but weak trust OR partial alignment
- NOT_ELIGIBLE: High conflict OR instability
- BLOCKED: Severe contradiction or trust collapse

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - NO action execution: Only computes eligibility verdict
    - NO action selection: Does not choose or recommend actions
    - Metadata-only persona integration: NO tone or semantic changes
    - Diagnostics/UI only: Feeds coherence state, session summary, unified API, and DILchat badges
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Fully bounded: All outputs [0.0, 1.0]
    - Graceful degradation: Returns None if insufficient data available
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ActionEligibilitySnapshot:
    """
    Immutable snapshot of Action Eligibility & Commitment Boundary Engine computation.

    This snapshot measures whether the system's current cognitive state is eligible
    to transition toward action consideration (NOT execution).

    Fields:
        action_eligibility_score: [0.0, 1.0] - Overall action eligibility score
        eligibility_band: Classification: "ELIGIBLE" | "CONDITIONALLY_ELIGIBLE" | "NOT_ELIGIBLE" | "BLOCKED"
        internal_stability_index: [0.0, 1.0] - Internal cognition stability
        external_alignment_index: [0.0, 1.0] - External reality alignment
        trust_confidence_index: [0.0, 1.0] - External trust calibration confidence
        conflict_suppression_index: [0.0, 1.0] - Conflict/contradiction resolution quality
        temporal_persistence_index: [0.0, 1.0] - Temporal stability persistence
        eligibility_tags: List of diagnostic pattern indicators
    """

    action_eligibility_score: float = 0.0
    eligibility_band: str = "NOT_ELIGIBLE"
    internal_stability_index: float = 0.0
    external_alignment_index: float = 0.0
    trust_confidence_index: float = 0.0
    conflict_suppression_index: float = 0.0
    temporal_persistence_index: float = 0.0
    eligibility_tags: List[str] = field(default_factory=list)


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp value to [min_val, max_val] range.

    Args:
        value: Value to clamp
        min_val: Minimum value (default 0.0)
        max_val: Maximum value (default 1.0)

    Returns:
        float: Clamped value
    """
    return max(min_val, min(max_val, value))


def _compute_mean(values: List[float]) -> float:
    """
    Compute mean of a list of values.

    Args:
        values: List of float values

    Returns:
        float: Mean value or 0.0 if empty
    """
    if not values:
        return 0.0
    # Filter out None values
    valid_values = [v for v in values if v is not None]
    if not valid_values:
        return 0.0
    return sum(valid_values) / len(valid_values)


def compute_action_eligibility_boundary(
    *,
    cognitive_consistency_signals: Optional[Dict[str, float]] = None,
    rag_coherence_signals: Optional[Dict[str, float]] = None,
    internal_external_alignment_signals: Optional[Dict[str, float]] = None,
    external_trust_signals: Optional[Dict[str, float]] = None,
    stability_signals: Optional[Dict[str, float]] = None,
) -> Optional[ActionEligibilitySnapshot]:
    """
    Compute Action Eligibility & Commitment Boundary Engine (AECBE) v1.0.

    This function computes whether the system's current cognitive state is eligible
    to transition toward action consideration (NOT execution).

    Args:
        cognitive_consistency_signals: Dict from Phase 50 (Cognitive Consistency Regression) containing:
            - regression_stability_index: [0.0, 1.0] - How stable regression patterns are
            - internal_consistency_strength: [0.0, 1.0] - Composite consistency metric
            - prediction_reversal_risk: [0.0, 1.0] - Whether slope directions flip
            - regression_drift_score: [0.0, 1.0] - How much signals are drifting

        rag_coherence_signals: Dict from Phase 51 (RAG Coherence Validation) containing:
            - evidence_alignment: [0.0, 1.0] - How well internal signals match RAG evidence
            - evidence_conflict_index: [0.0, 1.0] - Contradictions between cognition and RAG
            - evidence_stability: [0.0, 1.0] - Consistency of RAG evidence over time
            - context_relevance_score: [0.0, 1.0] - Relevance of RAG evidence

        internal_external_alignment_signals: Dict from Phase 52 (IER-CVE) containing:
            - alignment_index: [0.0, 1.0] - Agreement between internal and external reality
            - divergence_index: [0.0, 1.0] - Disagreement between internal and external
            - evidence_conflict_index: [0.0, 1.0] - Contradictions between internal and external
            - stability_projection_index: [0.0, 1.0] - Expected future stability

        external_trust_signals: Dict from Phase 53 (ERTCE) containing:
            - external_trust_score: [0.0, 1.0] - Overall confidence in external reality
            - internal_override_pressure: [0.0, 1.0] - Internal cognition contradicts external
            - external_signal_fragility: [0.0, 1.0] - External signal sensitivity
            - alignment_resilience: [0.0, 1.0] - Stability of internal-external agreement
            - trust_decay_risk: [0.0, 1.0] - Likelihood trust degrades

        stability_signals: Dict from Phases 47-49 containing:
            - synthesis_integrity: Phase 47 synthesis integrity [0.0, 1.0]
            - macro_stability_index: Phase 48 macro stability [0.0, 1.0]
            - temporal_stability_index: Phase 49 temporal stability [0.0, 1.0]

    Returns:
        ActionEligibilitySnapshot or None if insufficient data available

    Formula Design:
        Internal Stability Index (ISI):
            - Combines Phase 50 consistency + Phase 47-49 stability signals
            - High ISI = stable internal cognition

        External Alignment Index (EAI):
            - Combines Phase 51 RAG alignment + Phase 52 IER-CVE alignment
            - High EAI = external reality well-aligned

        Trust Confidence Index (TCI):
            - From Phase 53 trust score + resilience
            - High TCI = external trust is strong and stable

        Conflict Suppression Index (CSI):
            - Inverse of conflicts from Phases 51, 52, 53
            - High CSI = low conflict/contradiction

        Temporal Persistence Index (TPI):
            - From Phase 49 temporal stability + Phase 50 regression stability
            - High TPI = patterns persist over time

        Action Eligibility Score (AES):
            - Weighted combination of all indices
            - AES = 0.25*ISI + 0.25*EAI + 0.20*TCI + 0.15*CSI + 0.15*TPI

        Band Classification (priority-ordered, deterministic):
            * ELIGIBLE: AES >= 0.70 and ISI >= 0.65 and TCI >= 0.60 and CSI >= 0.70
            * CONDITIONALLY_ELIGIBLE: AES >= 0.50 and ISI >= 0.45 and CSI >= 0.50
            * NOT_ELIGIBLE: AES >= 0.30 or (ISI >= 0.30 and CSI >= 0.35)
            * BLOCKED: otherwise (AES < 0.30 or severe contradictions)

    Graceful Degradation:
        Returns None if insufficient data from prerequisite phases (50-53, 47-49)
    """
    # ========================================================================
    # STEP 1: VALIDATE INPUT AVAILABILITY
    # ========================================================================

    # Need at least 3 out of 5 input signal groups for meaningful analysis
    available_signals = 0
    if cognitive_consistency_signals:
        available_signals += 1
    if rag_coherence_signals:
        available_signals += 1
    if internal_external_alignment_signals:
        available_signals += 1
    if external_trust_signals:
        available_signals += 1
    if stability_signals:
        available_signals += 1

    if available_signals < 3:
        return None

    # ========================================================================
    # STEP 2: EXTRACT COGNITIVE CONSISTENCY SIGNALS (PHASE 50)
    # ========================================================================

    if cognitive_consistency_signals:
        cc_regression_stability = cognitive_consistency_signals.get("regression_stability_index", 0.5)
        cc_internal_consistency = cognitive_consistency_signals.get("internal_consistency_strength", 0.5)
        cc_reversal_risk = cognitive_consistency_signals.get("prediction_reversal_risk", 0.5)
        cc_drift_score = cognitive_consistency_signals.get("regression_drift_score", 0.5)
    else:
        cc_regression_stability = 0.5
        cc_internal_consistency = 0.5
        cc_reversal_risk = 0.5
        cc_drift_score = 0.5

    # ========================================================================
    # STEP 3: EXTRACT RAG COHERENCE SIGNALS (PHASE 51)
    # ========================================================================

    if rag_coherence_signals:
        rag_evidence_alignment = rag_coherence_signals.get("evidence_alignment", 0.5)
        rag_conflict_index = rag_coherence_signals.get("evidence_conflict_index", 0.5)
        rag_evidence_stability = rag_coherence_signals.get("evidence_stability", 0.5)
        rag_context_relevance = rag_coherence_signals.get("context_relevance_score", 0.5)
    else:
        rag_evidence_alignment = 0.5
        rag_conflict_index = 0.5
        rag_evidence_stability = 0.5
        rag_context_relevance = 0.5

    # ========================================================================
    # STEP 4: EXTRACT INTERNAL-EXTERNAL ALIGNMENT SIGNALS (PHASE 52)
    # ========================================================================

    if internal_external_alignment_signals:
        ier_alignment_index = internal_external_alignment_signals.get("alignment_index", 0.5)
        ier_divergence_index = internal_external_alignment_signals.get("divergence_index", 0.5)
        ier_conflict_index = internal_external_alignment_signals.get("evidence_conflict_index", 0.5)
        ier_stability_projection = internal_external_alignment_signals.get("stability_projection_index", 0.5)
    else:
        ier_alignment_index = 0.5
        ier_divergence_index = 0.5
        ier_conflict_index = 0.5
        ier_stability_projection = 0.5

    # ========================================================================
    # STEP 5: EXTRACT EXTERNAL TRUST SIGNALS (PHASE 53)
    # ========================================================================

    if external_trust_signals:
        ertce_trust_score = external_trust_signals.get("external_trust_score", 0.5)
        ertce_override_pressure = external_trust_signals.get("internal_override_pressure", 0.5)
        ertce_signal_fragility = external_trust_signals.get("external_signal_fragility", 0.5)
        ertce_alignment_resilience = external_trust_signals.get("alignment_resilience", 0.5)
        ertce_decay_risk = external_trust_signals.get("trust_decay_risk", 0.5)
    else:
        ertce_trust_score = 0.5
        ertce_override_pressure = 0.5
        ertce_signal_fragility = 0.5
        ertce_alignment_resilience = 0.5
        ertce_decay_risk = 0.5

    # ========================================================================
    # STEP 6: EXTRACT STABILITY SIGNALS (PHASES 47-49)
    # ========================================================================

    if stability_signals:
        synthesis_integrity = stability_signals.get("synthesis_integrity", 0.5)
        macro_stability_index = stability_signals.get("macro_stability_index", 0.5)
        temporal_stability_index = stability_signals.get("temporal_stability_index", 0.5)
    else:
        synthesis_integrity = 0.5
        macro_stability_index = 0.5
        temporal_stability_index = 0.5

    # ========================================================================
    # STEP 7: COMPUTE INTERNAL STABILITY INDEX (ISI)
    # ========================================================================

    # Internal stability combines:
    # - Phase 50 internal consistency + regression stability
    # - Phase 47-49 stability signals
    # - Inverse of reversal risk and drift

    internal_stability_components = [
        cc_internal_consistency,
        cc_regression_stability,
        synthesis_integrity,
        macro_stability_index,
        temporal_stability_index,
        1.0 - cc_reversal_risk,  # Lower reversal risk = more stable
        1.0 - (cc_drift_score * 0.5),  # Some drift is acceptable
    ]

    internal_stability_index = _compute_mean(internal_stability_components)
    internal_stability_index = _clamp(internal_stability_index, 0.0, 1.0)

    # ========================================================================
    # STEP 8: COMPUTE EXTERNAL ALIGNMENT INDEX (EAI)
    # ========================================================================

    # External alignment combines:
    # - Phase 51 RAG evidence alignment
    # - Phase 52 internal-external alignment
    # - Phase 51 context relevance

    external_alignment_components = [
        rag_evidence_alignment,
        ier_alignment_index,
        rag_context_relevance,
        ier_stability_projection,
    ]

    external_alignment_index = _compute_mean(external_alignment_components)
    external_alignment_index = _clamp(external_alignment_index, 0.0, 1.0)

    # ========================================================================
    # STEP 9: COMPUTE TRUST CONFIDENCE INDEX (TCI)
    # ========================================================================

    # Trust confidence from Phase 53:
    # - External trust score
    # - Alignment resilience
    # - Inverse of fragility and decay risk

    trust_confidence_components = [
        ertce_trust_score,
        ertce_alignment_resilience,
        1.0 - ertce_signal_fragility,
        1.0 - ertce_decay_risk,
    ]

    trust_confidence_index = _compute_mean(trust_confidence_components)
    trust_confidence_index = _clamp(trust_confidence_index, 0.0, 1.0)

    # ========================================================================
    # STEP 10: COMPUTE CONFLICT SUPPRESSION INDEX (CSI)
    # ========================================================================

    # Conflict suppression is inverse of conflicts from all sources:
    # - Phase 51 RAG conflict
    # - Phase 52 IER conflict + divergence
    # - Phase 53 override pressure

    conflict_suppression_components = [
        1.0 - rag_conflict_index,
        1.0 - ier_conflict_index,
        1.0 - ier_divergence_index,
        1.0 - ertce_override_pressure,
    ]

    conflict_suppression_index = _compute_mean(conflict_suppression_components)
    conflict_suppression_index = _clamp(conflict_suppression_index, 0.0, 1.0)

    # ========================================================================
    # STEP 11: COMPUTE TEMPORAL PERSISTENCE INDEX (TPI)
    # ========================================================================

    # Temporal persistence from:
    # - Phase 49 temporal stability
    # - Phase 50 regression stability
    # - Phase 51 evidence stability
    # - Phase 52 stability projection

    temporal_persistence_components = [
        temporal_stability_index,
        cc_regression_stability,
        rag_evidence_stability,
        ier_stability_projection,
    ]

    temporal_persistence_index = _compute_mean(temporal_persistence_components)
    temporal_persistence_index = _clamp(temporal_persistence_index, 0.0, 1.0)

    # ========================================================================
    # STEP 12: COMPUTE ACTION ELIGIBILITY SCORE (AES)
    # ========================================================================

    # Weighted combination of all indices
    # Prioritize: Internal stability (25%), External alignment (25%),
    #             Trust confidence (20%), Conflict suppression (15%), Temporal persistence (15%)

    action_eligibility_score = (
        0.25 * internal_stability_index +
        0.25 * external_alignment_index +
        0.20 * trust_confidence_index +
        0.15 * conflict_suppression_index +
        0.15 * temporal_persistence_index
    )
    action_eligibility_score = _clamp(action_eligibility_score, 0.0, 1.0)

    # ========================================================================
    # STEP 13: CLASSIFY ELIGIBILITY BAND (PRIORITY-ORDERED, DETERMINISTIC)
    # ========================================================================

    # Priority-ordered classification with deterministic tie-breaking
    if (action_eligibility_score >= 0.70 and
        internal_stability_index >= 0.65 and
        trust_confidence_index >= 0.60 and
        conflict_suppression_index >= 0.70):
        eligibility_band = "ELIGIBLE"
    elif (action_eligibility_score >= 0.50 and
          internal_stability_index >= 0.45 and
          conflict_suppression_index >= 0.50):
        eligibility_band = "CONDITIONALLY_ELIGIBLE"
    elif (action_eligibility_score >= 0.30 or
          (internal_stability_index >= 0.30 and conflict_suppression_index >= 0.35)):
        eligibility_band = "NOT_ELIGIBLE"
    else:
        eligibility_band = "BLOCKED"

    # ========================================================================
    # STEP 14: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    tags = []

    # Internal stability tags
    if internal_stability_index >= 0.75:
        tags.append("internal_cognition_stable")
    elif internal_stability_index >= 0.50:
        tags.append("internal_cognition_moderate")
    elif internal_stability_index <= 0.35:
        tags.append("internal_cognition_unstable")

    # External alignment tags
    if external_alignment_index >= 0.75:
        tags.append("external_alignment_strong")
    elif external_alignment_index >= 0.50:
        tags.append("external_alignment_moderate")
    elif external_alignment_index <= 0.35:
        tags.append("external_alignment_weak")

    # Trust confidence tags
    if trust_confidence_index >= 0.75:
        tags.append("external_trust_high")
    elif trust_confidence_index >= 0.50:
        tags.append("external_trust_moderate")
    elif trust_confidence_index <= 0.35:
        tags.append("external_trust_low")

    # Conflict suppression tags
    if conflict_suppression_index >= 0.75:
        tags.append("conflict_minimal")
    elif conflict_suppression_index >= 0.50:
        tags.append("conflict_moderate")
    elif conflict_suppression_index <= 0.35:
        tags.append("conflict_significant")

    # Temporal persistence tags
    if temporal_persistence_index >= 0.75:
        tags.append("temporal_patterns_persistent")
    elif temporal_persistence_index <= 0.35:
        tags.append("temporal_patterns_volatile")

    # Eligibility score tags
    if action_eligibility_score >= 0.80:
        tags.append("eligibility_optimal")
    elif action_eligibility_score >= 0.60:
        tags.append("eligibility_adequate")
    elif action_eligibility_score >= 0.40:
        tags.append("eligibility_marginal")
    else:
        tags.append("eligibility_insufficient")

    # Band tags
    if eligibility_band == "ELIGIBLE":
        tags.append("action_boundary_clear")
    elif eligibility_band == "BLOCKED":
        tags.append("action_boundary_blocked")

    # Pattern tags based on combinations
    if (internal_stability_index >= 0.70 and
        external_alignment_index >= 0.70 and
        conflict_suppression_index >= 0.70):
        tags.append("cognitive_coherence_strong")

    if (trust_confidence_index >= 0.70 and
        external_alignment_index >= 0.70 and
        temporal_persistence_index >= 0.70):
        tags.append("reality_alignment_robust")

    if (internal_stability_index >= 0.65 and
        conflict_suppression_index >= 0.65 and
        temporal_persistence_index >= 0.65):
        tags.append("internal_state_actionable")

    if (conflict_suppression_index <= 0.35 or
        internal_stability_index <= 0.35):
        tags.append("action_readiness_compromised")

    if (cc_reversal_risk >= 0.60 or
        ertce_decay_risk >= 0.60):
        tags.append("predictive_instability_detected")

    if (ertce_override_pressure >= 0.60 and
        rag_conflict_index >= 0.50):
        tags.append("internal_external_tension")

    if (internal_stability_index >= 0.70 and
        external_alignment_index <= 0.40):
        tags.append("internal_strong_external_misaligned")

    if (external_alignment_index >= 0.70 and
        internal_stability_index <= 0.40):
        tags.append("external_aligned_internal_unstable")

    if (trust_confidence_index <= 0.35 and
        external_alignment_index <= 0.35):
        tags.append("external_reality_unreliable")

    if (action_eligibility_score >= 0.70 and
        eligibility_band == "ELIGIBLE"):
        tags.append("eligibility_consensus_achieved")

    if (action_eligibility_score < 0.40 and
        conflict_suppression_index < 0.40):
        tags.append("eligibility_critically_low")

    if available_signals >= 5:
        tags.append("data_coverage_complete")
    elif available_signals <= 3:
        tags.append("data_coverage_sparse")

    # Sort and deduplicate for determinism
    tags = sorted(set(tags))

    # ========================================================================
    # STEP 15: RETURN SNAPSHOT
    # ========================================================================

    return ActionEligibilitySnapshot(
        action_eligibility_score=action_eligibility_score,
        eligibility_band=eligibility_band,
        internal_stability_index=internal_stability_index,
        external_alignment_index=external_alignment_index,
        trust_confidence_index=trust_confidence_index,
        conflict_suppression_index=conflict_suppression_index,
        temporal_persistence_index=temporal_persistence_index,
        eligibility_tags=tags,
    )
