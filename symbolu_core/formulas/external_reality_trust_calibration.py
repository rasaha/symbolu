"""
External Reality Trust Calibration Engine (ERTCE) v1.0 - Phase 53

Deterministic, zero-LLM, observation-only trust calibration engine that calibrates
how much trust should be assigned to external (RAG-derived) reality signals,
relative to internal cognition.

This engine does NOT validate facts, change predictions, or influence actions.
It answers only: "How trustworthy is the external reality signal right now?"

INPUTS (READ-ONLY):
- External Reality Inputs (Phase 51 — CRA)
- Internal–External Alignment (Phase 52)
- Internal Cognition Stability (Phases 47-50)

OUTPUTS (ALL ∈ [0.0, 1.0]):
- external_trust_score (ETS): Overall confidence in external reality
- internal_override_pressure (IOP): Degree internal cognition contradicts external signal
- external_signal_fragility (ESF): Sensitivity of external signal to perturbation
- alignment_resilience (AR): Stability of internal–external agreement over time
- trust_decay_risk (TDR): Likelihood trust degrades soon

BAND CLASSIFICATION (EXACTLY ONE):
- HIGH_EXTERNAL_TRUST
- CONDITIONAL_EXTERNAL_TRUST
- LOW_EXTERNAL_TRUST
- EXTERNAL_CONFLICT_ZONE

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - NO retrieval calls: Works only with existing Phase 51/52 outputs
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
import math


@dataclass
class ExternalRealityTrustSnapshot:
    """
    Immutable snapshot of External Reality Trust Calibration Engine computation.

    This snapshot measures how much trust should be assigned to external
    (RAG-derived) reality signals, relative to internal cognition.

    Fields:
        external_trust_score: [0.0, 1.0] - Overall confidence in external reality
        internal_override_pressure: [0.0, 1.0] - Degree internal cognition contradicts external signal
        external_signal_fragility: [0.0, 1.0] - Sensitivity of external signal to perturbation
        alignment_resilience: [0.0, 1.0] - Stability of internal–external agreement over time
        trust_decay_risk: [0.0, 1.0] - Likelihood trust degrades soon
        trust_band: Classification: "HIGH_EXTERNAL_TRUST" | "CONDITIONAL_EXTERNAL_TRUST" | "LOW_EXTERNAL_TRUST" | "EXTERNAL_CONFLICT_ZONE"
        diagnostic_tags: List of diagnostic pattern indicators
    """

    external_trust_score: float = 0.0
    internal_override_pressure: float = 0.0
    external_signal_fragility: float = 0.0
    alignment_resilience: float = 0.0
    trust_decay_risk: float = 0.0
    trust_band: str = "LOW_EXTERNAL_TRUST"
    diagnostic_tags: List[str] = field(default_factory=list)


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


def _compute_variance(values: List[float]) -> float:
    """
    Compute variance of a list of values.

    Args:
        values: List of float values

    Returns:
        float: Variance [0.0, ∞)
    """
    if not values:
        return 0.0

    # Filter out None values
    valid_values = [v for v in values if v is not None]
    if not valid_values or len(valid_values) < 2:
        return 0.0

    mean = _compute_mean(valid_values)
    variance = sum((x - mean) ** 2 for x in valid_values) / len(valid_values)

    return variance


def _compute_std_dev(values: List[float]) -> float:
    """
    Compute standard deviation of a list of values.

    Args:
        values: List of float values

    Returns:
        float: Standard deviation [0.0, ∞)
    """
    variance = _compute_variance(values)
    return math.sqrt(variance)


def compute_external_reality_trust_calibration(
    *,
    external_reality_signals: Dict[str, float],
    internal_external_alignment: Dict[str, float],
    internal_stability_signals: Dict[str, float],
) -> Optional[ExternalRealityTrustSnapshot]:
    """
    Compute External Reality Trust Calibration Engine (ERTCE) v1.0.

    This function calibrates how much trust should be assigned to external
    (RAG-derived) reality signals, relative to internal cognition.

    Args:
        external_reality_signals: Dict from Phase 51 (RAG Coherence Validation) containing:
            - evidence_alignment: [0.0, 1.0] - How well internal signals match RAG evidence
            - evidence_conflict_index: [0.0, 1.0] - Contradictions between cognition and RAG
            - evidence_stability: [0.0, 1.0] - Consistency of RAG evidence over time
            - context_relevance_score: [0.0, 1.0] - Relevance of RAG evidence to context
            - external_support_density: [0.0, 1.0] - How much RAG evidence supports conclusions

        internal_external_alignment: Dict from Phase 52 (IER-CVE) containing:
            - internal_consistency_index: [0.0, 1.0] - Agreement across internal cognition layers
            - external_evidence_consistency_index: [0.0, 1.0] - External RAG validation strength
            - alignment_index: [0.0, 1.0] - Agreement between internal and external reality
            - divergence_index: [0.0, 1.0] - Disagreement between internal and external
            - evidence_conflict_index: [0.0, 1.0] - Contradictions between internal and external
            - stability_projection_index: [0.0, 1.0] - Expected future stability of alignment

        internal_stability_signals: Dict from Phases 47-50 containing:
            - synthesis_integrity: Phase 47 synthesis integrity [0.0, 1.0]
            - macro_stability_index: Phase 48 macro stability [0.0, 1.0]
            - temporal_stability_index: Phase 49 temporal stability [0.0, 1.0]
            - internal_consistency_strength: Phase 50 ICS [0.0, 1.0]

    Returns:
        ExternalRealityTrustSnapshot or None if insufficient data available

    Formula Design:
        - External Trust Score (ETS): Weighted combination of external evidence quality,
          alignment with internal cognition, and stability
        - Internal Override Pressure (IOP): Degree to which internal cognition contradicts
          external signal (high divergence + high internal consistency)
        - External Signal Fragility (ESF): Sensitivity of external signal to perturbation
          (inverse of evidence stability)
        - Alignment Resilience (AR): Stability of internal–external agreement over time
        - Trust Decay Risk (TDR): Likelihood trust degrades soon (high fragility +
          low resilience + high conflict)

        Band Classification (priority-ordered, deterministic):
            * HIGH_EXTERNAL_TRUST: ETS >= 0.70 and IOP <= 0.30 and ESF <= 0.30
            * CONDITIONAL_EXTERNAL_TRUST: ETS >= 0.50 and IOP <= 0.50 and ESF <= 0.50
            * LOW_EXTERNAL_TRUST: ETS >= 0.30 or (IOP <= 0.70 and ESF <= 0.70)
            * EXTERNAL_CONFLICT_ZONE: otherwise (ETS < 0.30 or IOP > 0.70 or ESF > 0.70)

    Graceful Degradation:
        Returns None if:
        - External reality signals (Phase 51) unavailable
        - Internal-external alignment (Phase 52) unavailable
        - Internal stability signals (Phases 47-50) unavailable
    """
    # ========================================================================
    # STEP 1: VALIDATE INPUT AVAILABILITY
    # ========================================================================

    # Check if we have external reality signals (Phase 51)
    if not external_reality_signals:
        return None

    # Check if we have internal-external alignment (Phase 52)
    if not internal_external_alignment:
        return None

    # Check if we have internal stability signals (Phases 47-50)
    if not internal_stability_signals:
        return None

    # ========================================================================
    # STEP 2: EXTRACT EXTERNAL REALITY SIGNALS (PHASE 51)
    # ========================================================================

    evidence_alignment = external_reality_signals.get("evidence_alignment", 0.5)
    evidence_conflict_index_rag = external_reality_signals.get("evidence_conflict_index", 0.5)
    evidence_stability = external_reality_signals.get("evidence_stability", 0.5)
    context_relevance_score = external_reality_signals.get("context_relevance_score", 0.5)
    external_support_density = external_reality_signals.get("external_support_density", 0.5)

    # ========================================================================
    # STEP 3: EXTRACT INTERNAL-EXTERNAL ALIGNMENT (PHASE 52)
    # ========================================================================

    internal_consistency_index = internal_external_alignment.get("internal_consistency_index", 0.5)
    external_evidence_consistency_index = internal_external_alignment.get("external_evidence_consistency_index", 0.5)
    alignment_index = internal_external_alignment.get("alignment_index", 0.5)
    divergence_index = internal_external_alignment.get("divergence_index", 0.5)
    evidence_conflict_index = internal_external_alignment.get("evidence_conflict_index", 0.5)
    stability_projection_index = internal_external_alignment.get("stability_projection_index", 0.5)

    # ========================================================================
    # STEP 4: EXTRACT INTERNAL STABILITY SIGNALS (PHASES 47-50)
    # ========================================================================

    synthesis_integrity = internal_stability_signals.get("synthesis_integrity", 0.5)
    macro_stability_index = internal_stability_signals.get("macro_stability_index", 0.5)
    temporal_stability_index = internal_stability_signals.get("temporal_stability_index", 0.5)
    internal_consistency_strength = internal_stability_signals.get("internal_consistency_strength", 0.5)

    # ========================================================================
    # STEP 5: COMPUTE EXTERNAL TRUST SCORE (ETS)
    # ========================================================================

    # External trust score measures overall confidence in external reality
    # Weighted combination of:
    # 1. External evidence quality (alignment, support, relevance)
    # 2. Alignment with internal cognition
    # 3. Stability (evidence + projection)

    external_evidence_quality = _compute_mean([
        evidence_alignment,
        external_support_density,
        context_relevance_score,
        external_evidence_consistency_index,
    ])

    stability_factor = _compute_mean([
        evidence_stability,
        stability_projection_index,
    ])

    # High trust = high evidence quality + high alignment + high stability
    external_trust_score = (
        0.40 * external_evidence_quality +
        0.35 * alignment_index +
        0.25 * stability_factor
    )
    external_trust_score = _clamp(external_trust_score, 0.0, 1.0)

    # ========================================================================
    # STEP 6: COMPUTE INTERNAL OVERRIDE PRESSURE (IOP)
    # ========================================================================

    # Internal override pressure measures degree internal cognition contradicts external signal
    # High pressure = high divergence + high internal consistency + high conflict

    internal_strength = _compute_mean([
        internal_consistency_index,
        internal_consistency_strength,
        synthesis_integrity,
        macro_stability_index,
    ])

    # High override pressure = strong internal cognition contradicts external signal
    internal_override_pressure = (
        0.40 * divergence_index +
        0.35 * internal_strength +
        0.25 * evidence_conflict_index
    )
    internal_override_pressure = _clamp(internal_override_pressure, 0.0, 1.0)

    # ========================================================================
    # STEP 7: COMPUTE EXTERNAL SIGNAL FRAGILITY (ESF)
    # ========================================================================

    # External signal fragility measures sensitivity of external signal to perturbation
    # High fragility = low stability + low support + high conflict

    # Fragility factors (inverted where needed)
    fragility_components = [
        1.0 - evidence_stability,  # Unstable evidence = fragile
        1.0 - external_support_density,  # Low support = fragile
        evidence_conflict_index_rag,  # High conflict = fragile
        1.0 - context_relevance_score,  # Low relevance = fragile
    ]

    external_signal_fragility = _compute_mean(fragility_components)
    external_signal_fragility = _clamp(external_signal_fragility, 0.0, 1.0)

    # ========================================================================
    # STEP 8: COMPUTE ALIGNMENT RESILIENCE (AR)
    # ========================================================================

    # Alignment resilience measures stability of internal–external agreement over time
    # High resilience = high alignment + high stability projection + low conflict

    alignment_resilience = (
        0.40 * alignment_index +
        0.35 * stability_projection_index +
        0.25 * (1.0 - evidence_conflict_index)
    )
    alignment_resilience = _clamp(alignment_resilience, 0.0, 1.0)

    # ========================================================================
    # STEP 9: COMPUTE TRUST DECAY RISK (TDR)
    # ========================================================================

    # Trust decay risk measures likelihood trust degrades soon
    # High risk = high fragility + low resilience + high conflict + low stability

    trust_decay_risk = (
        0.30 * external_signal_fragility +
        0.30 * (1.0 - alignment_resilience) +
        0.25 * evidence_conflict_index +
        0.15 * (1.0 - stability_factor)
    )
    trust_decay_risk = _clamp(trust_decay_risk, 0.0, 1.0)

    # ========================================================================
    # STEP 10: CLASSIFY TRUST BAND (PRIORITY-ORDERED, DETERMINISTIC)
    # ========================================================================

    # Priority-ordered classification with deterministic tie-breaking
    if (external_trust_score >= 0.70 and
        internal_override_pressure <= 0.30 and
        external_signal_fragility <= 0.30):
        trust_band = "HIGH_EXTERNAL_TRUST"
    elif (external_trust_score >= 0.50 and
          internal_override_pressure <= 0.50 and
          external_signal_fragility <= 0.50):
        trust_band = "CONDITIONAL_EXTERNAL_TRUST"
    elif (external_trust_score >= 0.30 or
          (internal_override_pressure <= 0.70 and external_signal_fragility <= 0.70)):
        trust_band = "LOW_EXTERNAL_TRUST"
    else:
        trust_band = "EXTERNAL_CONFLICT_ZONE"

    # ========================================================================
    # STEP 11: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    tags = []

    # Trust score tags
    if external_trust_score >= 0.75:
        tags.append("external_trust_high")
    elif external_trust_score >= 0.50:
        tags.append("external_trust_moderate")
    elif external_trust_score >= 0.30:
        tags.append("external_trust_low")
    else:
        tags.append("external_trust_minimal")

    # Override pressure tags
    if internal_override_pressure >= 0.70:
        tags.append("internal_model_dominant")
    elif internal_override_pressure <= 0.30:
        tags.append("external_model_dominant")

    # Fragility tags
    if external_signal_fragility >= 0.70:
        tags.append("evidence_fragility_detected")
    elif external_signal_fragility <= 0.30:
        tags.append("evidence_fragility_low")

    # Resilience tags
    if alignment_resilience >= 0.70:
        tags.append("external_alignment_stable")
    elif alignment_resilience <= 0.30:
        tags.append("external_alignment_unstable")

    # Decay risk tags
    if trust_decay_risk >= 0.70:
        tags.append("trust_decay_projected")
    elif trust_decay_risk <= 0.30:
        tags.append("trust_decay_unlikely")

    # Band tags
    if trust_band == "HIGH_EXTERNAL_TRUST":
        tags.append("ertce_optimal")
    elif trust_band == "EXTERNAL_CONFLICT_ZONE":
        tags.append("ertce_conflict_zone")

    # Pattern tags based on combinations
    if (external_trust_score >= 0.70 and
        alignment_resilience >= 0.70 and
        trust_decay_risk <= 0.30):
        tags.append("external_reality_reliable")

    if (internal_override_pressure >= 0.70 and
        external_trust_score <= 0.40):
        tags.append("internal_cognition_preferred")

    if (evidence_conflict_index >= 0.60 and
        divergence_index >= 0.60):
        tags.append("rag_source_divergence")

    if (external_signal_fragility >= 0.60 and
        trust_decay_risk >= 0.60):
        tags.append("external_signal_unreliable")

    if (alignment_index >= 0.70 and
        stability_projection_index >= 0.70 and
        external_trust_score >= 0.70):
        tags.append("reality_consensus_strong")

    if (internal_consistency_index >= 0.70 and
        external_evidence_consistency_index <= 0.40):
        tags.append("internal_strong_external_weak")

    if (internal_consistency_index <= 0.40 and
        external_evidence_consistency_index >= 0.70):
        tags.append("internal_weak_external_strong")

    if (evidence_stability >= 0.70 and
        external_support_density >= 0.70):
        tags.append("rag_evidence_robust")

    if (evidence_stability <= 0.35 or
        external_support_density <= 0.35):
        tags.append("rag_evidence_sparse")

    if (divergence_index >= 0.70):
        tags.append("high_internal_external_divergence")

    # Sort and deduplicate for determinism
    tags = sorted(set(tags))

    # ========================================================================
    # STEP 12: RETURN SNAPSHOT
    # ========================================================================

    return ExternalRealityTrustSnapshot(
        external_trust_score=external_trust_score,
        internal_override_pressure=internal_override_pressure,
        external_signal_fragility=external_signal_fragility,
        alignment_resilience=alignment_resilience,
        trust_decay_risk=trust_decay_risk,
        trust_band=trust_band,
        diagnostic_tags=tags,
    )
