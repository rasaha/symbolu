"""
Phase 33: Persona Schema Adaptive Routing Layer (Observation-Only) v1.0
=========================================================================

Experimental, non-invasive, zero-LLM analytics layer that computes persona schema
alignment signals WITHOUT modifying routing or persona selection behavior.

This module:
    • Computes schema alignment scores for each persona schema
    • Tracks schema drift, schema stability, and schema fit confidence
    • Generates persona_schema_candidate_ranking (diagnostic-only)
    • Exposes experimental map for research & observability
    • Never affects actual routing or persona selection

All computations are:
    • Deterministic (same inputs → same outputs)
    • Bounded [0.0, 1.0]
    • Gracefully degrade to defaults when inputs missing
    • Zero-LLM (pure mathematical transforms)
    • Observation-only (no behavior changes)

CRITICAL: This is a DIAGNOSTIC-ONLY layer. All outputs are for analytics purposes.
The persona selection logic in PersonaSelector remains unchanged.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import math


@dataclass
class SchemaAdaptiveRoutingSnapshot:
    """
    Persona schema alignment snapshot (observation-only).

    Computes how well the user's coherence/semantic/resonance patterns
    align to different persona schemas, without affecting routing.

    Attributes:
        schema_alignment_scores: Alignment score for each persona schema [0.0, 1.0]
            Keys: persona_id (sage, analyst, coach, friendly, regulator, neutral)
            Values: alignment score (higher = better fit)

        schema_confidence: Overall confidence in schema alignment computation [0.0, 1.0]
            High confidence = sufficient signals available for robust alignment
            Low confidence = limited signals, use default neutral

        schema_drift: Schema drift score [0.0, 1.0]
            Measures how much the user's alignment pattern is shifting
            High drift = unstable schema fit, caution recommended

        schema_stability: Schema stability score [0.0, 1.0]
            Measures consistency of schema alignment over time
            High stability = consistent fit, low volatility

        persona_schema_candidate_ranking: Ordered list of (persona_id, score) tuples
            Ranked from highest to lowest alignment score
            Diagnostic-only: NEVER used for actual persona selection

        schema_tags: Diagnostic tags describing schema fit characteristics
            E.g., ["HIGH_ANALYST_ALIGNMENT", "SCHEMA_DRIFT_CAUTION", "STABLE_SCHEMA_FIT"]
    """

    schema_alignment_scores: Dict[str, float] = field(default_factory=dict)
    schema_confidence: float = 0.5
    schema_drift: float = 0.0
    schema_stability: float = 1.0
    persona_schema_candidate_ranking: List[tuple] = field(default_factory=list)
    schema_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "schema_alignment_scores": self.schema_alignment_scores,
            "schema_confidence": self.schema_confidence,
            "schema_drift": self.schema_drift,
            "schema_stability": self.schema_stability,
            "persona_schema_candidate_ranking": [
                {"persona_id": persona_id, "score": score}
                for persona_id, score in self.persona_schema_candidate_ranking
            ],
            "schema_tags": self.schema_tags,
        }


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value to [min_val, max_val] range."""
    return max(min_val, min(max_val, value))


def _safe_get(obj: Any, attr: str, default: Optional[float] = None) -> Optional[float]:
    """Safely get attribute from object, return default if missing."""
    return getattr(obj, attr, default)


def _compute_entropy(scores: Dict[str, float]) -> float:
    """
    Compute normalized entropy of score distribution.

    Returns:
        Entropy in [0.0, 1.0] where:
        - 0.0 = uniform distribution (all scores equal)
        - 1.0 = concentrated distribution (one score dominates)
    """
    if not scores:
        return 0.0

    values = list(scores.values())
    total = sum(values)

    if total == 0.0:
        return 0.0

    # Compute Shannon entropy
    entropy = 0.0
    for v in values:
        if v > 0:
            p = v / total
            entropy -= p * math.log2(p)

    # Normalize to [0, 1] (max entropy = log2(n))
    max_entropy = math.log2(len(values)) if len(values) > 1 else 1.0
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

    return _clamp(normalized_entropy)


def compute_schema_adaptive_map(
    coherence_observation: Any,
    previous_snapshot: Optional[SchemaAdaptiveRoutingSnapshot] = None
) -> SchemaAdaptiveRoutingSnapshot:
    """
    Compute persona schema adaptive routing map from CoherenceObservation.

    This is the CANONICAL v1.0 mapping function that computes schema alignment
    scores for all persona schemas based on coherence/semantic/resonance signals.

    Schema Alignment Logic (Deterministic):

        A. Persona Schema Signatures:
           Each persona has distinct trait signatures that we match against.

           ┌────────────────────────────────────────────────────────────────┐
           │ Persona    │ Key Traits                                        │
           ├────────────────────────────────────────────────────────────────┤
           │ sage       │ High symbolic, high metaphor, high reflective      │
           │ analyst    │ High structure, high practical, low metaphor      │
           │ coach      │ High warmth, high grounding, moderate structure   │
           │ friendly   │ High warmth, high expressiveness, low formality   │
           │ regulator  │ High caution, high structure, low expressiveness  │
           │ neutral    │ Balanced all traits (default fallback)            │
           └────────────────────────────────────────────────────────────────┘

        B. Alignment Computation:
           For each persona, compute alignment score as weighted sum:

           alignment = w1*symbolic_fit + w2*practical_fit + w3*resonance_fit +
                       w4*stability_fit + w5*drift_penalty

           Where:
           - symbolic_fit: How well user's symbolic signals match persona
           - practical_fit: How well user's practical signals match persona
           - resonance_fit: How well user's resonance signals match persona
           - stability_fit: User's coherence stability
           - drift_penalty: Penalty for high cognitive drift

        C. Schema Confidence:
           Confidence = availability_factor * quality_factor

           Where:
           - availability_factor: % of signals available (0-1)
           - quality_factor: quality of available signals

        D. Schema Drift & Stability:
           Compare current alignment to previous snapshot:
           - schema_drift: L2 distance between current and previous scores
           - schema_stability: 1.0 - schema_drift

    Args:
        coherence_observation: CoherenceObservation with all coherence signals
        previous_snapshot: Optional previous SchemaAdaptiveRoutingSnapshot for drift

    Returns:
        SchemaAdaptiveRoutingSnapshot with all schema alignment metrics

    Invariants:
        • All scores in [0.0, 1.0]
        • Deterministic: same inputs → same outputs
        • Graceful degradation: missing signals → neutral defaults
        • Zero-LLM: pure rule-based math
        • Observation-only: NEVER affects routing
    """
    # ========================================================================
    # STEP 1: Extract raw signals from coherence observation
    # ========================================================================

    # Symbolic/resonance signals
    symbolic_harmonization_index = _safe_get(coherence_observation, 'symbolic_harmonization_index', 0.5)
    guna_resonance_index = _safe_get(coherence_observation, 'guna_resonance_index', 0.5)
    kosha_resonance_index = _safe_get(coherence_observation, 'kosha_resonance_index', 0.5)

    # Practical/stability signals
    semantic_integrity_score = _safe_get(coherence_observation, 'semantic_integrity_score', 0.7)
    coherence_fused = _safe_get(coherence_observation, 'coherence_fused', 0.7)
    coherence_score = _safe_get(coherence_observation, 'coherence_score', 0.7)

    # Drift/volatility signals
    cognitive_drift_v3 = _safe_get(coherence_observation, 'cognitive_drift_v3', 0.3)
    persona_drift_score = _safe_get(coherence_observation, 'persona_drift_score', 0.2)
    mapper_volatility_score = _safe_get(coherence_observation, 'mapper_volatility_score', 0.2)

    # Resonance/expressiveness signals
    consciousness_order_index = _safe_get(coherence_observation, 'consciousness_order_index', 0.5)
    consciousness_stability_index = _safe_get(coherence_observation, 'consciousness_stability_index', 0.7)
    consciousness_integration_potential = _safe_get(coherence_observation, 'consciousness_integration_potential', 0.5)

    # Temporal/entropy signals
    temporal_entropy_volatility = _safe_get(coherence_observation, 'temporal_entropy_volatility', 0.3)

    # Count available signals for confidence
    signal_count = sum([
        symbolic_harmonization_index is not None,
        guna_resonance_index is not None,
        kosha_resonance_index is not None,
        semantic_integrity_score is not None,
        coherence_fused is not None,
        cognitive_drift_v3 is not None,
        consciousness_order_index is not None,
    ])

    availability_factor = signal_count / 7.0  # 7 key signals

    # ========================================================================
    # STEP 2: Compute derived aggregate signals
    # ========================================================================

    # Symbolic richness: how metaphorical/deep the user's patterns are
    # Use default 0.5 for None values
    symbolic_richness = (
        (symbolic_harmonization_index if symbolic_harmonization_index is not None else 0.5) +
        (guna_resonance_index if guna_resonance_index is not None else 0.5) +
        (kosha_resonance_index if kosha_resonance_index is not None else 0.5)
    ) / 3.0

    # Practical grounding: how concrete/stable the user's patterns are
    practical_grounding = (
        (semantic_integrity_score if semantic_integrity_score is not None else 0.7) +
        (coherence_fused if coherence_fused is not None else 0.7) +
        (coherence_score if coherence_score is not None else 0.7)
    ) / 3.0

    # Expressiveness: how open/integrative the user's patterns are
    expressiveness = (
        (consciousness_integration_potential if consciousness_integration_potential is not None else 0.5) +
        (consciousness_order_index if consciousness_order_index is not None else 0.5)
    ) / 2.0

    # Structure preference: inverse of entropy/volatility (high structure = low chaos)
    structure_preference = 1.0 - (temporal_entropy_volatility if temporal_entropy_volatility is not None else 0.3)

    # Warmth signal: inverse of drift (low drift = high warmth/stability)
    warmth_signal = 1.0 - (
        ((cognitive_drift_v3 if cognitive_drift_v3 is not None else 0.3) +
         (persona_drift_score if persona_drift_score is not None else 0.2)) / 2.0
    )

    # Caution signal: how much drift/volatility is present
    caution_signal = (
        (cognitive_drift_v3 if cognitive_drift_v3 is not None else 0.3) +
        (mapper_volatility_score if mapper_volatility_score is not None else 0.2) +
        (persona_drift_score if persona_drift_score is not None else 0.2)
    ) / 3.0

    # ========================================================================
    # STEP 3: Compute schema alignment scores for each persona
    # ========================================================================

    alignment_scores = {}

    # SAGE: High symbolic, high metaphor, high reflective
    # Weights: symbolic (0.40), expressiveness (0.25), consciousness (0.20), structure (0.15)
    sage_alignment = (
        0.40 * symbolic_richness +
        0.25 * expressiveness +
        0.20 * consciousness_stability_index +
        0.15 * structure_preference
    )
    alignment_scores["sage"] = _clamp(sage_alignment)

    # ANALYST: High structure, high practical, low metaphor
    # Weights: practical (0.40), structure (0.30), stability (0.20), -symbolic (0.10)
    analyst_alignment = (
        0.40 * practical_grounding +
        0.30 * structure_preference +
        0.20 * consciousness_stability_index +
        0.10 * (1.0 - symbolic_richness)  # Penalty for high symbolic
    )
    alignment_scores["analyst"] = _clamp(analyst_alignment)

    # COACH: High warmth, high grounding, moderate structure
    # Weights: warmth (0.35), practical (0.30), expressiveness (0.20), structure (0.15)
    coach_alignment = (
        0.35 * warmth_signal +
        0.30 * practical_grounding +
        0.20 * expressiveness +
        0.15 * structure_preference
    )
    alignment_scores["coach"] = _clamp(coach_alignment)

    # FRIENDLY: High warmth, high expressiveness, low formality
    # Weights: warmth (0.40), expressiveness (0.30), -caution (0.20), symbolic (0.10)
    friendly_alignment = (
        0.40 * warmth_signal +
        0.30 * expressiveness +
        0.20 * (1.0 - caution_signal) +
        0.10 * symbolic_richness
    )
    alignment_scores["friendly"] = _clamp(friendly_alignment)

    # REGULATOR: High caution, high structure, low expressiveness
    # Weights: caution (0.35), structure (0.30), practical (0.25), -expressiveness (0.10)
    regulator_alignment = (
        0.35 * caution_signal +
        0.30 * structure_preference +
        0.25 * practical_grounding +
        0.10 * (1.0 - expressiveness)
    )
    alignment_scores["regulator"] = _clamp(regulator_alignment)

    # NEUTRAL: Balanced all traits (always moderate alignment)
    # Compute as geometric mean of all signals to penalize extremes
    neutral_alignment = (
        symbolic_richness * practical_grounding * warmth_signal *
        structure_preference * expressiveness
    ) ** 0.2  # 5th root for geometric mean
    alignment_scores["neutral"] = _clamp(neutral_alignment * 0.6 + 0.3)  # Bias toward [0.3, 0.9]

    # ========================================================================
    # STEP 4: Compute schema confidence
    # ========================================================================

    # Quality factor: based on coherence and stability
    quality_factor = (
        (coherence_score if coherence_score is not None else 0.7) +
        (consciousness_stability_index if consciousness_stability_index is not None else 0.7)
    ) / 2.0

    # Overall confidence
    schema_confidence = _clamp(availability_factor * quality_factor)

    # ========================================================================
    # STEP 5: Compute schema drift and stability
    # ========================================================================

    schema_drift = 0.0
    schema_stability = 1.0

    if previous_snapshot is not None:
        # Compute L2 distance between current and previous alignment scores
        prev_scores = previous_snapshot.schema_alignment_scores

        if prev_scores:
            squared_diffs = []
            for persona_id in alignment_scores:
                curr_score = alignment_scores[persona_id]
                prev_score = prev_scores.get(persona_id, 0.5)
                squared_diffs.append((curr_score - prev_score) ** 2)

            # L2 distance, normalized by sqrt(n)
            if squared_diffs:
                schema_drift = math.sqrt(sum(squared_diffs) / len(squared_diffs))
                schema_drift = _clamp(schema_drift)
                schema_stability = _clamp(1.0 - schema_drift)

    # ========================================================================
    # STEP 6: Generate persona schema candidate ranking
    # ========================================================================

    # Sort personas by alignment score (descending)
    ranking = sorted(
        alignment_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # ========================================================================
    # STEP 7: Generate schema tags
    # ========================================================================

    tags = []

    # High alignment tags (threshold: >= 0.70)
    for persona_id, score in ranking[:2]:  # Top 2 personas
        if score >= 0.70:
            tags.append(f"HIGH_{persona_id.upper()}_ALIGNMENT")

    # Low alignment tags (threshold: all < 0.40)
    if all(score < 0.40 for score in alignment_scores.values()):
        tags.append("LOW_SCHEMA_ALIGNMENT")

    # Schema drift tags
    if schema_drift >= 0.50:
        tags.append("SCHEMA_DRIFT_CAUTION")
    elif schema_drift <= 0.20:
        tags.append("STABLE_SCHEMA_FIT")

    # Schema confidence tags
    if schema_confidence >= 0.75:
        tags.append("HIGH_SCHEMA_CONFIDENCE")
    elif schema_confidence <= 0.40:
        tags.append("LOW_SCHEMA_CONFIDENCE")

    # Dominant trait tags
    if symbolic_richness >= 0.70:
        tags.append("SYMBOLIC_DOMINANT")
    if practical_grounding >= 0.70:
        tags.append("PRACTICAL_DOMINANT")
    if caution_signal >= 0.60:
        tags.append("CAUTION_ELEVATED")

    # ========================================================================
    # STEP 8: Assemble and return snapshot
    # ========================================================================

    return SchemaAdaptiveRoutingSnapshot(
        schema_alignment_scores=alignment_scores,
        schema_confidence=schema_confidence,
        schema_drift=schema_drift,
        schema_stability=schema_stability,
        persona_schema_candidate_ranking=ranking,
        schema_tags=tags,
    )


# Public API
__all__ = [
    'SchemaAdaptiveRoutingSnapshot',
    'compute_schema_adaptive_map',
]
