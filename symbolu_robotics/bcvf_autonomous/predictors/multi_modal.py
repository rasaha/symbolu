"""Multi-modal predictor adapter — thin shim that lifts non-SE(2)
predictor outputs to the kernel's canonical SE(2) world-frame.

See ``MULTI_MODAL_PREDICTORS_DESIGN.md`` for the load-bearing
research finding: **Lemma 1 invariance carries through this shim
on straight-lane segments only**; curved lanes break it because
lane-tangent rotation introduces curvature-dependent terms in the
SE(2) trajectory's second derivative. The deployment partner
restricts to straight-lane segments or applies a lane-curvature-
aware gate threshold for the multi-modal mode.

Public surface:

* :class:`MultiModalPredictor` — pairs a native-state-space
  trajectory with the metadata needed to lift it (state space +
  optional :class:`~.state_space.LaneAnchor`).
* :func:`lane_frame_to_se2` — convert one ``(H, 3)`` lane-frame
  trajectory ``[s, d, psi]`` to SE(2) world-frame.
* :func:`se2_to_lane_frame` — the inverse, used for round-trip
  identity tests + for projecting an SE(2) ground-truth into the
  lane frame for adapter validation.
* :func:`unify_to_se2_bundle` — apply each predictor's transform
  and stack the result into the ``(M, H, 3)`` SE(2) tensor the
  kernel consumes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from ..manifold import wrap_angle
from .state_space import LaneAnchor, PredictorStateSpace


@dataclass(frozen=True)
class MultiModalPredictor:
    """One predictor's contribution to a multi-modal bundle.

    Args:
        trajectory: ``(H, 3)`` array in the predictor's native state
            space (SE(2) world-frame, lane-frame, ...).
        state_space: which :class:`PredictorStateSpace` ``trajectory``
            lives in. The bundle adapter dispatches on this value.
        lane_anchor: required when ``state_space == LANE_FRAME``;
            otherwise must be ``None``.
    """

    trajectory: np.ndarray
    state_space: PredictorStateSpace
    lane_anchor: Optional[LaneAnchor] = None

    def __post_init__(self) -> None:
        traj = np.asarray(self.trajectory, dtype=np.float64)
        if traj.ndim != 2 or traj.shape[1] != 3:
            raise ValueError(
                f"trajectory must be (H, 3); got {traj.shape}"
            )
        object.__setattr__(self, "trajectory", traj)
        # Lane-frame requires an anchor; SE(2) world-frame must not
        # carry one (it would be silently ignored — fail loud).
        if self.state_space == PredictorStateSpace.LANE_FRAME:
            if self.lane_anchor is None:
                raise ValueError(
                    "state_space=LANE_FRAME requires a lane_anchor"
                )
        elif self.lane_anchor is not None:
            raise ValueError(
                f"state_space={self.state_space.value} must not carry "
                "a lane_anchor; only LANE_FRAME consumes one"
            )


def lane_frame_to_se2(
    lane_traj: np.ndarray,
    anchor: LaneAnchor,
) -> np.ndarray:
    """Convert a lane-frame trajectory to SE(2) world-frame.

    Args:
        lane_traj: ``(H, 3)`` ``[s, d, psi]`` — arc length along the
            anchor's centerline, signed lateral offset (left = +d),
            heading relative to the lane direction.
        anchor: the lane geometry the trajectory references.

    Returns:
        ``(H, 3)`` SE(2) ``[x, y, theta]`` world-frame trajectory.
    """
    traj = np.asarray(lane_traj, dtype=np.float64)
    if traj.ndim != 2 or traj.shape[1] != 3:
        raise ValueError(
            f"lane_traj must be (H, 3); got {traj.shape}"
        )
    H = traj.shape[0]
    out = np.zeros_like(traj)
    for h in range(H):
        s, d, psi = traj[h]
        x_lane, y_lane, theta_lane = anchor.s_to_world(float(s))
        # Lateral offset is perpendicular to the lane tangent; left of
        # the lane (positive d) is rotated +pi/2 from the tangent.
        out[h, 0] = x_lane - d * np.sin(theta_lane)
        out[h, 1] = y_lane + d * np.cos(theta_lane)
        out[h, 2] = wrap_angle(theta_lane + psi)
    return out


def se2_to_lane_frame(
    se2_traj: np.ndarray,
    anchor: LaneAnchor,
) -> np.ndarray:
    """Convert an SE(2) world-frame trajectory to lane-frame.

    For each pose, finds the closest point on the anchor's polyline,
    extracts the arc length ``s`` and signed lateral offset ``d``,
    and computes the heading delta ``psi`` against the lane tangent.

    Used for round-trip identity tests + as the projection an
    adversarial spoofing detector at the deployment-partner layer
    might apply when comparing a lane-frame predictor against an
    SE(2) ground truth.
    """
    traj = np.asarray(se2_traj, dtype=np.float64)
    if traj.ndim != 2 or traj.shape[1] != 3:
        raise ValueError(
            f"se2_traj must be (H, 3); got {traj.shape}"
        )
    H = traj.shape[0]
    out = np.zeros_like(traj)
    centerline = anchor.centerline   # (N, 3)
    arc = anchor.arc_lengths          # (N,)
    for h in range(H):
        x, y, theta = traj[h]
        # Project the world-frame point onto every centerline segment
        # and pick the closest projection.
        best_dist2 = np.inf
        best = (0.0, 0.0, 0.0)
        for i in range(centerline.shape[0] - 1):
            x0, y0 = centerline[i, 0], centerline[i, 1]
            x1, y1 = centerline[i + 1, 0], centerline[i + 1, 1]
            dx, dy = x1 - x0, y1 - y0
            seg_len2 = dx * dx + dy * dy
            if seg_len2 == 0.0:
                continue
            t = ((x - x0) * dx + (y - y0) * dy) / seg_len2
            t = max(0.0, min(1.0, t))
            px, py = x0 + t * dx, y0 + t * dy
            dist2 = (x - px) ** 2 + (y - py) ** 2
            if dist2 < best_dist2:
                # Arc length at the projection.
                s = arc[i] + t * (arc[i + 1] - arc[i])
                # Lane tangent at the projection (segment direction).
                seg_theta = float(np.arctan2(dy, dx))
                # Signed lateral offset: left (positive d) is rotated
                # +pi/2 from tangent. Cross-product sign tells us which
                # side the world point is on.
                d_signed = (
                    -np.sin(seg_theta) * (x - px)
                    + np.cos(seg_theta) * (y - py)
                )
                psi = wrap_angle(theta - seg_theta)
                best = (s, d_signed, psi)
                best_dist2 = dist2
        out[h, 0] = best[0]
        out[h, 1] = best[1]
        out[h, 2] = best[2]
    return out


def unify_to_se2_bundle(
    predictors: Sequence[MultiModalPredictor],
) -> np.ndarray:
    """Stack a multi-modal bundle into the kernel's ``(M, H, 3)`` SE(2) tensor.

    Each predictor is dispatched on its ``state_space``:

    * ``SE2_WORLD`` — passed through unchanged.
    * ``LANE_FRAME`` — lifted via :func:`lane_frame_to_se2` using the
      paired :class:`LaneAnchor`.

    All predictors must agree on the horizon ``H``; mismatched
    horizons raise ``ValueError`` at the boundary rather than
    propagating into a kernel call that will misalign per-step costs.
    """
    if not predictors:
        raise ValueError("bundle must contain at least one predictor")
    horizons = {p.trajectory.shape[0] for p in predictors}
    if len(horizons) != 1:
        raise ValueError(
            f"all predictors must agree on horizon H; got {sorted(horizons)}"
        )
    out = []
    for p in predictors:
        if p.state_space == PredictorStateSpace.SE2_WORLD:
            out.append(p.trajectory)
        elif p.state_space == PredictorStateSpace.LANE_FRAME:
            assert p.lane_anchor is not None   # post_init enforces
            out.append(lane_frame_to_se2(p.trajectory, p.lane_anchor))
        else:
            raise NotImplementedError(
                f"state_space {p.state_space} is not supported by the "
                "multi-modal V1 thin-shim adapter; see "
                "MULTI_MODAL_PREDICTORS_DESIGN.md §4 for the supported set"
            )
    return np.stack(out, axis=0)
