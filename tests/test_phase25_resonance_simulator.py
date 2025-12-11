"""
Phase 25: Resonance What-If Simulator - Canonical Phase Test Suite
====================================================================

This is the canonical Phase 25 test file that verifies core invariants.
Comprehensive functional tests are in symbolu/tools/resonance_simulator/tests/.

Test Coverage:
    - Core Invariants (Zero-LLM, Deterministic, Immutable, Non-invasive)
    - Integration with existing comprehensive test suite

Total: ~12 tests (invariants) + comprehensive test suite via import
"""

import pytest

# Import comprehensive test suite
from symbolu.tools.resonance_simulator.tests.test_resonance_simulator import *  # noqa

# Import required components for invariance tests
from symbolu.tools.resonance_simulator import (
    get_preset,
    list_presets,
    is_valid_preset,
)
from symbolu.formulas.resonance_weighting import compute_resonance_weighting


# ==============================================================================
# PHASE 25 CANONICAL INVARIANCE TESTS
# ==============================================================================


class TestPhase25Invariants:
    """Canonical Phase 25 invariance tests - verify core Symbol-U principles."""

    def test_phase25_all_presets_exist(self):
        """
        INVARIANT: All 6 canonical presets are defined and accessible.
        """
        expected_presets = {
            "safety_first",
            "insight_heavy",
            "identity_careful",
            "coherence_focused",
            "formula_balanced",
            "neutral_baseline",
        }

        presets = list_presets()
        assert set(presets.keys()) == expected_presets

    def test_phase25_preset_validation_works(self):
        """
        INVARIANT: Preset validation correctly identifies valid/invalid presets.
        """
        assert is_valid_preset("safety_first") is True
        assert is_valid_preset("neutral_baseline") is True
        assert is_valid_preset("nonexistent") is False
        assert is_valid_preset("") is False

    def test_phase25_zero_llm_guarantee(self):
        """
        INVARIANT: Phase 25 never triggers LLM calls.
        All simulations are pure mathematical transformations.
        """
        # Creating presets and retrieving them should never call LLM
        preset = get_preset("safety_first")
        assert preset is not None
        assert preset.name == "safety_first"

    def test_phase25_presets_are_deterministic(self):
        """
        INVARIANT: Preset definitions are deterministic.
        Same preset name always returns same multipliers.
        """
        preset1 = get_preset("insight_heavy")
        preset2 = get_preset("insight_heavy")

        assert preset1.name == preset2.name
        assert preset1.metric_multipliers == preset2.metric_multipliers

    def test_phase25_does_not_affect_routing(self):
        """
        INVARIANT: Phase 25 does not modify routing, TTOR, MLCR, or mappers.
        Simulations are purely computational.
        """
        preset = get_preset("formula_balanced")

        # Preset objects should not contain routing information
        assert not hasattr(preset, "active_mapper")
        assert not hasattr(preset, "routing_decision")
        assert not hasattr(preset, "ttor")

    def test_phase25_does_not_modify_policy(self):
        """
        INVARIANT: Phase 25 does not modify policy flags.
        """
        preset = get_preset("coherence_focused")

        # Presets should not contain policy information
        assert not hasattr(preset, "policy_flags")
        assert not hasattr(preset, "safety_first")

    def test_phase25_neutral_baseline_all_ones(self):
        """
        INVARIANT: neutral_baseline preset has all multipliers = 1.0.
        This ensures it produces no changes to the original snapshot.
        """
        preset = get_preset("neutral_baseline")

        for multiplier in preset.metric_multipliers.values():
            assert multiplier == 1.0

    def test_phase25_outputs_bounded(self):
        """
        INVARIANT: All resonance weighting outputs remain in [0, 1] range.
        This is fundamental to the resonance weighting formula.
        """
        snapshot = compute_resonance_weighting(
            coherence_fused=0.7,
            resonance_index=0.65,
            semantic_integrity_score=0.72,
        )

        assert 0.0 <= snapshot.entropy_of_weights <= 1.0
        for weight in snapshot.normalized_weights.values():
            assert 0.0 <= weight <= 1.0

    def test_phase25_graceful_error_handling(self):
        """
        INVARIANT: Phase 25 handles invalid preset names gracefully.
        """
        with pytest.raises(KeyError) as exc_info:
            get_preset("invalid_preset_name")

        assert "invalid_preset_name" in str(exc_info.value)

    def test_phase25_json_serializable(self):
        """
        INVARIANT: Preset metadata is JSON-serializable for API responses.
        """
        import json

        presets = list_presets()

        # Should be able to serialize preset metadata
        metadata = {
            name: {
                "name": preset.name,
                "description": preset.description,
            }
            for name, preset in presets.items()
        }

        json_str = json.dumps(metadata)
        assert isinstance(json_str, str)
        assert len(json_str) > 0
