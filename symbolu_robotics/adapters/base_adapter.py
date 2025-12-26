"""
Base Adapter for Robotics
==========================

Abstract base class for hardware adapters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from symbolu_robotics.core.types import SensorFrame, ActuatorCommand


@dataclass
class AdapterConfig:
    """Configuration for hardware adapters."""
    update_rate_hz: float = 100.0
    timeout_ms: float = 100.0
    auto_reconnect: bool = True


class BaseAdapter(ABC):
    """
    Abstract base class for hardware adapters.

    Adapters bridge between Symbolu Robotics and hardware platforms.
    """

    def __init__(self, config: Optional[AdapterConfig] = None):
        self.config = config or AdapterConfig()
        self._connected = False

    @property
    @abstractmethod
    def adapter_name(self) -> str:
        """Return adapter name."""
        pass

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to hardware.

        Returns:
            True if connection successful
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from hardware."""
        pass

    @abstractmethod
    def read_sensors(self) -> SensorFrame:
        """
        Read sensor data from hardware.

        Returns:
            SensorFrame with current sensor data
        """
        pass

    @abstractmethod
    def send_command(self, command: ActuatorCommand) -> bool:
        """
        Send actuator command to hardware.

        Args:
            command: ActuatorCommand to send

        Returns:
            True if command sent successfully
        """
        pass

    def step(self, command: ActuatorCommand) -> SensorFrame:
        """
        Execute one control step.

        Sends command and reads sensors.
        """
        self.send_command(command)
        return self.read_sensors()

    def emergency_stop(self) -> bool:
        """Send emergency stop command."""
        return self.send_command(ActuatorCommand(emergency_stop=True))
