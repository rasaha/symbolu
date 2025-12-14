"""
Phase 45: Multi-Trajectory Stability Field Engine

Core computation logic for field-level stability aggregation.

Phase 45 computes a stability field over multiple possible futures,
measuring dispersion, volatility, and convergence tendency
without preferring or selecting any trajectory.

This is structural analysis, not decision-making.

Invariants:
    INV-P45-1: No trajectory preference (no ranking, sorting, or selection)
    INV-P45-2: Deterministic aggregation only (pure math, no heuristics, no learning)
    INV-P45-3: Field-level semantics only (individual variants do not influence bands)
    INV-P45-4: Observer-only (output never influences routing or governance)
    INV-P45-5: Absence-safe (missing inputs -> no output)

Computation Steps:
    1. Guard conditions - return None if required inputs missing
    2. Extract variant alignment scores from P44
    3. Compute volatility_index = std_dev(scores)
    4. Compute stability_index = (mean * 0.65) + ((1 - volatility) * 0.35)
    5. Compute convergence_index = 1 - mean_absolute_deviation(scores)
    6. Classify stability_band from stability_index only
    7. Package output
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .p45_schema import (
    MultiTrajectoryStabilityField,
    create_stability_field,
)


# ============================================================================
# DETERMINISTIC MATH HELPERS (INV-P45-2)
# ============================================================================


def _mean(values: List[float]) -> float:
    """
    Compute arithmetic mean deterministically.

    INV-P45-2: Pure math, no randomness.

    Args:
        values: Non-empty list of floats

    Returns:
        Arithmetic mean
    """
    return sum(values) / len(values)


def _std_dev(values: List[float]) -> float:
    """
    Compute population standard deviation deterministically.

    INV-P45-2: Pure math, no randomness.
    Uses population std dev (divide by n, not n-1).

    Args:
        values: Non-empty list of floats

    Returns:
        Population standard deviation
    """
    if len(values) == 1:
        return 0.0

    mean_val = _mean(values)
    variance = sum((x - mean_val) ** 2 for x in values) / len(values)
    return math.sqrt(variance)


def _mean_absolute_deviation(values: List[float]) -> float:
    """
    Compute mean absolute deviation from the mean.

    INV-P45-2: Pure math, no randomness.

    Args:
        values: Non-empty list of floats

    Returns:
        Mean absolute deviation
    """
    mean_val = _mean(values)
    return _mean([abs(x - mean_val) for x in values])


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp value to [min_val, max_val] range.

    INV-P45-2: Pure math, deterministic.

    Args:
        value: Value to clamp
        min_val: Minimum bound
        max_val: Maximum bound

    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))


# ============================================================================
# CORE COMPUTATION
# ============================================================================


def compute_stability_field(
    p44_alignment_report: Any,
    p43_what_if_set: Any,
) -> Optional[MultiTrajectoryStabilityField]:
    """
    Compute multi-trajectory stability field from P44 alignment data.

    This function performs field-level aggregation across trajectories.
    It does not choose, rank, or predict outcomes.
    It answers: "How stable is the future space as a whole?"

    INV-P45-1: No trajectory preference - no ranking, sorting, or selection.
    INV-P45-2: Deterministic aggregation only - pure math, no heuristics.
    INV-P45-3: Field-level semantics - variants don't influence bands.
    INV-P45-4: Observer-only - output never influences routing.
    INV-P45-5: Absence-safe - missing inputs -> None.

    Args:
        p44_alignment_report: CoherenceScenarioAlignmentReport from Phase 44
        p43_what_if_set: ScenarioWhatIfSet from Phase 43

    Returns:
        MultiTrajectoryStabilityField if computation succeeds, None otherwise
    """
    # =========================================================================
    # Step 1: Guard Conditions (INV-P45-5)
    # =========================================================================
    if p44_alignment_report is None:
        return None

    if p43_what_if_set is None:
        return None

    # =========================================================================
    # Step 2: Extract Variant Alignment Scores
    # =========================================================================
    variant_alignment = getattr(p44_alignment_report, "variant_alignment", None)
    if variant_alignment is None:
        return None

    scores: List[float] = list(variant_alignment.values())
    n = len(scores)

    if n == 0:
        return None

    # =========================================================================
    # Step 3: Volatility Index (INV-P45-2: deterministic std_dev)
    # =========================================================================
    # Normalized dispersion: standard deviation clamped to [0.0, 1.0]
    volatility_index = _clamp(_std_dev(scores), 0.0, 1.0)

    # =========================================================================
    # Step 4: Stability Index (INV-P45-2: deterministic weighted formula)
    # =========================================================================
    # stability_index = (mean * 0.65) + ((1 - volatility) * 0.35)
    mean_score = _mean(scores)
    stability_index = _clamp(
        (mean_score * 0.65) + ((1.0 - volatility_index) * 0.35),
        0.0,
        1.0,
    )

    # =========================================================================
    # Step 5: Convergence Index (INV-P45-2: deterministic MAD)
    # =========================================================================
    # Measure clustering near the mean:
    # convergence_index = 1.0 - mean(abs(score - mean(scores)) for score)
    mad = _mean_absolute_deviation(scores)
    convergence_index = _clamp(1.0 - mad, 0.0, 1.0)

    # =========================================================================
    # Step 6 & 7: Stability Band Classification and Package Output
    # (INV-P45-3: Band derived from stability_index only)
    # =========================================================================
    trajectory_count = n

    # Build debug info for observability
    debug_info: Dict[str, Any] = {
        "raw_scores": scores,
        "mean_score": mean_score,
        "std_dev": _std_dev(scores),
        "mad": mad,
    }

    # Use factory function which enforces invariants
    return create_stability_field(
        stability_index=stability_index,
        volatility_index=volatility_index,
        convergence_index=convergence_index,
        trajectory_count=trajectory_count,
        debug=debug_info,
    )


# Public exports
__all__ = [
    "compute_stability_field",
]
