"""
Identity Resonance Memory (IRM) v1.0 - Phase 36

Deterministic, zero-LLM, observation-only "identity stability memory" that models how
resonant identity patterns accumulate, persist, decay, and resurface across turns.

IRM acts as the first temporal memory model for identity-related signals in Symbol-U
and tracks identity resonance patterns over time.

This formula produces identity resonance memory metrics:
  1. Identity Memory Strength (IMS): How strongly identity signals persist [0.0, 1.0]
  2. Identity Echo Persistence (IEP): Whether identity themes keep resurfacing [0.0, 1.0]
  3. Identity Drift Anchoring (IDA): Identity stabilization in presence of drift [0.0, 1.0]
  4. Identity Resonance Memory Band: LOW / MEDIUM / HIGH classification
  5. Diagnostic Tags: IDENTITY_ANCHORING_STRONG, IDENTITY_ECHO_PERSISTENT, etc.

IRM is designed for:
  • Tone-only micro-adjustments (±0.02 max total)
  • Identity stability analytics & diagnostics
  • Temporal memory modeling
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
class IdentityResonanceMemorySnapshot:
    """
    Immutable snapshot of identity resonance memory formula computation.

    Fields:
        identity_memory_strength (IMS): How strongly identity signals persist [0.0, 1.0]
        identity_echo_persistence (IEP): Whether identity themes resurface [0.0, 1.0]
        identity_drift_anchoring (IDA): Stability vs predictive drift [0.0, 1.0]
        memory_band: Classification ("LOW", "MEDIUM", "HIGH")
        diagnostic_tags: Deterministic diagnostic tags
        raw_signals: Raw signal values for API exposure
    """

    identity_memory_strength: float  # IMS: Identity persistence [0.0, 1.0]
    identity_echo_persistence: float  # IEP: Identity theme resurfacing [0.0, 1.0]
    identity_drift_anchoring: float  # IDA: Stability vs drift [0.0, 1.0]
    memory_band: str  # "LOW", "MEDIUM", "HIGH"
    diagnostic_tags: List[str] = field(default_factory=list)
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


def _compute_persistence_score(
    current_value: float,
    history: List[float],
    decay_factor: float = 0.85
) -> float:
    """
    Compute persistence score using exponential weighted moving average.

    Higher score = signal persists over time
    Lower score = signal is volatile/ephemeral

    Args:
        current_value: Current signal value [0.0, 1.0]
        history: Historical signal values (most recent last)
        decay_factor: Exponential decay factor [0.0, 1.0] (default 0.85)

    Returns:
        float: Persistence score [0.0, 1.0]
    """
    if not history:
        # No history, return neutral
        return 0.5

    # Compute exponential weighted average
    # More recent values have higher weight
    weighted_sum = 0.0
    weight_sum = 0.0

    for i, value in enumerate(history):
        weight = decay_factor ** (len(history) - i - 1)
        weighted_sum += weight * value
        weight_sum += weight

    # Add current value with full weight
    weighted_sum += current_value
    weight_sum += 1.0

    if weight_sum == 0.0:
        return 0.5

    weighted_avg = weighted_sum / weight_sum

    # Compute stability: inverse of variance
    values_with_current = history[-10:] + [current_value]  # Last 10 + current
    variance = _compute_variance(values_with_current)
    stability = _clamp(1.0 - min(variance * 2.0, 1.0), 0.0, 1.0)

    # Persistence = weighted average * stability
    # High values that are stable = high persistence
    persistence = _clamp(weighted_avg * (0.6 + 0.4 * stability), 0.0, 1.0)

    return persistence


def _compute_echo_score(
    history: List[float],
    threshold: float = 0.6,
    window: int = 10
) -> float:
    """
    Compute echo persistence score: how often signals resurface above threshold.

    High echo = identity themes keep resurfacing
    Low echo = identity themes fade away

    Args:
        history: Historical signal values (most recent last)
        threshold: Minimum value to count as "present" [0.0, 1.0]
        window: Window size for recent history

    Returns:
        float: Echo persistence score [0.0, 1.0]
    """
    if not history:
        return 0.5

    # Take recent window
    recent = history[-window:]

    if len(recent) < 3:
        # Not enough data
        return 0.5

    # Count how many times signal is above threshold
    above_threshold_count = sum(1 for v in recent if v >= threshold)

    # Compute ratio
    echo_ratio = above_threshold_count / len(recent)

    # Check for cyclic pattern: signal drops then resurfaces
    resurfacing_count = 0
    was_below = False

    for value in recent:
        if value < threshold:
            was_below = True
        elif was_below and value >= threshold:
            # Resurfaced!
            resurfacing_count += 1
            was_below = False

    # Bonus for resurfacing behavior (echo pattern)
    resurfacing_bonus = min(resurfacing_count * 0.1, 0.2)

    echo_score = _clamp(echo_ratio + resurfacing_bonus, 0.0, 1.0)

    return echo_score


def compute_identity_resonance_memory(
    *,
    # Phase 34: Identity Harmonics
    core_identity_harmonic: Optional[float] = None,
    adaptive_identity_harmonic: Optional[float] = None,
    relational_identity_harmonic: Optional[float] = None,
    identity_stability_score: Optional[float] = None,
    identity_flexibility_score: Optional[float] = None,
    # Phase 35: Predictive Persona Drift
    drift_magnitude_prediction: Optional[float] = None,
    drift_stability_score: Optional[float] = None,
    drift_likelihood_band: Optional[str] = None,
    # Phase 17: Semantic Integrity
    semantic_integrity: Optional[float] = None,
    # Phase 27: Symbolic Harmonization
    symbolic_harmonization_index: Optional[float] = None,
    # Phase 26: Unified Consciousness
    consciousness_order_index: Optional[float] = None,
    # Phase 18: Temporal Entropy
    temporal_entropy_volatility: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
    # Phase 24: Resonance Weighting
    resonance_weighting_entropy: Optional[float] = None,
    # Phase 22: Mirror-Time Cycle Stability (optional)
    cycle_alignment: Optional[float] = None,
    cycle_stability_band: Optional[str] = None,
    # Historical context (for persistence/echo computation)
    cih_history: Optional[List[float]] = None,
    aih_history: Optional[List[float]] = None,
    rih_history: Optional[List[float]] = None,
    identity_stability_history: Optional[List[float]] = None,
    semantic_integrity_history: Optional[List[float]] = None,
    symbolic_harmonization_history: Optional[List[float]] = None,
    drift_magnitude_history: Optional[List[float]] = None,
    consciousness_order_history: Optional[List[float]] = None,
) -> Optional[IdentityResonanceMemorySnapshot]:
    """
    Compute Identity Resonance Memory (IRM) v1.0.

    This formula models how resonant identity patterns accumulate, persist, decay,
    and resurface across turns. It acts as temporal memory for identity signals.

    The result is a memory snapshot containing:
      1. Identity Memory Strength (IMS): Signal persistence [0.0, 1.0]
      2. Identity Echo Persistence (IEP): Theme resurfacing [0.0, 1.0]
      3. Identity Drift Anchoring (IDA): Stability vs drift [0.0, 1.0]
      4. Memory Band: LOW / MEDIUM / HIGH
      5. Diagnostic Tags: IDENTITY_ANCHORING_STRONG, etc.

    Args:
        core_identity_harmonic: CIH from Phase 34 [0.0, 1.0]
        adaptive_identity_harmonic: AIH from Phase 34 [0.0, 1.0]
        relational_identity_harmonic: RIH from Phase 34 [0.0, 1.0]
        identity_stability_score: Identity stability from Phase 34 [0.0, 1.0]
        identity_flexibility_score: Identity flexibility from Phase 34 [0.0, 1.0]
        drift_magnitude_prediction: DMP from Phase 35 [0.0, 1.0]
        drift_stability_score: DSS from Phase 35 [0.0, 1.0]
        drift_likelihood_band: Drift band from Phase 35: "LOW" | "MEDIUM" | "HIGH"
        semantic_integrity: Semantic integrity from Phase 17 [0.0, 1.0]
        symbolic_harmonization_index: SHI from Phase 27 [0.0, 1.0]
        consciousness_order_index: COI from Phase 26 [0.0, 1.0]
        temporal_entropy_volatility: Entropy volatility from Phase 18 [0.0, 1.0]
        temporal_entropy_diff: Entropy diff from Phase 18 [0.0, 1.0]
        resonance_weighting_entropy: Resonance entropy from Phase 24 [0.0, 1.0]
        cycle_alignment: Cycle alignment from Phase 22 [0.0, 1.0]
        cycle_stability_band: Cycle stability from Phase 22
        cih_history: Historical CIH values
        aih_history: Historical AIH values
        rih_history: Historical RIH values
        identity_stability_history: Historical stability values
        semantic_integrity_history: Historical semantic integrity values
        symbolic_harmonization_history: Historical symbolic harmonization values
        drift_magnitude_history: Historical drift magnitude values
        consciousness_order_history: Historical consciousness order values

    Returns:
        IdentityResonanceMemorySnapshot or None if insufficient data

    Graceful Degradation:
        Returns None if we lack core required signals:
          - At least ONE identity harmonic (CIH, AIH, RIH)
          - At least ONE stability/semantic signal (semantic_integrity, symbolic_harmonization, identity_stability)
    """
    tags = []
    raw_signals = {}

    # ========================================================================
    # STEP 1: CHECK CORE INPUT AVAILABILITY (Graceful Degradation)
    # ========================================================================

    # Require at least ONE identity harmonic signal
    has_identity_harmonic = any([
        core_identity_harmonic is not None,
        adaptive_identity_harmonic is not None,
        relational_identity_harmonic is not None,
    ])

    # Require at least ONE stability/semantic signal
    has_stability_signal = any([
        semantic_integrity is not None,
        symbolic_harmonization_index is not None,
        identity_stability_score is not None,
    ])

    if not (has_identity_harmonic and has_stability_signal):
        # Insufficient data for IRM computation
        return None

    # ========================================================================
    # STEP 2: EXTRACT SIGNALS WITH SAFE FALLBACKS
    # ========================================================================

    # Phase 34: Identity Harmonics
    cih = _safe_get(core_identity_harmonic, 0.5)
    aih = _safe_get(adaptive_identity_harmonic, 0.5)
    rih = _safe_get(relational_identity_harmonic, 0.5)
    identity_stability = _safe_get(identity_stability_score, 0.5)
    identity_flexibility = _safe_get(identity_flexibility_score, 0.5)

    # Phase 35: Predictive Drift
    drift_magnitude = _safe_get(drift_magnitude_prediction, 0.5)
    drift_stability = _safe_get(drift_stability_score, 0.5)

    # Phase 17: Semantic Integrity
    sem_int = _safe_get(semantic_integrity, 0.5)

    # Phase 27: Symbolic Harmonization
    sym_harm = _safe_get(symbolic_harmonization_index, 0.5)

    # Phase 26: Unified Consciousness
    cons_order = _safe_get(consciousness_order_index, 0.5)

    # Phase 18: Temporal Entropy
    temp_entropy_vol = _safe_get(temporal_entropy_volatility, 0.5)
    temp_entropy_diff = _safe_get(temporal_entropy_diff, 0.5)

    # Phase 24: Resonance Weighting
    res_weight_ent = _safe_get(resonance_weighting_entropy, 0.5)

    # Phase 22: Mirror-Time Cycle (optional)
    cycle_align = _safe_get(cycle_alignment, 0.5)

    # Track fallbacks
    if core_identity_harmonic is None:
        tags.append("cih_fallback")
    if adaptive_identity_harmonic is None:
        tags.append("aih_fallback")
    if relational_identity_harmonic is None:
        tags.append("rih_fallback")

    # ========================================================================
    # STEP 3: COMPUTE IDENTITY MEMORY STRENGTH (IMS)
    # ========================================================================
    # IMS measures how strongly identity signals persist over recent turns
    # Based on:
    #   - Identity harmonics (CIH, AIH, RIH) with history persistence
    #   - Semantic integrity persistence
    #   - Symbolic harmonization persistence
    #   - Consciousness order persistence

    # Compute persistence for each signal
    cih_persistence = _compute_persistence_score(
        cih, cih_history if cih_history else []
    )

    aih_persistence = _compute_persistence_score(
        aih, aih_history if aih_history else []
    )

    rih_persistence = _compute_persistence_score(
        rih, rih_history if rih_history else []
    )

    semantic_persistence = _compute_persistence_score(
        sem_int, semantic_integrity_history if semantic_integrity_history else []
    )

    symbolic_persistence = _compute_persistence_score(
        sym_harm, symbolic_harmonization_history if symbolic_harmonization_history else []
    )

    # Weighted blend of persistence scores
    # Identity harmonics are most important (60%)
    # Semantic/symbolic coherence is secondary (40%)
    ims_raw = (
        0.25 * cih_persistence +
        0.20 * aih_persistence +
        0.15 * rih_persistence +
        0.25 * semantic_persistence +
        0.15 * symbolic_persistence
    )

    # Apply temporal entropy damping
    # High entropy volatility → reduces memory strength
    entropy_damping = _clamp(1.0 - (0.3 * temp_entropy_vol), 0.7, 1.0)

    ims = _clamp(ims_raw * entropy_damping, 0.0, 1.0)

    raw_signals["identity_memory_strength"] = ims

    # ========================================================================
    # STEP 4: COMPUTE IDENTITY ECHO PERSISTENCE (IEP)
    # ========================================================================
    # IEP measures whether identity themes keep resurfacing
    # Based on:
    #   - CIH, AIH, RIH echo patterns
    #   - Semantic integrity echo
    #   - Symbolic harmonization echo
    #   - Consciousness order echo

    # Compute echo scores for each signal
    cih_echo = _compute_echo_score(
        cih_history if cih_history else [], threshold=0.6
    )

    semantic_echo = _compute_echo_score(
        semantic_integrity_history if semantic_integrity_history else [], threshold=0.6
    )

    symbolic_echo = _compute_echo_score(
        symbolic_harmonization_history if symbolic_harmonization_history else [], threshold=0.6
    )

    consciousness_echo = _compute_echo_score(
        consciousness_order_history if consciousness_order_history else [], threshold=0.6
    )

    # Weighted blend of echo scores
    iep_raw = (
        0.35 * cih_echo +
        0.25 * semantic_echo +
        0.25 * symbolic_echo +
        0.15 * consciousness_echo
    )

    # Apply resonance weighting entropy factor
    # High resonance entropy → more diffuse echo (reduce IEP)
    # Low resonance entropy → focused echo (increase IEP)
    echo_focus_factor = _clamp(1.0 - (0.2 * res_weight_ent), 0.8, 1.0)

    iep = _clamp(iep_raw * echo_focus_factor, 0.0, 1.0)

    raw_signals["identity_echo_persistence"] = iep

    # ========================================================================
    # STEP 5: COMPUTE IDENTITY DRIFT ANCHORING (IDA)
    # ========================================================================
    # IDA measures how stabilized identity becomes in presence of predictive drift
    # Based on:
    #   - Identity stability (high = strong anchor)
    #   - Drift magnitude prediction (high = weak anchor)
    #   - Drift stability (high = predictable, easier to anchor)
    #   - Temporal entropy volatility (high = hard to anchor)

    # Core anchoring signal: identity stability
    core_anchoring = identity_stability

    # Drift resistance: inverse of drift magnitude
    # High drift magnitude → low resistance → weak anchoring
    drift_resistance = _clamp(1.0 - drift_magnitude, 0.0, 1.0)

    # Drift stability contributes positively
    # High drift stability = predictable drift = easier to anchor
    drift_predictability = drift_stability

    # Entropy stability: inverse of entropy volatility
    # High entropy volatility → unstable → weak anchoring
    entropy_stability = _clamp(1.0 - temp_entropy_vol, 0.0, 1.0)

    # Weighted blend
    ida_raw = (
        0.40 * core_anchoring +
        0.30 * drift_resistance +
        0.20 * drift_predictability +
        0.10 * entropy_stability
    )

    # Apply cycle alignment bonus (if available)
    # High cycle alignment → stronger anchoring
    if cycle_alignment is not None:
        cycle_bonus = 0.05 * cycle_align
        ida_raw = min(ida_raw + cycle_bonus, 1.0)
        tags.append("cycle_alignment_applied")

    ida = _clamp(ida_raw, 0.0, 1.0)

    raw_signals["identity_drift_anchoring"] = ida

    # ========================================================================
    # STEP 6: COMPUTE IDENTITY RESONANCE MEMORY BAND
    # ========================================================================
    # Band classification based on IMS + IEP
    # HIGH: Strong memory + persistent echo
    # MEDIUM: Moderate memory or echo
    # LOW: Weak memory and echo

    # Combined memory score (weighted average)
    memory_score = (
        0.50 * ims +
        0.35 * iep +
        0.15 * ida
    )

    if memory_score >= 0.65:
        memory_band = "HIGH"
    elif memory_score >= 0.40:
        memory_band = "MEDIUM"
    else:
        memory_band = "LOW"

    # ========================================================================
    # STEP 7: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    # IMS level tags
    if ims >= 0.70:
        tags.append("identity_memory_strong")
    elif ims <= 0.35:
        tags.append("identity_memory_weak")

    # IEP level tags
    if iep >= 0.70:
        tags.append("IDENTITY_ECHO_PERSISTENT")
    elif iep <= 0.35:
        tags.append("IDENTITY_ECHO_VOLATILE")

    # IDA level tags
    if ida >= 0.70:
        tags.append("IDENTITY_ANCHORING_STRONG")
    elif ida <= 0.35:
        tags.append("IDENTITY_ANCHORING_WEAK")

    # Memory band tags
    if memory_band == "HIGH":
        tags.append("IRM_MEMORY_HIGH")
    elif memory_band == "MEDIUM":
        tags.append("IRM_MEMORY_MEDIUM")
    else:
        tags.append("IRM_MEMORY_LOW")

    # Identity harmonics dominance
    if cih >= 0.70 and aih >= 0.70 and rih >= 0.70:
        tags.append("IDENTITY_HARMONICS_DOMINANT")

    # Drift interaction tags
    if drift_magnitude >= 0.65 and ida >= 0.65:
        tags.append("strong_anchoring_despite_drift")
    elif drift_magnitude >= 0.65 and ida <= 0.35:
        tags.append("weak_anchoring_high_drift_risk")

    # Echo + memory alignment
    if ims >= 0.65 and iep >= 0.65:
        tags.append("memory_echo_aligned")
    elif abs(ims - iep) >= 0.4:
        tags.append("memory_echo_divergent")

    # Entropy interference tags
    if temp_entropy_vol >= 0.65 and ims <= 0.40:
        tags.append("entropy_disrupting_memory")

    # ========================================================================
    # STEP 8: STORE ALL RAW SIGNALS FOR API EXPOSURE
    # ========================================================================

    raw_signals.update({
        "cih": cih,
        "aih": aih,
        "rih": rih,
        "identity_stability": identity_stability,
        "drift_magnitude": drift_magnitude,
        "drift_stability": drift_stability,
        "semantic_integrity": sem_int,
        "symbolic_harmonization": sym_harm,
        "consciousness_order": cons_order,
        "temporal_entropy_volatility": temp_entropy_vol,
        "memory_score": memory_score,
    })

    # ========================================================================
    # STEP 9: RETURN SNAPSHOT
    # ========================================================================

    return IdentityResonanceMemorySnapshot(
        identity_memory_strength=ims,
        identity_echo_persistence=iep,
        identity_drift_anchoring=ida,
        memory_band=memory_band,
        diagnostic_tags=sorted(set(tags)),  # Deduplicate and sort for determinism
        raw_signals=raw_signals,
    )
