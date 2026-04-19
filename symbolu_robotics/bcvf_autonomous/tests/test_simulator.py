"""Tests for bcvf_autonomous.simulator — DESIGN.md §3A.10."""

from __future__ import annotations

import math

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.predictors import create_predictor_set
from symbolu_robotics.bcvf_autonomous.simulator import (
    Obstacle,
    SimConfig,
    Simulator,
    make_curved_road,
    make_straight_road,
    make_urban_road,
)


def _config(**overrides) -> SimConfig:
    cfg = SimConfig()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def test_straight_drive_no_collision() -> None:
    predictors = create_predictor_set(seed=0)
    sim = Simulator(_config(max_steps=30), predictors)
    sim.reset()
    for _ in range(30):
        sim.step(np.array([5.0, 0.0]))
    assert not sim.is_done() or sim.get_history()[-1].collision is False
    # All recorded states should have collision=False.
    assert not any(s.collision for s in sim.get_history())


def test_collision_detection() -> None:
    predictors = create_predictor_set(seed=0)
    obs = [Obstacle(x=10.0, y=0.0, radius=1.5)]
    sim = Simulator(_config(obstacles=obs, max_steps=50), predictors)
    sim.reset()
    collided = False
    for _ in range(50):
        state = sim.step(np.array([8.0, 0.0]))
        if state.collision:
            collided = True
            break
    assert collided
    assert sim.is_done()


def test_predictor_states_updated() -> None:
    predictors = create_predictor_set(seed=0)
    sim = Simulator(_config(max_steps=10), predictors)
    sim.reset()
    before = {name: p.state.x for name, p in predictors.items()}
    sim.step(np.array([5.0, 0.0]))
    after = {name: p.state.x for name, p in predictors.items()}
    # Each predictor's x should have advanced by ~0.5m (5 m/s * 0.1 s).
    for name in predictors:
        assert after[name] > before[name] + 0.4


def test_history_length() -> None:
    predictors = create_predictor_set(seed=0)
    sim = Simulator(_config(max_steps=15), predictors)
    sim.reset()
    for _ in range(10):
        sim.step(np.array([3.0, 0.05]))
    # Initial state + 10 steps = 11 entries.
    assert len(sim.get_history()) == 11


def test_deterministic_replay() -> None:
    controls = [np.array([4.0, 0.1]) for _ in range(20)]

    def run() -> np.ndarray:
        predictors = create_predictor_set(seed=7)
        sim = Simulator(_config(max_steps=20, seed=7), predictors)
        sim.reset()
        for c in controls:
            sim.step(c)
        return np.stack([
            np.array([s.ground_truth.x, s.ground_truth.y, s.ground_truth.theta])
            for s in sim.get_history()
        ])

    a = run()
    b = run()
    assert np.array_equal(a, b)


def test_road_centerline_geometry() -> None:
    straight = make_straight_road(length=100.0, spacing=1.0)
    assert straight.centerline.ndim == 2
    assert straight.centerline.shape[1] == 2
    assert np.allclose(straight.centerline[:, 1], 0.0)
    assert straight.centerline[0, 0] == pytest.approx(0.0)
    assert straight.centerline[-1, 0] == pytest.approx(100.0)

    curved = make_curved_road(radius=50.0, arc_degrees=90.0)
    # Start at (0, 0), end at (R, R) for a 90° arc from origin heading +x.
    assert curved.centerline[0, 0] == pytest.approx(0.0, abs=1e-6)
    assert curved.centerline[0, 1] == pytest.approx(0.0, abs=1e-6)
    assert curved.centerline[-1, 0] == pytest.approx(50.0, abs=1e-3)
    assert curved.centerline[-1, 1] == pytest.approx(50.0, abs=1e-3)
    # All arc points should be distance R from (0, R).
    radii = np.hypot(curved.centerline[:, 0], curved.centerline[:, 1] - 50.0)
    assert np.allclose(radii, 50.0, atol=1e-6)

    urban = make_urban_road(blocks=3, block_size=20.0)
    assert urban.centerline.shape[0] > 10


def test_reset_clears_state() -> None:
    predictors = create_predictor_set(seed=0)
    sim = Simulator(_config(max_steps=20), predictors)
    sim.reset()
    for _ in range(5):
        sim.step(np.array([3.0, 0.0]))
    assert len(sim.get_history()) == 6

    sim.reset()
    assert len(sim.get_history()) == 1  # only the initial state
    assert sim.get_history()[0].step == 0
    assert not sim.is_done()
