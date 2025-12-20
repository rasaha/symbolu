"""
Phase 48: Macro-Stability Regime Analyzer Tests

TESTING POLICY (from TESTING.md):
    - Every test MUST be mapped to exactly one invariant
    - One test -> one invariant
    - If a test cannot map to an invariant -> delete it
    - No math micro-tests, no boundary theatrics, no redundancy

INVARIANTS:
    INV-P48-1: Classification-only (no numeric synthesis beyond confidence)
    INV-P48-2: No future selection (no path choice, no ranking)
    INV-P48-3: Deterministic (pure rule + arithmetic)
    INV-P48-4: Observer-only (cannot influence authority layers)
    INV-P48-5: Absence-safe (missing input -> None)
"""

from dataclasses import dataclass

import pytest

from symbolu.mechanical.pipeline.p48_macro_stability import (
    run_p48_directly,
    maybe_run_p48,
    MacroStabilityRegimeReport,
    VALID_MACRO_REGIMES,
)


# =============================================================================
# Mock Objects for Testing
# =============================================================================


@dataclass
class MockMultiTrajectoryStabilityField:
    """Mock P45 MultiTrajectoryStabilityField for testing."""

    stability_index: float
    volatility_index: float = 0.15
    convergence_index: float = 0.75
    trajectory_count: int = 3
    stability_band: str = "stable"
    observer_only: bool = True


@dataclass
class MockTrajectoryFieldConvergenceReport:
    """Mock P46 TrajectoryFieldConvergenceReport for testing."""

    convergence_score: float
    convergence_trend: str = "flat"
    field_state: str = "neutral"
    sample_window: int = 2
    observer_only: bool = True


@dataclass
class MockUnifiedTrajectoryScenarioReport:
    """Mock P47 UnifiedTrajectoryScenarioReport for testing."""

    alignment_score: float
    alignment_band: str = "aligned"
    dominant_factor: str = "balanced"
    observer_only: bool = True


class MockContext:
    """Mock PipelineContext for testing."""

    def __init__(self):
        self.p45_multi_trajectory_stability = None
        self.p46_trajectory_convergence = None
        self.p47_unified_trajectory_scenario = None
        self.p48_macro_stability = None
        self._p48_disabled = False


# =============================================================================
# INVARIANT TESTS (exactly one test per invariant)
# =============================================================================


# Proves INV-P48-1: Classification-only (no numeric synthesis beyond confidence)
def test_classification_only():
    """
    Invariant: INV-P48-1
    Proves that P48 produces only regime classification with confidence,
    not numeric synthesis, aggregation, or computed scores.

    The output contains:
    - macro_regime: a categorical classification
    - confidence: a derived measure of clarity (not a synthesized score)
    - No composite scores, no weighted averages, no fusion metrics
    """
    # Create mock inputs for stable_convergent regime
    p45_stability = MockMultiTrajectoryStabilityField(stability_index=0.80)
    p46_convergence = MockTrajectoryFieldConvergenceReport(convergence_score=0.70)
    p47_synthesis = MockUnifiedTrajectoryScenarioReport(alignment_score=0.75)

    result = run_p48_directly(
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=p46_convergence,
        p47_unified_trajectory_scenario=p47_synthesis,
    )

    assert result is not None

    # Verify: Output is a categorical classification, not a score
    assert result.macro_regime in VALID_MACRO_REGIMES
    assert result.macro_regime == "stable_convergent"

    # Verify: No synthesized scores exist
    assert not hasattr(result, "synthesis_score")
    assert not hasattr(result, "composite_metric")
    assert not hasattr(result, "weighted_average")
    assert not hasattr(result, "fusion_score")
    assert not hasattr(result, "aggregate_score")

    # Verify: confidence is present but derived from distance-from-ambiguity
    assert 0.0 <= result.confidence <= 1.0


# Proves INV-P48-2: No future selection (no path choice, no ranking)
def test_no_future_selection():
    """
    Invariant: INV-P48-2
    Proves that P48 performs regime classification without selecting,
    ranking, or preferring any future path or trajectory.

    The output characterizes the current state regime only.
    """
    p45_stability = MockMultiTrajectoryStabilityField(stability_index=0.75)
    p46_convergence = MockTrajectoryFieldConvergenceReport(convergence_score=0.68)
    p47_synthesis = MockUnifiedTrajectoryScenarioReport(alignment_score=0.70)

    result = run_p48_directly(
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=p46_convergence,
        p47_unified_trajectory_scenario=p47_synthesis,
    )

    assert result is not None

    # Verify: No selection attributes exist
    assert not hasattr(result, "selected_path")
    assert not hasattr(result, "best_trajectory")
    assert not hasattr(result, "recommended_future")
    assert not hasattr(result, "path_ranking")
    assert not hasattr(result, "trajectory_choice")
    assert not hasattr(result, "future_selection")

    # Verify: Output is purely observational classification
    assert result.macro_regime in VALID_MACRO_REGIMES

    # Verify: No ranking or ordering information
    assert not hasattr(result, "rank")
    assert not hasattr(result, "priority")
    assert not hasattr(result, "preference")


# Proves INV-P48-3: Deterministic (pure rule + arithmetic)
def test_deterministic():
    """
    Invariant: INV-P48-3
    Proves that P48 produces identical outputs for identical inputs,
    demonstrating deterministic computation with no randomness,
    no learning, and no heuristics.
    """
    p45_stability = MockMultiTrajectoryStabilityField(stability_index=0.65)
    p46_convergence = MockTrajectoryFieldConvergenceReport(convergence_score=0.55)
    p47_synthesis = MockUnifiedTrajectoryScenarioReport(alignment_score=0.60)

    # Run computation multiple times with identical inputs
    results = []
    for _ in range(5):
        result = run_p48_directly(
            p45_multi_trajectory_stability=p45_stability,
            p46_trajectory_convergence=p46_convergence,
            p47_unified_trajectory_scenario=p47_synthesis,
        )
        results.append(result)

    # Verify: All results are identical (deterministic)
    first_result = results[0]
    for result in results[1:]:
        assert result.macro_regime == first_result.macro_regime
        assert result.confidence == first_result.confidence
        assert result.observer_only == first_result.observer_only


# Proves INV-P48-4: Observer-only (cannot influence authority layers)
def test_observer_only_no_authority_influence():
    """
    Invariant: INV-P48-4
    Proves that P48 output is observer-only and cannot influence
    any authority phase, routing, gating, or decisions.

    The output must have observer_only=True enforced, and the integration
    must only write to its designated field without modifying other state.
    """
    # Create a mock context with existing state
    ctx = MockContext()
    ctx.p45_multi_trajectory_stability = MockMultiTrajectoryStabilityField(
        stability_index=0.75
    )
    ctx.p46_trajectory_convergence = MockTrajectoryFieldConvergenceReport(
        convergence_score=0.70
    )
    ctx.p47_unified_trajectory_scenario = MockUnifiedTrajectoryScenarioReport(
        alignment_score=0.68
    )

    # Capture pre-existing state references
    pre_p45 = ctx.p45_multi_trajectory_stability
    pre_p46 = ctx.p46_trajectory_convergence
    pre_p47 = ctx.p47_unified_trajectory_scenario

    # Run P48
    result = maybe_run_p48(ctx)

    # Verify: observer_only is True (enforced)
    assert result is not None
    assert result.observer_only is True

    # Verify: P48 did NOT modify any input state
    assert ctx.p45_multi_trajectory_stability is pre_p45
    assert ctx.p46_trajectory_convergence is pre_p46
    assert ctx.p47_unified_trajectory_scenario is pre_p47

    # Verify: Output attached only to designated field
    assert ctx.p48_macro_stability is result

    # Verify: Cannot create with observer_only=False
    with pytest.raises(ValueError, match="observer_only must be True"):
        MacroStabilityRegimeReport(
            macro_regime="stable_convergent",
            confidence=0.75,
            observer_only=False,  # type: ignore
        )


# Proves INV-P48-5: Absence-safe (missing input -> None)
def test_absence_safe_missing_inputs():
    """
    Invariant: INV-P48-5
    Proves that P48 returns None (no output) when any required input is missing,
    without fabricating data or raising errors.
    """
    p45_stability = MockMultiTrajectoryStabilityField(stability_index=0.80)
    p46_convergence = MockTrajectoryFieldConvergenceReport(convergence_score=0.70)
    p47_synthesis = MockUnifiedTrajectoryScenarioReport(alignment_score=0.75)

    # Test 1: Missing P45
    result_no_p45 = run_p48_directly(
        p45_multi_trajectory_stability=None,
        p46_trajectory_convergence=p46_convergence,
        p47_unified_trajectory_scenario=p47_synthesis,
    )
    assert result_no_p45 is None

    # Test 2: Missing P46
    result_no_p46 = run_p48_directly(
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=None,
        p47_unified_trajectory_scenario=p47_synthesis,
    )
    assert result_no_p46 is None

    # Test 3: Missing P47
    result_no_p47 = run_p48_directly(
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=p46_convergence,
        p47_unified_trajectory_scenario=None,
    )
    assert result_no_p47 is None

    # Test 4: P45 present but missing stability_index
    @dataclass
    class BrokenP45:
        volatility_index: float = 0.15
        # Missing stability_index

    result_broken_p45 = run_p48_directly(
        p45_multi_trajectory_stability=BrokenP45(),
        p46_trajectory_convergence=p46_convergence,
        p47_unified_trajectory_scenario=p47_synthesis,
    )
    assert result_broken_p45 is None

    # Test 5: Context-based integration with missing inputs
    ctx_missing = MockContext()
    # All inputs None by default
    result_ctx_empty = maybe_run_p48(ctx_missing)
    assert result_ctx_empty is None

    # Verify: No exceptions raised, clean None returns
    # (absence-safe means graceful degradation, not errors)
