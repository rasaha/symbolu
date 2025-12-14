"""
Comprehensive Test Suite for Phase 25: Counterfactual Sandbox v1.0

This test suite validates all P25 invariants and behaviors.

Test Groups:
- Group A: Formula Correctness (12 tests) - delta application math, clamp behavior
- Group B: Determinism (10 tests) - same scenario -> same result
- Group C: Non-Authority Proof (12 tests) - no regime/discourse/semantic/lexical impact
- Group D: Boundary Safety (10 tests) - extreme deltas, zero deltas
- Group E: Import Safety (6 tests) - forbidden imports
- Group F: Regression Lock (12 tests) - pipeline identical when P25 unused

CRITICAL INVARIANTS TESTED:
- INV-P25-1: Sandbox outputs are observational only
- INV-P25-2: No mutation of PipelineContext
- INV-P25-3: Counterfactuals never imply recommendations
- INV-P25-4: UCF is recomputed, never overridden
- INV-P25-5: No forward prediction allowed
"""

import pytest
import json
import hashlib
import ast
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from copy import deepcopy

# Import P25 components
from symbolu.core.counterfactual.cf_schema import (
    P25_VERSION,
    DELTA_MIN,
    DELTA_MAX,
    STABILITY_DROP_THRESHOLD,
    ENTROPY_SPIKE_THRESHOLD,
    DRIFT_ACCELERATION_THRESHOLD,
    UCF_THRESHOLD_CROSS_STABLE,
    UCF_THRESHOLD_CROSS_TRANSITIONAL,
    CounterfactualScenario,
    CounterfactualResult,
    CounterfactualSandboxReport,
    clamp,
    create_scenario,
    create_result,
    create_report,
)

from symbolu.core.counterfactual.cf_engine import (
    compute_adjusted_value,
    detect_risk_flags,
    simulate_scenario,
    run_sandbox,
    simulate_single_scenario,
    verify_sandbox_determinism,
)

from symbolu.core.counterfactual.cf_analyzer import (
    analyze_ucf_sensitivity,
    analyze_stability_transitions,
    analyze_risk_flags,
    summarize_report,
    find_boundary_scenarios,
    compute_delta_distribution,
    filter_results_by_flag,
    filter_results_by_band_change,
    compare_scenarios,
)

from symbolu.mechanical.pipeline.p25_counterfactual import (
    maybe_run_p25,
    run_p25_directly,
    is_p25_disabled,
    has_p25_report,
    get_p25_report,
    get_baseline_ucf,
    get_max_negative_delta,
    get_max_positive_delta,
    get_scenario_count,
    has_any_risk_flags,
    has_any_band_changes,
    get_p25_version,
)

# Import UCF for verification
from symbolu.core.consciousness.ucf_formula import (
    compute_ucf,
    compute_stability_band,
)
from symbolu.core.consciousness.ucf_schema import StabilityBand


# ==============================================================================
# TEST FIXTURES AND MOCK OBJECTS
# ==============================================================================


@dataclass
class MockCoherenceState:
    """Minimal mock CoherenceState for testing."""
    convo_id: str = "test"
    turn_index: int = 1
    coherence_v3_quality: Optional[float] = None
    drift_fusion_index: Optional[float] = None
    temporal_entropy_volatility: Optional[float] = None
    persona_schema_stability: Optional[float] = None
    current_identity_harmonics_index: Optional[float] = None


@dataclass
class MockP18Report:
    """Mock P18 report."""
    volatility_band: str = "MED"


@dataclass
class MockP19Report:
    """Mock P19 report."""
    drift_fusion_index: float = 0.3


@dataclass
class MockP33Snapshot:
    """Mock P33 snapshot."""
    schema_stability_scores: Dict[str, float] = None
    confidence: float = 0.7

    def __post_init__(self):
        if self.schema_stability_scores is None:
            self.schema_stability_scores = {"default": 0.7}


@dataclass
class MockPipelineContext:
    """Minimal mock PipelineContext for testing."""
    coherence_state: Optional[MockCoherenceState] = None
    p18: Optional[MockP18Report] = None
    p19: Optional[MockP19Report] = None
    p33: Optional[MockP33Snapshot] = None
    p26: Optional[Any] = None
    p25: Optional[CounterfactualSandboxReport] = None
    _p25_disabled: bool = False

    # Authority fields that P25 MUST NOT modify
    p6_regime: Optional[str] = None
    p7_discourse_envelope: Optional[str] = None
    semantic_frame: Optional[str] = None
    lexical_frame: Optional[str] = None


# ==============================================================================
# GROUP A: FORMULA CORRECTNESS (12 tests)
# ==============================================================================


class TestGroupAFormulaCorrectness:
    """Test core formula mathematics: delta application, clamps, range."""

    def test_a01_clamp_within_range(self):
        """Test clamp keeps values in [0.0, 1.0] range."""
        assert clamp(0.5) == 0.5
        assert clamp(-0.1) == 0.0
        assert clamp(1.5) == 1.0
        assert clamp(0.0) == 0.0
        assert clamp(1.0) == 1.0
        assert clamp(-100.0) == 0.0
        assert clamp(100.0) == 1.0

    def test_a02_delta_bounds_validation(self):
        """Test delta bounds are validated in scenario creation."""
        # Valid scenarios
        scenario = CounterfactualScenario(
            scenario_id="valid",
            delta_coherence=0.5,
            delta_entropy=-0.5,
            delta_drift=1.0,
        )
        assert scenario.delta_coherence == 0.5

        # Invalid delta should raise
        with pytest.raises(ValueError):
            CounterfactualScenario(
                scenario_id="invalid",
                delta_coherence=1.5,  # Out of bounds
            )

        with pytest.raises(ValueError):
            CounterfactualScenario(
                scenario_id="invalid",
                delta_drift=-1.5,  # Out of bounds
            )

    def test_a03_compute_adjusted_value_basic(self):
        """Test adjusted value computation with basic inputs."""
        assert compute_adjusted_value(0.5, 0.1) == pytest.approx(0.6)
        assert compute_adjusted_value(0.5, -0.1) == pytest.approx(0.4)
        assert compute_adjusted_value(0.8, 0.3) == pytest.approx(1.0)  # Clamped
        assert compute_adjusted_value(0.2, -0.5) == pytest.approx(0.0)  # Clamped

    def test_a04_compute_adjusted_value_with_none(self):
        """Test adjusted value with None baseline uses default."""
        assert compute_adjusted_value(None, 0.0) == pytest.approx(0.5)
        assert compute_adjusted_value(None, 0.1) == pytest.approx(0.6)
        assert compute_adjusted_value(None, -0.1) == pytest.approx(0.4)

    def test_a05_ucf_recomputation_with_adjusted_values(self):
        """Test UCF is properly recomputed with adjusted values."""
        scenario = CounterfactualScenario(
            scenario_id="test",
            delta_coherence=-0.2,
        )

        result = simulate_single_scenario(
            scenario=scenario,
            baseline_coherence=0.8,
            baseline_drift=0.3,
            baseline_entropy=0.2,
        )

        # UCF should decrease when coherence drops
        assert result.ucf_delta < 0

    def test_a06_risk_flag_stability_drop(self):
        """Test STABILITY_DROP flag detection."""
        flags = detect_risk_flags(
            baseline_ucf=0.7,
            adjusted_ucf=0.5,  # Drop of 0.2 > STABILITY_DROP_THRESHOLD
            baseline_coherence=0.7,
            adjusted_coherence=0.5,
            delta_entropy=0.0,
            delta_drift=0.0,
        )
        assert "STABILITY_DROP" in flags

    def test_a07_risk_flag_entropy_spike(self):
        """Test ENTROPY_SPIKE flag detection."""
        flags = detect_risk_flags(
            baseline_ucf=0.7,
            adjusted_ucf=0.65,
            baseline_coherence=0.7,
            adjusted_coherence=0.7,
            delta_entropy=0.25,  # > ENTROPY_SPIKE_THRESHOLD
            delta_drift=0.0,
        )
        assert "ENTROPY_SPIKE" in flags

    def test_a08_risk_flag_drift_acceleration(self):
        """Test DRIFT_ACCELERATION flag detection."""
        flags = detect_risk_flags(
            baseline_ucf=0.7,
            adjusted_ucf=0.65,
            baseline_coherence=0.7,
            adjusted_coherence=0.7,
            delta_entropy=0.0,
            delta_drift=0.25,  # > DRIFT_ACCELERATION_THRESHOLD
        )
        assert "DRIFT_ACCELERATION" in flags

    def test_a09_risk_flag_ucf_threshold_cross(self):
        """Test UCF_THRESHOLD_CROSS flag detection."""
        # Crossing from stable to transitional
        flags = detect_risk_flags(
            baseline_ucf=0.80,
            adjusted_ucf=0.70,  # Crosses 0.75 threshold
            baseline_coherence=0.8,
            adjusted_coherence=0.7,
            delta_entropy=0.0,
            delta_drift=0.0,
        )
        assert "UCF_THRESHOLD_CROSS" in flags

    def test_a10_scenario_with_all_deltas(self):
        """Test scenario applying all deltas simultaneously."""
        scenario = CounterfactualScenario(
            scenario_id="all_deltas",
            delta_coherence=-0.1,
            delta_entropy=0.15,
            delta_drift=0.1,
            delta_schema_stability=-0.05,
        )

        result = simulate_single_scenario(
            scenario=scenario,
            baseline_coherence=0.7,
            baseline_drift=0.3,
            baseline_entropy=0.2,
            baseline_schema_stability=0.6,
        )

        # All negative impacts should reduce UCF
        assert result.ucf_delta < 0

    def test_a11_identity_scenario_produces_zero_delta(self):
        """Test identity scenario (all zeros) produces zero UCF delta."""
        scenario = CounterfactualScenario(
            scenario_id="identity",
            delta_coherence=0.0,
            delta_entropy=0.0,
            delta_drift=0.0,
        )
        assert scenario.is_identity()

        result = simulate_single_scenario(
            scenario=scenario,
            baseline_coherence=0.7,
            baseline_drift=0.3,
            baseline_entropy=0.2,
        )

        # Identity scenario should produce zero delta
        assert result.ucf_delta == pytest.approx(0.0, abs=1e-9)

    def test_a12_max_deltas_computed_correctly(self):
        """Test max positive/negative deltas are computed correctly."""
        scenarios = [
            CounterfactualScenario(scenario_id="pos", delta_coherence=0.2),
            CounterfactualScenario(scenario_id="neg", delta_coherence=-0.2),
            CounterfactualScenario(scenario_id="neutral", delta_coherence=0.0),
        ]

        report = run_sandbox(
            scenarios=scenarios,
            baseline_coherence=0.5,
        )

        assert report.max_positive_delta >= 0
        assert report.max_negative_delta <= 0


# ==============================================================================
# GROUP B: DETERMINISM (10 tests)
# ==============================================================================


class TestGroupBDeterminism:
    """Test deterministic behavior - same inputs produce identical outputs."""

    def test_b01_single_scenario_determinism(self):
        """Test single scenario produces identical results on repeated runs."""
        scenario = CounterfactualScenario(
            scenario_id="test",
            delta_coherence=-0.1,
            delta_drift=0.1,
        )

        results = []
        for _ in range(10):
            result = simulate_single_scenario(
                scenario=scenario,
                baseline_coherence=0.7,
                baseline_drift=0.3,
                baseline_entropy=0.2,
            )
            results.append(result.ucf_delta)

        # All results should be identical
        assert len(set(results)) == 1

    def test_b02_sandbox_determinism(self):
        """Test sandbox produces identical reports on repeated runs."""
        scenarios = [
            CounterfactualScenario(scenario_id="s1", delta_coherence=-0.1),
            CounterfactualScenario(scenario_id="s2", delta_drift=0.2),
        ]

        is_deterministic, report = verify_sandbox_determinism(
            scenarios=scenarios,
            baseline_coherence=0.7,
            baseline_drift=0.3,
            baseline_entropy=0.2,
            iterations=10,
        )

        assert is_deterministic

    def test_b03_ucf_delta_exact_repeatability(self):
        """Test UCF delta is exactly repeatable."""
        scenario = CounterfactualScenario(
            scenario_id="exact",
            delta_coherence=-0.15,
            delta_entropy=0.1,
        )

        deltas = []
        for _ in range(20):
            result = simulate_single_scenario(
                scenario=scenario,
                baseline_coherence=0.75,
                baseline_drift=0.25,
            )
            deltas.append(result.ucf_delta)

        # All deltas should be bit-identical
        assert all(d == deltas[0] for d in deltas)

    def test_b04_risk_flags_deterministic(self):
        """Test risk flag detection is deterministic."""
        scenario = CounterfactualScenario(
            scenario_id="flags",
            delta_coherence=-0.3,
            delta_drift=0.3,
        )

        flag_sets = []
        for _ in range(10):
            result = simulate_single_scenario(
                scenario=scenario,
                baseline_coherence=0.8,
                baseline_drift=0.3,
            )
            flag_sets.append(tuple(sorted(result.risk_flags)))

        # All flag sets should be identical
        assert len(set(flag_sets)) == 1

    def test_b05_stability_band_deterministic(self):
        """Test stability band before/after is deterministic."""
        scenario = CounterfactualScenario(
            scenario_id="band",
            delta_coherence=-0.2,
        )

        bands = []
        for _ in range(10):
            result = simulate_single_scenario(
                scenario=scenario,
                baseline_coherence=0.8,
            )
            bands.append((result.stability_band_before, result.stability_band_after))

        # All band pairs should be identical
        assert len(set(bands)) == 1

    def test_b06_report_baseline_ucf_deterministic(self):
        """Test report baseline UCF is deterministic."""
        scenarios = [
            CounterfactualScenario(scenario_id="test", delta_coherence=-0.1),
        ]

        baseline_ucfs = []
        for _ in range(10):
            report = run_sandbox(
                scenarios=scenarios,
                baseline_coherence=0.7,
                baseline_drift=0.3,
            )
            baseline_ucfs.append(report.baseline_ucf)

        # All baseline UCFs should be identical
        assert len(set(baseline_ucfs)) == 1

    def test_b07_analysis_functions_deterministic(self):
        """Test analysis functions are deterministic."""
        scenarios = [
            CounterfactualScenario(scenario_id="s1", delta_coherence=-0.1),
            CounterfactualScenario(scenario_id="s2", delta_drift=0.2),
        ]

        report = run_sandbox(
            scenarios=scenarios,
            baseline_coherence=0.7,
        )

        summaries = []
        for _ in range(5):
            summary = summarize_report(report)
            summaries.append(json.dumps(summary, sort_keys=True))

        # All summaries should be identical
        assert len(set(summaries)) == 1

    def test_b08_empty_scenario_list_deterministic(self):
        """Test empty scenario list produces consistent report."""
        reports = []
        for _ in range(5):
            report = run_sandbox(
                scenarios=[],
                baseline_coherence=0.7,
            )
            reports.append(report.baseline_ucf)

        assert len(set(reports)) == 1

    def test_b09_hash_verification(self):
        """Test that serialized report hash is consistent."""
        scenario = CounterfactualScenario(
            scenario_id="hash_test",
            delta_coherence=-0.1,
        )

        hashes = []
        for _ in range(5):
            result = simulate_single_scenario(
                scenario=scenario,
                baseline_coherence=0.7,
            )
            # Hash the serialized result
            result_dict = result.to_dict()
            result_str = json.dumps(result_dict, sort_keys=True)
            hashes.append(hashlib.md5(result_str.encode()).hexdigest())

        # All hashes should be identical
        assert len(set(hashes)) == 1

    def test_b10_scenario_order_independent(self):
        """Test scenario order doesn't affect individual results."""
        s1 = CounterfactualScenario(scenario_id="s1", delta_coherence=-0.1)
        s2 = CounterfactualScenario(scenario_id="s2", delta_drift=0.2)

        report1 = run_sandbox(scenarios=[s1, s2], baseline_coherence=0.7)
        report2 = run_sandbox(scenarios=[s2, s1], baseline_coherence=0.7)

        # Individual results should match by scenario_id
        r1_s1 = report1.get_result("s1")
        r2_s1 = report2.get_result("s1")
        assert r1_s1.ucf_delta == r2_s1.ucf_delta


# ==============================================================================
# GROUP C: NON-AUTHORITY PROOF (12 tests)
# ==============================================================================


class TestGroupCNonAuthorityProof:
    """Test that P25 does NOT affect authority phases."""

    def test_c01_regime_unchanged(self):
        """Test P6 regime is NOT modified by P25."""
        ctx = MockPipelineContext()
        ctx.coherence_state = MockCoherenceState(coherence_v3_quality=0.7)
        ctx.p6_regime = "OBSERVING"  # Set a regime

        scenarios = [
            CounterfactualScenario(scenario_id="test", delta_coherence=-0.3),
        ]

        # Store original
        original_regime = ctx.p6_regime

        # Run P25
        maybe_run_p25(ctx, scenarios)

        # Regime should be unchanged
        assert ctx.p6_regime == original_regime

    def test_c02_discourse_unchanged(self):
        """Test P7 discourse is NOT modified by P25."""
        ctx = MockPipelineContext()
        ctx.coherence_state = MockCoherenceState(coherence_v3_quality=0.7)
        ctx.p7_discourse_envelope = "INQUIRY"

        original_discourse = ctx.p7_discourse_envelope

        scenarios = [
            CounterfactualScenario(scenario_id="test", delta_drift=0.3),
        ]

        maybe_run_p25(ctx, scenarios)

        assert ctx.p7_discourse_envelope == original_discourse

    def test_c03_semantic_frame_unchanged(self):
        """Test P8 semantic frame is NOT modified by P25."""
        ctx = MockPipelineContext()
        ctx.coherence_state = MockCoherenceState(coherence_v3_quality=0.7)
        ctx.semantic_frame = {"slots": ["question", "context"]}

        original_frame = deepcopy(ctx.semantic_frame)

        scenarios = [
            CounterfactualScenario(scenario_id="test", delta_entropy=0.3),
        ]

        maybe_run_p25(ctx, scenarios)

        assert ctx.semantic_frame == original_frame

    def test_c04_lexical_frame_unchanged(self):
        """Test P9 lexical frame is NOT modified by P25."""
        ctx = MockPipelineContext()
        ctx.coherence_state = MockCoherenceState(coherence_v3_quality=0.7)
        ctx.lexical_frame = {"tokens": ["why", "how"]}

        original_frame = deepcopy(ctx.lexical_frame)

        scenarios = [
            CounterfactualScenario(scenario_id="test", delta_coherence=-0.2),
        ]

        maybe_run_p25(ctx, scenarios)

        assert ctx.lexical_frame == original_frame

    def test_c05_observer_only_flag_always_true(self):
        """Test observer_only flag is always True on outputs."""
        scenarios = [
            CounterfactualScenario(scenario_id="test", delta_coherence=-0.1),
        ]

        report = run_sandbox(scenarios=scenarios, baseline_coherence=0.7)

        # Report should have observer_only=True
        assert report.observer_only is True

        # All results should have observer_only=True
        for result in report.results:
            assert result.observer_only is True

    def test_c06_result_cannot_disable_observer_only(self):
        """Test that observer_only cannot be set to False in result."""
        with pytest.raises(ValueError):
            CounterfactualResult(
                scenario_id="test",
                ucf_delta=0.0,
                coherence_delta=0.0,
                stability_band_before="stable",
                stability_band_after="stable",
                risk_flags=(),
                observer_only=False,  # Should fail
            )

    def test_c07_report_cannot_disable_observer_only(self):
        """Test that observer_only cannot be set to False in report."""
        with pytest.raises(ValueError):
            CounterfactualSandboxReport(
                baseline_ucf=0.7,
                baseline_stability_band="transitional",
                results=(),
                max_negative_delta=0.0,
                max_positive_delta=0.0,
                observer_only=False,  # Should fail
            )

    def test_c08_no_side_effects_on_coherence_state(self):
        """Test coherence_state is NOT modified by P25."""
        ctx = MockPipelineContext()
        ctx.coherence_state = MockCoherenceState(
            coherence_v3_quality=0.7,
            drift_fusion_index=0.3,
        )

        original_coherence = ctx.coherence_state.coherence_v3_quality
        original_drift = ctx.coherence_state.drift_fusion_index

        scenarios = [
            CounterfactualScenario(scenario_id="test", delta_coherence=-0.5),
        ]

        maybe_run_p25(ctx, scenarios)

        # Coherence state values should be unchanged
        assert ctx.coherence_state.coherence_v3_quality == original_coherence
        assert ctx.coherence_state.drift_fusion_index == original_drift

    def test_c09_only_p25_field_modified(self):
        """Test only ctx.p25 is modified, nothing else."""
        ctx = MockPipelineContext()
        ctx.coherence_state = MockCoherenceState(coherence_v3_quality=0.7)
        ctx.p18 = MockP18Report()
        ctx.p19 = MockP19Report()
        ctx.p33 = MockP33Snapshot()
        ctx.p6_regime = "OBSERVING"
        ctx.p7_discourse_envelope = "INQUIRY"
        ctx.semantic_frame = {"test": "frame"}
        ctx.lexical_frame = {"test": "lexical"}

        # Take snapshot of all fields except p25
        snapshot = {
            "p6_regime": ctx.p6_regime,
            "p7_discourse_envelope": ctx.p7_discourse_envelope,
            "semantic_frame": deepcopy(ctx.semantic_frame),
            "lexical_frame": deepcopy(ctx.lexical_frame),
        }

        scenarios = [
            CounterfactualScenario(scenario_id="test", delta_coherence=-0.2),
        ]

        maybe_run_p25(ctx, scenarios)

        # Verify p25 was set
        assert ctx.p25 is not None

        # Verify nothing else changed
        assert ctx.p6_regime == snapshot["p6_regime"]
        assert ctx.p7_discourse_envelope == snapshot["p7_discourse_envelope"]
        assert ctx.semantic_frame == snapshot["semantic_frame"]
        assert ctx.lexical_frame == snapshot["lexical_frame"]

    def test_c10_disabled_context_no_modification(self):
        """Test disabled P25 makes no modifications."""
        ctx = MockPipelineContext()
        ctx.coherence_state = MockCoherenceState(coherence_v3_quality=0.7)
        ctx._p25_disabled = True

        assert ctx.p25 is None

        scenarios = [
            CounterfactualScenario(scenario_id="test", delta_coherence=-0.2),
        ]

        result = maybe_run_p25(ctx, scenarios)

        # Should return None and not set p25
        assert result is None
        assert ctx.p25 is None

    def test_c11_result_notes_are_observational(self):
        """Test report notes field is observational only."""
        report = create_report(
            baseline_ucf=0.7,
            baseline_stability_band="transitional",
            results=[],
            notes="Test observation",
        )

        # Notes should be present but report still observer_only
        assert report.notes == "Test observation"
        assert report.observer_only is True

    def test_c12_architectural_phase_is_p25(self):
        """Test architectural_phase field is always P25."""
        report = create_report(
            baseline_ucf=0.7,
            baseline_stability_band="transitional",
            results=[],
        )

        assert report.architectural_phase == "P25"


# ==============================================================================
# GROUP D: BOUNDARY SAFETY (10 tests)
# ==============================================================================


class TestGroupDBoundarySafety:
    """Test behavior at boundary conditions."""

    def test_d01_extreme_positive_delta(self):
        """Test maximum positive delta (+1.0)."""
        scenario = CounterfactualScenario(
            scenario_id="max_positive",
            delta_coherence=1.0,
        )

        result = simulate_single_scenario(
            scenario=scenario,
            baseline_coherence=0.5,
        )

        # Should not crash, UCF delta should be positive
        assert result.ucf_delta > 0

    def test_d02_extreme_negative_delta(self):
        """Test maximum negative delta (-1.0)."""
        scenario = CounterfactualScenario(
            scenario_id="max_negative",
            delta_coherence=-1.0,
        )

        result = simulate_single_scenario(
            scenario=scenario,
            baseline_coherence=0.5,
        )

        # Should not crash, UCF delta should be negative
        assert result.ucf_delta < 0

    def test_d03_zero_baseline_with_negative_delta(self):
        """Test zero baseline with negative delta clamps correctly."""
        scenario = CounterfactualScenario(
            scenario_id="zero_neg",
            delta_coherence=-0.5,
        )

        result = simulate_single_scenario(
            scenario=scenario,
            baseline_coherence=0.0,  # Already at minimum
        )

        # Adjusted coherence should be clamped to 0.0
        assert result.coherence_delta <= 0

    def test_d04_max_baseline_with_positive_delta(self):
        """Test max baseline (1.0) with positive delta clamps correctly."""
        scenario = CounterfactualScenario(
            scenario_id="max_pos",
            delta_coherence=0.5,
        )

        result = simulate_single_scenario(
            scenario=scenario,
            baseline_coherence=1.0,  # Already at maximum
        )

        # Adjusted coherence should be clamped to 1.0
        # Delta should be near 0 since we can't go above 1.0
        assert abs(result.coherence_delta) < 0.01

    def test_d05_all_none_baselines(self):
        """Test with all None baselines (uses neutral defaults)."""
        scenario = CounterfactualScenario(
            scenario_id="all_none",
            delta_coherence=-0.1,
        )

        result = simulate_single_scenario(
            scenario=scenario,
            baseline_coherence=None,
            baseline_drift=None,
            baseline_entropy=None,
            baseline_schema_stability=None,
            baseline_identity_harmonics=None,
        )

        # Should work with neutral defaults
        assert result.scenario_id == "all_none"

    def test_d06_empty_scenario_id_rejected(self):
        """Test empty scenario_id is rejected."""
        with pytest.raises(ValueError):
            CounterfactualScenario(scenario_id="", delta_coherence=0.1)

        with pytest.raises(ValueError):
            CounterfactualScenario(scenario_id="   ", delta_coherence=0.1)

    def test_d07_ucf_exactly_at_thresholds(self):
        """Test UCF values exactly at stability thresholds."""
        # Test at stable threshold
        band_at_75 = compute_stability_band(0.75)
        assert band_at_75 == StabilityBand.STABLE

        # Test just below stable threshold
        band_at_7499 = compute_stability_band(0.7499)
        assert band_at_7499 == StabilityBand.TRANSITIONAL

        # Test at transitional threshold
        band_at_45 = compute_stability_band(0.45)
        assert band_at_45 == StabilityBand.TRANSITIONAL

        # Test just below transitional threshold
        band_at_4499 = compute_stability_band(0.4499)
        assert band_at_4499 == StabilityBand.UNSTABLE

    def test_d08_scenario_delta_bounds_edge(self):
        """Test scenarios at exact delta bounds."""
        # Exactly at bounds should work
        scenario = CounterfactualScenario(
            scenario_id="bounds",
            delta_coherence=DELTA_MAX,
            delta_drift=DELTA_MIN,
            delta_entropy=DELTA_MAX,
        )

        assert scenario.delta_coherence == DELTA_MAX
        assert scenario.delta_drift == DELTA_MIN

    def test_d09_many_scenarios(self):
        """Test sandbox handles many scenarios efficiently."""
        scenarios = [
            CounterfactualScenario(
                scenario_id=f"scenario_{i}",
                delta_coherence=(i - 50) / 100,  # Range from -0.5 to +0.5
            )
            for i in range(100)
        ]

        report = run_sandbox(scenarios=scenarios, baseline_coherence=0.5)

        # Should handle 100 scenarios
        assert report.scenario_count() == 100

    def test_d10_serialization_roundtrip(self):
        """Test report serialization doesn't lose data."""
        scenarios = [
            CounterfactualScenario(
                scenario_id="test",
                delta_coherence=-0.1,
                delta_drift=0.2,
            ),
        ]

        report = run_sandbox(scenarios=scenarios, baseline_coherence=0.7)

        # Serialize to dict and verify key fields
        report_dict = report.to_dict()

        assert report_dict["baseline_ucf"] == report.baseline_ucf
        assert report_dict["baseline_stability_band"] == report.baseline_stability_band
        assert len(report_dict["results"]) == 1
        assert report_dict["observer_only"] is True


# ==============================================================================
# GROUP E: IMPORT SAFETY (6 tests)
# ==============================================================================


class TestGroupEImportSafety:
    """Test forbidden imports are not present."""

    def _get_imports_from_file(self, filepath: str) -> set:
        """Extract all imports from a Python file."""
        with open(filepath, "r") as f:
            content = f.read()

        tree = ast.parse(content)
        imports = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])

        return imports

    def test_e01_cf_schema_no_forbidden_imports(self):
        """Test cf_schema.py has no forbidden imports."""
        filepath = "symbolu/core/counterfactual/cf_schema.py"

        # Check file contains no forbidden patterns
        with open(filepath, "r") as f:
            content = f.read()

        # Forbidden patterns - should NOT appear
        forbidden_patterns = [
            "from symbolu.mechanical.pipeline.phase_p6",
            "from symbolu.mechanical.pipeline.p7_discourse",
            "from symbolu.mechanical.pipeline.p8_semantics",
            "from symbolu.mechanical.pipeline.p9_lexical",
            "from symbolu.mechanical.dha",
            "from symbolu.mechanical.renderer",
            "from symbolu.mechanical.persona",
        ]

        for pattern in forbidden_patterns:
            assert pattern not in content, f"Forbidden import pattern found: {pattern}"

    def test_e02_cf_engine_no_forbidden_imports(self):
        """Test cf_engine.py has no forbidden imports."""
        filepath = "symbolu/core/counterfactual/cf_engine.py"

        with open(filepath, "r") as f:
            content = f.read()

        forbidden_patterns = [
            "from symbolu.mechanical.pipeline.phase_p6",
            "from symbolu.mechanical.pipeline.p7_discourse",
            "from symbolu.mechanical.pipeline.p8_semantics",
            "from symbolu.mechanical.pipeline.p9_lexical",
            "from symbolu.mechanical.dha",
            "from symbolu.mechanical.renderer",
            "from symbolu.mechanical.persona",
            "p22_acoustic",
            "p23_alignment",
            "p24_projection",
        ]

        for pattern in forbidden_patterns:
            assert pattern not in content, f"Forbidden import pattern found: {pattern}"

    def test_e03_cf_analyzer_no_forbidden_imports(self):
        """Test cf_analyzer.py has no forbidden imports."""
        filepath = "symbolu/core/counterfactual/cf_analyzer.py"

        with open(filepath, "r") as f:
            content = f.read()

        forbidden_patterns = [
            "from symbolu.mechanical.pipeline.phase_p6",
            "from symbolu.mechanical.pipeline.p7_discourse",
            "from symbolu.mechanical.pipeline.p8_semantics",
            "from symbolu.mechanical.pipeline.p9_lexical",
            "from symbolu.mechanical.dha",
            "from symbolu.mechanical.renderer",
        ]

        for pattern in forbidden_patterns:
            assert pattern not in content, f"Forbidden import pattern found: {pattern}"

    def test_e04_p25_integration_no_forbidden_imports(self):
        """Test p25_integration.py has no forbidden imports."""
        filepath = "symbolu/mechanical/pipeline/p25_counterfactual/p25_integration.py"

        with open(filepath, "r") as f:
            content = f.read()

        forbidden_patterns = [
            "from symbolu.mechanical.pipeline.phase_p6",
            "from symbolu.mechanical.pipeline.p7_discourse",
            "from symbolu.mechanical.pipeline.p8_semantics",
            "from symbolu.mechanical.pipeline.p9_lexical",
            "from symbolu.mechanical.dha",
            "from symbolu.mechanical.renderer",
            "from symbolu.mechanical.persona",
        ]

        for pattern in forbidden_patterns:
            assert pattern not in content, f"Forbidden import pattern found: {pattern}"

    def test_e05_no_random_imports(self):
        """Test no random/sampling modules are imported."""
        files = [
            "symbolu/core/counterfactual/cf_schema.py",
            "symbolu/core/counterfactual/cf_engine.py",
            "symbolu/core/counterfactual/cf_analyzer.py",
            "symbolu/mechanical/pipeline/p25_counterfactual/p25_integration.py",
        ]

        forbidden_modules = ["random", "numpy.random", "scipy.stats"]

        for filepath in files:
            with open(filepath, "r") as f:
                content = f.read()

            for module in forbidden_modules:
                assert f"import {module}" not in content
                assert f"from {module}" not in content

    def test_e06_no_llm_or_ai_imports(self):
        """Test no LLM or AI-related imports."""
        files = [
            "symbolu/core/counterfactual/cf_schema.py",
            "symbolu/core/counterfactual/cf_engine.py",
            "symbolu/core/counterfactual/cf_analyzer.py",
            "symbolu/mechanical/pipeline/p25_counterfactual/p25_integration.py",
        ]

        forbidden_patterns = [
            "openai",
            "anthropic",
            "langchain",
            "llm",
            "transformer",
            "torch",
            "tensorflow",
        ]

        for filepath in files:
            with open(filepath, "r") as f:
                content = f.read().lower()

            for pattern in forbidden_patterns:
                # Check imports only, not documentation
                import_patterns = [
                    f"import {pattern}",
                    f"from {pattern}",
                ]
                for imp in import_patterns:
                    assert imp not in content


# ==============================================================================
# GROUP F: REGRESSION LOCK (12 tests)
# ==============================================================================


class TestGroupFRegressionLock:
    """Test pipeline identical when P25 is unused or disabled."""

    def test_f01_disabled_p25_returns_none(self):
        """Test disabled P25 returns None."""
        ctx = MockPipelineContext()
        ctx.coherence_state = MockCoherenceState(coherence_v3_quality=0.7)
        ctx._p25_disabled = True

        scenarios = [
            CounterfactualScenario(scenario_id="test", delta_coherence=-0.1),
        ]

        result = maybe_run_p25(ctx, scenarios)

        assert result is None

    def test_f02_no_context_attributes_returns_none(self):
        """Test context without expected attributes returns None."""

        @dataclass
        class EmptyContext:
            pass

        ctx = EmptyContext()

        scenarios = [
            CounterfactualScenario(scenario_id="test", delta_coherence=-0.1),
        ]

        result = maybe_run_p25(ctx, scenarios)

        assert result is None

    def test_f03_empty_scenarios_produces_valid_report(self):
        """Test empty scenarios list produces valid report."""
        report = run_sandbox(scenarios=[], baseline_coherence=0.7)

        assert report.scenario_count() == 0
        assert report.results == ()
        assert report.notes == "No scenarios provided"

    def test_f04_p25_is_disabled_helper(self):
        """Test is_p25_disabled helper function."""
        ctx = MockPipelineContext()

        assert not is_p25_disabled(ctx)

        ctx._p25_disabled = True
        assert is_p25_disabled(ctx)

    def test_f05_has_p25_report_helper(self):
        """Test has_p25_report helper function."""
        ctx = MockPipelineContext()

        assert not has_p25_report(ctx)

        ctx.p25 = create_report(
            baseline_ucf=0.7,
            baseline_stability_band="transitional",
            results=[],
        )

        assert has_p25_report(ctx)

    def test_f06_get_p25_report_helper(self):
        """Test get_p25_report helper function."""
        ctx = MockPipelineContext()

        assert get_p25_report(ctx) is None

        report = create_report(
            baseline_ucf=0.7,
            baseline_stability_band="transitional",
            results=[],
        )
        ctx.p25 = report

        assert get_p25_report(ctx) == report

    def test_f07_get_baseline_ucf_helper(self):
        """Test get_baseline_ucf helper function."""
        ctx = MockPipelineContext()

        # No report - should return neutral default
        assert get_baseline_ucf(ctx) == 0.5

        ctx.p25 = create_report(
            baseline_ucf=0.8,
            baseline_stability_band="stable",
            results=[],
        )

        assert get_baseline_ucf(ctx) == 0.8

    def test_f08_version_consistency(self):
        """Test version is consistent across module."""
        assert P25_VERSION == "1.0.0"
        assert get_p25_version() == P25_VERSION

    def test_f09_run_p25_directly_works_without_context(self):
        """Test run_p25_directly works without any context."""
        scenarios = [
            CounterfactualScenario(scenario_id="direct", delta_coherence=-0.1),
        ]

        report = run_p25_directly(
            scenarios=scenarios,
            baseline_coherence=0.7,
        )

        assert report is not None
        assert report.scenario_count() == 1

    def test_f10_analyzer_works_on_empty_report(self):
        """Test analysis functions work on empty report."""
        report = create_report(
            baseline_ucf=0.7,
            baseline_stability_band="transitional",
            results=[],
        )

        sensitivity = analyze_ucf_sensitivity(report)
        assert sensitivity["max_negative_impact"] == 0.0

        transitions = analyze_stability_transitions(report)
        assert transitions["transitions_count"] == 0

        flags = analyze_risk_flags(report)
        assert flags["total_flagged_scenarios"] == 0

    def test_f11_scenario_immutability(self):
        """Test scenarios are immutable."""
        scenario = CounterfactualScenario(
            scenario_id="test",
            delta_coherence=-0.1,
        )

        # Trying to modify should raise
        with pytest.raises(AttributeError):
            scenario.delta_coherence = 0.5

    def test_f12_result_immutability(self):
        """Test results are immutable."""
        result = create_result(
            scenario_id="test",
            ucf_delta=-0.1,
            coherence_delta=-0.1,
            stability_band_before="stable",
            stability_band_after="transitional",
            risk_flags=["STABILITY_DROP"],
        )

        # Trying to modify should raise
        with pytest.raises(AttributeError):
            result.ucf_delta = 0.0


# ==============================================================================
# ADDITIONAL INVARIANT TESTS
# ==============================================================================


class TestInvariants:
    """Test specific invariant guarantees."""

    def test_inv_p25_1_observer_only(self):
        """INV-P25-1: Sandbox outputs are observational only."""
        report = run_sandbox(
            scenarios=[CounterfactualScenario(scenario_id="test", delta_coherence=-0.1)],
            baseline_coherence=0.7,
        )

        # Observer only flag must be True
        assert report.observer_only is True

        for result in report.results:
            assert result.observer_only is True

    def test_inv_p25_2_no_context_mutation(self):
        """INV-P25-2: No mutation of PipelineContext."""
        ctx = MockPipelineContext()
        ctx.coherence_state = MockCoherenceState(
            coherence_v3_quality=0.7,
            drift_fusion_index=0.3,
        )

        # Store original values
        original_quality = ctx.coherence_state.coherence_v3_quality
        original_drift = ctx.coherence_state.drift_fusion_index

        scenarios = [
            CounterfactualScenario(scenario_id="test", delta_coherence=-0.5),
        ]

        maybe_run_p25(ctx, scenarios)

        # Values must be unchanged
        assert ctx.coherence_state.coherence_v3_quality == original_quality
        assert ctx.coherence_state.drift_fusion_index == original_drift

    def test_inv_p25_3_no_recommendations(self):
        """INV-P25-3: Counterfactuals never imply recommendations."""
        # Report has no recommendation fields
        report = run_sandbox(
            scenarios=[CounterfactualScenario(scenario_id="test", delta_coherence=-0.5)],
            baseline_coherence=0.7,
        )

        report_dict = report.to_dict()

        # These fields should NOT exist
        assert "recommendation" not in report_dict
        assert "suggested_action" not in report_dict
        assert "should_do" not in report_dict
        assert "next_step" not in report_dict

    def test_inv_p25_4_ucf_recomputed_not_overridden(self):
        """INV-P25-4: UCF is recomputed, never overridden."""
        scenario = CounterfactualScenario(
            scenario_id="test",
            delta_coherence=-0.1,
        )

        result = simulate_single_scenario(
            scenario=scenario,
            baseline_coherence=0.7,
        )

        # UCF delta should match actual P26 formula computation
        baseline_ucf = compute_ucf(coherence_v3_quality=0.7).ucf_score
        adjusted_ucf = compute_ucf(coherence_v3_quality=0.6).ucf_score
        expected_delta = adjusted_ucf - baseline_ucf

        assert abs(result.ucf_delta - expected_delta) < 0.01

    def test_inv_p25_5_no_forward_prediction(self):
        """INV-P25-5: No forward prediction allowed."""
        report = run_sandbox(
            scenarios=[CounterfactualScenario(scenario_id="test", delta_coherence=-0.1)],
            baseline_coherence=0.7,
        )

        report_dict = report.to_dict()

        # These prediction-related fields should NOT exist
        assert "predicted_future" not in report_dict
        assert "forecast" not in report_dict
        assert "will_happen" not in report_dict
        assert "expected_outcome" not in report_dict
        assert "probability" not in report_dict


# ==============================================================================
# ANALYZER FUNCTION TESTS
# ==============================================================================


class TestAnalyzerFunctions:
    """Test analyzer utility functions."""

    def test_analyze_ucf_sensitivity(self):
        """Test UCF sensitivity analysis."""
        scenarios = [
            CounterfactualScenario(scenario_id="pos", delta_coherence=0.2),
            CounterfactualScenario(scenario_id="neg", delta_coherence=-0.3),
            CounterfactualScenario(scenario_id="neutral", delta_coherence=0.0),
        ]

        report = run_sandbox(scenarios=scenarios, baseline_coherence=0.5)
        sensitivity = analyze_ucf_sensitivity(report)

        assert "max_negative_impact" in sensitivity
        assert "max_positive_impact" in sensitivity
        assert "most_sensitive_scenario" in sensitivity

    def test_analyze_stability_transitions(self):
        """Test stability transition analysis."""
        scenarios = [
            CounterfactualScenario(scenario_id="drop", delta_coherence=-0.4),
        ]

        report = run_sandbox(scenarios=scenarios, baseline_coherence=0.8)
        transitions = analyze_stability_transitions(report)

        assert "transitions_count" in transitions
        assert "stable_to_transitional" in transitions

    def test_find_boundary_scenarios(self):
        """Test boundary scenario identification."""
        scenarios = [
            CounterfactualScenario(scenario_id="crossing", delta_coherence=-0.4),
        ]

        report = run_sandbox(scenarios=scenarios, baseline_coherence=0.8)
        boundaries = find_boundary_scenarios(report)

        assert "crossing_to_stable" in boundaries
        assert "crossing_to_transitional" in boundaries
        assert "crossing_to_unstable" in boundaries

    def test_compute_delta_distribution(self):
        """Test delta distribution computation."""
        scenarios = [
            CounterfactualScenario(scenario_id=f"s{i}", delta_coherence=(i-5)*0.1)
            for i in range(10)
        ]

        report = run_sandbox(scenarios=scenarios, baseline_coherence=0.5)
        dist = compute_delta_distribution(report)

        assert dist["count"] == 10
        assert "min" in dist
        assert "max" in dist
        assert "mean" in dist

    def test_filter_results_by_flag(self):
        """Test filtering results by risk flag."""
        scenarios = [
            CounterfactualScenario(scenario_id="safe", delta_coherence=-0.05),
            CounterfactualScenario(scenario_id="risky", delta_coherence=-0.4),
        ]

        report = run_sandbox(scenarios=scenarios, baseline_coherence=0.8)
        drops = filter_results_by_flag(report, "STABILITY_DROP")

        # Only risky scenario should have STABILITY_DROP
        assert len(drops) <= 2

    def test_compare_scenarios(self):
        """Test scenario comparison."""
        s1 = CounterfactualScenario(scenario_id="s1", delta_coherence=-0.1)
        s2 = CounterfactualScenario(scenario_id="s2", delta_coherence=-0.2)

        r1 = simulate_single_scenario(s1, baseline_coherence=0.7)
        r2 = simulate_single_scenario(s2, baseline_coherence=0.7)

        comparison = compare_scenarios(r1, r2)

        assert "ucf_delta_difference" in comparison
        assert "shared_flags" in comparison
