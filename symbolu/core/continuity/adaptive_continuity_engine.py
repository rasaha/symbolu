"""
P37 - Adaptive Continuity Engine Formula

Deterministic formula computation for adaptive continuity assessment.
This module contains the locked formula implementation.

FORMULA (LOCKED):

continuity_score =
    0.40 * persistence_score
  + 0.30 * (1 - volatility_index)
  + 0.30 * (1 - predicted_drift_score)

Clamped to [0.0, 1.0].

continuity_pressure = 1 - continuity_score

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs
    - No LLM, no ML, no learning
    - No probabilistic sampling
    - Pure arithmetic operations only

INVARIANTS:
    - INV-P37-1: Deterministic (same input -> same output)
    - INV-P37-4: continuity_score is monotonic w.r.t inputs
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from symbolu.core.continuity.continuity_models import (
    # Weights
    W_PERSISTENCE,
    W_INVERSE_VOLATILITY,
    W_INVERSE_DRIFT,
    # Thresholds
    MODE_STABLE_THRESHOLD,
    MODE_STRAINED_THRESHOLD,
    OSCILLATION_VOLATILITY_THRESHOLD,
    OSCILLATION_MIN_REVERSALS,
    OSCILLATION_WINDOW_SIZE,
    HIGH_DRIFT_THRESHOLD,
    LOW_PERSISTENCE_THRESHOLD,
    HIGH_VOLATILITY_THRESHOLD,
    # Types
    AdaptiveContinuityReport,
    create_report,
    mode_from_score,
    create_empty_report,
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp a value to a specified range.

    Args:
        value: The value to clamp
        min_val: Minimum value (default 0.0)
        max_val: Maximum value (default 1.0)

    Returns:
        Value clamped to [min_val, max_val]
    """
    return max(min_val, min(max_val, value))


def safe_get(value: Optional[float], default: float = 0.5) -> float:
    """
    Safely get a value with a default fallback.

    Args:
        value: The value to get (may be None)
        default: Default value if None (default 0.5)

    Returns:
        The value if not None, otherwise the default
    """
    if value is None:
        return default
    return clamp(value)


# =============================================================================
# CORE FORMULAS
# =============================================================================


def compute_continuity_score(
    persistence_score: float,
    volatility_index: float,
    predicted_drift_score: float,
) -> float:
    """
    Compute the continuity score using the locked formula.

    FORMULA (LOCKED):
        continuity_score =
            0.40 * persistence_score
          + 0.30 * (1 - volatility_index)
          + 0.30 * (1 - predicted_drift_score)

    All inputs are clamped to [0.0, 1.0] before computation.
    Output is clamped to [0.0, 1.0].

    Args:
        persistence_score: P36 persistence score [0.0, 1.0]
        volatility_index: P36 volatility index [0.0, 1.0]
        predicted_drift_score: P35 predicted drift score [0.0, 1.0]

    Returns:
        Continuity score in [0.0, 1.0]
    """
    # Clamp all inputs to [0.0, 1.0]
    ps = clamp(persistence_score)
    vi = clamp(volatility_index)
    pds = clamp(predicted_drift_score)

    # Apply the locked formula
    score = (
        W_PERSISTENCE * ps
        + W_INVERSE_VOLATILITY * (1.0 - vi)
        + W_INVERSE_DRIFT * (1.0 - pds)
    )

    # Clamp output to [0.0, 1.0]
    return clamp(score)


def compute_continuity_pressure(continuity_score: float) -> float:
    """
    Compute continuity pressure from continuity score.

    FORMULA (LOCKED):
        continuity_pressure = 1 - continuity_score

    Args:
        continuity_score: Continuity score [0.0, 1.0]

    Returns:
        Continuity pressure in [0.0, 1.0]
    """
    return clamp(1.0 - clamp(continuity_score))


def compute_continuity_mode(continuity_score: float) -> str:
    """
    Compute continuity mode from continuity score.

    RULES (LOCKED):
        - continuity_score >= 0.75 -> "stable"
        - continuity_score >= 0.45 -> "strained"
        - continuity_score < 0.45 -> "fragmenting"

    Args:
        continuity_score: Continuity score [0.0, 1.0]

    Returns:
        Mode string: "stable", "strained", or "fragmenting"
    """
    return mode_from_score(continuity_score)


def count_direction_reversals(values: List[float]) -> int:
    """
    Count the number of direction reversals in a sequence of values.

    A reversal occurs when the direction of change (increasing/decreasing)
    changes between consecutive pairs.

    Args:
        values: List of numeric values

    Returns:
        Number of direction reversals
    """
    if len(values) < 3:
        return 0

    reversals = 0
    prev_direction = None

    for i in range(1, len(values)):
        diff = values[i] - values[i - 1]

        if abs(diff) < 1e-9:
            # No significant change, skip
            continue

        current_direction = 1 if diff > 0 else -1

        if prev_direction is not None and current_direction != prev_direction:
            reversals += 1

        prev_direction = current_direction

    return reversals


def detect_oscillation(
    volatility_index: float,
    historical_resonance_values: List[float],
) -> bool:
    """
    Detect oscillation in identity trajectory.

    RULES (LOCKED):
        oscillation_detected = True if:
        - volatility_index > 0.6 AND
        - historical resonance index shows >= 2 direction reversals
          over last N snapshots (N = 5 max, deterministic window)

    Args:
        volatility_index: P36 volatility index [0.0, 1.0]
        historical_resonance_values: List of historical resonance index values

    Returns:
        True if oscillation detected, False otherwise
    """
    # Check volatility threshold
    if volatility_index <= OSCILLATION_VOLATILITY_THRESHOLD:
        return False

    # Get window of values (max OSCILLATION_WINDOW_SIZE)
    window = historical_resonance_values[-OSCILLATION_WINDOW_SIZE:]

    # Count direction reversals
    reversals = count_direction_reversals(window)

    return reversals >= OSCILLATION_MIN_REVERSALS


def compute_contributing_factors(
    predicted_drift_score: float,
    persistence_score: float,
    volatility_index: float,
    oscillation_detected: bool,
) -> Tuple[str, ...]:
    """
    Compute contributing factors based on threshold rules.

    RULES (LOCKED):
        - "high_drift" if predicted_drift_score > 0.6
        - "low_persistence" if persistence_score < 0.4
        - "high_volatility" if volatility_index > 0.6
        - "oscillation" if oscillation_detected

    No interpretation. No emotion labeling.

    Args:
        predicted_drift_score: P35 predicted drift score [0.0, 1.0]
        persistence_score: P36 persistence score [0.0, 1.0]
        volatility_index: P36 volatility index [0.0, 1.0]
        oscillation_detected: Whether oscillation was detected

    Returns:
        Tuple of contributing factor tags
    """
    factors: List[str] = []

    if predicted_drift_score > HIGH_DRIFT_THRESHOLD:
        factors.append("high_drift")

    if persistence_score < LOW_PERSISTENCE_THRESHOLD:
        factors.append("low_persistence")

    if volatility_index > HIGH_VOLATILITY_THRESHOLD:
        factors.append("high_volatility")

    if oscillation_detected:
        factors.append("oscillation")

    return tuple(factors)


# =============================================================================
# MAIN COMPUTATION FUNCTION
# =============================================================================


def compute_adaptive_continuity(
    p35_predicted_drift_score: Optional[float] = None,
    p35_drift_risk_band: Optional[str] = None,
    p36_identity_resonance_index: Optional[float] = None,
    p36_persistence_score: Optional[float] = None,
    p36_volatility_index: Optional[float] = None,
    historical_resonance_values: Optional[List[float]] = None,
) -> AdaptiveContinuityReport:
    """
    Compute adaptive continuity report from P35 and P36 inputs.

    This is the main entry point for Phase 37 computation.

    FORMULA (LOCKED):
        continuity_score =
            0.40 * persistence_score
          + 0.30 * (1 - volatility_index)
          + 0.30 * (1 - predicted_drift_score)

        continuity_pressure = 1 - continuity_score

    Args:
        p35_predicted_drift_score: P35 predicted drift score [0.0, 1.0]
        p35_drift_risk_band: P35 drift risk band ("low", "moderate", "high")
        p36_identity_resonance_index: P36 identity resonance index [0.0, 1.0]
        p36_persistence_score: P36 persistence score [0.0, 1.0]
        p36_volatility_index: P36 volatility index [0.0, 1.0]
        historical_resonance_values: List of historical resonance index values

    Returns:
        AdaptiveContinuityReport with computed values
    """
    # Get values with neutral defaults
    drift_score = safe_get(p35_predicted_drift_score, 0.5)
    drift_band = p35_drift_risk_band or "moderate"
    resonance_index = safe_get(p36_identity_resonance_index, 0.5)
    persistence = safe_get(p36_persistence_score, 0.5)
    volatility = safe_get(p36_volatility_index, 0.5)
    history = historical_resonance_values or []

    # Compute continuity score
    continuity_score = compute_continuity_score(
        persistence_score=persistence,
        volatility_index=volatility,
        predicted_drift_score=drift_score,
    )

    # Compute continuity pressure
    continuity_pressure = compute_continuity_pressure(continuity_score)

    # Compute continuity mode
    continuity_mode = compute_continuity_mode(continuity_score)

    # Detect oscillation
    oscillation_detected = detect_oscillation(
        volatility_index=volatility,
        historical_resonance_values=history,
    )

    # Compute contributing factors
    contributing_factors = compute_contributing_factors(
        predicted_drift_score=drift_score,
        persistence_score=persistence,
        volatility_index=volatility,
        oscillation_detected=oscillation_detected,
    )

    # Create and return report
    return create_report(
        continuity_score=continuity_score,
        continuity_mode=continuity_mode,
        continuity_pressure=continuity_pressure,
        oscillation_detected=oscillation_detected,
        contributing_factors=contributing_factors,
        p35_predicted_drift_score=drift_score,
        p35_drift_risk_band=drift_band,
        p36_identity_resonance_index=resonance_index,
        p36_persistence_score=persistence,
        p36_volatility_index=volatility,
        historical_resonance_count=len(history),
        debug={},
    )


# Public exports
__all__ = [
    # Helpers
    "clamp",
    "safe_get",
    # Core formulas
    "compute_continuity_score",
    "compute_continuity_pressure",
    "compute_continuity_mode",
    "count_direction_reversals",
    "detect_oscillation",
    "compute_contributing_factors",
    # Main function
    "compute_adaptive_continuity",
]
