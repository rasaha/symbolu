"""
v2.7 State Evolution for Robotics
==================================

Adapted EMA (Exponential Moving Average) state tracking for robotics.

In robotics context:
- EMA smooths sensor noise over time
- Tracks layer activation history
- Provides temporal stability for control

Key Features:
- Configurable alpha (learning rate) per tier
- Fast alpha for reactive tier (quick response)
- Slow alpha for deliberative tier (stable planning)
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional
import numpy as np

from symbolu_robotics.core.types import Layer12D


@dataclass
class EMAConfig:
    """
    EMA configuration for robotics state tracking.

    Attributes:
        alpha: Learning rate (0 < alpha < 1)
            - Higher alpha = faster adaptation, more noise
            - Lower alpha = slower adaptation, smoother
        tier: Associated robotics tier
        half_life_steps: Number of steps for 50% decay
    """
    alpha: float = 0.1
    tier: str = "reactive"

    def __post_init__(self):
        if not (0.0 < self.alpha < 1.0):
            raise ValueError(f"alpha must be in (0, 1), got {self.alpha}")

    @property
    def half_life_steps(self) -> float:
        """Number of steps for 50% decay toward target."""
        import math
        return math.log(0.5) / math.log(1 - self.alpha)


# Tier-specific configurations
EMA_REFLEXIVE = EMAConfig(alpha=0.5, tier="reflexive")    # Very fast, ~1-2 steps
EMA_REACTIVE = EMAConfig(alpha=0.1, tier="reactive")      # Moderate, ~7 steps
EMA_DELIBERATIVE = EMAConfig(alpha=0.02, tier="deliberative")  # Slow, ~35 steps


def get_ema_config(tier: str) -> EMAConfig:
    """Get EMA configuration for a tier."""
    configs = {
        "reflexive": EMA_REFLEXIVE,
        "reactive": EMA_REACTIVE,
        "deliberative": EMA_DELIBERATIVE,
    }
    return configs.get(tier, EMA_REACTIVE)


@dataclass
class EMAState:
    """
    EMA state register for 12D layer tracking.

    Tracks the smoothed layer activations over time.
    """
    # Current smoothed 12D state
    layer_values: Layer12D = field(default_factory=lambda: np.zeros(12, dtype=np.float32))

    # Number of updates
    n_updates: int = 0

    # Timestamp of last update
    last_timestamp: float = 0.0

    # Per-layer variance estimates (for uncertainty)
    layer_variances: Layer12D = field(default_factory=lambda: np.zeros(12, dtype=np.float32))

    def to_dict(self) -> Dict:
        return {
            "layer_values": self.layer_values.tolist(),
            "n_updates": self.n_updates,
            "last_timestamp": self.last_timestamp,
            "layer_variances": self.layer_variances.tolist(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "EMAState":
        return cls(
            layer_values=np.array(data["layer_values"], dtype=np.float32),
            n_updates=data["n_updates"],
            last_timestamp=data["last_timestamp"],
            layer_variances=np.array(data.get("layer_variances", [0.0]*12), dtype=np.float32),
        )


def update_ema_state(
    state: EMAState,
    new_values: Layer12D,
    config: EMAConfig,
    timestamp: float = 0.0
) -> EMAState:
    """
    Update EMA state with new layer values.

    EMA formula: new_state = (1 - alpha) * old_state + alpha * new_values

    Args:
        state: Current EMA state
        new_values: New 12D layer values
        config: EMA configuration
        timestamp: Current timestamp

    Returns:
        Updated EMAState
    """
    alpha = config.alpha

    # EMA update
    new_layer_values = (1 - alpha) * state.layer_values + alpha * new_values

    # Update variance estimate (for uncertainty tracking)
    delta = new_values - state.layer_values
    new_variances = (1 - alpha) * state.layer_variances + alpha * (delta ** 2)

    return EMAState(
        layer_values=new_layer_values,
        n_updates=state.n_updates + 1,
        last_timestamp=timestamp,
        layer_variances=new_variances,
    )


def decay_ema_state(
    state: EMAState,
    decay_factor: float = 0.95
) -> EMAState:
    """
    Decay EMA state toward zero (for timeout handling).

    Args:
        state: Current EMA state
        decay_factor: Decay multiplier (0 < factor < 1)

    Returns:
        Decayed EMAState
    """
    return EMAState(
        layer_values=state.layer_values * decay_factor,
        n_updates=state.n_updates,
        last_timestamp=state.last_timestamp,
        layer_variances=state.layer_variances * decay_factor,
    )


def compute_ema_confidence(state: EMAState) -> float:
    """
    Compute confidence in EMA estimates.

    Confidence increases with:
    - More updates
    - Lower variance

    Args:
        state: Current EMA state

    Returns:
        Confidence score [0, 1]
    """
    # Update factor: more updates = higher confidence
    update_factor = 1.0 - 1.0 / (1.0 + state.n_updates)

    # Variance factor: lower variance = higher confidence
    mean_variance = np.mean(state.layer_variances)
    variance_factor = 1.0 - min(1.0, mean_variance)

    return update_factor * variance_factor


@dataclass
class RobotStateTracker:
    """
    Complete state tracker for robotics.

    Maintains EMA states for different time scales:
    - Fast: For immediate reflexes
    - Medium: For reactive behaviors
    - Slow: For deliberative planning
    """
    fast_state: EMAState = field(default_factory=EMAState)
    medium_state: EMAState = field(default_factory=EMAState)
    slow_state: EMAState = field(default_factory=EMAState)

    fast_config: EMAConfig = field(default_factory=lambda: EMA_REFLEXIVE)
    medium_config: EMAConfig = field(default_factory=lambda: EMA_REACTIVE)
    slow_config: EMAConfig = field(default_factory=lambda: EMA_DELIBERATIVE)

    def update(self, new_values: Layer12D, timestamp: float = 0.0) -> None:
        """Update all time scales with new values."""
        self.fast_state = update_ema_state(
            self.fast_state, new_values, self.fast_config, timestamp
        )
        self.medium_state = update_ema_state(
            self.medium_state, new_values, self.medium_config, timestamp
        )
        self.slow_state = update_ema_state(
            self.slow_state, new_values, self.slow_config, timestamp
        )

    def get_state_for_tier(self, tier: str) -> EMAState:
        """Get the appropriate state for a tier."""
        states = {
            "reflexive": self.fast_state,
            "reactive": self.medium_state,
            "deliberative": self.slow_state,
        }
        return states.get(tier, self.medium_state)

    def get_temporal_difference(self) -> Layer12D:
        """
        Compute difference between fast and slow states.

        Large differences indicate rapid changes in the environment.
        """
        return self.fast_state.layer_values - self.slow_state.layer_values

    def detect_sudden_change(self, threshold: float = 0.3) -> bool:
        """
        Detect sudden changes by comparing time scales.

        Args:
            threshold: Difference threshold

        Returns:
            True if sudden change detected
        """
        diff = np.abs(self.get_temporal_difference())
        max_diff = np.max(diff)
        return max_diff > threshold
