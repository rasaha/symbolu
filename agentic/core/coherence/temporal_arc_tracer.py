"""
Temporal Arc Tracer - Track temporal coherence across conversation.

Integrates with TemporalBhavaTracker to compute temporal arc quality scores
based on recovery patterns, resilience, and tension dynamics.
"""

from typing import List, Dict


def compute_temporal_arc_score(
    temporal_flags_history: List[Dict[str, bool]],
    tension_history: List[float],
) -> float:
    """
    Compute temporal arc coherence score.

    Temporal coherence is high when:
    - Recovery trajectory or resilience patterns frequently present
    - Tension corridor not dominating
    - Tension history shows smooth trends (not wild oscillations)

    Args:
        temporal_flags_history: List of temporal flag dicts per turn
        tension_history: List of long_arc_tension values per turn

    Returns:
        Temporal arc score 0.0-1.0 (higher = better)
    """
    if not temporal_flags_history:
        return 0.5  # Neutral score for no history

    # Component 1: Positive pattern score (recovery, resilience, breakthrough)
    positive_score = _compute_positive_pattern_score(temporal_flags_history)

    # Component 2: Negative pattern score (tension corridor, chronic stress)
    negative_score = _compute_negative_pattern_score(temporal_flags_history)

    # Component 3: Tension smoothness score
    tension_smoothness = _compute_tension_smoothness(tension_history)

    # Combine scores: positive factors + smoothness - negative factors
    arc_score = (
        0.4 * positive_score
        + 0.3 * tension_smoothness
        + 0.3 * (1.0 - negative_score)
    )

    return max(0.0, min(1.0, arc_score))


def _compute_positive_pattern_score(temporal_flags_history: List[Dict[str, bool]]) -> float:
    """
    Compute score from positive temporal patterns.

    Args:
        temporal_flags_history: List of temporal flag dicts

    Returns:
        Positive pattern score 0.0-1.0
    """
    if not temporal_flags_history:
        return 0.0

    total_score = 0.0
    num_turns = len(temporal_flags_history)

    for flags in temporal_flags_history:
        turn_score = 0.0

        if flags.get("recovery_trajectory", False):
            turn_score += 0.4

        if flags.get("resilience_pattern", False):
            turn_score += 0.4

        if flags.get("breakthrough_insight", False):
            turn_score += 0.2

        total_score += min(1.0, turn_score)

    return total_score / num_turns


def _compute_negative_pattern_score(temporal_flags_history: List[Dict[str, bool]]) -> float:
    """
    Compute score from negative temporal patterns.

    Args:
        temporal_flags_history: List of temporal flag dicts

    Returns:
        Negative pattern score 0.0-1.0 (higher = more negative patterns)
    """
    if not temporal_flags_history:
        return 0.0

    total_score = 0.0
    num_turns = len(temporal_flags_history)

    for flags in temporal_flags_history:
        turn_score = 0.0

        if flags.get("tension_corridor", False):
            turn_score += 0.5

        if flags.get("chronic_stress", False):
            turn_score += 0.5

        total_score += min(1.0, turn_score)

    return total_score / num_turns


def _compute_tension_smoothness(tension_history: List[float]) -> float:
    """
    Compute tension smoothness from tension history.

    Smoothness is high when tension values don't oscillate wildly.

    Args:
        tension_history: List of tension values

    Returns:
        Smoothness score 0.0-1.0 (higher = smoother)
    """
    if not tension_history or len(tension_history) < 2:
        return 1.0  # No oscillations possible

    # Compute total absolute changes
    total_change = 0.0
    for i in range(1, len(tension_history)):
        total_change += abs(tension_history[i] - tension_history[i - 1])

    # Normalize by number of transitions
    avg_change = total_change / (len(tension_history) - 1)

    # Map average change to smoothness score
    # Heuristic: avg_change > 0.3 is considered high volatility
    # Use sigmoid-like transformation
    smoothness = 1.0 / (1.0 + avg_change / 0.3)

    return max(0.0, min(1.0, smoothness))


def compute_tension_trend(tension_history: List[float]) -> str:
    """
    Compute overall tension trend (increasing, decreasing, stable).

    Args:
        tension_history: List of tension values

    Returns:
        Trend string: "increasing", "decreasing", or "stable"
    """
    if not tension_history or len(tension_history) < 3:
        return "stable"

    # Use linear regression slope to determine trend
    n = len(tension_history)
    x_mean = (n - 1) / 2.0
    y_mean = sum(tension_history) / n

    numerator = sum((i - x_mean) * (tension_history[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return "stable"

    slope = numerator / denominator

    # Thresholds for trend classification
    if slope > 0.05:
        return "increasing"
    elif slope < -0.05:
        return "decreasing"
    else:
        return "stable"
