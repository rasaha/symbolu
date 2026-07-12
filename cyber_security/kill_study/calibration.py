"""Per-arm score calibration against the DEV-legit null distribution.

Each arm emits a raw per-step core score in its own natural units (identity
distance ~O(1), CUSUM ~O(100)). To place every arm on a comparable DET axis we
standardize each arm's raw score by the mean/std of that arm's score over the
**DEV-legit** events only — the null. This is computed once and applied to all
events. Crucially it does NOT chase the mean within an event, so sustained /
accumulating signals (CUSUM, LLT+CUSUM, a sustained identity offset) are
preserved rather than normalized away. Using a within-event EMA here would
silently cripple exactly the accumulating baselines the study must not weaken.

Fit uses DEV-legit only, so there is no EVAL leakage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np

from .config import LEGIT_FAMILIES, StudyConfig
from .detectors import ARMS, ARM_ORDER


@dataclass
class Calibration:
    mean: Dict[str, float]
    std: Dict[str, float]

    def transform(self, arm_key: str, s_raw: np.ndarray) -> np.ndarray:
        mu = self.mean[arm_key]
        sd = self.std[arm_key]
        return (np.asarray(s_raw, dtype=np.float64) - mu) / (sd + 1e-9)

    def to_dict(self) -> dict:
        return {"mean": self.mean, "std": self.std}


def fit_calibration(cfg: StudyConfig) -> Calibration:
    """Fit per-arm (mean, std) over all DEV-legit event steps."""
    import itertools

    from .config import DEV_GRID, DEV_SEED_BASE
    from .trajectories import generate

    keys = ("sigma", "separation", "ramp_duration", "missing_rate")
    cells = list(itertools.product(*(DEV_GRID[k] for k in keys)))

    pooled: Dict[str, list] = {k: [] for k in ARM_ORDER}
    for family_idx, family in enumerate(LEGIT_FAMILIES):
        # legit families occupy the same family-index space as ALL_FAMILIES;
        # recover the true index so seeds match the experiment stream.
        from .config import ALL_FAMILIES

        true_idx = ALL_FAMILIES.index(family)
        for cell_idx, cell in enumerate(cells):
            sigma, separation, ramp_duration, missing_rate = cell
            for seed_idx in range(cfg.dev_seeds_per_cell):
                seed = DEV_SEED_BASE + true_idx * 100_000 + cell_idx * 1_000 + seed_idx
                ev = generate(family, seed=seed, cfg=cfg, sigma=sigma,
                              separation=separation, ramp_duration=ramp_duration,
                              missing_rate=missing_rate)
                for arm_key in ARM_ORDER:
                    pooled[arm_key].append(ARMS[arm_key](ev, cfg).s_raw)

    mean: Dict[str, float] = {}
    std: Dict[str, float] = {}
    for arm_key in ARM_ORDER:
        allvals = np.concatenate(pooled[arm_key])
        mean[arm_key] = float(np.mean(allvals))
        std[arm_key] = float(np.std(allvals))
    return Calibration(mean=mean, std=std)
