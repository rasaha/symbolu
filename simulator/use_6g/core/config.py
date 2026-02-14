"""
Configuration for USE-6G Massive MIMO simulator.

Defines antenna array parameters, timing constraints, frequency bands,
and synchronization thresholds for 6G phone applications.

Reference: UCP Spec Section 5.1 (6G Telecom: $110B/yr TAM)
Key requirement: +/-100ps phase precision for Massive MIMO synchronization.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List
import math


class FrequencyBand(Enum):
    """6G candidate frequency bands."""
    FR3_UPPER = "fr3_upper"        # 7-24 GHz (upper mid-band)
    FR2_MMWAVE = "fr2_mmwave"      # 24-71 GHz (mmWave, 5G-Advanced/6G)
    SUB_THZ_LOW = "sub_thz_low"    # 100-300 GHz (sub-THz, 6G primary)
    SUB_THZ_HIGH = "sub_thz_high"  # 300 GHz - 1 THz (sub-THz, 6G research)


class ArrayTopology(Enum):
    """Antenna array physical layout."""
    ULA = "ula"        # Uniform Linear Array
    UPA = "upa"        # Uniform Planar Array (rectangular grid)
    UCA = "uca"        # Uniform Circular Array


@dataclass
class FrequencyConfig:
    """Frequency band parameters."""
    band: FrequencyBand = FrequencyBand.SUB_THZ_LOW

    @property
    def carrier_freq_ghz(self) -> float:
        """Representative carrier frequency in GHz."""
        freqs = {
            FrequencyBand.FR3_UPPER: 15.0,
            FrequencyBand.FR2_MMWAVE: 39.0,
            FrequencyBand.SUB_THZ_LOW: 140.0,
            FrequencyBand.SUB_THZ_HIGH: 500.0,
        }
        return freqs[self.band]

    @property
    def wavelength_mm(self) -> float:
        """Wavelength in millimeters."""
        # lambda = c / f
        c_mm_per_ns = 299.792458  # speed of light in mm/ns
        freq_ghz = self.carrier_freq_ghz
        return c_mm_per_ns / freq_ghz

    @property
    def max_phase_error_rad(self) -> float:
        """Maximum tolerable phase error in radians.

        At sub-THz frequencies, even 100ps timing error produces
        significant phase drift. This computes the phase error
        corresponding to the timing precision target.
        """
        timing_precision_ps = 100.0  # +/-100ps from UCP spec
        freq_hz = self.carrier_freq_ghz * 1e9
        # phase_error = 2*pi * f * dt
        return 2.0 * math.pi * freq_hz * (timing_precision_ps * 1e-12)

    @property
    def bandwidth_ghz(self) -> float:
        """Channel bandwidth in GHz."""
        bw = {
            FrequencyBand.FR3_UPPER: 0.4,
            FrequencyBand.FR2_MMWAVE: 2.0,
            FrequencyBand.SUB_THZ_LOW: 10.0,
            FrequencyBand.SUB_THZ_HIGH: 50.0,
        }
        return bw[self.band]


@dataclass
class AntennaConfig:
    """Antenna array configuration for 6G phone form factor."""
    # Array dimensions
    num_elements_x: int = 8     # Elements along x-axis
    num_elements_y: int = 8     # Elements along y-axis (1 for ULA)
    topology: ArrayTopology = ArrayTopology.UPA

    # Element spacing as fraction of wavelength
    element_spacing_lambda: float = 0.5

    # Number of RF chains (hybrid beamforming)
    num_rf_chains: int = 4

    # Number of simultaneous beams
    max_beams: int = 4

    # Panel count (multi-panel for phone form factor)
    num_panels: int = 2

    @property
    def total_elements(self) -> int:
        """Total antenna elements across all panels."""
        if self.topology == ArrayTopology.ULA:
            return self.num_elements_x * self.num_panels
        return self.num_elements_x * self.num_elements_y * self.num_panels

    @property
    def elements_per_panel(self) -> int:
        """Elements per panel."""
        if self.topology == ArrayTopology.ULA:
            return self.num_elements_x
        return self.num_elements_x * self.num_elements_y


@dataclass
class TimingConfig:
    """Timing and synchronization parameters."""
    # Phase synchronization
    timing_precision_ps: float = 100.0       # +/-100ps (UCP spec)
    sync_update_interval_us: float = 10.0    # Phase update period
    max_drift_rate_ps_per_ms: float = 1.0    # Max acceptable drift

    # USE algorithm parameters (from patent U1-U5)
    sync_learning_rate: float = 0.1          # U4: alpha for phase updates
    correlation_window: int = 16             # U1: sliding window W for correlation
    mean_field_enabled: bool = True          # U3: O(n) mean-field approximation

    # Convergence criteria
    coherence_threshold: float = 0.95        # Min global coherence for sync lock
    max_sync_iterations: int = 50            # Max iterations to achieve lock
    phase_lock_hysteresis: float = 0.02      # Hysteresis band for lock/unlock


@dataclass
class PowerConfig:
    """Power envelope for UCP-Edge mobile form factor."""
    max_power_w: float = 15.0       # UCP-Edge: 10-20W
    idle_power_w: float = 0.5       # Idle/sleep power
    sync_power_w: float = 3.0       # During synchronization
    beamform_power_w: float = 8.0   # During active beamforming

    # Thermal constraints (phone form factor)
    max_junction_temp_c: float = 105.0
    thermal_throttle_temp_c: float = 90.0


@dataclass
class AcceptanceThresholds:
    """Validation acceptance thresholds for USE-6G chip."""
    # Phase synchronization quality
    min_global_coherence: float = 0.95       # Global coherence >= 0.95
    max_phase_error_deg: float = 5.0         # Max per-element phase error
    max_sync_time_us: float = 500.0          # Time to achieve phase lock

    # Beamforming performance
    min_beam_gain_db: float = 15.0           # Minimum array gain
    max_sidelobe_level_db: float = -13.0     # Max sidelobe relative to main
    min_null_depth_db: float = -25.0         # Interference null depth

    # Throughput
    min_sync_updates_per_sec: float = 100e3  # 100K sync updates/sec
    min_beam_steers_per_sec: float = 10e3    # 10K beam steers/sec

    # Power
    max_sync_power_w: float = 5.0            # Power during sync operations
    max_total_power_w: float = 20.0          # Total chip power

    # Hardware
    max_area_mm2: float = 25.0               # Die area
    target_process_nm: int = 4               # 4nm target for mobile


@dataclass
class USE6GConfig:
    """
    Complete USE-6G simulator configuration.

    Combines all sub-configurations for simulating a USE chip
    targeting 6G phone Massive MIMO synchronization.
    """
    # Sub-configurations
    frequency: FrequencyConfig = field(default_factory=FrequencyConfig)
    antenna: AntennaConfig = field(default_factory=AntennaConfig)
    timing: TimingConfig = field(default_factory=TimingConfig)
    power: PowerConfig = field(default_factory=PowerConfig)
    thresholds: AcceptanceThresholds = field(default_factory=AcceptanceThresholds)

    # Simulation settings
    simulation_duration_ms: float = 100.0    # Simulation duration
    time_step_us: float = 1.0               # Simulation time step
    enable_channel_fading: bool = True       # Simulate channel variations
    enable_mobility: bool = True             # Simulate phone movement
    random_seed: int = 42

    def summary(self) -> str:
        """Human-readable configuration summary."""
        lines = [
            "=== USE-6G Configuration ===",
            f"Frequency: {self.frequency.carrier_freq_ghz} GHz "
            f"({self.frequency.band.value})",
            f"Wavelength: {self.frequency.wavelength_mm:.2f} mm",
            f"Bandwidth: {self.frequency.bandwidth_ghz} GHz",
            f"Max phase error at timing precision: "
            f"{math.degrees(self.frequency.max_phase_error_rad):.1f} deg",
            f"",
            f"Antenna: {self.antenna.total_elements} elements "
            f"({self.antenna.num_elements_x}x{self.antenna.num_elements_y} "
            f"x{self.antenna.num_panels} panels, "
            f"{self.antenna.topology.value})",
            f"RF chains: {self.antenna.num_rf_chains}",
            f"Max beams: {self.antenna.max_beams}",
            f"",
            f"Timing: +/-{self.timing.timing_precision_ps}ps precision",
            f"Sync rate: {self.timing.sync_learning_rate}",
            f"Coherence target: {self.timing.coherence_threshold}",
            f"",
            f"Power: {self.power.max_power_w}W max "
            f"(sync: {self.power.sync_power_w}W, "
            f"beam: {self.power.beamform_power_w}W)",
        ]
        return "\n".join(lines)
