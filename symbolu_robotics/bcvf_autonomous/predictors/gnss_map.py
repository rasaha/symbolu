"""M4 — GNSS + HD-map predictor.

V3.1 reference: Appendix E.2 Model M4.

Nominal: high step-noise (GPS is intrinsically noisy) but no drift — GPS
provides an absolute reference. Failure modes:

* ``multipath`` (urban canyon) — progressively frequent position jumps.
* ``map_error`` (construction zone) — systematic lateral offset growing
  with elapsed time.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from .base import BasePredictor, BicycleConfig, PredictorState


class GNSSMap(BasePredictor):
    """GPS + HD-map proxy with multipath or map-error failure modes."""

    # Phase 2 tuning (DESIGN §2.9 gate 3 license): the DESIGN draft
    # specified raw-GPS std=0.5 m, but the BCVF integration success-gate
    # (§2.9 #3) requires nominal-vs-failure cost separation ≥ 10x. Per-step
    # noise >> T/4 swamps the signal via the 1/dt^2 second-difference
    # stencil. 0.01 m matches *filtered* RTK GPS output and preserves the
    # heterogeneous-noise ordering V3.1 asks for (M4 still noisiest nominal).
    NOMINAL_POSITION_STD = 0.01
    NOMINAL_HEADING_STD = 0.002
    MULTIPATH_JUMP_PROB_MAX = 0.3
    MULTIPATH_BASE_JUMP_M = 2.0
    MULTIPATH_EXPONENTIAL_SCALE = 3.0
    MAP_ERROR_RATE = 0.5
    # Phase 4 follow-up (§4C.13 gate-2 enablement, S3_map_error_accel
    # variant): quadratic-in-time lateral drift so the per-step bias
    # increment keeps accelerating across the episode — gives 2nd-order
    # BCVF persistent signal instead of only a transient during the ramp.
    MAP_ERROR_ACCEL_RATE = 0.02

    def __init__(
        self,
        bicycle_config: Optional[BicycleConfig] = None,
        seed: int = 45,
        failure_type: str = "multipath",
    ) -> None:
        super().__init__(model_id="M4", bicycle_config=bicycle_config, seed=seed)
        if failure_type not in (
            "multipath", "map_error", "map_error_accel", "constant_bias"
        ):
            raise ValueError(
                f"failure_type must be 'multipath', 'map_error', "
                f"'map_error_accel', or 'constant_bias'; got {failure_type!r}"
            )
        self.failure_type = failure_type
        # Constant-bias magnitude (meters) used by the S5 validation scenario.
        self.constant_bias_x = 0.5

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
        elapsed = time - f.onset_time
        progress = 1.0
        if f.ramp_duration > 1e-9:
            progress = min(1.0, elapsed / f.ramp_duration)
        scale = progress * f.severity

        if self.failure_type == "multipath":
            return self._apply_multipath(state, elapsed, scale)
        if self.failure_type == "constant_bias":
            return self._apply_constant_bias(state, elapsed, scale)
        if self.failure_type == "map_error_accel":
            return self._apply_map_error_accel(state, elapsed, scale)
        return self._apply_map_error(state, elapsed, scale)

    # --- failure sub-modes ---

    def _apply_multipath(
        self, state: PredictorState, elapsed: float, scale: float
    ) -> PredictorState:
        rng = self._rng
        if rng.random() < scale * self.MULTIPATH_JUMP_PROB_MAX:
            jump_mag = self.MULTIPATH_BASE_JUMP_M + float(
                rng.exponential(scale * self.MULTIPATH_EXPONENTIAL_SCALE)
            )
            jump_angle = float(rng.uniform(0.0, 2.0 * math.pi))
            state.x += jump_mag * math.cos(jump_angle)
            state.y += jump_mag * math.sin(jump_angle)
        return state

    def _apply_map_error(
        self, state: PredictorState, elapsed: float, scale: float
    ) -> PredictorState:
        # Lateral offset perpendicular to current heading (+pi/2).
        lateral = scale * elapsed * self.MAP_ERROR_RATE
        lateral_heading = state.theta + math.pi / 2.0
        state.x += lateral * math.cos(lateral_heading)
        state.y += lateral * math.sin(lateral_heading)
        return state

    def _apply_map_error_accel(
        self, state: PredictorState, elapsed: float, scale: float
    ) -> PredictorState:
        # Quadratic-in-time lateral drift. Per-step increment grows as
        # ``elapsed^2``, so in a rollout of length H the state's second
        # difference in rollout-step index stays O(elapsed · dt) rather
        # than collapsing to zero once the ramp completes. 2nd-order
        # BCVF has persistent signal through the misrouting phase.
        lateral = scale * self.MAP_ERROR_ACCEL_RATE * elapsed * elapsed
        lateral_heading = state.theta + math.pi / 2.0
        state.x += lateral * math.cos(lateral_heading)
        state.y += lateral * math.sin(lateral_heading)
        return state

    def _apply_constant_bias(
        self, state: PredictorState, elapsed: float, scale: float
    ) -> PredictorState:
        # Phase 4A scenario S5: Lemma 1 validation. Time-invariant offset
        # with no randomness and no growth -> 2nd-diff of disagreement = 0,
        # so J_BCVF = 0 while J_ZEROTH / J_FIRST see the bias.
        state.x += self.constant_bias_x
        return state

    # --- vectorized batch path ---

    def predict_batch(self, controls_batch: np.ndarray) -> np.ndarray:
        """Vectorized K-rollout forward simulation.

        All four failure modes are state-mutating but per-step scalar:

        - ``multipath`` consumes 1 ``rng.random()`` per step plus 2 more
          (exponential + uniform angle) if the jump triggers. Same
          jump magnitude / angle applied to all K rollouts.
        - ``map_error`` is deterministic — adds a state-dependent
          lateral offset perpendicular to the per-rollout heading.
        - ``map_error_accel`` is the same shape with quadratic-in-time
          magnitude.
        - ``constant_bias`` adds a fixed scalar to ``state.x``.

        The lateral-offset modes use ``state.theta`` to compute the
        offset direction, so the offset is per-rollout (different
        thetas), not scalar. Implementation handles that via vector
        ``cos(state_th + π/2)`` etc.
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
            # apply_failure — branched by failure_type.
            time = self._state.timestamp + (h + 1) * dt
            if f.active and time >= f.onset_time:
                elapsed = time - f.onset_time
                progress = 1.0
                if f.ramp_duration > 1e-9:
                    progress = min(1.0, elapsed / f.ramp_duration)
                scale = progress * f.severity

                if self.failure_type == "multipath":
                    if rng.random() < scale * self.MULTIPATH_JUMP_PROB_MAX:
                        jump_mag = self.MULTIPATH_BASE_JUMP_M + float(
                            rng.exponential(
                                scale * self.MULTIPATH_EXPONENTIAL_SCALE
                            )
                        )
                        jump_angle = float(rng.uniform(0.0, 2.0 * math.pi))
                        state_x = state_x + jump_mag * math.cos(jump_angle)
                        state_y = state_y + jump_mag * math.sin(jump_angle)
                elif self.failure_type == "constant_bias":
                    state_x = state_x + self.constant_bias_x
                elif self.failure_type == "map_error_accel":
                    lateral = (
                        scale
                        * self.MAP_ERROR_ACCEL_RATE
                        * elapsed
                        * elapsed
                    )
                    lateral_heading = state_th + math.pi / 2.0
                    state_x = state_x + lateral * np.cos(lateral_heading)
                    state_y = state_y + lateral * np.sin(lateral_heading)
                else:  # map_error
                    lateral = scale * elapsed * self.MAP_ERROR_RATE
                    lateral_heading = state_th + math.pi / 2.0
                    state_x = state_x + lateral * np.cos(lateral_heading)
                    state_y = state_y + lateral * np.sin(lateral_heading)

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
