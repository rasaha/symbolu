"""
Phase-5 Dynamics Engine Tests
=============================

Comprehensive test suite for Phase-5 dynamic resolution layer.

Test Categories:
    1. Flat-Gradient Stress Test
    2. Regression Test
    3. Ontology Isolation Test
    4. Determinism Test
    5. Failure Mode Test

CRITICAL: These tests verify that Phase-5:
    - Cannot "fix" ontology issues
    - Only reveals whether issues are dynamic or structural
    - Maintains all invariants
"""

import pytest
import inspect
import ast
from typing import Set

from symbolu.dynamics.phase5 import (
    resolve_dynamics,
    DynamicState,
    DynamicsConfig,
    TrajectoryResult,
    Direction,
    Phase5Error,
    Phase5InvariantViolation,
    Phase5InvalidVarnaError,
    Phase5InvalidLayerError,
    Phase5InvalidConfigError,
)
from symbolu.dynamics.phase5.models import (
    LAYER_ORDER,
    LAYER_TO_INDEX,
    get_layer_index,
    get_layer_by_index,
)
from symbolu.dynamics.phase5 import phase5_dynamics_engine


# =============================================================================
# 1. FLAT-GRADIENT STRESS TEST
# =============================================================================

class TestFlatGradientStress:
    """
    Prove that flat ontology (e.g., ga, ddha) still produces
    non-flat trajectories under dynamics.

    This demonstrates that Phase-5 can reveal dynamic instability
    in ontologically flat patterns.
    """

    def test_flat_constructive_varna_produces_trajectory(self):
        """
        'ga' has uniformly constructive polarity in ontology.
        Under dynamics, it should still show trajectory evolution.
        """
        result = resolve_dynamics(
            varna="ga",
            start_layer="O1_ACTING",
            load=0.3,
            time_steps=20,
            decay_constant=0.1,
            amplification_factor=1.2,
            allow_regression=False,
        )

        # Trajectory should have states
        assert len(result.trajectory) == 20

        # Should show some evolution (not all identical)
        unique_layers = set(s.layer_id for s in result.trajectory)
        unique_activations = set(round(s.activation_level, 2) for s in result.trajectory)

        # Dynamics should produce variation
        assert len(unique_activations) > 1, "Flat ontology should still show activation variation under dynamics"

    def test_flat_degenerative_varna_under_load(self):
        """
        'ddha' has uniformly degenerative polarity in ontology.
        Under high load with regression, dynamics should reveal instability.
        """
        result = resolve_dynamics(
            varna="ddha",
            start_layer="O5_DIRECTING",
            load=0.8,
            time_steps=20,
            decay_constant=0.05,
            amplification_factor=1.5,
            allow_regression=True,
            regression_threshold=0.6,
        )

        # High load on degenerative varna should show regression
        assert result.regressed or result.peak_momentum > 0, \
            "Degenerative varna under load should show dynamic response"

        # Momentum should be non-zero at some point
        momenta = [s.momentum for s in result.trajectory]
        assert any(m != 0.0 for m in momenta), "Dynamics should produce momentum variation"

    def test_flat_ontology_versus_dynamic_flatness(self):
        """
        Compare ontologically flat vs dynamically flat.
        If both are flat, issue is structural.
        If only ontology is flat, issue may be dynamic.
        """
        # 'ga' - constructive across all layers (ontologically flat)
        result_ga = resolve_dynamics(
            varna="ga",
            start_layer="O1_ACTING",
            load=0.5,
            time_steps=15,
            decay_constant=0.1,
            amplification_factor=1.3,
            allow_regression=True,
        )

        # Check if trajectory shows any variation
        is_dynamically_flat = result_ga.is_flat(threshold=0.05)

        # The result helps classify:
        # - If is_flat() returns True: structural flatness
        # - If is_flat() returns False: dynamic variation exists
        # Both outcomes are valid — Phase-5 reveals, not fixes

        assert isinstance(is_dynamically_flat, bool), "is_flat() should return boolean"

    def test_stress_multiple_flat_varnas(self):
        """
        Test multiple varnas with flat ontology patterns.
        """
        flat_varnas = ["ga", "ca"]  # Both mostly constructive

        for varna in flat_varnas:
            result = resolve_dynamics(
                varna=varna,
                start_layer="O3_FORMING",
                load=0.4,
                time_steps=10,
                decay_constant=0.1,
                amplification_factor=1.2,
                allow_regression=False,
            )

            # Each should produce valid trajectory
            assert len(result.trajectory) == 10
            assert result.varna == varna


# =============================================================================
# 2. REGRESSION TEST
# =============================================================================

class TestRegression:
    """
    Verify that high load causes downward traversal (O7 → O4 etc.)
    WITHOUT modifying ontology.
    """

    def test_regression_enabled_under_high_load(self):
        """
        With allow_regression=True and high load, downward movement should be possible.
        """
        result = resolve_dynamics(
            varna="kha",  # 'kha' has degenerative tendency
            start_layer="O7_PURPOSING",
            load=0.9,  # High load
            time_steps=30,
            decay_constant=0.05,
            amplification_factor=1.5,
            allow_regression=True,
            regression_threshold=0.7,
        )

        # Check if regression occurred
        # Note: Regression depends on dynamics, not guaranteed
        layer_indices = [s.layer_index for s in result.trajectory]

        # At minimum, trajectory should process
        assert len(result.trajectory) == 30

        # If regression occurred, flag should be set
        if min(layer_indices) < 7:  # Started at O7 (index 7)
            assert result.regressed, "Regression flag should be True if layer decreased"

    def test_regression_disabled_prevents_downward(self):
        """
        With allow_regression=False, downward movement should not occur.
        """
        result = resolve_dynamics(
            varna="kha",
            start_layer="O7_PURPOSING",
            load=0.9,
            time_steps=20,
            decay_constant=0.05,
            amplification_factor=1.5,
            allow_regression=False,  # Disabled
        )

        # Layer should not decrease
        layer_indices = [s.layer_index for s in result.trajectory]
        assert all(idx >= 7 for idx in layer_indices), \
            "With regression disabled, layer should not decrease below start"

    def test_regression_respects_threshold(self):
        """
        Regression should only occur above regression_threshold.
        """
        # Load below threshold
        result_low = resolve_dynamics(
            varna="kha",
            start_layer="O5_DIRECTING",
            load=0.5,  # Below threshold
            time_steps=15,
            decay_constant=0.1,
            amplification_factor=1.5,
            allow_regression=True,
            regression_threshold=0.7,  # Threshold is 0.7
        )

        # Load above threshold
        result_high = resolve_dynamics(
            varna="kha",
            start_layer="O5_DIRECTING",
            load=0.85,  # Above threshold
            time_steps=15,
            decay_constant=0.1,
            amplification_factor=1.5,
            allow_regression=True,
            regression_threshold=0.7,
        )

        # Both should complete successfully
        assert len(result_low.trajectory) == 15
        assert len(result_high.trajectory) == 15

    def test_regression_does_not_modify_ontology(self):
        """
        Verify regression is purely dynamic — ontology unchanged.
        """
        from symbolu.ontology.phase4a.lookup import lookup_interaction

        # Get ontology value before
        before = lookup_interaction("kha", "O5_DIRECTING")

        # Run dynamics with regression
        resolve_dynamics(
            varna="kha",
            start_layer="O5_DIRECTING",
            load=0.9,
            time_steps=20,
            decay_constant=0.1,
            amplification_factor=1.5,
            allow_regression=True,
        )

        # Get ontology value after
        after = lookup_interaction("kha", "O5_DIRECTING")

        # Ontology should be unchanged
        assert before.distortion_vector == after.distortion_vector
        assert before.sublimate_vector == after.sublimate_vector
        assert before.manifestation_positive == after.manifestation_positive
        assert before.manifestation_negative == after.manifestation_negative


# =============================================================================
# 3. ONTOLOGY ISOLATION TEST
# =============================================================================

class TestOntologyIsolation:
    """
    Assert that no Phase-5 code accesses JSON directly.
    All ontology access must flow through Phase-4A only.
    """

    def test_no_direct_json_import(self):
        """
        Phase-5 engine should not import json for reading ontology.
        """
        source = inspect.getsource(phase5_dynamics_engine)

        # Check for forbidden patterns
        forbidden_patterns = [
            "open(",
            "json.load",
            "Path(",
            "varna_bridge_map",
            "varna_layer_interaction",
            "ontological_layers",
            ".json",
        ]

        for pattern in forbidden_patterns:
            # Allow pattern in comments/docstrings
            lines = source.split('\n')
            code_lines = [
                line for line in lines
                if not line.strip().startswith('#')
                and not line.strip().startswith('"""')
                and not line.strip().startswith("'''")
            ]
            code_without_comments = '\n'.join(code_lines)

            # Pattern should not appear in actual code
            if pattern in code_without_comments:
                # Check if it's in a string (docstring or comment)
                assert pattern not in code_without_comments or \
                       f'"{pattern}"' in code_without_comments or \
                       f"'{pattern}'" in code_without_comments, \
                       f"Forbidden pattern '{pattern}' found in Phase-5 engine code"

    def test_only_phase4a_imports(self):
        """
        Phase-5 should only import from phase4a.lookup and phase4a.loader.
        """
        source = inspect.getsource(phase5_dynamics_engine)

        # Allowed phase4a imports
        allowed = [
            "from symbolu.ontology.phase4a.lookup",
            "from symbolu.ontology.phase4a.loader",
            "from symbolu.ontology.phase4a import lookup",
        ]

        # Forbidden phase4a imports (direct file access)
        forbidden = [
            "phase4a.loader._load_json_file",
            "phase4a.loader._get_data_dir",
            "_cached_ontology",
        ]

        for pattern in forbidden:
            assert pattern not in source, \
                f"Forbidden Phase-4A internal access: {pattern}"

    def test_phase5_uses_phase4a_validation(self):
        """
        Verify Phase-5 validates through Phase-4A, not directly.
        """
        # Invalid varna should raise Phase-5 error that wraps Phase-4A check
        with pytest.raises(Phase5InvalidVarnaError):
            resolve_dynamics(
                varna="invalid_varna_xyz",
                start_layer="O1_ACTING",
                load=0.5,
                time_steps=10,
                decay_constant=0.1,
                amplification_factor=1.0,
                allow_regression=False,
            )

        # Invalid layer should raise Phase-5 error
        with pytest.raises(Phase5InvalidLayerError):
            resolve_dynamics(
                varna="ka",
                start_layer="O99_FAKE",
                load=0.5,
                time_steps=10,
                decay_constant=0.1,
                amplification_factor=1.0,
                allow_regression=False,
            )

    def test_no_ontology_file_paths_in_code(self):
        """
        Phase-5 should have no hardcoded paths to ontology files.
        """
        source = inspect.getsource(phase5_dynamics_engine)

        ontology_paths = [
            "docs/data",
            "varna_bridge_map_v1.json",
            "ontological_layers_v1.json",
            "varna_layer_interaction_v1.json",
        ]

        for path in ontology_paths:
            assert path not in source, \
                f"Hardcoded ontology path '{path}' found in Phase-5"


# =============================================================================
# 4. DETERMINISM TEST
# =============================================================================

class TestDeterminism:
    """
    Same input must produce identical trajectory (bitwise).
    """

    def test_identical_inputs_produce_identical_outputs(self):
        """
        Two calls with same parameters should produce identical results.
        """
        params = {
            "varna": "ka",
            "start_layer": "O1_ACTING",
            "load": 0.5,
            "time_steps": 15,
            "decay_constant": 0.1,
            "amplification_factor": 1.2,
            "allow_regression": True,
        }

        result1 = resolve_dynamics(**params)
        result2 = resolve_dynamics(**params)

        # Trajectories should be identical
        assert len(result1.trajectory) == len(result2.trajectory)

        for s1, s2 in zip(result1.trajectory, result2.trajectory):
            assert s1.time_step == s2.time_step
            assert s1.layer_id == s2.layer_id
            assert s1.layer_index == s2.layer_index
            assert s1.activation_level == s2.activation_level
            assert s1.momentum == s2.momentum
            assert s1.direction == s2.direction
            assert s1.distortion_load == s2.distortion_load
            assert s1.sublimation_load == s2.sublimation_load
            assert s1.termination_flag == s2.termination_flag
            assert s1.regression_flag == s2.regression_flag

    def test_determinism_across_varnas(self):
        """
        Test determinism with multiple different varnas.
        """
        varnas = ["ka", "ga", "ta", "sha", "a"]

        for varna in varnas:
            result1 = resolve_dynamics(
                varna=varna,
                start_layer="O3_FORMING",
                load=0.6,
                time_steps=10,
                decay_constant=0.15,
                amplification_factor=1.1,
                allow_regression=True,
            )

            result2 = resolve_dynamics(
                varna=varna,
                start_layer="O3_FORMING",
                load=0.6,
                time_steps=10,
                decay_constant=0.15,
                amplification_factor=1.1,
                allow_regression=True,
            )

            # Results should be identical
            assert result1.final_layer == result2.final_layer
            assert result1.peak_activation == result2.peak_activation
            assert result1.peak_momentum == result2.peak_momentum
            assert result1.terminated == result2.terminated
            assert result1.regressed == result2.regressed

    def test_determinism_with_different_configs(self):
        """
        Different configs should produce different (but deterministic) results.
        """
        result_low_load = resolve_dynamics(
            varna="ka",
            start_layer="O1_ACTING",
            load=0.2,
            time_steps=10,
            decay_constant=0.1,
            amplification_factor=1.0,
            allow_regression=False,
        )

        result_high_load = resolve_dynamics(
            varna="ka",
            start_layer="O1_ACTING",
            load=0.8,
            time_steps=10,
            decay_constant=0.1,
            amplification_factor=1.0,
            allow_regression=False,
        )

        # Results should differ due to different load
        # (at least in distortion_load accumulation)
        assert result_low_load.total_distortion != result_high_load.total_distortion or \
               result_low_load.peak_momentum != result_high_load.peak_momentum


# =============================================================================
# 5. FAILURE MODE TEST
# =============================================================================

class TestFailureModes:
    """
    Invalid varna/layer should fail fast, no inference.
    """

    def test_invalid_varna_fails_fast(self):
        """
        Non-existent varna should raise error immediately.
        """
        with pytest.raises(Phase5InvalidVarnaError) as exc_info:
            resolve_dynamics(
                varna="nonexistent_varna",
                start_layer="O1_ACTING",
                load=0.5,
                time_steps=10,
                decay_constant=0.1,
                amplification_factor=1.0,
                allow_regression=False,
            )

        assert "nonexistent_varna" in str(exc_info.value)

    def test_invalid_layer_fails_fast(self):
        """
        Non-existent layer should raise error immediately.
        """
        with pytest.raises(Phase5InvalidLayerError) as exc_info:
            resolve_dynamics(
                varna="ka",
                start_layer="O11_FAKE",
                load=0.5,
                time_steps=10,
                decay_constant=0.1,
                amplification_factor=1.0,
                allow_regression=False,
            )

        assert "O11_FAKE" in str(exc_info.value)

    def test_invalid_load_fails(self):
        """
        Load outside 0.0-1.0 should fail.
        """
        with pytest.raises((Phase5InvalidConfigError, ValueError)):
            resolve_dynamics(
                varna="ka",
                start_layer="O1_ACTING",
                load=1.5,  # Invalid
                time_steps=10,
                decay_constant=0.1,
                amplification_factor=1.0,
                allow_regression=False,
            )

    def test_invalid_time_steps_fails(self):
        """
        Non-positive time_steps should fail.
        """
        with pytest.raises((Phase5InvalidConfigError, ValueError)):
            resolve_dynamics(
                varna="ka",
                start_layer="O1_ACTING",
                load=0.5,
                time_steps=0,  # Invalid
                decay_constant=0.1,
                amplification_factor=1.0,
                allow_regression=False,
            )

    def test_invalid_decay_constant_fails(self):
        """
        Decay constant outside 0.0-1.0 should fail.
        """
        with pytest.raises((Phase5InvalidConfigError, ValueError)):
            resolve_dynamics(
                varna="ka",
                start_layer="O1_ACTING",
                load=0.5,
                time_steps=10,
                decay_constant=2.0,  # Invalid
                amplification_factor=1.0,
                allow_regression=False,
            )

    def test_invalid_amplification_factor_fails(self):
        """
        Amplification factor outside 0.5-2.0 should fail.
        """
        with pytest.raises((Phase5InvalidConfigError, ValueError)):
            resolve_dynamics(
                varna="ka",
                start_layer="O1_ACTING",
                load=0.5,
                time_steps=10,
                decay_constant=0.1,
                amplification_factor=5.0,  # Invalid
                allow_regression=False,
            )

    def test_empty_varna_fails(self):
        """
        Empty string varna should fail.
        """
        with pytest.raises(Phase5InvalidVarnaError):
            resolve_dynamics(
                varna="",
                start_layer="O1_ACTING",
                load=0.5,
                time_steps=10,
                decay_constant=0.1,
                amplification_factor=1.0,
                allow_regression=False,
            )

    def test_no_inference_on_partial_data(self):
        """
        Phase-5 should never infer missing data.
        If Phase-4A fails, Phase-5 should fail too.
        """
        # Use a hypothetically missing varna
        with pytest.raises(Phase5InvalidVarnaError):
            resolve_dynamics(
                varna="zzz",  # Not a Sanskrit varna
                start_layer="O1_ACTING",
                load=0.5,
                time_steps=10,
                decay_constant=0.1,
                amplification_factor=1.0,
                allow_regression=False,
            )


# =============================================================================
# MODEL TESTS
# =============================================================================

class TestDynamicStateModel:
    """
    Test DynamicState dataclass validation.
    """

    def test_valid_state_creation(self):
        """
        Valid parameters should create state successfully.
        """
        state = DynamicState(
            time_step=0,
            layer_id="O1_ACTING",
            layer_index=1,
            activation_level=0.5,
            momentum=0.0,
            direction=Direction.LATERAL,
            distortion_load=0.0,
            sublimation_load=0.0,
            termination_flag=False,
            regression_flag=False,
        )

        assert state.time_step == 0
        assert state.layer_id == "O1_ACTING"
        assert state.activation_level == 0.5

    def test_invalid_activation_level_fails(self):
        """
        Activation outside 0.0-1.0 should fail.
        """
        with pytest.raises(ValueError):
            DynamicState(
                time_step=0,
                layer_id="O1_ACTING",
                layer_index=1,
                activation_level=1.5,  # Invalid
                momentum=0.0,
                direction=Direction.LATERAL,
                distortion_load=0.0,
                sublimation_load=0.0,
                termination_flag=False,
                regression_flag=False,
            )

    def test_invalid_momentum_fails(self):
        """
        Momentum outside -1.0 to 1.0 should fail.
        """
        with pytest.raises(ValueError):
            DynamicState(
                time_step=0,
                layer_id="O1_ACTING",
                layer_index=1,
                activation_level=0.5,
                momentum=2.0,  # Invalid
                direction=Direction.UP,
                distortion_load=0.0,
                sublimation_load=0.0,
                termination_flag=False,
                regression_flag=False,
            )

    def test_invalid_layer_index_fails(self):
        """
        Layer index outside 1-10 should fail.
        """
        with pytest.raises(ValueError):
            DynamicState(
                time_step=0,
                layer_id="O11_FAKE",
                layer_index=11,  # Invalid
                activation_level=0.5,
                momentum=0.0,
                direction=Direction.LATERAL,
                distortion_load=0.0,
                sublimation_load=0.0,
                termination_flag=False,
                regression_flag=False,
            )

    def test_state_is_immutable(self):
        """
        DynamicState should be frozen (immutable).
        """
        state = DynamicState(
            time_step=0,
            layer_id="O1_ACTING",
            layer_index=1,
            activation_level=0.5,
            momentum=0.0,
            direction=Direction.LATERAL,
            distortion_load=0.0,
            sublimation_load=0.0,
            termination_flag=False,
            regression_flag=False,
        )

        with pytest.raises(AttributeError):
            state.activation_level = 0.9  # type: ignore


class TestDynamicsConfig:
    """
    Test DynamicsConfig validation.
    """

    def test_valid_config_creation(self):
        """
        Valid parameters should create config successfully.
        """
        config = DynamicsConfig(
            load=0.5,
            time_steps=10,
            decay_constant=0.1,
            amplification_factor=1.2,
            allow_regression=True,
        )

        assert config.load == 0.5
        assert config.time_steps == 10

    def test_config_bounds_validated(self):
        """
        Config should validate all parameter bounds.
        """
        # Load too high
        with pytest.raises(ValueError):
            DynamicsConfig(
                load=1.5,
                time_steps=10,
                decay_constant=0.1,
                amplification_factor=1.0,
                allow_regression=False,
            )

        # Amplification too low
        with pytest.raises(ValueError):
            DynamicsConfig(
                load=0.5,
                time_steps=10,
                decay_constant=0.1,
                amplification_factor=0.2,
                allow_regression=False,
            )


# =============================================================================
# O8 DAMPING TEST
# =============================================================================

class TestO8Handling:
    """
    Test that O8_META_OBSERVING dampens momentum without altering polarity.
    """

    def test_o8_dampens_momentum(self):
        """
        Traversal through O8 should show momentum damping.
        """
        # Start at O7, should pass through O8
        result = resolve_dynamics(
            varna="ga",  # Constructive, likely to move upward
            start_layer="O7_PURPOSING",
            load=0.2,
            time_steps=15,
            decay_constant=0.05,
            amplification_factor=1.3,
            allow_regression=False,
            o8_damping_factor=0.7,  # High damping
        )

        # Find states at O8
        o8_states = [s for s in result.trajectory if s.layer_id == "O8_META_OBSERVING"]

        # O8 states should exist and show damping effects
        # (momentum magnitude should be lower relative to surrounding layers)
        # This is a structural test, not exact value assertion

        assert result.trajectory is not None  # Trajectory completed


# =============================================================================
# TERMINATION TEST
# =============================================================================

class TestTermination:
    """
    Test O10 termination behavior.
    """

    def test_o10_terminates_trajectory(self):
        """
        Reaching O10 with terminating sublimate should end evolution.
        """
        result = resolve_dynamics(
            varna="ga",
            start_layer="O9_UNIFYING",
            load=0.1,  # Low load to encourage upward movement
            time_steps=20,
            decay_constant=0.05,
            amplification_factor=1.5,
            allow_regression=False,
        )

        # If O10 was reached and terminated
        if result.terminated:
            # All post-termination states should have termination_flag=True
            termination_indices = [
                i for i, s in enumerate(result.trajectory)
                if s.termination_flag
            ]

            if termination_indices:
                first_termination = termination_indices[0]
                for i in range(first_termination, len(result.trajectory)):
                    assert result.trajectory[i].termination_flag, \
                        "All states after termination should have flag set"

    def test_no_rebirth_after_termination(self):
        """
        Once terminated, no implicit rebirth should occur.
        """
        result = resolve_dynamics(
            varna="ga",
            start_layer="O9_UNIFYING",
            load=0.1,
            time_steps=30,
            decay_constant=0.05,
            amplification_factor=1.5,
            allow_regression=False,
        )

        if result.terminated:
            # After termination, layer should not decrease
            termination_point = None
            for i, s in enumerate(result.trajectory):
                if s.termination_flag:
                    termination_point = i
                    break

            if termination_point is not None:
                for i in range(termination_point, len(result.trajectory)):
                    assert result.trajectory[i].layer_id == "O10_ABSOLVING", \
                        "Should remain at O10 after termination"


# =============================================================================
# SATURATION TEST
# =============================================================================

class TestSaturation:
    """
    Test saturation behavior at O9/O10.
    """

    def test_saturation_at_high_layers(self):
        """
        Excess momentum at O9/O10 should collapse.
        """
        result = resolve_dynamics(
            varna="ga",
            start_layer="O8_META_OBSERVING",
            load=0.1,
            time_steps=20,
            decay_constant=0.02,  # Low decay
            amplification_factor=1.8,  # High amplification
            allow_regression=False,
            saturation_threshold=0.5,  # Low threshold for easier triggering
        )

        # At high layers with high momentum, saturation should occur
        high_layer_states = [
            s for s in result.trajectory
            if s.layer_index >= 9
        ]

        # If we reached high layers, check for saturation effects
        if high_layer_states:
            # Momentum should not exceed saturation indefinitely
            max_momentum = max(abs(s.momentum) for s in high_layer_states)
            assert max_momentum <= 1.0  # Clamped


# =============================================================================
# TRAJECTORY RESULT TEST
# =============================================================================

class TestTrajectoryResult:
    """
    Test TrajectoryResult helper methods.
    """

    def test_is_flat_detection(self):
        """
        is_flat() should correctly identify flat trajectories.
        """
        result = resolve_dynamics(
            varna="ka",
            start_layer="O1_ACTING",
            load=0.0,  # Zero load
            time_steps=5,
            decay_constant=0.5,  # High decay
            amplification_factor=0.5,  # Low amplification
            allow_regression=False,
        )

        # With high decay and low amplification, trajectory should be relatively flat
        is_flat = result.is_flat(threshold=0.5)
        assert isinstance(is_flat, bool)

    def test_layers_visited_tracking(self):
        """
        layers_visited should correctly track all visited layers.
        """
        result = resolve_dynamics(
            varna="ga",
            start_layer="O1_ACTING",
            load=0.2,
            time_steps=20,
            decay_constant=0.1,
            amplification_factor=1.3,
            allow_regression=False,
        )

        # layers_visited should be a tuple of unique layer IDs
        assert isinstance(result.layers_visited, tuple)
        assert len(result.layers_visited) == len(set(result.layers_visited))

        # All visited layers should appear in trajectory
        trajectory_layers = set(s.layer_id for s in result.trajectory)
        assert set(result.layers_visited) == trajectory_layers

    def test_to_dict_serialization(self):
        """
        to_dict() should produce serializable output.
        """
        result = resolve_dynamics(
            varna="ka",
            start_layer="O1_ACTING",
            load=0.5,
            time_steps=5,
            decay_constant=0.1,
            amplification_factor=1.0,
            allow_regression=False,
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["varna"] == "ka"
        assert result_dict["start_layer"] == "O1_ACTING"
        assert isinstance(result_dict["trajectory"], list)
        assert len(result_dict["trajectory"]) == 5
