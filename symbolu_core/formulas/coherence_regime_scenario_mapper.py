"""
Coherence-Regime Scenario Mapper (CRSM) v1.0 - Phase 41

Deterministic, zero-LLM, observation-only "Coherence-Regime Scenario Mapper" that classifies
each session into high-level regimes based on the full Symbol-U coherence/identity/drift/entropy stack.

CRSM is analytics-only and UI/diagnostics-only.
It must NOT change routing, scoring, mappers, guardrails, or semantics.

CRSM answers: "What kind of session is this?"
  • Stable therapeutic processing
  • Volatile identity drift
  • Balanced exploration
  • etc.

CRSM outputs:
  1. Regime scores across canonical regimes [0.0, 1.0]
  2. Dominant regime (highest score)
  3. Secondary regimes (sorted by score)
  4. Regime band: "stable" | "mixed" | "volatile"
  5. Diagnostic tags
  6. Deterministic notes

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Diagnostics/UI only: Feeds coherence state, session summary, unified API, and DILchat badges
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Fully bounded: All scores [0.0, 1.0]
    - Graceful degradation: Returns None if insufficient data
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import math


@dataclass
class CoherenceRegimeSnapshot:
    """
    Immutable snapshot of Coherence-Regime Scenario Mapper computation.

    Fields:
        dominant_regime: Canonical regime name (e.g., "stable_therapeutic_processing")
        regime_scores: Regime name → score [0.0, 1.0]
        secondary_regimes: Sorted list of non-dominant regimes by score
        regime_band: "stable" | "mixed" | "volatile"
        diagnostic_tags: Symbolic tags (e.g., "CONTEXT_STABLE", "IDENTITY_DRIFT_ELEVATED")
        notes: Short deterministic explanatory notes
    """

    dominant_regime: str
    regime_scores: Dict[str, float] = field(default_factory=dict)
    secondary_regimes: List[str] = field(default_factory=list)
    regime_band: str = "mixed"
    diagnostic_tags: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


# Canonical Regimes (v1.0)
CANONICAL_REGIMES = [
    "stable_therapeutic_processing",
    "volatile_identity_drift",
    "deep_reflective_exploration",
    "surface_level_interaction",
    "ambivalent_conflicted_state",
    "recovery_stabilization_phase",
]


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


def _compute_slope(history: List[float], window: int = 5) -> float:
    """
    Compute simple slope trend from recent history.

    Args:
        history: Historical values (most recent last)
        window: Window size for slope computation

    Returns:
        float: Normalized slope [-1.0, 1.0]
    """
    if not history or len(history) < 2:
        return 0.0

    recent = history[-window:] if len(history) >= window else history

    if len(recent) < 2:
        return 0.0

    # Simple linear slope
    n = len(recent)
    x_mean = (n - 1) / 2.0
    y_mean = sum(recent) / n

    numerator = sum((i - x_mean) * (recent[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return 0.0

    slope = numerator / denominator

    # Normalize to [-1.0, 1.0] using tanh
    return math.tanh(slope * 5.0)


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


def _score_stable_therapeutic_processing(
    coherence_fused: float,
    css: float,
    drift_fusion_index: float,
    entropy_instant: float,
    icc: float,
    v3: float,
) -> float:
    """
    Score: STABLE_THERAPEUTIC_PROCESSING

    High coherence_fused, high CSS, low drift_fusion_index, medium entropy, good ICC.

    Args:
        coherence_fused: Fused coherence [0.0, 1.0]
        css: Continuity Stability Score [0.0, 1.0]
        drift_fusion_index: Drift fusion index [0.0, 1.0]
        entropy_instant: Instant entropy [0.0, 1.0]
        icc: Identity Continuity Coefficient [0.0, 1.0]
        v3: Coherence v3 [0.0, 1.0]

    Returns:
        float: Regime score [0.0, 1.0]
    """
    # High coherence and continuity
    coherence_factor = (0.50 * coherence_fused + 0.30 * css + 0.20 * v3)

    # Low drift (inverted)
    drift_resistance = _clamp(1.0 - drift_fusion_index, 0.0, 1.0)

    # Medium entropy (not too low, not too high)
    # Peak at 0.4-0.6 entropy range
    entropy_factor = 1.0 - abs(entropy_instant - 0.5) * 2.0
    entropy_factor = _clamp(entropy_factor, 0.0, 1.0)

    # Strong identity continuity
    identity_factor = icc

    # Weighted blend
    score = (
        0.35 * coherence_factor +
        0.25 * drift_resistance +
        0.15 * entropy_factor +
        0.25 * identity_factor
    )

    return _clamp(score, 0.0, 1.0)


def _score_volatile_identity_drift(
    drift_fusion_index: float,
    css: float,
    entropy_instant: float,
    icc: float,
    predictive_drift: float,
    cognitive_drift_v3: float,
) -> float:
    """
    Score: VOLATILE_IDENTITY_DRIFT

    High drift_fusion_index, high entropy, low CSS, weak ICC, strong predictive drift.

    Args:
        drift_fusion_index: Drift fusion index [0.0, 1.0]
        css: Continuity Stability Score [0.0, 1.0]
        entropy_instant: Instant entropy [0.0, 1.0]
        icc: Identity Continuity Coefficient [0.0, 1.0]
        predictive_drift: Predictive drift magnitude [0.0, 1.0]
        cognitive_drift_v3: Cognitive drift v3 [0.0, 1.0]

    Returns:
        float: Regime score [0.0, 1.0]
    """
    # High drift indicators
    drift_factor = (
        0.40 * drift_fusion_index +
        0.35 * predictive_drift +
        0.25 * cognitive_drift_v3
    )

    # High entropy
    entropy_factor = entropy_instant

    # Low continuity/stability (inverted)
    instability_factor = _clamp(1.0 - css, 0.0, 1.0)

    # Weak identity continuity (inverted)
    weak_identity = _clamp(1.0 - icc, 0.0, 1.0)

    # Weighted blend
    score = (
        0.35 * drift_factor +
        0.25 * entropy_factor +
        0.20 * instability_factor +
        0.20 * weak_identity
    )

    return _clamp(score, 0.0, 1.0)


def _score_deep_reflective_exploration(
    v3: float,
    ucf_cip: float,
    shi: float,
    resonance_entropy: float,
    insight_window_active: bool,
    entropy_instant: float,
) -> float:
    """
    Score: DEEP_REFLECTIVE_EXPLORATION

    High v3, high UCF CIP, strong SHI, moderate to high resonance entropy, active insight window.

    Args:
        v3: Coherence v3 [0.0, 1.0]
        ucf_cip: UCF Consciousness Integration Potential [0.0, 1.0]
        shi: Symbolic Harmonization Index [0.0, 1.0]
        resonance_entropy: Resonance weighting entropy [0.0, 1.0]
        insight_window_active: Insight window gating active
        entropy_instant: Instant entropy [0.0, 1.0]

    Returns:
        float: Regime score [0.0, 1.0]
    """
    # High v3 quality and insight
    quality_factor = (0.50 * v3 + 0.50 * ucf_cip)

    # Strong symbolic harmonization
    symbolic_factor = shi

    # Moderate to high entropy (exploration space)
    # Peak at 0.5-0.7 entropy range
    exploration_entropy = entropy_instant
    if entropy_instant >= 0.5 and entropy_instant <= 0.7:
        exploration_entropy = 1.0
    elif entropy_instant < 0.5:
        exploration_entropy = entropy_instant * 2.0
    else:
        exploration_entropy = _clamp(1.0 - (entropy_instant - 0.7) * 2.0, 0.5, 1.0)

    # Insight window bonus
    insight_bonus = 0.15 if insight_window_active else 0.0

    # Weighted blend
    score = (
        0.35 * quality_factor +
        0.30 * symbolic_factor +
        0.20 * exploration_entropy +
        0.15 * resonance_entropy
    )

    score = min(score + insight_bonus, 1.0)

    return _clamp(score, 0.0, 1.0)


def _score_surface_level_interaction(
    v3_quality: float,
    shi: float,
    ncc: float,
    drift_fusion_index: float,
    ims: float,
    icc: float,
) -> float:
    """
    Score: SURFACE_LEVEL_INTERACTION

    Low v3 quality, low insight depth, low SHI, low identity measures.

    Args:
        v3_quality: Coherence v3 quality [0.0, 1.0]
        shi: Symbolic Harmonization Index [0.0, 1.0]
        ncc: Narrative Continuity Coefficient [0.0, 1.0]
        drift_fusion_index: Drift fusion index [0.0, 1.0]
        ims: Identity Memory Strength [0.0, 1.0]
        icc: Identity Continuity Coefficient [0.0, 1.0]

    Returns:
        float: Regime score [0.0, 1.0]
    """
    # Low depth indicators (inverted)
    low_v3_quality = _clamp(1.0 - v3_quality, 0.0, 1.0)
    low_shi = _clamp(1.0 - shi, 0.0, 1.0)
    low_ncc = _clamp(1.0 - ncc, 0.0, 1.0)

    # Low identity (inverted)
    low_identity = (
        0.50 * _clamp(1.0 - ims, 0.0, 1.0) +
        0.50 * _clamp(1.0 - icc, 0.0, 1.0)
    )

    # Neutral drift (not volatile, not stable)
    neutral_drift = 1.0 - abs(drift_fusion_index - 0.5) * 2.0
    neutral_drift = _clamp(neutral_drift, 0.0, 1.0)

    # Weighted blend
    score = (
        0.30 * low_v3_quality +
        0.25 * low_shi +
        0.20 * low_ncc +
        0.15 * low_identity +
        0.10 * neutral_drift
    )

    return _clamp(score, 0.0, 1.0)


def _score_ambivalent_conflicted_state(
    entropy_instant: float,
    coherence_fused: float,
    ims: float,
    iep: float,
    drift_fusion_index: float,
    dft: float,
) -> float:
    """
    Score: AMBIVALENT_CONFLICTED_STATE

    High tension/entropy, medium coherence, mixed identity signals.

    Args:
        entropy_instant: Instant entropy [0.0, 1.0]
        coherence_fused: Fused coherence [0.0, 1.0]
        ims: Identity Memory Strength [0.0, 1.0]
        iep: Identity Echo Persistence [0.0, 1.0]
        drift_fusion_index: Drift fusion index [0.0, 1.0]
        dft: Drift-Forecast Tension [0.0, 1.0]

    Returns:
        float: Regime score [0.0, 1.0]
    """
    # High entropy/tension
    tension_factor = (0.60 * entropy_instant + 0.40 * dft)

    # Medium coherence (mid-range)
    # Peak at 0.4-0.6 coherence range
    medium_coherence = 1.0 - abs(coherence_fused - 0.5) * 2.0
    medium_coherence = _clamp(medium_coherence, 0.0, 1.0)

    # Mixed identity signals (moderate values, not extreme)
    identity_ambivalence = (
        0.50 * (1.0 - abs(ims - 0.5) * 2.0) +
        0.50 * (1.0 - abs(iep - 0.5) * 2.0)
    )
    identity_ambivalence = _clamp(identity_ambivalence, 0.0, 1.0)

    # Moderate drift (conflict zone)
    conflict_drift = 1.0 - abs(drift_fusion_index - 0.5) * 2.0
    conflict_drift = _clamp(conflict_drift, 0.0, 1.0)

    # Weighted blend
    score = (
        0.40 * tension_factor +
        0.25 * medium_coherence +
        0.20 * identity_ambivalence +
        0.15 * conflict_drift
    )

    return _clamp(score, 0.0, 1.0)


def _score_recovery_stabilization_phase(
    coherence_slope: float,
    continuity_slope: float,
    entropy_slope: float,
    drift_slope: float,
    css: float,
) -> float:
    """
    Score: RECOVERY_STABILIZATION_PHASE

    Positive coherence/continuity slopes, decreasing entropy/drift vs history, moderate CSS trending up.

    Args:
        coherence_slope: Coherence trajectory slope [-1.0, 1.0]
        continuity_slope: Continuity trajectory slope [-1.0, 1.0]
        entropy_slope: Entropy trend slope [-1.0, 1.0]
        drift_slope: Drift trend slope [-1.0, 1.0]
        css: Continuity Stability Score [0.0, 1.0]

    Returns:
        float: Regime score [0.0, 1.0]
    """
    # Positive coherence/continuity slopes
    positive_coherence = _clamp((coherence_slope + 1.0) / 2.0, 0.0, 1.0)
    positive_continuity = _clamp((continuity_slope + 1.0) / 2.0, 0.0, 1.0)

    improvement_factor = (
        0.55 * positive_coherence +
        0.45 * positive_continuity
    )

    # Decreasing entropy/drift (negative slopes are good)
    decreasing_entropy = _clamp((1.0 - entropy_slope) / 2.0, 0.0, 1.0)
    decreasing_drift = _clamp((1.0 - drift_slope) / 2.0, 0.0, 1.0)

    stabilization_factor = (
        0.50 * decreasing_entropy +
        0.50 * decreasing_drift
    )

    # Moderate CSS (trending up)
    # CSS in 0.4-0.7 range is ideal for recovery
    css_recovery_zone = 0.0
    if css >= 0.4 and css <= 0.7:
        css_recovery_zone = 1.0
    elif css < 0.4:
        css_recovery_zone = css * 2.5
    else:
        css_recovery_zone = _clamp(1.0 - (css - 0.7) * 2.0, 0.5, 1.0)

    # Weighted blend
    score = (
        0.40 * improvement_factor +
        0.35 * stabilization_factor +
        0.25 * css_recovery_zone
    )

    return _clamp(score, 0.0, 1.0)


def _determine_regime_band(
    dominant_regime: str,
    dominant_score: float,
    second_score: float,
) -> str:
    """
    Determine regime band classification.

    Args:
        dominant_regime: Dominant regime name
        dominant_score: Score of dominant regime
        second_score: Score of second-place regime

    Returns:
        str: "stable" | "mixed" | "volatile"
    """
    # Check if dominant regime is stable/therapeutic or recovery
    stable_regimes = ["stable_therapeutic_processing", "recovery_stabilization_phase"]
    volatile_regimes = ["volatile_identity_drift", "ambivalent_conflicted_state"]

    # Check score margin
    score_margin = dominant_score - second_score

    # Stable band: stable/therapeutic regime with high score and clear margin
    if dominant_regime in stable_regimes and dominant_score >= 0.65 and score_margin >= 0.15:
        return "stable"

    # Volatile band: volatile/ambivalent regime dominates
    if dominant_regime in volatile_regimes and dominant_score >= 0.60:
        return "volatile"

    # Mixed band: close scores or mixed regime
    if score_margin <= 0.15:
        return "mixed"

    # Default: mixed
    return "mixed"


def _generate_diagnostic_tags(
    regime_scores: Dict[str, float],
    dominant_regime: str,
    regime_band: str,
    coherence_fused: float,
    drift_fusion_index: float,
    css: float,
    entropy_instant: float,
) -> List[str]:
    """
    Generate deterministic diagnostic tags.

    Args:
        regime_scores: All regime scores
        dominant_regime: Dominant regime name
        regime_band: Regime band classification
        coherence_fused: Fused coherence [0.0, 1.0]
        drift_fusion_index: Drift fusion index [0.0, 1.0]
        css: Continuity Stability Score [0.0, 1.0]
        entropy_instant: Instant entropy [0.0, 1.0]

    Returns:
        List[str]: Diagnostic tags
    """
    tags = []

    # Band tags
    if regime_band == "stable":
        tags.append("CONTEXT_STABLE")
    elif regime_band == "volatile":
        tags.append("CONTEXT_VOLATILE")
    elif regime_band == "mixed":
        tags.append("CONTEXT_MIXED")

    # Drift tags
    if drift_fusion_index >= 0.65:
        tags.append("IDENTITY_DRIFT_ELEVATED")
    elif drift_fusion_index <= 0.30:
        tags.append("IDENTITY_DRIFT_LOW")

    # Recovery pattern
    if dominant_regime == "recovery_stabilization_phase":
        tags.append("RECOVERY_PATTERN_DETECTED")

    # Exploration pattern
    if dominant_regime == "deep_reflective_exploration":
        tags.append("EXPLORATION_MODE_ACTIVE")

    # Surface level
    if dominant_regime == "surface_level_interaction":
        tags.append("SURFACE_LEVEL_ENGAGEMENT")

    # Conflict/ambivalence
    if dominant_regime == "ambivalent_conflicted_state":
        tags.append("CONFLICT_TENSION_ELEVATED")

    # High coherence
    if coherence_fused >= 0.70:
        tags.append("COHERENCE_STRONG")
    elif coherence_fused <= 0.35:
        tags.append("COHERENCE_WEAK")

    # High continuity
    if css >= 0.70:
        tags.append("CONTINUITY_STRONG")
    elif css <= 0.35:
        tags.append("CONTINUITY_FRAGMENTED")

    # Entropy tags
    if entropy_instant >= 0.70:
        tags.append("ENTROPY_ELEVATED")
    elif entropy_instant <= 0.30:
        tags.append("ENTROPY_LOW")

    # Regime-specific tags
    tags.append(f"regime_{dominant_regime}")
    tags.append(f"regime_band_{regime_band}")

    return sorted(set(tags))


def _generate_notes(
    dominant_regime: str,
    regime_band: str,
    drift_fusion_index: float,
    css: float,
) -> List[str]:
    """
    Generate deterministic explanatory notes.

    Args:
        dominant_regime: Dominant regime name
        regime_band: Regime band classification
        drift_fusion_index: Drift fusion index [0.0, 1.0]
        css: Continuity Stability Score [0.0, 1.0]

    Returns:
        List[str]: Notes
    """
    notes = []

    # Primary note
    drift_level = "low" if drift_fusion_index < 0.35 else "moderate" if drift_fusion_index < 0.65 else "high"
    css_level = "low" if css < 0.40 else "moderate" if css < 0.70 else "high"

    primary_note = f"dominant_regime={dominant_regime} with {drift_level} drift and {css_level} continuity"
    notes.append(primary_note)

    # Band note
    notes.append(f"regime_band={regime_band}")

    # Regime-specific notes
    if dominant_regime == "stable_therapeutic_processing":
        notes.append("session_exhibits_stable_therapeutic_processing_pattern")
    elif dominant_regime == "volatile_identity_drift":
        notes.append("session_exhibits_identity_drift_volatility")
    elif dominant_regime == "deep_reflective_exploration":
        notes.append("session_exhibits_deep_reflective_exploration")
    elif dominant_regime == "surface_level_interaction":
        notes.append("session_exhibits_surface_level_interaction")
    elif dominant_regime == "ambivalent_conflicted_state":
        notes.append("session_exhibits_ambivalent_conflicted_state")
    elif dominant_regime == "recovery_stabilization_phase":
        notes.append("session_exhibits_recovery_stabilization_pattern")

    return notes


def compute_coherence_regime(
    *,
    # Phase 16: Formula Fusion Stabilizer
    coherence_fused: Optional[float] = None,
    coherence_fused_history: Optional[List[float]] = None,
    # Phase 10: Coherence v3
    coherence_v3: Optional[float] = None,
    # Phase 12: Coherence v3 quality
    coherence_v3_quality: Optional[float] = None,
    # Phase 26: Unified Consciousness Formula
    ucf_coi: Optional[float] = None,
    ucf_csi: Optional[float] = None,
    ucf_cip: Optional[float] = None,
    # Phase 27: Symbolic Harmonization
    symbolic_harmonization_index: Optional[float] = None,
    # Phase 24: Resonance Weighting
    resonance_weighting_entropy: Optional[float] = None,
    # Phase 34: Identity Harmonics
    identity_stability_score: Optional[float] = None,
    # Phase 35: Predictive Persona Drift
    drift_magnitude_prediction: Optional[float] = None,
    # Phase 36: Identity Resonance Memory
    identity_memory_strength: Optional[float] = None,
    identity_echo_persistence: Optional[float] = None,
    identity_drift_anchoring: Optional[float] = None,
    # Phase 19: Drift Fusion
    drift_fusion_index: Optional[float] = None,
    drift_fusion_index_history: Optional[List[float]] = None,
    # Phase 17: Semantic Integrity & Cognitive Drift v3
    cognitive_drift_v3: Optional[float] = None,
    # Phase 18: Temporal Entropy
    temporal_entropy_instant: Optional[float] = None,
    temporal_entropy_volatility: Optional[float] = None,
    temporal_entropy_volatility_history: Optional[List[float]] = None,
    # Phase 37: Adaptive Continuity Engine
    ncc: Optional[float] = None,
    icc: Optional[float] = None,
    css: Optional[float] = None,
    css_history: Optional[List[float]] = None,
    # Phase 38: Temporal Coherence Forecasting
    coherence_slope: Optional[float] = None,
    continuity_slope: Optional[float] = None,
    # Phase 40: Cross-Horizon Resonance Alignment
    drift_forecast_tension: Optional[float] = None,
    # Phase 32: Insight Window Gating (if available)
    insight_window_active: Optional[bool] = None,
) -> Optional[CoherenceRegimeSnapshot]:
    """
    Compute Coherence-Regime Scenario Mapper (CRSM) v1.0.

    This formula classifies the current session into canonical coherence regimes based on
    the full Symbol-U coherence/identity/drift/entropy stack.

    The result is a regime snapshot containing:
      1. Regime scores for all canonical regimes [0.0, 1.0]
      2. Dominant regime (highest score)
      3. Secondary regimes (sorted by score, excluding dominant)
      4. Regime band: "stable" | "mixed" | "volatile"
      5. Diagnostic tags
      6. Deterministic notes

    Args:
        coherence_fused: Fused coherence from Phase 16 [0.0, 1.0]
        coherence_fused_history: Historical fused coherence values
        coherence_v3: Coherence v3 from Phase 10 [0.0, 1.0]
        coherence_v3_quality: Coherence v3 quality from Phase 12 [0.0, 1.0]
        ucf_coi: UCF Consciousness Order Index from Phase 26 [0.0, 1.0]
        ucf_csi: UCF Consciousness Stability Index from Phase 26 [0.0, 1.0]
        ucf_cip: UCF Consciousness Integration Potential from Phase 26 [0.0, 1.0]
        symbolic_harmonization_index: SHI from Phase 27 [0.0, 1.0]
        resonance_weighting_entropy: Resonance entropy from Phase 24 [0.0, 1.0]
        identity_stability_score: Identity stability from Phase 34 [0.0, 1.0]
        drift_magnitude_prediction: DMP from Phase 35 [0.0, 1.0]
        identity_memory_strength: IMS from Phase 36 [0.0, 1.0]
        identity_echo_persistence: IEP from Phase 36 [0.0, 1.0]
        identity_drift_anchoring: IDA from Phase 36 [0.0, 1.0]
        drift_fusion_index: Drift fusion index from Phase 19 [0.0, 1.0]
        drift_fusion_index_history: Historical drift fusion values
        cognitive_drift_v3: Cognitive drift v3 from Phase 17 [0.0, 1.0]
        temporal_entropy_instant: Instant entropy from Phase 18 [0.0, 1.0]
        temporal_entropy_volatility: Entropy volatility from Phase 18 [0.0, 1.0]
        temporal_entropy_volatility_history: Historical entropy volatility
        ncc: Narrative Continuity Coefficient from Phase 37 [0.0, 1.0]
        icc: Identity Continuity Coefficient from Phase 37 [0.0, 1.0]
        css: Continuity Stability Score from Phase 37 [0.0, 1.0]
        css_history: Historical CSS values
        coherence_slope: Coherence trajectory slope from Phase 38 [-1.0, 1.0]
        continuity_slope: Continuity trajectory slope from Phase 38 [-1.0, 1.0]
        drift_forecast_tension: DFT from Phase 40 [0.0, 1.0]
        insight_window_active: Insight window gating active (Phase 32)

    Returns:
        CoherenceRegimeSnapshot or None if insufficient data

    Graceful Degradation:
        Returns None if we lack essential core signals:
          - coherence_fused OR coherence_v3
          - drift_fusion_index
          - css
    """
    # ========================================================================
    # STEP 1: CHECK CORE INPUT AVAILABILITY (Graceful Degradation)
    # ========================================================================

    # Require essential core signals
    has_coherence = any([coherence_fused is not None, coherence_v3 is not None])
    has_drift = drift_fusion_index is not None
    has_continuity = css is not None

    if not (has_coherence and has_drift and has_continuity):
        # Insufficient data for CRSM computation
        return None

    # ========================================================================
    # STEP 2: EXTRACT SIGNALS WITH SAFE FALLBACKS
    # ========================================================================

    # Phase 16: Coherence Fusion
    coh_fused = _safe_get(coherence_fused, 0.5)

    # Phase 10: Coherence v3
    v3 = _safe_get(coherence_v3, 0.5)

    # Phase 12: Coherence v3 quality
    v3_quality = _safe_get(coherence_v3_quality, 0.5)

    # Phase 26: Unified Consciousness Formula
    coi = _safe_get(ucf_coi, 0.5)
    csi = _safe_get(ucf_csi, 0.5)
    cip = _safe_get(ucf_cip, 0.5)

    # Phase 27: Symbolic Harmonization
    shi = _safe_get(symbolic_harmonization_index, 0.5)

    # Phase 24: Resonance Weighting
    res_weight_ent = _safe_get(resonance_weighting_entropy, 0.5)

    # Phase 34: Identity Harmonics
    identity_stability = _safe_get(identity_stability_score, 0.5)

    # Phase 35: Predictive Persona Drift
    predictive_drift = _safe_get(drift_magnitude_prediction, 0.5)

    # Phase 36: Identity Resonance Memory
    ims = _safe_get(identity_memory_strength, 0.5)
    iep = _safe_get(identity_echo_persistence, 0.5)
    ida = _safe_get(identity_drift_anchoring, 0.5)

    # Phase 19: Drift Fusion
    drift_fusion_idx = _safe_get(drift_fusion_index, 0.5)

    # Phase 17: Semantic Integrity & Cognitive Drift v3
    cognitive_drift = _safe_get(cognitive_drift_v3, 0.5)

    # Phase 18: Temporal Entropy
    entropy_instant = _safe_get(temporal_entropy_instant, 0.5)
    entropy_volatility = _safe_get(temporal_entropy_volatility, 0.5)

    # Phase 37: Adaptive Continuity Engine
    ncc_val = _safe_get(ncc, 0.5)
    icc_val = _safe_get(icc, 0.5)
    css_val = _safe_get(css, 0.5)

    # Phase 38: Temporal Coherence Forecasting
    coh_slope = _safe_get(coherence_slope, 0.0)
    cont_slope = _safe_get(continuity_slope, 0.0)

    # Phase 40: Cross-Horizon Resonance Alignment
    dft = _safe_get(drift_forecast_tension, 0.5)

    # Phase 32: Insight Window Gating
    insight_active = insight_window_active if insight_window_active is not None else False

    # ========================================================================
    # STEP 3: COMPUTE SLOPE TRENDS FOR RECOVERY REGIME
    # ========================================================================

    # Entropy slope (decreasing is good for recovery)
    entropy_slope = 0.0
    if temporal_entropy_volatility_history and len(temporal_entropy_volatility_history) >= 3:
        entropy_slope = _compute_slope(temporal_entropy_volatility_history, window=5)

    # Drift slope (decreasing is good for recovery)
    drift_slope = 0.0
    if drift_fusion_index_history and len(drift_fusion_index_history) >= 3:
        drift_slope = _compute_slope(drift_fusion_index_history, window=5)

    # ========================================================================
    # STEP 4: COMPUTE REGIME SCORES
    # ========================================================================

    regime_scores = {}

    # 1. STABLE_THERAPEUTIC_PROCESSING
    regime_scores["stable_therapeutic_processing"] = _score_stable_therapeutic_processing(
        coherence_fused=coh_fused,
        css=css_val,
        drift_fusion_index=drift_fusion_idx,
        entropy_instant=entropy_instant,
        icc=icc_val,
        v3=v3,
    )

    # 2. VOLATILE_IDENTITY_DRIFT
    regime_scores["volatile_identity_drift"] = _score_volatile_identity_drift(
        drift_fusion_index=drift_fusion_idx,
        css=css_val,
        entropy_instant=entropy_instant,
        icc=icc_val,
        predictive_drift=predictive_drift,
        cognitive_drift_v3=cognitive_drift,
    )

    # 3. DEEP_REFLECTIVE_EXPLORATION
    regime_scores["deep_reflective_exploration"] = _score_deep_reflective_exploration(
        v3=v3,
        ucf_cip=cip,
        shi=shi,
        resonance_entropy=res_weight_ent,
        insight_window_active=insight_active,
        entropy_instant=entropy_instant,
    )

    # 4. SURFACE_LEVEL_INTERACTION
    regime_scores["surface_level_interaction"] = _score_surface_level_interaction(
        v3_quality=v3_quality,
        shi=shi,
        ncc=ncc_val,
        drift_fusion_index=drift_fusion_idx,
        ims=ims,
        icc=icc_val,
    )

    # 5. AMBIVALENT_CONFLICTED_STATE
    regime_scores["ambivalent_conflicted_state"] = _score_ambivalent_conflicted_state(
        entropy_instant=entropy_instant,
        coherence_fused=coh_fused,
        ims=ims,
        iep=iep,
        drift_fusion_index=drift_fusion_idx,
        dft=dft,
    )

    # 6. RECOVERY_STABILIZATION_PHASE
    regime_scores["recovery_stabilization_phase"] = _score_recovery_stabilization_phase(
        coherence_slope=coh_slope,
        continuity_slope=cont_slope,
        entropy_slope=entropy_slope,
        drift_slope=drift_slope,
        css=css_val,
    )

    # ========================================================================
    # STEP 5: SELECT DOMINANT REGIME AND SECONDARY REGIMES
    # ========================================================================

    # Sort regimes by score (descending)
    sorted_regimes = sorted(regime_scores.items(), key=lambda x: x[1], reverse=True)

    dominant_regime = sorted_regimes[0][0]
    dominant_score = sorted_regimes[0][1]

    # Secondary regimes (all except dominant, sorted by score)
    secondary_regimes = [regime for regime, _ in sorted_regimes[1:]]

    # ========================================================================
    # STEP 6: DETERMINE REGIME BAND
    # ========================================================================

    second_score = sorted_regimes[1][1] if len(sorted_regimes) > 1 else 0.0

    regime_band = _determine_regime_band(
        dominant_regime=dominant_regime,
        dominant_score=dominant_score,
        second_score=second_score,
    )

    # ========================================================================
    # STEP 7: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    diagnostic_tags = _generate_diagnostic_tags(
        regime_scores=regime_scores,
        dominant_regime=dominant_regime,
        regime_band=regime_band,
        coherence_fused=coh_fused,
        drift_fusion_index=drift_fusion_idx,
        css=css_val,
        entropy_instant=entropy_instant,
    )

    # ========================================================================
    # STEP 8: GENERATE NOTES
    # ========================================================================

    notes = _generate_notes(
        dominant_regime=dominant_regime,
        regime_band=regime_band,
        drift_fusion_index=drift_fusion_idx,
        css=css_val,
    )

    # ========================================================================
    # STEP 9: RETURN SNAPSHOT
    # ========================================================================

    return CoherenceRegimeSnapshot(
        dominant_regime=dominant_regime,
        regime_scores=regime_scores,
        secondary_regimes=secondary_regimes,
        regime_band=regime_band,
        diagnostic_tags=diagnostic_tags,
        notes=notes,
    )
