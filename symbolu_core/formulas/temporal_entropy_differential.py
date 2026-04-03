"""
Temporal Entropy Differential v1.0 - Phase 18

Deterministic, zero-LLM metrics that quantify how "noisy vs stable" the
emotional/cognitive field is over time, using existing entropy signals.

Computes:
  • instantaneous_entropy: current normalized entropy ∈ [0, 1]
  • short_window_entropy: avg entropy over short window
  • long_window_entropy: avg entropy over long window
  • entropy_diff: short - long (raw)
  • normalized_entropy_diff: mapped to [0, 1] (0.5 = no change)
  • entropy_volatility: spread/variance metric ∈ [0, 1]

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
class TemporalEntropySnapshot:
    """
    Immutable snapshot of temporal entropy differential computation.

    Fields:
        instantaneous_entropy: Current normalized entropy [0.0, 1.0]
        short_window_entropy: Average entropy over short window [0.0, 1.0]
        long_window_entropy: Average entropy over long window [0.0, 1.0]
        entropy_diff: Raw difference (short - long) [-1.0, +1.0]
        normalized_entropy_diff: Normalized difference [0.0, 1.0] (0.5 = no change)
        entropy_volatility: Volatility/variance measure [0.0, 1.0]
    """

    instantaneous_entropy: float
    short_window_entropy: float
    long_window_entropy: float
    entropy_diff: float
    normalized_entropy_diff: float
    entropy_volatility: float


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
        float: Mean value, or 0.5 if list is empty
    """
    if not values:
        return 0.5
    return sum(values) / len(values)


def _compute_variance_normalized(values: List[float], max_expected_variance: float = 0.25) -> float:
    """
    Compute normalized variance (volatility) from a list of values.

    Args:
        values: List of numeric values [0.0, 1.0]
        max_expected_variance: Maximum expected variance for normalization

    Returns:
        float: Normalized variance [0.0, 1.0]
    """
    if not values or len(values) < 2:
        return 0.0  # No volatility with < 2 samples

    try:
        variance = statistics.variance(values)
    except statistics.StatisticsError:
        return 0.0

    # Normalize to [0, 1] range
    normalized_variance = variance / max_expected_variance
    return _clamp(normalized_variance, 0.0, 1.0)


def effective_entropy_series(
    normalized_entropy_history: List[float],
    coherence_fused_history: Optional[List[float]] = None,
    blend_weight: float = 0.15,
) -> List[float]:
    """
    Optionally blend coherence_fused into entropy to get a 'smoothed' entropy signal.

    If coherence_fused_history is None or too short, fall back to pure normalized entropy.

    Formula:
        effective_entropy[i] = (1 - blend_weight) * normalized_entropy[i]
                             + blend_weight * (1 - coherence_fused[i])

    The (1 - coherence_fused) converts coherence (higher = better) to entropy-like
    signal (higher = more chaotic).

    Args:
        normalized_entropy_history: List of normalized entropy values [0.0, 1.0]
        coherence_fused_history: Optional list of fused coherence values [0.0, 1.0]
        blend_weight: Weight for blending coherence signal (0.0 = pure entropy, 1.0 = pure coherence)

    Returns:
        List[float]: Effective entropy series (same length as normalized_entropy_history)
    """
    if not normalized_entropy_history:
        return []

    # If no coherence history or mismatched lengths, return pure entropy
    if (
        coherence_fused_history is None
        or len(coherence_fused_history) != len(normalized_entropy_history)
    ):
        return normalized_entropy_history.copy()

    # Blend entropy and coherence
    effective_entropy = []
    for i in range(len(normalized_entropy_history)):
        entropy = normalized_entropy_history[i]
        coherence = coherence_fused_history[i]

        # Handle None values in coherence history
        if coherence is None:
            effective_entropy.append(entropy)
        else:
            # Blend: entropy + inverted coherence
            blended = (1.0 - blend_weight) * entropy + blend_weight * (1.0 - coherence)
            effective_entropy.append(_clamp(blended, 0.0, 1.0))

    return effective_entropy


def compute_temporal_entropy_snapshot(
    normalized_entropy_history: List[float],
    coherence_fused_history: Optional[List[float]] = None,
    short_window: int = 3,
    long_window: int = 10,
) -> Optional[TemporalEntropySnapshot]:
    """
    Compute temporal entropy differential snapshot from entropy history.

    This is the main temporal entropy computation function.

    Behavior:
        1. Extract instantaneous entropy (latest value)
        2. Compute short_window_entropy (mean of last short_window samples)
        3. Compute long_window_entropy (mean of last long_window samples)
        4. Compute entropy_diff = short_window_entropy - long_window_entropy
        5. Normalize entropy_diff to [0, 1] range (0.5 = no change)
        6. Compute entropy_volatility (normalized variance over long_window)

    Args:
        normalized_entropy_history: List of normalized entropy values [0.0, 1.0]
        coherence_fused_history: Optional list of fused coherence values for blending
        short_window: Window size for short-term average (default: 3)
        long_window: Window size for long-term average (default: 10)

    Returns:
        TemporalEntropySnapshot: Complete snapshot with all metrics
        None: If normalized_entropy_history is empty

    Note:
        - All math is deterministic and zero-LLM
        - Missing inputs are handled gracefully with safe defaults
        - If history is shorter than windows, uses full available history
    """
    # Validate input
    if not normalized_entropy_history:
        return None

    # Optional: blend with coherence_fused for smoothed signal
    effective_entropy = effective_entropy_series(
        normalized_entropy_history,
        coherence_fused_history,
        blend_weight=0.15,
    )

    # 1. Instantaneous entropy (latest value)
    instantaneous_entropy = effective_entropy[-1]

    # 2. Short window entropy (last short_window samples)
    short_samples = effective_entropy[-short_window:]
    short_window_entropy = _safe_mean(short_samples)
    short_window_entropy = _clamp(short_window_entropy, 0.0, 1.0)

    # 3. Long window entropy (last long_window samples)
    long_samples = effective_entropy[-long_window:]
    long_window_entropy = _safe_mean(long_samples)
    long_window_entropy = _clamp(long_window_entropy, 0.0, 1.0)

    # 4. Entropy diff (raw)
    entropy_diff = short_window_entropy - long_window_entropy
    entropy_diff = _clamp(entropy_diff, -1.0, 1.0)

    # 5. Normalized entropy diff (map [-1, +1] → [0, 1])
    # 0.0 = short << long (decreasing entropy)
    # 0.5 = short == long (stable entropy)
    # 1.0 = short >> long (increasing entropy)
    normalized_entropy_diff = 0.5 * (1.0 + entropy_diff)
    normalized_entropy_diff = _clamp(normalized_entropy_diff, 0.0, 1.0)

    # 6. Entropy volatility (normalized variance over long window)
    entropy_volatility = _compute_variance_normalized(
        long_samples,
        max_expected_variance=0.25,
    )

    return TemporalEntropySnapshot(
        instantaneous_entropy=instantaneous_entropy,
        short_window_entropy=short_window_entropy,
        long_window_entropy=long_window_entropy,
        entropy_diff=entropy_diff,
        normalized_entropy_diff=normalized_entropy_diff,
        entropy_volatility=entropy_volatility,
    )
