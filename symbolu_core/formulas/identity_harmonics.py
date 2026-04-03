"""
Identity Harmonics Layer (IHL) v1.0 - Phase 34

Deterministic, zero-LLM formula that computes identity resonance patterns across
semantic, emotional, symbolic, and temporal dimensions.

This formula produces three identity-resonance harmonics:
  1. Core Identity Harmonic (CIH): Stability of identity signals across turns
  2. Adaptive Identity Harmonic (AIH): Ability to shift identity expression coherently
  3. Relational Identity Harmonic (RIH): Resonance between persona tone + symbolic harmonization

IHL is designed for:
  • Persona tone micro-adjustments (±0.02 max)
  • Analytics & diagnostics
  • Session summaries
  • Observation-only (not for pipeline control)

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Tone-level only: NEVER semantic changes (bounded ±0.02)
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Graceful degradation: Returns None if core inputs missing
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import math


@dataclass
class IdentityHarmonicsSnapshot:
    """
    Immutable snapshot of identity harmonics formula computation.

    Fields:
        core_identity_harmonic (CIH): Stability of identity signals across turns [0.0, 1.0]
        adaptive_identity_harmonic (AIH): Ability to shift identity coherently [0.0, 1.0]
        relational_identity_harmonic (RIH): Resonance between persona and symbolic layers [0.0, 1.0]
        identity_harmonics_index: Combined overall harmonic score [0.0, 1.0]
        identity_entropy: Entropy of harmonic components [0.0, 1.0]
        identity_stability_score: Derived stability measure [0.0, 1.0]
        identity_flexibility_score: Derived flexibility measure [0.0, 1.0]
        notes: Deterministic diagnostic tags
    """

    core_identity_harmonic: float  # CIH: Identity stability [0.0, 1.0]
    adaptive_identity_harmonic: float  # AIH: Identity adaptability [0.0, 1.0]
    relational_identity_harmonic: float  # RIH: Persona-symbolic resonance [0.0, 1.0]
    identity_harmonics_index: float  # IHI: Combined overall score [0.0, 1.0]
    identity_entropy: float  # Component entropy [0.0, 1.0]
    identity_stability_score: float  # Stability derived metric [0.0, 1.0]
    identity_flexibility_score: float  # Flexibility derived metric [0.0, 1.0]
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


def _safe_get(value: Optional[float], default: float = 0.5) -> float:
    """
    Safely extract float value with fallback.

    Args:
        value: Optional float value
        default: Default value if None (default 0.5)

    Returns:
        float: Value or default
    """
    if value is None:
        return default
    return _clamp(value)


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


def _compute_variance(values: List[float]) -> float:
    """
    Compute variance of a list of values.

    Args:
        values: List of float values

    Returns:
        float: Variance [0.0, ∞)
    """
    if not values or len(values) < 2:
        return 0.0

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)

    return variance


def compute_identity_harmonics(
    *,
    # Semantic + symbolic signals (identity core)
    semantic_integrity: Optional[float] = None,
    symbolic_harmonization_index: Optional[float] = None,
    consciousness_order_index: Optional[float] = None,
    # Temporal + adaptive signals (identity flexibility)
    cognitive_drift_v3: Optional[float] = None,
    temporal_entropy_volatility: Optional[float] = None,
    loop_alignment: Optional[float] = None,
    # Persona + relational signals (identity expression)
    persona_drift_score: Optional[float] = None,
    guna_resonance_index: Optional[float] = None,
    kosha_resonance_index: Optional[float] = None,
    # Historical context (for stability computation)
    semantic_integrity_history: Optional[List[float]] = None,
    symbolic_harmonization_history: Optional[List[float]] = None,
    cognitive_drift_history: Optional[List[float]] = None,
) -> Optional[IdentityHarmonicsSnapshot]:
    """
    Compute Identity Harmonics Layer (IHL) v1.0.

    This formula measures identity resonance across three harmonics:
        1. Core Identity Harmonic (CIH): Stability of identity signals
        2. Adaptive Identity Harmonic (AIH): Ability to shift identity coherently
        3. Relational Identity Harmonic (RIH): Persona-symbolic resonance

    The result is an Identity Harmonics Index (IHI) computed using canonical
    v1.0 coefficients:

        CIH = clamp(
            0.40 * semantic_integrity +
            0.35 * symbolic_harmonization_index +
            0.25 * consciousness_order_index,
            0.0, 1.0
        )

        AIH = clamp(
            0.40 * (1.0 - cognitive_drift_v3) +
            0.30 * (1.0 - temporal_entropy_volatility) +
            0.30 * loop_alignment,
            0.0, 1.0
        )

        RIH = clamp(
            0.40 * (1.0 - persona_drift_score) +
            0.30 * guna_resonance_index +
            0.30 * kosha_resonance_index,
            0.0, 1.0
        )

        IHI = clamp(
            0.40 * CIH +
            0.30 * AIH +
            0.30 * RIH,
            0.0, 1.0
        )

    Args:
        semantic_integrity: Semantic integrity score [0.0, 1.0]
        symbolic_harmonization_index: Symbolic harmonization score [0.0, 1.0]
        consciousness_order_index: Consciousness order index [0.0, 1.0]
        cognitive_drift_v3: Cognitive drift v3 score [0.0, 1.0]
        temporal_entropy_volatility: Temporal entropy volatility [0.0, 1.0]
        loop_alignment: Mirror-time loop alignment [0.0, 1.0]
        persona_drift_score: Persona drift score [0.0, 1.0]
        guna_resonance_index: Guna resonance index [0.0, 1.0]
        kosha_resonance_index: Kosha resonance index [0.0, 1.0]
        semantic_integrity_history: Historical semantic integrity values
        symbolic_harmonization_history: Historical symbolic harmonization values
        cognitive_drift_history: Historical cognitive drift values

    Returns:
        IdentityHarmonicsSnapshot or None if insufficient data

    Graceful Degradation:
        Returns None if we lack at least ONE signal from each harmonic category.
    """
    notes = []

    # ========================================================================
    # STEP 1: CHECK CORE INPUT AVAILABILITY (Graceful Degradation)
    # ========================================================================

    # Check for at least one signal from each harmonic category
    has_core_signal = any([
        semantic_integrity is not None,
        symbolic_harmonization_index is not None,
        consciousness_order_index is not None,
    ])

    has_adaptive_signal = any([
        cognitive_drift_v3 is not None,
        temporal_entropy_volatility is not None,
        loop_alignment is not None,
    ])

    has_relational_signal = any([
        persona_drift_score is not None,
        guna_resonance_index is not None,
        kosha_resonance_index is not None,
    ])

    # Require at least one signal from each category
    if not (has_core_signal and has_adaptive_signal and has_relational_signal):
        # Insufficient data for IHL computation
        return None

    # ========================================================================
    # STEP 2: COMPUTE CORE IDENTITY HARMONIC (CIH)
    # ========================================================================

    # Extract core signals with safe fallbacks
    sem_int = _safe_get(semantic_integrity, 0.5)
    sym_harm = _safe_get(symbolic_harmonization_index, 0.5)
    cons_order = _safe_get(consciousness_order_index, 0.5)

    # Check if we're using fallbacks
    if semantic_integrity is None:
        notes.append("semantic_integrity_fallback")
    if symbolic_harmonization_index is None:
        notes.append("symbolic_harmonization_fallback")
    if consciousness_order_index is None:
        notes.append("consciousness_order_fallback")

    # Compute CIH with canonical v1.0 coefficients
    cih = _clamp(
        0.40 * sem_int +
        0.35 * sym_harm +
        0.25 * cons_order,
        0.0, 1.0
    )

    # ========================================================================
    # STEP 3: COMPUTE ADAPTIVE IDENTITY HARMONIC (AIH)
    # ========================================================================

    # Extract adaptive signals with safe fallbacks
    cog_drift = _safe_get(cognitive_drift_v3, 0.5)
    temp_entropy = _safe_get(temporal_entropy_volatility, 0.5)
    loop_align = _safe_get(loop_alignment, 0.5)

    # Check if we're using fallbacks
    if cognitive_drift_v3 is None:
        notes.append("cognitive_drift_fallback")
    if temporal_entropy_volatility is None:
        notes.append("temporal_entropy_fallback")
    if loop_alignment is None:
        notes.append("loop_alignment_fallback")

    # Compute AIH (invert drift/volatility signals)
    aih = _clamp(
        0.40 * (1.0 - cog_drift) +
        0.30 * (1.0 - temp_entropy) +
        0.30 * loop_align,
        0.0, 1.0
    )

    # ========================================================================
    # STEP 4: COMPUTE RELATIONAL IDENTITY HARMONIC (RIH)
    # ========================================================================

    # Extract relational signals with safe fallbacks
    persona_drift = _safe_get(persona_drift_score, 0.5)
    guna_res = _safe_get(guna_resonance_index, 0.5)
    kosha_res = _safe_get(kosha_resonance_index, 0.5)

    # Check if we're using fallbacks
    if persona_drift_score is None:
        notes.append("persona_drift_fallback")
    if guna_resonance_index is None:
        notes.append("guna_resonance_fallback")
    if kosha_resonance_index is None:
        notes.append("kosha_resonance_fallback")

    # Compute RIH (invert persona drift)
    rih = _clamp(
        0.40 * (1.0 - persona_drift) +
        0.30 * guna_res +
        0.30 * kosha_res,
        0.0, 1.0
    )

    # ========================================================================
    # STEP 5: COMPUTE IDENTITY HARMONICS INDEX (IHI)
    # ========================================================================

    # Canonical v1.0 coefficients for overall index
    ihi = _clamp(
        0.40 * cih +
        0.30 * aih +
        0.30 * rih,
        0.0, 1.0
    )

    # ========================================================================
    # STEP 6: COMPUTE IDENTITY ENTROPY
    # ========================================================================

    # Component weights for entropy calculation (using canonical coefficients)
    component_weights = [
        0.40 * cih,
        0.30 * aih,
        0.30 * rih,
    ]

    # Normalize component weights to sum to 1.0
    total_weight = sum(component_weights)
    if total_weight > 0.0:
        normalized_components = [w / total_weight for w in component_weights]
    else:
        normalized_components = [0.33, 0.33, 0.34]  # Uniform fallback

    identity_entropy = _compute_shannon_entropy(normalized_components)

    # ========================================================================
    # STEP 7: COMPUTE DERIVED STABILITY & FLEXIBILITY SCORES
    # ========================================================================

    # Identity stability: Combines CIH with historical variance (if available)
    if semantic_integrity_history and len(semantic_integrity_history) >= 3:
        sem_variance = _compute_variance(semantic_integrity_history)
        sem_stability = 1.0 - min(sem_variance * 2.0, 1.0)  # Scale variance to [0,1]
        identity_stability_score = _clamp(0.6 * cih + 0.4 * sem_stability)
        notes.append("stability_with_history")
    else:
        # No history, use CIH directly
        identity_stability_score = cih
        notes.append("stability_no_history")

    # Identity flexibility: Combines AIH with RIH
    identity_flexibility_score = _clamp(0.6 * aih + 0.4 * rih)

    # ========================================================================
    # STEP 8: GENERATE DIAGNOSTIC NOTES
    # ========================================================================

    # CIH level notes
    if cih >= 0.75:
        notes.append("IDENTITY_STABLE")
    elif cih >= 0.50:
        notes.append("IDENTITY_MODERATE")
    else:
        notes.append("IDENTITY_FRAGILE")

    # AIH level notes
    if aih >= 0.70:
        notes.append("IDENTITY_SHIFTING")
    elif aih <= 0.35:
        notes.append("IDENTITY_RIGID")

    # RIH level notes
    if rih >= 0.70:
        notes.append("IDENTITY_RESILIENT")
    elif rih <= 0.35:
        notes.append("IDENTITY_DISCONNECTED")

    # Overall IHI level notes
    if ihi >= 0.75:
        notes.append("HARMONIC_ALIGNMENT_HIGH")
    elif ihi >= 0.50:
        notes.append("HARMONIC_ALIGNMENT_MEDIUM")
    else:
        notes.append("HARMONIC_ALIGNMENT_LOW")

    # Entropy notes
    if identity_entropy < 0.35:
        notes.append("focused_identity_harmonics")
    elif identity_entropy >= 0.65:
        notes.append("diffuse_identity_harmonics")

    # Check for convergence (all harmonics high)
    if cih >= 0.70 and aih >= 0.70 and rih >= 0.70:
        notes.append("identity_harmonics_converging")

    # Check for divergence (any harmonic very low)
    if cih <= 0.30 or aih <= 0.30 or rih <= 0.30:
        notes.append("identity_harmonics_diverging")

    # Stability + flexibility balance notes
    if identity_stability_score >= 0.70 and identity_flexibility_score >= 0.70:
        notes.append("balanced_identity_profile")
    elif identity_stability_score >= 0.70 and identity_flexibility_score < 0.40:
        notes.append("stable_but_rigid_identity")
    elif identity_stability_score < 0.40 and identity_flexibility_score >= 0.70:
        notes.append("flexible_but_unstable_identity")

    # ========================================================================
    # STEP 9: RETURN SNAPSHOT
    # ========================================================================

    return IdentityHarmonicsSnapshot(
        core_identity_harmonic=cih,
        adaptive_identity_harmonic=aih,
        relational_identity_harmonic=rih,
        identity_harmonics_index=ihi,
        identity_entropy=identity_entropy,
        identity_stability_score=identity_stability_score,
        identity_flexibility_score=identity_flexibility_score,
        notes=sorted(set(notes)),  # Deduplicate and sort for determinism
    )
