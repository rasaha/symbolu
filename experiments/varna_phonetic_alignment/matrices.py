"""Matrix-alignment primitives for B0 (PREREG_VARNA_PHONETIC_ALIGNMENT.md).

Pure numpy. Operates on varṇa×varṇa dissimilarity matrices (symmetric, zero
diagonal). No semantics, no real-data fit, no verdict. The B0 statistics:

  - upper_triangle      : off-diagonal upper entries (the Mantel vector)
  - spearman            : rank correlation (numpy-only; no scipy)
  - mantel_r            : Spearman of the two upper triangles
  - partial_mantel_r    : Spearman partial r(T,P | C) — the mandatory C-control
  - mantel_permutation  : label-permutation null for a (partial) Mantel statistic
  - scrambled_null      : varṇa→table-entry scramble null (rebuilds T each draw)
  - bootstrap_partial   : varṇa-level bootstrap CI on the partial Mantel

p-values / CIs route through experiments/common/stats so the inference gates
match the rest of the track.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import stats  # noqa: E402  (rng, percentile_gate, permutation_pvalue, bootstrap_ci)


# ---------------------------------------------------------------- rank / corr --
def _rankdata(a: np.ndarray) -> np.ndarray:
    """Average ranks (ties shared), numpy-only (scipy-free)."""
    a = np.asarray(a, float)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(a.size, float)
    ranks[order] = np.arange(1, a.size + 1, dtype=float)
    # average tied ranks
    _, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
    sums = np.zeros(counts.size)
    np.add.at(sums, inv, ranks)
    return (sums / counts)[inv]


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, float); y = np.asarray(y, float)
    xc, yc = x - x.mean(), y - y.mean()
    den = np.sqrt(float(xc @ xc) * float(yc @ yc))
    return float(xc @ yc / den) if den > 0 else 0.0


def spearman(x, y) -> float:
    """Spearman rank correlation."""
    return _pearson(_rankdata(x), _rankdata(y))


# ------------------------------------------------------------- matrix helpers --
def upper_triangle(M: np.ndarray) -> np.ndarray:
    """Off-diagonal upper-triangular entries of a square matrix (row-major)."""
    M = np.asarray(M, float)
    iu = np.triu_indices(M.shape[0], k=1)
    return M[iu]


def _check_square(*Ms):
    n = np.asarray(Ms[0]).shape[0]
    for M in Ms:
        M = np.asarray(M)
        if M.ndim != 2 or M.shape[0] != M.shape[1] or M.shape[0] != n:
            raise ValueError("all inputs must be square matrices of equal size")
    return n


# ------------------------------------------------------------------- Mantel ----
def mantel_r(A: np.ndarray, B: np.ndarray) -> float:
    """Mantel statistic = Spearman correlation of the two upper triangles."""
    _check_square(A, B)
    return spearman(upper_triangle(A), upper_triangle(B))


def _residualize(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    """OLS residuals of y on [1, x]."""
    X = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return y - X @ beta


def partial_mantel_r(T: np.ndarray, P: np.ndarray, C: np.ndarray) -> float:
    """Spearman partial correlation r(T, P | C) on the upper triangles.

    Rank-transform each upper triangle, residualize rank(T) and rank(P) on
    rank(C) (with intercept), and Pearson-correlate the residuals. This is the
    mandatory trivial-class control: does T track P *beyond* the coarse class
    structure C the table is laid out on?
    """
    _check_square(T, P, C)
    rt = _rankdata(upper_triangle(T))
    rp = _rankdata(upper_triangle(P))
    rc = _rankdata(upper_triangle(C))
    return _pearson(_residualize(rt, rc), _residualize(rp, rc))


# ----------------------------------------------------------- permutation null --
def _permute_matrix(M: np.ndarray, perm: np.ndarray) -> np.ndarray:
    """Relabel rows AND columns of M by perm (a varṇa relabeling)."""
    return M[np.ix_(perm, perm)]


def mantel_permutation(T, P, C=None, n: int = 10000, seed: int = 0) -> np.ndarray:
    """Label-permutation null distribution of the (partial) Mantel statistic.

    Permutes the varṇa labels of T relative to fixed P (and C). Returns the null
    sample array; feed it to stats.permutation_pvalue / percentile_gate.
    """
    T = np.asarray(T, float); P = np.asarray(P, float)
    n_items = _check_square(T, P) if C is None else _check_square(T, P, C)
    g = stats.rng(seed)
    null = np.empty(n, float)
    for i in range(n):
        perm = g.permutation(n_items)
        Tp = _permute_matrix(T, perm)
        null[i] = mantel_r(Tp, P) if C is None else partial_mantel_r(Tp, P, C)
    return null


# --------------------------------------------------- scrambled-table null (T) --
def scrambled_null(build_T, P, C=None, n: int = 1000, seed: int = 0,
                   n_items: int | None = None) -> np.ndarray:
    """Scrambled-table null: rebuild T under a permuted varṇa→entry assignment.

    build_T(perm) -> T  must accept a varṇa→entry index permutation and return the
    table dissimilarity under that scrambled assignment. The label *set* is
    preserved; only which varṇa carries which table entry is shuffled. Returns the
    null distribution of mantel_r (or partial_mantel_r if C given).
    """
    P = np.asarray(P, float)
    if n_items is None:
        n_items = P.shape[0]
    g = stats.rng(seed)
    null = np.empty(n, float)
    for i in range(n):
        perm = g.permutation(n_items)
        T = np.asarray(build_T(perm), float)
        null[i] = mantel_r(T, P) if C is None else partial_mantel_r(T, P, C)
    return null


# ------------------------------------------------------------- bootstrap (CI) --
def bootstrap_partial(T, P, C, n_boot: int = 2000, seed: int = 0,
                      alpha: float = 0.05) -> dict:
    """Varṇa-level bootstrap CI on the partial Mantel r(T,P|C).

    Resample varṇa indices with replacement, subset all three matrices, recompute
    the partial statistic. (Duplicate indices create zero-distance pairs — a known
    bootstrap-on-distance-matrix wrinkle; acceptable for the scaffold and noted in
    the pre-registration §8.) Returns mean / CI / excludes_zero.
    """
    T = np.asarray(T, float); P = np.asarray(P, float); C = np.asarray(C, float)
    n_items = _check_square(T, P, C)
    g = stats.rng(seed)
    vals = []
    for _ in range(n_boot):
        idx = g.integers(0, n_items, size=n_items)
        sub = np.ix_(idx, idx)
        vals.append(partial_mantel_r(T[sub], P[sub], C[sub]))
    v = np.asarray(vals, float)
    lo, hi = np.percentile(v, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"mean": float(v.mean()), "lo": float(lo), "hi": float(hi),
            "excludes_zero": bool(lo > 0 or hi < 0)}


# convenience re-exports for the inference gates
permutation_pvalue = stats.permutation_pvalue
percentile_gate = stats.percentile_gate
