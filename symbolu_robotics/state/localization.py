"""
Localization for Robotics
==========================

O2_IDENTITY: Where am I?

Position estimation using various methods.
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple
from enum import Enum
import numpy as np

from symbolu_robotics.core.types import RobotPose


class LocalizationMethod(Enum):
    """Localization method types."""
    ODOMETRY = "odometry"
    LIDAR_SLAM = "lidar_slam"
    VISUAL_SLAM = "visual_slam"
    GPS = "gps"
    BEACON = "beacon"
    FUSION = "fusion"


@dataclass
class LocalizationResult:
    """Result of localization."""
    pose: RobotPose
    confidence: float = 1.0
    method: LocalizationMethod = LocalizationMethod.ODOMETRY
    covariance: Optional[np.ndarray] = None


class Localization:
    """
    Robot localization system.

    Estimates robot pose in world frame.
    """

    def __init__(
        self,
        method: LocalizationMethod = LocalizationMethod.ODOMETRY,
        initial_pose: Optional[RobotPose] = None
    ):
        self.method = method
        self._pose = initial_pose or RobotPose()
        self._covariance = np.eye(6) * 0.01  # Small initial uncertainty
        self._history: List[RobotPose] = []

    @property
    def pose(self) -> RobotPose:
        return self._pose

    @property
    def position(self) -> np.ndarray:
        return np.array([self._pose.x, self._pose.y, self._pose.z])

    @property
    def orientation(self) -> np.ndarray:
        return np.array([self._pose.roll, self._pose.pitch, self._pose.yaw])

    def update_odometry(
        self,
        delta_x: float,
        delta_y: float,
        delta_yaw: float,
        dt: float = 0.01
    ) -> LocalizationResult:
        """
        Update pose using wheel odometry.

        Dead reckoning with accumulating error.
        """
        # Rotate delta by current yaw
        cos_yaw = np.cos(self._pose.yaw)
        sin_yaw = np.sin(self._pose.yaw)

        global_dx = cos_yaw * delta_x - sin_yaw * delta_y
        global_dy = sin_yaw * delta_x + cos_yaw * delta_y

        self._pose = RobotPose(
            x=self._pose.x + global_dx,
            y=self._pose.y + global_dy,
            z=self._pose.z,
            roll=self._pose.roll,
            pitch=self._pose.pitch,
            yaw=self._normalize_angle(self._pose.yaw + delta_yaw)
        )

        # Increase uncertainty
        self._covariance *= 1.01

        self._history.append(self._pose)

        return LocalizationResult(
            pose=self._pose,
            confidence=self._compute_confidence(),
            method=LocalizationMethod.ODOMETRY,
            covariance=self._covariance.copy()
        )

    def update_absolute(
        self,
        position: np.ndarray,
        orientation: Optional[np.ndarray] = None,
        covariance: Optional[np.ndarray] = None
    ) -> LocalizationResult:
        """
        Update with absolute position (GPS, beacon, etc.).

        Reduces uncertainty.
        """
        self._pose = RobotPose(
            x=position[0],
            y=position[1],
            z=position[2] if len(position) > 2 else self._pose.z,
            roll=orientation[0] if orientation is not None else self._pose.roll,
            pitch=orientation[1] if orientation is not None else self._pose.pitch,
            yaw=orientation[2] if orientation is not None else self._pose.yaw
        )

        if covariance is not None:
            self._covariance = covariance
        else:
            self._covariance = np.eye(6) * 0.1  # Reset to low uncertainty

        self._history.append(self._pose)

        return LocalizationResult(
            pose=self._pose,
            confidence=self._compute_confidence(),
            method=self.method,
            covariance=self._covariance.copy()
        )

    def fuse(
        self,
        odometry_delta: Tuple[float, float, float],
        absolute_pose: Optional[RobotPose] = None,
        absolute_covariance: Optional[np.ndarray] = None
    ) -> LocalizationResult:
        """
        Fuse odometry with absolute measurement.

        Simple weighted average based on covariance.
        """
        # Predict with odometry
        dx, dy, dyaw = odometry_delta
        predicted = RobotPose(
            x=self._pose.x + dx,
            y=self._pose.y + dy,
            z=self._pose.z,
            yaw=self._normalize_angle(self._pose.yaw + dyaw)
        )

        if absolute_pose is None:
            self._pose = predicted
            self._covariance *= 1.01
        else:
            # Kalman-like fusion (simplified)
            if absolute_covariance is None:
                absolute_covariance = np.eye(6) * 0.1

            # Compute Kalman gain
            S = self._covariance + absolute_covariance
            K = self._covariance @ np.linalg.inv(S)

            # Innovation
            innovation = np.array([
                absolute_pose.x - predicted.x,
                absolute_pose.y - predicted.y,
                absolute_pose.z - predicted.z,
                absolute_pose.roll - predicted.roll,
                absolute_pose.pitch - predicted.pitch,
                self._normalize_angle(absolute_pose.yaw - predicted.yaw)
            ])

            # Update
            correction = K @ innovation

            self._pose = RobotPose(
                x=predicted.x + correction[0],
                y=predicted.y + correction[1],
                z=predicted.z + correction[2],
                roll=predicted.roll + correction[3],
                pitch=predicted.pitch + correction[4],
                yaw=self._normalize_angle(predicted.yaw + correction[5])
            )

            # Update covariance
            self._covariance = (np.eye(6) - K) @ self._covariance

        self._history.append(self._pose)

        return LocalizationResult(
            pose=self._pose,
            confidence=self._compute_confidence(),
            method=LocalizationMethod.FUSION,
            covariance=self._covariance.copy()
        )

    def _compute_confidence(self) -> float:
        """Compute confidence from covariance."""
        # Trace of covariance as uncertainty measure
        uncertainty = np.trace(self._covariance)
        return max(0.0, 1.0 - uncertainty / 6.0)

    def _normalize_angle(self, angle: float) -> float:
        """Normalize angle to [-pi, pi]."""
        while angle > np.pi:
            angle -= 2 * np.pi
        while angle < -np.pi:
            angle += 2 * np.pi
        return angle

    def compute_identity_level(self) -> float:
        """
        Compute O2_IDENTITY layer activation.

        Based on localization confidence.
        """
        return self._compute_confidence()

    def get_history(self, max_length: int = 100) -> List[RobotPose]:
        """Get pose history."""
        return self._history[-max_length:]

    def reset(self, pose: Optional[RobotPose] = None) -> None:
        """Reset localization."""
        self._pose = pose or RobotPose()
        self._covariance = np.eye(6) * 0.01
        self._history = []
