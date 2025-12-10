"""
Resonance Weighting Function v1.0 - Phase 24

Deterministic, zero-LLM layer that computes adaptive weights for all major Symbol-U metrics
based on their "resonance quality."

This is an analytics-only weighting layer that says:
  "Given all these signals (coherence, formulas, resonance, mirror-time, drift…),
   which ones are currently most trustworthy / resonant?"

These weights are:
  • Exposed to Unified API and Unified Dashboard
  • Optionally surfaced as DILchat diagnostics
  • NOT used to change any v1/v2/v3/coherence_fused scores yet

CRITICAL:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
import math


@dataclass
class ResonanceWeightingSnapshot:
    """
    Immutable snapshot of resonance weighting computation.

    Fields:
        weights: Raw weights for each metric [0.0, 1.0]
        normalized_weights: Normalized weights summing to 1.0
        entropy_of_weights: Shannon entropy of normalized weights [0.0, 1.0]
        dominant_metrics: Top N metrics by normalized weight
        notes: Deterministic diagnostic tags
    """

    weights: Dict[str, float]
    normalized_weights: Dict[str, float]
    entropy_of_weights: float
    dominant_metrics: Dict[str, float]
    notes: list[str] = field(default_factory=list)


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


def _normalize_weights(raw_weights: Dict[str, float]) -> tuple[Dict[str, float], float]:
    """
    Normalize weights to sum to 1.0 and compute Shannon entropy.

    Args:
        raw_weights: Raw weight values (must be >= 0)

    Returns:
        tuple: (normalized_weights dict, entropy value [0.0, 1.0])
               Returns ({}, 0.0) if sum is zero or empty
    """
    if not raw_weights:
        return {}, 0.0

    # Clamp all weights to >= 0
    clamped = {k: max(0.0, v) for k, v in raw_weights.items()}

    total = sum(clamped.values())
    if total <= 0.0:
        return {}, 0.0

    # Normalize to sum to 1.0
    normalized = {k: v / total for k, v in clamped.items()}

    # Compute Shannon entropy: H = -Σ(p_i * log2(p_i))
    # Normalized to [0.0, 1.0] by dividing by log2(N)
    entropy_raw = 0.0
    n = len(normalized)
    if n > 1:
        for weight in normalized.values():
            if weight > 0.0:
                entropy_raw -= weight * math.log2(weight)
        # Normalize by max entropy (log2(N))
        max_entropy = math.log2(n)
        entropy = entropy_raw / max_entropy if max_entropy > 0 else 0.0
    else:
        # Single metric = zero entropy (fully focused)
        entropy = 0.0

    return normalized, _clamp(entropy, 0.0, 1.0)


def compute_resonance_weighting(
    *,
    coherence_v1: Optional[float] = None,
    coherence_v2: Optional[float] = None,
    coherence_v3: Optional[float] = None,
    coherence_fused: Optional[float] = None,
    coherence_v3_quality: Optional[float] = None,
    enhanced_smi: Optional[float] = None,
    vritti_momentum: Optional[float] = None,
    arc_tension_harmonizer: Optional[float] = None,
    resonance_index: Optional[float] = None,
    tension_index: Optional[float] = None,
    arc_alignment_index: Optional[float] = None,
    guna_resonance_index: Optional[float] = None,
    kosha_resonance_index: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
    semantic_integrity_score: Optional[float] = None,
    cognitive_drift_v3: Optional[float] = None,
    temporal_entropy_volatility: Optional[float] = None,
) -> Optional[ResonanceWeightingSnapshot]:
    """
    Compute resonance weighting for all major Symbol-U metrics.

    This function assigns "trust weights" to each metric based on their resonance quality:
      - Positive metrics (higher = better): coherence_fused, resonance_index, semantic_integrity, etc.
      - Risk metrics (lower = better): tension_index, drift_fusion_index, cognitive_drift_v3, etc.
        These are inverted (1.0 - value) to convert to "quality" signals.

    Args:
        coherence_v1: Coherence score v1 [0.0, 1.0]
        coherence_v2: Coherence score v2 [0.0, 1.0]
        coherence_v3: Coherence score v3 [0.0, 1.0]
        coherence_fused: Fused coherence score [0.0, 1.0]
        coherence_v3_quality: V3 quality metric [0.0, 1.0]
        enhanced_smi: Enhanced SMI [0.0, 1.0]
        vritti_momentum: Vritti Momentum [0.0, 1.0]
        arc_tension_harmonizer: Arc-Tension Harmonizer [0.0, 1.0]
        resonance_index: Resonance Index [0.0, 1.0]
        tension_index: Tension Index [0.0, 1.0] - risk metric
        arc_alignment_index: Arc Alignment Index [0.0, 1.0]
        guna_resonance_index: Guna Resonance Index [0.0, 1.0]
        kosha_resonance_index: Kosha Resonance Index [0.0, 1.0]
        drift_fusion_index: Drift Fusion Index [0.0, 1.0] - risk metric
        semantic_integrity_score: Semantic Integrity [0.0, 1.0]
        cognitive_drift_v3: Cognitive Drift v3 [0.0, 1.0] - risk metric
        temporal_entropy_volatility: Temporal Entropy Volatility [0.0, 1.0] - risk metric

    Returns:
        ResonanceWeightingSnapshot or None if insufficient data
    """
    raw_weights = {}
    notes = []

    # ====== POSITIVE-VALUE METRICS (higher = better resonance) ======

    # Coherence signals - prioritize fused > v2 > v3 (if quality ok)
    if coherence_fused is not None and coherence_fused >= 0.0:
        # Fused coherence is stability-weighted and most reliable
        raw_weights["coherence_fused"] = 0.8 * _clamp(coherence_fused)
        if coherence_fused >= 0.7:
            notes.append("coherence_fused_strong")
    elif coherence_v2 is not None and coherence_v2 >= 0.0:
        # V2 is formula-aware and reliable
        raw_weights["coherence_v2"] = 0.75 * _clamp(coherence_v2)
    elif coherence_v3 is not None and coherence_v3 >= 0.0:
        # V3 requires quality check
        quality = coherence_v3_quality if coherence_v3_quality is not None else 0.5
        if quality >= 0.6:
            raw_weights["coherence_v3"] = 0.7 * _clamp(coherence_v3)
        else:
            # Lower weight if quality is questionable
            raw_weights["coherence_v3"] = 0.4 * _clamp(coherence_v3)
            notes.append("coherence_v3_low_quality")

    # Fallback to v1 if no higher versions available
    if "coherence_fused" not in raw_weights and "coherence_v2" not in raw_weights and "coherence_v3" not in raw_weights:
        if coherence_v1 is not None and coherence_v1 >= 0.0:
            raw_weights["coherence_v1"] = 0.6 * _clamp(coherence_v1)

    # Enhanced SMI (authenticity/tension index)
    if enhanced_smi is not None and enhanced_smi >= 0.0:
        raw_weights["enhanced_smi"] = 0.7 * _clamp(enhanced_smi)
        if enhanced_smi >= 0.75:
            notes.append("enhanced_smi_strong")

    # Vritti Momentum (thought-pattern momentum)
    if vritti_momentum is not None and vritti_momentum >= 0.0:
        raw_weights["vritti_momentum"] = 0.65 * _clamp(vritti_momentum)

    # Arc-Tension Harmonizer (harmonic balance)
    if arc_tension_harmonizer is not None and arc_tension_harmonizer >= 0.0:
        raw_weights["arc_tension_harmonizer"] = 0.7 * _clamp(arc_tension_harmonizer)
        if arc_tension_harmonizer >= 0.7:
            notes.append("arc_tension_harmonized")

    # Resonance Index (formula-weighted stabilizing signal)
    if resonance_index is not None and resonance_index >= 0.0:
        raw_weights["resonance_index"] = 0.75 * _clamp(resonance_index)
        if resonance_index >= 0.7:
            notes.append("resonance_index_dominant")

    # Arc Alignment Index (temporal pattern alignment)
    if arc_alignment_index is not None and arc_alignment_index >= 0.0:
        raw_weights["arc_alignment_index"] = 0.7 * _clamp(arc_alignment_index)

    # Guna Resonance Index (Guna balance/distortion)
    if guna_resonance_index is not None and guna_resonance_index >= 0.0:
        raw_weights["guna_resonance_index"] = 0.65 * _clamp(guna_resonance_index)

    # Kosha Resonance Index (Kosha coherence)
    if kosha_resonance_index is not None and kosha_resonance_index >= 0.0:
        raw_weights["kosha_resonance_index"] = 0.65 * _clamp(kosha_resonance_index)

    # Semantic Integrity (semantic coherence/self-consistency)
    if semantic_integrity_score is not None and semantic_integrity_score >= 0.0:
        raw_weights["semantic_integrity"] = 0.75 * _clamp(semantic_integrity_score)
        if semantic_integrity_score >= 0.7:
            notes.append("semantic_integrity_dominant")

    # ====== INVERTED-RISK METRICS (lower = better, so invert to quality signals) ======

    # Tension Index (session tension - inverted)
    if tension_index is not None and tension_index >= 0.0:
        inverted = 1.0 - _clamp(tension_index)
        raw_weights["tension_inverse"] = 0.6 * inverted
        if tension_index >= 0.7:
            notes.append("high_tension_detected")

    # Drift Fusion Index (combined drift signal - inverted)
    if drift_fusion_index is not None and drift_fusion_index >= 0.0:
        inverted = 1.0 - _clamp(drift_fusion_index)
        raw_weights["drift_inverse"] = 0.7 * inverted
        if drift_fusion_index >= 0.6:
            notes.append("drift_risk_elevated")

    # Cognitive Drift v3 (semantic center-of-gravity drift - inverted)
    if cognitive_drift_v3 is not None and cognitive_drift_v3 >= 0.0:
        inverted = 1.0 - _clamp(cognitive_drift_v3)
        raw_weights["cognitive_stability"] = 0.7 * inverted
        if cognitive_drift_v3 >= 0.6:
            notes.append("cognitive_drift_warning")

    # Temporal Entropy Volatility (entropy turbulence - inverted)
    if temporal_entropy_volatility is not None and temporal_entropy_volatility >= 0.0:
        inverted = 1.0 - _clamp(temporal_entropy_volatility)
        raw_weights["entropy_stability"] = 0.6 * inverted
        if temporal_entropy_volatility >= 0.7:
            notes.append("entropy_volatility_high")

    # ====== VALIDATION & NORMALIZATION ======

    # If no usable metrics, return None
    if not raw_weights:
        return None

    # Normalize weights and compute entropy
    normalized_weights, entropy = _normalize_weights(raw_weights)

    if not normalized_weights:
        # Should not happen if raw_weights is non-empty, but safeguard
        return None

    # Identify dominant metrics (top 3 by normalized weight)
    sorted_metrics = sorted(normalized_weights.items(), key=lambda x: x[1], reverse=True)
    dominant_metrics = dict(sorted_metrics[:3])

    # Add entropy-related notes
    if entropy < 0.35:
        notes.append("narrow_weight_distribution")
        notes.append("focused_resonance")
    elif entropy < 0.70:
        notes.append("balanced_weight_distribution")
    else:
        notes.append("broad_weight_distribution")
        notes.append("diffuse_resonance")

    # Add dominant metric tags
    for metric_name, weight in dominant_metrics.items():
        if weight >= 0.25:  # Significant dominance threshold
            notes.append(f"{metric_name}_weighted")

    return ResonanceWeightingSnapshot(
        weights=raw_weights,
        normalized_weights=normalized_weights,
        entropy_of_weights=entropy,
        dominant_metrics=dominant_metrics,
        notes=sorted(set(notes)),  # Deduplicate and sort for determinism
    )
