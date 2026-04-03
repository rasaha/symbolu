"""
Variance-Based Confidence Estimation
=====================================

Shared utility for lightweight confidence estimation via signal variance.
Used by both training (SattvicBrake) and inference (StateEvolutionEngine FAST mode).

Core idea: Low variance in signals = High confidence
           High variance in signals = Low confidence (model is "uncertain")

This provides a ~0.1% compute alternative to full Bayesian posterior tracking.

Version: 1.0.0
Date: 2025-01-04
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class VarianceConfidenceConfig:
    """Configuration for variance-based confidence estimation."""

    # Rolling window size for variance calculation
    window_size: int = 10

    # Confidence threshold for braking/hedging
    confidence_threshold: float = 0.5

    # Normalization factor (max theoretical variance for [0,1] signals is 0.25)
    max_variance: float = 0.25

    # Graduated braking thresholds
    brake_levels: Tuple[Tuple[float, float], ...] = (
        (0.3, 0.6),   # confidence < 0.3 → multiplier 0.6
        (0.4, 0.7),   # confidence < 0.4 → multiplier 0.7
        (0.5, 0.8),   # confidence < 0.5 → multiplier 0.8
    )

    def __post_init__(self):
        if self.window_size < 2:
            raise ValueError(f"window_size must be >= 2, got {self.window_size}")
        if not (0.0 <= self.confidence_threshold <= 1.0):
            raise ValueError(f"confidence_threshold must be in [0, 1], got {self.confidence_threshold}")


# Default configuration
DEFAULT_VARIANCE_CONFIG = VarianceConfidenceConfig()


class VarianceConfidence:
    """
    Lightweight confidence estimation via signal variance.

    Tracks a rolling window of signal observations and computes confidence
    as 1 - normalized_variance. This provides a cheap proxy for uncertainty
    without full Bayesian posterior tracking.

    Used by:
    - SattvicBrake (training): Tracks phase angle variance in Authority layers
    - StateEvolutionEngine FAST mode (inference): Tracks observable (s,r,t) variance

    Cost: ~0.1% compute, O(window_size) memory

    Usage:
        vc = VarianceConfidence(window_size=10, threshold=0.5)

        # Add observations (can be any tuple of floats)
        confidence = vc.update((0.6, 0.2, 0.2))
        confidence = vc.update((0.5, 0.3, 0.2))

        # Check if we should brake/hedge
        should_brake, multiplier = vc.should_brake()

        # Get current confidence
        conf = vc.get_confidence()
    """

    def __init__(
        self,
        window_size: int = 10,
        confidence_threshold: float = 0.5,
        config: Optional[VarianceConfidenceConfig] = None,
    ):
        """
        Initialize variance confidence tracker.

        Args:
            window_size: Rolling window size for variance calculation
            confidence_threshold: Threshold below which to brake/hedge
            config: Full configuration (overrides other args if provided)
        """
        if config is not None:
            self._config = config
        else:
            self._config = VarianceConfidenceConfig(
                window_size=window_size,
                confidence_threshold=confidence_threshold,
            )

        self._history: List[Tuple[float, ...]] = []
        self._confidence: float = 0.5  # Start neutral
        self._brake_count: int = 0

    @property
    def config(self) -> VarianceConfidenceConfig:
        """Current configuration."""
        return self._config

    @property
    def confidence(self) -> float:
        """Current confidence level [0, 1]."""
        return self._confidence

    @property
    def brake_count(self) -> int:
        """Number of times brake has been applied."""
        return self._brake_count

    @property
    def history_size(self) -> int:
        """Current number of observations in history."""
        return len(self._history)

    def update(self, values: Tuple[float, ...]) -> float:
        """
        Add observation and compute new confidence.

        Args:
            values: Tuple of signal values (e.g., (s, r, t) or phase angles)

        Returns:
            Updated confidence [0, 1]
        """
        # Add to history
        self._history.append(values)

        # Trim to window size
        if len(self._history) > self._config.window_size:
            self._history = self._history[-self._config.window_size:]

        # Compute variance and confidence
        variance = self._compute_variance()
        self._confidence = 1.0 - variance

        return self._confidence

    def _compute_variance(self) -> float:
        """
        Compute normalized variance across all signal dimensions.

        Returns:
            Variance in [0, 1] range (higher = less confident)
        """
        if len(self._history) < 2:
            return 0.5  # Not enough data, return neutral

        # Get number of dimensions from first observation
        n_dims = len(self._history[0])
        if n_dims == 0:
            return 0.5

        # Compute variance for each dimension
        variances = []
        for dim in range(n_dims):
            vals = [obs[dim] for obs in self._history]
            var = self._variance(vals)
            variances.append(var)

        # Average variance across dimensions
        avg_variance = sum(variances) / len(variances)

        # Normalize to [0, 1]
        normalized = min(1.0, avg_variance / self._config.max_variance)

        return normalized

    @staticmethod
    def _variance(vals: List[float]) -> float:
        """Compute sample variance."""
        if len(vals) < 2:
            return 0.0
        mean = sum(vals) / len(vals)
        return sum((v - mean) ** 2 for v in vals) / len(vals)

    def get_confidence(self) -> float:
        """Get current confidence level."""
        return self._confidence

    def should_brake(self, confidence: Optional[float] = None) -> Tuple[bool, float]:
        """
        Check if brake should be applied based on confidence.

        Args:
            confidence: Override confidence value (uses current if None)

        Returns:
            (should_apply, lr_multiplier)
        """
        conf = confidence if confidence is not None else self._confidence

        if conf >= self._config.confidence_threshold:
            return False, 1.0

        # Graduated braking based on confidence level
        self._brake_count += 1

        for threshold, multiplier in self._config.brake_levels:
            if conf < threshold:
                return True, multiplier

        # Default brake multiplier
        return True, 0.8

    def get_status_icon(self, confidence: Optional[float] = None) -> str:
        """Get status icon for confidence level."""
        conf = confidence if confidence is not None else self._confidence

        if conf >= 0.7:
            return "🟢"
        elif conf >= 0.5:
            return "🟡"
        elif conf >= 0.3:
            return "🟠"
        else:
            return "🔴"

    def format_status(self, confidence: Optional[float] = None) -> str:
        """Format status string for logging."""
        conf = confidence if confidence is not None else self._confidence
        icon = self.get_status_icon(conf)

        brake, mult = self.should_brake(conf)
        if brake:
            return f"Conf:{conf:.2f}{icon} [BRAKE×{mult:.2f}]"
        return f"Conf:{conf:.2f}{icon}"

    def reset(self) -> None:
        """Reset history and confidence to initial state."""
        self._history.clear()
        self._confidence = 0.5
        self._brake_count = 0
