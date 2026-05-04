"""Always-trust-anchor arbitrator — the null baseline.

What a system with no arbitration layer at all looks like: pick a
designated primary predictor and use its output unchanged. No
attribution; no outlier rejection. The shootout includes it as a
floor — any arbitrator that doesn't strictly beat the anchor on
failure families isn't earning its keep.
"""

from __future__ import annotations

import time

import numpy as np

from .base import ArbitrationResult, Arbitrator, validate_trajectories


class AnchorArbitrator:
    """Always trust ``trajectories[anchor_idx]``. No attribution."""

    name: str = "Anchor"

    def __init__(self, anchor_idx: int = 0) -> None:
        if anchor_idx < 0:
            raise ValueError("anchor_idx must be >= 0")
        self._anchor_idx = int(anchor_idx)

    def arbitrate(self, trajectories: np.ndarray) -> ArbitrationResult:
        arr = validate_trajectories(trajectories)
        if self._anchor_idx >= arr.shape[0]:
            raise IndexError(
                f"anchor_idx {self._anchor_idx} out of range for M={arr.shape[0]}"
            )
        t0 = time.perf_counter()
        consensus = arr[self._anchor_idx].copy()
        per_tick_us = (time.perf_counter() - t0) * 1e6 / arr.shape[1]
        attribution = np.zeros(arr.shape[0], dtype=np.float64)
        return ArbitrationResult(
            consensus=consensus,
            attribution=attribution,
            per_tick_us=per_tick_us,
            metadata={"anchor_idx": self._anchor_idx},
        )
