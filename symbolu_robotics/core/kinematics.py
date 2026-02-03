"""
Forward Kinematics Module
=========================

DH parameter-based forward kinematics for robot manipulators.

Implementation: Pure numpy using Denavit-Hartenberg convention
No external robotics libraries required (roboticstoolbox, pinocchio, etc.)

Supports:
- Forward kinematics (joint angles -> end-effector pose)
- Jacobian computation (for velocity mapping)
- Common robot configurations (UR5, Panda, generic 6-DOF)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class JointType(Enum):
    """Type of robot joint."""
    REVOLUTE = "revolute"
    PRISMATIC = "prismatic"
    FIXED = "fixed"


@dataclass
class DHParams:
    """
    Denavit-Hartenberg parameters for one joint.

    Standard DH convention:
    - a (link length): distance along x_{i} from z_{i-1} to z_{i}
    - alpha (link twist): angle about x_{i} from z_{i-1} to z_{i}
    - d (link offset): distance along z_{i-1} from x_{i-1} to x_{i}
    - theta (joint angle): angle about z_{i-1} from x_{i-1} to x_{i}

    For revolute joints: theta is variable
    For prismatic joints: d is variable
    """
    a: float = 0.0          # Link length (meters)
    alpha: float = 0.0      # Link twist (radians)
    d: float = 0.0          # Link offset (meters)
    theta: float = 0.0      # Joint angle offset (radians)
    joint_type: JointType = JointType.REVOLUTE

    # Joint limits
    lower_limit: float = -np.pi
    upper_limit: float = np.pi


@dataclass
class RobotPose:
    """Robot end-effector pose."""
    position: np.ndarray  # (x, y, z)
    rotation: np.ndarray  # 3x3 rotation matrix
    quaternion: Optional[np.ndarray] = None  # (w, x, y, z)

    @classmethod
    def from_transform(cls, T: np.ndarray) -> 'RobotPose':
        """Create pose from 4x4 homogeneous transform."""
        position = T[:3, 3]
        rotation = T[:3, :3]
        quaternion = cls._rotation_to_quaternion(rotation)
        return cls(position=position, rotation=rotation, quaternion=quaternion)

    @staticmethod
    def _rotation_to_quaternion(R: np.ndarray) -> np.ndarray:
        """Convert 3x3 rotation matrix to quaternion (w, x, y, z)."""
        trace = np.trace(R)
        if trace > 0:
            s = 0.5 / np.sqrt(trace + 1.0)
            w = 0.25 / s
            x = (R[2, 1] - R[1, 2]) * s
            y = (R[0, 2] - R[2, 0]) * s
            z = (R[1, 0] - R[0, 1]) * s
        elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
            s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
            w = (R[2, 1] - R[1, 2]) / s
            x = 0.25 * s
            y = (R[0, 1] + R[1, 0]) / s
            z = (R[0, 2] + R[2, 0]) / s
        elif R[1, 1] > R[2, 2]:
            s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
            w = (R[0, 2] - R[2, 0]) / s
            x = (R[0, 1] + R[1, 0]) / s
            y = 0.25 * s
            z = (R[1, 2] + R[2, 1]) / s
        else:
            s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
            w = (R[1, 0] - R[0, 1]) / s
            x = (R[0, 2] + R[2, 0]) / s
            y = (R[1, 2] + R[2, 1]) / s
            z = 0.25 * s
        return np.array([w, x, y, z])


class ForwardKinematics:
    """
    Forward kinematics using DH parameters.

    Computes end-effector pose from joint angles using the
    Denavit-Hartenberg convention.
    """

    def __init__(self, dh_params: List[DHParams], name: str = "robot"):
        """
        Initialize with DH parameters.

        Args:
            dh_params: List of DH parameters, one per joint
            name: Robot name for logging
        """
        self.dh_params = dh_params
        self.n_joints = len(dh_params)
        self.name = name

        logger.info(f"ForwardKinematics initialized for '{name}' with {self.n_joints} joints")

    def forward(self, joint_values: np.ndarray) -> RobotPose:
        """
        Compute end-effector pose from joint values.

        Args:
            joint_values: Array of joint values (angles for revolute, offsets for prismatic)

        Returns:
            End-effector pose
        """
        if len(joint_values) != self.n_joints:
            raise ValueError(f"Expected {self.n_joints} joints, got {len(joint_values)}")

        T = self.forward_transform(joint_values)
        return RobotPose.from_transform(T)

    def forward_transform(self, joint_values: np.ndarray) -> np.ndarray:
        """
        Compute 4x4 homogeneous transform to end-effector.

        Args:
            joint_values: Array of joint values

        Returns:
            4x4 homogeneous transformation matrix
        """
        T = np.eye(4)

        for i, (dh, q) in enumerate(zip(self.dh_params, joint_values)):
            # Apply joint value based on joint type
            if dh.joint_type == JointType.REVOLUTE:
                theta = dh.theta + q
                d = dh.d
            elif dh.joint_type == JointType.PRISMATIC:
                theta = dh.theta
                d = dh.d + q
            else:  # FIXED
                theta = dh.theta
                d = dh.d

            # Compute DH transformation matrix
            T_i = self._dh_matrix(dh.a, dh.alpha, d, theta)
            T = T @ T_i

        return T

    def _dh_matrix(self, a: float, alpha: float, d: float, theta: float) -> np.ndarray:
        """
        Compute DH transformation matrix.

        T = Rz(theta) * Tz(d) * Tx(a) * Rx(alpha)
        """
        ct = np.cos(theta)
        st = np.sin(theta)
        ca = np.cos(alpha)
        sa = np.sin(alpha)

        return np.array([
            [ct, -st * ca,  st * sa, a * ct],
            [st,  ct * ca, -ct * sa, a * st],
            [0,   sa,       ca,      d     ],
            [0,   0,        0,       1     ],
        ])

    def get_all_transforms(self, joint_values: np.ndarray) -> List[np.ndarray]:
        """
        Get transforms for all joints (useful for visualization/Jacobian).

        Returns:
            List of 4x4 transforms, one for each joint frame
        """
        transforms = [np.eye(4)]  # Base frame
        T = np.eye(4)

        for i, (dh, q) in enumerate(zip(self.dh_params, joint_values)):
            if dh.joint_type == JointType.REVOLUTE:
                theta = dh.theta + q
                d = dh.d
            elif dh.joint_type == JointType.PRISMATIC:
                theta = dh.theta
                d = dh.d + q
            else:
                theta = dh.theta
                d = dh.d

            T_i = self._dh_matrix(dh.a, dh.alpha, d, theta)
            T = T @ T_i
            transforms.append(T.copy())

        return transforms

    def jacobian(self, joint_values: np.ndarray) -> np.ndarray:
        """
        Compute geometric Jacobian at given configuration.

        The Jacobian maps joint velocities to end-effector velocities:
        [v; w] = J @ q_dot

        Returns:
            6 x n_joints Jacobian matrix [linear (3); angular (3)]
        """
        J = np.zeros((6, self.n_joints))

        # Get all transforms
        transforms = self.get_all_transforms(joint_values)

        # End-effector position
        T_ee = transforms[-1]
        p_ee = T_ee[:3, 3]

        for i in range(self.n_joints):
            # z-axis of frame i (before joint i)
            T_i = transforms[i]
            z_i = T_i[:3, 2]  # Third column of rotation matrix
            p_i = T_i[:3, 3]  # Position of frame i

            dh = self.dh_params[i]

            if dh.joint_type == JointType.REVOLUTE:
                # Revolute joint
                # Linear velocity: z_i x (p_ee - p_i)
                J[:3, i] = np.cross(z_i, p_ee - p_i)
                # Angular velocity: z_i
                J[3:, i] = z_i

            elif dh.joint_type == JointType.PRISMATIC:
                # Prismatic joint
                # Linear velocity: z_i
                J[:3, i] = z_i
                # Angular velocity: 0
                J[3:, i] = 0

            # Fixed joints contribute nothing
            # (already zero-initialized)

        return J

    def check_limits(self, joint_values: np.ndarray) -> Tuple[bool, List[int]]:
        """
        Check if joint values are within limits.

        Returns:
            (all_valid, list_of_violated_joint_indices)
        """
        violations = []
        for i, (dh, q) in enumerate(zip(self.dh_params, joint_values)):
            if dh.joint_type != JointType.FIXED:
                if q < dh.lower_limit or q > dh.upper_limit:
                    violations.append(i)

        return len(violations) == 0, violations


# ============================================================================
# Common Robot Configurations
# ============================================================================

def create_ur5_kinematics() -> ForwardKinematics:
    """Create forward kinematics for UR5 robot."""
    # UR5 DH parameters (standard convention)
    dh_params = [
        DHParams(a=0.0,      alpha=np.pi/2,  d=0.089159, theta=0, lower_limit=-2*np.pi, upper_limit=2*np.pi),
        DHParams(a=-0.425,   alpha=0,        d=0,        theta=0, lower_limit=-2*np.pi, upper_limit=2*np.pi),
        DHParams(a=-0.39225, alpha=0,        d=0,        theta=0, lower_limit=-np.pi, upper_limit=np.pi),
        DHParams(a=0.0,      alpha=np.pi/2,  d=0.10915,  theta=0, lower_limit=-2*np.pi, upper_limit=2*np.pi),
        DHParams(a=0.0,      alpha=-np.pi/2, d=0.09465,  theta=0, lower_limit=-2*np.pi, upper_limit=2*np.pi),
        DHParams(a=0.0,      alpha=0,        d=0.0823,   theta=0, lower_limit=-2*np.pi, upper_limit=2*np.pi),
    ]
    return ForwardKinematics(dh_params, name="UR5")


def create_panda_kinematics() -> ForwardKinematics:
    """Create forward kinematics for Franka Emika Panda robot."""
    # Panda DH parameters (modified DH convention adapted to standard)
    dh_params = [
        DHParams(a=0,      alpha=0,        d=0.333,  theta=0, lower_limit=-2.8973, upper_limit=2.8973),
        DHParams(a=0,      alpha=-np.pi/2, d=0,      theta=0, lower_limit=-1.7628, upper_limit=1.7628),
        DHParams(a=0,      alpha=np.pi/2,  d=0.316,  theta=0, lower_limit=-2.8973, upper_limit=2.8973),
        DHParams(a=0.0825, alpha=np.pi/2,  d=0,      theta=0, lower_limit=-3.0718, upper_limit=-0.0698),
        DHParams(a=-0.0825,alpha=-np.pi/2, d=0.384,  theta=0, lower_limit=-2.8973, upper_limit=2.8973),
        DHParams(a=0,      alpha=np.pi/2,  d=0,      theta=0, lower_limit=-0.0175, upper_limit=3.7525),
        DHParams(a=0.088,  alpha=np.pi/2,  d=0.107,  theta=0, lower_limit=-2.8973, upper_limit=2.8973),
    ]
    return ForwardKinematics(dh_params, name="Panda")


def create_generic_6dof_kinematics(
    link_lengths: List[float] = None,
) -> ForwardKinematics:
    """
    Create forward kinematics for generic 6-DOF robot.

    Args:
        link_lengths: List of 4 link lengths [l1, l2, l3, l4]
                     Defaults to [0.3, 0.3, 0.2, 0.1]
    """
    if link_lengths is None:
        link_lengths = [0.3, 0.3, 0.2, 0.1]

    l1, l2, l3, l4 = link_lengths

    dh_params = [
        DHParams(a=0,  alpha=np.pi/2, d=l1, theta=0),  # Base rotation
        DHParams(a=l2, alpha=0,       d=0,  theta=0),  # Shoulder
        DHParams(a=l3, alpha=0,       d=0,  theta=0),  # Elbow
        DHParams(a=0,  alpha=np.pi/2, d=0,  theta=0),  # Wrist 1
        DHParams(a=0,  alpha=-np.pi/2,d=0,  theta=0),  # Wrist 2
        DHParams(a=0,  alpha=0,       d=l4, theta=0),  # Wrist 3
    ]
    return ForwardKinematics(dh_params, name="Generic6DOF")


# ============================================================================
# Iterative Inverse Kinematics (Jacobian-based)
# ============================================================================

class InverseKinematics:
    """
    Iterative inverse kinematics using Jacobian transpose/pseudoinverse.

    This is a simple iterative solver - not guaranteed to find solution
    for all configurations, but works for many practical cases.
    """

    def __init__(
        self,
        fk: ForwardKinematics,
        max_iterations: int = 100,
        position_tolerance: float = 1e-4,
        orientation_tolerance: float = 1e-3,
        step_size: float = 0.1,
    ):
        self.fk = fk
        self.max_iterations = max_iterations
        self.position_tolerance = position_tolerance
        self.orientation_tolerance = orientation_tolerance
        self.step_size = step_size

    def solve(
        self,
        target_position: np.ndarray,
        target_orientation: Optional[np.ndarray] = None,
        initial_guess: Optional[np.ndarray] = None,
    ) -> Tuple[Optional[np.ndarray], bool, int]:
        """
        Solve inverse kinematics.

        Args:
            target_position: Target (x, y, z) position
            target_orientation: Target 3x3 rotation matrix (optional)
            initial_guess: Initial joint configuration

        Returns:
            (joint_values, success, iterations)
        """
        # Initial guess
        if initial_guess is None:
            q = np.zeros(self.fk.n_joints)
        else:
            q = initial_guess.copy()

        for iteration in range(self.max_iterations):
            # Current pose
            pose = self.fk.forward(q)
            current_pos = pose.position
            current_rot = pose.rotation

            # Position error
            pos_error = target_position - current_pos

            # Orientation error (if specified)
            if target_orientation is not None:
                # Rotation error as axis-angle
                R_error = target_orientation @ current_rot.T
                angle = np.arccos(np.clip((np.trace(R_error) - 1) / 2, -1, 1))
                if angle > 1e-6:
                    axis = np.array([
                        R_error[2, 1] - R_error[1, 2],
                        R_error[0, 2] - R_error[2, 0],
                        R_error[1, 0] - R_error[0, 1],
                    ]) / (2 * np.sin(angle))
                    ori_error = angle * axis
                else:
                    ori_error = np.zeros(3)

                error = np.concatenate([pos_error, ori_error])
            else:
                error = pos_error

            # Check convergence
            pos_norm = np.linalg.norm(pos_error)
            if target_orientation is not None:
                ori_norm = np.linalg.norm(ori_error)
                converged = pos_norm < self.position_tolerance and ori_norm < self.orientation_tolerance
            else:
                converged = pos_norm < self.position_tolerance

            if converged:
                return q, True, iteration

            # Compute Jacobian
            J = self.fk.jacobian(q)
            if target_orientation is None:
                J = J[:3, :]  # Only position rows

            # Jacobian pseudoinverse (damped least squares for stability)
            damping = 0.01
            JJT = J @ J.T + damping * np.eye(J.shape[0])
            J_pinv = J.T @ np.linalg.inv(JJT)

            # Update joints
            dq = self.step_size * J_pinv @ error

            # Apply update with clamping
            q = q + dq

            # Clamp to joint limits
            for i, dh in enumerate(self.fk.dh_params):
                q[i] = np.clip(q[i], dh.lower_limit, dh.upper_limit)

        # Did not converge
        return q, False, self.max_iterations
