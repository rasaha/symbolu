"""Predictor base class and shared kinematic bicycle dynamics.

V3.1 reference: Appendix E.2.

All four predictor implementations (M1–M4) inherit from
:class:`BasePredictor` and share the same ``bicycle_step`` forward dynamics.
They differ only in ``apply_noise`` / ``apply_failure``.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import Optional

import numpy as np

from ..manifold import wrap_angle


@dataclass
class BicycleConfig:
    """Kinematic bicycle model parameters."""

    wheelbase: float = 2.7
    max_steering: float = 0.6
    max_velocity: float = 15.0
    max_acceleration: float = 3.0
    dt: float = 0.1


@dataclass
class PredictorState:
    """Current state estimate held by a predictor."""

    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0
    velocity: float = 0.0
    timestamp: float = 0.0


@dataclass
class FailureConfig:
    """Failure injection parameters."""

    active: bool = False
    onset_time: float = 0.0
    severity: float = 1.0
    ramp_duration: float = 0.0


@dataclass
class ControlInput:
    """Single control input for the bicycle model."""

    velocity: float = 0.0
    steering: float = 0.0


def _clamp(value: float, low: float, high: float) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


class BasePredictor(ABC):
    """Abstract predictor that forward-simulates SE(2) trajectories.

    Concrete subclasses supply the predictor-specific ``apply_noise`` and
    ``apply_failure`` methods. The kinematic bicycle ``bicycle_step`` is
    inherited.

    ``predict`` never mutates the predictor's state estimate. All per-call
    transient state (RNG, drift accumulators, frozen frames) is reset at the
    top of each call so that identical seeds + identical control sequences
    produce identical trajectories.
    """

    def __init__(
        self,
        model_id: str,
        bicycle_config: Optional[BicycleConfig] = None,
        seed: int = 0,
    ) -> None:
        self.model_id = model_id
        self.bicycle_config = bicycle_config or BicycleConfig()
        self._seed = int(seed)
        self._state = PredictorState()
        self._failure = FailureConfig()
        # Per-call transient context. Reset at the start of each predict().
        self._rng: np.random.Generator = np.random.default_rng(self._seed)
        self._drift_x: float = 0.0
        self._drift_y: float = 0.0
        self._frozen_state: Optional[PredictorState] = None
        self._noise_multiplier: float = 1.0

    # --- dynamics ---

    def bicycle_step(
        self, state: PredictorState, control: ControlInput
    ) -> PredictorState:
        """One Euler step of the kinematic bicycle model (Appendix E.2)."""
        cfg = self.bicycle_config
        v = _clamp(control.velocity, -cfg.max_velocity, cfg.max_velocity)
        delta = _clamp(control.steering, -cfg.max_steering, cfg.max_steering)
        dt = cfg.dt

        x = state.x + v * math.cos(state.theta) * dt
        y = state.y + v * math.sin(state.theta) * dt
        theta = wrap_angle(state.theta + (v / cfg.wheelbase) * math.tan(delta) * dt)
        return PredictorState(
            x=x, y=y, theta=theta, velocity=v, timestamp=state.timestamp + dt
        )

    def bicycle_step_batch(
        self,
        state_x: np.ndarray,
        state_y: np.ndarray,
        state_th: np.ndarray,
        control_v: np.ndarray,
        control_delta: np.ndarray,
    ) -> tuple:
        """Vectorized one-step bicycle update for K rollouts.

        All inputs are ``(K,)`` ``float64`` arrays. Returns updated
        ``(state_x, state_y, state_th)`` triple. Heading is wrapped via
        ``arctan2(sin, cos)`` to match :func:`wrap_angle` exactly.
        """
        cfg = self.bicycle_config
        v = np.clip(control_v, -cfg.max_velocity, cfg.max_velocity)
        delta = np.clip(control_delta, -cfg.max_steering, cfg.max_steering)
        dt = cfg.dt
        new_x = state_x + v * np.cos(state_th) * dt
        new_y = state_y + v * np.sin(state_th) * dt
        raw_th = state_th + (v / cfg.wheelbase) * np.tan(delta) * dt
        new_th = np.arctan2(np.sin(raw_th), np.cos(raw_th))
        return new_x, new_y, new_th

    # --- subclass hooks ---

    @abstractmethod
    def apply_noise(self, state: PredictorState, step: int) -> PredictorState:
        """Return the recorded observation for a single step.

        Applies per-step observation error (non-compounding) to a *copy*
        of the propagated state. Does NOT mutate the state that
        propagates into the next ``bicycle_step``. Subclasses may read
        ``self._noise_multiplier`` to scale nominal standard deviations
        under failure-driven noise inflation.
        """

    def evolve_state(self, state: PredictorState, step: int) -> PredictorState:
        """Apply *state-carrying* cumulative effects (e.g. drift random walks)
        to the propagated state. Default: no-op.
        """
        return state

    @abstractmethod
    def apply_failure(self, state: PredictorState, time: float) -> PredictorState:
        """Apply predictor-specific failure distortion to the propagated state.

        Per DESIGN.md §2.3 pseudocode, failures corrupt the predictor's
        internal state belief — they compound across steps. Subclasses
        may also set ``self._noise_multiplier`` here so the subsequent
        ``apply_noise`` inflates observation noise.
        """

    # --- high-level API ---

    def _reset_call_context(self) -> None:
        """Reset all per-predict() transient state. Called at the top of predict()."""
        self._rng = np.random.default_rng(self._seed)
        self._drift_x = 0.0
        self._drift_y = 0.0
        self._frozen_state = None
        self._noise_multiplier = 1.0

    def predict(self, control_sequence: np.ndarray) -> np.ndarray:
        """Forward-simulate a trajectory from ``self._state``.

        ``control_sequence`` has shape ``(H, 2)`` with columns
        ``[velocity, steering]``. Returns an ``(H, 3)`` ``float64`` array of
        ``[x, y, theta]`` poses — directly consumable by
        :func:`symbolu_robotics.bcvf_autonomous.core.compute_bcvf_cost`.
        """
        ctrl = np.asarray(control_sequence, dtype=np.float64)
        if ctrl.ndim != 2 or ctrl.shape[1] != 2:
            raise ValueError(
                f"control_sequence must have shape (H, 2); got {ctrl.shape}"
            )

        self._reset_call_context()
        state = replace(self._state)
        horizon = ctrl.shape[0]
        trajectory = np.zeros((horizon, 3), dtype=np.float64)
        dt = self.bicycle_config.dt

        for k in range(horizon):
            control = ControlInput(velocity=float(ctrl[k, 0]), steering=float(ctrl[k, 1]))
            state = self.bicycle_step(state, control)
            state = self.evolve_state(state, k)               # cumulative drift
            time = self._state.timestamp + (k + 1) * dt
            state = self.apply_failure(state, time)           # state-corrupting failures
            observation = self.apply_noise(replace(state), k) # per-step obs noise
            trajectory[k, 0] = observation.x
            trajectory[k, 1] = observation.y
            trajectory[k, 2] = wrap_angle(observation.theta)

        return trajectory

    def predict_batch(self, controls_batch: np.ndarray) -> np.ndarray:
        """Forward-simulate ``K`` trajectories in parallel.

        ``controls_batch`` has shape ``(K, H, 2)``; returns ``(K, H, 3)``.

        The default implementation is a Python loop over ``K`` calls to
        :meth:`predict`. Subclasses MAY override with a vectorized
        implementation that runs the H sequential dynamics steps with
        ``(K,)``-shaped state arrays. Any override **must** produce
        numerically identical output to the default loop so that the
        existing test suite and downstream BCVF / trust-shaper behavior
        are bit-for-bit preserved.

        The numeric-equivalence contract relies on the fact that
        ``predict()`` resets the predictor's RNG at the top of every
        call, so all K rollouts of the same predictor at the same
        planning tick already receive identical noise streams. The
        only across-rollout variation comes from the differing control
        inputs and the resulting state evolution. A vectorized
        implementation can therefore draw each H-step's noise once
        (consuming the same RNG sequence the default loop consumes)
        and broadcast it across the K rollouts.
        """
        ctrl = np.asarray(controls_batch, dtype=np.float64)
        if ctrl.ndim != 3 or ctrl.shape[2] != 2:
            raise ValueError(
                f"controls_batch must have shape (K, H, 2); got {ctrl.shape}"
            )
        K, H, _ = ctrl.shape
        out = np.zeros((K, H, 3), dtype=np.float64)
        for k in range(K):
            out[k] = self.predict(ctrl[k])
        return out

    def update_state(
        self, ground_truth: PredictorState, noise_std: float = 0.0
    ) -> None:
        """Snap the internal estimate to ``ground_truth`` (plus optional noise)."""
        if noise_std > 0.0:
            self._state = PredictorState(
                x=ground_truth.x + float(self._rng.normal(0.0, noise_std)),
                y=ground_truth.y + float(self._rng.normal(0.0, noise_std)),
                theta=wrap_angle(ground_truth.theta),
                velocity=ground_truth.velocity,
                timestamp=ground_truth.timestamp,
            )
        else:
            self._state = replace(ground_truth)

    def set_state(self, state: PredictorState) -> None:
        """Testing helper: deterministically set the internal estimate."""
        self._state = replace(state)

    def set_failure(self, config: FailureConfig) -> None:
        """Configure failure injection."""
        self._failure = replace(config)

    def reset(self) -> None:
        """Reset to a zero state estimate, clear any failure."""
        self._state = PredictorState()
        self._failure = FailureConfig()
        self._reset_call_context()

    # --- accessors ---

    @property
    def state(self) -> PredictorState:
        return replace(self._state)

    @property
    def failure(self) -> FailureConfig:
        return replace(self._failure)
