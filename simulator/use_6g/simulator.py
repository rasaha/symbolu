"""
Main USE-6G simulator engine.

Orchestrates MIMO synchronization scenarios, beam management,
mobility simulation, and metrics collection for validating the
USE chip for 6G phone applications.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import math
import numpy as np

from .core.config import USE6GConfig, FrequencyBand
from .core.state import AntennaArrayState, SyncState
from .core.metrics import USE6GMetrics, MetricsCollector
from .mimo_sync import MIMOSyncEngine, SyncResult, BeamSteerResult


@dataclass
class SimulationResult:
    """Complete result of a USE-6G simulation run."""
    metrics: USE6GMetrics
    scenario: str
    config_summary: str
    sync_timeline: List[Dict]
    beam_events: List[Dict]
    final_state: Dict

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"=== USE-6G Simulation: {self.scenario} ===",
            f"",
            self.config_summary,
            f"",
            self.metrics.summary(),
        ]
        return "\n".join(lines)


class USE6GSimulator:
    """
    Main simulator for USE-6G chip validation.

    Supports multiple scenarios:
    1. Initial acquisition: Phase lock from cold start
    2. Beam tracking: Maintaining lock during mobility
    3. Multi-beam: Simultaneous multi-user MIMO
    4. Handover: Panel switching during rotation

    Usage:
        sim = USE6GSimulator(config)
        result = sim.run_acquisition_scenario()
        print(result.summary())
    """

    def __init__(
        self,
        config: Optional[USE6GConfig] = None,
        verbose: bool = True,
    ):
        self.config = config or USE6GConfig()
        self.verbose = verbose

    def _create_array_and_engine(
        self,
    ) -> Tuple[AntennaArrayState, MIMOSyncEngine]:
        """Create fresh array state and sync engine."""
        array = AntennaArrayState(
            num_elements_x=self.config.antenna.num_elements_x,
            num_elements_y=self.config.antenna.num_elements_y,
            num_panels=self.config.antenna.num_panels,
            element_spacing_lambda=self.config.antenna.element_spacing_lambda,
            num_rf_chains=self.config.antenna.num_rf_chains,
            max_beams=self.config.antenna.max_beams,
        )
        engine = MIMOSyncEngine(
            self.config, array,
            rng=np.random.default_rng(self.config.random_seed),
        )
        return array, engine

    def run_acquisition_scenario(
        self,
        num_trials: int = 10,
    ) -> SimulationResult:
        """
        Scenario 1: Initial phase synchronization acquisition.

        Tests how quickly the USE chip can achieve phase lock
        from a random initial state.

        Args:
            num_trials: Number of independent acquisition trials

        Returns:
            SimulationResult with acquisition metrics
        """
        collector = MetricsCollector()
        collector.start(0.0)
        sync_timeline = []
        time_us = 0.0

        for trial in range(num_trials):
            array, engine = self._create_array_and_engine()

            # Randomize initial phases
            rng = np.random.default_rng(self.config.random_seed + trial)
            for elem in array.elements.values():
                elem.phase = rng.uniform(0, 2 * math.pi)

            # Run synchronization
            lock_start_time = time_us
            collector._lock_start_time = time_us  # Reset per trial
            result = engine.synchronize()

            sync_time_us = result.iterations * self.config.timing.sync_update_interval_us
            time_us += sync_time_us

            collector.record_sync_step(
                coherence=result.coherence,
                mean_phase_error_deg=result.mean_phase_error_deg,
                max_phase_error_deg=result.max_phase_error_deg,
                time_us=time_us,
                power_w=self.config.power.sync_power_w,
            )

            if result.converged:
                collector.record_lock_acquired(time_us, result.iterations)
                collector.record_lock_maintained(sync_time_us)

            sync_timeline.append({
                "trial": trial,
                "coherence": result.coherence,
                "iterations": result.iterations,
                "converged": result.converged,
                "time_us": sync_time_us,
                "mean_error_deg": result.mean_phase_error_deg,
                "per_panel": result.per_panel_coherence,
            })

            if self.verbose and trial % max(1, num_trials // 5) == 0:
                status = "LOCKED" if result.converged else "FAILED"
                print(
                    f"  Trial {trial + 1}/{num_trials}: "
                    f"coherence={result.coherence:.4f}, "
                    f"iters={result.iterations}, "
                    f"[{status}]"
                )

        metrics = collector.finalize()

        return SimulationResult(
            metrics=metrics,
            scenario="Initial Acquisition",
            config_summary=self.config.summary(),
            sync_timeline=sync_timeline,
            beam_events=[],
            final_state={},
        )

    def run_beam_tracking_scenario(
        self,
        duration_ms: Optional[float] = None,
        beam_direction: Tuple[float, float] = (30.0, 10.0),
        mobility_speed_kmh: float = 5.0,
    ) -> SimulationResult:
        """
        Scenario 2: Beam tracking during mobility.

        Tests the USE chip's ability to maintain phase lock
        while the phone is moving and channel conditions change.

        Args:
            duration_ms: Simulation duration in milliseconds
            beam_direction: Initial (azimuth, elevation) in degrees
            mobility_speed_kmh: User movement speed

        Returns:
            SimulationResult with tracking metrics
        """
        duration_ms = duration_ms or self.config.simulation_duration_ms
        array, engine = self._create_array_and_engine()
        collector = MetricsCollector()
        collector.start(0.0)

        wavelength_mm = self.config.frequency.wavelength_mm
        time_step_us = self.config.timing.sync_update_interval_us
        total_steps = int(duration_ms * 1000 / time_step_us)

        # Initial beam setup
        az, el = beam_direction
        steering = array.compute_steering_vector(az, el, wavelength_mm)
        beam = array.steer_beam(0, az, el, wavelength_mm)

        # Initial synchronization
        init_result = engine.synchronize(target_phases=steering)

        sync_timeline = []
        beam_events = [{
            "time_us": 0.0,
            "type": "initial_steer",
            "azimuth": az,
            "elevation": el,
            "converged": init_result.converged,
        }]

        time_us = 0.0
        lock_time_us = 0.0

        for step in range(total_steps):
            time_us = step * time_step_us

            # Slowly drift beam direction (mobility)
            drift_rate_deg_per_ms = mobility_speed_kmh * 0.01
            az_drift = drift_rate_deg_per_ms * (time_us / 1000.0)
            current_az = beam_direction[0] + az_drift

            # Update steering vector periodically
            if step % 10 == 0:
                steering = array.compute_steering_vector(
                    current_az, el, wavelength_mm
                )

            # Tracking step
            result = engine.tracking_step(
                target_phases=steering,
                time_step_us=time_step_us,
            )

            # Record metrics
            collector.record_sync_step(
                coherence=result.coherence,
                mean_phase_error_deg=result.mean_phase_error_deg,
                max_phase_error_deg=result.max_phase_error_deg,
                time_us=time_us,
                power_w=self.config.power.sync_power_w,
            )

            if result.sync_state in (SyncState.LOCKED, SyncState.TRACKING):
                lock_time_us += time_step_us
                collector.record_lock_maintained(time_step_us)

            # Record timeline periodically
            if step % 100 == 0:
                sync_timeline.append({
                    "time_us": time_us,
                    "coherence": result.coherence,
                    "sync_state": result.sync_state.value,
                    "mean_error_deg": result.mean_phase_error_deg,
                    "azimuth": current_az,
                })

            # Re-acquire if lock lost
            if result.sync_state == SyncState.LOST:
                reacq = engine.synchronize(target_phases=steering)
                beam_events.append({
                    "time_us": time_us,
                    "type": "reacquisition",
                    "converged": reacq.converged,
                    "iterations": reacq.iterations,
                })

        if self.verbose:
            lock_pct = lock_time_us / time_us * 100 if time_us > 0 else 0
            print(
                f"  Beam tracking: {duration_ms}ms, "
                f"lock={lock_pct:.1f}%, "
                f"reacquisitions={sum(1 for e in beam_events if e['type'] == 'reacquisition')}"
            )

        metrics = collector.finalize()

        return SimulationResult(
            metrics=metrics,
            scenario="Beam Tracking",
            config_summary=self.config.summary(),
            sync_timeline=sync_timeline,
            beam_events=beam_events,
            final_state=array.get_stats(),
        )

    def run_multi_beam_scenario(
        self,
        num_users: int = 4,
        user_directions: Optional[List[Tuple[float, float]]] = None,
    ) -> SimulationResult:
        """
        Scenario 3: Multi-user MIMO with concurrent beams.

        Tests the USE chip's ability to maintain multiple
        phase-coherent beams simultaneously.

        Args:
            num_users: Number of simultaneous users
            user_directions: List of (azimuth, elevation) per user

        Returns:
            SimulationResult with multi-beam metrics
        """
        array, engine = self._create_array_and_engine()
        collector = MetricsCollector()
        collector.start(0.0)

        # Default user directions (spread across coverage)
        if user_directions is None:
            user_directions = [
                (-45.0, 10.0),
                (-15.0, 5.0),
                (15.0, 5.0),
                (45.0, 10.0),
            ][:num_users]

        beam_events = []
        time_us = 0.0
        max_beams = min(num_users, self.config.antenna.max_beams)

        for i in range(max_beams):
            az, el = user_directions[i]
            result = engine.steer_beam(
                beam_id=i,
                azimuth_deg=az,
                elevation_deg=el,
                user_id=i,
            )

            time_us += self.config.timing.sync_update_interval_us * 10  # Estimated

            collector.record_beam_steer(
                gain_db=result.gain_db,
                sidelobe_db=result.sidelobe_db,
                success=result.success,
                time_us=time_us,
                power_w=self.config.power.beamform_power_w,
            )

            beam_events.append({
                "time_us": time_us,
                "beam_id": i,
                "azimuth": az,
                "elevation": el,
                "gain_db": result.gain_db,
                "sidelobe_db": result.sidelobe_db,
                "success": result.success,
                "sync_error_deg": result.sync_error_deg,
            })

            if self.verbose:
                status = "OK" if result.success else "DEGRADED"
                print(
                    f"  Beam {i}: az={az:.0f}, el={el:.0f}, "
                    f"gain={result.gain_db:.1f}dB, [{status}]"
                )

        collector.metrics.beamforming.simultaneous_beams_max = max_beams

        # Run tracking for all beams simultaneously
        track_steps = 100
        for step in range(track_steps):
            time_us += self.config.timing.sync_update_interval_us
            result = engine.tracking_step(time_step_us=self.config.timing.sync_update_interval_us)
            collector.record_sync_step(
                coherence=result.coherence,
                mean_phase_error_deg=result.mean_phase_error_deg,
                max_phase_error_deg=result.max_phase_error_deg,
                time_us=time_us,
                power_w=self.config.power.beamform_power_w,
            )
            if result.sync_state in (SyncState.LOCKED, SyncState.TRACKING):
                collector.record_lock_maintained(self.config.timing.sync_update_interval_us)

        metrics = collector.finalize()

        return SimulationResult(
            metrics=metrics,
            scenario="Multi-Beam MIMO",
            config_summary=self.config.summary(),
            sync_timeline=[],
            beam_events=beam_events,
            final_state=array.get_stats(),
        )

    def run_panel_handover_scenario(
        self,
        rotation_rate_deg_per_sec: float = 90.0,
        duration_ms: float = 2000.0,
    ) -> SimulationResult:
        """
        Scenario 4: Panel handover during phone rotation.

        Tests the USE chip's ability to switch between antenna
        panels as the phone rotates (e.g., user turning).

        Args:
            rotation_rate_deg_per_sec: Phone rotation speed
            duration_ms: Simulation duration

        Returns:
            SimulationResult with handover metrics
        """
        array, engine = self._create_array_and_engine()
        collector = MetricsCollector()
        collector.start(0.0)

        wavelength_mm = self.config.frequency.wavelength_mm
        time_step_us = self.config.timing.sync_update_interval_us * 10
        total_steps = int(duration_ms * 1000 / time_step_us)

        beam_events = []
        sync_timeline = []
        active_panel = 0
        time_us = 0.0

        # Initial beam toward panel 0
        initial_az = 0.0
        steering = array.compute_steering_vector(initial_az, 0.0, wavelength_mm)
        engine.synchronize(target_phases=steering)

        for step in range(total_steps):
            time_us = step * time_step_us

            # Current rotation angle
            rotation_deg = rotation_rate_deg_per_sec * (time_us / 1e6)
            effective_az = initial_az + rotation_deg

            # Determine which panel is best
            # Panel 0 faces forward, panel 1 faces backward
            wrapped_angle = effective_az % 360
            best_panel = 0 if wrapped_angle < 180 else 1

            # Panel handover
            if best_panel != active_panel:
                active_panel = best_panel
                beam_events.append({
                    "time_us": time_us,
                    "type": "panel_handover",
                    "from_panel": 1 - active_panel,
                    "to_panel": active_panel,
                    "rotation_deg": rotation_deg,
                })

                # Re-synchronize on new panel
                steering = array.compute_steering_vector(
                    effective_az % 90 - 45, 0.0, wavelength_mm,
                )
                reacq = engine.synchronize(target_phases=steering)

                if self.verbose:
                    print(
                        f"  Handover at {time_us:.0f}us: "
                        f"panel {1 - active_panel} -> {active_panel}, "
                        f"converged={reacq.converged}"
                    )

            # Tracking step
            result = engine.tracking_step(time_step_us=time_step_us)

            collector.record_sync_step(
                coherence=result.coherence,
                mean_phase_error_deg=result.mean_phase_error_deg,
                max_phase_error_deg=result.max_phase_error_deg,
                time_us=time_us,
                power_w=self.config.power.sync_power_w,
            )

            if result.sync_state in (SyncState.LOCKED, SyncState.TRACKING):
                collector.record_lock_maintained(time_step_us)

            if step % 50 == 0:
                sync_timeline.append({
                    "time_us": time_us,
                    "coherence": result.coherence,
                    "active_panel": active_panel,
                    "rotation_deg": rotation_deg,
                    "sync_state": result.sync_state.value,
                })

        metrics = collector.finalize()
        handover_count = sum(1 for e in beam_events if e["type"] == "panel_handover")

        if self.verbose:
            print(f"  Panel handovers: {handover_count}")

        return SimulationResult(
            metrics=metrics,
            scenario="Panel Handover",
            config_summary=self.config.summary(),
            sync_timeline=sync_timeline,
            beam_events=beam_events,
            final_state=array.get_stats(),
        )

    def run_all_scenarios(self) -> Dict[str, SimulationResult]:
        """Run all validation scenarios."""
        results = {}

        if self.verbose:
            print("=== USE-6G Validation Suite ===")
            print(f"Array: {self.config.antenna.total_elements} elements")
            print(f"Freq: {self.config.frequency.carrier_freq_ghz} GHz")
            print()

        if self.verbose:
            print("--- Scenario 1: Initial Acquisition ---")
        results["acquisition"] = self.run_acquisition_scenario()

        if self.verbose:
            print("\n--- Scenario 2: Beam Tracking ---")
        results["tracking"] = self.run_beam_tracking_scenario()

        if self.verbose:
            print("\n--- Scenario 3: Multi-Beam MIMO ---")
        results["multi_beam"] = self.run_multi_beam_scenario()

        if self.verbose:
            print("\n--- Scenario 4: Panel Handover ---")
        results["panel_handover"] = self.run_panel_handover_scenario()

        if self.verbose:
            print("\n=== Summary ===")
            for name, result in results.items():
                gates = result.metrics.check_acceptance_gates()
                passed = sum(1 for v in gates.values() if v)
                total = len(gates)
                print(f"  {name}: {passed}/{total} gates passed")

        return results
