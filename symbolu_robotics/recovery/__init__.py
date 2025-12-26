# Symbolu Robotics - Recovery Module
"""
Error recovery and fault tolerance for robotics systems.

Components:
- Watchdog: Communication and heartbeat monitoring
- TierFallback: Automatic tier degradation on failure
- SensorRecovery: Sensor failure handling and graceful degradation

Usage:
    from symbolu_robotics.recovery import (
        Watchdog,
        TierFallbackManager,
        SensorRecoveryHandler,
    )
"""

from symbolu_robotics.recovery.watchdog import Watchdog, WatchdogConfig
from symbolu_robotics.recovery.fallback import TierFallbackManager, FallbackConfig
from symbolu_robotics.recovery.sensor_recovery import SensorRecoveryHandler

__all__ = [
    "Watchdog",
    "WatchdogConfig",
    "TierFallbackManager",
    "FallbackConfig",
    "SensorRecoveryHandler",
]
