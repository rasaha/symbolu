"""
Mirror-Time Cycle Engine (MTCE) v1.0 - Phase 22

Deterministic, zero-LLM analytical layer that builds on Phase 21 Mirror-Time Loop
metrics to detect and classify mirror-time cycles at the conversation level.

Computes:
  • Cycle detection: Segments loop history into discrete cycles
  • Cycle classification: converging | diverging | oscillating | stalled
  • Cycle gradients: forward_gradient, mirror_gradient
  • Stability bands: stable | transitional | unstable
  • Reversal bias: toward_alignment | toward_divergence | neutral

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
class MirrorTimeCycleSnapshot:
    """
    Immutable snapshot of a single mirror-time cycle.

    A cycle represents a coherent segment of mirror-time loop evolution,
    characterized by directional trends and stability patterns.

    Fields:
        cycle_id: Unique identifier for this cycle
        start_turn: Turn index where cycle begins (inclusive)
        end_turn: Turn index where cycle ends (inclusive)
        length: Number of turns in this cycle
        avg_loop_alignment: Average loop_alignment over cycle [0.0, 1.0]
        avg_loop_tension: Average loop_tension over cycle [0.0, 1.0]
        avg_reversal_probability: Average reversal_probability over cycle [0.0, 1.0]
        forward_gradient: Slope of loop_delta over cycle (trend direction)
        mirror_gradient: Alternative gradient (reuses forward_gradient for simplicity)
        cycle_type: Classification ("converging" | "diverging" | "oscillating" | "stalled")
        stability_band: Stability classification ("stable" | "transitional" | "unstable")
        reversal_bias: Reversal direction ("toward_alignment" | "toward_divergence" | "neutral")
    """

    cycle_id: str
    start_turn: int
    end_turn: int
    length: int
    avg_loop_alignment: float
    avg_loop_tension: float
    avg_reversal_probability: float
    forward_gradient: float
    mirror_gradient: float
    cycle_type: str
    stability_band: str
    reversal_bias: str


@dataclass
class MirrorTimeCycleSummary:
    """
    Summary of all detected mirror-time cycles in a conversation.

    Fields:
        cycles: List of individual cycle snapshots
        dominant_cycle_type: Most common cycle_type across all cycles
        dominant_stability_band: Most common stability_band across all cycles
        avg_cycle_length: Average length of cycles (in turns)
        avg_forward_gradient: Average forward_gradient across cycles
        avg_reversal_probability: Average reversal_probability across cycles
    """

    cycles: List[MirrorTimeCycleSnapshot]
    dominant_cycle_type: Optional[str] = None
    dominant_stability_band: Optional[str] = None
    avg_cycle_length: Optional[float] = None
    avg_forward_gradient: Optional[float] = None
    avg_reversal_probability: Optional[float] = None


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


def _safe_stdev(values: List[float]) -> float:
    """
    Compute standard deviation of values, handling edge cases gracefully.

    Args:
        values: List of numeric values

    Returns:
        float: Standard deviation, or 0.0 if insufficient data
    """
    if not values or len(values) < 2:
        return 0.0

    try:
        return statistics.stdev(values)
    except statistics.StatisticsError:
        return 0.0


def _compute_linear_gradient(values: List[float]) -> float:
    """
    Compute linear regression gradient (slope) over a sequence of values.

    Uses simple linear regression: slope = Cov(x,y) / Var(x)
    where x is the index and y is the value.

    Args:
        values: List of numeric values

    Returns:
        float: Slope (gradient) of the trend line
    """
    n = len(values)
    if n < 2:
        return 0.0

    indices = list(range(n))
    mean_x = sum(indices) / n
    mean_y = sum(values) / n

    # Compute covariance and variance
    cov_xy = sum((indices[i] - mean_x) * (values[i] - mean_y) for i in range(n)) / n
    var_x = sum((x - mean_x) ** 2 for x in indices) / n

    if var_x == 0:
        return 0.0

    slope = cov_xy / var_x
    return slope


def _detect_cycle_boundaries(loop_history: List) -> List[int]:
    """
    Detect cycle boundaries in loop history based on local extrema and thresholds.

    Strategy:
        1. Detect local extrema (peaks/valleys) in loop_alignment
        2. Detect threshold crossings in reversal_probability
        3. Combine to identify natural cycle boundaries

    Args:
        loop_history: List of MirrorTimeLoopSnapshot objects

    Returns:
        List[int]: List of turn indices where cycles begin (includes 0 and len)
    """
    if len(loop_history) < 2:
        return [0, len(loop_history)]

    boundaries = [0]  # Always start with turn 0

    # Extract alignment and reversal probability series
    alignments = [snapshot.loop_alignment for snapshot in loop_history]
    reversals = [snapshot.reversal_probability for snapshot in loop_history]

    # Detect local extrema in alignment (peaks and valleys)
    for i in range(1, len(alignments) - 1):
        prev_align = alignments[i - 1]
        curr_align = alignments[i]
        next_align = alignments[i + 1]

        # Local maximum (peak)
        is_peak = curr_align > prev_align and curr_align > next_align
        # Local minimum (valley)
        is_valley = curr_align < prev_align and curr_align < next_align

        if is_peak or is_valley:
            boundaries.append(i)

    # Detect threshold crossings in reversal_probability
    REVERSAL_THRESHOLD = 0.5
    for i in range(1, len(reversals)):
        prev_rev = reversals[i - 1]
        curr_rev = reversals[i]

        # Crossing threshold upward or downward
        crossing_up = prev_rev < REVERSAL_THRESHOLD <= curr_rev
        crossing_down = prev_rev >= REVERSAL_THRESHOLD > curr_rev

        if (crossing_up or crossing_down) and i not in boundaries:
            boundaries.append(i)

    # Add final boundary
    if len(loop_history) not in boundaries:
        boundaries.append(len(loop_history))

    # Sort and deduplicate
    boundaries = sorted(set(boundaries))

    # Ensure minimum cycle length of 2 turns (merge small cycles)
    MIN_CYCLE_LENGTH = 2
    filtered_boundaries = [boundaries[0]]
    for i in range(1, len(boundaries)):
        if boundaries[i] - filtered_boundaries[-1] >= MIN_CYCLE_LENGTH:
            filtered_boundaries.append(boundaries[i])
        elif i == len(boundaries) - 1:
            # Keep final boundary even if cycle is small
            filtered_boundaries[-1] = boundaries[i]

    return filtered_boundaries


def _classify_cycle_type(
    alignment_trend: float,
    tension_trend: float,
    alignment_values: List[float],
) -> str:
    """
    Classify cycle type based on alignment and tension trends.

    Classification logic:
        • converging: alignment increasing AND tension decreasing
        • diverging: alignment decreasing AND tension increasing
        • oscillating: multiple sign changes in alignment gradient
        • stalled: low change in alignment and tension

    Args:
        alignment_trend: Linear gradient of loop_alignment over cycle
        tension_trend: Linear gradient of loop_tension over cycle
        alignment_values: Raw alignment values for oscillation detection

    Returns:
        str: Cycle type ("converging" | "diverging" | "oscillating" | "stalled")
    """
    TREND_THRESHOLD = 0.01  # Minimum gradient to consider significant

    # Detect oscillation: count sign changes in alignment differences
    sign_changes = 0
    if len(alignment_values) >= 3:
        for i in range(1, len(alignment_values) - 1):
            diff_prev = alignment_values[i] - alignment_values[i - 1]
            diff_next = alignment_values[i + 1] - alignment_values[i]
            if diff_prev * diff_next < 0:  # Sign change
                sign_changes += 1

    # Oscillating: multiple sign changes
    if sign_changes >= 2:
        return "oscillating"

    # Converging: alignment increasing, tension decreasing
    if alignment_trend > TREND_THRESHOLD and tension_trend < -TREND_THRESHOLD:
        return "converging"

    # Diverging: alignment decreasing, tension increasing
    if alignment_trend < -TREND_THRESHOLD and tension_trend > TREND_THRESHOLD:
        return "diverging"

    # Stalled: low change in both
    if abs(alignment_trend) <= TREND_THRESHOLD and abs(tension_trend) <= TREND_THRESHOLD:
        return "stalled"

    # Default: classify based on dominant trend
    if abs(alignment_trend) > abs(tension_trend):
        return "converging" if alignment_trend > 0 else "diverging"
    else:
        return "diverging" if tension_trend > 0 else "converging"


def _classify_stability_band(avg_stability_bands: List[str], variance: float) -> str:
    """
    Classify overall stability band for a cycle.

    Strategy:
        1. Count frequency of stability bands within cycle
        2. Use variance as tie-breaker
        3. Return most common band

    Args:
        avg_stability_bands: List of stability_band strings from loop snapshots
        variance: Variance of alignment/tension within cycle

    Returns:
        str: Stability band ("stable" | "transitional" | "unstable")
    """
    if not avg_stability_bands:
        return "transitional"

    # Count frequency
    stable_count = avg_stability_bands.count("stable")
    transitional_count = avg_stability_bands.count("transitional")
    unstable_count = avg_stability_bands.count("unstable")

    # Determine dominant band
    max_count = max(stable_count, transitional_count, unstable_count)

    if unstable_count == max_count:
        return "unstable"
    elif stable_count == max_count:
        # Use variance as tie-breaker: high variance → downgrade to transitional
        if variance > 0.1:
            return "transitional"
        return "stable"
    else:
        return "transitional"


def _classify_reversal_bias(
    avg_reversal_prob: float,
    forward_gradient: float,
) -> str:
    """
    Classify reversal bias based on reversal probability and gradient.

    Classification logic:
        • toward_alignment: low reversal probability AND positive gradient
        • toward_divergence: high reversal probability AND negative gradient
        • neutral: all other cases

    Args:
        avg_reversal_prob: Average reversal probability over cycle [0.0, 1.0]
        forward_gradient: Forward gradient (slope of loop_delta)

    Returns:
        str: Reversal bias ("toward_alignment" | "toward_divergence" | "neutral")
    """
    REVERSAL_THRESHOLD = 0.5
    GRADIENT_THRESHOLD = 0.01

    # Toward alignment: low reversal + positive gradient
    if avg_reversal_prob < REVERSAL_THRESHOLD and forward_gradient > GRADIENT_THRESHOLD:
        return "toward_alignment"

    # Toward divergence: high reversal + negative gradient
    if avg_reversal_prob >= REVERSAL_THRESHOLD and forward_gradient < -GRADIENT_THRESHOLD:
        return "toward_divergence"

    # Neutral: all other cases
    return "neutral"


def detect_mirror_time_cycles(
    loop_history: List,
) -> MirrorTimeCycleSummary:
    """
    Detect and classify mirror-time cycles from loop history.

    This is the main cycle detection function for Phase 22.

    Behavior:
        1. Segment loop_history into cycles based on extrema and thresholds
        2. For each cycle:
            a. Compute averages (alignment, tension, reversal_probability)
            b. Compute forward_gradient (slope of loop_delta)
            c. Classify cycle_type (converging/diverging/oscillating/stalled)
            d. Classify stability_band (stable/transitional/unstable)
            e. Classify reversal_bias (toward_alignment/toward_divergence/neutral)
        3. Compute summary statistics across all cycles

    Args:
        loop_history: List of MirrorTimeLoopSnapshot objects (Phase 21 output)

    Returns:
        MirrorTimeCycleSummary: Complete cycle analysis with individual cycles
            and aggregate statistics

    Note:
        - All math is deterministic and zero-LLM
        - Gracefully handles empty or short histories (no cycles)
        - Missing inputs are handled with safe defaults
    """
    # Handle empty or insufficient history
    if not loop_history or len(loop_history) < 2:
        return MirrorTimeCycleSummary(cycles=[])

    # Detect cycle boundaries
    boundaries = _detect_cycle_boundaries(loop_history)

    # Build cycles
    cycles: List[MirrorTimeCycleSnapshot] = []

    for i in range(len(boundaries) - 1):
        start_idx = boundaries[i]
        end_idx = boundaries[i + 1] - 1  # Inclusive end

        # Handle edge case: empty cycle
        if end_idx < start_idx:
            continue

        # Extract cycle segment
        cycle_segment = loop_history[start_idx : end_idx + 1]
        cycle_length = len(cycle_segment)

        # Skip if cycle is too short
        if cycle_length < 1:
            continue

        # Extract metrics from cycle segment
        alignments = [s.loop_alignment for s in cycle_segment]
        tensions = [s.loop_tension for s in cycle_segment]
        reversals = [s.reversal_probability for s in cycle_segment]
        deltas = [s.loop_delta for s in cycle_segment]
        stability_bands = [s.stability_band for s in cycle_segment]

        # Compute averages
        avg_alignment = _safe_mean(alignments)
        avg_tension = _safe_mean(tensions)
        avg_reversal = _safe_mean(reversals)

        # Compute gradients
        forward_gradient = _compute_linear_gradient(deltas)
        mirror_gradient = forward_gradient  # Reuse for simplicity (as per spec)

        # Compute variance for stability classification
        alignment_variance = _safe_stdev(alignments) ** 2 if len(alignments) > 1 else 0.0

        # Classify cycle type
        alignment_trend = _compute_linear_gradient(alignments)
        tension_trend = _compute_linear_gradient(tensions)
        cycle_type = _classify_cycle_type(alignment_trend, tension_trend, alignments)

        # Classify stability band
        stability_band = _classify_stability_band(stability_bands, alignment_variance)

        # Classify reversal bias
        reversal_bias = _classify_reversal_bias(avg_reversal, forward_gradient)

        # Create cycle snapshot
        cycle = MirrorTimeCycleSnapshot(
            cycle_id=f"cycle_{start_idx}_{end_idx}",
            start_turn=start_idx,
            end_turn=end_idx,
            length=cycle_length,
            avg_loop_alignment=avg_alignment,
            avg_loop_tension=avg_tension,
            avg_reversal_probability=avg_reversal,
            forward_gradient=forward_gradient,
            mirror_gradient=mirror_gradient,
            cycle_type=cycle_type,
            stability_band=stability_band,
            reversal_bias=reversal_bias,
        )

        cycles.append(cycle)

    # Compute summary statistics
    if cycles:
        # Dominant cycle type (most frequent)
        cycle_types = [c.cycle_type for c in cycles]
        dominant_cycle_type = max(set(cycle_types), key=cycle_types.count)

        # Dominant stability band (most frequent)
        stability_bands_list = [c.stability_band for c in cycles]
        dominant_stability_band = max(
            set(stability_bands_list), key=stability_bands_list.count
        )

        # Averages
        avg_cycle_length = _safe_mean([c.length for c in cycles])
        avg_forward_gradient = _safe_mean([c.forward_gradient for c in cycles])
        avg_reversal_probability = _safe_mean(
            [c.avg_reversal_probability for c in cycles]
        )
    else:
        dominant_cycle_type = None
        dominant_stability_band = None
        avg_cycle_length = None
        avg_forward_gradient = None
        avg_reversal_probability = None

    return MirrorTimeCycleSummary(
        cycles=cycles,
        dominant_cycle_type=dominant_cycle_type,
        dominant_stability_band=dominant_stability_band,
        avg_cycle_length=avg_cycle_length,
        avg_forward_gradient=avg_forward_gradient,
        avg_reversal_probability=avg_reversal_probability,
    )
