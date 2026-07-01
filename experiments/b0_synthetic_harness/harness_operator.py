"""B.0.1 — operator-aware (ordered-product) probe (numpy only; calibration only).

Extends B.0 with an Option-A operator-product probe: given a candidate operator
family ``{M_i}`` and init ``s0`` (exactly as the real probe would be handed the
theory's operators), the per-sequence feature is the ordered-product state

    s(seq) = M_{x_L} ... M_{x_1} s0   (op_dim features)

— the sufficient statistic for any linear readout ``u . s``. A generic detector
``detect_with`` compares ``[bag + order_features]`` vs ``[bag]`` against the same
within-sequence shuffle null used in B.0, so bag / bigram / operator probes are
calibrated identically.

SYNTHETIC CALIBRATION ONLY: no semantics, no real data, no A', no B-G,
no Symbol-U PASS/FAIL/bottom. Preserves bottom.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import stats  # noqa: E402
from harness import (MIN_DELTA_R2, SHUFFLE_PCTL, bag_features, bigram_features,
                     ridge_oof_r2, _shuffle_within)


def operator_product_features(seqs, ops, s0) -> np.ndarray:
    """Ordered-product final-state coordinates under a GIVEN operator family."""
    d = len(s0)
    X = np.zeros((len(seqs), d))
    for r, seq in enumerate(seqs):
        s = np.array(s0, float)
        for i in seq:
            s = ops[i] @ s
        X[r] = s
    return X


def random_operator_family(n_units: int, op_dim: int, seed: int):
    """A DIFFERENT random orthogonal family + init (for the mismatched probe)."""
    g = stats.rng(seed)
    ops = stats.random_orthogonal_matrices(n_units, op_dim, g)
    s0 = g.standard_normal(op_dim); s0 /= np.linalg.norm(s0)
    return ops, s0


def detect_with(seqs, y, n_units: int, order_feature_fn, K: int = 60,
                seed: int = 0, lam: float = 1.0) -> dict:
    """Generic order detector: ``order_feature_fn(seqs) -> (n_samples, p)``.

    Statistic = incremental OOF R^2 of [bag + order_features] over [bag], judged
    against the within-sequence shuffle null (counts fixed, order destroyed).
    """
    rng = np.random.default_rng(seed)
    Xb = bag_features(seqs, n_units)
    Xo = np.hstack([Xb, order_feature_fn(seqs)])
    r2_bag = ridge_oof_r2(Xb, y, seed=seed, lam=lam)
    r2_ord = ridge_oof_r2(Xo, y, seed=seed, lam=lam)
    delta = r2_ord - r2_bag
    null = np.empty(K)
    for kk in range(K):
        sh = _shuffle_within(seqs, rng)
        null[kk] = ridge_oof_r2(np.hstack([Xb, order_feature_fn(sh)]), y,
                                seed=seed, lam=lam) - r2_bag
    p_hi = float(np.percentile(null, SHUFFLE_PCTL))
    detected = bool(delta > p_hi and delta > MIN_DELTA_R2)
    learnable = bool(r2_ord > MIN_DELTA_R2 or r2_bag > MIN_DELTA_R2)
    return {"r2_bag": r2_bag, "r2_order": r2_ord, "delta": delta,
            "null_p95": p_hi, "detected": detected, "learnable": learnable}


# ---- convenience feature-fn factories -------------------------------------
def bigram_fn(n_units: int):
    return lambda seqs: bigram_features(seqs, n_units)


def operator_fn(ops, s0):
    return lambda seqs: operator_product_features(seqs, ops, s0)
