"""Tests for USE-6G MIMO synchronization engine."""

import math
import numpy as np
import pytest

from simulator.use_6g.core.config import USE6GConfig, FrequencyConfig, FrequencyBand, AntennaConfig
from simulator.use_6g.core.state import AntennaArrayState, SyncState
from simulator.use_6g.mimo_sync import MIMOSyncEngine, SyncResult, BeamSteerResult


def make_small_array(nx=4, ny=4, panels=1) -> AntennaArrayState:
    """Create a small array for fast testing."""
    return AntennaArrayState(
        num_elements_x=nx, num_elements_y=ny, num_panels=panels,
    )


def make_config(**kwargs) -> USE6GConfig:
    """Create a config with optional overrides."""
    return USE6GConfig(**kwargs)


def make_engine(
    array=None, config=None, seed=42,
) -> MIMOSyncEngine:
    """Create a sync engine for testing."""
    config = config or make_config()
    array = array or make_small_array()
    return MIMOSyncEngine(config, array, rng=np.random.default_rng(seed))


class TestSynchronize:
    """Tests for the synchronize() method (U3+U4 loop)."""

    def test_converges_from_random(self):
        """Should converge to high coherence from random initial phases."""
        array = make_small_array(nx=4, ny=4, panels=1)
        rng = np.random.default_rng(42)
        for elem in array.elements.values():
            elem.phase = rng.uniform(0, 2 * math.pi)

        engine = make_engine(array=array)
        result = engine.synchronize()

        assert result.coherence > 0.9
        assert result.converged

    def test_converges_with_target_phases(self):
        """Should converge phases toward a steering vector target."""
        array = make_small_array(nx=4, ny=4, panels=1)
        engine = make_engine(array=array)

        # Create a steering vector
        targets = array.compute_steering_vector(30.0, 10.0, 2.14)

        result = engine.synchronize(target_phases=targets)
        assert result.converged

        # Elements should be close to their targets
        for elem in array.active_elements:
            target = targets[elem.element_id]
            error = (elem.phase - target + math.pi) % (2 * math.pi) - math.pi
            assert abs(error) < 0.5  # Within ~28 degrees

    def test_sync_state_transitions(self):
        """Should transition from ACQUIRING to LOCKED."""
        array = make_small_array(nx=4, ny=4, panels=1)
        rng = np.random.default_rng(42)
        for elem in array.elements.values():
            elem.phase = rng.uniform(0, 2 * math.pi)

        engine = make_engine(array=array)
        assert array.sync_state == SyncState.UNSYNCHRONIZED

        result = engine.synchronize()
        if result.converged:
            assert array.sync_state == SyncState.LOCKED
        else:
            assert array.sync_state == SyncState.ACQUIRING

    def test_returns_sync_result(self):
        """Result should contain all required fields."""
        array = make_small_array()
        engine = make_engine(array=array)
        result = engine.synchronize()

        assert isinstance(result, SyncResult)
        assert isinstance(result.coherence, float)
        assert isinstance(result.mean_phase_error_deg, float)
        assert isinstance(result.max_phase_error_deg, float)
        assert isinstance(result.iterations, int)
        assert isinstance(result.converged, bool)
        assert isinstance(result.per_panel_coherence, dict)

    def test_max_iterations_respected(self):
        """Should stop at max_iterations even if not converged."""
        array = make_small_array(nx=8, ny=8, panels=2)
        rng = np.random.default_rng(42)
        for elem in array.elements.values():
            elem.phase = rng.uniform(0, 2 * math.pi)

        engine = make_engine(array=array)
        result = engine.synchronize(max_iterations=3)
        assert result.iterations <= 3

    def test_already_converged_fast_exit(self):
        """If already aligned, should converge immediately."""
        array = make_small_array(nx=4, ny=4, panels=1)
        for elem in array.elements.values():
            elem.phase = 1.0  # All aligned

        engine = make_engine(array=array)
        result = engine.synchronize()
        assert result.iterations <= 10  # Should converge very fast


class TestTrackingStep:
    """Tests for the tracking_step() method."""

    def test_maintains_lock_without_disturbance(self):
        """Should maintain lock in calm conditions."""
        config = make_config(enable_channel_fading=False, enable_mobility=False)
        array = make_small_array(nx=4, ny=4, panels=1)
        engine = make_engine(array=array, config=config)

        # First synchronize
        targets = array.compute_steering_vector(30.0, 10.0, 2.14)
        engine.synchronize(target_phases=targets)
        array.sync_state = SyncState.LOCKED

        # Track for several steps
        for _ in range(20):
            result = engine.tracking_step(target_phases=targets, time_step_us=10.0)

        assert result.coherence > 0.99
        assert result.sync_state in (SyncState.LOCKED, SyncState.TRACKING)

    def test_tracking_with_channel_effects(self):
        """Should maintain reasonable coherence with channel noise."""
        config = make_config(enable_channel_fading=True, enable_mobility=False)
        array = make_small_array(nx=4, ny=4, panels=1)
        engine = make_engine(array=array, config=config)

        targets = array.compute_steering_vector(30.0, 10.0, 2.14)
        engine.synchronize(target_phases=targets)
        array.sync_state = SyncState.LOCKED

        coherences = []
        for _ in range(50):
            result = engine.tracking_step(target_phases=targets, time_step_us=10.0)
            coherences.append(result.coherence)

        mean_coh = sum(coherences) / len(coherences)
        assert mean_coh > 0.9

    def test_tracking_returns_correct_type(self):
        array = make_small_array()
        engine = make_engine(array=array)
        result = engine.tracking_step(time_step_us=1.0)
        assert isinstance(result, SyncResult)

    def test_lock_lost_detection(self):
        """Should detect lock loss when coherence drops."""
        config = make_config(enable_channel_fading=False)
        array = make_small_array(nx=4, ny=4, panels=1)
        engine = make_engine(array=array, config=config)

        targets = array.compute_steering_vector(30.0, 10.0, 2.14)
        engine.synchronize(target_phases=targets)
        array.sync_state = SyncState.LOCKED

        # Scramble phases to simulate severe disruption
        rng = np.random.default_rng(99)
        for elem in array.elements.values():
            elem.phase = rng.uniform(0, 2 * math.pi)

        result = engine.tracking_step(target_phases=targets, time_step_us=1.0)
        # Should detect loss or at least be in tracking mode
        assert result.sync_state in (SyncState.TRACKING, SyncState.LOST)


class TestBeamSteering:
    """Tests for beam steering through sync engine."""

    def test_steer_single_beam(self):
        array = make_small_array(nx=8, ny=8, panels=1)
        engine = make_engine(array=array)
        result = engine.steer_beam(0, 30.0, 10.0)

        assert isinstance(result, BeamSteerResult)
        assert result.beam_id == 0
        assert result.azimuth_deg == 30.0
        assert result.elevation_deg == 10.0
        assert result.gain_db > 0

    def test_steer_beam_gain_reasonable(self):
        """64-element array should give ~18 dB gain."""
        array = make_small_array(nx=8, ny=8, panels=1)
        engine = make_engine(array=array)
        result = engine.steer_beam(0, 0.0, 0.0)

        expected = 10 * math.log10(64)
        # Allow some loss due to sync imperfection
        assert result.gain_db > expected - 3.0

    def test_multi_beam_steer(self):
        array = make_small_array(nx=8, ny=8, panels=1)
        engine = make_engine(array=array)

        configs = [
            (0, -30.0, 5.0, 0),
            (1, 30.0, 5.0, 1),
        ]
        results = engine.multi_beam_steer(configs)
        assert len(results) == 2
        assert all(isinstance(r, BeamSteerResult) for r in results)

    def test_steer_without_sync(self):
        """Should return result even without post-steer sync."""
        array = make_small_array()
        engine = make_engine(array=array)
        result = engine.steer_beam(0, 30.0, 10.0, sync_after_steer=False)
        assert isinstance(result, BeamSteerResult)


class TestAdaptiveLearningRate:
    """Tests for adaptive learning rate behavior."""

    def test_lr_reduces_near_convergence(self):
        """LR should decrease when coherence is high."""
        array = make_small_array(nx=4, ny=4, panels=1)
        for elem in array.elements.values():
            elem.phase = 0.5  # Already aligned

        engine = make_engine(array=array)
        # Warm up the coherence history
        for _ in range(5):
            engine.synchronize(max_iterations=1)

        lr = engine._adapt_learning_rate()
        # Should be reduced from base (0.1) since coherence is high
        assert lr <= engine._base_lr

    def test_lr_stays_positive(self):
        """Learning rate should always be positive."""
        array = make_small_array()
        engine = make_engine(array=array)

        rng = np.random.default_rng(42)
        for _ in range(20):
            for elem in array.elements.values():
                elem.phase = rng.uniform(0, 2 * math.pi)
            engine.synchronize(max_iterations=1)
            lr = engine._adapt_learning_rate()
            assert lr > 0
