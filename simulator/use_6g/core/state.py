"""
State management for USE-6G Massive MIMO simulator.

Tracks antenna element phases, synchronization state, beam configurations,
and channel conditions. Implements the USE patent formulas (U1-U5)
for phase-coherent MIMO synchronization.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set
from enum import Enum
import math
import numpy as np


class SyncState(Enum):
    """Phase synchronization state machine."""
    UNSYNCHRONIZED = "unsynchronized"
    ACQUIRING = "acquiring"        # Actively converging
    LOCKED = "locked"              # Phase lock achieved
    TRACKING = "tracking"          # Maintaining lock with drift correction
    LOST = "lost"                  # Lock lost, needs re-acquisition


@dataclass
class AntennaElement:
    """State of a single antenna element."""
    element_id: int
    panel_id: int

    # Physical position (relative to array center, in wavelengths)
    pos_x: float = 0.0
    pos_y: float = 0.0

    # Current phase state (radians)
    phase: float = 0.0
    target_phase: float = 0.0

    # Phase error tracking
    phase_error_history: List[float] = field(default_factory=list)
    max_history: int = 64

    # Calibration
    phase_offset_cal: float = 0.0    # Factory calibration offset
    amplitude_cal: float = 1.0       # Element gain calibration

    # Operational state
    active: bool = True
    failed: bool = False

    @property
    def current_error_rad(self) -> float:
        """Current phase error in radians."""
        diff = self.target_phase - self.phase
        # Wrap to [-pi, pi]
        return (diff + math.pi) % (2 * math.pi) - math.pi

    @property
    def current_error_deg(self) -> float:
        """Current phase error in degrees."""
        return math.degrees(self.current_error_rad)

    @property
    def rms_error_rad(self) -> float:
        """RMS phase error over recent history."""
        if not self.phase_error_history:
            return 0.0
        squared = [e * e for e in self.phase_error_history]
        return math.sqrt(sum(squared) / len(squared))

    def update_phase(self, new_phase: float) -> None:
        """Update element phase and record error."""
        self.phase = new_phase % (2 * math.pi)
        error = self.current_error_rad
        self.phase_error_history.append(error)
        if len(self.phase_error_history) > self.max_history:
            self.phase_error_history.pop(0)


@dataclass
class BeamState:
    """State of a single beam."""
    beam_id: int

    # Beam direction (azimuth, elevation in degrees)
    azimuth_deg: float = 0.0
    elevation_deg: float = 0.0

    # Beam quality metrics
    gain_db: float = 0.0
    sidelobe_level_db: float = 0.0
    half_power_beamwidth_deg: float = 0.0

    # Target steering vector (per-element phases)
    steering_phases: Dict[int, float] = field(default_factory=dict)

    # Active element assignments
    assigned_elements: Set[int] = field(default_factory=set)

    # Tracking state
    active: bool = False
    user_id: Optional[int] = None


@dataclass
class ChannelState:
    """Simulated channel conditions."""
    # Path loss (dB)
    path_loss_db: float = 80.0

    # Fading state per element
    fading_amplitudes: Dict[int, float] = field(default_factory=dict)
    fading_phases: Dict[int, float] = field(default_factory=dict)

    # Doppler (from mobility)
    doppler_shift_hz: float = 0.0

    # Interference
    interference_power_dbm: float = -90.0
    num_interferers: int = 0

    # SNR
    snr_db: float = 20.0


class AntennaArrayState:
    """
    Complete antenna array state manager.

    Implements USE patent formulas for phase synchronization:
    - U1: Correlation matrix between antenna elements
    - U2: Total coherence objective across the array
    - U3: Mean-field gradient for O(n) phase optimization
    - U4: Phase update rule
    - U5: Correlation interpretation and thresholds
    """

    def __init__(
        self,
        num_elements_x: int = 8,
        num_elements_y: int = 8,
        num_panels: int = 2,
        element_spacing_lambda: float = 0.5,
        num_rf_chains: int = 4,
        max_beams: int = 4,
    ):
        self.num_elements_x = num_elements_x
        self.num_elements_y = num_elements_y
        self.num_panels = num_panels
        self.element_spacing = element_spacing_lambda
        self.num_rf_chains = num_rf_chains
        self.max_beams = max_beams

        # Phase history for correlation computation (U1)
        self._phase_history: Dict[int, List[float]] = {}
        self._correlation_window: int = 16

        # Initialize antenna elements
        self.elements: Dict[int, AntennaElement] = {}
        self._init_elements()

        # Beam states
        self.beams: Dict[int, BeamState] = {
            i: BeamState(beam_id=i) for i in range(max_beams)
        }

        # Channel state
        self.channel = ChannelState()

        # Synchronization state
        self.sync_state = SyncState.UNSYNCHRONIZED
        self.global_coherence: float = 0.0
        self.sync_iterations: int = 0
        self.total_sync_updates: int = 0

        # Timing
        self.current_time_us: float = 0.0

    def _init_elements(self) -> None:
        """Initialize antenna elements with physical positions."""
        elem_id = 0
        for panel in range(self.num_panels):
            for y in range(self.num_elements_y):
                for x in range(self.num_elements_x):
                    # Position relative to panel center (in wavelengths)
                    pos_x = (x - (self.num_elements_x - 1) / 2) * self.element_spacing
                    pos_y = (y - (self.num_elements_y - 1) / 2) * self.element_spacing

                    # Offset panels (e.g., opposite sides of phone)
                    if panel > 0:
                        pos_x += panel * self.num_elements_x * self.element_spacing * 1.5

                    self.elements[elem_id] = AntennaElement(
                        element_id=elem_id,
                        panel_id=panel,
                        pos_x=pos_x,
                        pos_y=pos_y,
                    )
                    self._phase_history[elem_id] = []
                    elem_id += 1

    @property
    def total_elements(self) -> int:
        return len(self.elements)

    @property
    def active_elements(self) -> List[AntennaElement]:
        return [e for e in self.elements.values() if e.active and not e.failed]

    def compute_steering_vector(
        self,
        azimuth_deg: float,
        elevation_deg: float,
        wavelength_mm: float,
    ) -> Dict[int, float]:
        """
        Compute steering vector phases for a given beam direction.

        Args:
            azimuth_deg: Beam azimuth angle in degrees
            elevation_deg: Beam elevation angle in degrees
            wavelength_mm: Operating wavelength in mm

        Returns:
            Dict mapping element_id to target phase (radians)
        """
        az_rad = math.radians(azimuth_deg)
        el_rad = math.radians(elevation_deg)

        # Direction cosines
        u = math.sin(az_rad) * math.cos(el_rad)
        v = math.sin(el_rad)

        steering = {}
        for elem_id, elem in self.elements.items():
            if not elem.active or elem.failed:
                continue
            # Phase = 2*pi/lambda * (x*u + y*v) * lambda * spacing
            # Since positions are already in wavelengths:
            phase = 2.0 * math.pi * (elem.pos_x * u + elem.pos_y * v)
            # Apply calibration offset
            phase += elem.phase_offset_cal
            steering[elem_id] = phase % (2 * math.pi)

        return steering

    def compute_correlation_matrix(self) -> np.ndarray:
        """
        Compute U1: Pairwise correlation matrix between antenna elements.

        Formula (from USE patent):
            C[i,j] = (1/W) * sum_{k=0}^{W-1} cos(phi_i(t-k) - phi_j(t-k))

        Uses phase history for windowed correlation.

        Returns:
            Correlation matrix (n_elements x n_elements)
        """
        active = self.active_elements
        n = len(active)
        if n == 0:
            return np.array([[]])

        # Build phase history matrix
        W = self._correlation_window
        phase_matrix = []  # [n_elements, W]
        elem_ids = []

        for elem in active:
            history = self._phase_history.get(elem.element_id, [])
            if len(history) < W:
                # Pad with current phase
                padded = [elem.phase] * (W - len(history)) + history
            else:
                padded = history[-W:]
            phase_matrix.append(padded)
            elem_ids.append(elem.element_id)

        phase_array = np.array(phase_matrix)  # [n, W]

        # Compute pairwise correlation
        C = np.zeros((n, n))
        for i in range(n):
            C[i, i] = 1.0  # Self-correlation
            for j in range(i + 1, n):
                phase_diff = phase_array[i] - phase_array[j]
                correlation = np.mean(np.cos(phase_diff))
                C[i, j] = correlation
                C[j, i] = correlation

        return C

    def compute_total_coherence(
        self,
        coupling_matrix: Optional[np.ndarray] = None,
    ) -> float:
        """
        Compute U2: Total coherence objective.

        Formula:
            C_total = sum_{i<j} M_ij * C[i,j]
            C_normalized = C_total / (n*(n-1)/2)

        Args:
            coupling_matrix: Optional coupling weights M_ij

        Returns:
            Normalized total coherence in [-1, 1]
        """
        active = self.active_elements
        n = len(active)
        if n < 2:
            return 1.0

        phases = {elem.element_id: elem.phase for elem in active}
        elem_ids = list(phases.keys())

        c_total = 0.0
        num_pairs = 0

        for i_idx in range(n):
            for j_idx in range(i_idx + 1, n):
                phase_diff = phases[elem_ids[i_idx]] - phases[elem_ids[j_idx]]
                correlation = math.cos(phase_diff)

                if coupling_matrix is not None:
                    correlation *= coupling_matrix[i_idx, j_idx]

                c_total += correlation
                num_pairs += 1

        if num_pairs == 0:
            return 0.0

        return c_total / num_pairs

    def compute_gradient_mean_field(
        self,
        element_id: int,
    ) -> float:
        """
        Compute U3: Mean-field gradient for O(n) phase optimization.

        Formula:
            dC/dphi_i ~= -N * sin(phi_i - phi_mean)

        Where phi_mean is the mean phase of all other elements.
        This is O(n) vs. O(n^2) for exact pairwise gradients.

        Args:
            element_id: Target element for gradient computation

        Returns:
            Phase gradient (radians)
        """
        elem = self.elements.get(element_id)
        if elem is None or not elem.active:
            return 0.0

        active = self.active_elements
        other_phases = [
            e.phase for e in active
            if e.element_id != element_id
        ]

        if not other_phases:
            return 0.0

        # Mean phase using circular mean (handles wraparound)
        sin_sum = sum(math.sin(p) for p in other_phases)
        cos_sum = sum(math.cos(p) for p in other_phases)
        phi_mean = math.atan2(sin_sum, cos_sum)

        # Normalize by N for stable convergence in large arrays
        # (standard Kuramoto coupling strength)
        gradient = -math.sin(elem.phase - phi_mean)
        return gradient

    def synchronize_step(
        self,
        learning_rate: float = 0.1,
        target_phases: Optional[Dict[int, float]] = None,
    ) -> float:
        """
        Execute U4: One synchronization step for all elements.

        Formula:
            delta_phi_i = alpha * dC/dphi_i
            phi_i(t+1) = (phi_i(t) + delta_phi_i) mod 2*pi

        If target_phases is provided, elements synchronize toward
        the target steering vector (beamforming mode).
        Otherwise, elements synchronize toward mutual coherence.

        Args:
            learning_rate: U4 alpha parameter
            target_phases: Optional target phases for beamforming

        Returns:
            Mean absolute phase update (convergence indicator)
        """
        total_update = 0.0
        count = 0

        for elem in self.active_elements:
            if target_phases and elem.element_id in target_phases:
                # Beamforming mode: steer toward target
                target = target_phases[elem.element_id]
                error = target - elem.phase
                # Wrap to [-pi, pi]
                error = (error + math.pi) % (2 * math.pi) - math.pi
                delta = learning_rate * error
            else:
                # Coherence mode: USE mean-field gradient
                gradient = self.compute_gradient_mean_field(elem.element_id)
                delta = learning_rate * gradient

            new_phase = (elem.phase + delta) % (2 * math.pi)
            elem.update_phase(new_phase)

            # Record in phase history for U1 correlation
            history = self._phase_history[elem.element_id]
            history.append(new_phase)
            if len(history) > self._correlation_window * 2:
                self._phase_history[elem.element_id] = history[-self._correlation_window * 2:]

            total_update += abs(delta)
            count += 1

        self.sync_iterations += 1
        self.total_sync_updates += count

        mean_update = total_update / count if count > 0 else 0.0

        # Update global coherence
        self.global_coherence = self.compute_total_coherence()

        return mean_update

    def compute_beam_coherence(
        self,
        target_phases: Dict[int, float],
    ) -> float:
        """
        Compute coherence of array phases relative to a target steering vector.

        Measures how well the array is aligned with the intended beam direction.
        Uses the array factor magnitude: |AF| = |sum(exp(j*(phase_i - target_i)))| / N

        This is the correct metric for beamforming scenarios, where elements
        intentionally have different phases.

        Args:
            target_phases: Target steering vector (element_id -> phase)

        Returns:
            Beam coherence in [0, 1] (1 = perfect alignment)
        """
        af_real = 0.0
        af_imag = 0.0
        count = 0

        for elem in self.active_elements:
            target = target_phases.get(elem.element_id)
            if target is None:
                continue
            error = elem.phase - target
            af_real += math.cos(error)
            af_imag += math.sin(error)
            count += 1

        if count == 0:
            return 0.0

        return math.sqrt(af_real**2 + af_imag**2) / count

    def evaluate_correlation(self, i: int, j: int) -> str:
        """
        Apply U5: Correlation interpretation.

        Thresholds:
            C[i,j] > 0.7: Strong alignment
            0.3 < C[i,j] < 0.7: Moderate correlation
            C[i,j] < 0.3: Weak or no correlation
            C[i,j] < -0.3: Anti-correlation (issue)

        Returns:
            Classification string
        """
        elem_i = self.elements.get(i)
        elem_j = self.elements.get(j)
        if elem_i is None or elem_j is None:
            return "invalid"

        phase_diff = elem_i.phase - elem_j.phase
        c = math.cos(phase_diff)

        if c > 0.7:
            return "strong_alignment"
        elif c > 0.3:
            return "moderate_correlation"
        elif c > -0.3:
            return "weak_correlation"
        else:
            return "anti_correlation"

    def steer_beam(
        self,
        beam_id: int,
        azimuth_deg: float,
        elevation_deg: float,
        wavelength_mm: float,
        user_id: Optional[int] = None,
    ) -> BeamState:
        """
        Configure a beam with target steering vector.

        Args:
            beam_id: Beam index
            azimuth_deg: Target azimuth
            elevation_deg: Target elevation
            wavelength_mm: Operating wavelength
            user_id: Optional user association

        Returns:
            Updated BeamState
        """
        if beam_id not in self.beams:
            return BeamState(beam_id=beam_id)

        beam = self.beams[beam_id]
        beam.azimuth_deg = azimuth_deg
        beam.elevation_deg = elevation_deg
        beam.active = True
        beam.user_id = user_id

        # Compute steering vector
        steering = self.compute_steering_vector(
            azimuth_deg, elevation_deg, wavelength_mm
        )
        beam.steering_phases = steering
        beam.assigned_elements = set(steering.keys())

        # Estimate beam metrics
        n_active = len(beam.assigned_elements)
        if n_active > 0:
            beam.gain_db = 10.0 * math.log10(n_active)
            beam.half_power_beamwidth_deg = 51.0 / (
                math.sqrt(n_active) * self.element_spacing
            )

        return beam

    def apply_channel_effects(
        self,
        rng: np.random.Generator,
        doppler_hz: float = 0.0,
        time_step_us: float = 1.0,
    ) -> None:
        """
        Apply simulated channel fading and drift to element phases.

        Simulates real-world impairments:
        - Rayleigh fading amplitude variations
        - Phase noise from oscillator drift
        - Doppler-induced phase shifts from mobility
        """
        # Doppler shift is a uniform carrier offset for all elements
        doppler_phase = 0.0
        if doppler_hz > 0:
            doppler_phase = 2.0 * math.pi * doppler_hz * time_step_us * 1e-6

        for elem in self.active_elements:
            # Phase noise (oscillator jitter, per-element independent)
            phase_noise = rng.normal(0, 0.005)  # ~0.3 deg RMS

            # Doppler is a common-mode shift (same for all elements)
            total_noise = phase_noise + doppler_phase

            # Apply perturbation (no update_phase to avoid double-recording)
            elem.phase = (elem.phase + total_noise) % (2 * math.pi)

            # Update channel fading per element
            fade_amplitude = abs(rng.normal(1.0, 0.1))
            self.channel.fading_amplitudes[elem.element_id] = fade_amplitude
            self.channel.fading_phases[elem.element_id] = rng.uniform(0, 2 * math.pi)

    def detect_element_failures(self, threshold_rad: float = 1.0) -> List[int]:
        """
        Detect elements with persistently high phase error.

        Returns list of element IDs with suspected failures.
        """
        failures = []
        for elem in self.elements.values():
            if elem.failed:
                continue
            if elem.rms_error_rad > threshold_rad:
                failures.append(elem.element_id)
        return failures

    def get_per_panel_coherence(self) -> Dict[int, float]:
        """Compute coherence per panel (useful for multi-panel phones)."""
        panel_coherence = {}
        for panel_id in range(self.num_panels):
            panel_elements = [
                e for e in self.active_elements if e.panel_id == panel_id
            ]
            if len(panel_elements) < 2:
                panel_coherence[panel_id] = 1.0
                continue

            phases = [e.phase for e in panel_elements]
            sin_sum = sum(math.sin(p) for p in phases)
            cos_sum = sum(math.cos(p) for p in phases)
            # Circular coherence (resultant length / n)
            R = math.sqrt(sin_sum**2 + cos_sum**2) / len(phases)
            panel_coherence[panel_id] = R

        return panel_coherence

    def get_stats(self) -> Dict:
        """Get current array statistics."""
        active = self.active_elements
        phase_errors = [abs(e.current_error_rad) for e in active]

        return {
            "total_elements": self.total_elements,
            "active_elements": len(active),
            "failed_elements": sum(1 for e in self.elements.values() if e.failed),
            "sync_state": self.sync_state.value,
            "global_coherence": self.global_coherence,
            "sync_iterations": self.sync_iterations,
            "total_sync_updates": self.total_sync_updates,
            "mean_phase_error_deg": math.degrees(
                sum(phase_errors) / len(phase_errors)
            ) if phase_errors else 0.0,
            "max_phase_error_deg": math.degrees(
                max(phase_errors)
            ) if phase_errors else 0.0,
            "per_panel_coherence": self.get_per_panel_coherence(),
            "active_beams": sum(1 for b in self.beams.values() if b.active),
        }
