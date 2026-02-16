"""Tests for USE-6G antenna array state management."""

import math
import numpy as np
import pytest

from simulator.use_6g.core.state import (
    AntennaArrayState,
    AntennaElement,
    BeamState,
    SyncState,
)


class TestAntennaElement:
    """Tests for individual antenna element state."""

    def test_default_phase_zero(self):
        elem = AntennaElement(element_id=0, panel_id=0)
        assert elem.phase == 0.0

    def test_phase_error_when_on_target(self):
        elem = AntennaElement(element_id=0, panel_id=0)
        elem.phase = 1.5
        elem.target_phase = 1.5
        assert abs(elem.current_error_rad) < 1e-10

    def test_phase_error_wrapping(self):
        """Error should wrap to [-pi, pi]."""
        elem = AntennaElement(element_id=0, panel_id=0)
        elem.phase = 0.1
        elem.target_phase = 2 * math.pi - 0.1
        # Error should be ~0.2, not ~6.08
        assert abs(elem.current_error_rad) < 0.3

    def test_update_phase_records_history(self):
        elem = AntennaElement(element_id=0, panel_id=0)
        elem.update_phase(1.0)
        elem.update_phase(1.1)
        assert len(elem.phase_error_history) == 2

    def test_update_phase_wraps(self):
        elem = AntennaElement(element_id=0, panel_id=0)
        elem.update_phase(7.0)
        assert 0 <= elem.phase < 2 * math.pi

    def test_rms_error_zero_when_no_history(self):
        elem = AntennaElement(element_id=0, panel_id=0)
        assert elem.rms_error_rad == 0.0

    def test_history_limit(self):
        elem = AntennaElement(element_id=0, panel_id=0, max_history=5)
        for i in range(10):
            elem.update_phase(float(i) * 0.1)
        assert len(elem.phase_error_history) == 5


class TestAntennaArrayState:
    """Tests for antenna array state management."""

    def test_default_element_count(self):
        array = AntennaArrayState()
        assert array.total_elements == 128

    def test_custom_element_count(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        assert array.total_elements == 16

    def test_all_elements_active_initially(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        assert len(array.active_elements) == 16

    def test_failed_element_excluded(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        array.elements[0].failed = True
        assert len(array.active_elements) == 15

    def test_initial_sync_state(self):
        array = AntennaArrayState()
        assert array.sync_state == SyncState.UNSYNCHRONIZED

    def test_beams_initialized(self):
        array = AntennaArrayState(max_beams=4)
        assert len(array.beams) == 4
        assert all(not b.active for b in array.beams.values())


class TestSteeringVector:
    """Tests for beam steering vector computation."""

    def test_broadside_steering_all_zero(self):
        """Broadside (0,0) should give nearly zero phase for all elements."""
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        steering = array.compute_steering_vector(0.0, 0.0, 2.14)
        for phase in steering.values():
            assert abs(phase) < 1e-10 or abs(phase - 2 * math.pi) < 1e-10

    def test_steering_vector_size_matches_active(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        steering = array.compute_steering_vector(30.0, 10.0, 2.14)
        assert len(steering) == array.total_elements

    def test_steering_vector_varies_with_angle(self):
        """Different angles should produce different steering vectors."""
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        s1 = array.compute_steering_vector(0.0, 0.0, 2.14)
        s2 = array.compute_steering_vector(30.0, 0.0, 2.14)
        # At least some elements should have different phases
        diffs = [abs(s1[k] - s2[k]) for k in s1]
        assert max(diffs) > 0.01

    def test_failed_element_excluded_from_steering(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        array.elements[0].failed = True
        steering = array.compute_steering_vector(30.0, 10.0, 2.14)
        assert 0 not in steering


class TestCorrelationMatrix:
    """Tests for USE U1: correlation matrix computation."""

    def test_self_correlation_is_one(self):
        """Diagonal elements should be 1.0."""
        array = AntennaArrayState(num_elements_x=2, num_elements_y=2, num_panels=1)
        C = array.compute_correlation_matrix()
        for i in range(4):
            assert abs(C[i, i] - 1.0) < 1e-10

    def test_symmetric_matrix(self):
        array = AntennaArrayState(num_elements_x=3, num_elements_y=1, num_panels=1)
        rng = np.random.default_rng(42)
        for elem in array.elements.values():
            elem.phase = rng.uniform(0, 2 * math.pi)
        C = array.compute_correlation_matrix()
        np.testing.assert_allclose(C, C.T, atol=1e-10)

    def test_aligned_phases_high_correlation(self):
        """Elements with same phase should have correlation ~1."""
        array = AntennaArrayState(num_elements_x=4, num_elements_y=1, num_panels=1)
        # All elements at same phase
        for elem in array.elements.values():
            elem.phase = 1.0
        C = array.compute_correlation_matrix()
        # All correlations should be ~1
        assert np.all(C > 0.99)

    def test_opposite_phases_negative_correlation(self):
        """Elements pi apart should have correlation ~-1."""
        array = AntennaArrayState(num_elements_x=2, num_elements_y=1, num_panels=1)
        array.elements[0].phase = 0.0
        array.elements[1].phase = math.pi
        C = array.compute_correlation_matrix()
        assert C[0, 1] < -0.99


class TestTotalCoherence:
    """Tests for USE U2: total coherence objective."""

    def test_all_aligned_coherence_one(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=1, num_panels=1)
        for elem in array.elements.values():
            elem.phase = 0.5
        coherence = array.compute_total_coherence()
        assert abs(coherence - 1.0) < 1e-10

    def test_random_phases_low_coherence(self):
        array = AntennaArrayState(num_elements_x=8, num_elements_y=8, num_panels=1)
        rng = np.random.default_rng(42)
        for elem in array.elements.values():
            elem.phase = rng.uniform(0, 2 * math.pi)
        coherence = array.compute_total_coherence()
        # Random phases should give coherence near 0
        assert abs(coherence) < 0.15

    def test_coherence_range(self):
        """Coherence should be in [-1, 1]."""
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        rng = np.random.default_rng(123)
        for elem in array.elements.values():
            elem.phase = rng.uniform(0, 2 * math.pi)
        coherence = array.compute_total_coherence()
        assert -1.0 <= coherence <= 1.0

    def test_single_element_coherence_is_one(self):
        array = AntennaArrayState(num_elements_x=1, num_elements_y=1, num_panels=1)
        coherence = array.compute_total_coherence()
        assert coherence == 1.0


class TestMeanFieldGradient:
    """Tests for USE U3: mean-field gradient."""

    def test_gradient_zero_when_aligned(self):
        """Gradient should be ~0 when element matches mean."""
        array = AntennaArrayState(num_elements_x=4, num_elements_y=1, num_panels=1)
        for elem in array.elements.values():
            elem.phase = 1.0
        grad = array.compute_gradient_mean_field(0)
        assert abs(grad) < 1e-10

    def test_gradient_pushes_toward_mean(self):
        """Gradient should push element toward the group mean."""
        array = AntennaArrayState(num_elements_x=4, num_elements_y=1, num_panels=1)
        # 3 elements at 0, 1 element ahead at pi/2
        for i in range(3):
            array.elements[i].phase = 0.0
        array.elements[3].phase = math.pi / 2

        grad = array.compute_gradient_mean_field(3)
        # Should be negative (push back toward 0)
        assert grad < 0

    def test_invalid_element_returns_zero(self):
        array = AntennaArrayState(num_elements_x=2, num_elements_y=1, num_panels=1)
        grad = array.compute_gradient_mean_field(999)
        assert grad == 0.0


class TestSynchronizeStep:
    """Tests for USE U4: phase update rule."""

    def test_step_improves_coherence(self):
        """One sync step should increase coherence from random start."""
        array = AntennaArrayState(num_elements_x=8, num_elements_y=1, num_panels=1)
        rng = np.random.default_rng(42)
        for elem in array.elements.values():
            elem.phase = rng.uniform(0, 2 * math.pi)

        c_before = array.compute_total_coherence()
        array.synchronize_step(learning_rate=0.1)
        c_after = array.global_coherence

        assert c_after > c_before

    def test_step_with_targets(self):
        """Sync step with targets should move toward targets."""
        array = AntennaArrayState(num_elements_x=4, num_elements_y=1, num_panels=1)
        targets = {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0}

        # Start at 0, target at 1.0
        for elem in array.elements.values():
            elem.phase = 0.0

        array.synchronize_step(learning_rate=0.5, target_phases=targets)

        # All elements should have moved toward 1.0
        for elem in array.elements.values():
            assert elem.phase > 0.0

    def test_convergence_over_many_steps(self):
        """Multiple steps should converge to high coherence."""
        array = AntennaArrayState(num_elements_x=8, num_elements_y=1, num_panels=1)
        rng = np.random.default_rng(42)
        for elem in array.elements.values():
            elem.phase = rng.uniform(0, 2 * math.pi)

        for _ in range(100):
            array.synchronize_step(learning_rate=0.1)

        assert array.global_coherence > 0.95

    def test_phases_stay_in_range(self):
        """Phases should always be in [0, 2*pi)."""
        array = AntennaArrayState(num_elements_x=4, num_elements_y=1, num_panels=1)
        rng = np.random.default_rng(42)
        for elem in array.elements.values():
            elem.phase = rng.uniform(0, 2 * math.pi)

        for _ in range(20):
            array.synchronize_step(learning_rate=0.3)

        for elem in array.elements.values():
            assert 0 <= elem.phase < 2 * math.pi


class TestBeamCoherence:
    """Tests for beam coherence metric."""

    def test_perfect_alignment_gives_one(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=1, num_panels=1)
        targets = {}
        for elem in array.elements.values():
            elem.phase = 1.5
            targets[elem.element_id] = 1.5

        coherence = array.compute_beam_coherence(targets)
        assert abs(coherence - 1.0) < 1e-10

    def test_random_phases_low_beam_coherence(self):
        array = AntennaArrayState(num_elements_x=8, num_elements_y=8, num_panels=1)
        rng = np.random.default_rng(42)
        targets = {}
        for elem in array.elements.values():
            elem.phase = rng.uniform(0, 2 * math.pi)
            targets[elem.element_id] = rng.uniform(0, 2 * math.pi)

        coherence = array.compute_beam_coherence(targets)
        assert coherence < 0.3

    def test_beam_coherence_range(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        rng = np.random.default_rng(42)
        targets = {}
        for elem in array.elements.values():
            elem.phase = rng.uniform(0, 2 * math.pi)
            targets[elem.element_id] = rng.uniform(0, 2 * math.pi)

        coherence = array.compute_beam_coherence(targets)
        assert 0.0 <= coherence <= 1.0

    def test_empty_targets_returns_zero(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=1, num_panels=1)
        coherence = array.compute_beam_coherence({})
        assert coherence == 0.0


class TestCorrelationInterpretation:
    """Tests for USE U5: correlation interpretation."""

    def test_strong_alignment(self):
        array = AntennaArrayState(num_elements_x=2, num_elements_y=1, num_panels=1)
        array.elements[0].phase = 0.0
        array.elements[1].phase = 0.1
        assert array.evaluate_correlation(0, 1) == "strong_alignment"

    def test_anti_correlation(self):
        array = AntennaArrayState(num_elements_x=2, num_elements_y=1, num_panels=1)
        array.elements[0].phase = 0.0
        array.elements[1].phase = math.pi
        assert array.evaluate_correlation(0, 1) == "anti_correlation"

    def test_invalid_element(self):
        array = AntennaArrayState(num_elements_x=2, num_elements_y=1, num_panels=1)
        assert array.evaluate_correlation(0, 999) == "invalid"


class TestBeamSteering:
    """Tests for beam steering."""

    def test_steer_beam_activates(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        beam = array.steer_beam(0, 30.0, 10.0, 2.14)
        assert beam.active
        assert beam.azimuth_deg == 30.0
        assert beam.elevation_deg == 10.0

    def test_steer_beam_assigns_elements(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        beam = array.steer_beam(0, 30.0, 10.0, 2.14)
        assert len(beam.assigned_elements) == 16

    def test_steer_beam_computes_gain(self):
        array = AntennaArrayState(num_elements_x=8, num_elements_y=8, num_panels=1)
        beam = array.steer_beam(0, 30.0, 10.0, 2.14)
        # 64 elements -> gain ~18.1 dB
        expected_gain = 10 * math.log10(64)
        assert abs(beam.gain_db - expected_gain) < 0.1


class TestChannelEffects:
    """Tests for channel impairment simulation."""

    def test_channel_effects_change_phases(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        phases_before = {e.element_id: e.phase for e in array.elements.values()}

        rng = np.random.default_rng(42)
        array.apply_channel_effects(rng, doppler_hz=100.0, time_step_us=10.0)

        phases_after = {e.element_id: e.phase for e in array.elements.values()}
        changes = sum(1 for k in phases_before if phases_before[k] != phases_after[k])
        assert changes > 0

    def test_channel_effects_update_fading(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=1, num_panels=1)
        rng = np.random.default_rng(42)
        array.apply_channel_effects(rng, doppler_hz=0.0, time_step_us=1.0)
        assert len(array.channel.fading_amplitudes) == 4

    def test_no_doppler_small_phase_change(self):
        """Without Doppler, only jitter noise should be present."""
        array = AntennaArrayState(num_elements_x=4, num_elements_y=1, num_panels=1)
        for elem in array.elements.values():
            elem.phase = 1.0

        rng = np.random.default_rng(42)
        array.apply_channel_effects(rng, doppler_hz=0.0, time_step_us=1.0)

        for elem in array.elements.values():
            # Only jitter noise, should be small
            assert abs(elem.phase - 1.0) < 0.1


class TestPerPanelCoherence:
    """Tests for multi-panel coherence computation."""

    def test_single_panel_coherence(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        for elem in array.elements.values():
            elem.phase = 0.5
        panel_coh = array.get_per_panel_coherence()
        assert abs(panel_coh[0] - 1.0) < 1e-10

    def test_two_panels_independent(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=2)
        # Panel 0 aligned at 0
        # Panel 1 aligned at pi
        for elem in array.elements.values():
            if elem.panel_id == 0:
                elem.phase = 0.0
            else:
                elem.phase = math.pi
        panel_coh = array.get_per_panel_coherence()
        # Each panel internally coherent
        assert panel_coh[0] > 0.99
        assert panel_coh[1] > 0.99


class TestGetStats:
    """Tests for statistics reporting."""

    def test_stats_contains_required_keys(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        stats = array.get_stats()
        required_keys = [
            "total_elements", "active_elements", "failed_elements",
            "sync_state", "global_coherence", "sync_iterations",
            "mean_phase_error_deg", "max_phase_error_deg",
            "per_panel_coherence", "active_beams",
        ]
        for key in required_keys:
            assert key in stats, f"Missing key: {key}"

    def test_stats_element_counts(self):
        array = AntennaArrayState(num_elements_x=4, num_elements_y=4, num_panels=1)
        array.elements[0].failed = True
        stats = array.get_stats()
        assert stats["total_elements"] == 16
        assert stats["active_elements"] == 15
        assert stats["failed_elements"] == 1
