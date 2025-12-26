"""
Serial Adapter for Robotics
============================

Direct microcontroller communication via serial port.
"""

from typing import Optional, List
import struct
import time

from symbolu_robotics.adapters.base_adapter import BaseAdapter, AdapterConfig
from symbolu_robotics.core.types import SensorFrame, ActuatorCommand, JointState
import numpy as np


class SerialAdapter(BaseAdapter):
    """
    Adapter for direct serial communication with microcontrollers.

    Supports ESP32, Arduino, STM32, etc.
    """

    def __init__(
        self,
        config: Optional[AdapterConfig] = None,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 115200,
        num_joints: int = 6
    ):
        super().__init__(config)
        self.port = port
        self.baudrate = baudrate
        self.num_joints = num_joints

        self._serial = None
        self._buffer = bytearray()

    @property
    def adapter_name(self) -> str:
        return "serial"

    def connect(self) -> bool:
        """Open serial connection."""
        try:
            import serial
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.config.timeout_ms / 1000
            )
            time.sleep(0.5)  # Wait for Arduino reset
            self._connected = True
            return True

        except ImportError:
            print("pyserial not available. Running in mock mode.")
            self._init_mock()
            return True

        except Exception as e:
            print(f"Serial connection failed: {e}")
            return False

    def _init_mock(self) -> None:
        """Initialize mock for testing."""
        self._mock_positions = np.zeros(self.num_joints)
        self._mock_velocities = np.zeros(self.num_joints)
        self._connected = True

    def disconnect(self) -> None:
        """Close serial connection."""
        if self._serial:
            self._serial.close()
        self._connected = False

    def read_sensors(self) -> SensorFrame:
        """Read sensor data from microcontroller."""
        frame = SensorFrame()

        if self._serial and self._serial.is_open:
            # Send request
            self._serial.write(b'R')

            # Read response
            try:
                data = self._serial.read(self.num_joints * 4 * 2)  # positions + velocities
                if len(data) == self.num_joints * 4 * 2:
                    positions = struct.unpack(f'{self.num_joints}f', data[:self.num_joints * 4])
                    velocities = struct.unpack(f'{self.num_joints}f', data[self.num_joints * 4:])

                    frame.joints = JointState(
                        positions=np.array(positions),
                        velocities=np.array(velocities)
                    )
            except Exception as e:
                print(f"Serial read error: {e}")

        elif hasattr(self, '_mock_positions'):
            frame.joints = JointState(
                positions=self._mock_positions.copy(),
                velocities=self._mock_velocities.copy()
            )

        return frame

    def send_command(self, command: ActuatorCommand) -> bool:
        """Send command to microcontroller."""
        if command.emergency_stop:
            return self._send_estop()

        if self._serial and self._serial.is_open:
            try:
                if command.target_velocities is not None:
                    # Pack velocities
                    data = struct.pack(f'c{self.num_joints}f', b'V', *command.target_velocities)
                    self._serial.write(data)
                    return True

                elif command.target_positions is not None:
                    # Pack positions
                    data = struct.pack(f'c{self.num_joints}f', b'P', *command.target_positions)
                    self._serial.write(data)
                    return True

            except Exception as e:
                print(f"Serial write error: {e}")
                return False

        elif hasattr(self, '_mock_positions'):
            if command.target_velocities is not None:
                self._mock_velocities = command.target_velocities.copy()
                self._mock_positions += self._mock_velocities * 0.01
            return True

        return False

    def _send_estop(self) -> bool:
        """Send emergency stop."""
        if self._serial and self._serial.is_open:
            self._serial.write(b'E')
            return True
        elif hasattr(self, '_mock_velocities'):
            self._mock_velocities[:] = 0
            return True
        return False

    def send_raw(self, data: bytes) -> bool:
        """Send raw bytes."""
        if self._serial and self._serial.is_open:
            self._serial.write(data)
            return True
        return False

    def read_raw(self, size: int) -> bytes:
        """Read raw bytes."""
        if self._serial and self._serial.is_open:
            return self._serial.read(size)
        return b''

    @staticmethod
    def list_ports() -> List[str]:
        """List available serial ports."""
        try:
            import serial.tools.list_ports
            return [p.device for p in serial.tools.list_ports.comports()]
        except ImportError:
            return []
