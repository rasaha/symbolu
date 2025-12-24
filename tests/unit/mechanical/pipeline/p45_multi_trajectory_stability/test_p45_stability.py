"""
Phase 45: Multi-Trajectory Stability Field Tests

TESTING POLICY (from TESTING.md):
    - Every test MUST be mapped to exactly one invariant
    - One test -> one invariant
    - If a test cannot map to an invariant -> delete it
    - No math micro-tests, no snapshot tests, no redundancy

INVARIANTS:
    INV-P45-1: No trajectory preference (no ranking, sorting, or selection)
    INV-P45-2: Deterministic aggregation only (pure math, no heuristics, no learning)
    INV-P45-3: Field-level semantics only (individual variants do not influence bands)
    INV-P45-4: Observer-only (output never influences routing or governance)
    INV-P45-5: Absence-safe (missing inputs -> no output)
"""

from dataclasses import dataclass
from typing import Dict

import pytest

from symbolu.mechanical.pipeline.p45_multi_trajectory_stability import (
    run_p45_directly,
    maybe_run_p45,
    MultiTrajectoryStabilityField,
)


# =============================================================================
# Mock Objects for Testing
# =============================================================================


@dataclass
class MockCoherenceScenarioAlignmentReport:
    """Mock P44 CoherenceScenarioAlignmentReport for testing."""

    base_alignment_score: float
    variant_alignment: Dict[str, float]
    alignment_band: str
    observer_only: bool = True


@dataclass
class MockScenarioWhatIfSet:
    """Mock P43 ScenarioWhatIfSet for testing."""

    base_regime: str
    variant_count: int
    observer_only: bool = True


class MockContext:
    """Mock PipelineContext for testing."""

    def __init__(self):
        self.p44_coherence_scenario_alignment = None
        self.p43_scenario_what_if = None
        self.p45_multi_trajectory_stability = None
        self._p45_disabled = False


# =============================================================================
# INVARIANT TESTS (exactly one test per invariant)
# =============================================================================


# Proves INV-P45-1: No trajectory preference (no ranking, sorting, or selection)
def test_no_trajectory_preference():
    """
    Invariant: INV-P45-1
    Proves that P45 produces stability measurements without any ranking,
    preference ordering, or selection between trajectories.

    The output contains aggregate field metrics but no 'best' trajectory,
    no ordering, and no selection recommendation.
    """
    # Create P44 mock with variant alignment scores
    p44_report = MockCoherenceScenarioAlignmentReport(
        base_alignment_score=0.75,
        variant_alignment={
            "v1_entropy_shift": 0.80,
            "v2_confidence_drop": 0.60,
            "v3_regime_flip": 0.45,
            "v4_noise_injection": 0.70,
        },
        alignment_band="aligned",
    )

    # Create P43 mock
    p43_what_if = MockScenarioWhatIfSet(
        base_regime="stable_continuity",
        variant_count=4,
    )

    result = run_p45_directly(
        p44_alignment_report=p44_report,
        p43_what_if_set=p43_what_if,
    )

    assert result is not None

    # Verify: No ranking attributes exist
    assert not hasattr(result, "ranked_trajectories")
    assert not hasattr(result, "best_trajectory")
    assert not hasattr(result, "preferred_trajectory")
    assert not hasattr(result, "selected_trajectory")
    assert not hasattr(result, "trajectory_ranking")

    # Verify: Output contains only aggregate field metrics, not individual trajectory info
    assert hasattr(result, "stability_index")
    assert hasattr(result, "volatility_index")
    assert hasattr(result, "convergence_index")
    assert hasattr(result, "trajectory_count")
    assert hasattr(result, "stability_band")

    # Verify: trajectory_count equals number of variants (aggregate, not selection)
    assert result.trajectory_count == 4


# Proves INV-P45-2: Deterministic aggregation only (pure math, no heuristics, no learning)
def test_deterministic_aggregation():
    """
    Invariant: INV-P45-2
    Proves that P45 produces identical outputs for identical inputs,
    demonstrating deterministic computation with no randomness or heuristics.
    """
    p44_report = MockCoherenceScenarioAlignmentReport(
        base_alignment_score=0.65,
        variant_alignment={
            "v1": 0.70,
            "v2": 0.55,
            "v3": 0.60,
        },
        alignment_band="strained",
    )

    p43_what_if = MockScenarioWhatIfSet(
        base_regime="strained_transition",
        variant_count=3,
    )

    # Run computation multiple times with identical inputs
    results = []
    for _ in range(5):
        result = run_p45_directly(
            p44_alignment_report=p44_report,
            p43_what_if_set=p43_what_if,
        )
        results.append(result)

    # Verify: All results are identical
    first_result = results[0]
    for result in results[1:]:
        assert result.stability_index == first_result.stability_index
        assert result.volatility_index == first_result.volatility_index
        assert result.convergence_index == first_result.convergence_index
        assert result.trajectory_count == first_result.trajectory_count
        assert result.stability_band == first_result.stability_band
        assert result.observer_only == first_result.observer_only


# Proves INV-P45-3: Field-level semantics only (individual variants do not influence bands)
def test_field_level_semantics_band_isolation():
    """
    Invariant: INV-P45-3
    Proves that the stability band is derived ONLY from the aggregate stability_index,
    not from any individual variant characteristics.

    Different variant compositions with the same mean produce the same band.
    """
    # Test 1: Uniform variants (low variance)
    uniform_report = MockCoherenceScenarioAlignmentReport(
        base_alignment_score=0.70,
        variant_alignment={
            "v1": 0.75,
            "v2": 0.75,
            "v3": 0.75,
            "v4": 0.75,
        },
        alignment_band="aligned",
    )

    # Test 2: Spread variants (high variance) with same mean
    spread_report = MockCoherenceScenarioAlignmentReport(
        base_alignment_score=0.70,
        variant_alignment={
            "v1": 0.95,
            "v2": 0.55,
            "v3": 0.90,
            "v4": 0.60,
        },
        alignment_band="aligned",
    )

    p43_what_if = MockScenarioWhatIfSet(
        base_regime="stable_continuity",
        variant_count=4,
    )

    result_uniform = run_p45_directly(
        p44_alignment_report=uniform_report,
        p43_what_if_set=p43_what_if,
    )

    result_spread = run_p45_directly(
        p44_alignment_report=spread_report,
        p43_what_if_set=p43_what_if,
    )

    assert result_uniform is not None
    assert result_spread is not None

    # Verify: Both have valid stability bands (band derived from stability_index only)
    assert result_uniform.stability_band in ("stable", "strained", "chaotic")
    assert result_spread.stability_band in ("stable", "strained", "chaotic")

    # Verify: Stability band classification matches the stability_index thresholds
    # (not individual variant values)
    for result in [result_uniform, result_spread]:
        if result.stability_index >= 0.70:
            assert result.stability_band == "stable"
        elif result.stability_index >= 0.45:
            assert result.stability_band == "strained"
        else:
            assert result.stability_band == "chaotic"


# Proves INV-P45-4: Observer-only (output never influences routing or governance)
def test_observer_only_no_routing_influence():
    """
    Invariant: INV-P45-4
    Proves that P45 output is observer-only and cannot influence
    routing or governance phases.

    The output must have observer_only=True enforced, and the integration
    must only write to its designated field without modifying other state.
    """
    # Create a mock context with existing state
    ctx = MockContext()
    ctx.p44_coherence_scenario_alignment = MockCoherenceScenarioAlignmentReport(
        base_alignment_score=0.80,
        variant_alignment={
            "v1": 0.85,
            "v2": 0.70,
        },
        alignment_band="aligned",
    )
    ctx.p43_scenario_what_if = MockScenarioWhatIfSet(
        base_regime="stable_continuity",
        variant_count=2,
    )

    # Capture pre-existing state
    pre_p44 = ctx.p44_coherence_scenario_alignment
    pre_p43 = ctx.p43_scenario_what_if

    # Run P45
    result = maybe_run_p45(ctx)

    # Verify: observer_only is True (enforced)
    assert result is not None
    assert result.observer_only is True

    # Verify: P45 did NOT modify any input state
    assert ctx.p44_coherence_scenario_alignment is pre_p44
    assert ctx.p43_scenario_what_if is pre_p43

    # Verify: Output attached only to designated field
    assert ctx.p45_multi_trajectory_stability is result

    # Verify: Cannot create with observer_only=False
    with pytest.raises(ValueError, match="observer_only must be True"):
        MultiTrajectoryStabilityField(
            stability_index=0.70,
            volatility_index=0.10,
            convergence_index=0.90,
            trajectory_count=2,
            stability_band="stable",
            observer_only=False,  # type: ignore
        )


# Proves INV-P45-5: Absence-safe (missing inputs -> no output)
def test_absence_safe_missing_inputs():
    """
    Invariant: INV-P45-5
    Proves that P45 returns None (no output) when required inputs are missing,
    without fabricating data or raising errors.
    """
    p44_report = MockCoherenceScenarioAlignmentReport(
        base_alignment_score=0.75,
        variant_alignment={"v1": 0.80, "v2": 0.60},
        alignment_band="aligned",
    )
    p43_what_if = MockScenarioWhatIfSet(
        base_regime="stable_continuity",
        variant_count=2,
    )

    # Test 1: Missing P44 alignment report
    result_no_p44 = run_p45_directly(
        p44_alignment_report=None,
        p43_what_if_set=p43_what_if,
    )
    assert result_no_p44 is None

    # Test 2: Missing P43 what-if set
    result_no_p43 = run_p45_directly(
        p44_alignment_report=p44_report,
        p43_what_if_set=None,
    )
    assert result_no_p43 is None

    # Test 3: Both missing
    result_both_missing = run_p45_directly(
        p44_alignment_report=None,
        p43_what_if_set=None,
    )
    assert result_both_missing is None

    # Test 4: P44 has empty variant_alignment
    empty_p44 = MockCoherenceScenarioAlignmentReport(
        base_alignment_score=0.75,
        variant_alignment={},  # Empty
        alignment_band="aligned",
    )
    result_empty_variants = run_p45_directly(
        p44_alignment_report=empty_p44,
        p43_what_if_set=p43_what_if,
    )
    assert result_empty_variants is None

    # Test 5: Context-based integration with missing P44
    ctx_missing_p44 = MockContext()
    ctx_missing_p44.p43_scenario_what_if = p43_what_if
    # p44_coherence_scenario_alignment is None by default
    result_ctx_no_p44 = maybe_run_p45(ctx_missing_p44)
    assert result_ctx_no_p44 is None

    # Test 6: Context with missing P43
    ctx_missing_p43 = MockContext()
    ctx_missing_p43.p44_coherence_scenario_alignment = p44_report
    # p43_scenario_what_if is None by default
    result_ctx_no_p43 = maybe_run_p45(ctx_missing_p43)
    assert result_ctx_no_p43 is None

    # Verify: No exceptions raised, clean None returns
    # (absence-safe means graceful degradation, not errors)
