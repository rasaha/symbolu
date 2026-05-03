"""M1 — IMU + wheel-encoder dead-reckoning predictor (anchor model).

V3.1 reference: Appendix E.2 Model M1.

M1 is the anchor because its nominal and failure dynamics are the
mildest: Gaussian step noise plus a cumulative random walk. BCVF's
second-difference operator is invariant to linear drift (Lemma 1), so
M1's slow degradation does not contaminate the coherence signal.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from .base import BasePredictor, BicycleConfig, PredictorState


class IMUOdometry(BasePredictor):
    """Dead-reckoning predictor: graceful linear drift, no absolute reference."""

    # Phase 2 tuning (DESIGN §2.9 gate 3 license): nominal noise and drift
    # are scaled to post-filter (EKF-output) values so the per-step
    # observation stream stays well below the T=0.2 gate threshold and
    # does not dominate BCVF through the 1/dt^2 second-difference stencil.
    # FAILURE_EXTRA_DRIFT is likewise scaled to keep the DESIGN's ~10x
    # boost ratio at severity=1 (0.001 nominal -> 0.011 faulted), which
    # preserves the Lemma 1 invariance claim for drift-like failures.
    NOMINAL_POSITION_STD = 0.002
    NOMINAL_HEADING_STD = 0.0002
    NOMINAL_DRIFT_RATE = 0.001
    FAILURE_EXTRA_DRIFT = 0.01

    def __init__(
        self,
        bicycle_config: Optional[BicycleConfig] = None,
        seed: int = 42,
    ) -> None:
        super().__init__(model_id="M1", bicycle_config=bicycle_config, seed=seed)
        self._drift_rate = self.NOMINAL_DRIFT_RATE

    def _reset_call_context(self) -> None:
        super()._reset_call_context()
        self._drift_rate = self.NOMINAL_DRIFT_RATE

    def evolve_state(self, state: PredictorState, step: int) -> PredictorState:
        # Cumulative drift as a random walk — expected linear growth, so
        # BCVF's second-order detector (Lemma 1) will ignore it. This is the
        # reason M1 is the anchor: its slow degradation does not contaminate
        # the coherence signal.
        rng = self._rng
        self._drift_x += float(rng.normal(0.0, self._drift_rate))
        self._drift_y += float(rng.normal(0.0, self._drift_rate))
        state.x += self._drift_x
        state.y += self._drift_y
        return state

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
            return state
        progress = 1.0
        if f.ramp_duration > 1e-9:
            progress = min(1.0, (time - f.onset_time) / f.ramp_duration)
        self._drift_rate = self.NOMINAL_DRIFT_RATE + progress * f.severity * self.FAILURE_EXTRA_DRIFT
        return state

    # --- vectorized batch path ---

    def predict_batch(self, controls_batch: np.ndarray) -> np.ndarray:
        """Vectorized K-rollout forward simulation.

        Numerically identical to the default per-rollout loop (asserted
        by ``test_predict_batch_matches_predict_loop``). Runs all K
        rollouts through the H sequential dynamics steps with
        ``(K,)``-shaped state arrays; noise / drift / failure-induced
        biases are scalar per step (the per-rollout loop's reset RNG
        already gives every rollout the same sample) and broadcast
        across K.
        """
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
            # evolve_state — cumulative drift random walk (scalar accumulator).
            self._drift_x += float(rng.normal(0.0, self._drift_rate))
            self._drift_y += float(rng.normal(0.0, self._drift_rate))
            state_x = state_x + self._drift_x
            state_y = state_y + self._drift_y
            # apply_failure — for IMU this only retunes the drift rate;
            # there is no state-mutating term.
            time = self._state.timestamp + (h + 1) * dt
            if f.active and time >= f.onset_time:
                progress = 1.0
                if f.ramp_duration > 1e-9:
                    progress = min(1.0, (time - f.onset_time) / f.ramp_duration)
                self._drift_rate = (
                    self.NOMINAL_DRIFT_RATE
                    + progress * f.severity * self.FAILURE_EXTRA_DRIFT
                )
            # apply_noise — per-step observation noise (non-cumulative).
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
