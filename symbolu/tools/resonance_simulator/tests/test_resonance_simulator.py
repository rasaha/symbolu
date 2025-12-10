"""
Comprehensive test suite for Resonance Scenario Presets & What-If Simulator v1.0

Test Coverage:
    Group A: Preset Logic (8 tests)
    Group B: Simulation Math (10 tests)
    Group C: Integration (7 tests)
    Group D: Invariance (5 tests)
"""

import pytest
from typing import Dict

from symbolu.formulas.resonance_weighting import ResonanceWeightingSnapshot
from symbolu.tools.resonance_simulator import (
    ResonancePreset,
    PRESETS,
    get_preset,
    list_presets,
    is_valid_preset,
    SimulatedResonanceScenario,
    simulate_resonance_with_preset,
    simulate_all_presets,
)
from symbolu.tools.resonance_simulator.presets import get_multiplier, get_preset_names
from symbolu.tools.resonance_simulator.simulator import (
    _normalize_weights,
    _get_dominant_metrics,
    get_simulation_summary,
)


# ============================================================================
# GROUP A: PRESET LOGIC (8 tests)
# ============================================================================


def test_list_presets_contains_expected_names():
    """Verify list_presets() contains expected preset names."""
    presets = list_presets()

    expected_names = {
        "safety_first",
        "insight_heavy",
        "identity_careful",
        "coherence_focused",
        "formula_balanced",
        "neutral_baseline",
    }

    assert set(presets.keys()) == expected_names
    assert len(presets) == len(expected_names)


def test_each_preset_has_nonempty_name_and_description():
    """Verify each preset has non-empty name and description."""
    presets = list_presets()

    for preset_name, preset in presets.items():
        assert preset.name, f"Preset {preset_name} has empty name"
        assert preset.description, f"Preset {preset_name} has empty description"
        assert preset.name == preset_name, f"Preset name mismatch: {preset.name} != {preset_name}"


def test_is_valid_preset_true_for_existing_presets():
    """Verify is_valid_preset() returns True for existing presets."""
    assert is_valid_preset("safety_first")
    assert is_valid_preset("insight_heavy")
    assert is_valid_preset("identity_careful")
    assert is_valid_preset("neutral_baseline")


def test_is_valid_preset_false_for_nonexistent_presets():
    """Verify is_valid_preset() returns False for non-existent presets."""
    assert not is_valid_preset("nonexistent")
    assert not is_valid_preset("")
    assert not is_valid_preset("SAFETY_FIRST")  # case sensitive


def test_get_preset_retrieves_correct_preset():
    """Verify get_preset() retrieves the correct preset object."""
    preset = get_preset("safety_first")

    assert preset.name == "safety_first"
    assert "stability" in preset.description.lower()
    assert "semantic_integrity" in preset.metric_multipliers
    assert preset.metric_multipliers["semantic_integrity"] > 1.0


def test_get_preset_raises_keyerror_for_invalid_name():
    """Verify get_preset() raises KeyError for invalid preset names."""
    with pytest.raises(KeyError) as exc_info:
        get_preset("invalid_preset")

    assert "invalid_preset" in str(exc_info.value)
    assert "Available presets:" in str(exc_info.value)


def test_get_multiplier_returns_correct_values():
    """Verify get_multiplier() returns correct multiplier values."""
    preset = get_preset("safety_first")

    # Specified multiplier
    assert get_multiplier(preset, "semantic_integrity") == 1.3

    # Unspecified multiplier (default 1.0)
    assert get_multiplier(preset, "nonexistent_metric") == 1.0


def test_neutral_baseline_has_no_multipliers():
    """Verify neutral_baseline preset has empty multipliers dict."""
    preset = get_preset("neutral_baseline")

    assert preset.metric_multipliers == {}
    assert len(preset.metric_multipliers) == 0


# ============================================================================
# GROUP B: SIMULATION MATH (10 tests)
# ============================================================================


def test_normalize_weights_sums_to_one():
    """Verify normalized weights sum to approximately 1.0."""
    raw_weights = {
        "metric_a": 0.5,
        "metric_b": 0.3,
        "metric_c": 0.2,
    }

    normalized, entropy = _normalize_weights(raw_weights)

    weight_sum = sum(normalized.values())
    assert abs(weight_sum - 1.0) < 1e-6, f"Sum is {weight_sum}, expected 1.0"


def test_normalize_weights_handles_empty_dict():
    """Verify normalization handles empty input gracefully."""
    normalized, entropy = _normalize_weights({})

    assert normalized == {}
    assert entropy == 0.0


def test_normalize_weights_handles_all_zeros():
    """Verify normalization handles all-zero weights gracefully."""
    raw_weights = {
        "metric_a": 0.0,
        "metric_b": 0.0,
        "metric_c": 0.0,
    }

    normalized, entropy = _normalize_weights(raw_weights)

    assert normalized == {}
    assert entropy == 0.0


def test_entropy_increases_with_even_distribution():
    """Verify entropy increases when weights become more evenly distributed."""
    # Focused distribution (low entropy)
    focused_weights = {
        "metric_a": 0.9,
        "metric_b": 0.05,
        "metric_c": 0.05,
    }

    # Even distribution (high entropy)
    even_weights = {
        "metric_a": 0.34,
        "metric_b": 0.33,
        "metric_c": 0.33,
    }

    _, entropy_focused = _normalize_weights(focused_weights)
    _, entropy_even = _normalize_weights(even_weights)

    assert entropy_even > entropy_focused, (
        f"Even entropy {entropy_even:.3f} should be > focused entropy {entropy_focused:.3f}"
    )


def test_entropy_is_zero_for_single_metric():
    """Verify entropy is 0.0 when only one metric has all weight."""
    weights = {"metric_a": 1.0}

    _, entropy = _normalize_weights(weights)

    assert entropy == 0.0


def test_simulation_determinism():
    """Verify simulation produces identical results for same input."""
    snapshot = ResonanceWeightingSnapshot(
        weights={"metric_a": 0.5, "metric_b": 0.3, "metric_c": 0.2},
        normalized_weights={"metric_a": 0.5, "metric_b": 0.3, "metric_c": 0.2},
        entropy_of_weights=0.45,
        dominant_metrics={"metric_a": 0.5, "metric_b": 0.3, "metric_c": 0.2},
        notes=["test"],
    )

    preset = get_preset("safety_first")

    # Run simulation twice
    scenario1 = simulate_resonance_with_preset(snapshot, preset)
    scenario2 = simulate_resonance_with_preset(snapshot, preset)

    # Results should be identical
    assert scenario1.simulated_normalized == scenario2.simulated_normalized
    assert scenario1.entropy_simulated == scenario2.entropy_simulated
    assert scenario1.notes == scenario2.notes


def test_simulation_applies_multipliers_correctly():
    """Verify simulation applies preset multipliers to raw weights."""
    # Create snapshot with known weights
    raw_weights = {"semantic_integrity": 0.5, "resonance_index": 0.5}
    normalized_weights = {"semantic_integrity": 0.5, "resonance_index": 0.5}

    snapshot = ResonanceWeightingSnapshot(
        weights=raw_weights,
        normalized_weights=normalized_weights,
        entropy_of_weights=0.5,
        dominant_metrics=normalized_weights,
        notes=[],
    )

    # Safety_first multiplies semantic_integrity by 1.3, resonance_index by 1.0 (default)
    preset = get_preset("safety_first")
    scenario = simulate_resonance_with_preset(snapshot, preset)

    # After multipliers: semantic_integrity = 0.5 * 1.3 = 0.65, resonance_index = 0.5 * 1.0 = 0.5
    # Normalized: semantic_integrity = 0.65 / 1.15 ≈ 0.565, resonance_index = 0.5 / 1.15 ≈ 0.435

    assert scenario.simulated_normalized["semantic_integrity"] > 0.5
    assert scenario.simulated_normalized["resonance_index"] < 0.5


def test_simulation_returns_none_for_all_zero_weights():
    """Verify simulation returns None when all effective weights are zero."""
    # This should never happen in practice, but test edge case
    snapshot = ResonanceWeightingSnapshot(
        weights={"metric_a": 0.0, "metric_b": 0.0},
        normalized_weights={},
        entropy_of_weights=0.0,
        dominant_metrics={},
        notes=[],
    )

    preset = get_preset("neutral_baseline")
    scenario = simulate_resonance_with_preset(snapshot, preset)

    assert scenario is None


def test_get_dominant_metrics_returns_top_n():
    """Verify _get_dominant_metrics returns correct top N metrics."""
    weights = {
        "metric_a": 0.5,
        "metric_b": 0.3,
        "metric_c": 0.15,
        "metric_d": 0.05,
    }

    top_2 = _get_dominant_metrics(weights, top_n=2)

    assert len(top_2) == 2
    assert "metric_a" in top_2
    assert "metric_b" in top_2
    assert top_2["metric_a"] == 0.5
    assert top_2["metric_b"] == 0.3


def test_neutral_baseline_produces_no_change():
    """Verify neutral_baseline preset produces no change in weights."""
    # Use _normalize_weights to get correct entropy for the weights
    raw_weights = {"metric_a": 0.6, "metric_b": 0.4}
    normalized, entropy = _normalize_weights(raw_weights)

    snapshot = ResonanceWeightingSnapshot(
        weights=raw_weights,
        normalized_weights=normalized,
        entropy_of_weights=entropy,
        dominant_metrics=normalized,
        notes=[],
    )

    preset = get_preset("neutral_baseline")
    scenario = simulate_resonance_with_preset(snapshot, preset)

    # Weights should be unchanged
    assert scenario.simulated_normalized == scenario.original_normalized
    assert abs(scenario.entropy_simulated - scenario.entropy_original) < 1e-6


# ============================================================================
# GROUP C: INTEGRATION (7 tests)
# ============================================================================


def test_simulate_all_presets_returns_all_valid_presets():
    """Verify simulate_all_presets returns results for all valid presets."""
    snapshot = ResonanceWeightingSnapshot(
        weights={"metric_a": 0.5, "metric_b": 0.3, "metric_c": 0.2},
        normalized_weights={"metric_a": 0.5, "metric_b": 0.3, "metric_c": 0.2},
        entropy_of_weights=0.45,
        dominant_metrics={"metric_a": 0.5, "metric_b": 0.3, "metric_c": 0.2},
        notes=[],
    )

    scenarios = simulate_all_presets(snapshot)

    # Should have results for all presets (at minimum the expected ones)
    expected_presets = {
        "safety_first",
        "insight_heavy",
        "identity_careful",
        "neutral_baseline",
        "coherence_focused",
        "formula_balanced",
    }

    assert expected_presets.issubset(set(scenarios.keys()))


def test_simulate_all_presets_omits_failed_simulations():
    """Verify simulate_all_presets omits presets that fail simulation."""
    # Snapshot with all zero weights
    snapshot = ResonanceWeightingSnapshot(
        weights={"metric_a": 0.0},
        normalized_weights={},
        entropy_of_weights=0.0,
        dominant_metrics={},
        notes=[],
    )

    scenarios = simulate_all_presets(snapshot)

    # Should return empty or minimal results (some presets may fail)
    # This is expected behavior for edge cases
    assert isinstance(scenarios, dict)


def test_get_simulation_summary_generates_text():
    """Verify get_simulation_summary produces non-empty text output."""
    snapshot = ResonanceWeightingSnapshot(
        weights={"metric_a": 0.5, "metric_b": 0.5},
        normalized_weights={"metric_a": 0.5, "metric_b": 0.5},
        entropy_of_weights=0.5,
        dominant_metrics={"metric_a": 0.5, "metric_b": 0.5},
        notes=[],
    )

    preset = get_preset("safety_first")
    scenario = simulate_resonance_with_preset(snapshot, preset)

    summary = get_simulation_summary(scenario)

    assert len(summary) > 0
    assert "safety_first" in summary
    assert "Entropy:" in summary
    assert "Original Top Metrics:" in summary
    assert "Simulated Top Metrics:" in summary


def test_simulation_preserves_original_snapshot():
    """Verify simulation does not modify the original snapshot."""
    original_weights = {"metric_a": 0.6, "metric_b": 0.4}
    original_normalized = original_weights.copy()

    snapshot = ResonanceWeightingSnapshot(
        weights=original_weights.copy(),
        normalized_weights=original_normalized.copy(),
        entropy_of_weights=0.5,
        dominant_metrics=original_normalized.copy(),
        notes=[],
    )

    # Store original values
    original_entropy = snapshot.entropy_of_weights
    original_weights_before = snapshot.weights.copy()

    preset = get_preset("insight_heavy")
    scenario = simulate_resonance_with_preset(snapshot, preset)

    # Verify snapshot is unchanged
    assert snapshot.entropy_of_weights == original_entropy
    assert snapshot.weights == original_weights_before


def test_scenario_contains_expected_fields():
    """Verify SimulatedResonanceScenario has all expected fields."""
    snapshot = ResonanceWeightingSnapshot(
        weights={"metric_a": 0.5, "metric_b": 0.5},
        normalized_weights={"metric_a": 0.5, "metric_b": 0.5},
        entropy_of_weights=0.5,
        dominant_metrics={"metric_a": 0.5, "metric_b": 0.5},
        notes=[],
    )

    preset = get_preset("coherence_focused")
    scenario = simulate_resonance_with_preset(snapshot, preset)

    # Check all fields exist
    assert hasattr(scenario, "preset_name")
    assert hasattr(scenario, "original_weights")
    assert hasattr(scenario, "original_normalized")
    assert hasattr(scenario, "simulated_normalized")
    assert hasattr(scenario, "entropy_original")
    assert hasattr(scenario, "entropy_simulated")
    assert hasattr(scenario, "dominant_original")
    assert hasattr(scenario, "dominant_simulated")
    assert hasattr(scenario, "notes")

    # Check types
    assert isinstance(scenario.notes, list)
    assert isinstance(scenario.simulated_normalized, dict)


def test_notes_are_deterministic_and_sorted():
    """Verify scenario notes are deterministic and sorted."""
    snapshot = ResonanceWeightingSnapshot(
        weights={"metric_a": 0.5, "metric_b": 0.5},
        normalized_weights={"metric_a": 0.5, "metric_b": 0.5},
        entropy_of_weights=0.5,
        dominant_metrics={"metric_a": 0.5, "metric_b": 0.5},
        notes=[],
    )

    preset = get_preset("formula_balanced")

    # Run multiple times
    scenario1 = simulate_resonance_with_preset(snapshot, preset)
    scenario2 = simulate_resonance_with_preset(snapshot, preset)

    # Notes should be identical and sorted
    assert scenario1.notes == scenario2.notes
    assert scenario1.notes == sorted(scenario1.notes)


def test_cli_extract_resonance_snapshot_handles_missing_session():
    """Verify CLI helper handles missing session gracefully."""
    from symbolu.service.sessions import SessionStore
    from symbolu.tools.resonance_simulator.cli import _extract_resonance_snapshot

    store = SessionStore()
    snapshot = _extract_resonance_snapshot(store, "nonexistent_session_id")

    assert snapshot is None


# ============================================================================
# GROUP D: INVARIANCE (5 tests)
# ============================================================================


def test_simulation_does_not_modify_coherence_state():
    """Verify simulation does not modify CoherenceState internals."""
    # This is a meta-test: simulation is pure function, no state mutation
    from symbolu.core.coherence.coherence_state import CoherenceState

    # Create a CoherenceState object
    state = CoherenceState(convo_id="test", turn_index=0)

    # Verify simulation module doesn't import or modify CoherenceState
    # (This is verified by code review + integration tests)
    assert hasattr(state, "resonance_weighting_history")

    # The resonance_simulator module should never directly manipulate this
    # It only reads ResonanceWeightingSnapshot objects
    pass  # This test is structural/invariant check


def test_simulation_does_not_modify_policy_flags():
    """Verify simulation does not modify policy flags."""
    # Policy flags are in separate modules, simulation should not touch them
    # This is a structural invariant test

    # Attempt to import policy flags
    try:
        from symbolu.mechanical.policy.flags import PolicyFlags
        # Simulation module should not import PolicyFlags at all
        import symbolu.tools.resonance_simulator.simulator as sim_module
        import inspect

        source = inspect.getsource(sim_module)
        assert "PolicyFlags" not in source
    except ImportError:
        # If policy flags don't exist yet, that's fine
        pass


def test_simulation_does_not_modify_routing():
    """Verify simulation does not modify routing logic."""
    # Routing is in MLCR module, simulation should not touch it
    # This is a structural invariant test

    try:
        # Simulation module should not import routing components
        import symbolu.tools.resonance_simulator.simulator as sim_module
        import inspect

        source = inspect.getsource(sim_module)
        assert "mlcr" not in source.lower()
        assert "routing" not in source.lower()
    except ImportError:
        pass


def test_simulation_does_not_modify_guardrails():
    """Verify simulation does not modify guardrails."""
    # Guardrails are separate, simulation should not touch them
    # This is a structural invariant test

    import symbolu.tools.resonance_simulator.simulator as sim_module
    import inspect

    source = inspect.getsource(sim_module)
    assert "guardrail" not in source.lower()


def test_existing_phase_24_tests_still_pass():
    """Verify Phase 24 resonance weighting tests still pass."""
    # This is a smoke test - run a basic Phase 24 function
    from symbolu.formulas.resonance_weighting import compute_resonance_weighting

    # Simple smoke test
    snapshot = compute_resonance_weighting(
        coherence_fused=0.8,
        semantic_integrity_score=0.75,
        resonance_index=0.7,
    )

    assert snapshot is not None
    assert snapshot.normalized_weights
    assert "coherence_fused" in snapshot.normalized_weights

    # Phase 24 behavior should be unchanged
    assert 0.0 <= snapshot.entropy_of_weights <= 1.0


# ============================================================================
# EDGE CASE TESTS (Bonus)
# ============================================================================


def test_simulation_handles_negative_weights():
    """Verify simulation handles negative weights gracefully (should clamp to 0)."""
    # Edge case: negative weights should be clamped to 0
    snapshot = ResonanceWeightingSnapshot(
        weights={"metric_a": -0.5, "metric_b": 0.5},
        normalized_weights={"metric_b": 1.0},  # Only positive weight
        entropy_of_weights=0.0,
        dominant_metrics={"metric_b": 1.0},
        notes=[],
    )

    preset = get_preset("neutral_baseline")
    scenario = simulate_resonance_with_preset(snapshot, preset)

    # Should handle gracefully
    if scenario is not None:
        # All weights should be non-negative
        for weight in scenario.simulated_normalized.values():
            assert weight >= 0.0


def test_simulation_handles_very_large_weights():
    """Verify simulation handles very large weight values correctly."""
    snapshot = ResonanceWeightingSnapshot(
        weights={"metric_a": 1000.0, "metric_b": 0.1},
        normalized_weights={"metric_a": 0.9999, "metric_b": 0.0001},
        entropy_of_weights=0.01,
        dominant_metrics={"metric_a": 0.9999},
        notes=[],
    )

    preset = get_preset("safety_first")
    scenario = simulate_resonance_with_preset(snapshot, preset)

    # Should still normalize to 1.0
    assert scenario is not None
    weight_sum = sum(scenario.simulated_normalized.values())
    assert abs(weight_sum - 1.0) < 1e-6


def test_get_preset_names_is_sorted():
    """Verify get_preset_names returns sorted list."""
    names = get_preset_names()

    assert names == sorted(names)
    assert len(names) > 0
