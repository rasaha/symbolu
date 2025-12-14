"""
Formula Fusion Stabilizer v1.0 - Phase 16

Deterministic, zero-LLM stabilization layer that produces a new observable metric:
    coherence_fused — the stability-weighted, time-smoothed blend of:
        • coherence_score_v1 (baseline)
        • coherence_score_v2 (formula-aware)
        • coherence_score_v3 (megafusion)
        • coherence_v3_quality (Phase 12)
        • enhanced_smi (Phase 13)
        • VMF momentum + ATH harmonizer (Phase 14)
        • Guna/Kosha resonance indices (Phase 8)
        • Temporal inertia (sliding window)

CRITICAL:
    - This metric is OBSERVATION-ONLY
    - Feature-flag gated
    - Does NOT alter routing/mappers/policy safety layers
    - No change to v1/v2/v3 formulas or their activation logic
    - Fully deterministic, zero-LLM
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
import statistics


@dataclass
class FusionStabilizerSnapshot:
    """
    Immutable snapshot of formula fusion stabilizer computation.

    Fields:
        coherence_fused: Final fused coherence score [0.0, 1.0] or None
        stability_weight: Stability factor based on history variance [0.0, 1.0]
        inertia_factor: Temporal inertia factor [0.5, 1.0]
        quality_factor: Quality gating factor from v3_quality [0.0, 1.0]
        component_scores: Dictionary of all input component scores
    """

    coherence_fused: Optional[float]
    stability_weight: float
    inertia_factor: float
    quality_factor: float
    component_scores: Dict[str, Optional[float]]


def _safe(value: Optional[float]) -> float:
    """
    Safe accessor for optional float values.

    Args:
        value: Optional float value

    Returns:
        float: The value if not None, else 0.0
    """
    return value if value is not None else 0.0


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp value to [min_val, max_val] range.

    Args:
        value: Value to clamp
        min_val: Minimum value
        max_val: Maximum value

    Returns:
        float: Clamped value
    """
    return max(min_val, min(max_val, value))


def _compute_stability_weight(history_last_5: List[Optional[float]]) -> float:
    """
    Compute stability weight based on variance and monotonicity of history.

    Stability weight is higher when:
    - Low variance in recent history
    - Scores are consistent and stable

    Args:
        history_last_5: Last 5 coherence scores from history

    Returns:
        float: Stability weight [0.0, 1.0]
    """
    # Filter out None values
    valid_history = [h for h in history_last_5 if h is not None]

    # Not enough history → assume low stability (0.5 neutral)
    if len(valid_history) < 2:
        return 0.5

    # Compute variance
    try:
        variance = statistics.variance(valid_history)
    except statistics.StatisticsError:
        # Edge case: identical values (variance = 0)
        variance = 0.0

    # Stability = 1.0 - variance (clamped to [0, 1])
    # Lower variance → higher stability
    stability = 1.0 - variance
    return _clamp(stability, 0.0, 1.0)


def _compute_inertia_factor(stability_weight: float) -> float:
    """
    Compute temporal inertia factor based on stability.

    Inertia factor specifies how much weight to give to historical momentum
    vs. current blended score.

    Higher stability → higher inertia (more trust in historical continuity)
    Lower stability → lower inertia (more trust in current computation)

    Args:
        stability_weight: Stability weight [0.0, 1.0]

    Returns:
        float: Inertia factor [0.5, 1.0]
    """
    # Inertia ranges from 0.5 (low stability) to 1.0 (high stability)
    inertia = 0.5 + 0.5 * stability_weight
    return _clamp(inertia, 0.5, 1.0)


def _compute_quality_factor(v3_quality: Optional[float]) -> float:
    """
    Compute quality gating factor from v3_quality.

    If v3_quality exists, use it directly.
    Otherwise, return 0.0 (no quality gating).

    Args:
        v3_quality: Coherence v3 quality metric [0.0, 1.0] or None

    Returns:
        float: Quality factor [0.0, 1.0]
    """
    if v3_quality is not None:
        return _clamp(v3_quality, 0.0, 1.0)
    return 0.0


def compute_coherence_fused(
    v1: Optional[float],
    v2: Optional[float],
    v3: Optional[float],
    v3_quality: Optional[float],
    enhanced_smi: Optional[float],
    vritti_momentum: Optional[float],
    arc_tension_harmonizer: Optional[float],
    guna_resonance: Optional[float],
    kosha_resonance: Optional[float],
    history_last_5: List[Optional[float]],
) -> FusionStabilizerSnapshot:
    """
    Compute fused coherence score with stability-weighted temporal smoothing.

    This is the main Formula Fusion Stabilizer computation function.

    Algorithm:
        1. Compute stability_weight from history variance
        2. Compute inertia_factor from stability
        3. Compute quality_factor from v3_quality
        4. Blend all component scores with weighted formula
        5. Apply temporal inertia smoothing with last historical value

    Blending Formula:
        fused_raw = clamp(
            0.40 * safe(v1)
          + 0.25 * safe(v2)
          + 0.20 * safe(v3) * quality_factor
          + 0.05 * safe(enhanced_smi)
          + 0.05 * safe(arc_tension_harmonizer)
          + 0.03 * safe(guna_resonance)
          + 0.02 * safe(kosha_resonance),
          0.0, 1.0
        )

    Temporal Inertia:
        coherence_fused = inertia * fused_raw + (1 - inertia) * safe(history_last_5[-1])

    Args:
        v1: Coherence score v1 (baseline canonical) [0.0, 1.0]
        v2: Coherence score v2 (formula-aware) [0.0, 1.0]
        v3: Coherence score v3 (megafusion) [0.0, 1.0]
        v3_quality: Coherence v3 quality metric [0.0, 1.0]
        enhanced_smi: Enhanced SMI from Phase 13 [0.0, 1.0]
        vritti_momentum: Vritti Momentum from Phase 14 [0.0, 1.0]
        arc_tension_harmonizer: Arc-Tension Harmonizer from Phase 14 [0.0, 1.0]
        guna_resonance: Guna resonance index from Phase 8 [0.0, 1.0]
        kosha_resonance: Kosha resonance index from Phase 8 [0.0, 1.0]
        history_last_5: Last 5 coherence scores (v1) for temporal inertia

    Returns:
        FusionStabilizerSnapshot: Complete snapshot with fused score and diagnostics

    Note:
        - All math is deterministic and zero-LLM
        - Missing inputs are treated as 0.0 (safe fallback)
        - If v1 is None, coherence_fused will be None (cannot compute without baseline)
        - Quality factor gates v3 contribution (low quality → low v3 weight)
    """
    # Store all component scores for diagnostics
    component_scores = {
        "v1": v1,
        "v2": v2,
        "v3": v3,
        "v3_quality": v3_quality,
        "enhanced_smi": enhanced_smi,
        "vritti_momentum": vritti_momentum,
        "arc_tension_harmonizer": arc_tension_harmonizer,
        "guna_resonance": guna_resonance,
        "kosha_resonance": kosha_resonance,
    }

    # CRITICAL: Cannot compute fused score without baseline v1
    if v1 is None:
        return FusionStabilizerSnapshot(
            coherence_fused=None,
            stability_weight=0.0,
            inertia_factor=0.5,
            quality_factor=0.0,
            component_scores=component_scores,
        )

    # Step 1: Compute stability weight from history
    stability_weight = _compute_stability_weight(history_last_5)

    # Step 2: Compute inertia factor from stability
    inertia_factor = _compute_inertia_factor(stability_weight)

    # Step 3: Compute quality factor from v3_quality
    quality_factor = _compute_quality_factor(v3_quality)

    # Step 4: Blend all components with weighted formula
    # NOTE: v3 is gated by quality_factor
    fused_raw = _clamp(
        0.40 * _safe(v1)
        + 0.25 * _safe(v2)
        + 0.20 * _safe(v3) * quality_factor
        + 0.05 * _safe(enhanced_smi)
        + 0.05 * _safe(arc_tension_harmonizer)
        + 0.03 * _safe(guna_resonance)
        + 0.02 * _safe(kosha_resonance),
        0.0,
        1.0,
    )

    # Step 5: Apply temporal inertia smoothing
    # Get last historical value (v1 baseline)
    last_value = None
    if history_last_5:
        # Get most recent non-None value from history
        for val in reversed(history_last_5):
            if val is not None:
                last_value = val
                break

    # If no history, fused = raw (no smoothing)
    if last_value is None:
        coherence_fused = fused_raw
    else:
        # Apply inertia: inertia * raw + (1 - inertia) * last
        # Higher inertia → more weight to raw (current computation)
        # Lower inertia → more weight to last (historical momentum)
        coherence_fused = inertia_factor * fused_raw + (1 - inertia_factor) * last_value
        coherence_fused = _clamp(coherence_fused, 0.0, 1.0)

    return FusionStabilizerSnapshot(
        coherence_fused=coherence_fused,
        stability_weight=stability_weight,
        inertia_factor=inertia_factor,
        quality_factor=quality_factor,
        component_scores=component_scores,
    )
