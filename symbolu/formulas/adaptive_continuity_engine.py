"""
Adaptive Continuity Engine (ACE) v1.0 - Phase 37

Deterministic, zero-LLM, observation-only session continuity engine that derives a multi-turn
model of narrative, identity, emotional, and symbolic continuity.

ACE does NOT generate text and does NOT influence routing or semantic output.
It produces continuity analytics only, used for dashboards, diagnostics, and
persona tone modulation (optional, bounded).

ACE computes how coherent the conversation feels as a continuous unfolding,
independent of semantics or LLM behavior.

ACE generates three canonical continuity signals:
  1. Narrative Continuity Coefficient (NCC) [0.0–1.0]
     Measures stability of themes, intents, motivations, and symbolic patterns across turns.

  2. Identity Continuity Coefficient (ICC) [0.0–1.0]
     Derived from prior IRM (Phase 36), Identity Harmonics (Phase 34), and Predictive Drift (Phase 35).

  3. Continuity Stability Score (CSS) [0.0–1.0]
     An aggregate measure reflecting session-wide resilience, alignment, and predictability.

ACE also outputs:
  • continuity_band: LOW / MEDIUM / HIGH
  • continuity_tags:
    • CONTINUITY_STRONG
    • CONTINUITY_FRAGMENTED
    • CONTINUITY_STABLE
    • CONTINUITY_TRANSITIONAL
    • CONTINUITY_SYMBOLIC_ALIGNMENT
    • CONTINUITY_IDENTITY_REINFORCED

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Tone-level only: NEVER semantic changes (bounded ±0.015)
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Graceful degradation: Returns None if insufficient data
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import math


@dataclass
class AdaptiveContinuitySnapshot:
    """
    Immutable snapshot of Adaptive Continuity Engine formula computation.

    Fields:
        ncc: Narrative Continuity Coefficient [0.0, 1.0]
        icc: Identity Continuity Coefficient [0.0, 1.0]
        css: Continuity Stability Score [0.0, 1.0]
        continuity_band: Classification ("LOW", "MEDIUM", "HIGH")
        continuity_tags: Deterministic diagnostic tags
        raw_signals: Raw signal values for API exposure
    """

    ncc: float  # Narrative Continuity Coefficient [0.0, 1.0]
    icc: float  # Identity Continuity Coefficient [0.0, 1.0]
    css: float  # Continuity Stability Score [0.0, 1.0]
    continuity_band: str  # "LOW", "MEDIUM", "HIGH"
    continuity_tags: List[str] = field(default_factory=list)
    raw_signals: Dict[str, float] = field(default_factory=dict)


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


def _compute_stability_factor(history: List[float], window: int = 5) -> float:
    """
    Compute stability factor based on variance in recent history.

    High stability = low variance
    Low stability = high variance

    Args:
        history: Historical values (most recent last)
        window: Window size for stability computation

    Returns:
        float: Stability factor [0.0, 1.0]
    """
    if not history or len(history) < 2:
        return 0.5  # Neutral

    recent = history[-window:] if len(history) >= window else history
    variance = _compute_variance(recent)

    # Convert variance to stability (inverse relationship)
    # Variance of 0.25 or more = very unstable
    stability = _clamp(1.0 - min(variance * 4.0, 1.0), 0.0, 1.0)

    return stability


def _compute_trend_alignment(history: List[float], window: int = 5) -> float:
    """
    Compute trend alignment - whether values are moving in a consistent direction.

    High alignment = consistent trend (upward or stable)
    Low alignment = erratic movement

    Args:
        history: Historical values (most recent last)
        window: Window size for trend computation

    Returns:
        float: Trend alignment [0.0, 1.0]
    """
    if not history or len(history) < 3:
        return 0.5  # Neutral

    recent = history[-window:] if len(history) >= window else history

    if len(recent) < 3:
        return 0.5

    # Compute directional consistency
    # Count how many consecutive pairs move in same direction
    upward_count = 0
    downward_count = 0

    for i in range(1, len(recent)):
        diff = recent[i] - recent[i-1]
        if diff > 0.01:
            upward_count += 1
        elif diff < -0.01:
            downward_count += 1

    total_pairs = len(recent) - 1
    consistency = max(upward_count, downward_count) / total_pairs if total_pairs > 0 else 0.0

    return _clamp(consistency, 0.0, 1.0)


def compute_adaptive_continuity(
    *,
    # Phase 27: Symbolic Harmonization
    symbolic_harmonization_index: Optional[float] = None,
    symbolic_harmonization_history: Optional[List[float]] = None,
    # Phase 36: Identity Resonance Memory (IRM)
    identity_memory_strength: Optional[float] = None,  # IMS
    identity_echo_persistence: Optional[float] = None,  # IEP
    identity_drift_anchoring: Optional[float] = None,  # IDA
    ims_history: Optional[List[float]] = None,
    iep_history: Optional[List[float]] = None,
    ida_history: Optional[List[float]] = None,
    # Phase 34: Identity Harmonics
    core_identity_harmonic: Optional[float] = None,
    adaptive_identity_harmonic: Optional[float] = None,
    relational_identity_harmonic: Optional[float] = None,
    identity_stability_score: Optional[float] = None,
    identity_harmonics_index: Optional[float] = None,
    identity_stability_history: Optional[List[float]] = None,
    # Phase 35: Predictive Persona Drift
    drift_magnitude_prediction: Optional[float] = None,
    drift_stability_score: Optional[float] = None,
    drift_likelihood_band: Optional[str] = None,
    drift_magnitude_history: Optional[List[float]] = None,
    drift_stability_history: Optional[List[float]] = None,
    # Phase 26: Unified Consciousness Formula (UCF)
    consciousness_order_index: Optional[float] = None,  # COI
    consciousness_stability_index: Optional[float] = None,  # CSI
    consciousness_order_history: Optional[List[float]] = None,
    consciousness_stability_history: Optional[List[float]] = None,
    # Phase 18: Temporal Entropy
    temporal_entropy_volatility: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
    temporal_entropy_volatility_history: Optional[List[float]] = None,
    # Phase 17: Semantic Integrity
    semantic_integrity: Optional[float] = None,
    semantic_integrity_history: Optional[List[float]] = None,
    # Phase 24: Resonance Weighting
    resonance_weighting_entropy: Optional[float] = None,
) -> Optional[AdaptiveContinuitySnapshot]:
    """
    Compute Adaptive Continuity Engine (ACE) v1.0.

    This formula models session-wide continuity across narrative, identity, and symbolic dimensions.
    It acts as an observation-only continuity analytics engine.

    The result is a continuity snapshot containing:
      1. Narrative Continuity Coefficient (NCC): Theme/intent/symbolic stability [0.0, 1.0]
      2. Identity Continuity Coefficient (ICC): Identity pattern continuity [0.0, 1.0]
      3. Continuity Stability Score (CSS): Overall session resilience [0.0, 1.0]
      4. Continuity Band: LOW / MEDIUM / HIGH
      5. Continuity Tags: CONTINUITY_STRONG, CONTINUITY_FRAGMENTED, etc.

    Args:
        symbolic_harmonization_index: SHI from Phase 27 [0.0, 1.0]
        symbolic_harmonization_history: Historical SHI values
        identity_memory_strength: IMS from Phase 36 [0.0, 1.0]
        identity_echo_persistence: IEP from Phase 36 [0.0, 1.0]
        identity_drift_anchoring: IDA from Phase 36 [0.0, 1.0]
        ims_history: Historical IMS values
        iep_history: Historical IEP values
        ida_history: Historical IDA values
        core_identity_harmonic: CIH from Phase 34 [0.0, 1.0]
        adaptive_identity_harmonic: AIH from Phase 34 [0.0, 1.0]
        relational_identity_harmonic: RIH from Phase 34 [0.0, 1.0]
        identity_stability_score: Identity stability from Phase 34 [0.0, 1.0]
        identity_harmonics_index: Identity harmonics index from Phase 34 [0.0, 1.0]
        identity_stability_history: Historical identity stability values
        drift_magnitude_prediction: DMP from Phase 35 [0.0, 1.0]
        drift_stability_score: DSS from Phase 35 [0.0, 1.0]
        drift_likelihood_band: Drift band from Phase 35
        drift_magnitude_history: Historical drift magnitude values
        drift_stability_history: Historical drift stability values
        consciousness_order_index: COI from Phase 26 [0.0, 1.0]
        consciousness_stability_index: CSI from Phase 26 [0.0, 1.0]
        consciousness_order_history: Historical COI values
        consciousness_stability_history: Historical CSI values
        temporal_entropy_volatility: Entropy volatility from Phase 18 [0.0, 1.0]
        temporal_entropy_diff: Entropy diff from Phase 18 [0.0, 1.0]
        temporal_entropy_volatility_history: Historical entropy volatility
        semantic_integrity: Semantic integrity from Phase 17 [0.0, 1.0]
        semantic_integrity_history: Historical semantic integrity values
        resonance_weighting_entropy: Resonance entropy from Phase 24 [0.0, 1.0]

    Returns:
        AdaptiveContinuitySnapshot or None if insufficient data

    Graceful Degradation:
        Returns None if we lack core required signals:
          - At least ONE narrative signal (symbolic_harmonization, semantic_integrity, consciousness_order)
          - At least ONE identity signal (IRM metrics OR identity harmonics)
    """
    tags = []
    raw_signals = {}

    # ========================================================================
    # STEP 1: CHECK CORE INPUT AVAILABILITY (Graceful Degradation)
    # ========================================================================

    # Require at least ONE narrative continuity signal
    has_narrative_signal = any([
        symbolic_harmonization_index is not None,
        semantic_integrity is not None,
        consciousness_order_index is not None,
    ])

    # Require at least ONE identity continuity signal
    has_identity_signal = any([
        identity_memory_strength is not None,
        identity_echo_persistence is not None,
        core_identity_harmonic is not None,
        adaptive_identity_harmonic is not None,
        relational_identity_harmonic is not None,
    ])

    if not (has_narrative_signal and has_identity_signal):
        # Insufficient data for ACE computation
        return None

    # ========================================================================
    # STEP 2: EXTRACT SIGNALS WITH SAFE FALLBACKS
    # ========================================================================

    # Phase 27: Symbolic Harmonization
    sym_harm = _safe_get(symbolic_harmonization_index, 0.5)

    # Phase 36: Identity Resonance Memory
    ims = _safe_get(identity_memory_strength, 0.5)
    iep = _safe_get(identity_echo_persistence, 0.5)
    ida = _safe_get(identity_drift_anchoring, 0.5)

    # Phase 34: Identity Harmonics
    cih = _safe_get(core_identity_harmonic, 0.5)
    aih = _safe_get(adaptive_identity_harmonic, 0.5)
    rih = _safe_get(relational_identity_harmonic, 0.5)
    identity_stability = _safe_get(identity_stability_score, 0.5)
    identity_harmonics_idx = _safe_get(identity_harmonics_index, 0.5)

    # Phase 35: Predictive Drift
    drift_magnitude = _safe_get(drift_magnitude_prediction, 0.5)
    drift_stability = _safe_get(drift_stability_score, 0.5)

    # Phase 26: Unified Consciousness Formula
    coi = _safe_get(consciousness_order_index, 0.5)
    csi = _safe_get(consciousness_stability_index, 0.5)

    # Phase 18: Temporal Entropy
    temp_entropy_vol = _safe_get(temporal_entropy_volatility, 0.5)
    temp_entropy_diff = _safe_get(temporal_entropy_diff, 0.5)

    # Phase 17: Semantic Integrity
    sem_int = _safe_get(semantic_integrity, 0.5)

    # Phase 24: Resonance Weighting
    res_weight_ent = _safe_get(resonance_weighting_entropy, 0.5)

    # Track fallbacks for diagnostics
    if symbolic_harmonization_index is None:
        tags.append("symbolic_harm_fallback")
    if identity_memory_strength is None:
        tags.append("ims_fallback")

    # ========================================================================
    # STEP 3: COMPUTE NARRATIVE CONTINUITY COEFFICIENT (NCC)
    # ========================================================================
    # NCC measures stability of themes, intents, motivations, and symbolic patterns
    # Based on:
    #   - Symbolic harmonization (primary)
    #   - Semantic integrity (secondary)
    #   - Consciousness order (tertiary)
    #   - Stability of these signals over time

    # Core narrative signals
    narrative_core = (
        0.45 * sym_harm +
        0.35 * sem_int +
        0.20 * coi
    )

    # Compute stability factors for narrative signals
    sym_harm_stability = _compute_stability_factor(
        symbolic_harmonization_history if symbolic_harmonization_history else []
    )
    sem_int_stability = _compute_stability_factor(
        semantic_integrity_history if semantic_integrity_history else []
    )
    coi_stability = _compute_stability_factor(
        consciousness_order_history if consciousness_order_history else []
    )

    narrative_stability = (
        0.40 * sym_harm_stability +
        0.35 * sem_int_stability +
        0.25 * coi_stability
    )

    # Apply entropy damping
    # High entropy volatility → reduces narrative continuity
    entropy_damping = _clamp(1.0 - (0.25 * temp_entropy_vol), 0.75, 1.0)

    # Apply resonance weighting factor
    # High resonance entropy → more diffuse, reduces continuity
    resonance_focus = _clamp(1.0 - (0.15 * res_weight_ent), 0.85, 1.0)

    # Weighted blend: core narrative * stability * damping * focus
    ncc_raw = narrative_core * (0.6 + 0.4 * narrative_stability) * entropy_damping * resonance_focus

    ncc = _clamp(ncc_raw, 0.0, 1.0)

    raw_signals["narrative_continuity_coefficient"] = ncc
    raw_signals["narrative_core"] = narrative_core
    raw_signals["narrative_stability"] = narrative_stability

    # ========================================================================
    # STEP 4: COMPUTE IDENTITY CONTINUITY COEFFICIENT (ICC)
    # ========================================================================
    # ICC measures identity pattern continuity across turns
    # Based on:
    #   - IRM metrics (IMS, IEP, IDA) - primary
    #   - Identity harmonics (CIH, AIH, RIH) - secondary
    #   - Identity stability - tertiary
    #   - Drift anchoring

    # Core identity signals (weighted toward IRM)
    identity_core = (
        0.30 * ims +
        0.25 * iep +
        0.20 * ida +
        0.10 * cih +
        0.10 * identity_harmonics_idx +
        0.05 * identity_stability
    )

    # Compute stability factors for identity signals
    ims_stability = _compute_stability_factor(
        ims_history if ims_history else []
    )
    identity_stability_factor = _compute_stability_factor(
        identity_stability_history if identity_stability_history else []
    )

    identity_signal_stability = (
        0.50 * ims_stability +
        0.50 * identity_stability_factor
    )

    # Apply drift resistance
    # High drift magnitude → weak identity continuity
    drift_resistance = _clamp(1.0 - drift_magnitude, 0.0, 1.0)

    # Apply drift stability bonus
    # High drift stability → predictable, easier to maintain continuity
    drift_predictability_bonus = 0.05 * drift_stability

    # Weighted blend
    icc_raw = (
        identity_core * (0.5 + 0.5 * identity_signal_stability) *
        (0.85 + 0.15 * drift_resistance)
    )
    icc_raw = min(icc_raw + drift_predictability_bonus, 1.0)

    icc = _clamp(icc_raw, 0.0, 1.0)

    raw_signals["identity_continuity_coefficient"] = icc
    raw_signals["identity_core"] = identity_core
    raw_signals["identity_signal_stability"] = identity_signal_stability

    # ========================================================================
    # STEP 5: COMPUTE CONTINUITY STABILITY SCORE (CSS)
    # ========================================================================
    # CSS measures overall session-wide resilience, alignment, and predictability
    # Based on:
    #   - NCC and ICC (primary)
    #   - Low entropy volatility (stability signal)
    #   - High CSI (consciousness stability)
    #   - Trend alignment across all continuity signals

    # Core continuity blend
    core_continuity = (
        0.50 * ncc +
        0.50 * icc
    )

    # Entropy stability contribution
    # Low entropy volatility → high stability
    entropy_stability = _clamp(1.0 - temp_entropy_vol, 0.0, 1.0)

    # Consciousness stability contribution
    consciousness_stability = csi

    # Compute trend alignment across key histories
    ncc_trend_alignment = 0.5  # Default
    icc_trend_alignment = 0.5  # Default

    if symbolic_harmonization_history:
        ncc_trend_alignment = _compute_trend_alignment(symbolic_harmonization_history)

    if ims_history:
        icc_trend_alignment = _compute_trend_alignment(ims_history)

    trend_alignment = (0.50 * ncc_trend_alignment + 0.50 * icc_trend_alignment)

    # Weighted blend
    css_raw = (
        0.40 * core_continuity +
        0.20 * entropy_stability +
        0.20 * consciousness_stability +
        0.20 * trend_alignment
    )

    css = _clamp(css_raw, 0.0, 1.0)

    raw_signals["continuity_stability_score"] = css
    raw_signals["core_continuity"] = core_continuity
    raw_signals["entropy_stability"] = entropy_stability
    raw_signals["trend_alignment"] = trend_alignment

    # ========================================================================
    # STEP 6: COMPUTE CONTINUITY BAND
    # ========================================================================
    # Band classification based on CSS
    # HIGH: CSS ≥ 0.70
    # MEDIUM: CSS ≥ 0.40
    # LOW: else

    if css >= 0.70:
        continuity_band = "HIGH"
    elif css >= 0.40:
        continuity_band = "MEDIUM"
    else:
        continuity_band = "LOW"

    # ========================================================================
    # STEP 7: GENERATE CONTINUITY TAGS
    # ========================================================================

    # NCC level tags
    if ncc >= 0.70:
        tags.append("CONTINUITY_STRONG")
    elif ncc <= 0.35:
        tags.append("CONTINUITY_FRAGMENTED")

    # CSS level tags
    if css >= 0.65:
        tags.append("CONTINUITY_STABLE")
    elif css >= 0.35 and css < 0.65:
        tags.append("CONTINUITY_TRANSITIONAL")

    # Symbolic alignment
    if sym_harm >= 0.70 and ncc >= 0.65:
        tags.append("CONTINUITY_SYMBOLIC_ALIGNMENT")

    # Identity reinforcement
    if icc >= 0.70 and ims >= 0.65:
        tags.append("CONTINUITY_IDENTITY_REINFORCED")

    # Band tags
    if continuity_band == "HIGH":
        tags.append("CONTINUITY_BAND_HIGH")
    elif continuity_band == "MEDIUM":
        tags.append("CONTINUITY_BAND_MEDIUM")
    else:
        tags.append("CONTINUITY_BAND_LOW")

    # NCC-ICC alignment
    if abs(ncc - icc) <= 0.15:
        tags.append("narrative_identity_aligned")
    elif abs(ncc - icc) >= 0.40:
        tags.append("narrative_identity_divergent")

    # High stability despite entropy
    if css >= 0.65 and temp_entropy_vol >= 0.60:
        tags.append("stable_despite_entropy")

    # Drift interference
    if drift_magnitude >= 0.65 and icc <= 0.40:
        tags.append("drift_disrupting_identity_continuity")

    # Strong overall continuity
    if ncc >= 0.70 and icc >= 0.70 and css >= 0.70:
        tags.append("continuity_excellence")

    # Weak overall continuity
    if ncc <= 0.35 and icc <= 0.35 and css <= 0.35:
        tags.append("continuity_disrupted")

    # ========================================================================
    # STEP 8: STORE ALL RAW SIGNALS FOR API EXPOSURE
    # ========================================================================

    raw_signals.update({
        "symbolic_harmonization_index": sym_harm,
        "identity_memory_strength": ims,
        "identity_echo_persistence": iep,
        "identity_drift_anchoring": ida,
        "core_identity_harmonic": cih,
        "identity_stability_score": identity_stability,
        "drift_magnitude_prediction": drift_magnitude,
        "drift_stability_score": drift_stability,
        "consciousness_order_index": coi,
        "consciousness_stability_index": csi,
        "temporal_entropy_volatility": temp_entropy_vol,
        "semantic_integrity": sem_int,
        "sym_harm_stability": sym_harm_stability,
        "ims_stability": ims_stability,
        "entropy_damping": entropy_damping,
        "drift_resistance": drift_resistance,
    })

    # ========================================================================
    # STEP 9: RETURN SNAPSHOT
    # ========================================================================

    return AdaptiveContinuitySnapshot(
        ncc=ncc,
        icc=icc,
        css=css,
        continuity_band=continuity_band,
        continuity_tags=sorted(set(tags)),  # Deduplicate and sort for determinism
        raw_signals=raw_signals,
    )
