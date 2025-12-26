# Symbolu Robotics - Exception Hierarchy
"""
Comprehensive exception hierarchy for robotics error handling.

Enables structured error recovery and tier fallback mechanisms.

Exception Categories:
- RoboticsError: Base class for all robotics errors
- SensorError: Sensor-related failures
- ActuatorError: Actuator/motor failures
- SafetyError: Safety constraint violations
- CommunicationError: Network/bus failures
- PlanningError: Planning/reasoning failures
- TierError: Tier execution failures
"""

from typing import Optional, List, Dict, Any
from enum import Enum, auto


class ErrorSeverity(Enum):
    """Severity levels for error handling."""
    DEBUG = auto()      # Informational, no action needed
    WARNING = auto()    # Degraded performance, continue operation
    ERROR = auto()      # Significant issue, may need tier fallback
    CRITICAL = auto()   # Safety-critical, immediate stop required
    FATAL = auto()      # Unrecoverable, system shutdown


class RecoveryAction(Enum):
    """Recommended recovery actions."""
    NONE = auto()              # No action needed
    RETRY = auto()             # Retry the operation
    FALLBACK_TIER = auto()     # Fall back to lower tier
    REDUCE_SPEED = auto()      # Reduce operational speed
    STOP_MOTION = auto()       # Stop all motion
    EMERGENCY_STOP = auto()    # Trigger E-stop
    RESET_SENSOR = auto()      # Reset/recalibrate sensor
    RESET_SYSTEM = auto()      # Full system reset


class RoboticsError(Exception):
    """
    Base exception for all robotics errors.

    Attributes:
        message: Human-readable error description
        severity: Error severity level
        recovery: Recommended recovery action
        context: Additional context dictionary
        cause: Original exception that caused this error
    """

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        recovery: RecoveryAction = RecoveryAction.NONE,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.recovery = recovery
        self.context = context or {}
        self.cause = cause

    def __str__(self) -> str:
        return f"[{self.severity.name}] {self.message}"

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"severity={self.severity}, "
            f"recovery={self.recovery})"
        )

    def should_stop(self) -> bool:
        """Check if error requires stopping motion."""
        return self.severity in (ErrorSeverity.CRITICAL, ErrorSeverity.FATAL)

    def should_fallback(self) -> bool:
        """Check if error suggests tier fallback."""
        return self.recovery == RecoveryAction.FALLBACK_TIER


# =============================================================================
# Sensor Errors
# =============================================================================

class SensorError(RoboticsError):
    """Base class for sensor-related errors."""

    def __init__(
        self,
        message: str,
        sensor_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.sensor_name = sensor_name
        self.context["sensor_name"] = sensor_name


class SensorTimeoutError(SensorError):
    """Sensor failed to respond within timeout."""

    def __init__(
        self,
        sensor_name: str,
        timeout_ms: float,
        **kwargs
    ):
        message = f"Sensor '{sensor_name}' timeout after {timeout_ms:.1f}ms"
        super().__init__(
            message,
            sensor_name=sensor_name,
            severity=ErrorSeverity.WARNING,
            recovery=RecoveryAction.RETRY,
            **kwargs
        )
        self.timeout_ms = timeout_ms
        self.context["timeout_ms"] = timeout_ms


class SensorDataError(SensorError):
    """Sensor returned invalid or corrupted data."""

    def __init__(
        self,
        sensor_name: str,
        reason: str = "invalid data",
        **kwargs
    ):
        message = f"Sensor '{sensor_name}' data error: {reason}"
        super().__init__(
            message,
            sensor_name=sensor_name,
            severity=ErrorSeverity.WARNING,
            recovery=RecoveryAction.RESET_SENSOR,
            **kwargs
        )
        self.reason = reason


class SensorCoherenceError(SensorError):
    """Sensor readings inconsistent with other sensors (USE U1 detection)."""

    def __init__(
        self,
        sensor_name: str,
        coherence_score: float,
        threshold: float = 0.2,
        **kwargs
    ):
        message = (
            f"Sensor '{sensor_name}' coherence {coherence_score:.2f} "
            f"below threshold {threshold:.2f}"
        )
        super().__init__(
            message,
            sensor_name=sensor_name,
            severity=ErrorSeverity.WARNING,
            recovery=RecoveryAction.REDUCE_SPEED,
            **kwargs
        )
        self.coherence_score = coherence_score
        self.threshold = threshold
        self.context["coherence_score"] = coherence_score


class SensorDisconnectedError(SensorError):
    """Sensor physically disconnected or not responding."""

    def __init__(self, sensor_name: str, **kwargs):
        message = f"Sensor '{sensor_name}' disconnected"
        super().__init__(
            message,
            sensor_name=sensor_name,
            severity=ErrorSeverity.ERROR,
            recovery=RecoveryAction.FALLBACK_TIER,
            **kwargs
        )


# =============================================================================
# Actuator Errors
# =============================================================================

class ActuatorError(RoboticsError):
    """Base class for actuator-related errors."""

    def __init__(
        self,
        message: str,
        actuator_id: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.actuator_id = actuator_id
        self.context["actuator_id"] = actuator_id


class ActuatorLimitError(ActuatorError):
    """Actuator command exceeds limits."""

    def __init__(
        self,
        actuator_id: int,
        limit_type: str,
        value: float,
        limit: float,
        **kwargs
    ):
        message = (
            f"Actuator {actuator_id} {limit_type} limit exceeded: "
            f"{value:.3f} > {limit:.3f}"
        )
        super().__init__(
            message,
            actuator_id=actuator_id,
            severity=ErrorSeverity.WARNING,
            recovery=RecoveryAction.NONE,  # Automatically clamped
            **kwargs
        )
        self.limit_type = limit_type
        self.value = value
        self.limit = limit


class ActuatorFaultError(ActuatorError):
    """Actuator hardware fault detected."""

    def __init__(
        self,
        actuator_id: int,
        fault_code: int,
        fault_description: str = "unknown",
        **kwargs
    ):
        message = (
            f"Actuator {actuator_id} fault 0x{fault_code:04X}: "
            f"{fault_description}"
        )
        super().__init__(
            message,
            actuator_id=actuator_id,
            severity=ErrorSeverity.CRITICAL,
            recovery=RecoveryAction.STOP_MOTION,
            **kwargs
        )
        self.fault_code = fault_code
        self.fault_description = fault_description


class ActuatorOverheatError(ActuatorError):
    """Actuator temperature exceeds safe limits."""

    def __init__(
        self,
        actuator_id: int,
        temperature: float,
        max_temperature: float,
        **kwargs
    ):
        message = (
            f"Actuator {actuator_id} overheating: "
            f"{temperature:.1f}°C > {max_temperature:.1f}°C"
        )
        super().__init__(
            message,
            actuator_id=actuator_id,
            severity=ErrorSeverity.CRITICAL,
            recovery=RecoveryAction.STOP_MOTION,
            **kwargs
        )
        self.temperature = temperature
        self.max_temperature = max_temperature


# =============================================================================
# Safety Errors
# =============================================================================

class SafetyError(RoboticsError):
    """Base class for safety-related errors."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("severity", ErrorSeverity.CRITICAL)
        kwargs.setdefault("recovery", RecoveryAction.STOP_MOTION)
        super().__init__(message, **kwargs)


class CollisionDetectedError(SafetyError):
    """Collision detected or imminent."""

    def __init__(
        self,
        distance: float,
        threshold: float,
        obstacle_type: str = "unknown",
        **kwargs
    ):
        message = (
            f"Collision risk: {obstacle_type} at {distance:.3f}m "
            f"(threshold: {threshold:.3f}m)"
        )
        super().__init__(
            message,
            recovery=RecoveryAction.EMERGENCY_STOP,
            **kwargs
        )
        self.distance = distance
        self.threshold = threshold
        self.obstacle_type = obstacle_type


class HumanProximityError(SafetyError):
    """Human detected in unsafe proximity."""

    def __init__(
        self,
        distance: float,
        safe_distance: float,
        **kwargs
    ):
        message = (
            f"Human proximity violation: {distance:.2f}m "
            f"(safe: {safe_distance:.2f}m)"
        )
        super().__init__(
            message,
            recovery=RecoveryAction.EMERGENCY_STOP,
            **kwargs
        )
        self.distance = distance
        self.safe_distance = safe_distance


class CoherenceViolationError(SafetyError):
    """SCC coherence below safety threshold (S3/S9)."""

    def __init__(
        self,
        global_coherence: float,
        threshold: float,
        weakest_layers: Optional[List[int]] = None,
        **kwargs
    ):
        message = (
            f"Coherence violation: {global_coherence:.3f} < {threshold:.3f}"
        )
        super().__init__(
            message,
            severity=ErrorSeverity.ERROR,
            recovery=RecoveryAction.REDUCE_SPEED,
            **kwargs
        )
        self.global_coherence = global_coherence
        self.threshold = threshold
        self.weakest_layers = weakest_layers or []
        self.context["weakest_layers"] = self.weakest_layers


class EntropySpikError(SafetyError):
    """SCC entropy spike detected (S6)."""

    def __init__(
        self,
        entropy_rate: float,
        threshold: float,
        **kwargs
    ):
        message = (
            f"Entropy spike detected: rate {entropy_rate:.3f} "
            f"> threshold {threshold:.3f}"
        )
        super().__init__(
            message,
            severity=ErrorSeverity.WARNING,
            recovery=RecoveryAction.REDUCE_SPEED,
            **kwargs
        )
        self.entropy_rate = entropy_rate
        self.threshold = threshold


# =============================================================================
# Communication Errors
# =============================================================================

class CommunicationError(RoboticsError):
    """Base class for communication errors."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("severity", ErrorSeverity.ERROR)
        kwargs.setdefault("recovery", RecoveryAction.RETRY)
        super().__init__(message, **kwargs)


class ConnectionLostError(CommunicationError):
    """Connection to hardware/network lost."""

    def __init__(
        self,
        endpoint: str,
        last_contact_ms: Optional[float] = None,
        **kwargs
    ):
        message = f"Connection lost to {endpoint}"
        if last_contact_ms is not None:
            message += f" (last contact: {last_contact_ms:.0f}ms ago)"
        super().__init__(
            message,
            recovery=RecoveryAction.FALLBACK_TIER,
            **kwargs
        )
        self.endpoint = endpoint
        self.last_contact_ms = last_contact_ms


class MessageTimeoutError(CommunicationError):
    """Message not acknowledged within timeout."""

    def __init__(
        self,
        message_type: str,
        timeout_ms: float,
        **kwargs
    ):
        message = f"Message '{message_type}' timeout after {timeout_ms:.0f}ms"
        super().__init__(message, **kwargs)
        self.message_type = message_type
        self.timeout_ms = timeout_ms


class SwarmCommunicationError(CommunicationError):
    """Multi-robot communication failure."""

    def __init__(
        self,
        robot_id: str,
        reason: str = "no response",
        **kwargs
    ):
        message = f"Swarm communication error with {robot_id}: {reason}"
        super().__init__(message, **kwargs)
        self.robot_id = robot_id
        self.reason = reason


# =============================================================================
# Planning Errors
# =============================================================================

class PlanningError(RoboticsError):
    """Base class for planning/reasoning errors."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("severity", ErrorSeverity.ERROR)
        kwargs.setdefault("recovery", RecoveryAction.FALLBACK_TIER)
        super().__init__(message, **kwargs)


class NoPlanFoundError(PlanningError):
    """No valid plan found for goal."""

    def __init__(
        self,
        goal_description: str,
        reason: str = "no feasible path",
        **kwargs
    ):
        message = f"No plan found for '{goal_description}': {reason}"
        super().__init__(message, **kwargs)
        self.goal_description = goal_description
        self.reason = reason


class PlanExecutionError(PlanningError):
    """Plan execution failed."""

    def __init__(
        self,
        step_index: int,
        total_steps: int,
        reason: str,
        **kwargs
    ):
        message = (
            f"Plan execution failed at step {step_index}/{total_steps}: "
            f"{reason}"
        )
        super().__init__(message, **kwargs)
        self.step_index = step_index
        self.total_steps = total_steps
        self.reason = reason


class GoalUnreachableError(PlanningError):
    """Goal is physically unreachable."""

    def __init__(
        self,
        goal_description: str,
        reason: str = "out of workspace",
        **kwargs
    ):
        message = f"Goal '{goal_description}' unreachable: {reason}"
        super().__init__(message, **kwargs)
        self.goal_description = goal_description
        self.reason = reason


# =============================================================================
# Tier Errors
# =============================================================================

class TierError(RoboticsError):
    """Base class for tier execution errors."""

    def __init__(
        self,
        message: str,
        tier_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.tier_name = tier_name
        self.context["tier_name"] = tier_name


class TierTimeoutError(TierError):
    """Tier exceeded latency budget."""

    def __init__(
        self,
        tier_name: str,
        actual_latency_ms: float,
        budget_ms: float,
        **kwargs
    ):
        message = (
            f"Tier '{tier_name}' timeout: {actual_latency_ms:.1f}ms "
            f"> budget {budget_ms:.1f}ms"
        )
        super().__init__(
            message,
            tier_name=tier_name,
            severity=ErrorSeverity.WARNING,
            recovery=RecoveryAction.FALLBACK_TIER,
            **kwargs
        )
        self.actual_latency_ms = actual_latency_ms
        self.budget_ms = budget_ms


class TierUnavailableError(TierError):
    """Requested tier is unavailable."""

    def __init__(
        self,
        tier_name: str,
        reason: str = "not initialized",
        **kwargs
    ):
        message = f"Tier '{tier_name}' unavailable: {reason}"
        super().__init__(
            message,
            tier_name=tier_name,
            severity=ErrorSeverity.ERROR,
            recovery=RecoveryAction.FALLBACK_TIER,
            **kwargs
        )
        self.reason = reason


# =============================================================================
# Error Handler
# =============================================================================

class ErrorHandler:
    """
    Centralized error handling and recovery coordination.

    Usage:
        handler = ErrorHandler()

        try:
            result = tier.step(sensors)
        except RoboticsError as e:
            action = handler.handle(e)
            if action == RecoveryAction.FALLBACK_TIER:
                result = fallback_tier.step(sensors)
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_ms: float = 100.0,
    ):
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
        self._error_counts: Dict[str, int] = {}
        self._error_history: List[RoboticsError] = []

    def handle(self, error: RoboticsError) -> RecoveryAction:
        """
        Handle an error and return recommended recovery action.

        Updates error statistics and may escalate recovery action
        based on error frequency.
        """
        # Track error
        error_type = type(error).__name__
        self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1
        self._error_history.append(error)

        # Limit history size
        if len(self._error_history) > 100:
            self._error_history = self._error_history[-100:]

        # Escalate if repeated errors
        if self._error_counts[error_type] > self.max_retries:
            if error.recovery == RecoveryAction.RETRY:
                return RecoveryAction.FALLBACK_TIER
            if error.recovery == RecoveryAction.REDUCE_SPEED:
                return RecoveryAction.STOP_MOTION

        return error.recovery

    def clear_counts(self) -> None:
        """Clear error counts (e.g., after successful recovery)."""
        self._error_counts.clear()

    def get_statistics(self) -> Dict[str, int]:
        """Get error count statistics."""
        return self._error_counts.copy()

    def get_recent_errors(self, n: int = 10) -> List[RoboticsError]:
        """Get n most recent errors."""
        return self._error_history[-n:]
