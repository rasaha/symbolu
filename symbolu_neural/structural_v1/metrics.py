"""Structural metrics (Stage A): order-effect + factorization.

ALL outputs are structure, not validated meaning.

order-effect:
    e_ij = M_i M_j s0 - M_j M_i s0      (directed)
    B_ij = ||e_ij||                      (symmetric magnitude matrix)

factorization:
    structure_score(B, F): out-of-sample (k-fold) R^2 of predicting B_ij from
        "wedge" features  w_ab^{ij} = f_i[a] f_j[b] - f_i[b] f_j[a]  (one per
        generator pair a<b). Rationale: to leading order the commutator
        [A_i, A_j] = sum_{a<b} w_ab^{ij} [G_a, G_b], so generator pairs that
        COMMUTE contribute nothing -> their wedge should not predict B.
    effective_rank(B): participation ratio of singular values (low => low-dim).
    commuting/coupling coefficients: OLS coefficient on commuting-pair wedges
        (should be ~0) vs coupling-pair wedges (should be > 0).
"""
from __future__ import annotations

from itertools import combinations
from typing import Dict, List, Tuple

import numpy as np

from .engine import S0, read_product
from .operators import commuting_generator_pairs


def order_effect_matrix(ops: List[np.ndarray], s0: np.ndarray = S0):
    """Return (B, E) where B[i,j]=||e_ij|| (symmetric, zero diag) and E is the
    directed displacement tensor e_ij = M_i M_j s0 - M_j M_i s0."""
    n = len(ops)
    B = np.zeros((n, n))
    E = np.zeros((n, n, len(s0)))
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            ij = read_product([j, i], ops, s0)   # apply j then i  => M_i M_j s0
            ji = read_product([i, j], ops, s0)   # apply i then j  => M_j M_i s0
            e = ij - ji
            E[i, j] = e
            B[i, j] = float(np.linalg.norm(e))
    if not np.all(np.isfinite(B)):
        raise FloatingPointError("non-finite order-effect matrix")
    return B, E


def mean_standardized_order_effect(B: np.ndarray) -> float:
    """Mean of the off-diagonal B (states are unit-norm, so B in [0,2])."""
    n = B.shape[0]
    vals = [B[i, j] for i, j in combinations(range(n), 2)]
    return float(np.mean(vals)) if vals else 0.0


# ---- wedge feature construction ----
def _gen_pairs(k: int) -> List[Tuple[int, int]]:
    return list(combinations(range(k), 2))


def wedge_features(F: np.ndarray):
    """For each unordered unit pair (i<j) build wedge predictors |w_ab^{ij}|.

    Returns (X, y_index, pair_list, gen_pairs) where X has one row per unit-pair
    and one column per generator pair (a<b)."""
    n, k = F.shape
    gp = _gen_pairs(k)
    pairs = list(combinations(range(n), 2))
    X = np.zeros((len(pairs), len(gp)))
    for r, (i, j) in enumerate(pairs):
        for c, (a, b) in enumerate(gp):
            w = F[i, a] * F[j, b] - F[i, b] * F[j, a]
            X[r, c] = abs(w)
    return X, pairs, gp


def _ols_fit(X: np.ndarray, y: np.ndarray):
    """OLS with intercept; returns (coef, intercept)."""
    A = np.hstack([np.ones((X.shape[0], 1)), X])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    return beta[1:], beta[0]


def _kfold_r2(X: np.ndarray, y: np.ndarray, folds: int, rng: np.random.Generator) -> float:
    """Out-of-sample R^2 via k-fold CV (held-out predictions vs global mean)."""
    m = X.shape[0]
    if m < folds:
        folds = max(2, m)
    idx = rng.permutation(m)
    splits = np.array_split(idx, folds)
    yhat = np.full(m, np.nan)
    for f in range(folds):
        test = splits[f]
        train = np.concatenate([splits[g] for g in range(folds) if g != f])
        if len(train) == 0 or len(test) == 0:
            continue
        coef, b0 = _ols_fit(X[train], y[train])
        yhat[test] = X[test] @ coef + b0
    mask = ~np.isnan(yhat)
    yy, pp = y[mask], yhat[mask]
    ss_tot = float(np.sum((yy - yy.mean()) ** 2))
    if ss_tot <= 1e-30:
        return 0.0
    ss_res = float(np.sum((yy - pp) ** 2))
    return 1.0 - ss_res / ss_tot


def structure_score(B: np.ndarray, F: np.ndarray, folds: int = 5, seed: int = 0) -> float:
    """Out-of-sample R^2 predicting B_ij from real-feature wedge predictors."""
    X, pairs, _ = wedge_features(F)
    y = np.array([B[i, j] for (i, j) in pairs])
    rng = np.random.default_rng(seed)
    return _kfold_r2(X, y, folds, rng)


def effective_rank(B: np.ndarray) -> float:
    """Participation ratio of singular values: (sum s)^2 / sum s^2."""
    s = np.linalg.svd(B, compute_uv=False)
    s = s[s > 1e-12]
    if s.size == 0:
        return 0.0
    return float((s.sum() ** 2) / np.sum(s ** 2))


def commuting_vs_coupling_coeffs(B: np.ndarray, F: np.ndarray) -> Dict[str, float]:
    """Fit OLS on all unit-pairs; report mean |coef| on commuting-pair wedges vs
    coupling-pair wedges. Prediction: commuting ~ 0, coupling > 0."""
    X, pairs, gp = wedge_features(F)
    y = np.array([B[i, j] for (i, j) in pairs])
    coef, _ = _ols_fit(X, y)
    commuting = set(commuting_generator_pairs())
    comm_idx = [c for c, pair in enumerate(gp) if pair in commuting]
    coup_idx = [c for c, pair in enumerate(gp) if pair not in commuting]
    comm = float(np.mean([abs(coef[c]) for c in comm_idx])) if comm_idx else 0.0
    coup = float(np.mean([abs(coef[c]) for c in coup_idx])) if coup_idx else 0.0
    return {
        "commuting_coef_mean_abs": comm,
        "coupling_coef_mean_abs": coup,
        "gap": coup - comm,
    }
