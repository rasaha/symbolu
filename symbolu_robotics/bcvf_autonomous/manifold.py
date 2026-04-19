"""SE(2) Lie group operations for BCVF Autonomous.

V3.1 reference: Section 3.1-3.2.

This module provides the geometric foundation for the BCVF cost.
SE(2) is the group of rigid-body transformations in the plane:
position (x, y) and heading (theta). All disagreement computations
happen in the tangent space of this group, not in Euclidean space.

All functions are pure: float/ndarray in, float/ndarray out, no
mutable state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class SE2Pose:
    """Pose on SE(2): position + heading."""

    x: float
    y: float
    theta: float


def wrap_angle(angle: float) -> float:
    """Wrap ``angle`` into [-pi, pi) using atan2(sin, cos).

    Avoids modular-arithmetic edge cases at +/-pi.
    """
    return math.atan2(math.sin(angle), math.cos(angle))


def compose(a: SE2Pose, b: SE2Pose) -> SE2Pose:
    """Group composition a * b on SE(2).

    Rotate b's position by a's heading, add positions, add angles.
    """
    cos_a = math.cos(a.theta)
    sin_a = math.sin(a.theta)
    x = a.x + cos_a * b.x - sin_a * b.y
    y = a.y + sin_a * b.x + cos_a * b.y
    theta = wrap_angle(a.theta + b.theta)
    return SE2Pose(x=x, y=y, theta=theta)


def inverse(pose: SE2Pose) -> SE2Pose:
    """Group inverse on SE(2)."""
    cos_t = math.cos(pose.theta)
    sin_t = math.sin(pose.theta)
    x = -(cos_t * pose.x + sin_t * pose.y)
    y = -(-sin_t * pose.x + cos_t * pose.y)
    theta = wrap_angle(-pose.theta)
    return SE2Pose(x=x, y=y, theta=theta)


def log_map(pose: SE2Pose) -> np.ndarray:
    """Map a pose from SE(2) to the tangent space se(2) in R^3.

    Provided for completeness; ``body_frame_error`` is the operator
    called on the hot path.
    """
    theta = wrap_angle(pose.theta)
    if abs(theta) < 1e-9:
        v_x = pose.x
        v_y = pose.y
    else:
        half = 0.5 * theta
        cot_half = half / math.tan(half)
        v_x = cot_half * pose.x + half * pose.y
        v_y = -half * pose.x + cot_half * pose.y
    return np.array([v_x, v_y, theta], dtype=np.float64)


def body_frame_error(
    pose_i: SE2Pose, pose_j: SE2Pose, lever_arm: float
) -> np.ndarray:
    """V3.1 Section 3.2 disagreement operator specialized to SE(2).

    e_ij = [R(theta_j)^T (p_i - p_j);  wrap(theta_i - theta_j) * L]

    ``lever_arm`` (L) homogenizes yaw error into linear-displacement
    risk at the vehicle front.
    """
    dx_world = pose_i.x - pose_j.x
    dy_world = pose_i.y - pose_j.y
    cos_j = math.cos(pose_j.theta)
    sin_j = math.sin(pose_j.theta)
    dx_body = cos_j * dx_world + sin_j * dy_world
    dy_body = -sin_j * dx_world + cos_j * dy_world
    dtheta = wrap_angle(pose_i.theta - pose_j.theta) * lever_arm
    return np.array([dx_body, dy_body, dtheta], dtype=np.float64)


def body_frame_error_trajectory(
    traj_i: np.ndarray, traj_j: np.ndarray, lever_arm: float
) -> np.ndarray:
    """Vectorized body-frame error over a trajectory.

    Inputs are (H, 3) arrays with columns [x, y, theta]. Returns an
    (H, 3) array. Used by ``core.compute_disagreement`` so the hot
    path does not loop in Python.
    """
    if traj_i.shape != traj_j.shape or traj_i.shape[-1] != 3:
        raise ValueError(
            f"trajectories must have shape (H, 3); got {traj_i.shape} and {traj_j.shape}"
        )
    xi = traj_i[..., 0]
    yi = traj_i[..., 1]
    ti = traj_i[..., 2]
    xj = traj_j[..., 0]
    yj = traj_j[..., 1]
    tj = traj_j[..., 2]

    dx_world = xi - xj
    dy_world = yi - yj
    cos_j = np.cos(tj)
    sin_j = np.sin(tj)
    dx_body = cos_j * dx_world + sin_j * dy_world
    dy_body = -sin_j * dx_world + cos_j * dy_world
    dtheta_raw = ti - tj
    dtheta = np.arctan2(np.sin(dtheta_raw), np.cos(dtheta_raw)) * lever_arm

    return np.stack([dx_body, dy_body, dtheta], axis=-1).astype(np.float64, copy=False)
