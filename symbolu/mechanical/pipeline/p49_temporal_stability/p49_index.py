"""
Phase 49: Temporal Stability Index Computation Engine

Core computation engine with deterministic formula logic.

Phase 49 answers:
    "How stable is this system over time, as a single interpretable index?"

This is synthesis of temporal signals into one index - not action, not gating.

INPUTS (Read-Only):
    Phase 49 MAY read:
        - ctx.p38_temporal_forecast (forecast_score)
        - ctx.p40_cross_horizon_alignment (alignment_score)
        - ctx.p45_multi_trajectory_stability (stability_index)
        - ctx.p46_trajectory_convergence (convergence_score)
        - ctx.p47_unified_trajectory_scenario (alignment_score)

    Phase 49 MUST NOT read:
        - Regime (P6)
        - Discourse / semantics / lexical phases
        - Acoustic / vrtti / kosha observers
        - Governance phases (>=50)
        - Renderer or persona layers

INVARIANTS:
    INV-P49-1: Observer-only (no downstream influence)
    INV-P49-2: Deterministic (pure math, no state)
    INV-P49-3: No authority (cannot gate, block, or trigger)
    INV-P49-4: Absence-safe (missing inputs -> None)
    INV-P49-5: Temporal meaning only (index reflects time stability, not intent or emotion)
"""

from __future__ import annotations

from typing import Any, Optional

from .p49_schema import (
    TemporalStabilityIndex,
    create_temporal_stability_index,
    W_FORECAST,
    W_HORIZON,
    W_TRAJECTORY,
    W_CONVERGENCE,
    W_ALIGNMENT,
)


# ============================================================================
# CORE FORMULA
# ============================================================================


def _compute_temporal_stability_index(
    forecast_score: float,
    horizon_alignment_score: float,
    trajectory_stability_index: float,
    convergence_score: float,
    synthesis_alignment_score: float,
) -> float:
    """
    Compute temporal stability index using deterministic weighted aggregation.

    INV-P49-2: Deterministic - pure math, no randomness, no heuristics.
    INV-P49-5: Temporal meaning only - combines only temporal stability signals.

    Formula:
        temporal_stability_index = clamp(
            0.25 * F +  # P38 forecast_score
            0.20 * H +  # P40 alignment_score
            0.20 * T +  # P45 stability_index
            0.20 * C +  # P46 convergence_score
            0.15 * A,   # P47 alignment_score
            0.0,
            1.0
        )

    Args:
        forecast_score: F from P38 [0.0, 1.0]
        horizon_alignment_score: H from P40 [0.0, 1.0]
        trajectory_stability_index: T from P45 [0.0, 1.0]
        convergence_score: C from P46 [0.0, 1.0]
        synthesis_alignment_score: A from P47 [0.0, 1.0]

    Returns:
        Temporal stability index in [0.0, 1.0]
    """
    F = forecast_score
    H = horizon_alignment_score
    T = trajectory_stability_index
    C = convergence_score
    A = synthesis_alignment_score

    # Weighted aggregation
    raw_index = (
        W_FORECAST * F +
        W_HORIZON * H +
        W_TRAJECTORY * T +
        W_CONVERGENCE * C +
        W_ALIGNMENT * A
    )

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, raw_index))


# ============================================================================
# ENTRY POINTS
# ============================================================================


def compute_temporal_stability(
    forecast_score: float,
    horizon_alignment_score: float,
    trajectory_stability_index: float,
    convergence_score: float,
    synthesis_alignment_score: float,
) -> TemporalStabilityIndex:
    """
    Compute temporal stability index from raw inputs.

    INV-P49-1: Observer-only - creates report with observer_only=True.
    INV-P49-2: Deterministic - same inputs always produce same output.
    INV-P49-5: Temporal meaning only - interprets inputs as temporal signals.

    Args:
        forecast_score: F from P38 [0.0, 1.0]
        horizon_alignment_score: H from P40 [0.0, 1.0]
        trajectory_stability_index: T from P45 [0.0, 1.0]
        convergence_score: C from P46 [0.0, 1.0]
        synthesis_alignment_score: A from P47 [0.0, 1.0]

    Returns:
        TemporalStabilityIndex
    """
    # Compute the index
    temporal_index = _compute_temporal_stability_index(
        forecast_score=forecast_score,
        horizon_alignment_score=horizon_alignment_score,
        trajectory_stability_index=trajectory_stability_index,
        convergence_score=convergence_score,
        synthesis_alignment_score=synthesis_alignment_score,
    )

    # Create report with debug info
    debug = {
        "inputs": {
            "F_forecast": forecast_score,
            "H_horizon": horizon_alignment_score,
            "T_trajectory": trajectory_stability_index,
            "C_convergence": convergence_score,
            "A_alignment": synthesis_alignment_score,
        },
        "weights": {
            "W_FORECAST": W_FORECAST,
            "W_HORIZON": W_HORIZON,
            "W_TRAJECTORY": W_TRAJECTORY,
            "W_CONVERGENCE": W_CONVERGENCE,
            "W_ALIGNMENT": W_ALIGNMENT,
        },
    }

    return create_temporal_stability_index(
        temporal_stability_index=temporal_index,
        debug=debug,
    )


def run_p49_directly(
    p38_temporal_forecast: Any,
    p40_cross_horizon_alignment: Any,
    p45_multi_trajectory_stability: Any,
    p46_trajectory_convergence: Any,
    p47_unified_trajectory_scenario: Any,
) -> Optional[TemporalStabilityIndex]:
    """
    Run P49 temporal stability index computation directly with upstream reports.

    This is the direct computation entry point for testing and
    bypassing context extraction.

    INV-P49-4: Absence-safe - returns None if any input is missing or invalid.

    Args:
        p38_temporal_forecast: P38 report (needs forecast_score)
        p40_cross_horizon_alignment: P40 report (needs alignment_score)
        p45_multi_trajectory_stability: P45 report (needs stability_index)
        p46_trajectory_convergence: P46 report (needs convergence_score)
        p47_unified_trajectory_scenario: P47 report (needs alignment_score)

    Returns:
        TemporalStabilityIndex if all inputs valid, None otherwise
    """
    # INV-P49-4: Guard against missing inputs
    if p38_temporal_forecast is None:
        return None
    if p40_cross_horizon_alignment is None:
        return None
    if p45_multi_trajectory_stability is None:
        return None
    if p46_trajectory_convergence is None:
        return None
    if p47_unified_trajectory_scenario is None:
        return None

    # Extract required fields with safe getattr
    forecast_score = getattr(p38_temporal_forecast, "forecast_score", None)
    horizon_alignment_score = getattr(p40_cross_horizon_alignment, "alignment_score", None)
    trajectory_stability_index = getattr(p45_multi_trajectory_stability, "stability_index", None)
    convergence_score = getattr(p46_trajectory_convergence, "convergence_score", None)
    synthesis_alignment_score = getattr(p47_unified_trajectory_scenario, "alignment_score", None)

    # INV-P49-4: Guard against missing fields
    if forecast_score is None:
        return None
    if horizon_alignment_score is None:
        return None
    if trajectory_stability_index is None:
        return None
    if convergence_score is None:
        return None
    if synthesis_alignment_score is None:
        return None

    # Run computation
    return compute_temporal_stability(
        forecast_score=forecast_score,
        horizon_alignment_score=horizon_alignment_score,
        trajectory_stability_index=trajectory_stability_index,
        convergence_score=convergence_score,
        synthesis_alignment_score=synthesis_alignment_score,
    )


# Public exports
__all__ = [
    "compute_temporal_stability",
    "run_p49_directly",
]
