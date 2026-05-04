"""Predictor state-space taxonomy + lane-frame anchor geometry.

The base BCVF kernel consumes ``(M, H, 3)`` SE(2) world-frame
trajectories from M predictors. Production sensor stacks include
predictors that natively output in **non-SE(2)** coordinates:

* HD-map-anchored: ``(s, d, psi)`` lane-frame coordinates — arc
  length along the lane centerline, signed lateral offset, heading
  relative to the lane direction.
* Lane-detection cameras: similar lane-relative output.
* Map-relative SLAM: pose in the map's coordinate frame, which may
  differ from the canonical world frame by a rigid-body transform.

For multi-modal arbitration, two architectural options exist (see
``MULTI_MODAL_PREDICTORS_DESIGN.md`` §3):

1. **Thin-shim adapter** (this module). Convert at the boundary —
   each non-SE(2) predictor is paired with a transform that lifts
   its native trajectory to SE(2) world-frame; the kernel runs
   unchanged. **Lemma 1 invariance carries on straight-lane
   segments only**; curved lanes break it (see §4.2).
2. **Native multi-modal kernel** (research, out of scope). Define
   disagreement directly in a chosen common manifold; the second-
   derivative invariance properties on a curved manifold are a
   non-trivial extension of the SE(2) Lemma 1 proof.

This module ships the thin-shim adapter as the V1 mechanism. The
SOTIF clause-5 functional spec gains the new surfaces; the
deployment partner restricts to straight-lane segments or applies
a lane-curvature-aware gate threshold for the multi-modal mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

import numpy as np


class PredictorStateSpace(Enum):
    """Native state space a predictor emits its trajectory in.

    The kernel boundary expects SE(2) world-frame; predictors in
    other state spaces are paired with a transform via
    :class:`~symbolu_robotics.bcvf_autonomous.predictors.multi_modal.MultiModalPredictor`.
    """

    SE2_WORLD = "se2_world"
    """Standard SE(2) world-frame ``[x, y, theta]``. The kernel's
    canonical input space — no transform needed."""

    LANE_FRAME = "lane_frame"
    """Lane-frame ``[s, d, psi]`` — arc length along a lane
    centerline, signed lateral offset (left = +d), heading relative
    to the lane direction. Requires a paired :class:`LaneAnchor`."""


@dataclass(frozen=True)
class LaneAnchor:
    """Lane geometry: a polyline of SE(2) world-frame waypoints + the
    cumulative arc length at each waypoint.

    A :class:`LaneAnchor` is the second argument to the lane-frame
    transform. The two factory methods cover the cases the multi-
    modal V1 actually exercises:

    * :meth:`straight_x_axis` — a straight lane along ``+x`` at
      ``y = 0``. The Lemma-1 carry-through case where the thin-shim
      preserves invariance bit-exact (see DESIGN.md §4.1).
    * :meth:`constant_curvature` — a circular arc lane. The
      Lemma-1-break case the design doc names — invariance fails
      because lane-tangent rotation introduces curvature-dependent
      terms in the SE(2) trajectory's second derivative.

    Real deployment uses :meth:`from_waypoints` against the map
    provider's polyline.
    """

    centerline: np.ndarray   # (N, 3) — world-frame [x, y, theta] waypoints
    arc_lengths: np.ndarray  # (N,) — cumulative arc length at each waypoint

    def __post_init__(self) -> None:
        c = np.asarray(self.centerline, dtype=np.float64)
        a = np.asarray(self.arc_lengths, dtype=np.float64)
        if c.ndim != 2 or c.shape[1] != 3:
            raise ValueError(
                f"centerline must be (N, 3); got {c.shape}"
            )
        if a.ndim != 1 or a.shape[0] != c.shape[0]:
            raise ValueError(
                f"arc_lengths must have length N={c.shape[0]}; got {a.shape}"
            )
        if c.shape[0] < 2:
            raise ValueError(
                f"need at least 2 waypoints; got {c.shape[0]}"
            )
        # Arc lengths must be non-decreasing (strict-monotone in
        # practice; equal arc lengths would imply a duplicated
        # waypoint and break linear interpolation).
        if not np.all(np.diff(a) > 0):
            raise ValueError(
                "arc_lengths must be strictly increasing (no duplicated "
                "waypoints)"
            )
        # Mutate via object.__setattr__ since the dataclass is frozen.
        object.__setattr__(self, "centerline", c)
        object.__setattr__(self, "arc_lengths", a)

    @property
    def total_length(self) -> float:
        return float(self.arc_lengths[-1])

    @property
    def n_waypoints(self) -> int:
        return int(self.centerline.shape[0])

    def s_to_world(self, s: float) -> Tuple[float, float, float]:
        """Look up world-frame ``(x, y, theta_lane)`` at arc length ``s``.

        ``s`` outside ``[0, total_length]`` is clipped to the boundary
        — straight extrapolation past the centerline is intentionally
        not supported in V1; the multi-modal mode is documented as
        valid only when the predictor's lane-frame ``s`` stays inside
        the anchor's range.
        """
        s = float(np.clip(s, 0.0, self.total_length))
        idx = int(np.searchsorted(self.arc_lengths, s, side="right") - 1)
        idx = max(0, min(idx, self.n_waypoints - 2))
        s0 = self.arc_lengths[idx]
        s1 = self.arc_lengths[idx + 1]
        t = 0.0 if s1 == s0 else (s - s0) / (s1 - s0)
        wp0 = self.centerline[idx]
        wp1 = self.centerline[idx + 1]
        x = (1.0 - t) * wp0[0] + t * wp1[0]
        y = (1.0 - t) * wp0[1] + t * wp1[1]
        # Headings interpolated via atan2 so we stay on the circle.
        sin_th = (1.0 - t) * np.sin(wp0[2]) + t * np.sin(wp1[2])
        cos_th = (1.0 - t) * np.cos(wp0[2]) + t * np.cos(wp1[2])
        theta = float(np.arctan2(sin_th, cos_th))
        return x, y, theta

    @classmethod
    def from_waypoints(cls, waypoints: np.ndarray) -> "LaneAnchor":
        """Build a :class:`LaneAnchor` from ``(N, 2)`` ``[x, y]`` waypoints.

        Tangent angles are computed as the angle of the segment
        leaving each waypoint; the last waypoint inherits the
        previous segment's tangent (no segment to point at).
        """
        wp = np.asarray(waypoints, dtype=np.float64)
        if wp.ndim != 2 or wp.shape[1] != 2:
            raise ValueError(
                f"waypoints must be (N, 2); got {wp.shape}"
            )
        if wp.shape[0] < 2:
            raise ValueError(
                f"need at least 2 waypoints; got {wp.shape[0]}"
            )
        diffs = np.diff(wp, axis=0)
        seg_lengths = np.linalg.norm(diffs, axis=1)
        if not np.all(seg_lengths > 0):
            raise ValueError(
                "consecutive waypoints must be distinct (zero-length "
                "segments not allowed)"
            )
        cum_lengths = np.concatenate(
            [[0.0], np.cumsum(seg_lengths)]
        )
        seg_thetas = np.arctan2(diffs[:, 1], diffs[:, 0])
        # Each waypoint's tangent = direction of the segment leaving
        # it; last waypoint reuses the prior segment's tangent.
        thetas = np.concatenate([seg_thetas, [seg_thetas[-1]]])
        centerline = np.column_stack([wp, thetas])
        return cls(centerline=centerline, arc_lengths=cum_lengths)

    @classmethod
    def straight_x_axis(
        cls, length: float = 100.0, n: int = 11,
    ) -> "LaneAnchor":
        """Straight lane along ``+x`` at ``y = 0`` of total length ``length``.

        The Lemma-1-clean case: every waypoint has ``theta = 0``, so
        a constant lane-frame lateral offset ``d`` translates to a
        constant SE(2) ``y`` offset and the kernel's second-order
        invariance carries through.
        """
        if length <= 0:
            raise ValueError(f"length must be > 0; got {length}")
        if n < 2:
            raise ValueError(f"need at least 2 waypoints; got n={n}")
        xs = np.linspace(0.0, length, n)
        wp = np.column_stack([xs, np.zeros(n)])
        return cls.from_waypoints(wp)

    @classmethod
    def constant_curvature(
        cls, radius: float, arc_length: float = 50.0, n: int = 51,
    ) -> "LaneAnchor":
        """Circular-arc lane of given ``radius``, sampled at ``n`` points.

        Lane starts at the origin tangent to ``+x``; centre of curvature
        is at ``(0, radius)`` (positive radius curves left). Used by
        the Lemma-1-break demonstration in DESIGN.md §4.2 and the
        ``test_curved_lane_breaks_lemma_1_invariance`` regression pin.
        """
        if radius == 0.0:
            raise ValueError("radius must be non-zero")
        if arc_length <= 0:
            raise ValueError(f"arc_length must be > 0; got {arc_length}")
        if n < 2:
            raise ValueError(f"need at least 2 waypoints; got n={n}")
        sgn = 1.0 if radius > 0 else -1.0
        r = abs(radius)
        s = np.linspace(0.0, arc_length, n)
        # Angle subtended at curve centre, signed by the radius.
        phi = sgn * (s / r)
        # Centre of curvature at (0, sgn*r); arc starts at origin
        # heading +x, ends at (r*sin(|phi|), sgn*r*(1-cos(|phi|))).
        x = r * np.sin(np.abs(phi)) * 1.0
        y = sgn * r * (1.0 - np.cos(np.abs(phi)))
        wp = np.column_stack([x, y])
        return cls.from_waypoints(wp)
