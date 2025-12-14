"""
Phase 46: Trajectory Field Convergence Engine

Core computation logic for measuring whether the trajectory field
is converging, diverging, or unresolved over time.

This is field convergence measurement - not prediction,
not decision-making, not trajectory selection.

Invariants:
    INV-P46-1: No trajectory ranking (individual futures are never compared)
    INV-P46-2: Temporal comparison only (uses only past vs current convergence)
    INV-P46-3: Deterministic math (no learning, no heuristics)
    INV-P46-4: Observer-only (cannot influence routing, gating, or decisions)
    INV-P46-5: Absence-safe (missing inputs -> no output)

INPUTS (Read-Only):
    Phase 46 MAY read:
        - Current P45 MultiTrajectoryStabilityField (convergence_index)
        - Historical P45 snapshots (for trend computation)

    Phase 46 MUST NOT read:
        - Regime (P6)
        - Discourse / semantics / lexical layers
        - Acoustic / vrtti / kosha layers
        - Policy or governance phases (>=50)
        - Renderer or persona layers
"""

from __future__ import annotations

from typing import Any, List, Optional

from .p46_schema import (
    TrajectoryFieldConvergenceReport,
    create_convergence_report,
    _classify_convergence_trend,
    TREND_DELTA_THRESHOLD,
)


def compute_convergence_report(
    p45_stability_field: Any,
    p45_historical_snapshots: List[Any] | None = None,
) -> Optional[TrajectoryFieldConvergenceReport]:
    """
    Compute the trajectory field convergence report.

    Computation Steps:
    1. Guard conditions - return None if P45 is missing (INV-P46-5)
    2. Extract convergence_index from current P45
    3. Compute previous mean from historical snapshots (if available)
    4. Calculate temporal delta
    5. Classify trend and field state
    6. Package output

    INV-P46-1: No trajectory ranking - we only use aggregate convergence_index.
    INV-P46-2: Temporal comparison only - delta from past vs current.
    INV-P46-3: Deterministic math - pure arithmetic, no heuristics.
    INV-P46-4: Observer-only - we only produce a report, no side effects.
    INV-P46-5: Absence-safe - missing inputs produce None.

    Args:
        p45_stability_field: Current P45 MultiTrajectoryStabilityField
        p45_historical_snapshots: Optional list of prior P45 snapshots

    Returns:
        TrajectoryFieldConvergenceReport if computation succeeds, None otherwise
    """
    # =========================================================================
    # Step 1: Guard Conditions (INV-P46-5)
    # =========================================================================

    # If P45 is missing, return None
    if p45_stability_field is None:
        return None

    # Extract convergence_index from P45
    current_convergence = _extract_convergence_index(p45_stability_field)
    if current_convergence is None:
        return None

    # =========================================================================
    # Step 2: Extract Historical Data (INV-P46-2)
    # =========================================================================

    # Normalize historical snapshots to a list
    historical = p45_historical_snapshots or []

    # Extract convergence values from historical snapshots
    historical_values = _extract_historical_convergence_values(historical)

    # Total sample window (current + historical)
    sample_window = 1 + len(historical_values)

    # =========================================================================
    # Step 3: Compute Convergence Score (INV-P46-3)
    # =========================================================================

    # convergence_score = clamp(current, 0.0, 1.0)
    # (No smoothing, no weighting - deterministic)
    convergence_score = _clamp(current_convergence, 0.0, 1.0)

    # =========================================================================
    # Step 4: Trend Detection (INV-P46-2)
    # =========================================================================

    if len(historical_values) < 1:
        # Fewer than 2 snapshots total → trend = "flat"
        convergence_trend = "flat"
        delta = 0.0
    else:
        # Compute mean of historical convergence values
        previous_mean = _mean(historical_values)
        delta = current_convergence - previous_mean
        convergence_trend = _classify_convergence_trend(delta)

    # =========================================================================
    # Step 5: Package Output (INV-P46-4)
    # =========================================================================

    debug_info = {
        "current_convergence": current_convergence,
        "historical_count": len(historical_values),
        "delta": delta,
    }

    return create_convergence_report(
        convergence_score=convergence_score,
        convergence_trend=convergence_trend,
        sample_window=sample_window,
        debug=debug_info,
    )


# =============================================================================
# HELPER FUNCTIONS (Deterministic Math - INV-P46-3)
# =============================================================================


def _extract_convergence_index(p45_stability_field: Any) -> Optional[float]:
    """
    Extract convergence_index from P45 stability field.

    INV-P46-1: We only read the aggregate index, not individual trajectories.

    Args:
        p45_stability_field: P45 MultiTrajectoryStabilityField

    Returns:
        convergence_index if available, None otherwise
    """
    convergence_index = getattr(p45_stability_field, "convergence_index", None)

    if convergence_index is None:
        return None

    if not isinstance(convergence_index, (int, float)):
        return None

    return float(convergence_index)


def _extract_historical_convergence_values(
    historical_snapshots: List[Any],
) -> List[float]:
    """
    Extract convergence_index values from historical P45 snapshots.

    INV-P46-2: We only use temporal comparisons from past snapshots.
    INV-P46-3: Pure extraction, no transformation.

    Args:
        historical_snapshots: List of prior P45 stability fields

    Returns:
        List of convergence_index values
    """
    values = []
    for snapshot in historical_snapshots:
        convergence_index = _extract_convergence_index(snapshot)
        if convergence_index is not None:
            values.append(convergence_index)
    return values


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp a value to the specified range.

    INV-P46-3: Pure arithmetic, deterministic.

    Args:
        value: The value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))


def _mean(values: List[float]) -> float:
    """
    Compute the arithmetic mean of a list of values.

    INV-P46-3: Pure arithmetic, deterministic.

    Args:
        values: List of numeric values

    Returns:
        Arithmetic mean (0.0 if empty)
    """
    if not values:
        return 0.0
    return sum(values) / len(values)
