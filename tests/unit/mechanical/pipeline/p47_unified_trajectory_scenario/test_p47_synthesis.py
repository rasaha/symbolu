"""
Phase 47: Unified Trajectory-Scenario Synthesis Tests

TESTING POLICY (from TESTING.md):
    - Every test MUST be mapped to exactly one invariant
    - One test -> one invariant
    - If a test cannot map to an invariant -> delete it
    - No math micro-tests, no boundary theatrics, no redundancy

INVARIANTS:
    INV-P47-1: No prediction (no future selection or ranking)
    INV-P47-2: Symmetric synthesis (scenario and trajectory treated as peers)
    INV-P47-3: Deterministic math only (pure weighted aggregation)
    INV-P47-4: Observer-only (cannot influence any authority phase)
    INV-P47-5: Absence-safe (missing inputs -> no output)
"""

from dataclasses import dataclass

import pytest

from symbolu.mechanical.pipeline.p47_unified_trajectory_scenario import (
    run_p47_directly,
    maybe_run_p47,
    UnifiedTrajectoryScenarioReport,
)


# =============================================================================
# Mock Objects for Testing
# =============================================================================


@dataclass
class MockScenarioFusionField:
    """Mock P42 ScenarioFusionField for testing."""

    dominant_regime: str
    regime_distribution: dict
    fusion_confidence: float
    regime_entropy: float
    observer_only: bool = True


@dataclass
class MockMultiTrajectoryStabilityField:
    """Mock P45 MultiTrajectoryStabilityField for testing."""

    stability_index: float
    volatility_index: float
    convergence_index: float
    trajectory_count: int
    stability_band: str
    observer_only: bool = True


@dataclass
class MockTrajectoryFieldConvergenceReport:
    """Mock P46 TrajectoryFieldConvergenceReport for testing."""

    convergence_score: float
    convergence_trend: str
    field_state: str
    sample_window: int
    observer_only: bool = True


class MockContext:
    """Mock PipelineContext for testing."""

    def __init__(self):
        self.p42_scenario_fusion_field = None
        self.p45_multi_trajectory_stability = None
        self.p46_trajectory_convergence = None
        self.p47_unified_trajectory_scenario = None
        self._p47_disabled = False


# =============================================================================
# INVARIANT TESTS (exactly one test per invariant)
# =============================================================================


# Proves INV-P47-1: No prediction (no future selection or ranking)
def test_no_prediction():
    """
    Invariant: INV-P47-1
    Proves that P47 produces synthesis measurements without any prediction,
    future selection, ranking, or comparison between individual futures.

    The output contains only aggregate alignment metrics - no 'best' future,
    no outcome prediction, no trajectory selection.
    """
    # Create mock inputs
    p42_fusion = MockScenarioFusionField(
        dominant_regime="stable_continuity",
        regime_distribution={"stable_continuity": 0.8},
        fusion_confidence=0.75,
        regime_entropy=0.20,
    )

    p45_stability = MockMultiTrajectoryStabilityField(
        stability_index=0.80,
        volatility_index=0.15,
        convergence_index=0.85,
        trajectory_count=4,
        stability_band="stable",
    )

    p46_convergence = MockTrajectoryFieldConvergenceReport(
        convergence_score=0.70,
        convergence_trend="increasing",
        field_state="converging",
        sample_window=3,
    )

    result = run_p47_directly(
        p42_scenario_fusion=p42_fusion,
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=p46_convergence,
    )

    assert result is not None

    # Verify: No prediction attributes exist
    assert not hasattr(result, "predicted_outcome")
    assert not hasattr(result, "selected_future")
    assert not hasattr(result, "best_trajectory")
    assert not hasattr(result, "recommended_scenario")
    assert not hasattr(result, "future_ranking")
    assert not hasattr(result, "outcome_probability")

    # Verify: Output contains only structural alignment metrics
    assert hasattr(result, "alignment_score")
    assert hasattr(result, "alignment_band")
    assert hasattr(result, "dominant_factor")

    # Verify: No selection or ranking was performed
    # dominant_factor is a structural comparison, not a prediction
    assert result.dominant_factor in ("trajectory", "scenario", "balanced")


# Proves INV-P47-2: Symmetric synthesis (scenario and trajectory treated as peers)
def test_symmetric_synthesis():
    """
    Invariant: INV-P47-2
    Proves that P47 treats scenario coherence (S) and trajectory stability (T)
    symmetrically in the alignment formula.

    Both receive equal weight (0.40 each) in the alignment score computation.
    The dominant_factor detection uses symmetric thresholds.
    """
    # Test 1: When T and S are equal, result should be "balanced"
    p42_fusion = MockScenarioFusionField(
        dominant_regime="stable_continuity",
        regime_distribution={"stable_continuity": 0.8},
        fusion_confidence=0.70,  # S = 0.70
        regime_entropy=0.20,
    )

    p45_stability = MockMultiTrajectoryStabilityField(
        stability_index=0.70,  # T = 0.70 (equal to S)
        volatility_index=0.15,
        convergence_index=0.80,
        trajectory_count=3,
        stability_band="stable",
    )

    p46_convergence = MockTrajectoryFieldConvergenceReport(
        convergence_score=0.60,
        convergence_trend="flat",
        field_state="neutral",
        sample_window=2,
    )

    result_equal = run_p47_directly(
        p42_scenario_fusion=p42_fusion,
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=p46_convergence,
    )

    assert result_equal is not None
    # With T = S, dominant_factor must be "balanced" (symmetric treatment)
    assert result_equal.dominant_factor == "balanced"

    # Test 2: Swapping T and S values produces mirror dominant_factor
    # T = 0.85, S = 0.60 -> trajectory dominates
    p42_low = MockScenarioFusionField(
        dominant_regime="strained_transition",
        regime_distribution={"strained_transition": 0.7},
        fusion_confidence=0.60,  # S = 0.60
        regime_entropy=0.30,
    )

    p45_high = MockMultiTrajectoryStabilityField(
        stability_index=0.85,  # T = 0.85 (T > S + 0.10)
        volatility_index=0.10,
        convergence_index=0.80,
        trajectory_count=3,
        stability_band="stable",
    )

    result_t_high = run_p47_directly(
        p42_scenario_fusion=p42_low,
        p45_multi_trajectory_stability=p45_high,
        p46_trajectory_convergence=p46_convergence,
    )

    # T = 0.60, S = 0.85 -> scenario dominates (swapped)
    p42_high = MockScenarioFusionField(
        dominant_regime="stable_continuity",
        regime_distribution={"stable_continuity": 0.8},
        fusion_confidence=0.85,  # S = 0.85
        regime_entropy=0.15,
    )

    p45_low = MockMultiTrajectoryStabilityField(
        stability_index=0.60,  # T = 0.60 (S > T + 0.10)
        volatility_index=0.20,
        convergence_index=0.75,
        trajectory_count=3,
        stability_band="strained",
    )

    result_s_high = run_p47_directly(
        p42_scenario_fusion=p42_high,
        p45_multi_trajectory_stability=p45_low,
        p46_trajectory_convergence=p46_convergence,
    )

    # Verify symmetric behavior: swapping produces opposite dominant_factor
    assert result_t_high.dominant_factor == "trajectory"
    assert result_s_high.dominant_factor == "scenario"


# Proves INV-P47-3: Deterministic math only (pure weighted aggregation)
def test_deterministic_math():
    """
    Invariant: INV-P47-3
    Proves that P47 produces identical outputs for identical inputs,
    demonstrating deterministic computation with no randomness,
    no learning, and no heuristics.
    """
    p42_fusion = MockScenarioFusionField(
        dominant_regime="stable_continuity",
        regime_distribution={"stable_continuity": 0.75},
        fusion_confidence=0.72,
        regime_entropy=0.25,
    )

    p45_stability = MockMultiTrajectoryStabilityField(
        stability_index=0.68,
        volatility_index=0.18,
        convergence_index=0.75,
        trajectory_count=4,
        stability_band="strained",
    )

    p46_convergence = MockTrajectoryFieldConvergenceReport(
        convergence_score=0.65,
        convergence_trend="increasing",
        field_state="neutral",
        sample_window=3,
    )

    # Run computation multiple times with identical inputs
    results = []
    for _ in range(5):
        result = run_p47_directly(
            p42_scenario_fusion=p42_fusion,
            p45_multi_trajectory_stability=p45_stability,
            p46_trajectory_convergence=p46_convergence,
        )
        results.append(result)

    # Verify: All results are identical (deterministic)
    first_result = results[0]
    for result in results[1:]:
        assert result.alignment_score == first_result.alignment_score
        assert result.alignment_band == first_result.alignment_band
        assert result.dominant_factor == first_result.dominant_factor
        assert result.observer_only == first_result.observer_only


# Proves INV-P47-4: Observer-only (cannot influence any authority phase)
def test_observer_only_no_authority_influence():
    """
    Invariant: INV-P47-4
    Proves that P47 output is observer-only and cannot influence
    any authority phase, routing, gating, or decisions.

    The output must have observer_only=True enforced, and the integration
    must only write to its designated field without modifying other state.
    """
    # Create a mock context with existing state
    ctx = MockContext()
    ctx.p42_scenario_fusion_field = MockScenarioFusionField(
        dominant_regime="stable_continuity",
        regime_distribution={"stable_continuity": 0.8},
        fusion_confidence=0.80,
        regime_entropy=0.15,
    )
    ctx.p45_multi_trajectory_stability = MockMultiTrajectoryStabilityField(
        stability_index=0.75,
        volatility_index=0.12,
        convergence_index=0.80,
        trajectory_count=3,
        stability_band="stable",
    )
    ctx.p46_trajectory_convergence = MockTrajectoryFieldConvergenceReport(
        convergence_score=0.70,
        convergence_trend="flat",
        field_state="converging",
        sample_window=2,
    )

    # Capture pre-existing state references
    pre_p42 = ctx.p42_scenario_fusion_field
    pre_p45 = ctx.p45_multi_trajectory_stability
    pre_p46 = ctx.p46_trajectory_convergence

    # Run P47
    result = maybe_run_p47(ctx)

    # Verify: observer_only is True (enforced)
    assert result is not None
    assert result.observer_only is True

    # Verify: P47 did NOT modify any input state
    assert ctx.p42_scenario_fusion_field is pre_p42
    assert ctx.p45_multi_trajectory_stability is pre_p45
    assert ctx.p46_trajectory_convergence is pre_p46

    # Verify: Output attached only to designated field
    assert ctx.p47_unified_trajectory_scenario is result

    # Verify: Cannot create with observer_only=False
    with pytest.raises(ValueError, match="observer_only must be True"):
        UnifiedTrajectoryScenarioReport(
            alignment_score=0.75,
            alignment_band="aligned",
            dominant_factor="balanced",
            observer_only=False,  # type: ignore
        )


# Proves INV-P47-5: Absence-safe (missing inputs -> no output)
def test_absence_safe_missing_inputs():
    """
    Invariant: INV-P47-5
    Proves that P47 returns None (no output) when any required input is missing,
    without fabricating data or raising errors.
    """
    p42_fusion = MockScenarioFusionField(
        dominant_regime="stable_continuity",
        regime_distribution={"stable_continuity": 0.8},
        fusion_confidence=0.75,
        regime_entropy=0.20,
    )

    p45_stability = MockMultiTrajectoryStabilityField(
        stability_index=0.80,
        volatility_index=0.15,
        convergence_index=0.85,
        trajectory_count=3,
        stability_band="stable",
    )

    p46_convergence = MockTrajectoryFieldConvergenceReport(
        convergence_score=0.70,
        convergence_trend="increasing",
        field_state="converging",
        sample_window=2,
    )

    # Test 1: Missing P42
    result_no_p42 = run_p47_directly(
        p42_scenario_fusion=None,
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=p46_convergence,
    )
    assert result_no_p42 is None

    # Test 2: Missing P45
    result_no_p45 = run_p47_directly(
        p42_scenario_fusion=p42_fusion,
        p45_multi_trajectory_stability=None,
        p46_trajectory_convergence=p46_convergence,
    )
    assert result_no_p45 is None

    # Test 3: Missing P46
    result_no_p46 = run_p47_directly(
        p42_scenario_fusion=p42_fusion,
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=None,
    )
    assert result_no_p46 is None

    # Test 4: P42 present but missing fusion_confidence
    @dataclass
    class BrokenP42:
        dominant_regime: str = "stable_continuity"
        regime_distribution: dict = None
        # Missing fusion_confidence

    result_broken_p42 = run_p47_directly(
        p42_scenario_fusion=BrokenP42(),
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=p46_convergence,
    )
    assert result_broken_p42 is None

    # Test 5: Context-based integration with missing inputs
    ctx_missing = MockContext()
    # All inputs None by default
    result_ctx_empty = maybe_run_p47(ctx_missing)
    assert result_ctx_empty is None

    # Verify: No exceptions raised, clean None returns
    # (absence-safe means graceful degradation, not errors)
