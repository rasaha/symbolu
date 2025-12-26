"""
EMA Tracker for Robotics
=========================

v2.7 EMA (Exponential Moving Average) state tracking.
"""

from dataclasses import dataclass, field
from typing import Dict, Any
import numpy as np

from symbolu_robotics.core.types import Layer12D


@dataclass
class EMATrackerConfig:
    """EMA tracker configuration."""
    alpha: float = 0.1           # Learning rate
    variance_alpha: float = 0.05  # Variance tracking rate
    min_updates: int = 5         # Minimum updates for confidence


class EMATracker:
    """
    Multi-signal EMA tracker.

    Tracks 12D layer values with variance estimation.
    """

    def __init__(self, config: EMATrackerConfig = None):
        self.config = config or EMATrackerConfig()

        # State
        self._values = np.zeros(12, dtype=np.float32)
        self._variances = np.ones(12, dtype=np.float32) * 0.25  # Initial uncertainty
        self._n_updates = 0
        self._last_timestamp = 0.0

    @property
    def values(self) -> Layer12D:
        """Current smoothed values."""
        return self._values.copy()

    @property
    def variances(self) -> np.ndarray:
        """Current variance estimates."""
        return self._variances.copy()

    @property
    def n_updates(self) -> int:
        return self._n_updates

    def update(
        self,
        new_values: Layer12D,
        timestamp: float = 0.0
    ) -> Layer12D:
        """
        Update EMA with new values.

        EMA formula: x_t = (1 - α) * x_{t-1} + α * x_new

        Args:
            new_values: New 12D layer values
            timestamp: Current timestamp

        Returns:
            Updated smoothed values
        """
        alpha = self.config.alpha

        # Update EMA
        self._values = (1 - alpha) * self._values + alpha * new_values

        # Update variance estimate
        delta = new_values - self._values
        self._variances = (
            (1 - self.config.variance_alpha) * self._variances +
            self.config.variance_alpha * (delta ** 2)
        )

        self._n_updates += 1
        self._last_timestamp = timestamp

        return self._values.copy()

    def get_confidence(self) -> float:
        """
        Get overall confidence in estimates.

        Based on update count and variance.
        """
        if self._n_updates < self.config.min_updates:
            return self._n_updates / self.config.min_updates * 0.5

        # Lower variance = higher confidence
        mean_variance = np.mean(self._variances)
        variance_confidence = max(0.0, 1.0 - mean_variance)

        # Update count confidence (saturates)
        update_confidence = min(1.0, self._n_updates / 50)

        return 0.5 * variance_confidence + 0.5 * update_confidence

    def get_layer_confidence(self) -> np.ndarray:
        """Get per-layer confidence."""
        return 1.0 - np.clip(self._variances, 0, 1)

    def decay(self, factor: float = 0.95) -> None:
        """Decay values toward zero."""
        self._values *= factor
        # Increase variance when decaying (less certain)
        self._variances = np.minimum(self._variances / factor, 0.25)

    def reset(self) -> None:
        """Reset tracker state."""
        self._values = np.zeros(12, dtype=np.float32)
        self._variances = np.ones(12, dtype=np.float32) * 0.25
        self._n_updates = 0
        self._last_timestamp = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "values": self._values.tolist(),
            "variances": self._variances.tolist(),
            "n_updates": self._n_updates,
            "confidence": self.get_confidence(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EMATracker":
        tracker = cls()
        tracker._values = np.array(data["values"], dtype=np.float32)
        tracker._variances = np.array(data["variances"], dtype=np.float32)
        tracker._n_updates = data["n_updates"]
        return tracker
