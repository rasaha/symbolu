"""Tests for bcvf_autonomous.manifold — DESIGN.md Section 1.3.1."""

from __future__ import annotations

import math

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.manifold import (
    SE2Pose,
    body_frame_error,
    compose,
    inverse,
    wrap_angle,
)


IDENTITY = SE2Pose(x=0.0, y=0.0, theta=0.0)


def _assert_pose_close(a: SE2Pose, b: SE2Pose, tol: float = 1e-9) -> None:
    assert abs(a.x - b.x) < tol
    assert abs(a.y - b.y) < tol
    assert abs(wrap_angle(a.theta - b.theta)) < tol


# --- wrap_angle ---


@pytest.mark.parametrize("angle", [-math.pi + 1e-9, -1.0, 0.0, 0.5, math.pi - 1e-9])
def test_wrap_angle_identity(angle: float) -> None:
    assert wrap_angle(angle) == pytest.approx(angle, abs=1e-12)


def test_wrap_angle_overflow() -> None:
    assert wrap_angle(2 * math.pi) == pytest.approx(0.0, abs=1e-12)
    assert wrap_angle(-3 * math.pi) == pytest.approx(math.pi, abs=1e-12) or wrap_angle(
        -3 * math.pi
    ) == pytest.approx(-math.pi, abs=1e-12)


def test_wrap_angle_boundary() -> None:
    # atan2(sin(pi), cos(pi)) returns pi exactly; both +pi and -pi represent
    # the same point on the circle. Accept either as "wrapped".
    result = wrap_angle(math.pi)
    assert result == pytest.approx(math.pi, abs=1e-12) or result == pytest.approx(
        -math.pi, abs=1e-12
    )


# --- compose / inverse ---


def test_compose_identity() -> None:
    a = SE2Pose(x=1.0, y=2.0, theta=0.3)
    _assert_pose_close(compose(a, IDENTITY), a)
    _assert_pose_close(compose(IDENTITY, a), a)


def test_compose_inverse() -> None:
    a = SE2Pose(x=1.5, y=-0.25, theta=0.9)
    _assert_pose_close(compose(a, inverse(a)), IDENTITY)
    _assert_pose_close(compose(inverse(a), a), IDENTITY)


def test_inverse_inverse() -> None:
    a = SE2Pose(x=-0.3, y=4.2, theta=-2.1)
    _assert_pose_close(inverse(inverse(a)), a)


# --- body_frame_error ---


def test_body_frame_error_zero() -> None:
    a = SE2Pose(x=1.0, y=2.0, theta=0.7)
    e = body_frame_error(a, a, lever_arm=2.5)
    assert np.allclose(e, np.zeros(3), atol=1e-12)


def test_body_frame_error_pure_translation() -> None:
    # j heading aligned with world x; i offset +1m ahead of j.
    pose_i = SE2Pose(x=1.0, y=0.0, theta=0.0)
    pose_j = SE2Pose(x=0.0, y=0.0, theta=0.0)
    e = body_frame_error(pose_i, pose_j, lever_arm=2.5)
    assert e == pytest.approx(np.array([1.0, 0.0, 0.0]), abs=1e-12)


def test_body_frame_error_pure_rotation() -> None:
    pose_i = SE2Pose(x=0.0, y=0.0, theta=0.1)
    pose_j = SE2Pose(x=0.0, y=0.0, theta=0.0)
    L = 2.5
    e = body_frame_error(pose_i, pose_j, lever_arm=L)
    assert e == pytest.approx(np.array([0.0, 0.0, 0.1 * L]), abs=1e-12)


def test_body_frame_error_lever_arm() -> None:
    pose_i = SE2Pose(x=0.0, y=0.0, theta=0.2)
    pose_j = SE2Pose(x=0.0, y=0.0, theta=0.0)
    e1 = body_frame_error(pose_i, pose_j, lever_arm=2.5)
    e2 = body_frame_error(pose_i, pose_j, lever_arm=5.0)
    assert e2[2] == pytest.approx(2.0 * e1[2], abs=1e-12)
    assert e1[0] == pytest.approx(e2[0], abs=1e-12)
    assert e1[1] == pytest.approx(e2[1], abs=1e-12)


def test_body_frame_error_body_frame() -> None:
    # j is heading north (theta=pi/2); i is 1m east of j in world frame.
    # In j's body frame, east is "to the right" -> (dx_body=0, dy_body=-1).
    pose_i = SE2Pose(x=1.0, y=0.0, theta=math.pi / 2)
    pose_j = SE2Pose(x=0.0, y=0.0, theta=math.pi / 2)
    e = body_frame_error(pose_i, pose_j, lever_arm=2.5)
    assert e[0] == pytest.approx(0.0, abs=1e-12)
    assert e[1] == pytest.approx(-1.0, abs=1e-12)
    assert e[2] == pytest.approx(0.0, abs=1e-12)
