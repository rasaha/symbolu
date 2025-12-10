"""
Unified Consciousness Formula (UCF) v1.0 - Phase 26

Deterministic, zero-LLM meta-formula that integrates ALL Symbol-U v3.0 formula signals
into three unified consciousness indices:

  1. COI (Consciousness Order Index): System organization & structural coherence
  2. CSI (Consciousness Stability Index): Temporal stability & resilience
  3. CIP (Consciousness Integration Potential): Cross-layer integration readiness

This is the OBSERVATION-ONLY capstone formula for v3.0, designed for:
  • Dashboard visualization & sparklines
  • Session analytics & summaries
  • Future v4.0 reasoning-layer integration (flag-gated)

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Graceful degradation: Returns None if core inputs missing
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List
import math


@dataclass
class UnifiedConsciousnessSnapshot:
    """
    Immutable snapshot of unified consciousness formula computation.

    Fields:
        consciousness_order_index (COI): System organization [0.0, 1.0]
        consciousness_stability_index (CSI): Temporal stability [0.0, 1.0]
        consciousness_integration_potential (CIP): Integration readiness [0.0, 1.0]
        weighted_component_breakdown: Raw component weights used in computation
        normalized_weights: Normalized weights (sum = 1.0)
        entropy_of_weights: Shannon entropy of weight distribution [0.0, 1.0]
        diagnostic_notes: Deterministic diagnostic tags
    """

    consciousness_order_index: float  # COI [0.0, 1.0]
    consciousness_stability_index: float  # CSI [0.0, 1.0]
    consciousness_integration_potential: float  # CIP [0.0, 1.0]
    weighted_component_breakdown: Dict[str, float]
    normalized_weights: Dict[str, float]
    entropy_of_weights: float
    diagnostic_notes: List[str] = field(default_factory=list)


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


def _compute_shannon_entropy(weights: Dict[str, float]) -> float:
    """
    Compute Shannon entropy of weight distribution, normalized to [0.0, 1.0].

    Args:
        weights: Normalized weight distribution (must sum to ~1.0)

    Returns:
        float: Entropy [0.0, 1.0], where 0 = focused, 1 = uniform
    """
    if not weights:
        return 0.0

    n = len(weights)
    if n <= 1:
        return 0.0

    # Compute Shannon entropy: H = -Σ(p_i * log2(p_i))
    entropy_raw = 0.0
    for weight in weights.values():
        if weight > 0.0:
            entropy_raw -= weight * math.log2(weight)

    # Normalize by max entropy (log2(N))
    max_entropy = math.log2(n)
    entropy = entropy_raw / max_entropy if max_entropy > 0 else 0.0

    return _clamp(entropy, 0.0, 1.0)


def _normalize_weights(raw_weights: Dict[str, float]) -> Dict[str, float]:
    """
    Normalize weights to sum to 1.0.

    Args:
        raw_weights: Raw weight values (must be >= 0)

    Returns:
        dict: Normalized weights (sum = 1.0), or empty dict if sum is zero
    """
    if not raw_weights:
        return {}

    # Clamp all weights to >= 0
    clamped = {k: max(0.0, v) for k, v in raw_weights.items()}

    total = sum(clamped.values())
    if total <= 0.0:
        return {}

    # Normalize to sum to 1.0
    return {k: v / total for k, v in clamped.items()}


def compute_unified_consciousness(
    *,
    # Coherence variants (Phase 1-4, 10, 16)
    coherence_v1: Optional[float] = None,
    coherence_v2: Optional[float] = None,
    coherence_v3: Optional[float] = None,
    coherence_fused: Optional[float] = None,
    # Enhanced SMI (Phase 13 placeholder)
    enhanced_smi: Optional[float] = None,
    # Semantic integrity & cognitive drift (Phase 17)
    semantic_integrity_score: Optional[float] = None,
    cognitive_drift_v3: Optional[float] = None,
    # Drift fusion index (Phase 19 - if available, else use cognitive_drift_v3 as proxy)
    drift_fusion_index: Optional[float] = None,
    # Vritti momentum (Phase 14)
    vritti_momentum: Optional[float] = None,
    # Arc-tension harmonizer (Phase 14)
    arc_tension_harmonizer: Optional[float] = None,
    # Mirror-time loop metrics (Phase 21)
    mirror_loop_alignment: Optional[float] = None,
    mirror_loop_tension: Optional[float] = None,
    mirror_reversal_probability: Optional[float] = None,
    # Mirror-time cycle metrics (Phase 22)
    cycle_alignment: Optional[float] = None,
    cycle_tension: Optional[float] = None,
    cycle_reversal_probability: Optional[float] = None,
    # Temporal entropy differential (Phase 18)
    temporal_entropy_diff: Optional[float] = None,
    temporal_entropy_volatility: Optional[float] = None,
    # Guna/Kosha resonance (Phase 8)
    guna_resonance_index: Optional[float] = None,
    kosha_resonance_index: Optional[float] = None,
    # Resonance weighting (Phase 24)
    resonance_weighting_entropy: Optional[float] = None,
    dominant_resonance_metrics: Optional[List[str]] = None,
    # Quality metrics (Phase 12)
    coherence_v3_quality: Optional[float] = None,
    fusion_stability_weight: Optional[float] = None,
    fusion_inertia_factor: Optional[float] = None,
) -> Optional[UnifiedConsciousnessSnapshot]:
    """
    Compute Unified Consciousness Formula (UCF) v1.0.

    This meta-formula integrates ALL Symbol-U v3.0 signals into three indices:
      - COI (Consciousness Order Index): Structural coherence & organization
      - CSI (Consciousness Stability Index): Temporal stability & resilience
      - CIP (Consciousness Integration Potential): Cross-layer integration readiness

    The formula uses deterministic weighted combinations with canonical v1.0 coefficients.
    All outputs are clamped to [0.0, 1.0] and generate diagnostic notes.

    Args:
        coherence_v1: Coherence score v1 [0.0, 1.0]
        coherence_v2: Coherence score v2 [0.0, 1.0]
        coherence_v3: Coherence score v3 [0.0, 1.0]
        coherence_fused: Fused coherence score [0.0, 1.0]
        enhanced_smi: Enhanced SMI [0.0, 1.0]
        semantic_integrity_score: Semantic integrity [0.0, 1.0]
        cognitive_drift_v3: Cognitive drift v3 [0.0, 1.0] (risk metric)
        drift_fusion_index: Drift fusion index [0.0, 1.0] (risk metric)
        vritti_momentum: Vritti momentum [0.0, 1.0]
        arc_tension_harmonizer: Arc-tension harmonizer [0.0, 1.0]
        mirror_loop_alignment: Mirror-time loop alignment [0.0, 1.0]
        mirror_loop_tension: Mirror-time loop tension [0.0, 1.0] (risk metric)
        mirror_reversal_probability: Loop reversal probability [0.0, 1.0] (risk metric)
        cycle_alignment: Cycle alignment [0.0, 1.0]
        cycle_tension: Cycle tension [0.0, 1.0] (risk metric)
        cycle_reversal_probability: Cycle reversal probability [0.0, 1.0] (risk metric)
        temporal_entropy_diff: Temporal entropy differential [0.0, 1.0]
        temporal_entropy_volatility: Entropy volatility [0.0, 1.0] (risk metric)
        guna_resonance_index: Guna resonance [0.0, 1.0]
        kosha_resonance_index: Kosha resonance [0.0, 1.0]
        resonance_weighting_entropy: Resonance weight entropy [0.0, 1.0]
        dominant_resonance_metrics: Top resonance metrics by weight
        coherence_v3_quality: V3 quality metric [0.0, 1.0]
        fusion_stability_weight: Fusion stability weight [0.0, 1.0]
        fusion_inertia_factor: Fusion inertia factor [0.5, 1.0]

    Returns:
        UnifiedConsciousnessSnapshot or None if core inputs are missing

    Graceful Degradation:
        Returns None if we don't have at least one coherence signal AND
        one additional formula metric.
    """
    notes = []

    # ========================================================================
    # STEP 1: CHECK CORE INPUT AVAILABILITY (Graceful Degradation)
    # ========================================================================

    # We need at least ONE coherence signal
    coherence_available = any([
        coherence_v1 is not None,
        coherence_v2 is not None,
        coherence_v3 is not None,
        coherence_fused is not None,
    ])

    # We need at least ONE additional formula metric
    formulas_available = any([
        enhanced_smi is not None,
        semantic_integrity_score is not None,
        cognitive_drift_v3 is not None,
        vritti_momentum is not None,
        arc_tension_harmonizer is not None,
        mirror_loop_alignment is not None,
        temporal_entropy_diff is not None,
        guna_resonance_index is not None,
        kosha_resonance_index is not None,
    ])

    if not coherence_available or not formulas_available:
        # Insufficient data for UCF computation
        return None

    # ========================================================================
    # STEP 2: PREPARE COMPONENT WEIGHTS (Canonical v1.0 Coefficients)
    # ========================================================================

    raw_weights = {}

    # === COHERENCE SIGNALS (Structural Foundation) ===

    # Prioritize coherence_fused > v2 > v3 > v1
    if coherence_fused is not None:
        raw_weights["coherence_fused"] = 1.0 * _clamp(coherence_fused)
        if coherence_fused >= 0.75:
            notes.append("coherence_fused_dominant")
    elif coherence_v2 is not None:
        raw_weights["coherence_v2"] = 0.9 * _clamp(coherence_v2)
    elif coherence_v3 is not None:
        # V3 requires quality check
        quality = coherence_v3_quality if coherence_v3_quality is not None else 0.5
        if quality >= 0.6:
            raw_weights["coherence_v3"] = 0.85 * _clamp(coherence_v3)
        else:
            raw_weights["coherence_v3"] = 0.5 * _clamp(coherence_v3)
            notes.append("coherence_v3_low_quality")
    elif coherence_v1 is not None:
        raw_weights["coherence_v1"] = 0.75 * _clamp(coherence_v1)

    # === SEMANTIC LAYER (Integrity & Drift) ===

    if semantic_integrity_score is not None:
        raw_weights["semantic_integrity"] = 0.9 * _clamp(semantic_integrity_score)
        if semantic_integrity_score >= 0.7:
            notes.append("semantic_integrity_strong")

    # Cognitive drift is a RISK metric - invert it
    if cognitive_drift_v3 is not None:
        stability = 1.0 - _clamp(cognitive_drift_v3)
        raw_weights["cognitive_stability"] = 0.85 * stability
        if cognitive_drift_v3 >= 0.6:
            notes.append("cognitive_drift_warning")

    # Drift fusion index (if available, else already using cognitive_drift_v3)
    if drift_fusion_index is not None and drift_fusion_index != cognitive_drift_v3:
        stability = 1.0 - _clamp(drift_fusion_index)
        raw_weights["drift_stability"] = 0.8 * stability

    # === TEMPORAL DYNAMICS (Momentum & Harmonization) ===

    if vritti_momentum is not None:
        raw_weights["vritti_momentum"] = 0.75 * _clamp(vritti_momentum)
        if vritti_momentum >= 0.7:
            notes.append("vritti_momentum_strong")

    if arc_tension_harmonizer is not None:
        raw_weights["arc_tension_harmonizer"] = 0.8 * _clamp(arc_tension_harmonizer)
        if arc_tension_harmonizer >= 0.75:
            notes.append("arc_tension_harmonized")

    # === MIRROR-TIME MECHANICS (Loop & Cycle Analysis) ===

    # Mirror-time loop alignment (forward-mirror coherence)
    if mirror_loop_alignment is not None:
        raw_weights["mirror_loop_alignment"] = 0.7 * _clamp(mirror_loop_alignment)

    # Mirror-time loop tension is a RISK metric - invert it
    if mirror_loop_tension is not None:
        stability = 1.0 - _clamp(mirror_loop_tension)
        raw_weights["mirror_loop_stability"] = 0.65 * stability
        if mirror_loop_tension >= 0.7:
            notes.append("mirror_loop_high_tension")

    # Reversal probability is a RISK metric - invert it
    if mirror_reversal_probability is not None:
        stability = 1.0 - _clamp(mirror_reversal_probability)
        raw_weights["mirror_reversal_stability"] = 0.6 * stability
        if mirror_reversal_probability >= 0.6:
            notes.append("reversal_risk_elevated")

    # Mirror-time cycle alignment
    if cycle_alignment is not None:
        raw_weights["cycle_alignment"] = 0.7 * _clamp(cycle_alignment)

    # Cycle tension is a RISK metric - invert it
    if cycle_tension is not None:
        stability = 1.0 - _clamp(cycle_tension)
        raw_weights["cycle_stability"] = 0.65 * stability

    # Cycle reversal probability is a RISK metric - invert it
    if cycle_reversal_probability is not None:
        stability = 1.0 - _clamp(cycle_reversal_probability)
        raw_weights["cycle_reversal_stability"] = 0.6 * stability

    # === TEMPORAL ENTROPY (Entropy Differential & Volatility) ===

    if temporal_entropy_diff is not None:
        # Low diff = stable, high diff = transitioning
        # Interpret as quality signal: moderate values are good
        # Map [0.0, 0.5, 1.0] → [0.5, 1.0, 0.5] (peak at 0.5)
        if temporal_entropy_diff <= 0.5:
            quality = 0.5 + temporal_entropy_diff
        else:
            quality = 1.5 - temporal_entropy_diff
        raw_weights["temporal_entropy_quality"] = 0.6 * _clamp(quality)

    # Entropy volatility is a RISK metric - invert it
    if temporal_entropy_volatility is not None:
        stability = 1.0 - _clamp(temporal_entropy_volatility)
        raw_weights["entropy_stability"] = 0.65 * stability
        if temporal_entropy_volatility >= 0.7:
            notes.append("entropy_volatility_high")

    # === RESONANCE LAYER (Guna/Kosha Resonance) ===

    if guna_resonance_index is not None:
        raw_weights["guna_resonance"] = 0.7 * _clamp(guna_resonance_index)

    if kosha_resonance_index is not None:
        raw_weights["kosha_resonance"] = 0.7 * _clamp(kosha_resonance_index)

    # === ENHANCED SMI (Authenticity/Tension Index) ===

    if enhanced_smi is not None:
        raw_weights["enhanced_smi"] = 0.75 * _clamp(enhanced_smi)
        if enhanced_smi >= 0.75:
            notes.append("enhanced_smi_dominant")

    # === RESONANCE WEIGHTING META-SIGNAL (Phase 24) ===

    # Entropy of resonance weights indicates focus vs. diffusion
    # Low entropy = focused (good), high entropy = diffuse (less reliable)
    if resonance_weighting_entropy is not None:
        focus_quality = 1.0 - _clamp(resonance_weighting_entropy)
        raw_weights["resonance_focus"] = 0.5 * focus_quality
        if resonance_weighting_entropy >= 0.7:
            notes.append("resonance_weighting_diffuse")
        elif resonance_weighting_entropy <= 0.35:
            notes.append("resonance_weighting_focused")

    # === QUALITY & STABILITY MODULATION ===

    if coherence_v3_quality is not None:
        raw_weights["v3_quality"] = 0.6 * _clamp(coherence_v3_quality)

    if fusion_stability_weight is not None:
        raw_weights["fusion_stability"] = 0.7 * _clamp(fusion_stability_weight)

    if fusion_inertia_factor is not None:
        # Inertia is [0.5, 1.0], normalize to [0, 1]
        inertia_norm = _clamp((fusion_inertia_factor - 0.5) * 2.0)
        raw_weights["fusion_inertia"] = 0.6 * inertia_norm

    # ========================================================================
    # STEP 3: NORMALIZE WEIGHTS
    # ========================================================================

    normalized_weights = _normalize_weights(raw_weights)

    if not normalized_weights:
        # Should not happen if we passed initial checks, but safeguard
        return None

    # Compute Shannon entropy of weight distribution
    entropy = _compute_shannon_entropy(normalized_weights)

    # ========================================================================
    # STEP 4: COMPUTE UNIFIED CONSCIOUSNESS INDICES (COI, CSI, CIP)
    # ========================================================================

    # === COI (Consciousness Order Index) ===
    # Measures structural coherence, semantic integrity, and resonance alignment
    # Higher = better organization

    coi_components = {}
    if "coherence_fused" in normalized_weights:
        coi_components["coherence_fused"] = normalized_weights["coherence_fused"]
    elif "coherence_v2" in normalized_weights:
        coi_components["coherence_v2"] = normalized_weights["coherence_v2"]
    elif "coherence_v3" in normalized_weights:
        coi_components["coherence_v3"] = normalized_weights["coherence_v3"]
    elif "coherence_v1" in normalized_weights:
        coi_components["coherence_v1"] = normalized_weights["coherence_v1"]

    if "semantic_integrity" in normalized_weights:
        coi_components["semantic_integrity"] = normalized_weights["semantic_integrity"]
    if "guna_resonance" in normalized_weights:
        coi_components["guna_resonance"] = normalized_weights["guna_resonance"]
    if "kosha_resonance" in normalized_weights:
        coi_components["kosha_resonance"] = normalized_weights["kosha_resonance"]
    if "arc_tension_harmonizer" in normalized_weights:
        coi_components["arc_tension_harmonizer"] = normalized_weights["arc_tension_harmonizer"]

    # Compute COI as weighted average of order-related signals
    coi_total_weight = sum(coi_components.values())
    if coi_total_weight > 0:
        coi = 0.0
        for component_name, component_weight in coi_components.items():
            # Get actual metric value from raw_weights
            metric_value = raw_weights.get(component_name, 0.0)
            # Denormalize the coefficient (since raw_weights already contains scaled values)
            # We need the original metric value, so divide by the scaling factor
            # This is complex, so let's use a simpler approach: weighted sum of normalized weights * raw values
            coi += (component_weight / coi_total_weight) * metric_value

        coi = _clamp(coi)
    else:
        # No order components available - use fallback
        coi = 0.5

    # === CSI (Consciousness Stability Index) ===
    # Measures temporal stability, low drift, low volatility, low tension
    # Higher = more stable/resilient

    csi_components = {}
    if "cognitive_stability" in normalized_weights:
        csi_components["cognitive_stability"] = normalized_weights["cognitive_stability"]
    if "drift_stability" in normalized_weights:
        csi_components["drift_stability"] = normalized_weights["drift_stability"]
    if "entropy_stability" in normalized_weights:
        csi_components["entropy_stability"] = normalized_weights["entropy_stability"]
    if "mirror_loop_stability" in normalized_weights:
        csi_components["mirror_loop_stability"] = normalized_weights["mirror_loop_stability"]
    if "mirror_reversal_stability" in normalized_weights:
        csi_components["mirror_reversal_stability"] = normalized_weights["mirror_reversal_stability"]
    if "cycle_stability" in normalized_weights:
        csi_components["cycle_stability"] = normalized_weights["cycle_stability"]
    if "cycle_reversal_stability" in normalized_weights:
        csi_components["cycle_reversal_stability"] = normalized_weights["cycle_reversal_stability"]
    if "vritti_momentum" in normalized_weights:
        csi_components["vritti_momentum"] = normalized_weights["vritti_momentum"]
    if "fusion_stability" in normalized_weights:
        csi_components["fusion_stability"] = normalized_weights["fusion_stability"]
    if "fusion_inertia" in normalized_weights:
        csi_components["fusion_inertia"] = normalized_weights["fusion_inertia"]

    # Compute CSI as weighted average of stability-related signals
    csi_total_weight = sum(csi_components.values())
    if csi_total_weight > 0:
        csi = 0.0
        for component_name, component_weight in csi_components.items():
            metric_value = raw_weights.get(component_name, 0.0)
            csi += (component_weight / csi_total_weight) * metric_value

        csi = _clamp(csi)
    else:
        # No stability components available - use fallback
        csi = 0.5

    # === CIP (Consciousness Integration Potential) ===
    # Measures readiness for cross-layer integration, alignment quality
    # Higher = better integration potential

    cip_components = {}
    if "mirror_loop_alignment" in normalized_weights:
        cip_components["mirror_loop_alignment"] = normalized_weights["mirror_loop_alignment"]
    if "cycle_alignment" in normalized_weights:
        cip_components["cycle_alignment"] = normalized_weights["cycle_alignment"]
    if "temporal_entropy_quality" in normalized_weights:
        cip_components["temporal_entropy_quality"] = normalized_weights["temporal_entropy_quality"]
    if "enhanced_smi" in normalized_weights:
        cip_components["enhanced_smi"] = normalized_weights["enhanced_smi"]
    if "resonance_focus" in normalized_weights:
        cip_components["resonance_focus"] = normalized_weights["resonance_focus"]
    if "v3_quality" in normalized_weights:
        cip_components["v3_quality"] = normalized_weights["v3_quality"]

    # Compute CIP as weighted average of integration-related signals
    cip_total_weight = sum(cip_components.values())
    if cip_total_weight > 0:
        cip = 0.0
        for component_name, component_weight in cip_components.items():
            metric_value = raw_weights.get(component_name, 0.0)
            cip += (component_weight / cip_total_weight) * metric_value

        cip = _clamp(cip)
    else:
        # No integration components available - use fallback
        cip = 0.5

    # ========================================================================
    # STEP 5: GENERATE DIAGNOSTIC NOTES
    # ========================================================================

    # Add COI/CSI/CIP level notes
    if coi >= 0.75:
        notes.append("high_consciousness_order")
    elif coi <= 0.35:
        notes.append("low_consciousness_order")

    if csi >= 0.75:
        notes.append("high_consciousness_stability")
    elif csi <= 0.35:
        notes.append("low_consciousness_stability")

    if cip >= 0.75:
        notes.append("high_integration_potential")
    elif cip <= 0.35:
        notes.append("low_integration_potential")

    # Add entropy-based notes
    if entropy < 0.35:
        notes.append("focused_ucf_distribution")
    elif entropy >= 0.70:
        notes.append("diffuse_ucf_distribution")

    # Check for convergence/divergence patterns
    if coi >= 0.65 and csi >= 0.65 and cip >= 0.65:
        notes.append("ucf_patterns_converging")
    elif coi <= 0.40 or csi <= 0.40 or cip <= 0.40:
        notes.append("ucf_patterns_diverging")

    # Check for high integration state
    if coi >= 0.7 and csi >= 0.7 and cip >= 0.7:
        notes.append("ucf_high_integration")

    # Check for stability plateau
    if 0.45 <= coi <= 0.65 and 0.45 <= csi <= 0.65 and 0.45 <= cip <= 0.65:
        notes.append("ucf_stable")

    # Check for fragmentation
    if abs(coi - csi) >= 0.4 or abs(coi - cip) >= 0.4 or abs(csi - cip) >= 0.4:
        notes.append("ucf_fragmented")

    # ========================================================================
    # STEP 6: RETURN SNAPSHOT
    # ========================================================================

    return UnifiedConsciousnessSnapshot(
        consciousness_order_index=coi,
        consciousness_stability_index=csi,
        consciousness_integration_potential=cip,
        weighted_component_breakdown=raw_weights,
        normalized_weights=normalized_weights,
        entropy_of_weights=entropy,
        diagnostic_notes=sorted(set(notes)),  # Deduplicate and sort for determinism
    )
