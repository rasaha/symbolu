"""M3 — Visual odometry proxy predictor.

V3.1 reference: Appendix E.2 Model M3.

Nominal: tighter-than-GPS noise with mild drift (no loop closure).
Failure: two-phase degradation — first scan-matching noise inflation
with occasional heading jumps, then tracking loss (state freezes with
random walk).
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from ..manifold import wrap_angle
from .base import BasePredictor, BicycleConfig, PredictorState


class VisualOdometry(BasePredictor):
    """Monocular VO proxy with low-light / texture-loss failure."""

    # Phase 2 tuning (DESIGN §2.9 gate 3 license): post-filter VO noise.
    NOMINAL_POSITION_STD = 0.006
    NOMINAL_HEADING_STD = 0.0016
    NOMINAL_DRIFT_RATE = 0.0004
    DEGRADATION_NOISE_MULT = 8.0
    FROZEN_WALK_STD = 0.1
    HEADING_JUMP_STD = 0.2
    HEADING_JUMP_PROB_MAX = 0.1

    def __init__(
        self,
        bicycle_config: Optional[BicycleConfig] = None,
        seed: int = 44,
    ) -> None:
        super().__init__(model_id="M3", bicycle_config=bicycle_config, seed=seed)

    def evolve_state(self, state: PredictorState, step: int) -> PredictorState:
        # Mild cumulative drift (no loop closure) — persists in propagated state.
        rng = self._rng
        self._drift_x += float(rng.normal(0.0, self.NOMINAL_DRIFT_RATE))
        self._drift_y += float(rng.normal(0.0, self.NOMINAL_DRIFT_RATE))
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
            self._noise_multiplier = 1.0
            return state
        elapsed = time - f.onset_time
        progress = 1.0
        if f.ramp_duration > 1e-9:
            progress = min(1.0, elapsed / f.ramp_duration)
        scale = progress * f.severity
        rng = self._rng

        if scale < 0.5:
            # Degradation phase: observation noise inflates; heading
            # occasionally jumps (state-level perturbation).
            self._noise_multiplier = 1.0 + scale * self.DEGRADATION_NOISE_MULT
            if rng.random() < scale * self.HEADING_JUMP_PROB_MAX:
                state.theta = wrap_angle(
                    state.theta + float(rng.normal(0.0, self.HEADING_JUMP_STD))
                )
        else:
            # Tracking loss: freeze the state estimate at the first tracking-
            # loss step and random-walk around it. Observation noise scaled
            # by the walk std. The observation drifts while the true vehicle
            # moves away — this is what BCVF should detect.
            if self._frozen_state is None:
                self._frozen_state = PredictorState(
                    x=state.x, y=state.y, theta=state.theta
                )
            fs = self._frozen_state
            state.x = fs.x
            state.y = fs.y
            state.theta = fs.theta
            self._noise_multiplier = self.FROZEN_WALK_STD / self.NOMINAL_POSITION_STD
        return state

    # --- vectorized batch path ---

    def predict_batch(self, controls_batch: np.ndarray) -> np.ndarray:
        """Vectorized K-rollout forward simulation.

        Tricky cases for VO:

        - The cumulative drift in :meth:`evolve_state` is a scalar
          random-walk (broadcast across K — same as M1).
        - Tracking loss freezes ``state`` at the first H-step where
          ``scale >= 0.5``. The freeze step is the *same* across
          rollouts (depends only on time), so we capture the per-
          rollout state at that step into ``(K,)`` frozen arrays.
          Subsequent steps replace the propagated state with the
          per-rollout frozen state.
        - The degradation-phase heading jump uses one ``rng.random()``
          and (if triggered) one ``rng.normal()`` — both scalar; the
          jump is applied to all K headings identically. This matches
          the per-rollout loop because each rollout's reset RNG sees
          the same draws at the same H-step.
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
        # Per-rollout frozen state, captured at the first tracking-loss
        # step. None until then.
        frozen_x: Optional[np.ndarray] = None
        frozen_y: Optional[np.ndarray] = None
        frozen_th: Optional[np.ndarray] = None

        for h in range(H):
            state_x, state_y, state_th = self.bicycle_step_batch(
                state_x, state_y, state_th, ctrl[:, h, 0], ctrl[:, h, 1],
            )
            # evolve_state — cumulative drift random walk (scalar
            # accumulator, broadcast across K).
            self._drift_x += float(rng.normal(0.0, self.NOMINAL_DRIFT_RATE))
            self._drift_y += float(rng.normal(0.0, self.NOMINAL_DRIFT_RATE))
            state_x = state_x + self._drift_x
            state_y = state_y + self._drift_y

            # apply_failure
            time = self._state.timestamp + (h + 1) * dt
            if not f.active or time < f.onset_time:
                self._noise_multiplier = 1.0
            else:
                elapsed = time - f.onset_time
                progress = 1.0
                if f.ramp_duration > 1e-9:
                    progress = min(1.0, elapsed / f.ramp_duration)
                scale = progress * f.severity

                if scale < 0.5:
                    self._noise_multiplier = (
                        1.0 + scale * self.DEGRADATION_NOISE_MULT
                    )
                    # Heading-jump branch — consumes 1 rng.random() per
                    # step, plus 1 rng.normal() if triggered.
                    if rng.random() < scale * self.HEADING_JUMP_PROB_MAX:
                        jump = float(
                            rng.normal(0.0, self.HEADING_JUMP_STD)
                        )
                        raw = state_th + jump
                        state_th = np.arctan2(np.sin(raw), np.cos(raw))
                else:
                    if frozen_x is None:
                        frozen_x = state_x.copy()
                        frozen_y = state_y.copy()
                        frozen_th = state_th.copy()
                    state_x = frozen_x
                    state_y = frozen_y
                    state_th = frozen_th
                    self._noise_multiplier = (
                        self.FROZEN_WALK_STD / self.NOMINAL_POSITION_STD
                    )

            # apply_noise — per-step observation noise.
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
