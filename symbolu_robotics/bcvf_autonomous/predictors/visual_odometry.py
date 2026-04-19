"""M3 — Visual odometry proxy predictor.

V3.1 reference: Appendix E.2 Model M3.

Nominal: tighter-than-GPS noise with mild drift (no loop closure).
Failure: two-phase degradation — first scan-matching noise inflation
with occasional heading jumps, then tracking loss (state freezes with
random walk).
"""

from __future__ import annotations

from typing import Optional

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
