"""
P36 - Identity Resonance Memory Formula

Deterministic formula computation for identity resonance memory.
This module contains the locked formula implementations.

FORMULAS (LOCKED):

Step 1 - Identity Resonance Index:
    identity_resonance_index =
        0.40 * ucf_score
      + 0.30 * identity_harmonics_score
      + 0.20 * schema_stability
      + 0.10 * (1 - predicted_drift_score)

Step 2 - Persistence Score:
    persistence_score =
        1.0 - variance(identity_resonance_index over last N snapshots)

Step 3 - Volatility Index:
    volatility_index =
        average(|delta identity_resonance_index| over last N-1 transitions)

Step 4 - Stability Band (Rule-Based):
    - "stable" -> persistence >= 0.75 AND volatility < 0.20
    - "soft" -> otherwise
    - "fragile" -> persistence < 0.40 OR volatility >= 0.45

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs
    - No LLM, no ML, no learning
    - No probabilistic sampling
    - Pure arithmetic operations only
    - No decay heuristics beyond formulas

INVARIANTS:
    - INV-P36-4: Deterministic math only
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from symbolu.core.predictive.identity_memory.memory_state import (
    W_UCF_SCORE,
    W_IDENTITY_HARMONICS,
    W_SCHEMA_STABILITY,
    W_INVERSE_DRIFT,
    PERSISTENCE_STABLE_THRESHOLD,
    PERSISTENCE_FRAGILE_THRESHOLD,
    VOLATILITY_STABLE_THRESHOLD,
    VOLATILITY_FRAGILE_THRESHOLD,
    DEFAULT_MEMORY_DEPTH,
    MAX_MEMORY_DEPTH,
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


def compute_identity_resonance_index(
    ucf_score: Optional[float] = None,
    identity_harmonics_score: Optional[float] = None,
    schema_stability: Optional[float] = None,
    predicted_drift_score: Optional[float] = None,
) -> float:
    """
    Compute the identity resonance index using the locked formula.

    FORMULA (LOCKED):
        identity_resonance_index =
            0.40 * ucf_score
          + 0.30 * identity_harmonics_score
          + 0.20 * schema_stability
          + 0.10 * (1 - predicted_drift_score)

    All inputs default to 0.5 (neutral) if not provided.
    All inputs are clamped to [0.0, 1.0] before computation.
    Output is clamped to [0.0, 1.0].

    Args:
        ucf_score: P26 UCF score [0.0, 1.0]
        identity_harmonics_score: P34 identity harmonics score [0.0, 1.0]
        schema_stability: P33 schema stability [0.0, 1.0]
        predicted_drift_score: P35 predicted drift score [0.0, 1.0]

    Returns:
        Identity resonance index in [0.0, 1.0]
    """
    # Get values with neutral defaults
    ucf = safe_get(ucf_score, 0.5)
    harmonics = safe_get(identity_harmonics_score, 0.5)
    schema = safe_get(schema_stability, 0.5)
    drift = safe_get(predicted_drift_score, 0.5)

    # Apply the locked formula
    index = (
        W_UCF_SCORE * ucf
        + W_IDENTITY_HARMONICS * harmonics
        + W_SCHEMA_STABILITY * schema
        + W_INVERSE_DRIFT * (1.0 - drift)
    )

    # Clamp output to [0.0, 1.0]
    return clamp(index)


def compute_variance(values: List[float]) -> float:
    """
    Compute the variance of a list of values.

    Args:
        values: List of numeric values

    Returns:
        Variance of the values, or 0.0 if < 2 values
    """
    if len(values) < 2:
        return 0.0

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return variance


def compute_persistence_score(
    historical_resonance_values: List[float],
) -> float:
    """
    Compute persistence score from historical resonance values.

    FORMULA (LOCKED):
        persistence_score = 1.0 - variance(identity_resonance_index over last N snapshots)

    Clamped to [0.0, 1.0].

    For < 2 snapshots, returns 1.0 (perfect persistence due to lack of variance).

    Args:
        historical_resonance_values: List of historical identity_resonance_index values

    Returns:
        Persistence score in [0.0, 1.0]
    """
    if len(historical_resonance_values) < 2:
        # No variance possible with < 2 values, return perfect persistence
        return 1.0

    variance = compute_variance(historical_resonance_values)
    persistence = 1.0 - variance

    return clamp(persistence)


def compute_volatility_index(
    historical_resonance_values: List[float],
) -> float:
    """
    Compute volatility index from historical resonance values.

    FORMULA (LOCKED):
        volatility_index = average(|delta identity_resonance_index| over last N-1 transitions)

    Clamped to [0.0, 1.0].

    For < 2 snapshots, returns 0.0 (no volatility).

    Args:
        historical_resonance_values: List of historical identity_resonance_index values

    Returns:
        Volatility index in [0.0, 1.0]
    """
    if len(historical_resonance_values) < 2:
        # No transitions possible with < 2 values, return zero volatility
        return 0.0

    # Compute absolute deltas between consecutive values
    deltas = []
    for i in range(1, len(historical_resonance_values)):
        delta = abs(historical_resonance_values[i] - historical_resonance_values[i - 1])
        deltas.append(delta)

    # Average of absolute deltas
    if not deltas:
        return 0.0

    volatility = sum(deltas) / len(deltas)

    return clamp(volatility)


def compute_stability_band(
    persistence_score: float,
    volatility_index: float,
) -> str:
    """
    Compute stability band from persistence and volatility.

    RULES (LOCKED):
        - "stable" -> persistence >= 0.75 AND volatility < 0.20
        - "fragile" -> persistence < 0.40 OR volatility >= 0.45
        - "soft" -> otherwise

    Args:
        persistence_score: Persistence score [0.0, 1.0]
        volatility_index: Volatility index [0.0, 1.0]

    Returns:
        Stability band: "stable", "soft", or "fragile"
    """
    # Check fragile conditions first (OR logic)
    if persistence_score < PERSISTENCE_FRAGILE_THRESHOLD or volatility_index >= VOLATILITY_FRAGILE_THRESHOLD:
        return "fragile"

    # Check stable conditions (AND logic)
    if persistence_score >= PERSISTENCE_STABLE_THRESHOLD and volatility_index < VOLATILITY_STABLE_THRESHOLD:
        return "stable"

    # Default to soft
    return "soft"


def compute_all_metrics(
    ucf_score: Optional[float] = None,
    identity_harmonics_score: Optional[float] = None,
    schema_stability: Optional[float] = None,
    predicted_drift_score: Optional[float] = None,
    historical_resonance_values: Optional[List[float]] = None,
    memory_depth: int = DEFAULT_MEMORY_DEPTH,
) -> Tuple[float, float, float, str, List[float]]:
    """
    Compute all identity resonance memory metrics.

    Args:
        ucf_score: P26 UCF score [0.0, 1.0]
        identity_harmonics_score: P34 identity harmonics score [0.0, 1.0]
        schema_stability: P33 schema stability [0.0, 1.0]
        predicted_drift_score: P35 predicted drift score [0.0, 1.0]
        historical_resonance_values: List of historical resonance values
        memory_depth: Maximum number of snapshots to use (default 5, max 7)

    Returns:
        Tuple of:
        - identity_resonance_index: [0.0, 1.0]
        - persistence_score: [0.0, 1.0]
        - volatility_index: [0.0, 1.0]
        - stability_band: "stable" | "soft" | "fragile"
        - updated_historical_values: List of resonance values (capped at memory_depth)
    """
    # Cap memory depth
    memory_depth = min(memory_depth, MAX_MEMORY_DEPTH)

    # Compute current resonance index
    current_resonance = compute_identity_resonance_index(
        ucf_score=ucf_score,
        identity_harmonics_score=identity_harmonics_score,
        schema_stability=schema_stability,
        predicted_drift_score=predicted_drift_score,
    )

    # Build updated historical values (append current, cap at memory_depth)
    if historical_resonance_values is None:
        historical_resonance_values = []

    updated_values = list(historical_resonance_values) + [current_resonance]

    # Cap to memory_depth (keep most recent)
    if len(updated_values) > memory_depth:
        updated_values = updated_values[-memory_depth:]

    # Compute persistence and volatility from updated history
    persistence = compute_persistence_score(updated_values)
    volatility = compute_volatility_index(updated_values)

    # Determine stability band
    stability_band = compute_stability_band(persistence, volatility)

    return (
        current_resonance,
        persistence,
        volatility,
        stability_band,
        updated_values,
    )


# Public exports
__all__ = [
    # Helpers
    "clamp",
    "safe_get",
    # Core formulas
    "compute_identity_resonance_index",
    "compute_variance",
    "compute_persistence_score",
    "compute_volatility_index",
    "compute_stability_band",
    "compute_all_metrics",
]
