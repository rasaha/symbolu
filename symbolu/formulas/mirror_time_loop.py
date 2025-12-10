"""
Mirror-Time Loop Engine (MTL) v1.0 - Phase 21

Deterministic, zero-LLM analytical layer that computes the relationship between
forward-time consciousness (Self) and mirror-time reflection (Mirror-Self).

Computes:
  • forward_vector: forward-time trajectory strength [0.0, 1.0]
  • mirror_vector: mirror-time reflection strength [0.0, 1.0]
  • loop_delta: Self vs Mirror divergence [-1.0, +1.0]
  • loop_tension: |forward - mirror| [0.0, 1.0]
  • loop_alignment: cosine similarity-like index [0.0, 1.0]
  • reversal_probability: likelihood of temporal reversal [0.0, 1.0]
  • stability_band: {stable, transitional, unstable}

CRITICAL:
    - Zero-LLM: Pure math & simple statistics only
    - Non-invasive: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Observation-only: Outputs used only for diagnostics & analytics (no behavior change)
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs
"""

from dataclasses import dataclass
from typing import List, Optional
import statistics


@dataclass
class MirrorTimeLoopSnapshot:
    """
    Immutable snapshot of mirror-time loop computation.

    Fields:
        forward_vector: Forward-time trajectory strength [0.0, 1.0]
        mirror_vector: Mirror-time reflection strength [0.0, 1.0]
        loop_delta: Self vs Mirror divergence [-1.0, +1.0]
        loop_tension: Absolute difference |forward - mirror| [0.0, 1.0]
        loop_alignment: Cosine similarity-like alignment index [0.0, 1.0]
        reversal_probability: Likelihood of temporal reversal [0.0, 1.0]
        stability_band: Stability classification ("stable" | "transitional" | "unstable")
    """

    forward_vector: float
    mirror_vector: float
    loop_delta: float
    loop_tension: float
    loop_alignment: float
    reversal_probability: float
    stability_band: str


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


def _safe_mean(values: List[float]) -> float:
    """
    Compute mean of values, handling empty lists gracefully.

    Args:
        values: List of numeric values

    Returns:
        float: Mean value, or 0.5 if list is empty (neutral default)
    """
    if not values:
        return 0.5
    return sum(values) / len(values)


def _safe_variance(values: List[float]) -> float:
    """
    Compute variance of values, handling edge cases gracefully.

    Args:
        values: List of numeric values

    Returns:
        float: Variance, or 0.0 if insufficient data
    """
    if not values or len(values) < 2:
        return 0.0

    try:
        return statistics.variance(values)
    except statistics.StatisticsError:
        return 0.0


def _compute_forward_vector(
    delta_smi_history: List[float],
    tension_corridor_history: List[float],
    window: int = 5,
) -> float:
    """
    Compute forward-time vector from temporal metrics.

    Forward vector represents the momentum of self-directed consciousness
    trajectory based on recent ΔSMI and tension corridor patterns.

    Formula:
        recent_delta_avg = mean(delta_smi[-window:])
        recent_tension_avg = mean(tension_corridor[-window:])
        forward = 0.6 * (0.5 + recent_delta_avg / 2) + 0.4 * recent_tension_avg
        return clamp(forward, 0.0, 1.0)

    Args:
        delta_smi_history: Historical ΔSMI values [-1.0, +1.0]
        tension_corridor_history: Historical tension corridor values [0.0, 1.0]
        window: Window size for recent averaging (default: 5)

    Returns:
        float: Forward vector strength [0.0, 1.0]
    """
    # Filter out None values
    valid_delta = [d for d in delta_smi_history[-window:] if d is not None]
    valid_tension = [t for t in tension_corridor_history[-window:] if t is not None]

    # Compute recent averages
    recent_delta_avg = _safe_mean(valid_delta)  # Will be 0.5 if empty
    recent_tension_avg = _safe_mean(valid_tension)  # Will be 0.5 if empty

    # Normalize delta from [-1, +1] to [0, 1]
    delta_normalized = 0.5 + recent_delta_avg / 2.0

    # Combine: higher delta momentum + higher tension → stronger forward vector
    forward = 0.6 * delta_normalized + 0.4 * recent_tension_avg

    return _clamp(forward, 0.0, 1.0)


def _compute_mirror_vector(
    coherence_fused_history: List[float],
    semantic_integrity_history: List[float],
    window: int = 5,
) -> float:
    """
    Compute mirror-time vector from coherence and integrity metrics.

    Mirror vector represents the reflective self-consistency and coherence
    based on recent fusion stability and semantic integrity.

    Formula:
        recent_coherence_avg = mean(coherence_fused[-window:])
        recent_integrity_avg = mean(semantic_integrity[-window:])
        mirror = 0.5 * recent_coherence_avg + 0.5 * recent_integrity_avg
        return clamp(mirror, 0.0, 1.0)

    Args:
        coherence_fused_history: Historical coherence_fused values [0.0, 1.0]
        semantic_integrity_history: Historical semantic integrity values [0.0, 1.0]
        window: Window size for recent averaging (default: 5)

    Returns:
        float: Mirror vector strength [0.0, 1.0]
    """
    # Filter out None values
    valid_coherence = [c for c in coherence_fused_history[-window:] if c is not None]
    valid_integrity = [i for i in semantic_integrity_history[-window:] if i is not None]

    # Compute recent averages
    recent_coherence_avg = _safe_mean(valid_coherence)  # Will be 0.5 if empty
    recent_integrity_avg = _safe_mean(valid_integrity)  # Will be 0.5 if empty

    # Combine: balanced blend of coherence and integrity
    mirror = 0.5 * recent_coherence_avg + 0.5 * recent_integrity_avg

    return _clamp(mirror, 0.0, 1.0)


def _compute_loop_delta(forward_vector: float, mirror_vector: float) -> float:
    """
    Compute loop delta (Self vs Mirror divergence).

    Loop delta represents the signed difference between forward-time self
    and mirror-time reflection.

    Formula:
        delta = forward_vector - mirror_vector
        return clamp(delta, -1.0, +1.0)

    Args:
        forward_vector: Forward-time strength [0.0, 1.0]
        mirror_vector: Mirror-time strength [0.0, 1.0]

    Returns:
        float: Loop delta [-1.0, +1.0]
            • Positive: Self is ahead of Mirror (outpacing reflection)
            • Zero: Self and Mirror are aligned
            • Negative: Mirror is ahead of Self (reflection outpacing action)
    """
    delta = forward_vector - mirror_vector
    return _clamp(delta, -1.0, 1.0)


def _compute_loop_tension(forward_vector: float, mirror_vector: float) -> float:
    """
    Compute loop tension (absolute divergence).

    Loop tension represents the magnitude of misalignment between forward
    and mirror vectors, regardless of direction.

    Formula:
        tension = |forward_vector - mirror_vector|
        return clamp(tension, 0.0, 1.0)

    Args:
        forward_vector: Forward-time strength [0.0, 1.0]
        mirror_vector: Mirror-time strength [0.0, 1.0]

    Returns:
        float: Loop tension [0.0, 1.0]
            • 0.0: Perfect alignment
            • 1.0: Maximum divergence
    """
    tension = abs(forward_vector - mirror_vector)
    return _clamp(tension, 0.0, 1.0)


def _compute_loop_alignment(
    forward_vector: float,
    mirror_vector: float,
    delta_smi_history: List[float],
    coherence_fused_history: List[float],
) -> float:
    """
    Compute loop alignment (cosine similarity-like index).

    Loop alignment represents how well forward and mirror vectors are
    directionally aligned, accounting for their historical consistency.

    Formula:
        dot_product = forward_vector * mirror_vector
        magnitude = sqrt(forward_vector^2 + mirror_vector^2)
        base_alignment = dot_product / magnitude if magnitude > 0 else 0.5

        # Consistency bonus from variance
        delta_var = variance(delta_smi_history)
        coherence_var = variance(coherence_fused_history)
        consistency = 1.0 - min((delta_var + coherence_var) / 2, 1.0)

        alignment = 0.7 * base_alignment + 0.3 * consistency
        return clamp(alignment, 0.0, 1.0)

    Args:
        forward_vector: Forward-time strength [0.0, 1.0]
        mirror_vector: Mirror-time strength [0.0, 1.0]
        delta_smi_history: Historical ΔSMI values for consistency check
        coherence_fused_history: Historical coherence_fused for consistency check

    Returns:
        float: Loop alignment [0.0, 1.0]
            • 1.0: Perfect alignment (cosine similarity ~ 1)
            • 0.5: Orthogonal (no correlation)
            • 0.0: Complete misalignment (opposite directions)
    """
    # Compute dot product and magnitude
    dot_product = forward_vector * mirror_vector
    magnitude = (forward_vector ** 2 + mirror_vector ** 2) ** 0.5

    # Base alignment (cosine similarity approximation)
    if magnitude > 0.0:
        base_alignment = dot_product / magnitude
    else:
        base_alignment = 0.5  # Neutral if both vectors are zero

    # Consistency bonus: lower variance → higher consistency
    valid_delta = [d for d in delta_smi_history if d is not None]
    valid_coherence = [c for c in coherence_fused_history if c is not None]

    delta_var = _safe_variance(valid_delta)
    coherence_var = _safe_variance(valid_coherence)

    # Normalize variance to [0, 1] and invert (high variance → low consistency)
    avg_var = (delta_var + coherence_var) / 2.0
    consistency = 1.0 - min(avg_var, 1.0)

    # Blend base alignment with consistency bonus
    alignment = 0.7 * base_alignment + 0.3 * consistency

    return _clamp(alignment, 0.0, 1.0)


def _compute_reversal_probability(
    loop_tension: float,
    loop_delta: float,
    resonance_indices: List[float],
) -> float:
    """
    Compute reversal probability (likelihood of temporal reversal).

    Reversal probability represents the likelihood that the system will
    experience a temporal reversal (mirror overtaking forward).

    Formula:
        # Base reversal risk from tension
        tension_risk = loop_tension

        # Directional risk: negative delta (mirror ahead) increases risk
        delta_risk = max(-loop_delta, 0.0)  # Only negative delta contributes

        # Stability dampener from resonance
        valid_resonance = [r for r in resonance_indices if r is not None]
        avg_resonance = mean(valid_resonance) or 0.5
        stability_dampener = 1.0 - avg_resonance

        # Combine factors
        reversal = 0.5 * tension_risk + 0.3 * delta_risk + 0.2 * stability_dampener
        return clamp(reversal, 0.0, 1.0)

    Args:
        loop_tension: Loop tension [0.0, 1.0]
        loop_delta: Loop delta [-1.0, +1.0]
        resonance_indices: Historical resonance indices for stability check

    Returns:
        float: Reversal probability [0.0, 1.0]
            • 0.0: No reversal risk (stable forward progression)
            • 1.0: Imminent reversal (mirror overtaking forward)
    """
    # Tension risk: higher tension → higher reversal risk
    tension_risk = loop_tension

    # Directional risk: negative delta (mirror ahead) → higher risk
    delta_risk = max(-loop_delta, 0.0)

    # Stability dampener: lower resonance → higher risk
    valid_resonance = [r for r in resonance_indices if r is not None]
    avg_resonance = _safe_mean(valid_resonance)
    stability_dampener = 1.0 - avg_resonance

    # Combine factors
    reversal = 0.5 * tension_risk + 0.3 * delta_risk + 0.2 * stability_dampener

    return _clamp(reversal, 0.0, 1.0)


def _classify_stability_band(
    loop_tension: float,
    reversal_probability: float,
    loop_alignment: float,
) -> str:
    """
    Classify stability band from loop metrics.

    Stability bands:
        • stable: Low tension, low reversal risk, high alignment
        • transitional: Moderate metrics (in between)
        • unstable: High tension, high reversal risk, low alignment

    Thresholds:
        stable: tension < 0.3 AND reversal < 0.3 AND alignment > 0.6
        unstable: tension > 0.6 OR reversal > 0.6 OR alignment < 0.4
        transitional: all other cases

    Args:
        loop_tension: Loop tension [0.0, 1.0]
        reversal_probability: Reversal probability [0.0, 1.0]
        loop_alignment: Loop alignment [0.0, 1.0]

    Returns:
        str: Stability band ("stable" | "transitional" | "unstable")
    """
    # Stable: low tension, low reversal, high alignment
    if loop_tension < 0.3 and reversal_probability < 0.3 and loop_alignment > 0.6:
        return "stable"

    # Unstable: high tension, high reversal, or low alignment
    if loop_tension > 0.6 or reversal_probability > 0.6 or loop_alignment < 0.4:
        return "unstable"

    # Transitional: all other cases
    return "transitional"


def compute_mirror_time_loop(
    delta_smi_history: List[Optional[float]],
    tension_corridor_history: List[Optional[float]],
    coherence_fused_history: List[Optional[float]],
    semantic_integrity_history: List[Optional[float]],
    resonance_index_history: List[Optional[float]],
    window: int = 5,
) -> Optional[MirrorTimeLoopSnapshot]:
    """
    Compute mirror-time loop snapshot from temporal and coherence histories.

    This is the main mirror-time loop computation function.

    Behavior:
        1. Compute forward_vector from delta_smi + tension_corridor
        2. Compute mirror_vector from coherence_fused + semantic_integrity
        3. Compute loop_delta = forward - mirror
        4. Compute loop_tension = |forward - mirror|
        5. Compute loop_alignment (cosine similarity-like)
        6. Compute reversal_probability from tension, delta, resonance
        7. Classify stability_band from metrics

    Args:
        delta_smi_history: List of ΔSMI values [-1.0, +1.0]
        tension_corridor_history: List of tension corridor values [0.0, 1.0]
        coherence_fused_history: List of coherence_fused values [0.0, 1.0]
        semantic_integrity_history: List of semantic integrity values [0.0, 1.0]
        resonance_index_history: List of resonance indices [0.0, 1.0]
        window: Window size for recent averaging (default: 5)

    Returns:
        MirrorTimeLoopSnapshot: Complete snapshot with all metrics
        None: If insufficient data (all histories are empty)

    Note:
        - All math is deterministic and zero-LLM
        - Missing inputs are handled gracefully with safe defaults
        - If history is shorter than window, uses full available history
    """
    # Validate inputs: need at least some data to compute
    all_empty = (
        not any(d is not None for d in delta_smi_history)
        and not any(t is not None for t in tension_corridor_history)
        and not any(c is not None for c in coherence_fused_history)
        and not any(s is not None for s in semantic_integrity_history)
    )

    if all_empty:
        return None

    # 1. Compute forward vector
    forward_vector = _compute_forward_vector(
        delta_smi_history,
        tension_corridor_history,
        window=window,
    )

    # 2. Compute mirror vector
    mirror_vector = _compute_mirror_vector(
        coherence_fused_history,
        semantic_integrity_history,
        window=window,
    )

    # 3. Compute loop delta
    loop_delta = _compute_loop_delta(forward_vector, mirror_vector)

    # 4. Compute loop tension
    loop_tension = _compute_loop_tension(forward_vector, mirror_vector)

    # 5. Compute loop alignment
    loop_alignment = _compute_loop_alignment(
        forward_vector,
        mirror_vector,
        delta_smi_history,
        coherence_fused_history,
    )

    # 6. Compute reversal probability
    reversal_probability = _compute_reversal_probability(
        loop_tension,
        loop_delta,
        resonance_index_history,
    )

    # 7. Classify stability band
    stability_band = _classify_stability_band(
        loop_tension,
        reversal_probability,
        loop_alignment,
    )

    return MirrorTimeLoopSnapshot(
        forward_vector=forward_vector,
        mirror_vector=mirror_vector,
        loop_delta=loop_delta,
        loop_tension=loop_tension,
        loop_alignment=loop_alignment,
        reversal_probability=reversal_probability,
        stability_band=stability_band,
    )
