"""Shared assembly: load the cohort series and precompute all deterministic
tracks once; gather per-query token tensors for any arm.
"""
from __future__ import annotations

import numpy as np
import torch

from . import features as F


class Assembled:
    def __init__(self, npz_path: str, retrieval_v2: bool = False):
        minutes = np.load(npz_path)["minutes"]
        self.bins = F.bin_series(minutes)
        self.targets = F.targets(self.bins)                    # [F, T, 3]
        self.baselines = F.baseline_preds(self.bins)
        self.stats = F.stats_tokens(self.bins)                 # [F, T, 3, 6]
        self.harm = F.harmonic_tokens(self.bins)               # [F, T, 6, 6]
        self.seas_med = F.seasonal_median(self.bins)
        self.retrieval_v2 = retrieval_v2
        if retrieval_v2:
            self.retr = F.retrieval_tracks_v2(minutes, self.bins, self.seas_med)
        else:
            self.retr = F.retrieval_tracks(minutes, self.bins, self.seas_med)
        self.n_func = self.bins.shape[0]

    def tokens(self, arm: str, f_idx: np.ndarray, t_idx: np.ndarray):
        parts = [self.stats[f_idx, t_idx]]
        if arm in ("harmonic_reader", "harmonic_retrieval"):
            parts.append(self.harm[f_idx, t_idx])
        if arm in ("stats_retrieval", "harmonic_retrieval"):
            fn = F.retrieval_tokens_v2 if self.retrieval_v2 else F.retrieval_tokens
            parts.append(fn(self.retr, f_idx, t_idx))
        toks = np.concatenate(parts, axis=1)
        return (torch.from_numpy(toks),
                torch.from_numpy(F.query_features(t_idx)),
                torch.from_numpy(self.targets[f_idx, t_idx]))
