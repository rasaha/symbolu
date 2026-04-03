"""
Predictive Persona Drift Model (PPDM) v1.0 - Phase 35

Deterministic, zero-LLM formula that predicts future persona drift direction and magnitude
using the full identity + coherence + resonance + entropy signal stack from Symbol-U v3.0.

This formula produces predictive drift metrics:
  1. Drift Magnitude Prediction (DMP): Estimated future drift intensity [0.0, 1.0]
  2. Drift Direction Score (DDS): Predicted drift direction (structure, warmth, grounding)
  3. Drift Stability Score (DSS): Confidence in drift trajectory [0.0, 1.0]
  4. Drift Likelihood Band: LOW / MEDIUM / HIGH classification
  5. Diagnostic Tags: DRIFT_RISK_RISING, HARMONICS_INFLUENCE_HIGH, etc.

PPDM is designed for:
  • Tone-only micro-adjustments (±0.02 max total)
  • Predictive analytics & diagnostics
  • Session drift forecasting
  • Observation-only (not for pipeline control)

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Tone-level only: NEVER semantic changes (bounded ±0.02)
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Graceful degradation: Returns None if insufficient data
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import math


@dataclass
class PredictivePersonaDriftSnapshot:
    """
    Immutable snapshot of predictive persona drift formula computation.

    Fields:
        drift_magnitude_prediction (DMP): Predicted future drift intensity [0.0, 1.0]
        drift_direction_scores: Direction components (structure, warmth, grounding) [0.0, 1.0]
        drift_stability_score (DSS): Confidence in drift trajectory [0.0, 1.0]
        drift_likelihood_band: Classification ("LOW", "MEDIUM", "HIGH")
        predicted_drift_horizon: Turns ahead for prediction (typically 3-5)
        harmonic_influence_weight: Weight of identity harmonics on prediction [0.0, 1.0]
        entropy_volatility_weight: Weight of entropy signals on prediction [0.0, 1.0]
        drift_momentum_score: Velocity of drift change [0.0, 1.0]
        notes: Deterministic diagnostic tags
    """

    drift_magnitude_prediction: float  # DMP: Predicted drift intensity [0.0, 1.0]
    drift_direction_scores: Dict[str, float]  # Direction components [0.0, 1.0]
    drift_stability_score: float  # DSS: Trajectory confidence [0.0, 1.0]
    drift_likelihood_band: str  # "LOW", "MEDIUM", "HIGH"
    predicted_drift_horizon: int  # Turns ahead (3-5)
    harmonic_influence_weight: float  # Identity harmonics weight [0.0, 1.0]
    entropy_volatility_weight: float  # Entropy signal weight [0.0, 1.0]
    drift_momentum_score: float  # Drift velocity [0.0, 1.0]
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


def _compute_trend_slope(values: List[float]) -> float:
    """
    Compute linear trend slope using simple linear regression.

    Args:
        values: List of float values (time series)

    Returns:
        float: Slope of trend line
    """
    if not values or len(values) < 2:
        return 0.0

    n = len(values)
    x = list(range(n))  # Time indices
    y = values

    # Compute means
    x_mean = sum(x) / n
    y_mean = sum(y) / n

    # Compute slope: Σ((x - x_mean) * (y - y_mean)) / Σ((x - x_mean)^2)
    numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return 0.0

    slope = numerator / denominator
    return slope


def harmonic_weighting(
    *,
    cih: float,
    aih: float,
    rih: float,
    identity_stability: float,
    identity_flexibility: float,
) -> float:
    """
    Compute harmonic influence weight on drift prediction.

    High identity harmonics (especially CIH + stability) dampen predicted drift.
    Low identity harmonics amplify predicted drift.

    Args:
        cih: Core Identity Harmonic [0.0, 1.0]
        aih: Adaptive Identity Harmonic [0.0, 1.0]
        rih: Relational Identity Harmonic [0.0, 1.0]
        identity_stability: Identity stability score [0.0, 1.0]
        identity_flexibility: Identity flexibility score [0.0, 1.0]

    Returns:
        float: Harmonic influence weight [0.0, 1.0]
    """
    # Stability-focused weighting: CIH and stability are most important
    # High stability → low drift influence from harmonics
    # Low stability → high drift influence from harmonics

    stability_factor = 0.5 * cih + 0.3 * identity_stability + 0.2 * aih

    # Invert: high stability = low harmonic influence on drift prediction
    harmonic_influence = _clamp(1.0 - stability_factor, 0.0, 1.0)

    return harmonic_influence


def normalized_entropy_rescale(
    *,
    temporal_entropy_volatility: float,
    resonance_weighting_entropy: float,
    identity_entropy: float,
) -> float:
    """
    Compute normalized entropy volatility weight on drift prediction.

    High entropy volatility amplifies predicted drift.
    Low entropy volatility dampens predicted drift.

    Args:
        temporal_entropy_volatility: Temporal entropy volatility [0.0, 1.0]
        resonance_weighting_entropy: Resonance weighting entropy [0.0, 1.0]
        identity_entropy: Identity harmonics entropy [0.0, 1.0]

    Returns:
        float: Normalized entropy weight [0.0, 1.0]
    """
    # Weighted entropy blend
    entropy_blend = (
        0.45 * temporal_entropy_volatility +
        0.35 * resonance_weighting_entropy +
        0.20 * identity_entropy
    )

    return _clamp(entropy_blend, 0.0, 1.0)


def drift_direction_solver(
    *,
    semantic_integrity: float,
    symbolic_harmonization: float,
    cognitive_drift: float,
    persona_drift: float,
    guna_resonance: float,
    kosha_resonance: float,
) -> Dict[str, float]:
    """
    Solve for predicted drift direction components.

    Three directional tendencies:
      1. toward_structure: Drift toward clarity, logic, precision
      2. toward_warmth: Drift toward empathy, emotion, connection
      3. toward_grounding: Drift toward rootedness, stability, presence

    Args:
        semantic_integrity: Semantic integrity score [0.0, 1.0]
        symbolic_harmonization: Symbolic harmonization index [0.0, 1.0]
        cognitive_drift: Cognitive drift v3 score [0.0, 1.0]
        persona_drift: Persona drift score [0.0, 1.0]
        guna_resonance: Guna resonance index [0.0, 1.0]
        kosha_resonance: Kosha resonance index [0.0, 1.0]

    Returns:
        Dict[str, float]: Direction scores {"toward_structure", "toward_warmth", "toward_grounding"}
    """
    # toward_structure: High semantic integrity + low cognitive drift → structure
    # Indicates drift toward clarity and logical coherence
    toward_structure = _clamp(
        0.5 * semantic_integrity +
        0.3 * (1.0 - cognitive_drift) +
        0.2 * symbolic_harmonization,
        0.0, 1.0
    )

    # toward_warmth: High persona engagement + relational resonance → warmth
    # Indicates drift toward empathy and emotional connection
    toward_warmth = _clamp(
        0.4 * (1.0 - persona_drift) +
        0.3 * guna_resonance +
        0.3 * kosha_resonance,
        0.0, 1.0
    )

    # toward_grounding: Balanced harmonization + low drift → grounding
    # Indicates drift toward stability and rootedness
    toward_grounding = _clamp(
        0.4 * symbolic_harmonization +
        0.3 * (1.0 - cognitive_drift) +
        0.3 * kosha_resonance,
        0.0, 1.0
    )

    return {
        "toward_structure": toward_structure,
        "toward_warmth": toward_warmth,
        "toward_grounding": toward_grounding,
    }


def stability_curve(
    *,
    drift_variance: float,
    harmonic_stability: float,
    entropy_volatility: float,
) -> float:
    """
    Compute drift stability score (confidence in trajectory).

    High stability = confident prediction (smooth drift trajectory)
    Low stability = uncertain prediction (volatile drift trajectory)

    Args:
        drift_variance: Variance of recent drift values [0.0, ∞)
        harmonic_stability: Identity stability from harmonics [0.0, 1.0]
        entropy_volatility: Normalized entropy volatility [0.0, 1.0]

    Returns:
        float: Drift stability score [0.0, 1.0]
    """
    # Invert variance to stability (low variance = high stability)
    # Scale variance by 2.0 to normalize to [0, 1] range
    variance_stability = _clamp(1.0 - min(drift_variance * 2.0, 1.0), 0.0, 1.0)

    # Invert entropy volatility (low volatility = high stability)
    entropy_stability = _clamp(1.0 - entropy_volatility, 0.0, 1.0)

    # Weighted stability blend
    stability = _clamp(
        0.40 * variance_stability +
        0.35 * harmonic_stability +
        0.25 * entropy_stability,
        0.0, 1.0
    )

    return stability


def compute_predictive_persona_drift(
    *,
    # Identity Harmonics (Phase 34)
    core_identity_harmonic: Optional[float] = None,
    adaptive_identity_harmonic: Optional[float] = None,
    relational_identity_harmonic: Optional[float] = None,
    identity_stability_score: Optional[float] = None,
    identity_flexibility_score: Optional[float] = None,
    identity_entropy: Optional[float] = None,
    # Semantic + Cognitive signals (Phase 17)
    semantic_integrity: Optional[float] = None,
    cognitive_drift_v3: Optional[float] = None,
    # Temporal Entropy (Phase 18)
    temporal_entropy_volatility: Optional[float] = None,
    # Drift Fusion (Phase 19) - if available
    drift_fusion_index: Optional[float] = None,
    # Resonance Weighting (Phase 24)
    resonance_weighting_entropy: Optional[float] = None,
    # Symbolic Harmonization (Phase 27)
    symbolic_harmonization_index: Optional[float] = None,
    # Coherence signals
    coherence_fused: Optional[float] = None,
    unified_consciousness_order: Optional[float] = None,
    # Persona + Relational signals
    persona_drift_score: Optional[float] = None,
    guna_resonance_index: Optional[float] = None,
    kosha_resonance_index: Optional[float] = None,
    # Historical context (for trend analysis)
    cognitive_drift_history: Optional[List[float]] = None,
    persona_drift_history: Optional[List[float]] = None,
    coherence_fused_history: Optional[List[float]] = None,
    identity_stability_history: Optional[List[float]] = None,
) -> Optional[PredictivePersonaDriftSnapshot]:
    """
    Compute Predictive Persona Drift Model (PPDM) v1.0.

    This formula predicts future persona drift direction and magnitude using the
    full Symbol-U v3.0 signal stack:
      - Identity Harmonics (Phase 34): CIH, AIH, RIH, stability, flexibility, entropy
      - Semantic Integrity + Cognitive Drift v3 (Phase 17)
      - Temporal Entropy Differential (Phase 18)
      - Resonance Weighting Entropy (Phase 24)
      - Symbolic Harmonization (Phase 27)
      - Unified Consciousness (Phase 26)
      - Coherence Fusion (Phase 16)

    The result is a predictive drift snapshot containing:
      1. Drift Magnitude Prediction (DMP): Estimated future drift intensity [0.0, 1.0]
      2. Drift Direction Scores: Direction components (structure, warmth, grounding)
      3. Drift Stability Score (DSS): Confidence in trajectory [0.0, 1.0]
      4. Drift Likelihood Band: LOW / MEDIUM / HIGH
      5. Diagnostic Tags: DRIFT_RISK_RISING, HARMONICS_INFLUENCE_HIGH, etc.

    Args:
        core_identity_harmonic: CIH from Phase 34 [0.0, 1.0]
        adaptive_identity_harmonic: AIH from Phase 34 [0.0, 1.0]
        relational_identity_harmonic: RIH from Phase 34 [0.0, 1.0]
        identity_stability_score: Identity stability [0.0, 1.0]
        identity_flexibility_score: Identity flexibility [0.0, 1.0]
        identity_entropy: Identity entropy [0.0, 1.0]
        semantic_integrity: Semantic integrity score [0.0, 1.0]
        cognitive_drift_v3: Cognitive drift v3 score [0.0, 1.0]
        temporal_entropy_volatility: Temporal entropy volatility [0.0, 1.0]
        drift_fusion_index: Drift Fusion Index (if available) [0.0, 1.0]
        resonance_weighting_entropy: Resonance weighting entropy [0.0, 1.0]
        symbolic_harmonization_index: Symbolic harmonization index [0.0, 1.0]
        coherence_fused: Fused coherence score [0.0, 1.0]
        unified_consciousness_order: Consciousness order index [0.0, 1.0]
        persona_drift_score: Persona drift score [0.0, 1.0]
        guna_resonance_index: Guna resonance index [0.0, 1.0]
        kosha_resonance_index: Kosha resonance index [0.0, 1.0]
        cognitive_drift_history: Historical cognitive drift values
        persona_drift_history: Historical persona drift values
        coherence_fused_history: Historical coherence fused values
        identity_stability_history: Historical identity stability values

    Returns:
        PredictivePersonaDriftSnapshot or None if insufficient data

    Graceful Degradation:
        Returns None if we lack core required signals:
          - At least ONE identity harmonic (CIH, AIH, RIH)
          - At least ONE drift signal (cognitive_drift, persona_drift, drift_fusion)
          - At least ONE entropy signal (temporal, resonance, identity)
    """
    notes = []

    # ========================================================================
    # STEP 1: CHECK CORE INPUT AVAILABILITY (Graceful Degradation)
    # ========================================================================

    # Require at least ONE identity harmonic signal
    has_identity_harmonic = any([
        core_identity_harmonic is not None,
        adaptive_identity_harmonic is not None,
        relational_identity_harmonic is not None,
    ])

    # Require at least ONE drift signal
    has_drift_signal = any([
        cognitive_drift_v3 is not None,
        persona_drift_score is not None,
        drift_fusion_index is not None,
    ])

    # Require at least ONE entropy signal
    has_entropy_signal = any([
        temporal_entropy_volatility is not None,
        resonance_weighting_entropy is not None,
        identity_entropy is not None,
    ])

    if not (has_identity_harmonic and has_drift_signal and has_entropy_signal):
        # Insufficient data for PPDM computation
        return None

    # ========================================================================
    # STEP 2: EXTRACT SIGNALS WITH SAFE FALLBACKS
    # ========================================================================

    # Identity Harmonics (Phase 34)
    cih = _safe_get(core_identity_harmonic, 0.5)
    aih = _safe_get(adaptive_identity_harmonic, 0.5)
    rih = _safe_get(relational_identity_harmonic, 0.5)
    identity_stability = _safe_get(identity_stability_score, 0.5)
    identity_flexibility = _safe_get(identity_flexibility_score, 0.5)
    identity_ent = _safe_get(identity_entropy, 0.5)

    # Semantic + Cognitive (Phase 17)
    sem_int = _safe_get(semantic_integrity, 0.5)
    cog_drift = _safe_get(cognitive_drift_v3, 0.5)

    # Temporal Entropy (Phase 18)
    temp_ent_vol = _safe_get(temporal_entropy_volatility, 0.5)

    # Drift Fusion (Phase 19) - optional
    drift_fusion = _safe_get(drift_fusion_index, 0.5)

    # Resonance Weighting (Phase 24)
    res_weight_ent = _safe_get(resonance_weighting_entropy, 0.5)

    # Symbolic Harmonization (Phase 27)
    sym_harm = _safe_get(symbolic_harmonization_index, 0.5)

    # Coherence signals
    coh_fused = _safe_get(coherence_fused, 0.5)
    cons_order = _safe_get(unified_consciousness_order, 0.5)

    # Persona + Relational
    persona_drift = _safe_get(persona_drift_score, 0.5)
    guna_res = _safe_get(guna_resonance_index, 0.5)
    kosha_res = _safe_get(kosha_resonance_index, 0.5)

    # Track fallbacks
    if core_identity_harmonic is None:
        notes.append("cih_fallback")
    if adaptive_identity_harmonic is None:
        notes.append("aih_fallback")
    if relational_identity_harmonic is None:
        notes.append("rih_fallback")

    # ========================================================================
    # STEP 3: COMPUTE HARMONIC INFLUENCE WEIGHT
    # ========================================================================

    harmonic_influence = harmonic_weighting(
        cih=cih,
        aih=aih,
        rih=rih,
        identity_stability=identity_stability,
        identity_flexibility=identity_flexibility,
    )

    # ========================================================================
    # STEP 4: COMPUTE ENTROPY VOLATILITY WEIGHT
    # ========================================================================

    entropy_volatility = normalized_entropy_rescale(
        temporal_entropy_volatility=temp_ent_vol,
        resonance_weighting_entropy=res_weight_ent,
        identity_entropy=identity_ent,
    )

    # ========================================================================
    # STEP 5: COMPUTE DRIFT MOMENTUM (from historical trends)
    # ========================================================================

    drift_momentum = 0.5  # Default: neutral momentum

    if cognitive_drift_history and len(cognitive_drift_history) >= 3:
        # Compute slope of cognitive drift trend
        cog_drift_slope = _compute_trend_slope(cognitive_drift_history[-5:])
        # Positive slope = increasing drift = high momentum
        drift_momentum += 0.3 * _clamp(cog_drift_slope * 10.0, -0.5, 0.5)
        notes.append("drift_momentum_from_cognitive_history")

    if persona_drift_history and len(persona_drift_history) >= 3:
        # Compute slope of persona drift trend
        persona_drift_slope = _compute_trend_slope(persona_drift_history[-5:])
        drift_momentum += 0.2 * _clamp(persona_drift_slope * 10.0, -0.5, 0.5)
        notes.append("drift_momentum_from_persona_history")

    drift_momentum = _clamp(drift_momentum, 0.0, 1.0)

    # ========================================================================
    # STEP 6: COMPUTE DRIFT MAGNITUDE PREDICTION (DMP)
    # ========================================================================

    # Core drift signal blend
    core_drift_signal = (
        0.40 * cog_drift +
        0.30 * persona_drift +
        0.30 * drift_fusion
    )

    # Weighted by harmonic influence and entropy volatility
    # High harmonic influence → amplify drift
    # High entropy volatility → amplify drift
    drift_magnitude_raw = (
        core_drift_signal *
        (0.7 + 0.3 * harmonic_influence) *
        (0.7 + 0.3 * entropy_volatility)
    )

    # Apply momentum factor (momentum amplifies magnitude)
    drift_magnitude_prediction = _clamp(
        drift_magnitude_raw * (0.8 + 0.4 * drift_momentum),
        0.0, 1.0
    )

    # ========================================================================
    # STEP 7: COMPUTE DRIFT DIRECTION SCORES
    # ========================================================================

    drift_direction_scores = drift_direction_solver(
        semantic_integrity=sem_int,
        symbolic_harmonization=sym_harm,
        cognitive_drift=cog_drift,
        persona_drift=persona_drift,
        guna_resonance=guna_res,
        kosha_resonance=kosha_res,
    )

    # ========================================================================
    # STEP 8: COMPUTE DRIFT STABILITY SCORE (DSS)
    # ========================================================================

    # Compute drift variance from history
    drift_variance = 0.0
    if cognitive_drift_history and len(cognitive_drift_history) >= 3:
        drift_variance = _compute_variance(cognitive_drift_history[-5:])
        notes.append("drift_variance_computed")

    drift_stability = stability_curve(
        drift_variance=drift_variance,
        harmonic_stability=identity_stability,
        entropy_volatility=entropy_volatility,
    )

    # ========================================================================
    # STEP 9: COMPUTE DRIFT LIKELIHOOD BAND
    # ========================================================================

    # Likelihood band based on magnitude + inverse stability
    likelihood_score = (
        0.6 * drift_magnitude_prediction +
        0.4 * (1.0 - drift_stability)
    )

    if likelihood_score >= 0.65:
        drift_likelihood_band = "HIGH"
    elif likelihood_score >= 0.35:
        drift_likelihood_band = "MEDIUM"
    else:
        drift_likelihood_band = "LOW"

    # ========================================================================
    # STEP 10: DETERMINE PREDICTED DRIFT HORIZON
    # ========================================================================

    # Horizon: 3-5 turns based on stability
    # High stability → longer horizon (5 turns)
    # Low stability → shorter horizon (3 turns)
    if drift_stability >= 0.65:
        predicted_drift_horizon = 5
    elif drift_stability >= 0.35:
        predicted_drift_horizon = 4
    else:
        predicted_drift_horizon = 3

    # ========================================================================
    # STEP 11: GENERATE DIAGNOSTIC NOTES
    # ========================================================================

    # Drift risk level notes
    if drift_magnitude_prediction >= 0.70:
        notes.append("DRIFT_RISK_RISING")
    elif drift_magnitude_prediction <= 0.30:
        notes.append("DRIFT_RISK_DAMPENING")
    else:
        notes.append("DRIFT_RISK_STABLE")

    # Harmonic influence notes
    if harmonic_influence >= 0.65:
        notes.append("HARMONICS_INFLUENCE_HIGH")
    elif harmonic_influence <= 0.35:
        notes.append("HARMONICS_INFLUENCE_LOW")

    # Entropy volatility notes
    if entropy_volatility >= 0.70:
        notes.append("ENTROPY_VOLATILITY_HIGH")
    elif entropy_volatility <= 0.30:
        notes.append("ENTROPY_VOLATILITY_LOW")

    # Drift momentum notes
    if drift_momentum >= 0.65:
        notes.append("drift_momentum_accelerating")
    elif drift_momentum <= 0.35:
        notes.append("drift_momentum_decelerating")

    # Stability notes
    if drift_stability >= 0.70:
        notes.append("drift_trajectory_stable")
    elif drift_stability <= 0.35:
        notes.append("drift_trajectory_volatile")

    # Directional tendency notes (dominant direction)
    max_direction = max(drift_direction_scores.items(), key=lambda x: x[1])
    if max_direction[1] >= 0.60:
        notes.append(f"drift_tendency_{max_direction[0]}")

    # Likelihood band notes
    notes.append(f"drift_likelihood_{drift_likelihood_band.lower()}")

    # ========================================================================
    # STEP 12: RETURN SNAPSHOT
    # ========================================================================

    return PredictivePersonaDriftSnapshot(
        drift_magnitude_prediction=drift_magnitude_prediction,
        drift_direction_scores=drift_direction_scores,
        drift_stability_score=drift_stability,
        drift_likelihood_band=drift_likelihood_band,
        predicted_drift_horizon=predicted_drift_horizon,
        harmonic_influence_weight=harmonic_influence,
        entropy_volatility_weight=entropy_volatility,
        drift_momentum_score=drift_momentum,
        notes=sorted(set(notes)),  # Deduplicate and sort for determinism
    )
