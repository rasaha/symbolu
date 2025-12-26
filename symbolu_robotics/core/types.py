"""
Symbolu Robotics Core Types
===========================

Fundamental data types for the robotics module.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any
from enum import Enum, IntEnum
import numpy as np


class OntologicalLayer(IntEnum):
    """
    12 ontological layers for robotics (patent-exact sequence).

    Each layer maps to a specific aspect of robotic cognition and control.
    """
    O1_POTENTIAL = 0    # Sensor readiness
    O2_IDENTITY = 1     # Localization (x, y, theta)
    O3_EXECUTION = 2    # Motor commands
    O4_STRUCTURE = 3    # Body schema/kinematics
    O5_COGNITION = 4    # Perception processing
    O6_AGENCY = 5       # Control mode/autonomy level
    O7_REASONING = 6    # Path/task planning
    O8_PURPOSE = 7      # Goal hierarchy
    O9_WITNESSES = 8    # World model/scene
    O10_UNIFYING = 9    # Multi-agent coordination
    O11_INTEGRATION = 10  # Sensor fusion
    O12_ABSOLVING = 11   # Safety constraints


class SafetyLevel(Enum):
    """Safety constraint levels."""
    NOMINAL = "nominal"           # Normal operation
    CAUTION = "caution"           # Reduced speed
    RESTRICTED = "restricted"     # Minimal movement
    EMERGENCY_STOP = "emergency"  # Full stop


class ControlMode(Enum):
    """Robot control modes."""
    IDLE = "idle"
    TELEOPERATION = "teleoperation"
    SEMI_AUTONOMOUS = "semi_autonomous"
    FULLY_AUTONOMOUS = "fully_autonomous"


# Type alias for 12D layer vector
Layer12D = np.ndarray  # Shape: (12,)


@dataclass
class RobotPose:
    """
    Robot pose in 3D space.

    Attributes:
        x: X position (meters)
        y: Y position (meters)
        z: Z position (meters)
        roll: Roll angle (radians)
        pitch: Pitch angle (radians)
        yaw: Yaw angle (radians)
    """
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

    def to_array(self) -> np.ndarray:
        """Convert to numpy array [x, y, z, roll, pitch, yaw]."""
        return np.array([self.x, self.y, self.z, self.roll, self.pitch, self.yaw])

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "RobotPose":
        """Create from numpy array."""
        return cls(x=arr[0], y=arr[1], z=arr[2],
                   roll=arr[3], pitch=arr[4], yaw=arr[5])

    def distance_to(self, other: "RobotPose") -> float:
        """Euclidean distance to another pose."""
        return np.sqrt((self.x - other.x)**2 +
                       (self.y - other.y)**2 +
                       (self.z - other.z)**2)


@dataclass
class JointState:
    """
    Joint state for a robotic system.

    Attributes:
        positions: Joint positions (radians or meters)
        velocities: Joint velocities (rad/s or m/s)
        efforts: Joint efforts/torques (Nm or N)
        names: Joint names
    """
    positions: np.ndarray = field(default_factory=lambda: np.zeros(6))
    velocities: np.ndarray = field(default_factory=lambda: np.zeros(6))
    efforts: np.ndarray = field(default_factory=lambda: np.zeros(6))
    names: Tuple[str, ...] = field(default_factory=lambda: tuple(f"joint_{i}" for i in range(6)))

    @property
    def num_joints(self) -> int:
        """Number of joints."""
        return len(self.positions)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "positions": self.positions.tolist(),
            "velocities": self.velocities.tolist(),
            "efforts": self.efforts.tolist(),
            "names": list(self.names),
        }


@dataclass
class SensorFrame:
    """
    Complete sensor data frame at a single timestamp.

    Contains all sensor modalities available to the robot.
    """
    # Timestamp
    timestamp: float = 0.0

    # Proprioception
    joints: Optional[JointState] = None
    base_pose: Optional[RobotPose] = None

    # Vision
    rgb_image: Optional[np.ndarray] = None      # Shape: (H, W, 3)
    depth_image: Optional[np.ndarray] = None    # Shape: (H, W)

    # LIDAR
    lidar_points: Optional[np.ndarray] = None   # Shape: (N, 3)
    lidar_ranges: Optional[np.ndarray] = None   # Shape: (N,)

    # Tactile
    contact_forces: Optional[np.ndarray] = None # Shape: (num_contacts, 3)
    contact_points: Optional[np.ndarray] = None # Shape: (num_contacts, 3)

    # Audio
    audio_buffer: Optional[np.ndarray] = None   # Shape: (samples,)
    audio_sample_rate: int = 16000

    # IMU
    linear_acceleration: Optional[np.ndarray] = None  # Shape: (3,)
    angular_velocity: Optional[np.ndarray] = None     # Shape: (3,)

    # Proximity
    proximity_distances: Optional[np.ndarray] = None  # Shape: (num_sensors,)
    human_detected: bool = False
    human_distance: Optional[float] = None

    def has_vision(self) -> bool:
        """Check if vision data is available."""
        return self.rgb_image is not None or self.depth_image is not None

    def has_lidar(self) -> bool:
        """Check if LIDAR data is available."""
        return self.lidar_points is not None or self.lidar_ranges is not None

    def has_proprioception(self) -> bool:
        """Check if proprioception data is available."""
        return self.joints is not None

    def has_tactile(self) -> bool:
        """Check if tactile data is available."""
        return self.contact_forces is not None


@dataclass
class ActuatorCommand:
    """
    Command to robot actuators.

    Can represent different control modes:
    - Position control: target_positions
    - Velocity control: target_velocities
    - Torque control: target_efforts
    - Gripper control: gripper_command
    """
    # Timestamp
    timestamp: float = 0.0

    # Joint commands (one of these should be set)
    target_positions: Optional[np.ndarray] = None   # Radians/meters
    target_velocities: Optional[np.ndarray] = None  # Rad/s or m/s
    target_efforts: Optional[np.ndarray] = None     # Nm or N

    # Gripper command
    gripper_position: Optional[float] = None  # 0.0 (closed) to 1.0 (open)
    gripper_force: Optional[float] = None     # Force limit

    # Base commands (for mobile robots)
    base_linear_velocity: Optional[np.ndarray] = None   # [vx, vy, vz]
    base_angular_velocity: Optional[np.ndarray] = None  # [wx, wy, wz]

    # Control mode
    control_mode: str = "position"  # "position", "velocity", "effort"

    # Safety flags
    emergency_stop: bool = False
    safety_limited: bool = False

    @classmethod
    def stop(cls) -> "ActuatorCommand":
        """Create an emergency stop command."""
        return cls(emergency_stop=True)

    @classmethod
    def zero_velocity(cls, num_joints: int = 6) -> "ActuatorCommand":
        """Create a zero velocity command."""
        return cls(
            target_velocities=np.zeros(num_joints),
            control_mode="velocity"
        )

    def is_safe(self) -> bool:
        """Check if command is within safe limits."""
        if self.emergency_stop:
            return True  # E-stop is always safe

        # Check velocity limits
        if self.target_velocities is not None:
            if np.any(np.abs(self.target_velocities) > 3.0):  # rad/s limit
                return False

        # Check effort limits
        if self.target_efforts is not None:
            if np.any(np.abs(self.target_efforts) > 100.0):  # Nm limit
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "timestamp": self.timestamp,
            "control_mode": self.control_mode,
            "emergency_stop": self.emergency_stop,
            "safety_limited": self.safety_limited,
        }
        if self.target_positions is not None:
            result["target_positions"] = self.target_positions.tolist()
        if self.target_velocities is not None:
            result["target_velocities"] = self.target_velocities.tolist()
        if self.target_efforts is not None:
            result["target_efforts"] = self.target_efforts.tolist()
        if self.gripper_position is not None:
            result["gripper_position"] = self.gripper_position
        return result


@dataclass
class Goal:
    """
    Goal specification for task planning.

    Goals are hierarchical and map to O8_PURPOSE.
    """
    description: str
    target_pose: Optional[RobotPose] = None
    target_joints: Optional[np.ndarray] = None
    priority: float = 1.0
    timeout: float = 60.0  # seconds
    parent_goal: Optional["Goal"] = None
    subgoals: List["Goal"] = field(default_factory=list)

    def is_atomic(self) -> bool:
        """Check if goal has no subgoals."""
        return len(self.subgoals) == 0


@dataclass
class Plan:
    """
    Action plan generated by the deliberative tier.
    """
    actions: List[ActuatorCommand] = field(default_factory=list)
    goals: List[Goal] = field(default_factory=list)
    estimated_duration: float = 0.0
    success_probability: float = 1.0

    def is_empty(self) -> bool:
        """Check if plan has no actions."""
        return len(self.actions) == 0
