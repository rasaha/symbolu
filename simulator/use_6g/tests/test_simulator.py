"""Tests for USE-6G simulator scenarios."""

import math
import pytest

from simulator.use_6g.core.config import (
    USE6GConfig,
    FrequencyConfig,
    FrequencyBand,
    AntennaConfig,
)
from simulator.use_6g.simulator import USE6GSimulator, SimulationResult


def make_fast_config() -> USE6GConfig:
    """Config optimized for fast test execution."""
    return USE6GConfig(
        antenna=AntennaConfig(
            num_elements_x=4, num_elements_y=4,
            num_panels=2, num_rf_chains=2, max_beams=2,
        ),
        simulation_duration_ms=10.0,
        random_seed=42,
        enable_channel_fading=False,
        enable_mobility=False,
    )


class TestAcquisitionScenario:
    """Tests for initial phase acquisition scenario."""

    def test_runs_without_error(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_acquisition_scenario(num_trials=3)
        assert isinstance(result, SimulationResult)

    def test_scenario_name(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_acquisition_scenario(num_trials=2)
        assert result.scenario == "Initial Acquisition"

    def test_sync_timeline_populated(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_acquisition_scenario(num_trials=5)
        assert len(result.sync_timeline) == 5

    def test_coherence_positive(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_acquisition_scenario(num_trials=3)
        assert result.metrics.sync.mean_coherence > 0.5

    def test_at_least_some_converge(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_acquisition_scenario(num_trials=10)
        converged = sum(1 for t in result.sync_timeline if t["converged"])
        assert converged >= 1

    def test_metrics_populated(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_acquisition_scenario(num_trials=3)
        assert result.metrics.throughput.total_sync_ops == 3
        assert result.metrics.power.mean_power_w > 0


class TestBeamTrackingScenario:
    """Tests for beam tracking scenario."""

    def test_runs_without_error(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_beam_tracking_scenario(duration_ms=5.0)
        assert isinstance(result, SimulationResult)

    def test_scenario_name(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_beam_tracking_scenario(duration_ms=5.0)
        assert result.scenario == "Beam Tracking"

    def test_high_coherence_no_fading(self):
        """Without fading, tracking should maintain high coherence."""
        config = make_fast_config()
        config.enable_channel_fading = False
        sim = USE6GSimulator(config, verbose=False)
        result = sim.run_beam_tracking_scenario(duration_ms=5.0)
        assert result.metrics.sync.mean_coherence > 0.95

    def test_lock_ratio_high_no_fading(self):
        config = make_fast_config()
        config.enable_channel_fading = False
        sim = USE6GSimulator(config, verbose=False)
        result = sim.run_beam_tracking_scenario(duration_ms=5.0)
        assert result.metrics.sync.lock_ratio > 0.9

    def test_with_channel_fading(self):
        """Should still track reasonably with mild fading."""
        config = make_fast_config()
        config.enable_channel_fading = True
        config.enable_mobility = False
        sim = USE6GSimulator(config, verbose=False)
        result = sim.run_beam_tracking_scenario(duration_ms=5.0)
        assert result.metrics.sync.mean_coherence > 0.8

    def test_beam_events_has_initial_steer(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_beam_tracking_scenario(duration_ms=5.0)
        assert len(result.beam_events) >= 1
        assert result.beam_events[0]["type"] == "initial_steer"

    def test_custom_beam_direction(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_beam_tracking_scenario(
            duration_ms=5.0, beam_direction=(45.0, 20.0),
        )
        assert result.beam_events[0]["azimuth"] == 45.0
        assert result.beam_events[0]["elevation"] == 20.0


class TestMultiBeamScenario:
    """Tests for multi-beam MIMO scenario."""

    def test_runs_without_error(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_multi_beam_scenario(num_users=2)
        assert isinstance(result, SimulationResult)

    def test_scenario_name(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_multi_beam_scenario(num_users=2)
        assert result.scenario == "Multi-Beam MIMO"

    def test_beam_events_match_users(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_multi_beam_scenario(num_users=2)
        beam_events = [e for e in result.beam_events if "beam_id" in e]
        assert len(beam_events) == 2

    def test_beam_gain_positive(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_multi_beam_scenario(num_users=2)
        assert result.metrics.beamforming.mean_gain_db > 0

    def test_steers_recorded(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_multi_beam_scenario(num_users=2)
        assert result.metrics.beamforming.total_steers == 2

    def test_max_simultaneous_beams(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_multi_beam_scenario(num_users=2)
        assert result.metrics.beamforming.simultaneous_beams_max == 2

    def test_custom_directions(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        dirs = [(-20.0, 5.0), (20.0, 5.0)]
        result = sim.run_multi_beam_scenario(num_users=2, user_directions=dirs)
        assert len(result.beam_events) >= 2


class TestPanelHandoverScenario:
    """Tests for panel handover scenario."""

    def test_runs_without_error(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_panel_handover_scenario(duration_ms=100.0)
        assert isinstance(result, SimulationResult)

    def test_scenario_name(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_panel_handover_scenario(duration_ms=100.0)
        assert result.scenario == "Panel Handover"

    def test_coherence_maintained(self):
        """Should maintain coherence through handovers."""
        config = make_fast_config()
        config.enable_channel_fading = False
        sim = USE6GSimulator(config, verbose=False)
        result = sim.run_panel_handover_scenario(duration_ms=100.0)
        assert result.metrics.sync.mean_coherence > 0.8

    def test_final_state_populated(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_panel_handover_scenario(duration_ms=100.0)
        assert "total_elements" in result.final_state
        assert "global_coherence" in result.final_state


class TestRunAllScenarios:
    """Tests for running the full validation suite."""

    def test_returns_all_scenarios(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        results = sim.run_all_scenarios()
        assert "acquisition" in results
        assert "tracking" in results
        assert "multi_beam" in results
        assert "panel_handover" in results

    def test_all_results_valid(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        results = sim.run_all_scenarios()
        for name, result in results.items():
            assert isinstance(result, SimulationResult), f"Bad result for {name}"
            assert result.metrics.throughput.total_sync_ops > 0, f"No sync ops for {name}"


class TestSimulationResult:
    """Tests for SimulationResult output."""

    def test_summary_string(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_acquisition_scenario(num_trials=2)
        summary = result.summary()
        assert "USE-6G" in summary
        assert "Initial Acquisition" in summary
        assert "Synchronization:" in summary

    def test_gates_in_summary(self):
        sim = USE6GSimulator(make_fast_config(), verbose=False)
        result = sim.run_acquisition_scenario(num_trials=2)
        summary = result.summary()
        assert "gates passed" in summary


class TestFrequencyBandScenarios:
    """Tests across different frequency bands."""

    @pytest.mark.parametrize("band", [
        FrequencyBand.FR3_UPPER,
        FrequencyBand.FR2_MMWAVE,
        FrequencyBand.SUB_THZ_LOW,
        FrequencyBand.SUB_THZ_HIGH,
    ])
    def test_acquisition_all_bands(self, band):
        """Acquisition should work across all frequency bands."""
        config = USE6GConfig(
            frequency=FrequencyConfig(band=band),
            antenna=AntennaConfig(
                num_elements_x=4, num_elements_y=4, num_panels=1,
            ),
            random_seed=42,
        )
        sim = USE6GSimulator(config, verbose=False)
        result = sim.run_acquisition_scenario(num_trials=3)
        assert result.metrics.sync.mean_coherence > 0.5


class TestDeterminism:
    """Tests for deterministic simulation."""

    def test_same_seed_same_result(self):
        """Same seed should produce identical results."""
        config = make_fast_config()
        config.random_seed = 123

        sim1 = USE6GSimulator(config, verbose=False)
        r1 = sim1.run_acquisition_scenario(num_trials=3)

        sim2 = USE6GSimulator(config, verbose=False)
        r2 = sim2.run_acquisition_scenario(num_trials=3)

        assert r1.metrics.sync.mean_coherence == r2.metrics.sync.mean_coherence

    def test_different_seed_different_result(self):
        """Different seeds should generally produce different results."""
        config1 = make_fast_config()
        config1.random_seed = 42
        config2 = make_fast_config()
        config2.random_seed = 99

        sim1 = USE6GSimulator(config1, verbose=False)
        r1 = sim1.run_acquisition_scenario(num_trials=3)

        sim2 = USE6GSimulator(config2, verbose=False)
        r2 = sim2.run_acquisition_scenario(num_trials=3)

        # Not guaranteed but highly likely to differ
        assert r1.metrics.sync.mean_coherence != r2.metrics.sync.mean_coherence
