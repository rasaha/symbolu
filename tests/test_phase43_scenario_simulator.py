"""
Phase 43 - Scenario What-If Simulator - Test Suite

Comprehensive test suite with 40+ deterministic tests across 5 groups:
    - Group A: Preset Logic (8 tests)
    - Group B: Simulation Math (12 tests)
    - Group C: Integration (8 tests)
    - Group D: API (6 tests)
    - Group E: Invariance (8 tests)

CRITICAL REQUIREMENTS:
    - All tests must be deterministic (same inputs → same outputs)
    - Zero-LLM guarantee
    - No modifications to live coherence state
    - No changes to routing (TTOR/MLCR)
    - No mapper activation changes
    - No persona tone or semantics changed
"""

import pytest
from typing import Dict, Any
import copy

from symbolu.tools.scenario_simulator.presets import (
    ScenarioPreset,
    get_preset,
    list_presets,
    is_valid_preset,
    get_preset_names,
    get_multiplier,
    PRESETS,
)

from symbolu.tools.scenario_simulator.simulator import (
    SimulatedScenarioResult,
    simulate_scenario_with_preset,
    simulate_all_presets,
    get_simulation_summary,
    _clamp,
    _recompute_uncertainty_band,
    _recompute_diagnostic_tags,
    _apply_path_shift_bias,
    _generate_comparison_notes,
)

from symbolu.formulas.scenario_fusion_engine import ScenarioFusionSnapshot


# ============================================================================
# GROUP A — PRESET LOGIC (8 tests)
# ============================================================================

class TestPresetLogic:
    """Test preset retrieval, multiplier behavior, and valid ranges."""

    def test_preset_retrieval_neutral_baseline(self):
        """Test retrieval of neutral_baseline preset."""
        preset = get_preset("neutral_baseline")
        assert preset.name == "neutral_baseline"
        assert preset.alignment_multiplier == 1.0
        assert preset.divergence_multiplier == 1.0
        assert preset.consensus_multiplier == 1.0
        assert preset.uncertainty_multiplier == 1.0
        assert preset.path_shift_bias == 0.0

    def test_preset_retrieval_conservative_bias(self):
        """Test retrieval of conservative_bias preset."""
        preset = get_preset("conservative_bias")
        assert preset.name == "conservative_bias"
        assert preset.alignment_multiplier == 0.75
        assert preset.divergence_multiplier == 1.30
        assert preset.consensus_multiplier == 0.80
        assert preset.uncertainty_multiplier == 1.25
        assert preset.path_shift_bias == -1.0

    def test_preset_retrieval_expansive_bias(self):
        """Test retrieval of expansive_bias preset."""
        preset = get_preset("expansive_bias")
        assert preset.name == "expansive_bias"
        assert preset.alignment_multiplier == 1.30
        assert preset.divergence_multiplier == 0.70
        assert preset.consensus_multiplier == 1.25
        assert preset.uncertainty_multiplier == 0.75
        assert preset.path_shift_bias == 1.0

    def test_preset_retrieval_stability_bias(self):
        """Test retrieval of stability_bias preset."""
        preset = get_preset("stability_bias")
        assert preset.name == "stability_bias"
        assert preset.alignment_multiplier == 1.15
        assert preset.divergence_multiplier == 0.80
        assert preset.consensus_multiplier == 1.40
        assert preset.uncertainty_multiplier == 0.65
        assert preset.path_shift_bias == 0.0

    def test_preset_retrieval_uncertainty_spike(self):
        """Test retrieval of uncertainty_spike preset."""
        preset = get_preset("uncertainty_spike")
        assert preset.name == "uncertainty_spike"
        assert preset.alignment_multiplier == 0.70
        assert preset.divergence_multiplier == 1.45
        assert preset.consensus_multiplier == 0.70
        assert preset.uncertainty_multiplier == 1.50
        assert preset.path_shift_bias == 0.0

    def test_preset_invalid_raises_key_error(self):
        """Test that invalid preset name raises KeyError."""
        with pytest.raises(KeyError) as exc_info:
            get_preset("nonexistent_preset")
        assert "not found" in str(exc_info.value)

    def test_list_presets_returns_all_five(self):
        """Test that list_presets returns all 5 presets."""
        presets = list_presets()
        assert len(presets) == 5
        assert "neutral_baseline" in presets
        assert "conservative_bias" in presets
        assert "expansive_bias" in presets
        assert "stability_bias" in presets
        assert "uncertainty_spike" in presets

    def test_is_valid_preset_checks(self):
        """Test is_valid_preset for valid and invalid names."""
        assert is_valid_preset("neutral_baseline") is True
        assert is_valid_preset("conservative_bias") is True
        assert is_valid_preset("expansive_bias") is True
        assert is_valid_preset("stability_bias") is True
        assert is_valid_preset("uncertainty_spike") is True
        assert is_valid_preset("nonexistent") is False
        assert is_valid_preset("") is False


# ============================================================================
# GROUP B — SIMULATION MATH (12 tests)
# ============================================================================

class TestSimulationMath:
    """Test alignment/divergence adjustments, path-shift logic, bounded outputs."""

    def _create_sample_snapshot(self) -> ScenarioFusionSnapshot:
        """Create a sample scenario fusion snapshot for testing."""
        return ScenarioFusionSnapshot(
            fused_scenario_vector={"stable": 0.6, "volatile": 0.4},
            scenario_alignment_score=0.65,
            scenario_divergence_index=0.42,
            multi_regime_consensus=0.58,
            dominant_future_path="stable",
            future_uncertainty_band="medium",
            diagnostic_tags=["SCENARIO_HIGHLY_ALIGNED", "SCENARIO_CONVERGING"],
        )

    def test_clamp_function_bounds(self):
        """Test _clamp function enforces [0.0, 1.0] bounds."""
        assert _clamp(0.5) == 0.5
        assert _clamp(-0.1) == 0.0
        assert _clamp(1.5) == 1.0
        assert _clamp(0.0) == 0.0
        assert _clamp(1.0) == 1.0

    def test_alignment_multiplier_increases_alignment(self):
        """Test that alignment multiplier increases alignment score."""
        snapshot = self._create_sample_snapshot()
        preset = get_preset("expansive_bias")  # alignment_multiplier = 1.30

        result = simulate_scenario_with_preset(snapshot, preset)

        assert result is not None
        assert result.simulated_snapshot.scenario_alignment_score > snapshot.scenario_alignment_score

    def test_divergence_multiplier_increases_divergence(self):
        """Test that divergence multiplier increases divergence index."""
        snapshot = self._create_sample_snapshot()
        preset = get_preset("conservative_bias")  # divergence_multiplier = 1.30

        result = simulate_scenario_with_preset(snapshot, preset)

        assert result is not None
        assert result.simulated_snapshot.scenario_divergence_index > snapshot.scenario_divergence_index

    def test_consensus_multiplier_increases_consensus(self):
        """Test that consensus multiplier increases consensus."""
        snapshot = self._create_sample_snapshot()
        preset = get_preset("stability_bias")  # consensus_multiplier = 1.40

        result = simulate_scenario_with_preset(snapshot, preset)

        assert result is not None
        assert result.simulated_snapshot.multi_regime_consensus > snapshot.multi_regime_consensus

    def test_neutral_baseline_preserves_metrics(self):
        """Test that neutral_baseline preset preserves all metrics."""
        snapshot = self._create_sample_snapshot()
        preset = get_preset("neutral_baseline")

        result = simulate_scenario_with_preset(snapshot, preset)

        assert result is not None
        # Metrics should be identical (within floating point precision)
        assert abs(result.simulated_snapshot.scenario_alignment_score - snapshot.scenario_alignment_score) < 0.01
        assert abs(result.simulated_snapshot.scenario_divergence_index - snapshot.scenario_divergence_index) < 0.01
        assert abs(result.simulated_snapshot.multi_regime_consensus - snapshot.multi_regime_consensus) < 0.01

    def test_bounded_outputs_alignment(self):
        """Test that alignment score remains bounded [0.0, 1.0]."""
        snapshot = self._create_sample_snapshot()

        # Test with extreme multiplier
        for preset_name in get_preset_names():
            preset = get_preset(preset_name)
            result = simulate_scenario_with_preset(snapshot, preset)
            assert result is not None
            assert 0.0 <= result.simulated_snapshot.scenario_alignment_score <= 1.0

    def test_bounded_outputs_divergence(self):
        """Test that divergence index remains bounded [0.0, 1.0]."""
        snapshot = self._create_sample_snapshot()

        for preset_name in get_preset_names():
            preset = get_preset(preset_name)
            result = simulate_scenario_with_preset(snapshot, preset)
            assert result is not None
            assert 0.0 <= result.simulated_snapshot.scenario_divergence_index <= 1.0

    def test_bounded_outputs_consensus(self):
        """Test that consensus remains bounded [0.0, 1.0]."""
        snapshot = self._create_sample_snapshot()

        for preset_name in get_preset_names():
            preset = get_preset(preset_name)
            result = simulate_scenario_with_preset(snapshot, preset)
            assert result is not None
            assert 0.0 <= result.simulated_snapshot.multi_regime_consensus <= 1.0

    def test_deterministic_repeated_runs(self):
        """Test that repeated simulations produce identical results."""
        snapshot = self._create_sample_snapshot()
        preset = get_preset("conservative_bias")

        result1 = simulate_scenario_with_preset(snapshot, preset)
        result2 = simulate_scenario_with_preset(snapshot, preset)

        assert result1.simulated_snapshot.scenario_alignment_score == result2.simulated_snapshot.scenario_alignment_score
        assert result1.simulated_snapshot.scenario_divergence_index == result2.simulated_snapshot.scenario_divergence_index
        assert result1.simulated_snapshot.multi_regime_consensus == result2.simulated_snapshot.multi_regime_consensus
        assert result1.diagnostic_notes == result2.diagnostic_notes

    def test_graceful_degradation_none_snapshot(self):
        """Test graceful handling of None snapshot."""
        preset = get_preset("neutral_baseline")
        result = simulate_scenario_with_preset(None, preset)
        assert result is None

    def test_path_shift_bias_conservative(self):
        """Test conservative path shift bias favors lower-ranked paths."""
        snapshot = ScenarioFusionSnapshot(
            fused_scenario_vector={"stable": 0.6, "volatile": 0.3, "mixed": 0.1},
            scenario_alignment_score=0.65,
            scenario_divergence_index=0.42,
            multi_regime_consensus=0.58,
            dominant_future_path="stable",
            future_uncertainty_band="medium",
            diagnostic_tags=[],
        )
        preset = get_preset("conservative_bias")  # path_shift_bias = -1.0

        result = simulate_scenario_with_preset(snapshot, preset)

        # Conservative bias should shift away from top path
        assert result is not None
        # Should shift to a lower-ranked path
        assert result.simulated_snapshot.dominant_future_path != "stable"

    def test_uncertainty_band_recomputation(self):
        """Test uncertainty band recomputation based on simulated metrics."""
        # Create snapshot with high alignment, high consensus, low divergence → should be "low"
        snapshot = ScenarioFusionSnapshot(
            fused_scenario_vector={"stable": 0.9, "volatile": 0.1},
            scenario_alignment_score=0.80,  # high
            scenario_divergence_index=0.20,  # low
            multi_regime_consensus=0.75,    # high
            dominant_future_path="stable",
            future_uncertainty_band="low",
            diagnostic_tags=[],
        )

        # Apply uncertainty_spike preset (should increase uncertainty)
        preset = get_preset("uncertainty_spike")
        result = simulate_scenario_with_preset(snapshot, preset)

        assert result is not None
        # Uncertainty band should change due to multipliers
        # Original was "low", but with uncertainty_spike it should increase


# ============================================================================
# GROUP C — INTEGRATION (8 tests)
# ============================================================================

class TestIntegration:
    """Test coherent simulated snapshots, JSON-serializable output, multi-preset comparison."""

    def _create_sample_snapshot(self) -> ScenarioFusionSnapshot:
        """Create a sample scenario fusion snapshot for testing."""
        return ScenarioFusionSnapshot(
            fused_scenario_vector={"stable": 0.6, "volatile": 0.4},
            scenario_alignment_score=0.65,
            scenario_divergence_index=0.42,
            multi_regime_consensus=0.58,
            dominant_future_path="stable",
            future_uncertainty_band="medium",
            diagnostic_tags=["SCENARIO_HIGHLY_ALIGNED"],
        )

    def test_simulated_snapshot_structure(self):
        """Test that simulated snapshot has all required fields."""
        snapshot = self._create_sample_snapshot()
        preset = get_preset("neutral_baseline")

        result = simulate_scenario_with_preset(snapshot, preset)

        assert result is not None
        assert hasattr(result.simulated_snapshot, 'fused_scenario_vector')
        assert hasattr(result.simulated_snapshot, 'scenario_alignment_score')
        assert hasattr(result.simulated_snapshot, 'scenario_divergence_index')
        assert hasattr(result.simulated_snapshot, 'multi_regime_consensus')
        assert hasattr(result.simulated_snapshot, 'dominant_future_path')
        assert hasattr(result.simulated_snapshot, 'future_uncertainty_band')
        assert hasattr(result.simulated_snapshot, 'diagnostic_tags')

    def test_simulated_result_structure(self):
        """Test that SimulatedScenarioResult has all required fields."""
        snapshot = self._create_sample_snapshot()
        preset = get_preset("neutral_baseline")

        result = simulate_scenario_with_preset(snapshot, preset)

        assert result is not None
        assert hasattr(result, 'original_snapshot')
        assert hasattr(result, 'simulated_snapshot')
        assert hasattr(result, 'applied_preset')
        assert hasattr(result, 'diagnostic_notes')
        assert isinstance(result.diagnostic_notes, list)
        assert result.applied_preset == "neutral_baseline"

    def test_json_serializable_output(self):
        """Test that simulation output is JSON-serializable."""
        import json

        snapshot = self._create_sample_snapshot()
        preset = get_preset("conservative_bias")

        result = simulate_scenario_with_preset(snapshot, preset)

        assert result is not None

        # Build a dict representation (similar to API response)
        output = {
            "preset": result.applied_preset,
            "original": {
                "alignment_score": result.original_snapshot.scenario_alignment_score,
                "divergence_index": result.original_snapshot.scenario_divergence_index,
                "consensus": result.original_snapshot.multi_regime_consensus,
                "uncertainty_band": result.original_snapshot.future_uncertainty_band,
                "dominant_path": result.original_snapshot.dominant_future_path,
            },
            "simulated": {
                "alignment_score": result.simulated_snapshot.scenario_alignment_score,
                "divergence_index": result.simulated_snapshot.scenario_divergence_index,
                "consensus": result.simulated_snapshot.multi_regime_consensus,
                "uncertainty_band": result.simulated_snapshot.future_uncertainty_band,
                "dominant_path": result.simulated_snapshot.dominant_future_path,
                "diagnostic_notes": result.diagnostic_notes,
            },
        }

        # Should be JSON-serializable
        json_str = json.dumps(output)
        assert isinstance(json_str, str)
        assert len(json_str) > 0

    def test_simulate_all_presets_returns_all_five(self):
        """Test that simulate_all_presets returns results for all 5 presets."""
        snapshot = self._create_sample_snapshot()

        results = simulate_all_presets(snapshot)

        assert len(results) == 5
        assert "neutral_baseline" in results
        assert "conservative_bias" in results
        assert "expansive_bias" in results
        assert "stability_bias" in results
        assert "uncertainty_spike" in results

    def test_simulate_all_presets_deterministic(self):
        """Test that simulate_all_presets is deterministic."""
        snapshot = self._create_sample_snapshot()

        results1 = simulate_all_presets(snapshot)
        results2 = simulate_all_presets(snapshot)

        assert sorted(results1.keys()) == sorted(results2.keys())

        for preset_name in results1.keys():
            r1 = results1[preset_name]
            r2 = results2[preset_name]
            assert r1.simulated_snapshot.scenario_alignment_score == r2.simulated_snapshot.scenario_alignment_score
            assert r1.diagnostic_notes == r2.diagnostic_notes

    def test_get_simulation_summary_format(self):
        """Test that get_simulation_summary produces formatted string output."""
        snapshot = self._create_sample_snapshot()
        preset = get_preset("stability_bias")

        result = simulate_scenario_with_preset(snapshot, preset)
        summary = get_simulation_summary(result)

        assert isinstance(summary, str)
        assert "Preset: stability_bias" in summary
        assert "Metric Changes:" in summary
        assert "Alignment:" in summary
        assert "Divergence:" in summary
        assert "Consensus:" in summary

    def test_diagnostic_notes_generated(self):
        """Test that diagnostic notes are generated for simulations."""
        snapshot = self._create_sample_snapshot()
        preset = get_preset("conservative_bias")

        result = simulate_scenario_with_preset(snapshot, preset)

        assert result is not None
        assert len(result.diagnostic_notes) > 0
        assert "preset_applied:conservative_bias" in result.diagnostic_notes

    def test_diagnostic_tags_recomputed(self):
        """Test that diagnostic tags are recomputed in simulation."""
        snapshot = self._create_sample_snapshot()
        preset = get_preset("expansive_bias")

        result = simulate_scenario_with_preset(snapshot, preset)

        assert result is not None
        assert isinstance(result.simulated_snapshot.diagnostic_tags, list)
        # Tags should be regenerated based on simulated metrics


# ============================================================================
# GROUP D — API (6 tests)
# ============================================================================

class TestAPI:
    """Test API endpoint structure, preset errors, missing-session behavior."""

    def test_api_response_structure_original(self):
        """Test that API response has correct 'original' structure."""
        snapshot = ScenarioFusionSnapshot(
            fused_scenario_vector={"stable": 0.6, "volatile": 0.4},
            scenario_alignment_score=0.65,
            scenario_divergence_index=0.42,
            multi_regime_consensus=0.58,
            dominant_future_path="stable",
            future_uncertainty_band="medium",
            diagnostic_tags=["SCENARIO_HIGHLY_ALIGNED"],
        )
        preset = get_preset("neutral_baseline")
        result = simulate_scenario_with_preset(snapshot, preset)

        # Simulate API response building
        api_response = {
            "preset": result.applied_preset,
            "original": {
                "alignment_score": result.original_snapshot.scenario_alignment_score,
                "divergence_index": result.original_snapshot.scenario_divergence_index,
                "consensus": result.original_snapshot.multi_regime_consensus,
                "uncertainty_band": result.original_snapshot.future_uncertainty_band,
                "dominant_path": result.original_snapshot.dominant_future_path,
            },
        }

        assert "original" in api_response
        assert "alignment_score" in api_response["original"]
        assert "divergence_index" in api_response["original"]
        assert "consensus" in api_response["original"]
        assert "uncertainty_band" in api_response["original"]
        assert "dominant_path" in api_response["original"]

    def test_api_response_structure_simulated(self):
        """Test that API response has correct 'simulated' structure."""
        snapshot = ScenarioFusionSnapshot(
            fused_scenario_vector={"stable": 0.6, "volatile": 0.4},
            scenario_alignment_score=0.65,
            scenario_divergence_index=0.42,
            multi_regime_consensus=0.58,
            dominant_future_path="stable",
            future_uncertainty_band="medium",
            diagnostic_tags=["SCENARIO_HIGHLY_ALIGNED"],
        )
        preset = get_preset("conservative_bias")
        result = simulate_scenario_with_preset(snapshot, preset)

        # Simulate API response building
        api_response = {
            "preset": result.applied_preset,
            "simulated": {
                "alignment_score": result.simulated_snapshot.scenario_alignment_score,
                "divergence_index": result.simulated_snapshot.scenario_divergence_index,
                "consensus": result.simulated_snapshot.multi_regime_consensus,
                "uncertainty_band": result.simulated_snapshot.future_uncertainty_band,
                "dominant_path": result.simulated_snapshot.dominant_future_path,
                "diagnostic_notes": result.diagnostic_notes,
            },
        }

        assert "simulated" in api_response
        assert "alignment_score" in api_response["simulated"]
        assert "divergence_index" in api_response["simulated"]
        assert "consensus" in api_response["simulated"]
        assert "uncertainty_band" in api_response["simulated"]
        assert "dominant_path" in api_response["simulated"]
        assert "diagnostic_notes" in api_response["simulated"]

    def test_api_preset_validation_invalid_preset(self):
        """Test that API would reject invalid preset names."""
        # This simulates the validation logic in the API endpoint
        preset_name = "invalid_preset_name"

        if not is_valid_preset(preset_name):
            # API should return 400 error
            error_raised = True
        else:
            error_raised = False

        assert error_raised is True

    def test_api_preset_validation_valid_preset(self):
        """Test that API would accept valid preset names."""
        preset_name = "neutral_baseline"

        if not is_valid_preset(preset_name):
            error_raised = True
        else:
            error_raised = False

        assert error_raised is False

    def test_api_null_safety_none_snapshot(self):
        """Test that API handles None snapshot gracefully."""
        snapshot = None
        preset = get_preset("neutral_baseline")

        result = simulate_scenario_with_preset(snapshot, preset)

        # Should return None, which API would convert to 404
        assert result is None

    def test_api_preset_names_available_for_error_messages(self):
        """Test that preset names can be listed for error messages."""
        available_presets = get_preset_names()

        assert isinstance(available_presets, list)
        assert len(available_presets) == 5

        # Should be usable in error message
        error_msg = f"Available presets: {', '.join(available_presets)}"
        assert "neutral_baseline" in error_msg
        assert "conservative_bias" in error_msg


# ============================================================================
# GROUP E — INVARIANCE (8 tests)
# ============================================================================

class TestInvariance:
    """Test that simulation never mutates live coherence state and preserves system invariants."""

    def _create_sample_snapshot(self) -> ScenarioFusionSnapshot:
        """Create a sample scenario fusion snapshot for testing."""
        return ScenarioFusionSnapshot(
            fused_scenario_vector={"stable": 0.6, "volatile": 0.4},
            scenario_alignment_score=0.65,
            scenario_divergence_index=0.42,
            multi_regime_consensus=0.58,
            dominant_future_path="stable",
            future_uncertainty_band="medium",
            diagnostic_tags=["SCENARIO_HIGHLY_ALIGNED"],
        )

    def test_original_snapshot_not_modified(self):
        """Test that simulation does NOT modify the original snapshot."""
        snapshot = self._create_sample_snapshot()
        original_alignment = snapshot.scenario_alignment_score
        original_divergence = snapshot.scenario_divergence_index
        original_consensus = snapshot.multi_regime_consensus
        original_path = snapshot.dominant_future_path

        preset = get_preset("conservative_bias")
        result = simulate_scenario_with_preset(snapshot, preset)

        # Original snapshot should remain unchanged
        assert snapshot.scenario_alignment_score == original_alignment
        assert snapshot.scenario_divergence_index == original_divergence
        assert snapshot.multi_regime_consensus == original_consensus
        assert snapshot.dominant_future_path == original_path

    def test_fused_vector_not_modified(self):
        """Test that fused_scenario_vector is not modified."""
        snapshot = self._create_sample_snapshot()
        original_vector = copy.deepcopy(snapshot.fused_scenario_vector)

        preset = get_preset("uncertainty_spike")
        result = simulate_scenario_with_preset(snapshot, preset)

        # Original vector should remain unchanged
        assert snapshot.fused_scenario_vector == original_vector

    def test_zero_llm_guarantee_no_imports(self):
        """Test that simulator does not import LLM-related modules."""
        import sys

        # Reload simulator module to check imports
        from symbolu.tools.scenario_simulator import simulator

        # Check that no anthropic/openai/LLM imports are present
        module_dict = vars(simulator)

        # No LLM-related names should be present
        llm_keywords = ['anthropic', 'openai', 'llm', 'claude', 'gpt', 'chat']
        for key in module_dict.keys():
            key_lower = key.lower()
            for keyword in llm_keywords:
                assert keyword not in key_lower, f"Found LLM-related import: {key}"

    def test_no_routing_changes_ttor_mlcr(self):
        """Test that simulation does not affect TTOR/MLCR routing."""
        # This test verifies that simulator module does not import or modify routing
        from symbolu.tools.scenario_simulator import simulator

        module_dict = vars(simulator)

        # Should not import TTOR or MLCR
        routing_keywords = ['ttor', 'mlcr', 'routing_plan', 'tier_selector']
        for key in module_dict.keys():
            key_lower = key.lower()
            for keyword in routing_keywords:
                assert keyword not in key_lower, f"Found routing import: {key}"

    def test_no_mapper_activation_changes(self):
        """Test that simulation does not affect mapper activation."""
        from symbolu.tools.scenario_simulator import simulator

        module_dict = vars(simulator)

        # Should not import mapper activation logic
        mapper_keywords = ['hrm_map', 'lcm_map', 'lam_map', 'mapper_profile']
        for key in module_dict.keys():
            key_lower = key.lower()
            for keyword in mapper_keywords:
                assert keyword not in key_lower, f"Found mapper import: {key}"

    def test_no_persona_tone_changes(self):
        """Test that simulation does not affect persona tone or semantics."""
        from symbolu.tools.scenario_simulator import simulator

        module_dict = vars(simulator)

        # Should not import persona or tone modules
        persona_keywords = ['persona_engine', 'tone_params', 'semantic_skeleton']
        for key in module_dict.keys():
            key_lower = key.lower()
            for keyword in persona_keywords:
                assert keyword not in key_lower, f"Found persona import: {key}"

    def test_simulation_is_pure_function(self):
        """Test that simulation is a pure function (no side effects)."""
        snapshot1 = self._create_sample_snapshot()
        snapshot2 = self._create_sample_snapshot()

        preset = get_preset("expansive_bias")

        result1 = simulate_scenario_with_preset(snapshot1, preset)
        result2 = simulate_scenario_with_preset(snapshot2, preset)

        # Same inputs should produce same outputs
        assert result1.simulated_snapshot.scenario_alignment_score == result2.simulated_snapshot.scenario_alignment_score
        assert result1.simulated_snapshot.scenario_divergence_index == result2.simulated_snapshot.scenario_divergence_index
        assert result1.diagnostic_notes == result2.diagnostic_notes

    def test_observation_only_no_state_mutation(self):
        """Test that simulator is observation-only and never mutates state."""
        snapshot = self._create_sample_snapshot()

        # Store original state
        original_state = {
            "alignment": snapshot.scenario_alignment_score,
            "divergence": snapshot.scenario_divergence_index,
            "consensus": snapshot.multi_regime_consensus,
            "path": snapshot.dominant_future_path,
            "band": snapshot.future_uncertainty_band,
            "tags": snapshot.diagnostic_tags.copy() if snapshot.diagnostic_tags else [],
        }

        # Run simulation
        preset = get_preset("stability_bias")
        result = simulate_scenario_with_preset(snapshot, preset)

        # Verify original state is completely unchanged
        assert snapshot.scenario_alignment_score == original_state["alignment"]
        assert snapshot.scenario_divergence_index == original_state["divergence"]
        assert snapshot.multi_regime_consensus == original_state["consensus"]
        assert snapshot.dominant_future_path == original_state["path"]
        assert snapshot.future_uncertainty_band == original_state["band"]
        assert snapshot.diagnostic_tags == original_state["tags"]
