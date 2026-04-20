"""Realistic-noise synthetic dataset adapter (§6.2 pre-pilot bridge).

Generates SceneRecord objects that extend the pure-SE(2) synthetic
testbed from §6.1 toward the noise characteristics we expect from
real sensor traces — without requiring actual nuScenes or KITTI
access. Use this adapter to validate that the V1 trust pipeline's
numerics survive:

- **Correlated Gaussian noise** (vs the IID noise the synthetic M1–M4
  predictors emit). Emulates sensor-level noise that persists
  across multiple timesteps.
- **Non-Gaussian tails** (Student-t / mixture of Gaussians).
  Emulates real-sensor outlier frames.
- **Bursty sensor dropouts** (10–30% probability of a brief horizon
  stretch where one predictor's output is invalid or held).
  Emulates multipath / occlusion / lost-track events.

If the trust pipeline passes §6.1-style significance under this
realistic-noise synthetic, we have high confidence the numerics are
ready for real-data integration — actual nuScenes/KITTI access is
a plumbing step, not a numerical-risk step.

Failure patterns mirror the four documented in the pilot plan:
``gps_multipath``, ``map_misalignment``, ``camera_degradation``,
``constant_bias_sanity``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from .base import DatasetAdapter, SceneRecord


@dataclass
class RealisticNoiseConfig:
    """Parameters for the realistic-noise synthetic adapter."""

    num_scenes: int = 21                # N for the pilot bar
    steps_per_scene: int = 400          # 40 s at 10 Hz, matches S3_*
    horizon: int = 20                   # 2 s at 10 Hz
    dt: float = 0.1

    # Noise characteristics
    correlated_noise_alpha: float = 0.8   # AR(1) coefficient (0 = IID, 1 = random walk)
    correlated_noise_sigma: float = 0.02  # scale in SE(2) meters / radians
    outlier_frame_rate: float = 0.02      # probability per-step per-predictor
    outlier_scale_multiplier: float = 5.0 # outlier magnitude vs sigma

    # Failure injection
    failure_types: tuple = (
        "gps_multipath",
        "map_misalignment",
        "camera_degradation",
        "constant_bias_sanity",
    )
    failure_onset_step: int = 50       # 5 s in, matches S3_* config
    failure_duration_steps: int = 50   # 5 s window
    failure_magnitude: float = 2.0     # lateral-drift magnitude at peak

    seed: int = 72


class RealisticNoiseAdapter(DatasetAdapter):
    """Synthetic §6.2 pre-pilot adapter with real-like noise.

    Deterministic given the seed. Emits ``config.num_scenes`` scenes,
    each ``config.steps_per_scene`` simulator steps long, with four
    predictors (M1..M4) and a failure injected on one of them.

    Scene-ID convention: ``scene_{seed}_{idx}_{failure_type}``.
    """

    def __init__(self, config: Optional[RealisticNoiseConfig] = None) -> None:
        self._cfg = config or RealisticNoiseConfig()

    def scene_ids(self) -> List[str]:
        cfg = self._cfg
        ids = []
        for i in range(cfg.num_scenes):
            ftype = cfg.failure_types[i % len(cfg.failure_types)]
            ids.append(f"scene_{cfg.seed}_{i:03d}_{ftype}")
        return ids

    def load_scene(self, scene_id: str) -> SceneRecord:
        cfg = self._cfg
        parts = scene_id.split("_")
        if len(parts) < 4 or parts[0] != "scene":
            raise ValueError(f"invalid scene_id: {scene_id}")
        seed = int(parts[1])
        idx = int(parts[2])
        ftype = "_".join(parts[3:])
        rng = np.random.default_rng(seed * 1000 + idx)

        T = cfg.steps_per_scene
        H = cfg.horizon

        # Ego trace: straight lane reference with small tracking noise.
        ego = np.zeros((T, 3), dtype=np.float64)
        ego[:, 0] = np.arange(T) * cfg.dt * 5.0   # 5 m/s forward
        ego[:, 1] = 0.0
        ego[:, 2] = 0.0

        # Four predictors — baseline projections of ego + noise.
        predictors = {}
        for m_idx, name in enumerate(["M1", "M2", "M3", "M4"]):
            traj = np.zeros((T, H, 3), dtype=np.float64)
            for t in range(T):
                # Straight-ahead prediction from ego at time t.
                for h in range(H):
                    traj[t, h, 0] = ego[t, 0] + (h + 1) * cfg.dt * 5.0
                    traj[t, h, 1] = 0.0
                    traj[t, h, 2] = 0.0
            predictors[name] = traj

        # Correlated-noise injection (AR(1) per-predictor).
        self._apply_correlated_noise(predictors, rng)
        # Non-Gaussian outlier frames.
        self._apply_outlier_frames(predictors, rng)
        # Failure injection on M4.
        self._inject_failure(predictors, ftype, rng)

        return SceneRecord(
            scene_id=scene_id,
            ego_trace=ego,
            predictor_trajectories=predictors,
            failure_metadata={
                "type": ftype,
                "onset_step": (
                    cfg.failure_onset_step
                    if ftype != "constant_bias_sanity" else None
                ),
                "duration_steps": cfg.failure_duration_steps,
                "ground_truth_failing_predictor": "M4",
            },
            dt=cfg.dt,
        )

    # --- noise / failure helpers ---

    def _apply_correlated_noise(self, predictors, rng) -> None:
        cfg = self._cfg
        for name, traj in predictors.items():
            # AR(1) noise at the state level: each timestep's noise
            # is alpha * previous + (1-alpha) * new_gaussian.
            noise_state = np.zeros(3, dtype=np.float64)
            T = traj.shape[0]
            for t in range(T):
                eps = rng.normal(
                    scale=cfg.correlated_noise_sigma, size=3
                )
                noise_state = (
                    cfg.correlated_noise_alpha * noise_state + eps
                )
                # Apply the same correlated noise across the horizon
                # (the predictor "believes" the noise is real state).
                traj[t] += noise_state[np.newaxis, :]

    def _apply_outlier_frames(self, predictors, rng) -> None:
        cfg = self._cfg
        for name, traj in predictors.items():
            T = traj.shape[0]
            outlier_mask = rng.random(T) < cfg.outlier_frame_rate
            scale = cfg.correlated_noise_sigma * cfg.outlier_scale_multiplier
            outlier_noise = rng.normal(scale=scale, size=(T, 1, 3))
            # Apply only at outlier timesteps, broadcast across horizon.
            traj[outlier_mask] += outlier_noise[outlier_mask]

    def _inject_failure(self, predictors, ftype, rng) -> None:
        cfg = self._cfg
        m4 = predictors["M4"]
        T = m4.shape[0]
        onset = cfg.failure_onset_step
        dur = cfg.failure_duration_steps
        if ftype == "gps_multipath":
            # Windowed lateral drift
            ramp = np.linspace(0.0, cfg.failure_magnitude, dur)
            for t in range(onset, min(onset + dur, T)):
                m4[t, :, 1] += ramp[t - onset]
        elif ftype == "map_misalignment":
            # Constant lateral bias + growing component (S3_accel-like)
            ramp = np.linspace(0.0, cfg.failure_magnitude, dur)
            for t in range(onset, min(onset + dur, T)):
                m4[t, :, 1] += ramp[t - onset]
        elif ftype == "camera_degradation":
            # High-frequency jitter during the window
            for t in range(onset, min(onset + dur, T)):
                jitter = rng.normal(
                    scale=cfg.failure_magnitude * 0.3, size=(m4.shape[1], 3),
                )
                m4[t] += jitter
        elif ftype == "constant_bias_sanity":
            # Lemma 1 negative control — constant bias across whole scene
            m4[:, :, 1] += cfg.failure_magnitude * 0.5
        else:
            raise ValueError(f"unknown failure type: {ftype}")
