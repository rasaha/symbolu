"""Phase 3A — lightweight 2D SE(2) ground-vehicle simulator.

Owns ground-truth vehicle state, steps physics via the shared kinematic
bicycle model, updates predictor state estimates each cycle, and records
a full `SimState` history for downstream analysis (Phase 4 metrics).

Per DESIGN.md §3A.9: no planner dependency, deterministic, stateless
road/obstacles. This module imports the bicycle model via
``BasePredictor.bicycle_step`` (shared dynamics) but has no
Phase 1 math-kernel dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional

import numpy as np

from .predictors.base import (
    BasePredictor,
    BicycleConfig,
    ControlInput,
    PredictorState,
)


@dataclass
class Road:
    """Road geometry for J_perf computation — polyline centerline."""

    centerline: np.ndarray  # (N, 2) waypoints
    width: float = 3.5
    speed_limit: float = 10.0


@dataclass
class Obstacle:
    """Static circular obstacle."""

    x: float
    y: float
    radius: float = 1.0


@dataclass
class SimConfig:
    """Simulator configuration."""

    dt: float = 0.1
    max_steps: int = 200
    bicycle: BicycleConfig = field(default_factory=BicycleConfig)
    road: Road = field(default_factory=lambda: make_straight_road())
    obstacles: List[Obstacle] = field(default_factory=list)
    seed: int = 42


@dataclass
class SimState:
    """Complete simulation state at one time step."""

    step: int
    time: float
    ground_truth: PredictorState
    predictor_states: Dict[str, PredictorState]
    applied_control: np.ndarray
    bcvf_cost: float = 0.0
    perf_cost: float = 0.0
    total_cost: float = 0.0
    collision: bool = False


# --- Road generators (§3A.5) ---


def make_straight_road(length: float = 200.0, spacing: float = 1.0) -> Road:
    """Straight road along the +x axis through the origin."""
    n = max(int(length / spacing), 2)
    xs = np.linspace(0.0, length, n, dtype=np.float64)
    ys = np.zeros_like(xs)
    return Road(centerline=np.stack([xs, ys], axis=-1))


def make_curved_road(radius: float = 100.0, arc_degrees: float = 90.0) -> Road:
    """Constant-radius arc starting along +x, curving to +y."""
    arc_rad = math.radians(arc_degrees)
    n = max(int(radius * arc_rad), 2)
    thetas = np.linspace(0.0, arc_rad, n, dtype=np.float64)
    xs = radius * np.sin(thetas)
    ys = radius * (1.0 - np.cos(thetas))
    return Road(centerline=np.stack([xs, ys], axis=-1))


def make_urban_road(blocks: int = 4, block_size: float = 50.0) -> Road:
    """Grid-like urban road: repeated right-angle segments."""
    pts: List[tuple[float, float]] = [(0.0, 0.0)]
    heading = 0.0  # +x
    for i in range(blocks):
        dx = block_size * math.cos(heading)
        dy = block_size * math.sin(heading)
        last = pts[-1]
        pts.append((last[0] + dx, last[1] + dy))
        heading += math.pi / 2.0 if i % 2 == 0 else -math.pi / 2.0
    # Densify to ~1 m spacing.
    dense: List[tuple[float, float]] = []
    for a, b in zip(pts[:-1], pts[1:]):
        seg_len = math.hypot(b[0] - a[0], b[1] - a[1])
        m = max(int(seg_len), 2)
        for t in np.linspace(0.0, 1.0, m, endpoint=False):
            dense.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    dense.append(pts[-1])
    return Road(centerline=np.asarray(dense, dtype=np.float64))


# --- Simulator ---


class Simulator:
    """Closed-loop test bed for BCVF Autonomous."""

    def __init__(
        self,
        config: SimConfig,
        predictors: Dict[str, BasePredictor],
    ) -> None:
        self._config = config
        self._predictors = predictors
        self._ground_truth = PredictorState()
        self._step = 0
        self._history: List[SimState] = []
        # Reference predictor used for bicycle_step dynamics. All predictors
        # share the same bicycle model, so any one will do; the first keeps
        # the Simulator code path minimal.
        if not predictors:
            raise ValueError("Simulator requires at least one predictor")
        self._bicycle_owner = next(iter(predictors.values()))

    # --- lifecycle ---

    def reset(self, initial_pose: Optional[PredictorState] = None) -> SimState:
        self._ground_truth = replace(initial_pose) if initial_pose else PredictorState()
        self._step = 0
        self._history = []
        for predictor in self._predictors.values():
            predictor.reset()
            predictor.update_state(self._ground_truth)
        state = SimState(
            step=0,
            time=0.0,
            ground_truth=replace(self._ground_truth),
            predictor_states={
                name: replace(p.state) for name, p in self._predictors.items()
            },
            applied_control=np.zeros(2, dtype=np.float64),
            collision=False,
        )
        self._history.append(state)
        return state

    def step(self, control: np.ndarray) -> SimState:
        if self._step >= self._config.max_steps:
            raise RuntimeError("Simulator is already done; call reset() first")
        ctrl = np.asarray(control, dtype=np.float64).reshape(-1)
        if ctrl.shape != (2,):
            raise ValueError(f"control must have shape (2,); got {ctrl.shape}")

        cfg = self._config
        self._ground_truth = self._bicycle_owner.bicycle_step(
            self._ground_truth,
            ControlInput(velocity=float(ctrl[0]), steering=float(ctrl[1])),
        )
        collision = self._check_collision(self._ground_truth)

        # Update each predictor's internal state estimate from ground truth.
        for predictor in self._predictors.values():
            predictor.update_state(self._ground_truth)

        self._step += 1
        sim_state = SimState(
            step=self._step,
            time=self._step * cfg.dt,
            ground_truth=replace(self._ground_truth),
            predictor_states={
                name: replace(p.state) for name, p in self._predictors.items()
            },
            applied_control=ctrl.copy(),
            collision=collision,
        )
        self._history.append(sim_state)
        return sim_state

    # --- helpers ---

    def _check_collision(self, state: PredictorState) -> bool:
        for obs in self._config.obstacles:
            dx = state.x - obs.x
            dy = state.y - obs.y
            if dx * dx + dy * dy < obs.radius * obs.radius:
                return True
        return False

    def get_history(self) -> List[SimState]:
        return list(self._history)

    def is_done(self) -> bool:
        if not self._history:
            return False
        return (
            self._step >= self._config.max_steps or self._history[-1].collision
        )

    @property
    def ground_truth(self) -> PredictorState:
        return replace(self._ground_truth)

    @property
    def predictors(self) -> Dict[str, BasePredictor]:
        return self._predictors
