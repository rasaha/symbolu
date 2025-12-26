# Symbolu Robotics - Watchdog Monitor
"""
Watchdog timer for communication and system health monitoring.

Monitors:
- Tier execution latency
- Sensor update frequency
- Communication heartbeats
- System resource usage

Actions on timeout:
- Trigger tier fallback
- Emergency stop if safety-critical
- Alert and logging
"""

import time
import threading
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum, auto

from symbolu_robotics.core.exceptions import (
    RoboticsError,
    TierTimeoutError,
    SensorTimeoutError,
    ConnectionLostError,
    RecoveryAction,
    ErrorSeverity,
)


class WatchdogState(Enum):
    """Watchdog operational state."""
    IDLE = auto()
    RUNNING = auto()
    TRIGGERED = auto()
    STOPPED = auto()


@dataclass
class WatchdogConfig:
    """Configuration for watchdog monitoring."""
    # Tier latency budgets (ms)
    tier_r1_timeout_ms: float = 1.0      # Reflexive: <1ms
    tier_r2_timeout_ms: float = 10.0     # Reactive: <10ms
    tier_r3_timeout_ms: float = 100.0    # Deliberative: <100ms

    # Sensor timeouts (ms)
    sensor_timeout_ms: float = 100.0     # Max time between sensor updates

    # Communication heartbeat
    heartbeat_timeout_ms: float = 500.0  # Max time without heartbeat

    # Callback intervals
    check_interval_ms: float = 10.0      # How often to check timeouts

    # Recovery settings
    max_consecutive_timeouts: int = 3    # Timeouts before escalation
    escalation_multiplier: float = 2.0   # Multiply timeout on escalation


@dataclass
class WatchdogEntry:
    """Entry being monitored by watchdog."""
    name: str
    timeout_ms: float
    last_kick_time: float = field(default_factory=time.perf_counter)
    timeout_count: int = 0
    on_timeout: Optional[Callable[[], None]] = None


class Watchdog:
    """
    Watchdog timer for monitoring robotics system health.

    Usage:
        watchdog = Watchdog(config)
        watchdog.start()

        # In control loop
        while running:
            watchdog.kick("tier_r1")  # Reset timer
            result = tier_r1.step(sensors)
            watchdog.kick("tier_r1")  # Reset after completion

        watchdog.stop()

    Monitoring multiple sources:
        watchdog.register("sensor_vision", timeout_ms=50)
        watchdog.register("sensor_proprio", timeout_ms=20)
        watchdog.register("communication", timeout_ms=200)

        # On each update
        watchdog.kick("sensor_vision")
    """

    def __init__(
        self,
        config: Optional[WatchdogConfig] = None,
        on_timeout: Optional[Callable[[str, float], None]] = None,
        on_recovery: Optional[Callable[[str], None]] = None,
    ):
        self.config = config or WatchdogConfig()
        self._on_timeout = on_timeout
        self._on_recovery = on_recovery

        self._entries: Dict[str, WatchdogEntry] = {}
        self._state = WatchdogState.IDLE
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Statistics
        self._total_timeouts = 0
        self._last_timeout_time: Optional[float] = None

        # Register default tiers
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default monitored entries."""
        self.register("tier_r1", self.config.tier_r1_timeout_ms)
        self.register("tier_r2", self.config.tier_r2_timeout_ms)
        self.register("tier_r3", self.config.tier_r3_timeout_ms)
        self.register("heartbeat", self.config.heartbeat_timeout_ms)

    def register(
        self,
        name: str,
        timeout_ms: float,
        on_timeout: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Register a new entry to monitor.

        Args:
            name: Unique identifier for this entry
            timeout_ms: Timeout in milliseconds
            on_timeout: Optional callback on timeout
        """
        with self._lock:
            self._entries[name] = WatchdogEntry(
                name=name,
                timeout_ms=timeout_ms,
                last_kick_time=time.perf_counter(),
                on_timeout=on_timeout,
            )

    def unregister(self, name: str) -> None:
        """Remove an entry from monitoring."""
        with self._lock:
            self._entries.pop(name, None)

    def kick(self, name: str) -> None:
        """
        Reset the watchdog timer for an entry.

        Call this when the monitored component completes successfully.
        """
        with self._lock:
            if name in self._entries:
                entry = self._entries[name]
                old_count = entry.timeout_count
                entry.last_kick_time = time.perf_counter()
                entry.timeout_count = 0

                # Notify recovery if previously timed out
                if old_count > 0 and self._on_recovery:
                    self._on_recovery(name)

    def start(self) -> None:
        """Start the watchdog monitoring thread."""
        if self._state == WatchdogState.RUNNING:
            return

        self._stop_event.clear()
        self._state = WatchdogState.RUNNING
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the watchdog monitoring thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._state = WatchdogState.STOPPED

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in separate thread."""
        check_interval_s = self.config.check_interval_ms / 1000.0

        while not self._stop_event.is_set():
            self._check_timeouts()
            self._stop_event.wait(check_interval_s)

    def _check_timeouts(self) -> None:
        """Check all entries for timeouts."""
        current_time = time.perf_counter()

        with self._lock:
            for entry in self._entries.values():
                elapsed_ms = (current_time - entry.last_kick_time) * 1000.0

                if elapsed_ms > entry.timeout_ms:
                    self._handle_timeout(entry, elapsed_ms)

    def _handle_timeout(self, entry: WatchdogEntry, elapsed_ms: float) -> None:
        """Handle a timeout event."""
        entry.timeout_count += 1
        self._total_timeouts += 1
        self._last_timeout_time = time.perf_counter()
        self._state = WatchdogState.TRIGGERED

        # Call entry-specific callback
        if entry.on_timeout:
            try:
                entry.on_timeout()
            except Exception:
                pass  # Don't let callback errors crash watchdog

        # Call global callback
        if self._on_timeout:
            try:
                self._on_timeout(entry.name, elapsed_ms)
            except Exception:
                pass

    def is_healthy(self, name: Optional[str] = None) -> bool:
        """
        Check if monitored entry (or all entries) is healthy.

        Args:
            name: Specific entry to check, or None for all

        Returns:
            True if no timeouts, False otherwise
        """
        with self._lock:
            if name:
                entry = self._entries.get(name)
                return entry is not None and entry.timeout_count == 0
            else:
                return all(e.timeout_count == 0 for e in self._entries.values())

    def get_timeout_count(self, name: str) -> int:
        """Get consecutive timeout count for an entry."""
        with self._lock:
            entry = self._entries.get(name)
            return entry.timeout_count if entry else 0

    def get_elapsed_ms(self, name: str) -> float:
        """Get time elapsed since last kick for an entry."""
        with self._lock:
            entry = self._entries.get(name)
            if entry:
                return (time.perf_counter() - entry.last_kick_time) * 1000.0
            return float("inf")

    def get_status(self) -> Dict[str, Any]:
        """Get complete watchdog status."""
        with self._lock:
            return {
                "state": self._state.name,
                "total_timeouts": self._total_timeouts,
                "entries": {
                    name: {
                        "timeout_ms": entry.timeout_ms,
                        "elapsed_ms": (
                            time.perf_counter() - entry.last_kick_time
                        ) * 1000.0,
                        "timeout_count": entry.timeout_count,
                        "healthy": entry.timeout_count == 0,
                    }
                    for name, entry in self._entries.items()
                },
            }

    def raise_if_timeout(self, name: str) -> None:
        """
        Raise appropriate exception if entry has timed out.

        Use in control loop for explicit error handling.
        """
        with self._lock:
            entry = self._entries.get(name)
            if entry and entry.timeout_count > 0:
                elapsed = (time.perf_counter() - entry.last_kick_time) * 1000.0

                if name.startswith("tier_"):
                    raise TierTimeoutError(
                        tier_name=name,
                        actual_latency_ms=elapsed,
                        budget_ms=entry.timeout_ms,
                    )
                elif name.startswith("sensor_"):
                    raise SensorTimeoutError(
                        sensor_name=name,
                        timeout_ms=elapsed,
                    )
                else:
                    raise ConnectionLostError(
                        endpoint=name,
                        last_contact_ms=elapsed,
                    )


class TierWatchdog(Watchdog):
    """
    Specialized watchdog for tier latency monitoring.

    Automatically tracks tier execution time and triggers
    fallback on timeout.
    """

    def __init__(
        self,
        config: Optional[WatchdogConfig] = None,
        on_fallback: Optional[Callable[[str, str], None]] = None,
    ):
        super().__init__(config)
        self._on_fallback = on_fallback
        self._active_tier: Optional[str] = None
        self._tier_start_time: Optional[float] = None

    def start_tier(self, tier_name: str) -> None:
        """Mark start of tier execution."""
        self._active_tier = tier_name
        self._tier_start_time = time.perf_counter()

    def end_tier(self, tier_name: str) -> float:
        """
        Mark end of tier execution.

        Returns:
            Execution time in milliseconds
        """
        if self._tier_start_time is None:
            return 0.0

        elapsed_ms = (time.perf_counter() - self._tier_start_time) * 1000.0
        self.kick(tier_name)
        self._active_tier = None
        self._tier_start_time = None

        return elapsed_ms

    def check_tier_timeout(self) -> Optional[str]:
        """
        Check if active tier has exceeded timeout.

        Returns:
            Name of fallback tier if timeout, None otherwise
        """
        if self._active_tier is None or self._tier_start_time is None:
            return None

        elapsed_ms = (time.perf_counter() - self._tier_start_time) * 1000.0
        entry = self._entries.get(self._active_tier)

        if entry and elapsed_ms > entry.timeout_ms:
            # Determine fallback tier
            if self._active_tier == "tier_r3":
                fallback = "tier_r2"
            elif self._active_tier == "tier_r2":
                fallback = "tier_r1"
            else:
                fallback = None  # R1 has no fallback (E-stop)

            if self._on_fallback and fallback:
                self._on_fallback(self._active_tier, fallback)

            return fallback

        return None
