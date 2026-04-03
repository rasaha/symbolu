"""
Internal–External Reality Cross-Verification Engine (IER-CVE) v1.0 - Phase 52

Deterministic, zero-LLM, observation-only cross-verification engine that validates
internal cognitive predictions (Phases 35–51) against external RAG coherence validation
(Phase 51) and produces a unified Internal–External Reality Alignment Index (IERAI).

Phase 52 is the final internal validation gate before Symbol-U may rely on external
knowledge grounding.

This engine cross-verifies:
- Internal consistency (how well internal cognition layers agree)
- External evidence consistency (how well RAG evidence supports internal cognition)
- Alignment index (agreement between internal and external reality)
- Divergence index (disagreement between internal and external)
- Evidence conflict index (contradictions between internal and external)
- Stability projection (expected future stability of alignment)

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
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
class InternalExternalRealityCVESnapshot:
    """
    Immutable snapshot of Internal–External Reality Cross-Verification Engine computation.

    This snapshot measures how well internal cognitive predictions (Phases 35-51) align
    with external RAG coherence validation (Phase 51).

    Fields:
        internal_consistency_index: [0.0, 1.0] - agreement across internal cognition layers
        external_evidence_consistency_index: [0.0, 1.0] - external RAG validation strength
        alignment_index: [0.0, 1.0] - agreement between internal and external reality
        divergence_index: [0.0, 1.0] - disagreement between internal and external
        evidence_conflict_index: [0.0, 1.0] - contradictions between internal and external
        stability_projection_index: [0.0, 1.0] - expected future stability of alignment
        band: Classification: "high_alignment" | "medium_alignment" | "low_alignment" | "conflict"
        diagnostic_tags: List of diagnostic pattern indicators
    """

    internal_consistency_index: float = 0.0
    external_evidence_consistency_index: float = 0.0
    alignment_index: float = 0.0
    divergence_index: float = 0.0
    evidence_conflict_index: float = 0.0
    stability_projection_index: float = 0.0
    band: str = "low_alignment"
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


def compute_internal_external_reality_cve(
    *,
    internal_signals: Dict[str, float],
    external_rag_validation: Dict[str, float]
) -> Optional[InternalExternalRealityCVESnapshot]:
    """
    Compute Internal–External Reality Cross-Verification Engine (IER-CVE) v1.0.

    This function cross-verifies internal cognitive predictions (Phases 35-51) against
    external RAG coherence validation (Phase 51).

    Args:
        internal_signals: Dict of inputs from phases 35–51 containing:
            - drift_magnitude: Phase 35 drift magnitude [0.0, 1.0]
            - identity_drift_anchoring: Phase 36 IDA [0.0, 1.0]
            - continuity_stability: Phase 37 CSS [0.0, 1.0]
            - forecast_strength: Phase 38 forecast strength [0.0, 1.0]
            - future_stability_envelope: Phase 39 FSE [0.0, 1.0]
            - resonance_alignment_index: Phase 40 RAI [0.0, 1.0]
            - scenario_alignment: Phase 42 scenario alignment [0.0, 1.0]
            - alignment_score: Phase 44 alignment score [0.0, 1.0]
            - convergence_index: Phase 46 convergence index [0.0, 1.0]
            - synthesis_integrity: Phase 47 synthesis integrity [0.0, 1.0]
            - macro_stability_index: Phase 48 macro stability [0.0, 1.0]
            - temporal_stability_index: Phase 49 temporal stability [0.0, 1.0]
            - internal_consistency_strength: Phase 50 ICS [0.0, 1.0]

        external_rag_validation: Dict from Phase 51 RAG validation containing:
            - evidence_alignment: Phase 51 evidence alignment [0.0, 1.0]
            - evidence_conflict_index: Phase 51 evidence conflict [0.0, 1.0]
            - evidence_stability: Phase 51 evidence stability [0.0, 1.0]
            - context_relevance_score: Phase 51 context relevance [0.0, 1.0]
            - external_support_density: Phase 51 external support [0.0, 1.0]

    Returns:
        InternalExternalRealityCVESnapshot or None if insufficient data available

    Formula Design:
        - Internal Consistency Index: Agreement across internal cognition layers
        - External Evidence Consistency Index: External RAG validation strength
        - Alignment Index: 1 - abs(internal - external)
        - Divergence Index: 1 - alignment_index
        - Evidence Conflict Index: abs(internal - external)
        - Stability Projection Index: Expected future stability of alignment

        Band Classification:
            * high_alignment: alignment >= 0.70
            * medium_alignment: alignment >= 0.40
            * low_alignment: alignment >= 0.20
            * conflict: alignment < 0.20

    Graceful Degradation:
        Returns None if:
        - Fewer than 3 internal phase signals available
        - External RAG validation missing or insufficient
    """
    # ========================================================================
    # STEP 1: VALIDATE INPUT AVAILABILITY
    # ========================================================================

    # Check if we have sufficient internal signals (at least 3 phases)
    if not internal_signals or len(internal_signals) < 3:
        return None

    # Check if we have external RAG validation
    if not external_rag_validation:
        return None

    # ========================================================================
    # STEP 2: EXTRACT INTERNAL SIGNALS
    # ========================================================================

    # Extract all internal cognition signals (Phases 35-50)
    internal_values = []

    # Phase 35: Predictive Persona Drift
    drift_magnitude = internal_signals.get("drift_magnitude")
    if drift_magnitude is not None:
        # Invert drift (lower drift = higher stability)
        internal_values.append(1.0 - drift_magnitude)

    # Phase 36: Identity Resonance Memory
    identity_drift_anchoring = internal_signals.get("identity_drift_anchoring")
    if identity_drift_anchoring is not None:
        internal_values.append(identity_drift_anchoring)

    # Phase 37: Adaptive Continuity Engine
    continuity_stability = internal_signals.get("continuity_stability")
    if continuity_stability is not None:
        internal_values.append(continuity_stability)

    # Phase 38: Temporal Coherence Forecasting
    forecast_strength = internal_signals.get("forecast_strength")
    if forecast_strength is not None:
        internal_values.append(forecast_strength)

    # Phase 39: Multi-Horizon Temporal Forecasting
    future_stability_envelope = internal_signals.get("future_stability_envelope")
    if future_stability_envelope is not None:
        internal_values.append(future_stability_envelope)

    # Phase 40: Cross-Horizon Resonance Alignment
    resonance_alignment_index = internal_signals.get("resonance_alignment_index")
    if resonance_alignment_index is not None:
        internal_values.append(resonance_alignment_index)

    # Phase 42: Scenario Fusion Engine
    scenario_alignment = internal_signals.get("scenario_alignment")
    if scenario_alignment is not None:
        internal_values.append(scenario_alignment)

    # Phase 44: Coherence–Scenario Alignment
    alignment_score = internal_signals.get("alignment_score")
    if alignment_score is not None:
        internal_values.append(alignment_score)

    # Phase 46: Trajectory Field Convergence
    convergence_index = internal_signals.get("convergence_index")
    if convergence_index is not None:
        internal_values.append(convergence_index)

    # Phase 47: Unified Trajectory–Scenario Synthesis
    synthesis_integrity = internal_signals.get("synthesis_integrity")
    if synthesis_integrity is not None:
        internal_values.append(synthesis_integrity)

    # Phase 48: Macro-Stability Regulator
    macro_stability_index = internal_signals.get("macro_stability_index")
    if macro_stability_index is not None:
        internal_values.append(macro_stability_index)

    # Phase 49: Unified Cross-Phase Temporal Stability
    temporal_stability_index = internal_signals.get("temporal_stability_index")
    if temporal_stability_index is not None:
        internal_values.append(temporal_stability_index)

    # Phase 50: Cognitive Consistency Regression
    internal_consistency_strength = internal_signals.get("internal_consistency_strength")
    if internal_consistency_strength is not None:
        internal_values.append(internal_consistency_strength)

    # Require at least 3 internal signals
    if len(internal_values) < 3:
        return None

    # ========================================================================
    # STEP 3: EXTRACT EXTERNAL RAG VALIDATION SIGNALS
    # ========================================================================

    # Extract Phase 51 RAG validation signals
    evidence_alignment = external_rag_validation.get("evidence_alignment", 0.5)
    evidence_conflict_index_rag = external_rag_validation.get("evidence_conflict_index", 0.5)
    evidence_stability = external_rag_validation.get("evidence_stability", 0.5)
    context_relevance_score = external_rag_validation.get("context_relevance_score", 0.5)
    external_support_density = external_rag_validation.get("external_support_density", 0.5)

    # ========================================================================
    # STEP 4: COMPUTE INTERNAL CONSISTENCY INDEX
    # ========================================================================

    # Internal consistency measures agreement across internal cognition layers
    # Higher consistency = all internal phases agree on stability/alignment

    # Compute mean and variance of internal signals
    internal_mean = _compute_mean(internal_values)
    internal_variance = _compute_variance(internal_values)

    # Normalize variance (typical variance for [0,1] bounded values is ~0.25)
    normalized_internal_variance = min(internal_variance / 0.25, 1.0)

    # Internal consistency = high mean + low variance
    internal_consistency_index = (0.7 * internal_mean +
                                   0.3 * (1.0 - normalized_internal_variance))
    internal_consistency_index = _clamp(internal_consistency_index, 0.0, 1.0)

    # ========================================================================
    # STEP 5: COMPUTE EXTERNAL EVIDENCE CONSISTENCY INDEX
    # ========================================================================

    # External evidence consistency measures RAG validation strength
    # Higher consistency = strong, stable, relevant RAG evidence

    external_signals = [
        evidence_alignment,
        1.0 - evidence_conflict_index_rag,  # Invert conflict
        evidence_stability,
        context_relevance_score,
        external_support_density,
    ]

    external_evidence_consistency_index = _compute_mean(external_signals)
    external_evidence_consistency_index = _clamp(external_evidence_consistency_index, 0.0, 1.0)

    # ========================================================================
    # STEP 6: COMPUTE ALIGNMENT INDEX
    # ========================================================================

    # Alignment index measures agreement between internal and external reality
    # alignment = 1 - abs(internal - external)

    alignment_index = 1.0 - abs(internal_consistency_index - external_evidence_consistency_index)
    alignment_index = _clamp(alignment_index, 0.0, 1.0)

    # ========================================================================
    # STEP 7: COMPUTE DIVERGENCE INDEX
    # ========================================================================

    # Divergence index is the complement of alignment
    divergence_index = 1.0 - alignment_index
    divergence_index = _clamp(divergence_index, 0.0, 1.0)

    # ========================================================================
    # STEP 8: COMPUTE EVIDENCE CONFLICT INDEX
    # ========================================================================

    # Evidence conflict measures contradictions between internal and external
    # Incorporates both:
    # 1. Absolute difference between internal and external consistency
    # 2. RAG evidence conflict index

    internal_external_gap = abs(internal_consistency_index - external_evidence_consistency_index)

    evidence_conflict_index = (0.6 * internal_external_gap +
                                0.4 * evidence_conflict_index_rag)
    evidence_conflict_index = _clamp(evidence_conflict_index, 0.0, 1.0)

    # ========================================================================
    # STEP 9: COMPUTE STABILITY PROJECTION INDEX
    # ========================================================================

    # Stability projection predicts future stability of alignment
    # Higher stability = low variance + high alignment + stable evidence

    # Combine:
    # - Internal variance (lower = more stable)
    # - Alignment index (higher = more stable)
    # - Evidence stability (higher = more stable)

    stability_projection_index = (0.4 * (1.0 - normalized_internal_variance) +
                                   0.4 * alignment_index +
                                   0.2 * evidence_stability)
    stability_projection_index = _clamp(stability_projection_index, 0.0, 1.0)

    # ========================================================================
    # STEP 10: CLASSIFY ALIGNMENT BAND
    # ========================================================================

    if alignment_index >= 0.70:
        band = "high_alignment"
    elif alignment_index >= 0.40:
        band = "medium_alignment"
    elif alignment_index >= 0.20:
        band = "low_alignment"
    else:
        band = "conflict"

    # ========================================================================
    # STEP 11: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    tags = []

    # Internal consistency tags
    if internal_consistency_index >= 0.75:
        tags.append("internal_highly_consistent")
    elif internal_consistency_index <= 0.35:
        tags.append("internal_fragmented")
    else:
        tags.append("internal_moderately_consistent")

    # External consistency tags
    if external_evidence_consistency_index >= 0.75:
        tags.append("external_strongly_supported")
    elif external_evidence_consistency_index <= 0.35:
        tags.append("external_weakly_supported")

    # Alignment tags
    if alignment_index >= 0.80:
        tags.append("reality_consensus")
    elif alignment_index <= 0.30:
        tags.append("reality_divergence")

    # Conflict tags
    if evidence_conflict_index >= 0.70:
        tags.append("high_internal_external_conflict")
    elif evidence_conflict_index <= 0.30:
        tags.append("low_internal_external_conflict")

    # Stability projection tags
    if stability_projection_index >= 0.70:
        tags.append("stable_alignment_expected")
    elif stability_projection_index <= 0.35:
        tags.append("volatile_alignment_expected")

    # Band tags
    if band == "high_alignment":
        tags.append("ier_cve_optimal")
    elif band == "conflict":
        tags.append("ier_cve_conflict_detected")

    # Pattern tags based on combinations
    if (alignment_index >= 0.70 and
        stability_projection_index >= 0.70 and
        evidence_conflict_index <= 0.30):
        tags.append("reality_harmony")

    if (evidence_conflict_index >= 0.60 and
        alignment_index <= 0.40):
        tags.append("reality_contradiction")

    if (internal_consistency_index >= 0.70 and
        external_evidence_consistency_index >= 0.70 and
        alignment_index >= 0.70):
        tags.append("full_reality_alignment")

    if (internal_consistency_index >= 0.70 and
        external_evidence_consistency_index <= 0.40):
        tags.append("internal_strong_external_weak")

    if (internal_consistency_index <= 0.40 and
        external_evidence_consistency_index >= 0.70):
        tags.append("internal_weak_external_strong")

    if (normalized_internal_variance >= 0.60):
        tags.append("high_internal_variance")

    if (divergence_index >= 0.60):
        tags.append("high_divergence")

    # Sort and deduplicate for determinism
    tags = sorted(set(tags))

    # ========================================================================
    # STEP 12: RETURN SNAPSHOT
    # ========================================================================

    return InternalExternalRealityCVESnapshot(
        internal_consistency_index=internal_consistency_index,
        external_evidence_consistency_index=external_evidence_consistency_index,
        alignment_index=alignment_index,
        divergence_index=divergence_index,
        evidence_conflict_index=evidence_conflict_index,
        stability_projection_index=stability_projection_index,
        band=band,
        diagnostic_tags=tags,
    )
