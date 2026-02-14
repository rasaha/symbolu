"""
Metrics collection for USE-6G Massive MIMO validation.

Tracks synchronization quality, beamforming performance,
power consumption, and timing precision.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import statistics
import math


@dataclass
class LatencyStats:
    """Latency distribution statistics (reusable from PCAM pattern)."""
    samples: List[float] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0.0

    @property
    def p50(self) -> float:
        if not self.samples:
            return 0.0
        return statistics.median(self.samples)

    @property
    def p95(self) -> float:
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(0.95 * len(sorted_samples))
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

    @property
    def p99(self) -> float:
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(0.99 * len(sorted_samples))
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

    def add(self, value: float) -> None:
        self.samples.append(value)

    def to_dict(self) -> Dict:
        return {
            "count": self.count,
            "mean": self.mean,
            "p50": self.p50,
            "p95": self.p95,
            "p99": self.p99,
            "min": min(self.samples) if self.samples else 0.0,
            "max": max(self.samples) if self.samples else 0.0,
        }


@dataclass
class SyncMetrics:
    """Phase synchronization quality metrics."""
    # Coherence over time
    coherence_samples: List[float] = field(default_factory=list)

    # Phase error distribution (degrees)
    phase_error_samples: List[float] = field(default_factory=list)

    # Time to lock (microseconds)
    time_to_lock_samples: List[float] = field(default_factory=list)

    # Sync iterations to converge
    iterations_to_lock_samples: List[int] = field(default_factory=list)

    # Lock maintenance (fraction of time in locked state)
    lock_time_us: float = 0.0
    total_time_us: float = 0.0

    @property
    def mean_coherence(self) -> float:
        return statistics.mean(self.coherence_samples) if self.coherence_samples else 0.0

    @property
    def min_coherence(self) -> float:
        return min(self.coherence_samples) if self.coherence_samples else 0.0

    @property
    def mean_phase_error_deg(self) -> float:
        return statistics.mean(self.phase_error_samples) if self.phase_error_samples else 0.0

    @property
    def max_phase_error_deg(self) -> float:
        return max(self.phase_error_samples) if self.phase_error_samples else 0.0

    @property
    def mean_time_to_lock_us(self) -> float:
        return statistics.mean(self.time_to_lock_samples) if self.time_to_lock_samples else 0.0

    @property
    def lock_ratio(self) -> float:
        return self.lock_time_us / self.total_time_us if self.total_time_us > 0 else 0.0

    def add_coherence(self, coherence: float) -> None:
        self.coherence_samples.append(coherence)

    def add_phase_error(self, error_deg: float) -> None:
        self.phase_error_samples.append(error_deg)

    def add_lock_event(self, time_us: float, iterations: int) -> None:
        self.time_to_lock_samples.append(time_us)
        self.iterations_to_lock_samples.append(iterations)

    def to_dict(self) -> Dict:
        return {
            "mean_coherence": round(self.mean_coherence, 4),
            "min_coherence": round(self.min_coherence, 4),
            "mean_phase_error_deg": round(self.mean_phase_error_deg, 2),
            "max_phase_error_deg": round(self.max_phase_error_deg, 2),
            "mean_time_to_lock_us": round(self.mean_time_to_lock_us, 1),
            "lock_ratio": round(self.lock_ratio, 4),
            "coherence_samples": len(self.coherence_samples),
        }


@dataclass
class BeamformingMetrics:
    """Beamforming performance metrics."""
    # Array gain (dB)
    gain_samples: List[float] = field(default_factory=list)

    # Sidelobe levels (dB)
    sidelobe_samples: List[float] = field(default_factory=list)

    # Beam steering operations
    total_steers: int = 0
    successful_steers: int = 0

    # Multi-user MIMO
    total_users_served: int = 0
    simultaneous_beams_max: int = 0

    @property
    def mean_gain_db(self) -> float:
        return statistics.mean(self.gain_samples) if self.gain_samples else 0.0

    @property
    def mean_sidelobe_db(self) -> float:
        return statistics.mean(self.sidelobe_samples) if self.sidelobe_samples else 0.0

    @property
    def steer_success_rate(self) -> float:
        return self.successful_steers / self.total_steers if self.total_steers > 0 else 0.0

    def add_gain(self, gain_db: float) -> None:
        self.gain_samples.append(gain_db)

    def add_sidelobe(self, sidelobe_db: float) -> None:
        self.sidelobe_samples.append(sidelobe_db)

    def record_steer(self, success: bool) -> None:
        self.total_steers += 1
        if success:
            self.successful_steers += 1

    def to_dict(self) -> Dict:
        return {
            "mean_gain_db": round(self.mean_gain_db, 1),
            "mean_sidelobe_db": round(self.mean_sidelobe_db, 1),
            "total_steers": self.total_steers,
            "steer_success_rate": round(self.steer_success_rate, 4),
            "simultaneous_beams_max": self.simultaneous_beams_max,
        }


@dataclass
class PowerMetrics:
    """Power consumption metrics."""
    # Energy samples (watts * microseconds)
    energy_samples_wus: List[float] = field(default_factory=list)

    # Power by mode
    sync_energy_wus: float = 0.0
    beamform_energy_wus: float = 0.0
    idle_energy_wus: float = 0.0

    # Peak power
    peak_power_w: float = 0.0

    @property
    def total_energy_wus(self) -> float:
        return self.sync_energy_wus + self.beamform_energy_wus + self.idle_energy_wus

    @property
    def mean_power_w(self) -> float:
        if not self.energy_samples_wus:
            return 0.0
        return statistics.mean(self.energy_samples_wus)

    def add_power_sample(self, power_w: float, duration_us: float) -> None:
        energy = power_w * duration_us
        self.energy_samples_wus.append(power_w)
        self.peak_power_w = max(self.peak_power_w, power_w)

    def to_dict(self) -> Dict:
        return {
            "mean_power_w": round(self.mean_power_w, 2),
            "peak_power_w": round(self.peak_power_w, 2),
            "total_energy_wus": round(self.total_energy_wus, 0),
            "sync_energy_fraction": round(
                self.sync_energy_wus / self.total_energy_wus
                if self.total_energy_wus > 0 else 0.0, 3
            ),
        }


@dataclass
class ThroughputMetrics:
    """Throughput and operations metrics."""
    total_sync_ops: int = 0
    total_beam_ops: int = 0
    total_time_us: float = 0.0

    @property
    def sync_ops_per_sec(self) -> float:
        if self.total_time_us <= 0:
            return 0.0
        return self.total_sync_ops / (self.total_time_us * 1e-6)

    @property
    def beam_ops_per_sec(self) -> float:
        if self.total_time_us <= 0:
            return 0.0
        return self.total_beam_ops / (self.total_time_us * 1e-6)

    def to_dict(self) -> Dict:
        return {
            "total_sync_ops": self.total_sync_ops,
            "total_beam_ops": self.total_beam_ops,
            "sync_ops_per_sec": round(self.sync_ops_per_sec, 0),
            "beam_ops_per_sec": round(self.beam_ops_per_sec, 0),
        }


@dataclass
class USE6GMetrics:
    """
    Complete USE-6G metrics for validation.

    Aggregates all metric categories for 6G Massive MIMO
    chip validation.
    """
    sync: SyncMetrics = field(default_factory=SyncMetrics)
    beamforming: BeamformingMetrics = field(default_factory=BeamformingMetrics)
    power: PowerMetrics = field(default_factory=PowerMetrics)
    throughput: ThroughputMetrics = field(default_factory=ThroughputMetrics)

    # Latency breakdowns
    sync_latency: LatencyStats = field(default_factory=LatencyStats)
    steer_latency: LatencyStats = field(default_factory=LatencyStats)

    def check_acceptance_gates(
        self,
        thresholds: Optional[Dict] = None,
    ) -> Dict[str, bool]:
        """
        Check if metrics meet acceptance criteria.

        Returns:
            Dict of gate_name -> passed
        """
        from .config import AcceptanceThresholds
        thresh = AcceptanceThresholds()
        if thresholds:
            for k, v in thresholds.items():
                if hasattr(thresh, k):
                    setattr(thresh, k, v)

        gates = {}

        # Gate 1: Phase synchronization quality
        gates["sync_coherence"] = (
            self.sync.mean_coherence >= thresh.min_global_coherence
        )

        # Gate 2: Phase error
        gates["phase_error"] = (
            self.sync.max_phase_error_deg <= thresh.max_phase_error_deg
        )

        # Gate 3: Sync acquisition time
        gates["sync_time"] = (
            self.sync.mean_time_to_lock_us <= thresh.max_sync_time_us
        )

        # Gate 4: Beamforming gain
        gates["beam_gain"] = (
            self.beamforming.mean_gain_db >= thresh.min_beam_gain_db
        )

        # Gate 5: Throughput
        gates["sync_throughput"] = (
            self.throughput.sync_ops_per_sec >= thresh.min_sync_updates_per_sec
        )
        gates["beam_throughput"] = (
            self.throughput.beam_ops_per_sec >= thresh.min_beam_steers_per_sec
        )

        # Gate 6: Power
        gates["power"] = (
            self.power.peak_power_w <= thresh.max_total_power_w
        )

        return gates

    def to_dict(self) -> Dict:
        return {
            "sync": self.sync.to_dict(),
            "beamforming": self.beamforming.to_dict(),
            "power": self.power.to_dict(),
            "throughput": self.throughput.to_dict(),
            "sync_latency": self.sync_latency.to_dict(),
            "steer_latency": self.steer_latency.to_dict(),
        }

    def summary(self) -> str:
        """Human-readable summary."""
        gates = self.check_acceptance_gates()
        passed = sum(1 for v in gates.values() if v)
        total = len(gates)

        lines = [
            "=== USE-6G Metrics ===",
            "",
            "Synchronization:",
            f"  Mean coherence: {self.sync.mean_coherence:.4f}",
            f"  Min coherence: {self.sync.min_coherence:.4f}",
            f"  Mean phase error: {self.sync.mean_phase_error_deg:.2f} deg",
            f"  Max phase error: {self.sync.max_phase_error_deg:.2f} deg",
            f"  Lock ratio: {self.sync.lock_ratio:.1%}",
            f"  Mean time to lock: {self.sync.mean_time_to_lock_us:.1f} us",
            "",
            "Beamforming:",
            f"  Mean gain: {self.beamforming.mean_gain_db:.1f} dB",
            f"  Steer success: {self.beamforming.steer_success_rate:.1%}",
            f"  Max simultaneous beams: {self.beamforming.simultaneous_beams_max}",
            "",
            "Power:",
            f"  Mean: {self.power.mean_power_w:.2f} W",
            f"  Peak: {self.power.peak_power_w:.2f} W",
            "",
            "Throughput:",
            f"  Sync ops/sec: {self.throughput.sync_ops_per_sec:,.0f}",
            f"  Beam ops/sec: {self.throughput.beam_ops_per_sec:,.0f}",
            "",
            f"Acceptance: {passed}/{total} gates passed",
        ]

        for gate, passed_gate in gates.items():
            status = "PASS" if passed_gate else "FAIL"
            lines.append(f"  [{status}] {gate}")

        return "\n".join(lines)


class MetricsCollector:
    """
    Collects metrics during USE-6G simulation.

    Usage:
        collector = MetricsCollector()
        collector.start()
        collector.record_sync_step(coherence, phase_error_deg)
        collector.record_beam_steer(gain_db, success)
        metrics = collector.finalize()
    """

    def __init__(self):
        self.metrics = USE6GMetrics()
        self._start_time_us: float = 0.0
        self._current_time_us: float = 0.0
        self._lock_start_time: Optional[float] = None

    def start(self, time_us: float = 0.0) -> None:
        self._start_time_us = time_us
        self._current_time_us = time_us

    def record_sync_step(
        self,
        coherence: float,
        mean_phase_error_deg: float,
        max_phase_error_deg: float,
        time_us: float,
        power_w: float,
    ) -> None:
        """Record a synchronization step."""
        self.metrics.sync.add_coherence(coherence)
        self.metrics.sync.add_phase_error(max_phase_error_deg)
        self.metrics.throughput.total_sync_ops += 1

        duration = time_us - self._current_time_us
        self.metrics.power.add_power_sample(power_w, duration)
        self.metrics.power.sync_energy_wus += power_w * duration
        self.metrics.sync.total_time_us = time_us - self._start_time_us

        self._current_time_us = time_us

    def record_lock_acquired(self, time_us: float, iterations: int) -> None:
        """Record phase lock acquisition."""
        if self._lock_start_time is not None:
            lock_time = time_us - self._lock_start_time
            self.metrics.sync.add_lock_event(lock_time, iterations)
        self._lock_start_time = time_us

    def record_lock_maintained(self, duration_us: float) -> None:
        """Record time spent in locked state."""
        self.metrics.sync.lock_time_us += duration_us

    def record_beam_steer(
        self,
        gain_db: float,
        sidelobe_db: float,
        success: bool,
        time_us: float,
        power_w: float,
    ) -> None:
        """Record a beam steering operation."""
        self.metrics.beamforming.add_gain(gain_db)
        self.metrics.beamforming.add_sidelobe(sidelobe_db)
        self.metrics.beamforming.record_steer(success)
        self.metrics.throughput.total_beam_ops += 1

        duration = time_us - self._current_time_us
        self.metrics.power.add_power_sample(power_w, duration)
        self.metrics.power.beamform_energy_wus += power_w * duration

        self._current_time_us = time_us

    def record_idle(self, duration_us: float, power_w: float) -> None:
        """Record idle period."""
        self.metrics.power.idle_energy_wus += power_w * duration_us
        self.metrics.power.add_power_sample(power_w, duration_us)
        self._current_time_us += duration_us

    def finalize(self) -> USE6GMetrics:
        """Finalize and return metrics."""
        self.metrics.throughput.total_time_us = (
            self._current_time_us - self._start_time_us
        )
        return self.metrics
