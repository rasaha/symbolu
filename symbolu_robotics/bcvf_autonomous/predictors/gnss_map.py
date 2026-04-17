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

    def __init__(
        self,
        bicycle_config: Optional[BicycleConfig] = None,
        seed: int = 45,
        failure_type: str = "multipath",
    ) -> None:
        super().__init__(model_id="M4", bicycle_config=bicycle_config, seed=seed)
        if failure_type not in ("multipath", "map_error"):
            raise ValueError(
                f"failure_type must be 'multipath' or 'map_error'; got {failure_type!r}"
            )
        self.failure_type = failure_type

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
