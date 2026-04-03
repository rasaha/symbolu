"""
Symbolic Harmonization Formula (SHF) v1.0 - Phase 27

Deterministic, zero-LLM formula that measures alignment across three symbolic dimensions:
  1. Symbolic Layer: Meaning vectors / archetype consistency
  2. Practical Layer: Factual grounding / structure
  3. Mirror Layer: Contradictions, tensions, reflective coherence

This formula harmonizes symbolic, practical, and mirror layers with Guna/Kosha resonance
and semantic integrity, producing a unified symbolic resonance measure.

SHF is designed for:
  • Dashboard visualization & sparklines
  • Session analytics & summaries
  • Analytics-only observation (not for pipeline control)

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Graceful degradation: Returns None if core inputs missing
"""

from dataclasses import dataclass, field
from typing import List, Optional
import math


@dataclass
class SymbolicHarmonizationSnapshot:
    """
    Immutable snapshot of symbolic harmonization formula computation.

    Fields:
        symbolic_alignment: Alignment between symbolic and practical layers [0.0, 1.0]
        mirror_alignment: Alignment between symbolic and mirror layers [0.0, 1.0]
        guna_symbolic_resonance: Guna resonance projected into symbolic layer [0.0, 1.0]
        kosha_symbolic_resonance: Kosha resonance projected into symbolic layer [0.0, 1.0]
        semantic_integrity_weight: Normalized semantic integrity influence [0.0, 1.0]
        symbolic_harmonization_index: Final combined score [0.0, 1.0]
        harmonization_entropy: Entropy of component contributions [0.0, 1.0]
        notes: Deterministic diagnostic tags
    """

    symbolic_alignment: float  # Symbolic ↔ Practical alignment [0.0, 1.0]
    mirror_alignment: float  # Symbolic ↔ Mirror resonance [0.0, 1.0]
    guna_symbolic_resonance: float  # Guna projected to symbolic [0.0, 1.0]
    kosha_symbolic_resonance: float  # Kosha projected to symbolic [0.0, 1.0]
    semantic_integrity_weight: float  # Semantic integrity influence [0.0, 1.0]
    symbolic_harmonization_index: float  # SHI final score [0.0, 1.0]
    harmonization_entropy: float  # Component entropy [0.0, 1.0]
    notes: List[str] = field(default_factory=list)


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


def _compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        vec_a: First vector
        vec_b: Second vector

    Returns:
        float: Cosine similarity [0.0, 1.0], or 0.0 if either vector is zero
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    # Compute dot product
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))

    # Compute magnitudes
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))

    # Handle zero magnitude
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0

    # Cosine similarity is in [-1.0, 1.0], normalize to [0.0, 1.0]
    cosine_sim = dot_product / (mag_a * mag_b)
    normalized = (cosine_sim + 1.0) / 2.0

    return _clamp(normalized, 0.0, 1.0)


def _compute_shannon_entropy(component_weights: List[float]) -> float:
    """
    Compute Shannon entropy of component weights, normalized to [0.0, 1.0].

    Args:
        component_weights: List of component weights (must sum to ~1.0)

    Returns:
        float: Entropy [0.0, 1.0], where 0 = focused, 1 = uniform
    """
    if not component_weights:
        return 0.0

    n = len(component_weights)
    if n <= 1:
        return 0.0

    # Filter out zero weights
    non_zero_weights = [w for w in component_weights if w > 0.0]
    if not non_zero_weights:
        return 0.0

    # Compute Shannon entropy: H = -Σ(p_i * log2(p_i))
    entropy_raw = 0.0
    for weight in non_zero_weights:
        if weight > 0.0:
            entropy_raw -= weight * math.log2(weight)

    # Normalize by max entropy (log2(N))
    max_entropy = math.log2(n)
    entropy = entropy_raw / max_entropy if max_entropy > 0 else 0.0

    return _clamp(entropy, 0.0, 1.0)


def compute_symbolic_harmonization(
    *,
    symbolic_layer_vector: Optional[List[float]] = None,
    practical_layer_vector: Optional[List[float]] = None,
    mirror_layer_vector: Optional[List[float]] = None,
    guna_resonance: Optional[float] = None,
    kosha_resonance: Optional[float] = None,
    semantic_integrity: Optional[float] = None,
) -> Optional[SymbolicHarmonizationSnapshot]:
    """
    Compute Symbolic Harmonization Formula (SHF) v1.0.

    This formula measures alignment across symbolic, practical, and mirror layers,
    harmonized with Guna/Kosha resonance and semantic integrity.

    The result is a symbolic harmonization index (SHI) computed using canonical
    v1.0 coefficients:

        SHI = clamp(
            0.30 * symbolic_alignment +
            0.20 * mirror_alignment +
            0.20 * semantic_integrity +
            0.15 * guna_symbolic_resonance +
            0.15 * kosha_symbolic_resonance,
            0.0, 1.0
        )

    Args:
        symbolic_layer_vector: Symbolic layer representation (e.g., archetype activations)
        practical_layer_vector: Practical layer representation (e.g., fact/structure vector)
        mirror_layer_vector: Mirror layer representation (e.g., contradiction/tension vector)
        guna_resonance: Guna resonance index [0.0, 1.0]
        kosha_resonance: Kosha resonance index [0.0, 1.0]
        semantic_integrity: Semantic integrity score [0.0, 1.0]

    Returns:
        SymbolicHarmonizationSnapshot or None if insufficient data

    Graceful Degradation:
        Returns None if we lack at least TWO of the three layer vectors OR
        if we have no resonance/semantic metrics.
    """
    notes = []

    # ========================================================================
    # STEP 1: CHECK CORE INPUT AVAILABILITY (Graceful Degradation)
    # ========================================================================

    # Count available layer vectors
    layers_available = sum([
        symbolic_layer_vector is not None and len(symbolic_layer_vector) > 0,
        practical_layer_vector is not None and len(practical_layer_vector) > 0,
        mirror_layer_vector is not None and len(mirror_layer_vector) > 0,
    ])

    # Check if we have at least one resonance or semantic metric
    metrics_available = any([
        guna_resonance is not None,
        kosha_resonance is not None,
        semantic_integrity is not None,
    ])

    # Require at least TWO layer vectors AND at least one metric
    if layers_available < 2 or not metrics_available:
        # Insufficient data for SHF computation
        return None

    # ========================================================================
    # STEP 2: COMPUTE LAYER ALIGNMENTS (Cosine Similarity)
    # ========================================================================

    # Symbolic ↔ Practical alignment
    if symbolic_layer_vector and practical_layer_vector:
        symbolic_alignment = _compute_cosine_similarity(
            symbolic_layer_vector, practical_layer_vector
        )
        if symbolic_alignment >= 0.75:
            notes.append("symbolic_practical_aligned")
        elif symbolic_alignment <= 0.35:
            notes.append("symbolic_practical_misaligned")
    else:
        # Use neutral fallback if one vector is missing
        symbolic_alignment = 0.5
        notes.append("symbolic_practical_fallback")

    # Symbolic ↔ Mirror alignment
    if symbolic_layer_vector and mirror_layer_vector:
        mirror_alignment = _compute_cosine_similarity(
            symbolic_layer_vector, mirror_layer_vector
        )
        if mirror_alignment >= 0.70:
            notes.append("symbolic_mirror_resonant")
        elif mirror_alignment <= 0.30:
            notes.append("symbolic_mirror_divergent")
    else:
        # Use neutral fallback if one vector is missing
        mirror_alignment = 0.5
        notes.append("symbolic_mirror_fallback")

    # ========================================================================
    # STEP 3: PROJECT GUNA/KOSHA RESONANCE INTO SYMBOLIC LAYER
    # ========================================================================

    # Guna resonance → symbolic projection (direct passthrough with normalization)
    if guna_resonance is not None:
        guna_symbolic_resonance = _clamp(guna_resonance)
        if guna_symbolic_resonance >= 0.75:
            notes.append("guna_symbolic_strong")
    else:
        guna_symbolic_resonance = 0.5
        notes.append("guna_symbolic_fallback")

    # Kosha resonance → symbolic projection (direct passthrough with normalization)
    if kosha_resonance is not None:
        kosha_symbolic_resonance = _clamp(kosha_resonance)
        if kosha_symbolic_resonance >= 0.75:
            notes.append("kosha_symbolic_strong")
    else:
        kosha_symbolic_resonance = 0.5
        notes.append("kosha_symbolic_fallback")

    # ========================================================================
    # STEP 4: NORMALIZE SEMANTIC INTEGRITY WEIGHT
    # ========================================================================

    if semantic_integrity is not None:
        semantic_integrity_weight = _clamp(semantic_integrity)
        if semantic_integrity_weight >= 0.70:
            notes.append("semantic_integrity_strong")
        elif semantic_integrity_weight <= 0.35:
            notes.append("semantic_integrity_weak")
    else:
        semantic_integrity_weight = 0.5
        notes.append("semantic_integrity_fallback")

    # ========================================================================
    # STEP 5: COMPUTE SYMBOLIC HARMONIZATION INDEX (SHI)
    # ========================================================================

    # Canonical v1.0 coefficients
    shi = _clamp(
        0.30 * symbolic_alignment +
        0.20 * mirror_alignment +
        0.20 * semantic_integrity_weight +
        0.15 * guna_symbolic_resonance +
        0.15 * kosha_symbolic_resonance,
        0.0, 1.0
    )

    # ========================================================================
    # STEP 6: COMPUTE HARMONIZATION ENTROPY
    # ========================================================================

    # Component weights for entropy calculation (using canonical coefficients)
    component_weights = [
        0.30 * symbolic_alignment,
        0.20 * mirror_alignment,
        0.20 * semantic_integrity_weight,
        0.15 * guna_symbolic_resonance,
        0.15 * kosha_symbolic_resonance,
    ]

    # Normalize component weights to sum to 1.0
    total_weight = sum(component_weights)
    if total_weight > 0.0:
        normalized_components = [w / total_weight for w in component_weights]
    else:
        normalized_components = [0.2] * 5  # Uniform fallback

    harmonization_entropy = _compute_shannon_entropy(normalized_components)

    # ========================================================================
    # STEP 7: GENERATE DIAGNOSTIC NOTES
    # ========================================================================

    # SHI level notes
    if shi >= 0.75:
        notes.append("high_symbolic_harmonization")
    elif shi >= 0.50:
        notes.append("medium_symbolic_harmonization")
    else:
        notes.append("low_symbolic_harmonization")

    # Entropy notes
    if harmonization_entropy < 0.35:
        notes.append("focused_harmonization")
    elif harmonization_entropy >= 0.65:
        notes.append("diffuse_harmonization")

    # Check for convergence (all components high)
    if (symbolic_alignment >= 0.65 and mirror_alignment >= 0.65 and
        semantic_integrity_weight >= 0.65 and guna_symbolic_resonance >= 0.65 and
        kosha_symbolic_resonance >= 0.65):
        notes.append("harmonization_converging")

    # Check for divergence (any component very low)
    if (symbolic_alignment <= 0.35 or mirror_alignment <= 0.35 or
        semantic_integrity_weight <= 0.35):
        notes.append("harmonization_diverging")

    # Check for symbolic layer dominance
    if symbolic_alignment >= 0.75 and mirror_alignment >= 0.70:
        notes.append("symbolic_layer_dominant")

    # ========================================================================
    # STEP 8: RETURN SNAPSHOT
    # ========================================================================

    return SymbolicHarmonizationSnapshot(
        symbolic_alignment=symbolic_alignment,
        mirror_alignment=mirror_alignment,
        guna_symbolic_resonance=guna_symbolic_resonance,
        kosha_symbolic_resonance=kosha_symbolic_resonance,
        semantic_integrity_weight=semantic_integrity_weight,
        symbolic_harmonization_index=shi,
        harmonization_entropy=harmonization_entropy,
        notes=sorted(set(notes)),  # Deduplicate and sort for determinism
    )
