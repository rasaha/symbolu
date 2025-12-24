"""
Phase 47: Unified Trajectory-Scenario Synthesis Engine

Core computation logic for synthesizing trajectory and scenario spaces.

This module provides the deterministic synthesis computation that combines:
    - P42: Scenario coherence (fusion_confidence)
    - P45: Trajectory stability (stability_index)
    - P46: Convergence measurement (convergence_score)

Invariants:
    INV-P47-1: No prediction (no future selection or ranking)
    INV-P47-2: Symmetric synthesis (scenario and trajectory treated as peers)
    INV-P47-3: Deterministic math only (pure weighted aggregation)
    INV-P47-4: Observer-only (cannot influence any authority phase)
    INV-P47-5: Absence-safe (missing inputs -> no output)
"""

from typing import Any, Dict, Optional

from .p47_schema import (
    UnifiedTrajectoryScenarioReport,
    _classify_alignment_band,
    _classify_dominant_factor,
)


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value to the specified range."""
    return max(min_val, min(max_val, value))


def compute_synthesis_report(
    scenario_coherence: float,
    trajectory_stability: float,
    convergence_score: float,
) -> UnifiedTrajectoryScenarioReport:
    """
    Compute the unified trajectory-scenario synthesis report.

    This is pure deterministic computation with no side effects.

    Formula (INV-P47-3):
        alignment_score = clamp(
            0.40 * trajectory_stability +
            0.40 * scenario_coherence +
            0.20 * convergence_score,
            0.0,
            1.0
        )

    Note: The weights are symmetric for trajectory and scenario (0.40 each)
    to satisfy INV-P47-2 (symmetric synthesis).

    Args:
        scenario_coherence: S from P42 (fusion_confidence) [0.0, 1.0]
        trajectory_stability: T from P45 (stability_index) [0.0, 1.0]
        convergence_score: C from P46 (convergence_score) [0.0, 1.0]

    Returns:
        UnifiedTrajectoryScenarioReport with computed values
    """
    # Step 3: Alignment Score Formula (INV-P47-3: Deterministic math only)
    # Weights: T=0.40, S=0.40, C=0.20 (symmetric for T and S per INV-P47-2)
    raw_score = (
        0.40 * trajectory_stability
        + 0.40 * scenario_coherence
        + 0.20 * convergence_score
    )

    # Clamp to [0.0, 1.0] - no smoothing, no normalization beyond clamp
    alignment_score = _clamp(raw_score, 0.0, 1.0)

    # Step 4: Alignment Band classification
    alignment_band = _classify_alignment_band(alignment_score)

    # Step 5: Dominant Factor Detection (INV-P47-2: Symmetric comparison)
    # Compare T and S directly
    dominant_factor = _classify_dominant_factor(
        trajectory_value=trajectory_stability,
        scenario_value=scenario_coherence,
    )

    # Step 6: Package Output (INV-P47-4: Observer-only)
    return UnifiedTrajectoryScenarioReport(
        alignment_score=alignment_score,
        alignment_band=alignment_band,
        dominant_factor=dominant_factor,
        observer_only=True,
        debug={
            "scenario_coherence": scenario_coherence,
            "trajectory_stability": trajectory_stability,
            "convergence_score": convergence_score,
            "raw_score": raw_score,
        },
    )


def run_p47_directly(
    p42_scenario_fusion: Any,
    p45_multi_trajectory_stability: Any,
    p46_trajectory_convergence: Any,
) -> Optional[UnifiedTrajectoryScenarioReport]:
    """
    Run P47 synthesis directly with explicit phase inputs.

    This is the core execution entry point for testing and direct invocation.

    Args:
        p42_scenario_fusion: ScenarioFusionField from P42 (requires fusion_confidence)
        p45_multi_trajectory_stability: MultiTrajectoryStabilityField from P45
            (requires stability_index)
        p46_trajectory_convergence: TrajectoryFieldConvergenceReport from P46
            (requires convergence_score)

    Returns:
        UnifiedTrajectoryScenarioReport if all inputs valid, None otherwise
    """
    # Step 1: Guard Conditions (INV-P47-5: Absence-safe)
    if p42_scenario_fusion is None:
        return None
    if p45_multi_trajectory_stability is None:
        return None
    if p46_trajectory_convergence is None:
        return None

    # Step 2: Extract Inputs
    # S = scenario_coherence_score (mapped to fusion_confidence in P42)
    scenario_coherence = getattr(p42_scenario_fusion, "fusion_confidence", None)
    if scenario_coherence is None:
        return None

    # T = stability_index from P45
    trajectory_stability = getattr(
        p45_multi_trajectory_stability, "stability_index", None
    )
    if trajectory_stability is None:
        return None

    # C = convergence_score from P46
    convergence_score = getattr(p46_trajectory_convergence, "convergence_score", None)
    if convergence_score is None:
        return None

    # Compute and return synthesis report
    return compute_synthesis_report(
        scenario_coherence=scenario_coherence,
        trajectory_stability=trajectory_stability,
        convergence_score=convergence_score,
    )
