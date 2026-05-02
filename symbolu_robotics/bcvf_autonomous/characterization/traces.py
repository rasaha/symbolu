"""Synthetic SE(2) trace families for BCVF autonomous characterization.

Seven canonical families, each producing an ``(M, H, 3)`` predictor
bundle with an optional truth label (the index of the predictor that
should be attributed the disagreement) and an optional valid-mask
``(M, H)`` for sensor-dropout families.

Construction notes:

* ``baseline`` is identical predictors with no perturbation. BCVF
  cost should be ~0.
* ``constant_bias`` and ``linear_drift`` perturb predictor 1's
  position. Body-frame disagreement is constant or linear in time,
  so SECOND-order BCVF cost is exactly zero. The §3 ablation grid
  uses these two families to confirm only SECOND-order rejects them.
* ``accelerating`` perturbs predictor 1 with a quadratic position
  offset → constant body-frame acceleration. BCVF must fire and
  attribute to predictor 1.
* ``noise_floor`` adds IID per-step Gaussian noise to every
  predictor's position. The gate threshold ``T`` should suppress
  the cost when ``sigma_noise`` is small.
* ``outlier`` perturbs predictor 0 with a higher-magnitude
  quadratic offset; predictors 1 and 2 stay nominal. Truth label =
  0. The hit / margin / rank metrics are the headline outlier-
  attribution diagnostic.
* ``sensor_dropout`` wraps an outer family and freezes one
  predictor's pose after step ``k_dropout``. This is the
  autonomous analog of LLM EOS truncation. The frozen predictor
  diverges from the others as they continue propagating, which
  makes BCVF fire even on top of a `baseline` outer; combined with
  an outer that already has signal it provides a stress test of
  attribution under partial observability.

RNG discipline: one ``default_rng(seed)`` per call; draws happen in
fixed order (base → noise) so trace generation is reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np

from ..manifold import wrap_angle


_VALID_FAMILIES: Tuple[str, ...] = (
    "baseline",
    "constant_bias",
    "linear_drift",
    "accelerating",
    "noise_floor",
    "outlier",
    "sensor_dropout",
)

# Which families are nominal (BCVF should stay quiet) vs failure
# (BCVF should fire). Used by the sweep summary to tally per-family
# false-positive vs false-negative rates.
NOMINAL_FAMILIES: Tuple[str, ...] = (
    "baseline",
    "constant_bias",
    "linear_drift",
    "noise_floor",
)
FAILURE_FAMILIES: Tuple[str, ...] = (
    "accelerating",
    "outlier",
    "sensor_dropout",
)


@dataclass
class TraceBundle:
    """One synthetic trace bundle for the characterization sweep."""

    family: str
    trajectories: np.ndarray              # (M, H, 3) SE(2) [x, y, theta]
    truth_label: Optional[int]            # outlier predictor index, or None
    valid_masks: Optional[np.ndarray]     # (M, H) bool, or None
    metadata: Dict[str, Any] = field(default_factory=dict)


def _zero_bundle(M: int, H: int) -> np.ndarray:
    return np.zeros((M, H, 3), dtype=np.float64)


def _straight_baseline(M: int, H: int, dt: float, v: float) -> np.ndarray:
    """All predictors travel along the +x axis at constant velocity ``v``."""
    base = np.zeros((H, 3), dtype=np.float64)
    base[:, 0] = v * dt * np.arange(H, dtype=np.float64)
    return np.broadcast_to(base[None, :, :], (M, H, 3)).copy()


def generate_trace(
    family: str,
    M: int = 3,
    H: int = 50,
    dt: float = 0.1,
    seed: int = 0,
    base_velocity: float = 5.0,
    **family_params: Any,
) -> TraceBundle:
    """Generate a reproducible ``(M, H, 3)`` predictor bundle for ``family``.

    The bundle's nominal motion is a straight line along +x at
    ``base_velocity``; perturbations are layered on top of that so
    body-frame errors stay numerically clean (theta_j = 0 ⇒ the body
    frame coincides with the world frame).
    """
    if family not in _VALID_FAMILIES:
        raise ValueError(
            f"unknown family {family!r}; expected one of {_VALID_FAMILIES}"
        )
    if M < 2:
        raise ValueError(f"M must be >= 2; got {M}")
    if H < 3:
        raise ValueError(f"H must be >= 3; got {H}")

    rng = np.random.default_rng(seed=seed)
    trajectories = _straight_baseline(M, H, dt, base_velocity)
    metadata: Dict[str, Any] = {
        "family": family,
        "M": M,
        "H": H,
        "dt": dt,
        "seed": seed,
        "base_velocity": base_velocity,
    }
    metadata.update(family_params)

    truth_label: Optional[int] = None
    valid_masks: Optional[np.ndarray] = None

    ks = np.arange(H, dtype=np.float64)

    if family == "baseline":
        pass

    elif family == "constant_bias":
        bias = float(family_params.get("bias", 0.5))
        bias_axis = str(family_params.get("axis", "y"))
        target = int(family_params.get("target_predictor", 1))
        col = 1 if bias_axis == "y" else 0
        trajectories[target, :, col] += bias

    elif family == "linear_drift":
        rate = float(family_params.get("drift_rate", 0.05))
        target = int(family_params.get("target_predictor", 1))
        trajectories[target, :, 1] += rate * ks * dt

    elif family == "accelerating":
        accel = float(family_params.get("accel_mag", 0.5))
        target = int(family_params.get("target_predictor", 1))
        trajectories[target, :, 1] += 0.5 * accel * (ks * dt) ** 2
        truth_label = target

    elif family == "noise_floor":
        sigma = float(family_params.get("sigma_noise", 0.01))
        noise = rng.normal(loc=0.0, scale=sigma, size=(M, H, 2))
        trajectories[:, :, :2] += noise

    elif family == "outlier":
        accel = float(family_params.get("accel_mag", 1.0))
        target = int(family_params.get("target_predictor", 0))
        trajectories[target, :, 1] += 0.5 * accel * (ks * dt) ** 2
        truth_label = target

    elif family == "sensor_dropout":
        outer = str(family_params.get("outer_family", "outlier"))
        k_dropout = int(family_params.get("k_dropout", H // 2))
        dropped = int(family_params.get("dropped_predictor", 2))
        if outer == "sensor_dropout":
            raise ValueError("sensor_dropout cannot wrap itself")
        if not (0 <= k_dropout < H):
            raise ValueError(
                f"k_dropout must lie in [0, {H}); got {k_dropout}"
            )
        if not (0 <= dropped < M):
            raise ValueError(
                f"dropped_predictor must lie in [0, {M}); got {dropped}"
            )
        outer_params = {
            k: v for k, v in family_params.items()
            if k not in ("outer_family", "k_dropout", "dropped_predictor")
        }
        outer_bundle = generate_trace(
            family=outer,
            M=M,
            H=H,
            dt=dt,
            seed=seed,
            base_velocity=base_velocity,
            **outer_params,
        )
        trajectories = outer_bundle.trajectories.copy()
        # Freeze the dropped predictor's pose at step k_dropout for all
        # subsequent steps — emulates a sensor whose stream stops and
        # whose downstream estimator holds the last valid pose.
        if k_dropout < H - 1:
            trajectories[dropped, k_dropout + 1:, :] = trajectories[
                dropped, k_dropout, :
            ]
        valid_masks = np.ones((M, H), dtype=bool)
        valid_masks[dropped, k_dropout + 1:] = False
        # Truth label is the dropped predictor — that's where BCVF
        # should attribute the new disagreement, on top of whatever
        # outer attribution already exists.
        truth_label = dropped
        metadata["outer_family"] = outer
        metadata["k_dropout"] = k_dropout
        metadata["dropped_predictor"] = dropped
        if outer_bundle.truth_label is not None:
            metadata["outer_truth_label"] = outer_bundle.truth_label

    # Wrap heading just in case any kwarg requested a heading offset.
    trajectories[..., 2] = np.vectorize(wrap_angle)(trajectories[..., 2])

    return TraceBundle(
        family=family,
        trajectories=trajectories,
        truth_label=truth_label,
        valid_masks=valid_masks,
        metadata=metadata,
    )
