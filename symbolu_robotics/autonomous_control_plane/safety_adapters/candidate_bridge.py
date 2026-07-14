"""Candidate -> trajectory bridge (Phase 2, AUTHORED).

The deliberative call site emits a single constant-velocity ``ActuatorCommand``
for a ``move`` candidate (``deliberative.py:_plan_move``), not a joint
trajectory, so the real ``TrajectoryValidator`` cannot be called on it directly.
This bridge integrates such a command into a short joint ``TrajectoryPoint``
sequence the validator CAN check.

It is explicitly AUTHORED (simple forward Euler over ``dt``): a demonstration of
how physical evidence *could* be obtained at the deliberative call site without
fabricating safety data. It is NOT a production motion planner and does not claim
to reproduce real robot dynamics.
"""
from __future__ import annotations

from typing import List

import numpy as np

from symbolu_robotics.safety.trajectory_validator import TrajectoryPoint


def velocity_command_to_trajectory(
    q0: np.ndarray, velocities: np.ndarray, *, dt: float = 0.1, steps: int = 5,
    coherence: float = 1.0,
) -> List[TrajectoryPoint]:
    """Integrate a constant joint-velocity command into TrajectoryPoints.

    q0: initial joint positions (n,). velocities: constant joint velocities (n,).
    Deterministic; no randomness, no clock.
    """
    q0 = np.asarray(q0, dtype=np.float64)
    v = np.asarray(velocities, dtype=np.float64)
    pts: List[TrajectoryPoint] = []
    for k in range(steps + 1):
        pts.append(TrajectoryPoint(
            timestamp=k * dt, positions=q0 + v * (k * dt),
            velocities=v.copy(), coherence=coherence))
    return pts
