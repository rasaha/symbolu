"""Majority-vote arbitrator — clusters predictors per tick, takes the mode.

At each horizon step:
  1. Cluster the M predictor positions using a distance threshold
     (default 0.5 m). Predictors within ``cluster_radius`` of each
     other join the same cluster.
  2. Identify the *largest* cluster; ties broken by lowest
     predictor index.
  3. Consensus position = mean of largest cluster.
  4. Per-predictor attribution = Euclidean distance from the
     largest cluster's centroid, summed across the horizon. A
     predictor in the largest cluster every tick gets attribution
     ~0; an outlier predictor far from the majority gets a high
     attribution.

Heading consensus uses circular-statistics mean (atan2 of the
sin/cos averages over the majority cluster).
"""

from __future__ import annotations

import time

import numpy as np

from .base import ArbitrationResult, Arbitrator, validate_trajectories


def _cluster_majority(positions: np.ndarray, radius: float) -> np.ndarray:
    """Greedy single-pass clustering on a (M, 2) position array.

    Returns an (M,) int array of cluster IDs.
    """
    M = positions.shape[0]
    cluster_ids = -np.ones(M, dtype=np.int64)
    next_id = 0
    for i in range(M):
        if cluster_ids[i] >= 0:
            continue
        cluster_ids[i] = next_id
        for j in range(i + 1, M):
            if cluster_ids[j] >= 0:
                continue
            d = np.linalg.norm(positions[i] - positions[j])
            if d <= radius:
                cluster_ids[j] = next_id
        next_id += 1
    return cluster_ids


class MajorityVoteArbitrator:
    name: str = "MajorityVote"

    def __init__(self, cluster_radius: float = 0.5) -> None:
        if cluster_radius <= 0:
            raise ValueError("cluster_radius must be > 0")
        self._radius = float(cluster_radius)

    def arbitrate(self, trajectories: np.ndarray) -> ArbitrationResult:
        arr = validate_trajectories(trajectories)
        M, H, _ = arr.shape
        consensus = np.zeros((H, 3), dtype=np.float64)
        attribution = np.zeros(M, dtype=np.float64)
        per_tick_times: list = []

        for h in range(H):
            t0 = time.perf_counter()
            xy = arr[:, h, :2]
            cluster_ids = _cluster_majority(xy, self._radius)
            counts = np.bincount(cluster_ids)
            largest = int(counts.argmax())
            in_majority = cluster_ids == largest
            majority_xy = xy[in_majority].mean(axis=0)
            sin_th = np.sin(arr[in_majority, h, 2]).mean()
            cos_th = np.cos(arr[in_majority, h, 2]).mean()
            consensus[h, 0] = majority_xy[0]
            consensus[h, 1] = majority_xy[1]
            consensus[h, 2] = float(np.arctan2(sin_th, cos_th))

            # Attribution: distance from majority centroid.
            distances = np.linalg.norm(xy - majority_xy[None, :], axis=-1)
            attribution += distances
            per_tick_times.append((time.perf_counter() - t0) * 1e6)

        return ArbitrationResult(
            consensus=consensus,
            attribution=attribution,
            per_tick_us=float(np.median(per_tick_times)),
            metadata={"cluster_radius": self._radius},
        )
