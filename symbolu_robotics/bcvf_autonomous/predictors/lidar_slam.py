"""M2 — LiDAR SLAM proxy predictor.

V3.1 reference: Appendix E.2 Model M2.

Nominal behavior: tighter step noise than IMU, with SLAM loop closure
correcting long-term drift (no random walk).

Failure mode: glass / rain / fog degrades scan matching. We model this
as noise inflation plus a quadratic systematic bias — an *accelerating*
divergence that is exactly the signal BCVF's second-order detector is
designed to catch.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from .base import BasePredictor, BicycleConfig, PredictorState


class LidarSLAM(BasePredictor):
    """LiDAR SLAM proxy with glass/rain failure (quadratic divergence)."""

    # Phase 2 tuning (DESIGN §2.9 gate 3 license): post-filter SLAM noise.
    # FAILURE_QUADRATIC_COEFF raised from the DESIGN draft's 0.01 to 0.5 so
    # the accelerating SLAM-drift signal meets the ≥ 10x nominal-vs-failure
    # separation criterion once predictor noise is at post-filter levels.
    NOMINAL_POSITION_STD = 0.004
    NOMINAL_HEADING_STD = 0.001
    FAILURE_NOISE_MULT = 10.0
    FAILURE_QUADRATIC_COEFF = 0.5

    def __init__(
        self,
        bicycle_config: Optional[BicycleConfig] = None,
        seed: int = 43,
    ) -> None:
        super().__init__(model_id="M2", bicycle_config=bicycle_config, seed=seed)

    def apply_noise(self, state: PredictorState, step: int) -> PredictorState:
        rng = self._rng
        mult = self._noise_multiplier
        state.x += float(rng.normal(0.0, self.NOMINAL_POSITION_STD * mult))
        state.y += float(rng.normal(0.0, self.NOMINAL_POSITION_STD * mult))
        state.theta += float(rng.normal(0.0, self.NOMINAL_HEADING_STD * mult))
        return state

    def apply_failure(self, state: PredictorState, time: float) -> PredictorState:
        f = self._failure
        if not f.active or time < f.onset_time:
            self._noise_multiplier = 1.0
            return state
        elapsed = time - f.onset_time
        progress = 1.0
        if f.ramp_duration > 1e-9:
            progress = min(1.0, elapsed / f.ramp_duration)
        scale = progress * f.severity

        # Scan-matching uncertainty -> observation noise inflates.
        self._noise_multiplier = 1.0 + scale * self.FAILURE_NOISE_MULT
        # Systematic quadratic bias on the propagated state — compounds per
        # step and produces accelerating divergence (the BCVF target signal).
        state.x += scale * 0.5 * elapsed * elapsed * self.FAILURE_QUADRATIC_COEFF
        return state

    # --- vectorized batch path ---

    def predict_batch(self, controls_batch: np.ndarray) -> np.ndarray:
        """Vectorized K-rollout forward simulation. See
        ``BasePredictor.predict_batch`` for the equivalence contract."""
        ctrl = np.asarray(controls_batch, dtype=np.float64)
        if ctrl.ndim != 3 or ctrl.shape[2] != 2:
            raise ValueError(
                f"controls_batch must have shape (K, H, 2); got {ctrl.shape}"
            )
        K, H, _ = ctrl.shape

        self._reset_call_context()
        cfg = self.bicycle_config
        dt = cfg.dt
        s = self._state
        state_x = np.full(K, s.x, dtype=np.float64)
        state_y = np.full(K, s.y, dtype=np.float64)
        state_th = np.full(K, s.theta, dtype=np.float64)

        out = np.zeros((K, H, 3), dtype=np.float64)
        rng = self._rng
        f = self._failure

        for h in range(H):
            state_x, state_y, state_th = self.bicycle_step_batch(
                state_x, state_y, state_th, ctrl[:, h, 0], ctrl[:, h, 1],
            )
            # apply_failure — quadratic scan-matching bias plus noise
            # multiplier. Both per-step values are scalar (depend only on
            # elapsed time, not state) and broadcast across K.
            time = self._state.timestamp + (h + 1) * dt
            if not f.active or time < f.onset_time:
                self._noise_multiplier = 1.0
            else:
                elapsed = time - f.onset_time
                progress = 1.0
                if f.ramp_duration > 1e-9:
                    progress = min(1.0, elapsed / f.ramp_duration)
                scale = progress * f.severity
                self._noise_multiplier = 1.0 + scale * self.FAILURE_NOISE_MULT
                state_x = state_x + scale * 0.5 * elapsed * elapsed * (
                    self.FAILURE_QUADRATIC_COEFF
                )
            # apply_noise — observation noise drawn once per step.
            mult = self._noise_multiplier
            nx = float(rng.normal(0.0, self.NOMINAL_POSITION_STD * mult))
            ny = float(rng.normal(0.0, self.NOMINAL_POSITION_STD * mult))
            nth = float(rng.normal(0.0, self.NOMINAL_HEADING_STD * mult))
            obs_th = state_th + nth
            obs_th = np.arctan2(np.sin(obs_th), np.cos(obs_th))
            out[:, h, 0] = state_x + nx
            out[:, h, 1] = state_y + ny
            out[:, h, 2] = obs_th

        return out
