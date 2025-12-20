"""
Phase 49: Temporal Stability Index Tests

TESTING POLICY (from TESTING.md):
    - Every test MUST be mapped to exactly one invariant
    - One test -> one invariant
    - If a test cannot map to an invariant -> delete it
    - No math micro-tests, no boundary theatrics, no redundancy

INVARIANTS:
    INV-P49-1: Observer-only (no downstream influence)
    INV-P49-2: Deterministic (pure math, no state)
    INV-P49-3: No authority (cannot gate, block, or trigger)
    INV-P49-4: Absence-safe (missing inputs -> None)
    INV-P49-5: Temporal meaning only (index reflects time stability, not intent or emotion)
"""

from dataclasses import dataclass

import pytest

from symbolu.mechanical.pipeline.p49_temporal_stability import (
    run_p49_directly,
    maybe_run_p49,
    TemporalStabilityIndex,
    VALID_STABILITY_BANDS,
)


# =============================================================================
# Mock Objects for Testing
# =============================================================================


@dataclass
class MockPhase38TemporalForecast:
    """Mock P38 Phase38TemporalForecast for testing."""

    forecast_score: float
    forecast_trend: str = "stable"
    confidence: float = 0.8
    horizon: str = "near"
    observer_only: bool = True


@dataclass
class MockCrossHorizonAlignment:
    """Mock P40 CrossHorizonAlignment for testing."""

    alignment_score: float
    alignment_band: str = "aligned"
    divergence_index: float = 0.1
    dominant_horizon: str = "none"
    observer_only: bool = True


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
        self.p38_temporal_forecast = None
        self.p40_cross_horizon_alignment = None
        self.p45_multi_trajectory_stability = None
        self.p46_trajectory_convergence = None
        self.p47_unified_trajectory_scenario = None
        self.p49_temporal_stability = None
        self._p49_disabled = False


# =============================================================================
# INVARIANT TESTS (exactly one test per invariant)
# =============================================================================


# Proves INV-P49-1: Observer-only (no downstream influence)
def test_observer_only_no_downstream_influence():
    """
    Invariant: INV-P49-1
    Proves that P49 output is observer-only and cannot influence
    any downstream phase, routing, gating, or decisions.

    The output must have observer_only=True enforced, and the integration
    must only write to its designated field without modifying other state.
    """
    # Create a mock context with existing state
    ctx = MockContext()
    ctx.p38_temporal_forecast = MockPhase38TemporalForecast(forecast_score=0.75)
    ctx.p40_cross_horizon_alignment = MockCrossHorizonAlignment(alignment_score=0.70)
    ctx.p45_multi_trajectory_stability = MockMultiTrajectoryStabilityField(
        stability_index=0.80
    )
    ctx.p46_trajectory_convergence = MockTrajectoryFieldConvergenceReport(
        convergence_score=0.72
    )
    ctx.p47_unified_trajectory_scenario = MockUnifiedTrajectoryScenarioReport(
        alignment_score=0.68
    )

    # Capture pre-existing state references
    pre_p38 = ctx.p38_temporal_forecast
    pre_p40 = ctx.p40_cross_horizon_alignment
    pre_p45 = ctx.p45_multi_trajectory_stability
    pre_p46 = ctx.p46_trajectory_convergence
    pre_p47 = ctx.p47_unified_trajectory_scenario

    # Run P49
    result = maybe_run_p49(ctx)

    # Verify: observer_only is True (enforced)
    assert result is not None
    assert result.observer_only is True

    # Verify: P49 did NOT modify any input state
    assert ctx.p38_temporal_forecast is pre_p38
    assert ctx.p40_cross_horizon_alignment is pre_p40
    assert ctx.p45_multi_trajectory_stability is pre_p45
    assert ctx.p46_trajectory_convergence is pre_p46
    assert ctx.p47_unified_trajectory_scenario is pre_p47

    # Verify: Output attached only to designated field
    assert ctx.p49_temporal_stability is result

    # Verify: Cannot create with observer_only=False
    with pytest.raises(ValueError, match="observer_only must be True"):
        TemporalStabilityIndex(
            temporal_stability_index=0.75,
            stability_band="stable",
            observer_only=False,  # type: ignore
        )


# Proves INV-P49-2: Deterministic (pure math, no state)
def test_deterministic_pure_math():
    """
    Invariant: INV-P49-2
    Proves that P49 produces identical outputs for identical inputs,
    demonstrating deterministic computation with no randomness,
    no learning, no heuristics, and no internal state.
    """
    p38_forecast = MockPhase38TemporalForecast(forecast_score=0.65)
    p40_alignment = MockCrossHorizonAlignment(alignment_score=0.60)
    p45_stability = MockMultiTrajectoryStabilityField(stability_index=0.70)
    p46_convergence = MockTrajectoryFieldConvergenceReport(convergence_score=0.55)
    p47_synthesis = MockUnifiedTrajectoryScenarioReport(alignment_score=0.62)

    # Run computation multiple times with identical inputs
    results = []
    for _ in range(5):
        result = run_p49_directly(
            p38_temporal_forecast=p38_forecast,
            p40_cross_horizon_alignment=p40_alignment,
            p45_multi_trajectory_stability=p45_stability,
            p46_trajectory_convergence=p46_convergence,
            p47_unified_trajectory_scenario=p47_synthesis,
        )
        results.append(result)

    # Verify: All results are identical (deterministic)
    first_result = results[0]
    for result in results[1:]:
        assert result.temporal_stability_index == first_result.temporal_stability_index
        assert result.stability_band == first_result.stability_band
        assert result.observer_only == first_result.observer_only


# Proves INV-P49-3: No authority (cannot gate, block, or trigger)
def test_no_authority_cannot_gate_or_trigger():
    """
    Invariant: INV-P49-3
    Proves that P49 output has no authority to gate, block, or trigger
    any system behavior. It produces only observational data.

    The output contains no action fields, no gating flags, no trigger signals.
    """
    p38_forecast = MockPhase38TemporalForecast(forecast_score=0.80)
    p40_alignment = MockCrossHorizonAlignment(alignment_score=0.75)
    p45_stability = MockMultiTrajectoryStabilityField(stability_index=0.85)
    p46_convergence = MockTrajectoryFieldConvergenceReport(convergence_score=0.78)
    p47_synthesis = MockUnifiedTrajectoryScenarioReport(alignment_score=0.72)

    result = run_p49_directly(
        p38_temporal_forecast=p38_forecast,
        p40_cross_horizon_alignment=p40_alignment,
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=p46_convergence,
        p47_unified_trajectory_scenario=p47_synthesis,
    )

    assert result is not None

    # Verify: No authority/action attributes exist
    assert not hasattr(result, "gate")
    assert not hasattr(result, "block")
    assert not hasattr(result, "trigger")
    assert not hasattr(result, "action")
    assert not hasattr(result, "decision")
    assert not hasattr(result, "command")
    assert not hasattr(result, "eligibility")
    assert not hasattr(result, "policy")
    assert not hasattr(result, "governance")

    # Verify: Output is purely observational
    assert result.stability_band in VALID_STABILITY_BANDS
    assert 0.0 <= result.temporal_stability_index <= 1.0


# Proves INV-P49-4: Absence-safe (missing inputs -> None)
def test_absence_safe_missing_inputs():
    """
    Invariant: INV-P49-4
    Proves that P49 returns None (no output) when any required input is missing,
    without fabricating data or raising errors.
    """
    p38_forecast = MockPhase38TemporalForecast(forecast_score=0.80)
    p40_alignment = MockCrossHorizonAlignment(alignment_score=0.75)
    p45_stability = MockMultiTrajectoryStabilityField(stability_index=0.85)
    p46_convergence = MockTrajectoryFieldConvergenceReport(convergence_score=0.78)
    p47_synthesis = MockUnifiedTrajectoryScenarioReport(alignment_score=0.72)

    # Test 1: Missing P38
    result_no_p38 = run_p49_directly(
        p38_temporal_forecast=None,
        p40_cross_horizon_alignment=p40_alignment,
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=p46_convergence,
        p47_unified_trajectory_scenario=p47_synthesis,
    )
    assert result_no_p38 is None

    # Test 2: Missing P40
    result_no_p40 = run_p49_directly(
        p38_temporal_forecast=p38_forecast,
        p40_cross_horizon_alignment=None,
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=p46_convergence,
        p47_unified_trajectory_scenario=p47_synthesis,
    )
    assert result_no_p40 is None

    # Test 3: Missing P45
    result_no_p45 = run_p49_directly(
        p38_temporal_forecast=p38_forecast,
        p40_cross_horizon_alignment=p40_alignment,
        p45_multi_trajectory_stability=None,
        p46_trajectory_convergence=p46_convergence,
        p47_unified_trajectory_scenario=p47_synthesis,
    )
    assert result_no_p45 is None

    # Test 4: Missing P46
    result_no_p46 = run_p49_directly(
        p38_temporal_forecast=p38_forecast,
        p40_cross_horizon_alignment=p40_alignment,
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=None,
        p47_unified_trajectory_scenario=p47_synthesis,
    )
    assert result_no_p46 is None

    # Test 5: Missing P47
    result_no_p47 = run_p49_directly(
        p38_temporal_forecast=p38_forecast,
        p40_cross_horizon_alignment=p40_alignment,
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=p46_convergence,
        p47_unified_trajectory_scenario=None,
    )
    assert result_no_p47 is None

    # Test 6: P38 present but missing forecast_score
    @dataclass
    class BrokenP38:
        forecast_trend: str = "stable"
        # Missing forecast_score

    result_broken_p38 = run_p49_directly(
        p38_temporal_forecast=BrokenP38(),
        p40_cross_horizon_alignment=p40_alignment,
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=p46_convergence,
        p47_unified_trajectory_scenario=p47_synthesis,
    )
    assert result_broken_p38 is None

    # Test 7: Context-based integration with missing inputs
    ctx_missing = MockContext()
    # All inputs None by default
    result_ctx_empty = maybe_run_p49(ctx_missing)
    assert result_ctx_empty is None

    # Verify: No exceptions raised, clean None returns
    # (absence-safe means graceful degradation, not errors)


# Proves INV-P49-5: Temporal meaning only (index reflects time stability, not intent or emotion)
def test_temporal_meaning_only():
    """
    Invariant: INV-P49-5
    Proves that P49 output reflects only temporal stability signals,
    not intent, emotion, semantic content, or discourse meaning.

    The output is a synthesis of time-based stability metrics only.
    """
    p38_forecast = MockPhase38TemporalForecast(forecast_score=0.70)
    p40_alignment = MockCrossHorizonAlignment(alignment_score=0.65)
    p45_stability = MockMultiTrajectoryStabilityField(stability_index=0.75)
    p46_convergence = MockTrajectoryFieldConvergenceReport(convergence_score=0.68)
    p47_synthesis = MockUnifiedTrajectoryScenarioReport(alignment_score=0.60)

    result = run_p49_directly(
        p38_temporal_forecast=p38_forecast,
        p40_cross_horizon_alignment=p40_alignment,
        p45_multi_trajectory_stability=p45_stability,
        p46_trajectory_convergence=p46_convergence,
        p47_unified_trajectory_scenario=p47_synthesis,
    )

    assert result is not None

    # Verify: No intent/emotion/semantic attributes exist
    assert not hasattr(result, "intent")
    assert not hasattr(result, "emotion")
    assert not hasattr(result, "sentiment")
    assert not hasattr(result, "discourse")
    assert not hasattr(result, "semantic")
    assert not hasattr(result, "lexical")
    assert not hasattr(result, "meaning")
    assert not hasattr(result, "vrtti")
    assert not hasattr(result, "kosha")
    assert not hasattr(result, "acoustic")

    # Verify: Output reflects temporal stability only
    # The index is derived from temporal-stability signals (P38, P40, P45, P46, P47)
    assert result.stability_band in VALID_STABILITY_BANDS
    assert 0.0 <= result.temporal_stability_index <= 1.0

    # Verify: Debug info shows only temporal inputs
    assert "inputs" in result.debug
    inputs = result.debug["inputs"]
    # All input keys should be temporal stability signals
    temporal_keys = {"F_forecast", "H_horizon", "T_trajectory", "C_convergence", "A_alignment"}
    assert set(inputs.keys()) == temporal_keys
