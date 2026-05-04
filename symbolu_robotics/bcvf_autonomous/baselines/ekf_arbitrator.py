"""EKF arbitrator — Kalman fusion over predictor outputs with
Mahalanobis outlier rejection.

The fair comparison to BCVF at the predictor-arbitration interface.
At each horizon step:
  1. Predict step — propagate the state estimate forward via a
     constant-velocity motion model on the (x, y, theta) state.
  2. For each predictor's pose at this step, compute the
     **innovation** ``y_i = z_i - H * x_pred`` and the
     **innovation covariance** ``S_i = H * P * H^T + R_i``.
  3. **Mahalanobis gate**: if ``sqrt(y_i^T S_i^-1 y_i) >
     mahalanobis_threshold``, reject this measurement (don't
     apply the Kalman update). This is the same outlier-rejection
     mechanism ``robot_localization`` uses on individual sensor
     measurements.
  4. For accepted measurements, apply the standard Kalman update.

State: ``[x, y, theta, vx, vy, omega]`` (6-D). Constant-velocity
motion. Measurement model: each predictor measures ``[x, y, theta]``.

Per-predictor attribution = max-across-horizon Mahalanobis distance.
A predictor whose pose consistently exceeds the 3-sigma gate is
"the outlier" the EKF identifies.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from .base import ArbitrationResult, Arbitrator, validate_trajectories


@dataclass
class EKFConfig:
    """EKF arbitrator tuning."""

    dt: float = 0.1
    process_noise_pos: float = 0.5      # m^2 per step
    process_noise_heading: float = 0.05  # rad^2 per step
    measurement_noise_pos: float = 0.1   # m^2 per measurement
    measurement_noise_heading: float = 0.01  # rad^2 per measurement
    mahalanobis_threshold: float = 3.0   # 3-sigma gate
    initial_position_uncertainty: float = 1.0
    initial_velocity_uncertainty: float = 1.0


class EKFArbitrator:
    name: str = "EKF"

    def __init__(self, config: EKFConfig | None = None) -> None:
        self._cfg = config or EKFConfig()

    def arbitrate(self, trajectories: np.ndarray) -> ArbitrationResult:
        arr = validate_trajectories(trajectories)
        M, H, _ = arr.shape
        cfg = self._cfg

        # State: [x, y, theta, vx, vy, omega]
        # Initialise from the mean of the first-step poses.
        first_xy = arr[:, 0, :2].mean(axis=0)
        first_th = float(np.arctan2(
            np.sin(arr[:, 0, 2]).mean(),
            np.cos(arr[:, 0, 2]).mean(),
        ))
        x = np.zeros(6, dtype=np.float64)
        x[0] = first_xy[0]
        x[1] = first_xy[1]
        x[2] = first_th
        # Initial velocity guess from second-vs-first step diff.
        if H >= 2:
            v_xy = (arr[:, 1, :2] - arr[:, 0, :2]).mean(axis=0) / cfg.dt
            x[3] = v_xy[0]
            x[4] = v_xy[1]

        P = np.eye(6, dtype=np.float64)
        P[:2, :2] *= cfg.initial_position_uncertainty
        P[2, 2] = cfg.initial_position_uncertainty
        P[3:, 3:] *= cfg.initial_velocity_uncertainty

        # Process noise Q.
        Q = np.zeros((6, 6), dtype=np.float64)
        Q[0, 0] = Q[1, 1] = cfg.process_noise_pos
        Q[2, 2] = cfg.process_noise_heading
        Q[3, 3] = Q[4, 4] = cfg.process_noise_pos
        Q[5, 5] = cfg.process_noise_heading

        # Measurement model H: pose only (3-D out of 6-D state).
        H_meas = np.zeros((3, 6), dtype=np.float64)
        H_meas[0, 0] = 1.0
        H_meas[1, 1] = 1.0
        H_meas[2, 2] = 1.0

        # Measurement noise R per predictor.
        R = np.diag([
            cfg.measurement_noise_pos,
            cfg.measurement_noise_pos,
            cfg.measurement_noise_heading,
        ])

        consensus = np.zeros((H, 3), dtype=np.float64)
        # max Mahalanobis seen per predictor across the horizon.
        max_mahal = np.zeros(M, dtype=np.float64)
        per_tick_times: list = []

        for h in range(H):
            t0 = time.perf_counter()
            # Predict step (constant velocity).
            F = np.eye(6, dtype=np.float64)
            F[0, 3] = cfg.dt
            F[1, 4] = cfg.dt
            F[2, 5] = cfg.dt
            x = F @ x
            P = F @ P @ F.T + Q

            # Update step: per-predictor measurement with Mahalanobis gate.
            for i in range(M):
                z = arr[i, h, :].copy()
                # Wrap heading innovation to [-pi, pi] to avoid 2π jumps.
                y = z - H_meas @ x
                y[2] = np.arctan2(np.sin(y[2]), np.cos(y[2]))
                S = H_meas @ P @ H_meas.T + R
                try:
                    S_inv = np.linalg.inv(S)
                except np.linalg.LinAlgError:
                    continue
                mahal = float(np.sqrt(max(y @ S_inv @ y, 0.0)))
                max_mahal[i] = max(max_mahal[i], mahal)
                if mahal > cfg.mahalanobis_threshold:
                    continue   # reject outlier measurement
                K = P @ H_meas.T @ S_inv
                x = x + K @ y
                # Wrap heading back into [-pi, pi].
                x[2] = float(np.arctan2(np.sin(x[2]), np.cos(x[2])))
                P = (np.eye(6) - K @ H_meas) @ P

            consensus[h, 0] = x[0]
            consensus[h, 1] = x[1]
            consensus[h, 2] = float(np.arctan2(np.sin(x[2]), np.cos(x[2])))
            per_tick_times.append((time.perf_counter() - t0) * 1e6)

        return ArbitrationResult(
            consensus=consensus,
            attribution=max_mahal,
            per_tick_us=float(np.median(per_tick_times)),
            metadata={
                "mahalanobis_threshold": cfg.mahalanobis_threshold,
            },
        )
