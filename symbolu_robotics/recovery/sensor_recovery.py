# Symbolu Robotics - Sensor Recovery Handler
"""
Sensor failure detection and graceful degradation.

Integrates with USE (U1-U4) formulas for:
- Coherence-based failure detection
- Automatic sensor downweighting
- Graceful degradation when sensors fail
- Recovery when sensors come back online

Features:
- Monitors sensor health via USE correlation matrix
- Tracks sensor reliability over time
- Provides fallback values during sensor outage
- Alerts on sensor anomalies
"""

import time
from typing import Optional, Callable, Dict, List, Any, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np

from symbolu_robotics.core.exceptions import (
    SensorError,
    SensorTimeoutError,
    SensorDataError,
    SensorCoherenceError,
    SensorDisconnectedError,
    RecoveryAction,
    ErrorSeverity,
)


class SensorStatus(Enum):
    """Sensor operational status."""
    HEALTHY = auto()         # Normal operation
    DEGRADED = auto()        # Low coherence but usable
    FAILING = auto()         # Intermittent failures
    DISCONNECTED = auto()    # Not responding
    RECOVERING = auto()      # Coming back online


@dataclass
class SensorConfig:
    """Configuration for sensor recovery."""
    # Coherence thresholds (from USE U1)
    coherence_warning_threshold: float = 0.3    # Below this: degraded
    coherence_failure_threshold: float = 0.15   # Below this: failing

    # Timeout settings
    timeout_ms: float = 100.0                   # Max time between updates
    max_consecutive_timeouts: int = 3           # Before marking disconnected

    # Recovery settings
    recovery_coherence_threshold: float = 0.4   # Required for recovery
    min_recovery_readings: int = 5              # Stable readings for recovery

    # Fallback behavior
    use_last_known_value: bool = True           # Use last value on failure
    fallback_decay_rate: float = 0.95           # Decay factor for stale values


@dataclass
class SensorState:
    """State tracking for a single sensor."""
    name: str
    status: SensorStatus = SensorStatus.HEALTHY
    coherence_score: float = 1.0
    last_update_time: float = field(default_factory=time.perf_counter)
    last_valid_value: Optional[np.ndarray] = None
    consecutive_timeouts: int = 0
    consecutive_valid_readings: int = 0
    total_failures: int = 0
    total_readings: int = 0

    @property
    def failure_rate(self) -> float:
        """Calculate sensor failure rate."""
        if self.total_readings == 0:
            return 0.0
        return self.total_failures / self.total_readings


class SensorRecoveryHandler:
    """
    Handles sensor failure detection and recovery.

    Integrates with FusionEncoder to monitor sensor health via USE
    correlation matrix and provide graceful degradation.

    Usage:
        handler = SensorRecoveryHandler()

        # Register sensors
        handler.register("vision", config)
        handler.register("proprioception", config)
        handler.register("tactile", config)

        # In control loop
        while running:
            # Update from fusion encoder
            modality_weights = encoder.get_modality_weights()
            handler.update_coherence(modality_weights)

            # Check health before using values
            if not handler.is_healthy("vision"):
                # Use fallback or degraded mode
                vision_value = handler.get_fallback_value("vision")

            # Process normal sensor data
            value = encoder.encode(sensors)
            handler.report_reading("vision", value[:12])

    With automatic detection:
        failed_sensors = handler.detect_failures(
            encoder.get_coherence_matrix()
        )
        for sensor in failed_sensors:
            handler.handle_failure(sensor)
    """

    def __init__(
        self,
        default_config: Optional[SensorConfig] = None,
        on_failure: Optional[Callable[[str, SensorStatus, str], None]] = None,
        on_recovery: Optional[Callable[[str], None]] = None,
    ):
        self.default_config = default_config or SensorConfig()
        self._on_failure = on_failure
        self._on_recovery = on_recovery

        self._sensors: Dict[str, SensorState] = {}
        self._configs: Dict[str, SensorConfig] = {}
        self._failed_sensors: Set[str] = set()

    def register(
        self,
        name: str,
        config: Optional[SensorConfig] = None,
    ) -> None:
        """
        Register a sensor for monitoring.

        Args:
            name: Sensor identifier (must match modality name in FusionEncoder)
            config: Optional custom configuration
        """
        self._sensors[name] = SensorState(name=name)
        self._configs[name] = config or self.default_config

    def unregister(self, name: str) -> None:
        """Remove a sensor from monitoring."""
        self._sensors.pop(name, None)
        self._configs.pop(name, None)
        self._failed_sensors.discard(name)

    def update_coherence(
        self,
        modality_weights: Dict[str, float],
    ) -> List[str]:
        """
        Update sensor coherence from USE fusion weights.

        Args:
            modality_weights: Weights from FusionEncoder.get_modality_weights()

        Returns:
            List of sensors that changed status
        """
        changed = []

        for name, weight in modality_weights.items():
            if name in self._sensors:
                state = self._sensors[name]
                config = self._configs.get(name, self.default_config)

                old_status = state.status
                state.coherence_score = weight

                # Update status based on coherence
                if weight >= config.recovery_coherence_threshold:
                    if state.status in (SensorStatus.DEGRADED, SensorStatus.FAILING):
                        state.consecutive_valid_readings += 1
                        if state.consecutive_valid_readings >= config.min_recovery_readings:
                            state.status = SensorStatus.HEALTHY
                            self._failed_sensors.discard(name)
                            if self._on_recovery:
                                self._on_recovery(name)
                    else:
                        state.status = SensorStatus.HEALTHY

                elif weight >= config.coherence_warning_threshold:
                    state.status = SensorStatus.DEGRADED
                    state.consecutive_valid_readings = 0

                elif weight >= config.coherence_failure_threshold:
                    state.status = SensorStatus.FAILING
                    state.consecutive_valid_readings = 0
                    self._failed_sensors.add(name)

                else:
                    # Very low coherence - potential disconnection
                    state.status = SensorStatus.DISCONNECTED
                    state.consecutive_valid_readings = 0
                    self._failed_sensors.add(name)

                if state.status != old_status:
                    changed.append(name)
                    if state.status in (SensorStatus.FAILING, SensorStatus.DISCONNECTED):
                        if self._on_failure:
                            self._on_failure(
                                name,
                                state.status,
                                f"Coherence {weight:.3f} below threshold"
                            )

        return changed

    def report_reading(
        self,
        name: str,
        value: np.ndarray,
        is_valid: bool = True,
    ) -> None:
        """
        Report a sensor reading.

        Args:
            name: Sensor identifier
            value: Sensor value (typically 12D encoding)
            is_valid: Whether the reading is valid
        """
        if name not in self._sensors:
            return

        state = self._sensors[name]
        config = self._configs.get(name, self.default_config)

        state.total_readings += 1
        state.last_update_time = time.perf_counter()

        if is_valid:
            state.last_valid_value = value.copy()
            state.consecutive_timeouts = 0

            # Track recovery from failure
            if state.status == SensorStatus.RECOVERING:
                state.consecutive_valid_readings += 1
                if state.consecutive_valid_readings >= config.min_recovery_readings:
                    state.status = SensorStatus.HEALTHY
                    self._failed_sensors.discard(name)
                    if self._on_recovery:
                        self._on_recovery(name)

        else:
            state.total_failures += 1

    def report_timeout(self, name: str) -> None:
        """Report a sensor timeout."""
        if name not in self._sensors:
            return

        state = self._sensors[name]
        config = self._configs.get(name, self.default_config)

        state.consecutive_timeouts += 1
        state.total_failures += 1
        state.consecutive_valid_readings = 0

        if state.consecutive_timeouts >= config.max_consecutive_timeouts:
            old_status = state.status
            state.status = SensorStatus.DISCONNECTED
            self._failed_sensors.add(name)

            if old_status != SensorStatus.DISCONNECTED and self._on_failure:
                self._on_failure(
                    name,
                    SensorStatus.DISCONNECTED,
                    f"Timeout after {state.consecutive_timeouts} attempts"
                )

    def is_healthy(self, name: str) -> bool:
        """Check if sensor is healthy."""
        state = self._sensors.get(name)
        return state is not None and state.status == SensorStatus.HEALTHY

    def is_available(self, name: str) -> bool:
        """Check if sensor is available (healthy or degraded)."""
        state = self._sensors.get(name)
        if state is None:
            return False
        return state.status in (SensorStatus.HEALTHY, SensorStatus.DEGRADED)

    def get_status(self, name: str) -> Optional[SensorStatus]:
        """Get sensor status."""
        state = self._sensors.get(name)
        return state.status if state else None

    def get_failed_sensors(self) -> List[str]:
        """Get list of failed sensor names."""
        return list(self._failed_sensors)

    def get_fallback_value(
        self,
        name: str,
        default: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Get fallback value for a failed sensor.

        Args:
            name: Sensor identifier
            default: Default value if no fallback available

        Returns:
            Last known value (decayed) or default
        """
        state = self._sensors.get(name)
        config = self._configs.get(name, self.default_config)

        if state is None or state.last_valid_value is None:
            if default is not None:
                return default
            return np.zeros(12, dtype=np.float32)

        if not config.use_last_known_value:
            if default is not None:
                return default
            return np.zeros(12, dtype=np.float32)

        # Calculate decay based on time since last valid reading
        elapsed = time.perf_counter() - state.last_update_time
        decay_steps = int(elapsed * 10)  # ~100ms per step
        decay = config.fallback_decay_rate ** decay_steps

        return (state.last_valid_value * decay).astype(np.float32)

    def detect_failures(
        self,
        correlation_matrix: np.ndarray,
        modality_names: List[str],
        threshold: float = 0.2,
    ) -> List[str]:
        """
        Detect sensor failures from USE correlation matrix (U1).

        Args:
            correlation_matrix: NxN correlation matrix from compute_correlation_matrix
            modality_names: Names corresponding to matrix indices
            threshold: Coherence threshold for failure detection

        Returns:
            List of sensor names with low coherence
        """
        failures = []

        if correlation_matrix.size == 0:
            return failures

        n = len(modality_names)
        if correlation_matrix.shape != (n, n):
            return failures

        # Check each modality's average correlation with others
        for i, name in enumerate(modality_names):
            if name not in self._sensors:
                continue

            # Calculate mean correlation with other modalities
            mask = np.ones(n, dtype=bool)
            mask[i] = False
            mean_corr = np.mean(np.abs(correlation_matrix[i, mask]))

            if mean_corr < threshold:
                failures.append(name)
                self._sensors[name].coherence_score = mean_corr

        return failures

    def handle_failure(
        self,
        name: str,
        reason: str = "unknown",
    ) -> RecoveryAction:
        """
        Handle a detected sensor failure.

        Args:
            name: Sensor identifier
            reason: Failure reason

        Returns:
            Recommended recovery action
        """
        state = self._sensors.get(name)
        if state is None:
            return RecoveryAction.NONE

        state.total_failures += 1
        state.status = SensorStatus.FAILING
        self._failed_sensors.add(name)

        if self._on_failure:
            self._on_failure(name, SensorStatus.FAILING, reason)

        # Determine recovery action based on failure severity
        failure_rate = state.failure_rate

        if failure_rate > 0.5:
            # High failure rate - reduce reliance
            return RecoveryAction.REDUCE_SPEED
        elif state.status == SensorStatus.DISCONNECTED:
            # Completely disconnected
            return RecoveryAction.FALLBACK_TIER
        else:
            # Intermittent - retry
            return RecoveryAction.RETRY

    def reset(self, name: Optional[str] = None) -> None:
        """
        Reset sensor state.

        Args:
            name: Specific sensor to reset, or None for all
        """
        if name:
            if name in self._sensors:
                self._sensors[name] = SensorState(name=name)
                self._failed_sensors.discard(name)
        else:
            for sensor_name in self._sensors:
                self._sensors[sensor_name] = SensorState(name=sensor_name)
            self._failed_sensors.clear()

    def get_health_report(self) -> Dict[str, Any]:
        """Get complete sensor health report."""
        return {
            "sensors": {
                name: {
                    "status": state.status.name,
                    "coherence": state.coherence_score,
                    "failure_rate": state.failure_rate,
                    "consecutive_timeouts": state.consecutive_timeouts,
                    "total_readings": state.total_readings,
                    "total_failures": state.total_failures,
                }
                for name, state in self._sensors.items()
            },
            "failed_sensors": list(self._failed_sensors),
            "healthy_count": sum(
                1 for s in self._sensors.values()
                if s.status == SensorStatus.HEALTHY
            ),
            "total_count": len(self._sensors),
        }

    def raise_if_critical(self) -> None:
        """
        Raise exception if critical sensors have failed.

        Call this to enforce sensor requirements before operation.
        """
        for name in self._failed_sensors:
            state = self._sensors.get(name)
            if state and state.status == SensorStatus.DISCONNECTED:
                raise SensorDisconnectedError(
                    sensor_name=name,
                )
