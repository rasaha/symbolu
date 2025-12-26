# Symbolu Robotics - Tier Fallback Manager
"""
Automatic tier degradation and recovery management.

Handles graceful fallback when higher tiers fail:
- R3 (Deliberative) → R2 (Reactive) → R1 (Reflexive)

Features:
- Automatic fallback on timeout or error
- Gradual recovery when conditions improve
- State preservation across fallbacks
- Configurable fallback thresholds
"""

import time
from typing import Optional, Callable, Dict, List, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum, auto

from symbolu_robotics.core.exceptions import (
    RoboticsError,
    TierError,
    TierTimeoutError,
    TierUnavailableError,
    RecoveryAction,
    ErrorSeverity,
    ErrorHandler,
)

if TYPE_CHECKING:
    from symbolu_robotics.tiers.base import BaseTier
    from symbolu_robotics.core.types import SensorFrame, ActuatorCommand, Plan


class TierLevel(Enum):
    """Tier hierarchy levels."""
    R3_DELIBERATIVE = 3
    R2_REACTIVE = 2
    R1_REFLEXIVE = 1
    EMERGENCY_STOP = 0


@dataclass
class FallbackConfig:
    """Configuration for tier fallback behavior."""
    # Fallback triggers
    max_consecutive_errors: int = 3     # Errors before fallback
    timeout_tolerance_factor: float = 1.5  # Multiply latency budget

    # Recovery settings
    min_stable_time_s: float = 5.0      # Stable time before recovery
    recovery_check_interval_s: float = 1.0

    # Coherence thresholds (SCC S3)
    min_coherence_r3: float = 0.5       # Min coherence for R3
    min_coherence_r2: float = 0.3       # Min coherence for R2

    # Enable/disable automatic recovery
    auto_recover: bool = True

    # Emergency stop on R1 failure
    estop_on_r1_failure: bool = True


@dataclass
class TierState:
    """State tracking for a tier."""
    level: TierLevel
    is_available: bool = True
    consecutive_errors: int = 0
    last_error_time: Optional[float] = None
    last_success_time: Optional[float] = None
    total_errors: int = 0
    total_successes: int = 0


class TierFallbackManager:
    """
    Manages automatic tier fallback and recovery.

    Usage:
        fallback = TierFallbackManager(config)
        fallback.register_tier(TierLevel.R3_DELIBERATIVE, deliberative_tier)
        fallback.register_tier(TierLevel.R2_REACTIVE, reactive_tier)
        fallback.register_tier(TierLevel.R1_REFLEXIVE, reflexive_tier)

        # In control loop
        while running:
            try:
                tier = fallback.get_active_tier()
                result = tier.step(sensors)
                fallback.report_success()
            except RoboticsError as e:
                fallback.report_error(e)
                # Will automatically fall back if needed

    With error handler:
        fallback = TierFallbackManager(config, error_handler=handler)
        result = fallback.execute(sensors, command)  # Auto-fallback
    """

    def __init__(
        self,
        config: Optional[FallbackConfig] = None,
        error_handler: Optional[ErrorHandler] = None,
        on_fallback: Optional[Callable[[TierLevel, TierLevel, str], None]] = None,
        on_recovery: Optional[Callable[[TierLevel, TierLevel], None]] = None,
        on_estop: Optional[Callable[[str], None]] = None,
    ):
        self.config = config or FallbackConfig()
        self._error_handler = error_handler or ErrorHandler()
        self._on_fallback = on_fallback
        self._on_recovery = on_recovery
        self._on_estop = on_estop

        self._tiers: Dict[TierLevel, Any] = {}
        self._tier_states: Dict[TierLevel, TierState] = {}
        self._current_level = TierLevel.R3_DELIBERATIVE
        self._target_level = TierLevel.R3_DELIBERATIVE
        self._last_stable_time: Optional[float] = None
        self._in_emergency = False

    def register_tier(self, level: TierLevel, tier: "BaseTier") -> None:
        """
        Register a tier implementation.

        Args:
            level: Tier level (R1, R2, R3)
            tier: Tier implementation
        """
        self._tiers[level] = tier
        self._tier_states[level] = TierState(level=level)

    def unregister_tier(self, level: TierLevel) -> None:
        """Remove a tier."""
        self._tiers.pop(level, None)
        self._tier_states.pop(level, None)

    def get_active_tier(self) -> Optional["BaseTier"]:
        """Get the currently active tier."""
        return self._tiers.get(self._current_level)

    @property
    def current_level(self) -> TierLevel:
        """Get current tier level."""
        return self._current_level

    @property
    def target_level(self) -> TierLevel:
        """Get target tier level (may differ during recovery)."""
        return self._target_level

    @property
    def is_degraded(self) -> bool:
        """Check if currently operating at reduced capability."""
        return self._current_level.value < self._target_level.value

    @property
    def in_emergency(self) -> bool:
        """Check if in emergency stop state."""
        return self._in_emergency

    def set_target_level(self, level: TierLevel) -> None:
        """
        Set the desired operating tier level.

        The manager will attempt to reach this level when conditions allow.
        """
        self._target_level = level

    def report_success(self) -> None:
        """Report successful tier execution."""
        state = self._tier_states.get(self._current_level)
        if state:
            state.consecutive_errors = 0
            state.last_success_time = time.perf_counter()
            state.total_successes += 1

            # Update stable time
            if state.consecutive_errors == 0:
                if self._last_stable_time is None:
                    self._last_stable_time = time.perf_counter()

        # Check for recovery opportunity
        if self.config.auto_recover and self.is_degraded:
            self._check_recovery()

    def report_error(self, error: RoboticsError) -> RecoveryAction:
        """
        Report an error from tier execution.

        Args:
            error: The error that occurred

        Returns:
            Recovery action taken
        """
        state = self._tier_states.get(self._current_level)
        if state:
            state.consecutive_errors += 1
            state.last_error_time = time.perf_counter()
            state.total_errors += 1
            self._last_stable_time = None

        # Let error handler determine action
        action = self._error_handler.handle(error)

        # Handle fallback
        if action == RecoveryAction.FALLBACK_TIER or error.should_fallback():
            self._trigger_fallback(str(error))
        elif action == RecoveryAction.EMERGENCY_STOP or error.should_stop():
            self._trigger_emergency_stop(str(error))

        return action

    def _trigger_fallback(self, reason: str) -> bool:
        """
        Trigger fallback to lower tier.

        Returns:
            True if fallback successful, False if no lower tier available
        """
        old_level = self._current_level

        # Find next available lower tier
        for level in TierLevel:
            if level.value < self._current_level.value:
                if level in self._tiers:
                    state = self._tier_states.get(level)
                    if state and state.is_available:
                        self._current_level = level
                        self._last_stable_time = None

                        if self._on_fallback:
                            self._on_fallback(old_level, level, reason)

                        return True

        # No fallback available - emergency stop
        if self.config.estop_on_r1_failure:
            self._trigger_emergency_stop(f"No fallback available: {reason}")

        return False

    def _trigger_emergency_stop(self, reason: str) -> None:
        """Trigger emergency stop."""
        self._in_emergency = True
        self._current_level = TierLevel.EMERGENCY_STOP

        if self._on_estop:
            self._on_estop(reason)

    def _check_recovery(self) -> None:
        """Check if conditions allow recovery to higher tier."""
        if self._last_stable_time is None:
            return

        stable_duration = time.perf_counter() - self._last_stable_time
        if stable_duration < self.config.min_stable_time_s:
            return

        # Try to recover to next higher tier
        for level in sorted(TierLevel, key=lambda x: x.value, reverse=True):
            if level.value <= self._target_level.value:
                if level.value > self._current_level.value:
                    if self._can_recover_to(level):
                        old_level = self._current_level
                        self._current_level = level
                        self._last_stable_time = time.perf_counter()

                        if self._on_recovery:
                            self._on_recovery(old_level, level)

                        # Clear error handler counts on recovery
                        self._error_handler.clear_counts()
                        break

    def _can_recover_to(self, level: TierLevel) -> bool:
        """Check if recovery to specified level is possible."""
        if level not in self._tiers:
            return False

        state = self._tier_states.get(level)
        if not state or not state.is_available:
            return False

        # Check if tier has been stable recently
        if state.consecutive_errors > 0:
            return False

        return True

    def execute(
        self,
        sensor_frame: "SensorFrame",
        command: Optional[str] = None,
        coherence: Optional[float] = None,
    ) -> Optional["Plan"]:
        """
        Execute the appropriate tier with automatic fallback.

        Args:
            sensor_frame: Current sensor data
            command: Optional NL command (for R3)
            coherence: Current coherence score (SCC S2)

        Returns:
            Plan from executed tier, or None on emergency stop
        """
        if self._in_emergency:
            return None

        # Check coherence requirements
        if coherence is not None:
            self._check_coherence_requirements(coherence)

        # Try current tier
        tier = self.get_active_tier()
        if tier is None:
            self._trigger_fallback("No tier available")
            tier = self.get_active_tier()
            if tier is None:
                self._trigger_emergency_stop("All tiers unavailable")
                return None

        try:
            # Execute tier
            if self._current_level == TierLevel.R3_DELIBERATIVE:
                result = tier.step(sensor_frame, command)
            else:
                result = tier.step(sensor_frame)

            self.report_success()
            return result

        except RoboticsError as e:
            action = self.report_error(e)

            # Retry with fallback tier if available
            if action == RecoveryAction.FALLBACK_TIER:
                return self.execute(sensor_frame, command, coherence)

            return None

        except Exception as e:
            # Wrap unexpected errors
            error = TierError(
                message=str(e),
                tier_name=self._current_level.name,
                severity=ErrorSeverity.ERROR,
                recovery=RecoveryAction.FALLBACK_TIER,
                cause=e,
            )
            self.report_error(error)
            return self.execute(sensor_frame, command, coherence)

    def _check_coherence_requirements(self, coherence: float) -> None:
        """Check if coherence meets tier requirements."""
        if self._current_level == TierLevel.R3_DELIBERATIVE:
            if coherence < self.config.min_coherence_r3:
                self._trigger_fallback(
                    f"Coherence {coherence:.2f} < R3 threshold "
                    f"{self.config.min_coherence_r3:.2f}"
                )

        elif self._current_level == TierLevel.R2_REACTIVE:
            if coherence < self.config.min_coherence_r2:
                self._trigger_fallback(
                    f"Coherence {coherence:.2f} < R2 threshold "
                    f"{self.config.min_coherence_r2:.2f}"
                )

    def reset_emergency(self) -> None:
        """Reset emergency stop state (requires manual intervention)."""
        self._in_emergency = False
        self._current_level = TierLevel.R1_REFLEXIVE
        self._last_stable_time = None

        # Reset all tier states
        for state in self._tier_states.values():
            state.consecutive_errors = 0
            state.is_available = True

        self._error_handler.clear_counts()

    def set_tier_available(self, level: TierLevel, available: bool) -> None:
        """Manually set tier availability."""
        state = self._tier_states.get(level)
        if state:
            state.is_available = available

    def get_status(self) -> Dict[str, Any]:
        """Get complete fallback manager status."""
        return {
            "current_level": self._current_level.name,
            "target_level": self._target_level.name,
            "is_degraded": self.is_degraded,
            "in_emergency": self._in_emergency,
            "tier_states": {
                level.name: {
                    "available": state.is_available,
                    "consecutive_errors": state.consecutive_errors,
                    "total_errors": state.total_errors,
                    "total_successes": state.total_successes,
                }
                for level, state in self._tier_states.items()
            },
        }
