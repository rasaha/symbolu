"""Probe / baseline / null machinery for B.0 calibration (numpy only).

Featurizations:
  * bag_features    — unit counts (order-blind baseline).
  * bigram_features — ordered adjacent-pair counts (order-aware, no knowledge of
    the generative operators).

Probe = ridge regression, out-of-fold R^2. The order signal statistic is the
incremental OOF R^2 of [bag + bigram] over [bag], judged against a within-
sequence SHUFFLE null (preserves counts, destroys order). Decision returns one
of: DETECTED_PLANTED_SIGNAL / CORRECT_NULL / FALSE_POSITIVE / FALSE_NEGATIVE /
AMBIGUOUS. Instrument calibration only — no semantics, no real data.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common.stats import ridge_oof_r2  # noqa: E402  (shared; re-exported here)
from common.stats import shuffle_within as _shuffle_within  # noqa: E402

# pre-registered decision thresholds (fixed before execution)
MIN_DELTA_R2 = 0.01     # minimum incremental OOF R^2 to call an order effect real
SHUFFLE_PCTL = 95       # real delta must exceed this percentile of the shuffle null
LEARNABLE_FLOOR = 0.01  # if neither baseline learns anything -> underpowered/AMBIGUOUS


def bag_features(seqs, n_units: int) -> np.ndarray:
    X = np.zeros((len(seqs), n_units))
    for r, s in enumerate(seqs):
        for i in s:
            X[r, i] += 1.0
    return X


def bigram_features(seqs, n_units: int) -> np.ndarray:
    X = np.zeros((len(seqs), n_units * n_units))
    for r, s in enumerate(seqs):
        for a, b in zip(s[:-1], s[1:]):
            X[r, a * n_units + b] += 1.0
    return X


def detect_order(seqs, y, n_units: int, K: int = 60, seed: int = 0,
                 lam: float = 1.0) -> dict:
    """Order-signal detector with within-sequence shuffle null."""
    rng = np.random.default_rng(seed)
    Xb = bag_features(seqs, n_units)
    Xo = np.hstack([Xb, bigram_features(seqs, n_units)])
    r2_bag = ridge_oof_r2(Xb, y, seed=seed, lam=lam)
    r2_ord = ridge_oof_r2(Xo, y, seed=seed, lam=lam)
    delta = r2_ord - r2_bag
    null = np.empty(K)
    for kk in range(K):                       # bag features invariant under within-seq shuffle
        sh = _shuffle_within(seqs, rng)
        Xo_sh = np.hstack([Xb, bigram_features(sh, n_units)])
        null[kk] = ridge_oof_r2(Xo_sh, y, seed=seed, lam=lam) - r2_bag
    p_hi = float(np.percentile(null, SHUFFLE_PCTL))
    detected = bool(delta > p_hi and delta > MIN_DELTA_R2)
    learnable = bool(r2_ord > LEARNABLE_FLOOR or r2_bag > LEARNABLE_FLOOR)
    return {"r2_bag": r2_bag, "r2_order": r2_ord, "delta": delta,
            "null_p95": p_hi, "null_mean": float(null.mean()),
            "detected": detected, "learnable": learnable}


def relabel_invariance(seqs, y, n_units: int, seed: int = 0) -> dict:
    """Relabel/unit-permutation check: apply ONE global unit permutation to every
    sequence. For a linear probe this is a column permutation -> R^2 is invariant.
    Reported as a probe-symmetry sanity check (not a signal destroyer)."""
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n_units)
    relabeled = [[int(perm[i]) for i in s] for s in seqs]
    base = detect_order(seqs, y, n_units, K=20, seed=seed)
    rel = detect_order(relabeled, y, n_units, K=20, seed=seed)
    return {"delta_original": base["delta"], "delta_relabeled": rel["delta"],
            "invariant": bool(abs(base["delta"] - rel["delta"]) < 1e-6)}


def decision_label(res: dict, order_present: bool) -> str:
    if order_present and not res["learnable"]:
        return "AMBIGUOUS"          # underpowered: no learnable signal at all
    if res["detected"] and order_present:
        return "DETECTED_PLANTED_SIGNAL"
    if res["detected"] and not order_present:
        return "FALSE_POSITIVE"
    if (not res["detected"]) and order_present:
        return "FALSE_NEGATIVE"
    return "CORRECT_NULL"
