"""
MIMO Synchronization Engine for USE-6G.

Implements the core synchronization loop using USE patent formulas
(U1-U5) adapted for 6G Massive MIMO antenna arrays.

Key features:
- O(n) mean-field phase synchronization (U3)
- Multi-beam concurrent synchronization
- Adaptive learning rate based on coherence state
- Phase lock detection with hysteresis
- Channel-aware compensation
"""

import math
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .core.config import USE6GConfig, FrequencyBand
from .core.state import AntennaArrayState, SyncState, BeamState
from .core.metrics import MetricsCollector


@dataclass
class SyncResult:
    """Result of a synchronization cycle."""
    coherence: float
    mean_phase_error_deg: float
    max_phase_error_deg: float
    iterations: int
    converged: bool
    sync_state: SyncState
    per_panel_coherence: Dict[int, float]


@dataclass
class BeamSteerResult:
    """Result of a beam steering operation."""
    beam_id: int
    azimuth_deg: float
    elevation_deg: float
    gain_db: float
    sidelobe_db: float
    sync_error_deg: float
    success: bool


class MIMOSyncEngine:
    """
    MIMO synchronization engine using USE formulas.

    Orchestrates the synchronization of antenna elements
    for 6G Massive MIMO using O(n) phase-based coherence.
    """

    def __init__(
        self,
        config: USE6GConfig,
        array_state: AntennaArrayState,
        rng: Optional[np.random.Generator] = None,
    ):
        self.config = config
        self.array = array_state
        self.rng = rng or np.random.default_rng(config.random_seed)

        # Adaptive learning rate state
        self._base_lr = config.timing.sync_learning_rate
        self._current_lr = self._base_lr
        self._coherence_history: List[float] = []
        self._lr_adaptation_window = 10

        # Lock detection state
        self._lock_coherence_history: List[float] = []
        self._lock_check_window = 5

    def synchronize(
        self,
        target_phases: Optional[Dict[int, float]] = None,
        max_iterations: Optional[int] = None,
    ) -> SyncResult:
        """
        Run synchronization loop until convergence or max iterations.

        Uses USE formulas:
        - U3: Mean-field gradient for O(n) phase updates
        - U4: Phase update rule with adaptive learning rate
        - U2: Total coherence as convergence metric

        Args:
            target_phases: Optional steering vector for beamforming sync
            max_iterations: Override max iterations

        Returns:
            SyncResult with convergence info
        """
        max_iter = max_iterations or self.config.timing.max_sync_iterations
        threshold = self.config.timing.coherence_threshold

        self.array.sync_state = SyncState.ACQUIRING
        initial_coherence = self.array.compute_total_coherence()

        converged = False
        for iteration in range(max_iter):
            # Adaptive learning rate
            lr = self._adapt_learning_rate()

            # Execute one synchronization step (U3 + U4)
            mean_update = self.array.synchronize_step(
                learning_rate=lr,
                target_phases=target_phases,
            )

            # Check convergence (U2 or beam coherence)
            if target_phases:
                coherence = self.array.compute_beam_coherence(target_phases)
            else:
                coherence = self.array.global_coherence

            # Track coherence for lock detection
            self._lock_coherence_history.append(coherence)
            if len(self._lock_coherence_history) > self._lock_check_window:
                self._lock_coherence_history.pop(0)

            # Check if locked
            if coherence >= threshold and self._is_stable():
                converged = True
                self.array.sync_state = SyncState.LOCKED
                break

            # Early termination if barely changing
            if mean_update < 1e-6 and iteration > 5:
                break

        # Compute final metrics
        active = self.array.active_elements

        if target_phases:
            # Beamforming mode: error relative to target
            phase_errors = [abs(e.current_error_deg) for e in active]
        else:
            # Coherence mode: error relative to circular mean
            phases = [e.phase for e in active]
            sin_sum = sum(math.sin(p) for p in phases)
            cos_sum = sum(math.cos(p) for p in phases)
            mean_phase = math.atan2(sin_sum, cos_sum)
            phase_errors = [
                abs(math.degrees(
                    (e.phase - mean_phase + math.pi) % (2 * math.pi) - math.pi
                ))
                for e in active
            ]

        mean_error = sum(phase_errors) / len(phase_errors) if phase_errors else 0.0
        max_error = max(phase_errors) if phase_errors else 0.0

        if not converged:
            self.array.sync_state = SyncState.ACQUIRING

        return SyncResult(
            coherence=self.array.global_coherence,
            mean_phase_error_deg=mean_error,
            max_phase_error_deg=max_error,
            iterations=iteration + 1,
            converged=converged,
            sync_state=self.array.sync_state,
            per_panel_coherence=self.array.get_per_panel_coherence(),
        )

    def tracking_step(
        self,
        target_phases: Optional[Dict[int, float]] = None,
        time_step_us: float = 1.0,
    ) -> SyncResult:
        """
        Single tracking step to maintain phase lock.

        Used after initial synchronization to correct for
        drift and channel variations.

        Args:
            target_phases: Current beam steering vector
            time_step_us: Time since last tracking step

        Returns:
            SyncResult with current state
        """
        # Apply channel effects (phase noise, Doppler)
        if self.config.enable_channel_fading:
            doppler_hz = 0.0
            if self.config.enable_mobility:
                # Typical pedestrian Doppler at sub-THz
                speed_kmh = 5.0  # Walking speed
                freq_ghz = self.config.frequency.carrier_freq_ghz
                doppler_hz = (speed_kmh / 3.6) * freq_ghz * 1e9 / 3e8

            self.array.apply_channel_effects(
                self.rng, doppler_hz=doppler_hz, time_step_us=time_step_us,
            )

        # Use moderate learning rate for tracking
        # Must exceed Doppler bandwidth to maintain lock
        tracking_lr = self._base_lr * 0.7
        mean_update = self.array.synchronize_step(
            learning_rate=tracking_lr,
            target_phases=target_phases,
        )

        # Use beam coherence when tracking a steering vector
        if target_phases:
            coherence = self.array.compute_beam_coherence(target_phases)
        else:
            coherence = self.array.global_coherence

        # Check if lock is maintained
        hysteresis = self.config.timing.phase_lock_hysteresis
        if self.array.sync_state == SyncState.LOCKED:
            if coherence < self.config.timing.coherence_threshold - hysteresis:
                self.array.sync_state = SyncState.TRACKING
        elif self.array.sync_state == SyncState.TRACKING:
            if coherence >= self.config.timing.coherence_threshold:
                self.array.sync_state = SyncState.LOCKED
            elif coherence < self.config.timing.coherence_threshold - 3 * hysteresis:
                self.array.sync_state = SyncState.LOST

        active = self.array.active_elements

        if target_phases:
            # Beamforming mode: error relative to steering vector
            phase_errors = []
            for e in active:
                target = target_phases.get(e.element_id, 0.0)
                err = (e.phase - target + math.pi) % (2 * math.pi) - math.pi
                phase_errors.append(abs(math.degrees(err)))
        else:
            # Coherence mode: error relative to circular mean
            phases = [e.phase for e in active]
            sin_sum = sum(math.sin(p) for p in phases)
            cos_sum = sum(math.cos(p) for p in phases)
            mean_phase = math.atan2(sin_sum, cos_sum)
            phase_errors = [
                abs(math.degrees(
                    (e.phase - mean_phase + math.pi) % (2 * math.pi) - math.pi
                ))
                for e in active
            ]

        mean_error = sum(phase_errors) / len(phase_errors) if phase_errors else 0.0
        max_error = max(phase_errors) if phase_errors else 0.0

        return SyncResult(
            coherence=coherence,
            mean_phase_error_deg=mean_error,
            max_phase_error_deg=max_error,
            iterations=1,
            converged=self.array.sync_state in (SyncState.LOCKED, SyncState.TRACKING),
            sync_state=self.array.sync_state,
            per_panel_coherence=self.array.get_per_panel_coherence(),
        )

    def steer_beam(
        self,
        beam_id: int,
        azimuth_deg: float,
        elevation_deg: float,
        user_id: Optional[int] = None,
        sync_after_steer: bool = True,
    ) -> BeamSteerResult:
        """
        Steer a beam and optionally synchronize.

        Args:
            beam_id: Beam to steer
            azimuth_deg: Target azimuth
            elevation_deg: Target elevation
            user_id: Optional user association
            sync_after_steer: Whether to run sync after steering

        Returns:
            BeamSteerResult with beam quality metrics
        """
        wavelength_mm = self.config.frequency.wavelength_mm

        # Configure beam with steering vector
        beam = self.array.steer_beam(
            beam_id, azimuth_deg, elevation_deg, wavelength_mm, user_id,
        )

        # Synchronize phases toward steering vector
        if sync_after_steer and beam.steering_phases:
            sync_result = self.synchronize(target_phases=beam.steering_phases)
        else:
            sync_result = SyncResult(
                coherence=self.array.global_coherence,
                mean_phase_error_deg=0.0,
                max_phase_error_deg=0.0,
                iterations=0,
                converged=True,
                sync_state=self.array.sync_state,
                per_panel_coherence=self.array.get_per_panel_coherence(),
            )

        # Compute actual beam quality with phase errors
        gain_db, sidelobe_db = self._compute_beam_quality(beam)
        success = (
            sync_result.converged
            and gain_db >= self.config.thresholds.min_beam_gain_db * 0.8
        )

        return BeamSteerResult(
            beam_id=beam_id,
            azimuth_deg=azimuth_deg,
            elevation_deg=elevation_deg,
            gain_db=gain_db,
            sidelobe_db=sidelobe_db,
            sync_error_deg=sync_result.mean_phase_error_deg,
            success=success,
        )

    def multi_beam_steer(
        self,
        beam_configs: List[Tuple[int, float, float, Optional[int]]],
    ) -> List[BeamSteerResult]:
        """
        Steer multiple beams for multi-user MIMO.

        Args:
            beam_configs: List of (beam_id, azimuth, elevation, user_id)

        Returns:
            List of BeamSteerResult for each beam
        """
        results = []
        for beam_id, az, el, uid in beam_configs:
            result = self.steer_beam(beam_id, az, el, uid, sync_after_steer=True)
            results.append(result)
        return results

    def _adapt_learning_rate(self) -> float:
        """
        Adapt learning rate based on coherence trajectory.

        - High coherence, stable -> reduce LR for fine-tuning
        - Low coherence -> increase LR for faster convergence
        - Oscillating coherence -> reduce LR to avoid overshooting
        """
        coherence = self.array.global_coherence
        self._coherence_history.append(coherence)

        if len(self._coherence_history) > self._lr_adaptation_window:
            self._coherence_history.pop(0)

        if len(self._coherence_history) < 3:
            return self._base_lr

        # Check for oscillation (alternating increases and decreases)
        diffs = [
            self._coherence_history[i] - self._coherence_history[i - 1]
            for i in range(1, len(self._coherence_history))
        ]
        sign_changes = sum(
            1 for i in range(1, len(diffs))
            if (diffs[i] > 0) != (diffs[i - 1] > 0)
        )
        oscillating = sign_changes > len(diffs) * 0.5

        if oscillating:
            # Reduce LR to dampen oscillations
            self._current_lr = self._base_lr * 0.3
        elif coherence > 0.9:
            # Fine-tuning mode
            self._current_lr = self._base_lr * 0.5
        elif coherence < 0.5:
            # Fast convergence mode
            self._current_lr = self._base_lr * 1.5
        else:
            self._current_lr = self._base_lr

        return self._current_lr

    def _is_stable(self) -> bool:
        """Check if coherence is stable (for lock detection)."""
        if len(self._lock_coherence_history) < self._lock_check_window:
            return False

        # Check variance of recent coherence values
        mean_c = sum(self._lock_coherence_history) / len(self._lock_coherence_history)
        variance = sum(
            (c - mean_c) ** 2 for c in self._lock_coherence_history
        ) / len(self._lock_coherence_history)

        # Stable if variance is small
        return variance < 0.001

    def _compute_beam_quality(self, beam: BeamState) -> Tuple[float, float]:
        """
        Compute beam gain and sidelobe level considering phase errors.

        Returns:
            (gain_db, sidelobe_level_db)
        """
        if not beam.assigned_elements:
            return 0.0, 0.0

        n = len(beam.assigned_elements)

        # Ideal gain = 10*log10(N)
        ideal_gain_db = 10.0 * math.log10(n)

        # Gain loss due to phase errors
        # Array factor magnitude: |AF| = |sum(exp(j*phase_error_i))| / N
        af_real = 0.0
        af_imag = 0.0
        for elem_id in beam.assigned_elements:
            elem = self.array.elements.get(elem_id)
            if elem is None:
                continue
            target = beam.steering_phases.get(elem_id, 0.0)
            error = elem.phase - target
            af_real += math.cos(error)
            af_imag += math.sin(error)

        af_magnitude = math.sqrt(af_real**2 + af_imag**2) / n
        gain_loss_db = 20.0 * math.log10(max(af_magnitude, 1e-10))

        actual_gain_db = ideal_gain_db + gain_loss_db

        # Estimate sidelobe level (simplified)
        # With phase errors, sidelobes increase
        ideal_sidelobe = -13.3  # First sidelobe of uniform array
        rms_error = 0.0
        for elem_id in beam.assigned_elements:
            elem = self.array.elements.get(elem_id)
            if elem is None:
                continue
            target = beam.steering_phases.get(elem_id, 0.0)
            error = elem.phase - target
            rms_error += error**2
        rms_error = math.sqrt(rms_error / n) if n > 0 else 0.0

        # Phase errors raise sidelobe floor
        sidelobe_floor_db = 10.0 * math.log10(max(rms_error**2, 1e-10))
        sidelobe_db = max(ideal_sidelobe, sidelobe_floor_db)

        return actual_gain_db, sidelobe_db
