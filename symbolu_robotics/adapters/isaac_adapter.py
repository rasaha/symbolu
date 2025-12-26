"""
NVIDIA Isaac Sim Adapter for Robotics
======================================

Integration with NVIDIA Isaac Sim.

Note: Requires Isaac Sim to be installed.
"""

from typing import Optional
import numpy as np

from symbolu_robotics.adapters.base_adapter import BaseAdapter, AdapterConfig
from symbolu_robotics.core.types import SensorFrame, ActuatorCommand, JointState, RobotPose


class IsaacAdapter(BaseAdapter):
    """
    Adapter for NVIDIA Isaac Sim.

    Provides integration with Isaac Sim's physics and rendering.
    """

    def __init__(
        self,
        config: Optional[AdapterConfig] = None,
        usd_path: Optional[str] = None,
        robot_prim_path: str = "/World/Robot"
    ):
        super().__init__(config)
        self.usd_path = usd_path
        self.robot_prim_path = robot_prim_path

        self._simulation = None
        self._robot = None
        self._dc = None  # Dynamic control interface

    @property
    def adapter_name(self) -> str:
        return "isaac"

    def connect(self) -> bool:
        """
        Initialize Isaac Sim connection.

        Note: Isaac Sim must be running.
        """
        try:
            # Try to import Isaac Sim modules
            from omni.isaac.core import World
            from omni.isaac.core.robots import Robot
            from omni.isaac.core.utils.stage import add_reference_to_stage

            # Create world
            self._simulation = World(stage_units_in_meters=1.0)

            # Load robot if USD path provided
            if self.usd_path:
                add_reference_to_stage(
                    usd_path=self.usd_path,
                    prim_path=self.robot_prim_path
                )

            # Get robot
            self._robot = Robot(prim_path=self.robot_prim_path)
            self._simulation.scene.add(self._robot)

            # Initialize
            self._simulation.reset()

            self._connected = True
            return True

        except ImportError:
            print("Isaac Sim not available. Running in simulation mode.")
            self._init_mock()
            return True

        except Exception as e:
            print(f"Isaac Sim connection failed: {e}")
            return False

    def _init_mock(self) -> None:
        """Initialize mock simulation for testing."""
        self._mock_joints = np.zeros(6)
        self._mock_velocities = np.zeros(6)
        self._mock_pose = RobotPose()
        self._connected = True

    def disconnect(self) -> None:
        """Close Isaac Sim connection."""
        if self._simulation:
            try:
                self._simulation.stop()
            except:
                pass
        self._connected = False

    def read_sensors(self) -> SensorFrame:
        """Read sensors from Isaac Sim."""
        frame = SensorFrame()

        if self._robot:
            try:
                # Get joint states
                positions = self._robot.get_joint_positions()
                velocities = self._robot.get_joint_velocities()

                frame.joints = JointState(
                    positions=np.array(positions),
                    velocities=np.array(velocities)
                )

                # Get world pose
                position, orientation = self._robot.get_world_pose()
                frame.base_pose = RobotPose(
                    x=position[0],
                    y=position[1],
                    z=position[2]
                )

            except Exception as e:
                print(f"Isaac sensor read error: {e}")

        elif hasattr(self, '_mock_joints'):
            # Mock mode
            frame.joints = JointState(
                positions=self._mock_joints.copy(),
                velocities=self._mock_velocities.copy()
            )
            frame.base_pose = self._mock_pose

        return frame

    def send_command(self, command: ActuatorCommand) -> bool:
        """Send command to Isaac Sim robot."""
        if command.emergency_stop:
            if self._robot:
                self._robot.set_joint_velocities(np.zeros(6))
            elif hasattr(self, '_mock_velocities'):
                self._mock_velocities = np.zeros(6)
            return True

        if self._robot:
            try:
                if command.target_positions is not None:
                    self._robot.set_joint_position_targets(command.target_positions)
                if command.target_velocities is not None:
                    self._robot.set_joint_velocity_targets(command.target_velocities)
                return True
            except Exception as e:
                print(f"Isaac command error: {e}")
                return False

        elif hasattr(self, '_mock_joints'):
            # Mock mode: simple integration
            if command.target_velocities is not None:
                self._mock_velocities = command.target_velocities
                self._mock_joints += command.target_velocities * 0.01
            return True

        return False

    def step_simulation(self, dt: float = 1.0 / 60.0) -> None:
        """Step the physics simulation."""
        if self._simulation:
            self._simulation.step(render=True)
        elif hasattr(self, '_mock_joints'):
            # Mock step
            self._mock_joints += self._mock_velocities * dt
