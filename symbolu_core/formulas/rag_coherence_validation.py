"""
RAG Coherence Validation Engine (RCVE) v1.0 - Phase 51

Deterministic, zero-LLM, observation-only validation engine that validates internal
cognition (Phases 35–50) against prefetched RAG evidence.

This engine validates:
- Evidence alignment (how well internal signals match RAG evidence)
- Evidence conflict (contradictions between internal cognition and RAG)
- Evidence stability (consistency of RAG evidence over time)
- Context relevance (how relevant RAG evidence is to current context)
- External support density (how much RAG evidence supports internal conclusions)

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - NO retrieval calls: Works only with prefetched RAG evidence
    - Metadata-only persona integration: NO tone or semantic changes
    - Diagnostics/UI only: Feeds coherence state, session summary, unified API, and DILchat badges
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Fully bounded: All outputs [0.0, 1.0]
    - Graceful degradation: Returns None if no RAG evidence available
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import math


@dataclass
class RAGCoherenceValidationSnapshot:
    """
    Immutable snapshot of RAG Coherence Validation Engine computation.

    This snapshot measures how well internal cognition (Phases 35-50) aligns
    with prefetched RAG evidence.

    Fields:
        evidence_alignment: [0.0, 1.0] - how well internal signals match RAG evidence
        evidence_conflict_index: [0.0, 1.0] - contradictions between cognition and RAG
        evidence_stability: [0.0, 1.0] - consistency of RAG evidence over time
        context_relevance_score: [0.0, 1.0] - relevance of RAG evidence to context
        external_support_density: [0.0, 1.0] - how much RAG evidence supports conclusions
        alignment_band: Classification: "HIGH_ALIGNMENT" | "MEDIUM_ALIGNMENT" | "LOW_ALIGNMENT" | "CONTRADICTION"
        diagnostic_tags: List of diagnostic pattern indicators
    """

    evidence_alignment: float = 0.0
    evidence_conflict_index: float = 0.0
    evidence_stability: float = 0.0
    context_relevance_score: float = 0.0
    external_support_density: float = 0.0
    alignment_band: str = "LOW_ALIGNMENT"
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


def compute_rag_coherence_validation(
    internal_signals: Dict[str, Any],
    rag_prefetch_data: Optional[Dict[str, Any]] = None,
) -> Optional[RAGCoherenceValidationSnapshot]:
    """
    Compute RAG Coherence Validation Engine (RCVE) v1.0.

    This function validates internal cognition (Phases 35-50) against
    prefetched RAG evidence.

    Args:
        internal_signals: Dict of inputs from phases 35–50 containing:
            - drift_magnitude: Phase 35 drift magnitude [0.0, 1.0]
            - identity_drift_anchoring: Phase 36 IDA [0.0, 1.0]
            - continuity_stability: Phase 37 CSS [0.0, 1.0]
            - forecast_strength: Phase 38 forecast strength [0.0, 1.0]
            - future_stability_envelope: Phase 39 FSE [0.0, 1.0]
            - scenario_alignment: Phase 42 scenario alignment [0.0, 1.0]
            - alignment_score: Phase 44 alignment score [0.0, 1.0]
            - convergence_index: Phase 46 convergence index [0.0, 1.0]
            - synthesis_integrity: Phase 47 synthesis integrity [0.0, 1.0]
            - macro_stability_index: Phase 48 macro stability [0.0, 1.0]
            - temporal_stability_index: Phase 49 temporal stability [0.0, 1.0]
            - internal_consistency_strength: Phase 50 ICS [0.0, 1.0]

        rag_prefetch_data: Pre-fetched RAG evidence (read-only) containing:
            - evidence_scores: List of evidence relevance scores [0.0, 1.0]
            - evidence_timestamps: List of evidence timestamps (for stability)
            - evidence_context_matches: List of context match scores [0.0, 1.0]
            - evidence_conflicts: List of conflict indicators (0.0 = no conflict, 1.0 = high conflict)
            - evidence_support_signals: Dict mapping signal names to support scores [0.0, 1.0]

    Returns:
        RAGCoherenceValidationSnapshot or None if no RAG evidence available

    Formula Design:
        - Evidence Alignment: How well internal signals match RAG evidence
        - Evidence Conflict Index: Contradictions between cognition and RAG
        - Evidence Stability: Consistency of RAG evidence over time
        - Context Relevance Score: Relevance of RAG evidence to context
        - External Support Density: How much RAG evidence supports conclusions

        Band Classification:
            * HIGH_ALIGNMENT: alignment >= 0.70 and conflict <= 0.30
            * MEDIUM_ALIGNMENT: alignment >= 0.50 and conflict <= 0.50
            * LOW_ALIGNMENT: alignment >= 0.30 or conflict <= 0.70
            * CONTRADICTION: alignment < 0.30 and conflict > 0.70

    Graceful Degradation:
        Returns None if no RAG evidence available.
    """
    # ========================================================================
    # STEP 1: VALIDATE RAG EVIDENCE AVAILABILITY
    # ========================================================================

    if rag_prefetch_data is None:
        return None

    # Check if we have any evidence at all
    evidence_scores = rag_prefetch_data.get("evidence_scores", [])
    if not evidence_scores or len(evidence_scores) == 0:
        return None

    # ========================================================================
    # STEP 2: EXTRACT INTERNAL SIGNALS
    # ========================================================================

    # Extract all internal cognition signals (Phases 35-50)
    drift_magnitude = internal_signals.get("drift_magnitude", 0.5)
    identity_drift_anchoring = internal_signals.get("identity_drift_anchoring", 0.5)
    continuity_stability = internal_signals.get("continuity_stability", 0.5)
    forecast_strength = internal_signals.get("forecast_strength", 0.5)
    future_stability_envelope = internal_signals.get("future_stability_envelope", 0.5)
    scenario_alignment = internal_signals.get("scenario_alignment", 0.5)
    alignment_score = internal_signals.get("alignment_score", 0.5)
    convergence_index = internal_signals.get("convergence_index", 0.5)
    synthesis_integrity = internal_signals.get("synthesis_integrity", 0.5)
    macro_stability_index = internal_signals.get("macro_stability_index", 0.5)
    temporal_stability_index = internal_signals.get("temporal_stability_index", 0.5)
    internal_consistency_strength = internal_signals.get("internal_consistency_strength", 0.5)

    # ========================================================================
    # STEP 3: EXTRACT RAG EVIDENCE DATA
    # ========================================================================

    evidence_scores = rag_prefetch_data.get("evidence_scores", [])
    evidence_timestamps = rag_prefetch_data.get("evidence_timestamps", [])
    evidence_context_matches = rag_prefetch_data.get("evidence_context_matches", [])
    evidence_conflicts = rag_prefetch_data.get("evidence_conflicts", [])
    evidence_support_signals = rag_prefetch_data.get("evidence_support_signals", {})

    # ========================================================================
    # STEP 4: COMPUTE EVIDENCE ALIGNMENT
    # ========================================================================

    # Evidence alignment measures how well internal signals match RAG evidence
    # We compute this by:
    # 1. Averaging evidence scores (how strong the evidence is)
    # 2. Comparing internal stability signals with evidence support

    avg_evidence_score = _compute_mean(evidence_scores)

    # Compute how well evidence supports our internal signals
    # Higher internal stability + higher evidence scores = higher alignment
    stability_signals = [
        identity_drift_anchoring,
        continuity_stability,
        forecast_strength,
        future_stability_envelope,
        macro_stability_index,
        temporal_stability_index,
        internal_consistency_strength,
    ]
    avg_internal_stability = _compute_mean(stability_signals)

    # Compute support from RAG for each signal
    support_scores = list(evidence_support_signals.values()) if evidence_support_signals else []
    avg_support = _compute_mean(support_scores) if support_scores else avg_evidence_score

    # Alignment is the product of evidence quality and internal-external agreement
    # High alignment = strong evidence + high internal stability + high support
    evidence_alignment = (0.4 * avg_evidence_score +
                          0.3 * avg_internal_stability +
                          0.3 * avg_support)
    evidence_alignment = _clamp(evidence_alignment, 0.0, 1.0)

    # ========================================================================
    # STEP 5: COMPUTE EVIDENCE CONFLICT INDEX
    # ========================================================================

    # Evidence conflict measures contradictions between cognition and RAG
    # Higher conflict = internal signals suggest one thing, RAG suggests another

    avg_conflict = _compute_mean(evidence_conflicts) if evidence_conflicts else 0.0

    # Also check for alignment-support mismatch
    # If internal signals are stable but RAG support is low, that's a conflict
    # If internal signals are unstable but RAG support is high, that's also a conflict
    alignment_mismatch = abs(avg_internal_stability - avg_support)

    evidence_conflict_index = (0.6 * avg_conflict +
                                0.4 * alignment_mismatch)
    evidence_conflict_index = _clamp(evidence_conflict_index, 0.0, 1.0)

    # ========================================================================
    # STEP 6: COMPUTE EVIDENCE STABILITY
    # ========================================================================

    # Evidence stability measures consistency of RAG evidence over time
    # Lower variance in evidence scores = higher stability

    if len(evidence_scores) >= 2:
        evidence_variance = _compute_variance(evidence_scores)
        # Normalize variance (typical variance for [0,1] bounded values is ~0.25)
        normalized_variance = min(evidence_variance / 0.25, 1.0)
        evidence_stability = 1.0 - normalized_variance
    else:
        # Single evidence point = assume moderate stability
        evidence_stability = 0.5

    evidence_stability = _clamp(evidence_stability, 0.0, 1.0)

    # ========================================================================
    # STEP 7: COMPUTE CONTEXT RELEVANCE SCORE
    # ========================================================================

    # Context relevance measures how relevant RAG evidence is to current context

    avg_context_match = _compute_mean(evidence_context_matches) if evidence_context_matches else avg_evidence_score

    # Higher context matches = higher relevance
    context_relevance_score = avg_context_match
    context_relevance_score = _clamp(context_relevance_score, 0.0, 1.0)

    # ========================================================================
    # STEP 8: COMPUTE EXTERNAL SUPPORT DENSITY
    # ========================================================================

    # External support density measures how much RAG evidence supports conclusions
    # This is based on:
    # 1. Number of evidence pieces
    # 2. Average support for internal signals
    # 3. Evidence quality

    num_evidence = len(evidence_scores)
    # Normalize evidence count (1-10 pieces is typical)
    evidence_density = min(num_evidence / 10.0, 1.0)

    external_support_density = (0.4 * evidence_density +
                                 0.4 * avg_support +
                                 0.2 * avg_evidence_score)
    external_support_density = _clamp(external_support_density, 0.0, 1.0)

    # ========================================================================
    # STEP 9: CLASSIFY ALIGNMENT BAND
    # ========================================================================

    if evidence_alignment >= 0.70 and evidence_conflict_index <= 0.30:
        alignment_band = "HIGH_ALIGNMENT"
    elif evidence_alignment >= 0.50 and evidence_conflict_index <= 0.50:
        alignment_band = "MEDIUM_ALIGNMENT"
    elif evidence_alignment >= 0.30 or evidence_conflict_index <= 0.70:
        alignment_band = "LOW_ALIGNMENT"
    else:
        alignment_band = "CONTRADICTION"

    # ========================================================================
    # STEP 10: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    tags = []

    # Alignment tags
    if evidence_alignment >= 0.75:
        tags.append("evidence_alignment_strong")
    elif evidence_alignment <= 0.35:
        tags.append("evidence_alignment_weak")
    else:
        tags.append("evidence_alignment_moderate")

    # Conflict tags
    if evidence_conflict_index >= 0.70:
        tags.append("high_conflict")
    elif evidence_conflict_index <= 0.30:
        tags.append("low_conflict")

    # Stability tags
    if evidence_stability >= 0.70:
        tags.append("evidence_stable")
    elif evidence_stability <= 0.35:
        tags.append("evidence_volatile")

    # Relevance tags
    if context_relevance_score >= 0.70:
        tags.append("context_highly_relevant")
    elif context_relevance_score <= 0.35:
        tags.append("context_weakly_relevant")

    # Support density tags
    if external_support_density >= 0.70:
        tags.append("strong_external_support")
    elif external_support_density <= 0.35:
        tags.append("weak_external_support")

    # Band tags
    if alignment_band == "HIGH_ALIGNMENT":
        tags.append("rag_validation_optimal")
    elif alignment_band == "CONTRADICTION":
        tags.append("rag_contradiction_detected")

    # Pattern tags based on combinations
    if (evidence_alignment >= 0.70 and
        evidence_stability >= 0.70 and
        evidence_conflict_index <= 0.30):
        tags.append("rag_consensus")

    if (evidence_conflict_index >= 0.60 and
        evidence_alignment <= 0.40):
        tags.append("rag_internal_divergence")

    if (external_support_density >= 0.70 and
        context_relevance_score >= 0.70):
        tags.append("rag_well_supported")

    if num_evidence >= 5:
        tags.append("data_rich_rag")
    elif num_evidence <= 2:
        tags.append("data_sparse_rag")

    if evidence_stability <= 0.40 and evidence_conflict_index >= 0.50:
        tags.append("rag_uncertain")

    # Sort and deduplicate for determinism
    tags = sorted(set(tags))

    # ========================================================================
    # STEP 11: RETURN SNAPSHOT
    # ========================================================================

    return RAGCoherenceValidationSnapshot(
        evidence_alignment=evidence_alignment,
        evidence_conflict_index=evidence_conflict_index,
        evidence_stability=evidence_stability,
        context_relevance_score=context_relevance_score,
        external_support_density=external_support_density,
        alignment_band=alignment_band,
        diagnostic_tags=tags,
    )
