"""
Online Calibration Module
=========================

Continuous sensor and actuator calibration during operation.

Features:
- Sensor bias/drift estimation
- Actuator model refinement
- Cross-modal calibration via USE coherence
- Automatic re-calibration triggers

Integration with Symbolu:
- USE (U1) correlation matrix identifies sensor drift
- SCC coherence degradation triggers recalibration
- Calibration preserves 12D layer semantics
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import numpy as np

from symbolu_robotics.core.types import Layer12D, SensorFrame


class CalibrationStatus(Enum):
    """Calibration status."""
    UNKNOWN = "unknown"
    CALIBRATING = "calibrating"
    CALIBRATED = "calibrated"
    DRIFT_DETECTED = "drift_detected"
    NEEDS_RECALIBRATION = "needs_recalibration"


@dataclass
class CalibrationConfig:
    """Configuration for online calibration."""
    # Sensor calibration
    bias_estimation_window: int = 100  # Samples for bias estimation
    drift_threshold: float = 0.1  # Threshold for drift detection

    # Actuator calibration
    model_update_rate: float = 0.01  # EMA for model updates

    # Coherence triggers
    coherence_recalibration_threshold: float = 0.3  # Trigger recalibration
    correlation_drop_threshold: float = 0.2  # USE correlation drop

    # Auto-calibration
    auto_recalibrate: bool = True
    recalibration_cooldown: float = 60.0  # Seconds between recalibrations


@dataclass
class CalibrationState:
    """Current calibration state for a sensor/actuator."""
    name: str
    status: CalibrationStatus = CalibrationStatus.UNKNOWN

    # Bias estimation
    bias: np.ndarray = field(default_factory=lambda: np.zeros(3))
    scale: np.ndarray = field(default_factory=lambda: np.ones(3))

    # Drift tracking
    drift_rate: float = 0.0
    last_calibration_time: float = 0.0

    # Quality metrics
    confidence: float = 0.0
    samples_collected: int = 0

    def apply(self, raw_value: np.ndarray) -> np.ndarray:
        """Apply calibration to raw sensor value."""
        return (raw_value - self.bias) * self.scale


class SensorCalibrator:
    """
    Online sensor calibration.

    Estimates bias and scale for sensor readings.
    Uses cross-modal consistency for validation.
    """

    def __init__(self, name: str, expected_dim: int = 3):
        self._name = name
        self._dim = expected_dim
        self._state = CalibrationState(name=name)

        # Running statistics
        self._samples: List[np.ndarray] = []
        self._reference_samples: List[np.ndarray] = []

        # EMA estimators
        self._mean_ema: np.ndarray = np.zeros(expected_dim)
        self._var_ema: np.ndarray = np.ones(expected_dim)
        self._alpha = 0.1

    @property
    def state(self) -> CalibrationState:
        return self._state

    def update(
        self,
        raw_value: np.ndarray,
        reference: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Update calibration with new sample.

        Args:
            raw_value: Raw sensor reading
            reference: Optional reference value (from other sensor or known)

        Returns:
            Calibrated value
        """
        # Ensure correct shape
        raw_value = np.atleast_1d(raw_value)[:self._dim]
        if len(raw_value) < self._dim:
            raw_value = np.pad(raw_value, (0, self._dim - len(raw_value)))

        # Update statistics
        self._samples.append(raw_value)
        if reference is not None:
            self._reference_samples.append(reference)

        # EMA update
        self._mean_ema = self._alpha * raw_value + (1 - self._alpha) * self._mean_ema
        diff_sq = (raw_value - self._mean_ema) ** 2
        self._var_ema = self._alpha * diff_sq + (1 - self._alpha) * self._var_ema

        # Update state
        self._state.samples_collected += 1

        # Check for calibration
        if self._state.status == CalibrationStatus.UNKNOWN:
            self._state.status = CalibrationStatus.CALIBRATING

        # Apply current calibration
        return self._state.apply(raw_value)

    def calibrate(self, known_reference: Optional[np.ndarray] = None) -> bool:
        """
        Perform calibration from collected samples.

        Args:
            known_reference: Known reference value for absolute calibration

        Returns:
            True if calibration successful
        """
        if len(self._samples) < 10:
            return False

        samples = np.array(self._samples[-100:])  # Use recent samples

        # Estimate bias (mean under static conditions)
        if known_reference is not None:
            # Absolute calibration with reference
            self._state.bias = samples.mean(axis=0) - known_reference
            self._state.scale = np.ones(self._dim)
        elif len(self._reference_samples) >= 10:
            # Cross-modal calibration
            refs = np.array(self._reference_samples[-100:])
            self._state.bias = samples.mean(axis=0) - refs.mean(axis=0)

            # Scale estimation
            sample_std = samples.std(axis=0)
            ref_std = refs.std(axis=0)
            self._state.scale = np.where(
                sample_std > 1e-6,
                ref_std / sample_std,
                np.ones(self._dim)
            )
        else:
            # Zero-mean assumption
            self._state.bias = samples.mean(axis=0)
            self._state.scale = np.ones(self._dim)

        self._state.status = CalibrationStatus.CALIBRATED
        self._state.confidence = min(1.0, len(samples) / 100)

        return True

    def detect_drift(self) -> Tuple[bool, float]:
        """
        Detect sensor drift.

        Returns:
            (drift_detected, drift_magnitude)
        """
        if len(self._samples) < 50:
            return False, 0.0

        # Compare recent mean to calibration
        recent = np.array(self._samples[-20:])
        recent_mean = recent.mean(axis=0)

        # Drift = deviation from expected zero (after calibration)
        calibrated_mean = self._state.apply(recent_mean)
        drift = np.linalg.norm(calibrated_mean)

        drift_detected = drift > 0.1

        if drift_detected:
            self._state.status = CalibrationStatus.DRIFT_DETECTED
            self._state.drift_rate = drift

        return drift_detected, drift

    def reset(self) -> None:
        """Reset calibration state."""
        self._samples.clear()
        self._reference_samples.clear()
        self._state = CalibrationState(name=self._name)
        self._mean_ema = np.zeros(self._dim)
        self._var_ema = np.ones(self._dim)


class ActuatorCalibrator:
    """
    Online actuator model calibration.

    Learns mapping from commanded to actual actuator response.
    """

    def __init__(self, name: str, num_joints: int = 6):
        self._name = name
        self._num_joints = num_joints
        self._state = CalibrationState(
            name=name,
            bias=np.zeros(num_joints),
            scale=np.ones(num_joints),
        )

        # Command-response pairs
        self._commands: List[np.ndarray] = []
        self._responses: List[np.ndarray] = []

    @property
    def state(self) -> CalibrationState:
        return self._state

    def record(self, command: np.ndarray, actual: np.ndarray) -> None:
        """Record command-response pair."""
        self._commands.append(command.copy())
        self._responses.append(actual.copy())
        self._state.samples_collected += 1

    def calibrate(self) -> bool:
        """Calibrate actuator model from recorded pairs."""
        if len(self._commands) < 20:
            return False

        commands = np.array(self._commands[-100:])
        responses = np.array(self._responses[-100:])

        # Linear model: actual = scale * command + bias
        # Simple least squares
        mean_cmd = commands.mean(axis=0)
        mean_resp = responses.mean(axis=0)

        cmd_var = ((commands - mean_cmd) ** 2).mean(axis=0)
        covar = ((commands - mean_cmd) * (responses - mean_resp)).mean(axis=0)

        self._state.scale = np.where(
            cmd_var > 1e-6,
            covar / cmd_var,
            np.ones(self._num_joints)
        )
        self._state.bias = mean_resp - self._state.scale * mean_cmd

        self._state.status = CalibrationStatus.CALIBRATED
        self._state.confidence = min(1.0, len(commands) / 100)

        return True

    def compensate(self, command: np.ndarray) -> np.ndarray:
        """
        Compensate command for actuator model.

        Returns command that should produce desired actual output.
        """
        # Inverse of: actual = scale * command + bias
        # So: compensated = (desired - bias) / scale
        compensated = (command - self._state.bias) / np.maximum(
            self._state.scale, 1e-6
        )
        return compensated

    def reset(self) -> None:
        """Reset calibration."""
        self._commands.clear()
        self._responses.clear()
        self._state = CalibrationState(
            name=self._name,
            bias=np.zeros(self._num_joints),
            scale=np.ones(self._num_joints),
        )


class OnlineCalibrator:
    """
    Unified online calibration system.

    Manages calibration for all sensors and actuators.
    Integrates with Symbolu coherence for quality assurance.
    """

    def __init__(self, config: Optional[CalibrationConfig] = None):
        self._config = config or CalibrationConfig()

        # Calibrators
        self._sensors: Dict[str, SensorCalibrator] = {}
        self._actuators: Dict[str, ActuatorCalibrator] = {}

        # Overall state
        self._last_coherence = 0.0
        self._recalibration_count = 0
        self._last_recalibration_time = 0.0

    def register_sensor(self, name: str, dim: int = 3) -> SensorCalibrator:
        """Register a sensor for calibration."""
        calibrator = SensorCalibrator(name, dim)
        self._sensors[name] = calibrator
        return calibrator

    def register_actuator(self, name: str, num_joints: int = 6) -> ActuatorCalibrator:
        """Register an actuator for calibration."""
        calibrator = ActuatorCalibrator(name, num_joints)
        self._actuators[name] = calibrator
        return calibrator

    def update_sensor(
        self,
        name: str,
        raw_value: np.ndarray,
        reference: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Update sensor with new reading."""
        if name not in self._sensors:
            return raw_value
        return self._sensors[name].update(raw_value, reference)

    def record_actuator(
        self,
        name: str,
        command: np.ndarray,
        actual: np.ndarray,
    ) -> None:
        """Record actuator command-response pair."""
        if name in self._actuators:
            self._actuators[name].record(command, actual)

    def update_coherence(self, coherence: float, correlation_matrix: Optional[np.ndarray] = None) -> None:
        """
        Update with USE coherence and correlation.

        Triggers recalibration if needed.
        """
        prev_coherence = self._last_coherence
        self._last_coherence = coherence

        # Check for coherence drop
        coherence_drop = prev_coherence - coherence
        if coherence_drop > self._config.correlation_drop_threshold:
            self._trigger_recalibration("coherence_drop")

        # Check for low coherence
        if coherence < self._config.coherence_recalibration_threshold:
            self._trigger_recalibration("low_coherence")

    def _trigger_recalibration(self, reason: str) -> None:
        """Trigger recalibration if conditions met."""
        if not self._config.auto_recalibrate:
            return

        # Mark sensors as needing recalibration
        for sensor in self._sensors.values():
            if sensor.state.status == CalibrationStatus.CALIBRATED:
                sensor._state.status = CalibrationStatus.NEEDS_RECALIBRATION

        self._recalibration_count += 1

    def calibrate_all(self) -> Dict[str, bool]:
        """Calibrate all sensors and actuators."""
        results = {}

        for name, sensor in self._sensors.items():
            results[f"sensor_{name}"] = sensor.calibrate()

        for name, actuator in self._actuators.items():
            results[f"actuator_{name}"] = actuator.calibrate()

        return results

    def detect_drift_all(self) -> Dict[str, Tuple[bool, float]]:
        """Detect drift in all sensors."""
        results = {}

        for name, sensor in self._sensors.items():
            results[name] = sensor.detect_drift()

        return results

    def get_sensor_state(self, name: str) -> Optional[CalibrationState]:
        """Get sensor calibration state."""
        if name in self._sensors:
            return self._sensors[name].state
        return None

    def get_actuator_state(self, name: str) -> Optional[CalibrationState]:
        """Get actuator calibration state."""
        if name in self._actuators:
            return self._actuators[name].state
        return None

    def get_metrics(self) -> Dict[str, Any]:
        """Get calibration metrics."""
        return {
            "sensors": {
                name: {
                    "status": sensor.state.status.value,
                    "confidence": sensor.state.confidence,
                    "samples": sensor.state.samples_collected,
                    "drift_rate": sensor.state.drift_rate,
                }
                for name, sensor in self._sensors.items()
            },
            "actuators": {
                name: {
                    "status": actuator.state.status.value,
                    "confidence": actuator.state.confidence,
                    "samples": actuator.state.samples_collected,
                }
                for name, actuator in self._actuators.items()
            },
            "recalibration_count": self._recalibration_count,
            "last_coherence": self._last_coherence,
        }

    def reset(self) -> None:
        """Reset all calibrators."""
        for sensor in self._sensors.values():
            sensor.reset()
        for actuator in self._actuators.values():
            actuator.reset()
        self._recalibration_count = 0
