"""
Phase 46: Trajectory Field Convergence Engine Tests

TESTING POLICY (from TESTING.md):
    - Every test MUST be mapped to exactly one invariant
    - One test -> one invariant
    - If a test cannot map to an invariant -> delete it
    - No math micro-tests, no snapshot tests, no redundancy

INVARIANTS:
    INV-P46-1: No trajectory ranking (individual futures are never compared)
    INV-P46-2: Temporal comparison only (uses only past vs current convergence)
    INV-P46-3: Deterministic math (no learning, no heuristics)
    INV-P46-4: Observer-only (cannot influence routing, gating, or decisions)
    INV-P46-5: Absence-safe (missing inputs -> no output)
"""

from dataclasses import dataclass
from typing import List

import pytest

from symbolu.mechanical.pipeline.p46_trajectory_convergence import (
    run_p46_directly,
    maybe_run_p46,
    TrajectoryFieldConvergenceReport,
)


# =============================================================================
# Mock Objects for Testing
# =============================================================================


@dataclass
class MockMultiTrajectoryStabilityField:
    """Mock P45 MultiTrajectoryStabilityField for testing."""

    stability_index: float
    volatility_index: float
    convergence_index: float
    trajectory_count: int
    stability_band: str
    observer_only: bool = True


class MockContext:
    """Mock PipelineContext for testing."""

    def __init__(self):
        self.p45_multi_trajectory_stability = None
        self.p45_historical_snapshots = None
        self.p46_trajectory_convergence = None
        self._p46_disabled = False


# =============================================================================
# INVARIANT TESTS (exactly one test per invariant)
# =============================================================================


# Proves INV-P46-1: No trajectory ranking (individual futures are never compared)
def test_no_trajectory_ranking():
    """
    Invariant: INV-P46-1
    Proves that P46 produces convergence measurements without any ranking,
    preference ordering, or comparison between individual trajectories.

    The output contains only aggregate field metrics derived from P45's
    convergence_index - no 'best' trajectory, no ordering, no selection.
    """
    # Create P45 mock with convergence_index
    p45_stability = MockMultiTrajectoryStabilityField(
        stability_index=0.75,
        volatility_index=0.15,
        convergence_index=0.80,
        trajectory_count=4,
        stability_band="stable",
    )

    result = run_p46_directly(
        p45_stability_field=p45_stability,
        p45_historical_snapshots=None,
    )

    assert result is not None

    # Verify: No ranking attributes exist
    assert not hasattr(result, "ranked_trajectories")
    assert not hasattr(result, "best_trajectory")
    assert not hasattr(result, "preferred_trajectory")
    assert not hasattr(result, "selected_trajectory")
    assert not hasattr(result, "trajectory_ranking")
    assert not hasattr(result, "trajectory_comparison")

    # Verify: Output contains only aggregate field metrics
    assert hasattr(result, "convergence_score")
    assert hasattr(result, "convergence_trend")
    assert hasattr(result, "field_state")
    assert hasattr(result, "sample_window")

    # Verify: convergence_score derived from P45's convergence_index (aggregate)
    assert result.convergence_score == 0.80


# Proves INV-P46-2: Temporal comparison only (uses only past vs current convergence)
def test_temporal_comparison_only():
    """
    Invariant: INV-P46-2
    Proves that P46 trend detection uses ONLY temporal delta between
    past and current convergence values, not any other signal.

    The convergence_trend is derived purely from comparing current
    convergence_index to the mean of historical convergence_index values.
    """
    # Create current P45 with convergence_index = 0.80
    p45_current = MockMultiTrajectoryStabilityField(
        stability_index=0.75,
        volatility_index=0.15,
        convergence_index=0.80,
        trajectory_count=3,
        stability_band="stable",
    )

    # Create historical snapshots with lower convergence (mean = 0.60)
    p45_historical = [
        MockMultiTrajectoryStabilityField(
            stability_index=0.60,
            volatility_index=0.20,
            convergence_index=0.55,
            trajectory_count=3,
            stability_band="strained",
        ),
        MockMultiTrajectoryStabilityField(
            stability_index=0.65,
            volatility_index=0.18,
            convergence_index=0.65,
            trajectory_count=3,
            stability_band="strained",
        ),
    ]

    result = run_p46_directly(
        p45_stability_field=p45_current,
        p45_historical_snapshots=p45_historical,
    )

    assert result is not None

    # delta = 0.80 - mean(0.55, 0.65) = 0.80 - 0.60 = +0.20
    # Since delta > +0.05, trend should be "increasing"
    assert result.convergence_trend == "increasing"

    # Verify sample_window counts all snapshots (current + historical)
    assert result.sample_window == 3  # 1 current + 2 historical

    # Test decreasing trend
    p45_current_low = MockMultiTrajectoryStabilityField(
        stability_index=0.50,
        volatility_index=0.25,
        convergence_index=0.40,  # Lower than historical mean
        trajectory_count=3,
        stability_band="strained",
    )

    p45_historical_high = [
        MockMultiTrajectoryStabilityField(
            stability_index=0.80,
            volatility_index=0.10,
            convergence_index=0.85,
            trajectory_count=3,
            stability_band="stable",
        ),
    ]

    result_decreasing = run_p46_directly(
        p45_stability_field=p45_current_low,
        p45_historical_snapshots=p45_historical_high,
    )

    # delta = 0.40 - 0.85 = -0.45
    # Since delta < -0.05, trend should be "decreasing"
    assert result_decreasing.convergence_trend == "decreasing"


# Proves INV-P46-3: Deterministic math (no learning, no heuristics)
def test_deterministic_math():
    """
    Invariant: INV-P46-3
    Proves that P46 produces identical outputs for identical inputs,
    demonstrating deterministic computation with no randomness,
    no learning, and no heuristics.
    """
    p45_stability = MockMultiTrajectoryStabilityField(
        stability_index=0.70,
        volatility_index=0.20,
        convergence_index=0.65,
        trajectory_count=3,
        stability_band="stable",
    )

    p45_historical = [
        MockMultiTrajectoryStabilityField(
            stability_index=0.60,
            volatility_index=0.25,
            convergence_index=0.55,
            trajectory_count=3,
            stability_band="strained",
        ),
    ]

    # Run computation multiple times with identical inputs
    results = []
    for _ in range(5):
        result = run_p46_directly(
            p45_stability_field=p45_stability,
            p45_historical_snapshots=p45_historical,
        )
        results.append(result)

    # Verify: All results are identical
    first_result = results[0]
    for result in results[1:]:
        assert result.convergence_score == first_result.convergence_score
        assert result.convergence_trend == first_result.convergence_trend
        assert result.field_state == first_result.field_state
        assert result.sample_window == first_result.sample_window
        assert result.observer_only == first_result.observer_only


# Proves INV-P46-4: Observer-only (cannot influence routing, gating, or decisions)
def test_observer_only_no_routing_influence():
    """
    Invariant: INV-P46-4
    Proves that P46 output is observer-only and cannot influence
    routing, gating, or decision phases.

    The output must have observer_only=True enforced, and the integration
    must only write to its designated field without modifying other state.
    """
    # Create a mock context with existing state
    ctx = MockContext()
    ctx.p45_multi_trajectory_stability = MockMultiTrajectoryStabilityField(
        stability_index=0.80,
        volatility_index=0.10,
        convergence_index=0.85,
        trajectory_count=2,
        stability_band="stable",
    )
    ctx.p45_historical_snapshots = [
        MockMultiTrajectoryStabilityField(
            stability_index=0.75,
            volatility_index=0.12,
            convergence_index=0.80,
            trajectory_count=2,
            stability_band="stable",
        ),
    ]

    # Capture pre-existing state
    pre_p45 = ctx.p45_multi_trajectory_stability
    pre_historical = ctx.p45_historical_snapshots

    # Run P46
    result = maybe_run_p46(ctx)

    # Verify: observer_only is True (enforced)
    assert result is not None
    assert result.observer_only is True

    # Verify: P46 did NOT modify any input state
    assert ctx.p45_multi_trajectory_stability is pre_p45
    assert ctx.p45_historical_snapshots is pre_historical

    # Verify: Output attached only to designated field
    assert ctx.p46_trajectory_convergence is result

    # Verify: Cannot create with observer_only=False
    with pytest.raises(ValueError, match="observer_only must be True"):
        TrajectoryFieldConvergenceReport(
            convergence_score=0.85,
            convergence_trend="increasing",
            field_state="converging",
            sample_window=2,
            observer_only=False,  # type: ignore
        )


# Proves INV-P46-5: Absence-safe (missing inputs -> no output)
def test_absence_safe_missing_inputs():
    """
    Invariant: INV-P46-5
    Proves that P46 returns None (no output) when required inputs are missing,
    without fabricating data or raising errors.
    """
    p45_stability = MockMultiTrajectoryStabilityField(
        stability_index=0.75,
        volatility_index=0.15,
        convergence_index=0.80,
        trajectory_count=3,
        stability_band="stable",
    )

    # Test 1: Missing P45 stability field
    result_no_p45 = run_p46_directly(
        p45_stability_field=None,
        p45_historical_snapshots=None,
    )
    assert result_no_p45 is None

    # Test 2: P45 present but with no convergence_index
    @dataclass
    class BrokenP45:
        stability_index: float = 0.75
        volatility_index: float = 0.15
        # Missing convergence_index

    result_broken_p45 = run_p46_directly(
        p45_stability_field=BrokenP45(),
        p45_historical_snapshots=None,
    )
    assert result_broken_p45 is None

    # Test 3: P45 present, historical is empty list (valid, not absence)
    result_empty_history = run_p46_directly(
        p45_stability_field=p45_stability,
        p45_historical_snapshots=[],
    )
    # Empty history is valid - should return result with trend="flat"
    assert result_empty_history is not None
    assert result_empty_history.convergence_trend == "flat"
    assert result_empty_history.sample_window == 1

    # Test 4: Context-based integration with missing P45
    ctx_missing_p45 = MockContext()
    # p45_multi_trajectory_stability is None by default
    result_ctx_no_p45 = maybe_run_p46(ctx_missing_p45)
    assert result_ctx_no_p45 is None

    # Verify: No exceptions raised, clean None returns
    # (absence-safe means graceful degradation, not errors)
