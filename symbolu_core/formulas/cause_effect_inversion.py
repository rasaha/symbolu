"""
Cause-Effect Inversion Analytics v1.0 - Phase 23

Deterministic, zero-LLM analytical layer that estimates when the mirror-time
explanation of a session fits better than the naive forward-time "cause → effect" reading.

Computes:
  • forward_alignment: Forward-time trajectory alignment [0.0, 1.0]
  • mirror_alignment: Mirror-time reflection alignment [0.0, 1.0]
  • inversion_score: Likelihood of inversion explanation [0.0, 1.0]
  • inversion_band: Classification of inversion plausibility
  • cause_chain_stability: Stability of cause-effect chain [0.0, 1.0]
  • notes: Diagnostic tags for interpretation

CRITICAL:
    - Zero-LLM: Pure math & simple statistics only
    - Non-invasive: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Observation-only: Outputs used only for diagnostics & analytics (no behavior change)
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs
"""

from dataclasses import dataclass, field
from typing import List, Optional, Sequence
import statistics


@dataclass
class CauseEffectInversionSnapshot:
    """
    Immutable snapshot of cause-effect inversion computation.

    Fields:
        forward_alignment: Forward-time trajectory alignment [0.0, 1.0]
        mirror_alignment: Mirror-time reflection alignment [0.0, 1.0]
        inversion_score: Likelihood of inversion explanation [0.0, 1.0]
        inversion_band: Classification ("forward_dominant" | "ambiguous" |
                        "inversion_plausible" | "inversion_dominant")
        cause_chain_stability: Stability of cause-effect chain [0.0, 1.0]
        notes: List of human-readable diagnostic tags
    """

    forward_alignment: float
    mirror_alignment: float
    inversion_score: float
    inversion_band: str
    cause_chain_stability: float
    notes: List[str]


def _clamp_01(x: float) -> float:
    """
    Clamp value to [0.0, 1.0] range.

    Args:
        x: Value to clamp

    Returns:
        float: Clamped value in [0.0, 1.0]
    """
    return max(0.0, min(1.0, x))


def _safe_mean(values: Sequence[float]) -> float:
    """
    Compute mean of values, handling empty sequences gracefully.

    Args:
        values: Sequence of numeric values

    Returns:
        float: Mean value, or 0.5 if sequence is empty (neutral default)
    """
    if not values:
        return 0.5
    return sum(values) / len(values)


def _safe_stdev(values: Sequence[float]) -> float:
    """
    Compute standard deviation of values, handling edge cases gracefully.

    Args:
        values: Sequence of numeric values

    Returns:
        float: Standard deviation, or 0.0 if insufficient data
    """
    if not values or len(values) < 2:
        return 0.0

    try:
        return statistics.stdev(values)
    except statistics.StatisticsError:
        return 0.0


def _compute_forward_alignment(
    coherence_history: Sequence[float],
    semantic_integrity: Optional[float],
    temporal_entropy_diff: Optional[float],
) -> float:
    """
    Compute forward-time alignment from coherence and semantic integrity.

    Forward alignment measures how well the conversation fits a forward-time
    "cause → effect" explanation, based on coherence trends and semantic integrity.

    Formula:
        1. Compute coherence trend (positive slope → improving)
        2. Weight coherence trend with semantic integrity
        3. Adjust for temporal entropy (high asymmetry → lower forward alignment)

    Args:
        coherence_history: Historical coherence values [0.0, 1.0]
        semantic_integrity: Current semantic integrity score [0.0, 1.0] (optional)
        temporal_entropy_diff: Normalized entropy diff [0.0, 1.0] (optional)

    Returns:
        float: Forward alignment score [0.0, 1.0]
    """
    if not coherence_history:
        return 0.5  # Neutral default

    # Compute coherence trend (linear gradient)
    n = len(coherence_history)
    if n >= 2:
        indices = list(range(n))
        mean_x = sum(indices) / n
        mean_y = sum(coherence_history) / n

        cov_xy = sum((indices[i] - mean_x) * (coherence_history[i] - mean_y) for i in range(n)) / n
        var_x = sum((x - mean_x) ** 2 for x in indices) / n

        if var_x > 0:
            slope = cov_xy / var_x
        else:
            slope = 0.0
    else:
        slope = 0.0

    # Normalize slope to [0, 1] (positive slope → higher forward alignment)
    # Slope range is typically [-0.1, +0.1] for normalized coherence
    slope_normalized = _clamp_01(0.5 + slope * 5.0)

    # Factor in semantic integrity (higher integrity → higher forward alignment)
    integrity_factor = semantic_integrity if semantic_integrity is not None else 0.5

    # Factor in temporal entropy (asymmetry → lower forward alignment)
    # entropy_diff = 0.5 means stable, deviations indicate asymmetry
    if temporal_entropy_diff is not None:
        entropy_asymmetry = abs(temporal_entropy_diff - 0.5) * 2.0  # [0, 1]
        entropy_penalty = 1.0 - entropy_asymmetry * 0.3  # Mild penalty
    else:
        entropy_penalty = 1.0

    # Combine factors
    forward_alignment = 0.5 * slope_normalized + 0.3 * integrity_factor + 0.2 * entropy_penalty

    return _clamp_01(forward_alignment)


def _compute_mirror_alignment(
    mirror_loop_stability: Optional[float],
    mirror_loop_tension: Optional[float],
    cycle_types: Sequence[str],
    coherence_history: Sequence[float],
) -> float:
    """
    Compute mirror-time alignment from mirror-time loop and cycle metrics.

    Mirror alignment measures how well the conversation fits a mirror-time
    explanation, where effects precede causes in the reflective timeline.

    Formula:
        1. Use mirror_loop_stability as base signal
        2. Weight by inverse of mirror_loop_tension (low tension → high alignment)
        3. Boost for converging/stabilizing cycle types
        4. Adjust for coherence variance (stable coherence → higher mirror alignment)

    Args:
        mirror_loop_stability: Mirror-time loop stability [0.0, 1.0] (optional)
        mirror_loop_tension: Mirror-time loop tension [0.0, 1.0] (optional)
        cycle_types: List of cycle type strings (e.g., ["converging", "oscillating"])
        coherence_history: Historical coherence values for variance analysis

    Returns:
        float: Mirror alignment score [0.0, 1.0]
    """
    # Base mirror alignment from loop stability
    if mirror_loop_stability is not None:
        base_alignment = mirror_loop_stability
    else:
        base_alignment = 0.5  # Neutral default

    # Tension penalty: high tension → lower mirror alignment
    if mirror_loop_tension is not None:
        tension_penalty = 1.0 - mirror_loop_tension
    else:
        tension_penalty = 0.5

    # Cycle type boost: converging/stabilizing cycles → higher mirror alignment
    cycle_boost = 0.0
    if cycle_types:
        converging_count = sum(1 for ct in cycle_types if ct in ["converging", "stalled"])
        cycle_boost = min(converging_count / len(cycle_types), 1.0) * 0.2

    # Coherence variance: low variance → stable mirror reflection
    if coherence_history and len(coherence_history) >= 2:
        coherence_stdev = _safe_stdev(coherence_history)
        variance_stability = 1.0 - min(coherence_stdev, 1.0)
    else:
        variance_stability = 0.5

    # Combine factors
    mirror_alignment = (
        0.4 * base_alignment
        + 0.3 * tension_penalty
        + 0.2 * variance_stability
        + 0.1 * cycle_boost
    )

    return _clamp_01(mirror_alignment)


def _compute_cause_chain_stability(
    drift_fusion_index: Optional[float],
    semantic_integrity: Optional[float],
    temporal_entropy_diff: Optional[float],
    coherence_history: Sequence[float],
) -> float:
    """
    Compute cause-chain stability from drift, integrity, entropy, and coherence.

    Cause-chain stability measures how stable the cause-effect chain is,
    regardless of forward vs mirror interpretation.

    Formula:
        1. Low drift → high stability
        2. High semantic integrity → high stability
        3. Low entropy volatility → high stability
        4. Stable coherence → high stability

    Args:
        drift_fusion_index: Drift fusion index [0.0, 1.0] (optional)
        semantic_integrity: Semantic integrity score [0.0, 1.0] (optional)
        temporal_entropy_diff: Normalized entropy diff [0.0, 1.0] (optional)
        coherence_history: Historical coherence values for stability analysis

    Returns:
        float: Cause-chain stability score [0.0, 1.0]
    """
    # Low drift → high stability
    if drift_fusion_index is not None:
        drift_stability = 1.0 - drift_fusion_index
    else:
        drift_stability = 0.5

    # High semantic integrity → high stability
    integrity_stability = semantic_integrity if semantic_integrity is not None else 0.5

    # Low entropy volatility → high stability
    # Entropy diff close to 0.5 (stable) → high stability
    if temporal_entropy_diff is not None:
        entropy_stability = 1.0 - abs(temporal_entropy_diff - 0.5) * 2.0
        entropy_stability = _clamp_01(entropy_stability)
    else:
        entropy_stability = 0.5

    # Coherence variance: low variance → high stability
    if coherence_history and len(coherence_history) >= 2:
        coherence_stdev = _safe_stdev(coherence_history)
        coherence_stability = 1.0 - min(coherence_stdev * 2.0, 1.0)
    else:
        coherence_stability = 0.5

    # Combine factors
    cause_chain_stability = (
        0.3 * drift_stability
        + 0.3 * integrity_stability
        + 0.2 * entropy_stability
        + 0.2 * coherence_stability
    )

    return _clamp_01(cause_chain_stability)


def _classify_inversion_band(inversion_score: float) -> str:
    """
    Classify inversion band from inversion score.

    Thresholds (exact):
        inversion_score < 0.25: "forward_dominant"
        inversion_score < 0.45: "ambiguous"
        inversion_score < 0.70: "inversion_plausible"
        inversion_score >= 0.70: "inversion_dominant"

    Args:
        inversion_score: Inversion score [0.0, 1.0]

    Returns:
        str: Inversion band classification
    """
    if inversion_score < 0.25:
        return "forward_dominant"
    elif inversion_score < 0.45:
        return "ambiguous"
    elif inversion_score < 0.70:
        return "inversion_plausible"
    else:
        return "inversion_dominant"


def _generate_diagnostic_notes(
    forward_alignment: float,
    mirror_alignment: float,
    inversion_score: float,
    cause_chain_stability: float,
    drift_fusion_index: Optional[float],
    semantic_integrity: Optional[float],
    temporal_entropy_diff: Optional[float],
) -> List[str]:
    """
    Generate deterministic diagnostic notes based on metric values.

    Args:
        forward_alignment: Forward alignment score
        mirror_alignment: Mirror alignment score
        inversion_score: Inversion score
        cause_chain_stability: Cause-chain stability score
        drift_fusion_index: Drift fusion index (optional)
        semantic_integrity: Semantic integrity score (optional)
        temporal_entropy_diff: Temporal entropy diff (optional)

    Returns:
        List[str]: Diagnostic tags
    """
    notes = []

    # Mirror vs forward comparison
    if mirror_alignment > forward_alignment + 0.15:
        notes.append("mirror_alignment_outweighs_forward")
    elif forward_alignment > mirror_alignment + 0.15:
        notes.append("forward_alignment_outweighs_mirror")
    else:
        notes.append("balanced_forward_mirror_alignment")

    # Drift and integrity
    if drift_fusion_index is not None and drift_fusion_index > 0.6:
        if semantic_integrity is not None and semantic_integrity < 0.4:
            notes.append("high_drift_low_integrity")
        elif semantic_integrity is not None and semantic_integrity > 0.6:
            notes.append("high_drift_high_integrity")
    elif drift_fusion_index is not None and drift_fusion_index < 0.3:
        notes.append("low_drift_stable")

    # Entropy asymmetry
    if temporal_entropy_diff is not None:
        entropy_deviation = abs(temporal_entropy_diff - 0.5)
        if entropy_deviation > 0.25:
            notes.append("entropy_asymmetry_detected")

    # Coherence stability
    if cause_chain_stability > 0.7:
        notes.append("cause_chain_highly_stable")
    elif cause_chain_stability < 0.3:
        notes.append("cause_chain_unstable")

    # Forward coherence pattern
    if forward_alignment > 0.7:
        notes.append("coherence_stable_forward")
    elif forward_alignment < 0.3:
        notes.append("coherence_unstable_forward")

    # Mirror stability pattern
    if mirror_alignment > 0.7:
        notes.append("mirror_reflection_stable")
    elif mirror_alignment < 0.3:
        notes.append("mirror_reflection_unstable")

    # Inversion strength
    if inversion_score > 0.7:
        notes.append("strong_inversion_signal")
    elif inversion_score < 0.25:
        notes.append("weak_inversion_signal")

    return notes


def compute_cause_effect_inversion(
    *,
    coherence_history: Sequence[float],
    mirror_loop_stability: Optional[float] = None,
    mirror_loop_tension: Optional[float] = None,
    cycle_types: Sequence[str] = (),
    drift_fusion_index: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
    semantic_integrity: Optional[float] = None,
) -> Optional[CauseEffectInversionSnapshot]:
    """
    Compute cause-effect inversion snapshot from temporal and coherence metrics.

    This is the main cause-effect inversion computation function for Phase 23.

    Behavior:
        1. Compute forward_alignment from coherence trend + semantic integrity
        2. Compute mirror_alignment from mirror-time loop + cycle metrics
        3. Compute inversion_score from alignment difference + drift + entropy
        4. Classify inversion_band from inversion_score
        5. Compute cause_chain_stability from drift + integrity + entropy + coherence
        6. Generate diagnostic notes

    Args:
        coherence_history: Historical coherence values [0.0, 1.0]
        mirror_loop_stability: Mirror-time loop stability [0.0, 1.0] (optional)
        mirror_loop_tension: Mirror-time loop tension [0.0, 1.0] (optional)
        cycle_types: List of cycle type strings (optional)
        drift_fusion_index: Drift fusion index [0.0, 1.0] (optional)
        temporal_entropy_diff: Normalized entropy diff [0.0, 1.0] (optional)
        semantic_integrity: Semantic integrity score [0.0, 1.0] (optional)

    Returns:
        CauseEffectInversionSnapshot: Complete snapshot with all metrics
        None: If insufficient data (coherence_history too short)

    Note:
        - All math is deterministic and zero-LLM
        - Missing inputs are handled gracefully with safe defaults
        - Requires at least 2 coherence values to compute
    """
    # Validate minimum input requirements
    if not coherence_history or len(coherence_history) < 2:
        return None

    # 1. Compute forward alignment
    forward_alignment = _compute_forward_alignment(
        coherence_history=coherence_history,
        semantic_integrity=semantic_integrity,
        temporal_entropy_diff=temporal_entropy_diff,
    )

    # 2. Compute mirror alignment
    mirror_alignment = _compute_mirror_alignment(
        mirror_loop_stability=mirror_loop_stability,
        mirror_loop_tension=mirror_loop_tension,
        cycle_types=cycle_types,
        coherence_history=coherence_history,
    )

    # 3. Compute inversion score
    # Formula: weighted blend of alignment difference, drift, and entropy asymmetry
    alignment_diff = max(mirror_alignment - forward_alignment, 0.0)
    drift_component = drift_fusion_index if drift_fusion_index is not None else 0.0

    if temporal_entropy_diff is not None:
        entropy_asymmetry = abs(temporal_entropy_diff - 0.5)
    else:
        entropy_asymmetry = 0.0

    inversion_score = _clamp_01(
        0.5 * alignment_diff
        + 0.3 * drift_component
        + 0.2 * entropy_asymmetry
    )

    # 4. Classify inversion band
    inversion_band = _classify_inversion_band(inversion_score)

    # 5. Compute cause-chain stability
    cause_chain_stability = _compute_cause_chain_stability(
        drift_fusion_index=drift_fusion_index,
        semantic_integrity=semantic_integrity,
        temporal_entropy_diff=temporal_entropy_diff,
        coherence_history=coherence_history,
    )

    # 6. Generate diagnostic notes
    notes = _generate_diagnostic_notes(
        forward_alignment=forward_alignment,
        mirror_alignment=mirror_alignment,
        inversion_score=inversion_score,
        cause_chain_stability=cause_chain_stability,
        drift_fusion_index=drift_fusion_index,
        semantic_integrity=semantic_integrity,
        temporal_entropy_diff=temporal_entropy_diff,
    )

    return CauseEffectInversionSnapshot(
        forward_alignment=forward_alignment,
        mirror_alignment=mirror_alignment,
        inversion_score=inversion_score,
        inversion_band=inversion_band,
        cause_chain_stability=cause_chain_stability,
        notes=notes,
    )
