"""
MuJoCo Adapter for Robotics
============================

Integration with MuJoCo physics simulation.
"""

from typing import Optional
import numpy as np

from symbolu_robotics.adapters.base_adapter import BaseAdapter, AdapterConfig
from symbolu_robotics.core.types import SensorFrame, ActuatorCommand, JointState, RobotPose


class MuJoCoAdapter(BaseAdapter):
    """
    Adapter for MuJoCo simulation.

    Provides physics-based simulation for robotics development.
    """

    def __init__(
        self,
        config: Optional[AdapterConfig] = None,
        model_path: Optional[str] = None,
        model_xml: Optional[str] = None
    ):
        super().__init__(config)
        self.model_path = model_path
        self.model_xml = model_xml

        self._model = None
        self._data = None
        self._viewer = None

    @property
    def adapter_name(self) -> str:
        return "mujoco"

    def connect(self) -> bool:
        """Load MuJoCo model."""
        try:
            import mujoco

            if self.model_path:
                self._model = mujoco.MjModel.from_xml_path(self.model_path)
            elif self.model_xml:
                self._model = mujoco.MjModel.from_xml_string(self.model_xml)
            else:
                # Create simple default model
                self._model = mujoco.MjModel.from_xml_string(self._default_model())

            self._data = mujoco.MjData(self._model)
            self._connected = True
            return True

        except ImportError:
            print("MuJoCo not available. Running in mock mode.")
            self._init_mock()
            return True

        except Exception as e:
            print(f"MuJoCo connection failed: {e}")
            return False

    def _default_model(self) -> str:
        """Default 6-DOF arm model."""
        return """
        <mujoco>
          <worldbody>
            <body name="link0" pos="0 0 0">
              <joint name="joint0" type="hinge" axis="0 0 1"/>
              <geom type="cylinder" size="0.05 0.1"/>
              <body name="link1" pos="0 0 0.2">
                <joint name="joint1" type="hinge" axis="0 1 0"/>
                <geom type="cylinder" size="0.04 0.15"/>
                <body name="link2" pos="0 0 0.3">
                  <joint name="joint2" type="hinge" axis="0 1 0"/>
                  <geom type="cylinder" size="0.03 0.12"/>
                </body>
              </body>
            </body>
          </worldbody>
          <actuator>
            <motor joint="joint0" gear="100"/>
            <motor joint="joint1" gear="100"/>
            <motor joint="joint2" gear="100"/>
          </actuator>
        </mujoco>
        """

    def _init_mock(self) -> None:
        """Initialize mock for testing without MuJoCo."""
        self._mock_qpos = np.zeros(6)
        self._mock_qvel = np.zeros(6)
        self._connected = True

    def disconnect(self) -> None:
        """Close MuJoCo simulation."""
        if self._viewer:
            self._viewer.close()
        self._model = None
        self._data = None
        self._connected = False

    def read_sensors(self) -> SensorFrame:
        """Read sensor data from MuJoCo."""
        frame = SensorFrame()

        if self._data:
            frame.joints = JointState(
                positions=self._data.qpos.copy(),
                velocities=self._data.qvel.copy(),
                efforts=self._data.ctrl.copy() if len(self._data.ctrl) > 0 else np.zeros(len(self._data.qpos))
            )

            # Base pose (first 7 elements if floating base)
            if len(self._data.qpos) >= 7:
                frame.base_pose = RobotPose(
                    x=self._data.qpos[0],
                    y=self._data.qpos[1],
                    z=self._data.qpos[2]
                )

            # Contact forces
            if self._data.ncon > 0:
                frame.contact_forces = np.array([
                    self._data.contact[i].frame[:3]
                    for i in range(self._data.ncon)
                ])

        elif hasattr(self, '_mock_qpos'):
            frame.joints = JointState(
                positions=self._mock_qpos.copy(),
                velocities=self._mock_qvel.copy()
            )

        return frame

    def send_command(self, command: ActuatorCommand) -> bool:
        """Send command to MuJoCo simulation."""
        if command.emergency_stop:
            if self._data:
                self._data.ctrl[:] = 0
            elif hasattr(self, '_mock_qvel'):
                self._mock_qvel[:] = 0
            return True

        if self._data:
            if command.target_efforts is not None:
                self._data.ctrl[:len(command.target_efforts)] = command.target_efforts
            elif command.target_velocities is not None:
                # Simple velocity control via effort
                kv = 10.0
                self._data.ctrl[:len(command.target_velocities)] = (
                    kv * (command.target_velocities - self._data.qvel[:len(command.target_velocities)])
                )
            return True

        elif hasattr(self, '_mock_qpos'):
            if command.target_velocities is not None:
                self._mock_qvel = command.target_velocities.copy()
            return True

        return False

    def step(self, command: ActuatorCommand = None) -> SensorFrame:
        """Step simulation forward."""
        if command:
            self.send_command(command)

        if self._model and self._data:
            import mujoco
            mujoco.mj_step(self._model, self._data)

        elif hasattr(self, '_mock_qpos'):
            # Mock integration
            self._mock_qpos += self._mock_qvel * 0.01

        return self.read_sensors()

    def render(self) -> None:
        """Render simulation."""
        if self._model and self._data:
            try:
                import mujoco.viewer
                if self._viewer is None:
                    self._viewer = mujoco.viewer.launch_passive(
                        self._model, self._data
                    )
                self._viewer.sync()
            except ImportError:
                pass

    def get_model(self):
        """Get MuJoCo model."""
        return self._model

    def get_data(self):
        """Get MuJoCo data."""
        return self._data
