"""M1 — IMU + wheel-encoder dead-reckoning predictor (anchor model).

V3.1 reference: Appendix E.2 Model M1.

M1 is the anchor because its nominal and failure dynamics are the
mildest: Gaussian step noise plus a cumulative random walk. BCVF's
second-difference operator is invariant to linear drift (Lemma 1), so
M1's slow degradation does not contaminate the coherence signal.
"""

from __future__ import annotations

from typing import Optional

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
