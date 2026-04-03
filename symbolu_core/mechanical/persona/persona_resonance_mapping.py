"""
Phase 30: Cross-Layer Resonance Persona Mapping (CL-RPM)
==========================================================

Deterministic, zero-LLM, observation-only mapping layer that translates
Symbol-U v3.0 resonance signals into stable persona tone parameters.

This module:
    • Observes multi-layer resonance signals (Guna/Kosha, SHF, UCF, drift, etc.)
    • Maps them deterministically into persona tone modulation parameters
    • Does NOT affect semantics, routing, or reasoning
    • Only shapes tone inside the Persona Engine

All mappings are:
    • Deterministic (same inputs → same outputs)
    • Bounded [0.0, 1.0]
    • Gracefully degrade to defaults when inputs missing
    • Zero-LLM (pure mathematical transforms)
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class CrossLayerResonanceMap:
    """
    Cross-layer resonance map that translates formula signals into persona tone parameters.

    Raw Formula Signals (Inputs):
        These are observed from CoherenceObservation and used to compute tone parameters.
        All are optional and gracefully degrade to defaults if missing.

    Derived Persona Modulation Parameters (Outputs):
        These control tone-only adjustments in the Persona Engine.
        All are deterministic functions of input signals.
    """

    # ========================================================================
    # RAW FORMULA SIGNALS (Inputs from CoherenceObservation)
    # ========================================================================

    guna_resonance: Optional[float] = None
    kosha_resonance: Optional[float] = None
    semantic_integrity: Optional[float] = None
    cognitive_drift_v3: Optional[float] = None
    temporal_entropy: Optional[float] = None
    drift_fusion_index: Optional[float] = None  # From coherence_fused
    coherence_fused: Optional[float] = None
    shf: Optional[float] = None  # Symbolic Harmonization Index
    ucf_coi: Optional[float] = None  # Unified Consciousness: Order Index
    ucf_csi: Optional[float] = None  # Unified Consciousness: Stability Index
    ucf_cip: Optional[float] = None  # Unified Consciousness: Integration Potential

    # ========================================================================
    # DERIVED PERSONA MODULATION PARAMETERS (Outputs)
    # ========================================================================

    metaphor_weight: float = 0.5
    warmth_weight: float = 0.5
    structure_weight: float = 0.5
    reflective_bandwidth: float = 0.5
    grounding_bias: float = 0.5
    expressiveness_bias: float = 0.5
    resonance_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "raw_signals": {
                "guna_resonance": self.guna_resonance,
                "kosha_resonance": self.kosha_resonance,
                "semantic_integrity": self.semantic_integrity,
                "cognitive_drift_v3": self.cognitive_drift_v3,
                "temporal_entropy": self.temporal_entropy,
                "drift_fusion_index": self.drift_fusion_index,
                "coherence_fused": self.coherence_fused,
                "shf": self.shf,
                "ucf_coi": self.ucf_coi,
                "ucf_csi": self.ucf_csi,
                "ucf_cip": self.ucf_cip,
            },
            "modulation_parameters": {
                "metaphor_weight": self.metaphor_weight,
                "warmth_weight": self.warmth_weight,
                "structure_weight": self.structure_weight,
                "reflective_bandwidth": self.reflective_bandwidth,
                "grounding_bias": self.grounding_bias,
                "expressiveness_bias": self.expressiveness_bias,
            },
            "resonance_tags": self.resonance_tags,
        }


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value to [min_val, max_val] range."""
    return max(min_val, min(max_val, value))


def _safe_avg(a: Optional[float], b: Optional[float], default: float = 0.5) -> float:
    """Safely average two optional floats."""
    if a is not None and b is not None:
        return (a + b) / 2.0
    elif a is not None:
        return a
    elif b is not None:
        return b
    else:
        return default


def compute_cross_layer_persona_map(snapshot: Any) -> CrossLayerResonanceMap:
    """
    Compute cross-layer resonance persona map from CoherenceObservation snapshot.

    This is the CANONICAL v1.0 mapping function that translates multi-layer
    coherence signals into persona tone parameters.

    Mapping Logic (Deterministic):

        A. Tone Surface Mapping:
           ┌─────────────────────────────────────────────────────────────┐
           │ Input Signal              │ Persona Tone Effect           │
           ├─────────────────────────────────────────────────────────────┤
           │ High Guna/Kosha resonance │ ↑ metaphors, ↑ warmth         │
           │ Low Semantic Integrity    │ ↑ structure, ↓ metaphor       │
           │ High Cognitive Drift      │ ↑ grounding_bias              │
           │ High Temporal Entropy     │ ↓ expressiveness              │
           │ High SHF                  │ ↑ symbolic richness           │
           │ High UCF.COI              │ ↑ structure, ↑ alignment      │
           │ High UCF.CSI              │ ↑ stability weighting         │
           │ High UCF.CIP              │ ↑ openness bandwidth          │
           └─────────────────────────────────────────────────────────────┘

        B. Resonance Tags (Rule-Based):
           • "HIGH_RESONANCE" if (guna + kosha) / 2 ≥ 0.70
           • "LOW_RESONANCE" if (guna + kosha) / 2 ≤ 0.40
           • "HIGH_STABILITY" if ucf_csi ≥ 0.70
           • "HIGH_INTEGRATION" if ucf_cip ≥ 0.70
           • "SYMBOLIC_RICH" if shf ≥ 0.70
           • "DRIFT_CAUTION" if cognitive_drift_v3 ≥ 0.60
           • "ENTROPY_HIGH" if temporal_entropy ≥ 0.60

    Args:
        snapshot: CoherenceObservation instance with formula signals

    Returns:
        CrossLayerResonanceMap with all tone parameters computed

    Invariants:
        • All weights in [0.0, 1.0]
        • Deterministic: same inputs → same outputs
        • Graceful degradation: missing inputs → default weights
        • Zero-LLM: pure math, no inference
    """

    # ========================================================================
    # STEP 1: Extract raw signals from snapshot
    # ========================================================================

    guna_resonance = getattr(snapshot, 'guna_resonance_index', None)
    kosha_resonance = getattr(snapshot, 'kosha_resonance_index', None)
    semantic_integrity = getattr(snapshot, 'semantic_integrity_score', None)
    cognitive_drift_v3 = getattr(snapshot, 'cognitive_drift_v3', None)
    temporal_entropy = getattr(snapshot, 'temporal_entropy_diff', None)
    coherence_fused = getattr(snapshot, 'coherence_fused', None)
    shf = getattr(snapshot, 'symbolic_harmonization_index', None)
    ucf_coi = getattr(snapshot, 'consciousness_order_index', None)
    ucf_csi = getattr(snapshot, 'consciousness_stability_index', None)
    ucf_cip = getattr(snapshot, 'consciousness_integration_potential', None)

    # ========================================================================
    # STEP 2: Compute derived tone parameters (deterministic mapping)
    # ========================================================================

    # A. Metaphor Weight
    # High Guna/Kosha → ↑ metaphor
    # Low Semantic Integrity → ↓ metaphor
    # High SHF → ↑ metaphor
    base_metaphor = _safe_avg(guna_resonance, kosha_resonance, default=0.5)
    if shf is not None:
        base_metaphor = (base_metaphor * 0.6 + shf * 0.4)
    if semantic_integrity is not None and semantic_integrity < 0.5:
        # Low semantic integrity reduces metaphor weight
        base_metaphor *= (0.7 + semantic_integrity * 0.6)  # Scale down
    metaphor_weight = _clamp(base_metaphor, 0.0, 1.0)

    # B. Warmth Weight
    # High Guna/Kosha → ↑ warmth
    # High UCF.CIP → ↑ warmth (openness)
    base_warmth = _safe_avg(guna_resonance, kosha_resonance, default=0.5)
    if ucf_cip is not None:
        base_warmth = (base_warmth * 0.7 + ucf_cip * 0.3)
    warmth_weight = _clamp(base_warmth, 0.0, 1.0)

    # C. Structure Weight
    # Low Semantic Integrity → ↑ structure (compensate)
    # High UCF.COI → ↑ structure (order)
    # High UCF.CSI → ↑ structure (stability)
    base_structure = 0.5
    if semantic_integrity is not None:
        # Low semantic integrity increases structure weight
        base_structure = 0.5 + (0.5 - semantic_integrity) * 0.4
    if ucf_coi is not None:
        base_structure = (base_structure * 0.6 + ucf_coi * 0.4)
    if ucf_csi is not None:
        base_structure = (base_structure * 0.8 + ucf_csi * 0.2)
    structure_weight = _clamp(base_structure, 0.0, 1.0)

    # D. Reflective Bandwidth
    # High SHF → ↑ reflective bandwidth
    # High UCF.CIP → ↑ reflective bandwidth
    base_reflective = 0.5
    if shf is not None:
        base_reflective = (base_reflective * 0.5 + shf * 0.5)
    if ucf_cip is not None:
        base_reflective = (base_reflective * 0.7 + ucf_cip * 0.3)
    reflective_bandwidth = _clamp(base_reflective, 0.0, 1.0)

    # E. Grounding Bias
    # High Cognitive Drift → ↑ grounding (compensate)
    # Low Semantic Integrity → ↑ grounding (compensate)
    base_grounding = 0.5
    if cognitive_drift_v3 is not None:
        # High drift increases grounding bias
        base_grounding = 0.5 + cognitive_drift_v3 * 0.3
    if semantic_integrity is not None and semantic_integrity < 0.5:
        # Low semantic integrity increases grounding
        base_grounding += (0.5 - semantic_integrity) * 0.2
    grounding_bias = _clamp(base_grounding, 0.0, 1.0)

    # F. Expressiveness Bias
    # High Temporal Entropy → ↓ expressiveness (stabilize)
    # High SHF → ↑ expressiveness
    base_expressiveness = 0.5
    if temporal_entropy is not None:
        # High entropy reduces expressiveness
        base_expressiveness = 0.5 - temporal_entropy * 0.3
    if shf is not None:
        base_expressiveness += shf * 0.2
    expressiveness_bias = _clamp(base_expressiveness, 0.0, 1.0)

    # ========================================================================
    # STEP 3: Generate resonance tags (rule-based)
    # ========================================================================

    tags = []

    # Combined Guna/Kosha resonance
    combined_resonance = _safe_avg(guna_resonance, kosha_resonance, default=None)
    if combined_resonance is not None:
        if combined_resonance >= 0.70:
            tags.append("HIGH_RESONANCE")
        elif combined_resonance <= 0.40:
            tags.append("LOW_RESONANCE")

    # UCF stability
    if ucf_csi is not None and ucf_csi >= 0.70:
        tags.append("HIGH_STABILITY")

    # UCF integration
    if ucf_cip is not None and ucf_cip >= 0.70:
        tags.append("HIGH_INTEGRATION")

    # Symbolic richness
    if shf is not None and shf >= 0.70:
        tags.append("SYMBOLIC_RICH")

    # Drift caution
    if cognitive_drift_v3 is not None and cognitive_drift_v3 >= 0.60:
        tags.append("DRIFT_CAUTION")

    # Entropy high
    if temporal_entropy is not None and temporal_entropy >= 0.60:
        tags.append("ENTROPY_HIGH")

    # Deduplicate and sort tags
    tags = sorted(set(tags))

    # ========================================================================
    # STEP 4: Build and return CrossLayerResonanceMap
    # ========================================================================

    return CrossLayerResonanceMap(
        # Raw signals
        guna_resonance=guna_resonance,
        kosha_resonance=kosha_resonance,
        semantic_integrity=semantic_integrity,
        cognitive_drift_v3=cognitive_drift_v3,
        temporal_entropy=temporal_entropy,
        drift_fusion_index=None,  # Not used in v1.0
        coherence_fused=coherence_fused,
        shf=shf,
        ucf_coi=ucf_coi,
        ucf_csi=ucf_csi,
        ucf_cip=ucf_cip,
        # Derived parameters
        metaphor_weight=round(metaphor_weight, 4),
        warmth_weight=round(warmth_weight, 4),
        structure_weight=round(structure_weight, 4),
        reflective_bandwidth=round(reflective_bandwidth, 4),
        grounding_bias=round(grounding_bias, 4),
        expressiveness_bias=round(expressiveness_bias, 4),
        resonance_tags=tags,
    )
