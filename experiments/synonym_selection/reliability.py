"""Reliability-gate helpers for the target→vṛtti bridge (scaffolding).

Implements a Krippendorff-style interval reliability coefficient for COMPLETE data and
the two-stage gate from PREREG_OBJECT_PROFILE_FIT.md §7 (reused by the synonym pilot §5):

  within-pool α below floor   -> MEASUREMENT_FAILURE
  between-pool (insider vs naïve) α below floor -> CIRCULARITY_FAILURE
  else                         -> OK

Operates on numeric arrays only; no file I/O, no real data, no semantic claim.
Ratings are shaped [n_targets, n_traits, n_coders] per pool.
"""
from __future__ import annotations

import numpy as np

FLOOR = 0.67          # required α (PREREG); ≥0.80 is "good"


def _pairwise_sqdiff(vals) -> np.ndarray:
    v = np.asarray(vals, float)
    iu = np.triu_indices(len(v), 1)
    d = v[:, None] - v[None, :]
    return d[iu] ** 2


def alpha_interval(ratings) -> float:
    """Krippendorff-style interval α for COMPLETE data, ratings = [n_items x n_coders]."""
    R = np.asarray(ratings, float)
    if R.ndim != 2 or R.shape[1] < 2 or R.shape[0] < 1:
        return float("nan")
    Do = np.concatenate([_pairwise_sqdiff(R[i]) for i in range(R.shape[0])]).mean()
    De = _pairwise_sqdiff(R.flatten()).mean()
    if De <= 0:
        return 1.0          # no variance anywhere -> degenerate perfect agreement
    return float(1.0 - Do / De)


def _flatten_items(pool) -> np.ndarray:
    """[n_targets, n_traits, n_coders] -> [n_targets*n_traits, n_coders]."""
    p = np.asarray(pool, float)
    return p.reshape(-1, p.shape[-1])


def within_pool_alpha(pool) -> float:
    return alpha_interval(_flatten_items(pool))


def between_pool_alpha(insider, naive) -> float:
    """Per-item insider-pool mean vs naïve-pool mean as two 'coders' -> α."""
    a = _flatten_items(insider).mean(axis=1)
    b = _flatten_items(naive).mean(axis=1)
    return alpha_interval(np.stack([a, b], axis=1))


def reliability_gate(insider, naive, floor: float = FLOOR) -> dict:
    """Two-stage gate. Returns {status, alpha_insider, alpha_naive, alpha_between}.

    status ∈ {'MEASUREMENT_FAILURE', 'CIRCULARITY_FAILURE', 'OK'}.
    """
    a_in = within_pool_alpha(insider)
    a_na = within_pool_alpha(naive)
    out = {"alpha_insider": a_in, "alpha_naive": a_na, "alpha_between": None}
    if not (a_in >= floor) or not (a_na >= floor):
        out["status"] = "MEASUREMENT_FAILURE"
        return out
    a_btw = between_pool_alpha(insider, naive)
    out["alpha_between"] = a_btw
    out["status"] = "OK" if a_btw >= floor else "CIRCULARITY_FAILURE"
    return out
