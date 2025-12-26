"""
Sim-to-Real Transfer Module
===========================

Domain adaptation for transferring learned policies from simulation.

Key Challenges Addressed:
- Sensor noise differences
- Actuator dynamics mismatch
- Unmodeled physics

Integration with Symbolu:
- 12D Layer provides domain-invariant representation
- SCC coherence measures reality gap
- USE correlation validates transfer quality

Approach:
- Domain randomization during simulation
- Online adaptation during real deployment
- Coherence-based confidence estimation
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple, Callable
from enum import Enum
import numpy as np

from symbolu_robotics.core.types import Layer12D


class TransferMode(Enum):
    """Transfer learning mode."""
    DIRECT = "direct"  # Direct transfer, no adaptation
    FINE_TUNE = "fine_tune"  # Fine-tune on real data
    DOMAIN_ADAPT = "domain_adapt"  # Domain adaptation
    GROUNDED = "grounded"  # Grounded simulation


@dataclass
class TransferConfig:
    """Configuration for sim-to-real transfer."""
    mode: TransferMode = TransferMode.DOMAIN_ADAPT

    # Adaptation parameters
    adaptation_rate: float = 0.01
    min_samples_for_adaptation: int = 100

    # Domain randomization (for simulation)
    randomize_noise: bool = True
    noise_scale_range: Tuple[float, float] = (0.8, 1.2)
    randomize_dynamics: bool = True
    dynamics_scale_range: Tuple[float, float] = (0.9, 1.1)

    # Reality gap thresholds
    coherence_gap_threshold: float = 0.3
    distribution_shift_threshold: float = 0.5

    # Confidence
    min_confidence_for_transfer: float = 0.5


@dataclass
class DomainGap:
    """Measures of domain gap between sim and real."""
    coherence_gap: float = 0.0  # SCC coherence difference
    state_distribution_gap: float = 0.0  # State distribution difference
    dynamics_gap: float = 0.0  # Dynamics model error

    # Per-layer gaps (12D)
    layer_gaps: np.ndarray = field(default_factory=lambda: np.zeros(12))

    # Adaptation status
    adaptation_progress: float = 0.0  # 0-1, how much adapted
    samples_collected: int = 0

    def total_gap(self) -> float:
        """Compute total domain gap."""
        return (
            0.4 * self.coherence_gap +
            0.3 * self.state_distribution_gap +
            0.3 * self.dynamics_gap
        )

    def is_acceptable(self, threshold: float = 0.3) -> bool:
        """Check if gap is acceptable for transfer."""
        return self.total_gap() < threshold


class DomainRandomizer:
    """
    Domain randomization for simulation.

    Applies randomization to simulation parameters to improve transfer.
    """

    def __init__(self, config: Optional[TransferConfig] = None):
        self._config = config or TransferConfig()
        self._rng = np.random.default_rng()

    def randomize_sensor_noise(
        self,
        base_noise_std: float,
    ) -> float:
        """Randomize sensor noise scale."""
        if not self._config.randomize_noise:
            return base_noise_std

        low, high = self._config.noise_scale_range
        scale = self._rng.uniform(low, high)
        return base_noise_std * scale

    def randomize_dynamics_params(
        self,
        params: Dict[str, float],
    ) -> Dict[str, float]:
        """Randomize dynamics parameters."""
        if not self._config.randomize_dynamics:
            return params

        low, high = self._config.dynamics_scale_range
        randomized = {}

        for key, value in params.items():
            scale = self._rng.uniform(low, high)
            randomized[key] = value * scale

        return randomized

    def randomize_state(self, state: Layer12D) -> Layer12D:
        """Add randomization to state."""
        noise = self._rng.normal(0, 0.05, size=12)
        randomized = state + noise
        return np.clip(randomized, 0, 1).astype(np.float32)


class DomainAdapter:
    """
    Online domain adaptation for sim-to-real transfer.

    Learns mapping from sim domain to real domain based on collected data.
    """

    def __init__(self, config: Optional[TransferConfig] = None):
        self._config = config or TransferConfig()

        # Collected real data
        self._real_states: List[Layer12D] = []
        self._real_coherences: List[float] = []

        # Adaptation parameters (simple affine transform)
        self._scale: np.ndarray = np.ones(12, dtype=np.float32)
        self._bias: np.ndarray = np.zeros(12, dtype=np.float32)

        # Statistics
        self._sim_mean: np.ndarray = np.zeros(12)
        self._sim_std: np.ndarray = np.ones(12)
        self._real_mean: np.ndarray = np.zeros(12)
        self._real_std: np.ndarray = np.ones(12)

        self._adapted = False

    def record_real_sample(
        self,
        real_state: Layer12D,
        coherence: float = 1.0,
    ) -> None:
        """Record real-world sample for adaptation."""
        self._real_states.append(real_state.copy())
        self._real_coherences.append(coherence)

    def set_sim_statistics(
        self,
        mean: np.ndarray,
        std: np.ndarray,
    ) -> None:
        """Set simulation distribution statistics."""
        self._sim_mean = mean.copy()
        self._sim_std = std.copy()

    def adapt(self) -> bool:
        """
        Learn adaptation from collected real samples.

        Uses simple distribution matching.
        """
        if len(self._real_states) < self._config.min_samples_for_adaptation:
            return False

        # Compute real statistics (weighted by coherence)
        states = np.array(self._real_states)
        weights = np.array(self._real_coherences)
        weights = weights / weights.sum()

        self._real_mean = np.average(states, axis=0, weights=weights)

        # Weighted variance
        var = np.average(
            (states - self._real_mean) ** 2,
            axis=0,
            weights=weights
        )
        self._real_std = np.sqrt(var + 1e-6)

        # Compute adaptation transform
        # Normalize sim -> standard -> real
        self._scale = self._real_std / np.maximum(self._sim_std, 1e-6)
        self._bias = self._real_mean - self._scale * self._sim_mean

        self._adapted = True
        return True

    def adapt_state(self, sim_state: Layer12D) -> Layer12D:
        """
        Adapt simulation state to real domain.

        Applies learned affine transformation.
        """
        if not self._adapted:
            return sim_state

        adapted = self._scale * sim_state + self._bias
        return np.clip(adapted, 0, 1).astype(np.float32)

    def get_adaptation_confidence(self) -> float:
        """Get confidence in current adaptation."""
        if not self._adapted:
            return 0.0

        # Confidence based on samples and coherence
        sample_factor = min(1.0, len(self._real_states) / 500)
        coherence_factor = np.mean(self._real_coherences[-100:]) if self._real_coherences else 0.0

        return sample_factor * coherence_factor

    def reset(self) -> None:
        """Reset adaptation."""
        self._real_states.clear()
        self._real_coherences.clear()
        self._scale = np.ones(12, dtype=np.float32)
        self._bias = np.zeros(12, dtype=np.float32)
        self._adapted = False


class SimToRealAdapter:
    """
    Complete sim-to-real transfer system.

    Combines domain randomization (for simulation) with
    online adaptation (for real deployment).

    Integration with Symbolu:
    - Uses 12D Layer as domain-invariant representation
    - SCC coherence measures reality gap
    - Adaptation preserves ontological semantics
    """

    def __init__(self, config: Optional[TransferConfig] = None):
        self._config = config or TransferConfig()

        # Components
        self._randomizer = DomainRandomizer(config)
        self._adapter = DomainAdapter(config)

        # Domain gap tracking
        self._gap = DomainGap()

        # Mode tracking
        self._in_simulation = True
        self._sim_coherence_history: List[float] = []
        self._real_coherence_history: List[float] = []

    @property
    def domain_gap(self) -> DomainGap:
        """Get current domain gap estimate."""
        return self._gap

    def set_simulation_mode(self, is_sim: bool) -> None:
        """Set whether currently in simulation or real."""
        self._in_simulation = is_sim

    def process_state(
        self,
        state: Layer12D,
        coherence: float,
    ) -> Layer12D:
        """
        Process state based on current mode.

        In simulation: Apply randomization
        In real: Record for adaptation and adapt if needed
        """
        if self._in_simulation:
            # Simulation: Apply randomization
            self._sim_coherence_history.append(coherence)
            return self._randomizer.randomize_state(state)
        else:
            # Real: Record and adapt
            self._real_coherence_history.append(coherence)
            self._adapter.record_real_sample(state, coherence)

            # Update gap estimate
            self._update_domain_gap(coherence)

            return state

    def adapt_sim_output(self, sim_state: Layer12D) -> Layer12D:
        """
        Adapt simulation output for real deployment.

        Called when deploying sim-trained policy to real robot.
        """
        return self._adapter.adapt_state(sim_state)

    def _update_domain_gap(self, real_coherence: float) -> None:
        """Update domain gap estimate."""
        # Coherence gap
        if self._sim_coherence_history:
            sim_coherence = np.mean(self._sim_coherence_history[-100:])
            self._gap.coherence_gap = abs(sim_coherence - real_coherence)

        # Samples collected
        self._gap.samples_collected = len(self._adapter._real_states)

        # Adaptation progress
        if self._adapter._adapted:
            confidence = self._adapter.get_adaptation_confidence()
            self._gap.adaptation_progress = confidence

    def trigger_adaptation(self) -> bool:
        """
        Trigger domain adaptation if enough data collected.

        Returns True if adaptation successful.
        """
        # Set sim statistics if available
        if self._sim_coherence_history:
            # Use coherence-weighted sim samples
            # (Placeholder: would need actual sim states)
            pass

        return self._adapter.adapt()

    def should_adapt(self) -> bool:
        """Check if adaptation should be triggered."""
        return (
            self._gap.samples_collected >= self._config.min_samples_for_adaptation and
            self._gap.total_gap() > self._config.coherence_gap_threshold and
            not self._adapter._adapted
        )

    def get_transfer_confidence(self) -> float:
        """
        Get confidence in sim-to-real transfer.

        Low confidence indicates large domain gap.
        """
        if self._in_simulation:
            return 1.0

        # Based on gap and adaptation
        gap_factor = max(0, 1.0 - self._gap.total_gap())
        adapt_factor = self._gap.adaptation_progress

        return 0.5 * gap_factor + 0.5 * adapt_factor

    def is_transfer_safe(self) -> bool:
        """Check if transfer confidence is sufficient."""
        return self.get_transfer_confidence() >= self._config.min_confidence_for_transfer

    def get_metrics(self) -> Dict[str, Any]:
        """Get transfer metrics."""
        return {
            "mode": "simulation" if self._in_simulation else "real",
            "domain_gap": {
                "coherence_gap": self._gap.coherence_gap,
                "state_gap": self._gap.state_distribution_gap,
                "dynamics_gap": self._gap.dynamics_gap,
                "total": self._gap.total_gap(),
            },
            "adaptation": {
                "progress": self._gap.adaptation_progress,
                "samples": self._gap.samples_collected,
                "adapted": self._adapter._adapted,
            },
            "confidence": self.get_transfer_confidence(),
            "transfer_safe": self.is_transfer_safe(),
        }

    def reset(self) -> None:
        """Reset transfer state."""
        self._adapter.reset()
        self._gap = DomainGap()
        self._sim_coherence_history.clear()
        self._real_coherence_history.clear()
