"""Signal Normalizer — raw metrics to [0, 1] state vector.

Converts raw Prometheus values to normalized signals suitable for the
controller's core equation. Two normalization strategies:

1. Z-score + sigmoid: For unbounded metrics (CPU seconds, latency, queue depth).
   Uses a rolling window to compute mean/std, then sigmoid to map to [0, 1].

2. Direct ratio: For metrics already in [0, 1] (memory fraction, error rate).
   Just clamp to bounds.

The rolling window is per-metric and self-calibrating — no manual threshold
tuning needed. The normalizer learns what "normal" looks like for each metric.
"""

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class NormalizerConfig:
    """Configuration for signal normalization."""
    # Rolling window size for z-score computation (in samples)
    window_size: int = 240  # 240 samples at 15s = 1 hour
    # Minimum samples before z-score is reliable (use raw sigmoid before this)
    min_samples: int = 10
    # Sigmoid steepness for z-score mapping (higher = sharper transition)
    sigmoid_k: float = 1.0
    # Sigmoid center (z-score at which output = 0.5)
    sigmoid_center: float = 0.0


@dataclass
class MetricSpec:
    """Specification for a single metric's normalization behavior."""
    name: str
    # Normalization method: "zscore" or "ratio"
    method: str = "zscore"
    # For ratio method: expected range [low, high] mapped to [0, 1]
    ratio_low: float = 0.0
    ratio_high: float = 1.0
    # For zscore: override sigmoid steepness (None = use config default)
    sigmoid_k: Optional[float] = None
    # Invert: if True, high raw value → LOW normalized value (e.g., available memory)
    invert: bool = False


# Default metric specifications for the MVP set
DEFAULT_METRIC_SPECS: Dict[str, MetricSpec] = {
    "cpu": MetricSpec(
        name="cpu",
        method="zscore",
        sigmoid_k=1.5,  # Sharper — CPU spikes are meaningful
    ),
    "memory": MetricSpec(
        name="memory",
        method="ratio",
        ratio_low=0.0,
        ratio_high=1.0,
        # Prometheus query already returns utilization fraction
    ),
    "latency_p99": MetricSpec(
        name="latency_p99",
        method="zscore",
        sigmoid_k=1.0,
    ),
    "error_rate": MetricSpec(
        name="error_rate",
        method="ratio",
        ratio_low=0.0,
        ratio_high=1.0,
        # Already a fraction [0, 1]
    ),
    "queue_depth": MetricSpec(
        name="queue_depth",
        method="zscore",
        sigmoid_k=0.8,  # Softer — queue depth varies more naturally
    ),
}


@dataclass
class NormalizationResult:
    """Result of normalizing a single metric."""
    name: str
    raw_value: float
    normalized: float       # In [0, 1]
    method: str             # "zscore" or "ratio"
    z_score: Optional[float] = None  # Only for zscore method
    window_mean: Optional[float] = None
    window_std: Optional[float] = None
    window_size: int = 0    # Current number of samples in window


class SignalNormalizer:
    """Normalizes raw metric values to [0, 1] using rolling statistics.

    Each metric has its own rolling window for z-score computation.
    The normalizer is stateful — it learns the distribution of each metric
    over time and adapts its normalization accordingly.

    Usage:
        normalizer = SignalNormalizer()
        raw = {"cpu": 0.82, "latency_p99": 0.340, "error_rate": 0.021, ...}
        normalized = normalizer.normalize(raw)
        # normalized = {"cpu": 0.73, "latency_p99": 0.81, "error_rate": 0.021, ...}
    """

    def __init__(
        self,
        config: Optional[NormalizerConfig] = None,
        metric_specs: Optional[Dict[str, MetricSpec]] = None,
    ):
        self.config = config or NormalizerConfig()
        self.metric_specs = metric_specs or dict(DEFAULT_METRIC_SPECS)
        # Rolling windows: metric_name → deque of (timestamp, value)
        self._windows: Dict[str, deque] = {}

    def normalize(
        self,
        raw_metrics: Dict[str, float],
        timestamp: Optional[float] = None,
    ) -> Dict[str, float]:
        """Normalize all raw metrics to [0, 1].

        Args:
            raw_metrics: Dict of metric_name → raw value from Prometheus.
            timestamp: Optional timestamp for the sample. Defaults to now.

        Returns:
            Dict of metric_name → normalized value in [0, 1].
        """
        if timestamp is None:
            timestamp = time.time()

        normalized: Dict[str, float] = {}
        for name, value in raw_metrics.items():
            if not math.isfinite(value):
                continue
            result = self.normalize_one(name, value, timestamp)
            normalized[name] = result.normalized

        return normalized

    def normalize_one(
        self,
        name: str,
        value: float,
        timestamp: Optional[float] = None,
    ) -> NormalizationResult:
        """Normalize a single metric value.

        Args:
            name: Metric name (must match a MetricSpec key, or uses zscore default).
            value: Raw metric value.
            timestamp: Sample timestamp.

        Returns:
            NormalizationResult with normalized value and diagnostics.
        """
        if timestamp is None:
            timestamp = time.time()

        spec = self.metric_specs.get(name, MetricSpec(name=name))

        # Add to rolling window
        self._add_sample(name, timestamp, value)

        if spec.method == "ratio":
            normalized = self._normalize_ratio(value, spec)
            return NormalizationResult(
                name=name,
                raw_value=value,
                normalized=normalized,
                method="ratio",
                window_size=len(self._windows.get(name, [])),
            )
        else:
            # Z-score + sigmoid
            return self._normalize_zscore(name, value, spec)

    def normalize_detailed(
        self,
        raw_metrics: Dict[str, float],
        timestamp: Optional[float] = None,
    ) -> Dict[str, NormalizationResult]:
        """Normalize all metrics and return detailed results.

        Same as normalize() but returns NormalizationResult objects
        instead of plain floats.
        """
        if timestamp is None:
            timestamp = time.time()

        results: Dict[str, NormalizationResult] = {}
        for name, value in raw_metrics.items():
            if not math.isfinite(value):
                continue
            results[name] = self.normalize_one(name, value, timestamp)

        return results

    def _add_sample(self, name: str, timestamp: float, value: float) -> None:
        """Add a sample to the rolling window for a metric."""
        if name not in self._windows:
            self._windows[name] = deque(maxlen=self.config.window_size)
        self._windows[name].append((timestamp, value))

    def _normalize_ratio(self, value: float, spec: MetricSpec) -> float:
        """Normalize using direct ratio mapping."""
        range_size = spec.ratio_high - spec.ratio_low
        if range_size <= 0:
            return 0.5

        normalized = (value - spec.ratio_low) / range_size

        if spec.invert:
            normalized = 1.0 - normalized

        return max(0.0, min(1.0, normalized))

    def _normalize_zscore(
        self,
        name: str,
        value: float,
        spec: MetricSpec,
    ) -> NormalizationResult:
        """Normalize using rolling z-score + sigmoid."""
        window = self._windows.get(name, deque())
        values = [v for _, v in window]
        window_size = len(values)

        if window_size < self.config.min_samples:
            # Not enough data — use raw sigmoid centered at current value
            # This gives a neutral 0.5 for the first sample, then adapts
            k = spec.sigmoid_k if spec.sigmoid_k is not None else self.config.sigmoid_k
            normalized = self._sigmoid(0.0, k)  # z=0 → 0.5
            return NormalizationResult(
                name=name,
                raw_value=value,
                normalized=normalized,
                method="zscore",
                z_score=0.0,
                window_mean=None,
                window_std=None,
                window_size=window_size,
            )

        # Compute rolling mean and std
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(variance) if variance > 0 else 0.0

        # Z-score
        if std > 1e-10:
            z = (value - mean) / std
        else:
            # All values are the same — any deviation is notable
            z = 0.0 if abs(value - mean) < 1e-10 else (1.0 if value > mean else -1.0)

        # Sigmoid mapping: z-score → [0, 1]
        k = spec.sigmoid_k if spec.sigmoid_k is not None else self.config.sigmoid_k
        center = self.config.sigmoid_center
        normalized = self._sigmoid(z - center, k)

        if spec.invert:
            normalized = 1.0 - normalized

        return NormalizationResult(
            name=name,
            raw_value=value,
            normalized=normalized,
            method="zscore",
            z_score=z,
            window_mean=mean,
            window_std=std,
            window_size=window_size,
        )

    @staticmethod
    def _sigmoid(x: float, k: float = 1.0) -> float:
        """Numerically stable sigmoid: 1 / (1 + exp(-k * x))."""
        z = k * x
        if z >= 0:
            return 1.0 / (1.0 + math.exp(-z))
        else:
            ez = math.exp(z)
            return ez / (1.0 + ez)

    def get_window_stats(self, name: str) -> Optional[Dict[str, float]]:
        """Return current rolling window statistics for a metric."""
        window = self._windows.get(name)
        if not window:
            return None
        values = [v for _, v in window]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return {
            "mean": mean,
            "std": math.sqrt(variance),
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }

    def reset(self, name: Optional[str] = None) -> None:
        """Reset rolling windows.

        Args:
            name: If specified, reset only this metric. Otherwise reset all.
        """
        if name is not None:
            self._windows.pop(name, None)
        else:
            self._windows.clear()
