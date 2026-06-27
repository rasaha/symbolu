"""Measurement primitives for the complementarity probe.

Two families:

1. Invariance (exp1): does `U` cluster by MEANING or by SOUND? Given groups of
   synonyms, compute a between-vs-within separation index and a permutation
   p-value. Semantic ⇒ within-group tight, between-group far ⇒ index > 0 with
   small p. Phonological ⇒ index ≈ 0.

2. Incremental decodability (exp2): does `E + U` decode a semantic label better
   than `E` alone — and better than `E + null`? A cross-validated L2 linear
   probe (multinomial logistic regression, torch) reports mean held-out
   accuracy. The deltas vs `E` are what matter; nulls bound the "generic
   capacity" baseline.

No sklearn dependency — the probe is a small torch model.
"""
from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np


# --------------------------------------------------------------------------- #
# 1. Invariance index
# --------------------------------------------------------------------------- #
def _pairwise_mean_dist(X: np.ndarray) -> float:
    """Mean Euclidean distance over all unordered pairs (vectorized)."""
    n = len(X)
    if n < 2:
        return 0.0
    sq = (X * X).sum(1)
    d2 = sq[:, None] + sq[None, :] - 2.0 * (X @ X.T)
    np.clip(d2, 0.0, None, out=d2)
    iu = np.triu_indices(n, k=1)
    return float(np.sqrt(d2[iu]).mean())


def invariance_index(group_vectors: Sequence[np.ndarray]) -> Dict[str, float]:
    """group_vectors: list of [n_i, dim] arrays, one per concept group.

    Returns within (mean intra-group pairwise dist), between (mean dist across
    all items ignoring groups), and index = (between - within)/(between + within).
    index → 1 perfectly meaning-invariant; → 0 no structure; < 0 anti-clustered.
    """
    withins = [_pairwise_mean_dist(g) for g in group_vectors if len(g) >= 2]
    within = float(np.mean(withins)) if withins else 0.0
    allX = np.concatenate([g for g in group_vectors if len(g) > 0], 0)
    between = _pairwise_mean_dist(allX)
    denom = between + within
    idx = (between - within) / denom if denom > 0 else 0.0
    return {"within": within, "between": between, "index": idx}


def invariance_permutation_p(group_vectors: Sequence[np.ndarray], n_perm: int = 2000,
                             seed: int = 0) -> Dict[str, float]:
    """Permutation test: shuffle group labels, recompute index. p = P(perm >= obs)."""
    rng = np.random.default_rng(seed)
    sizes = [len(g) for g in group_vectors]
    allX = np.concatenate(list(group_vectors), 0)
    obs = invariance_index(group_vectors)["index"]
    ge = 0
    for _ in range(n_perm):
        perm = rng.permutation(len(allX))
        shuffled = allX[perm]
        groups, s = [], 0
        for sz in sizes:
            groups.append(shuffled[s : s + sz])
            s += sz
        if invariance_index(groups)["index"] >= obs:
            ge += 1
    return {"index": obs, "p_value": (ge + 1) / (n_perm + 1)}


# --------------------------------------------------------------------------- #
# 2. Cross-validated linear probe
# --------------------------------------------------------------------------- #
def _zscore(train: np.ndarray, test: np.ndarray):
    mu = train.mean(0, keepdims=True)
    sd = train.std(0, keepdims=True) + 1e-8
    return (train - mu) / sd, (test - mu) / sd


def _fit_logreg(X: np.ndarray, y: np.ndarray, n_classes: int, l2: float = 1.0,
                epochs: int = 300, lr: float = 0.5):
    import torch

    Xt = torch.tensor(X, dtype=torch.float32)
    yt = torch.tensor(y, dtype=torch.long)
    W = torch.zeros(X.shape[1], n_classes, requires_grad=True)
    b = torch.zeros(n_classes, requires_grad=True)
    opt = torch.optim.LBFGS([W, b], lr=lr, max_iter=epochs, line_search_fn="strong_wolfe")

    def closure():
        opt.zero_grad()
        logits = Xt @ W + b
        loss = torch.nn.functional.cross_entropy(logits, yt) + l2 * (W * W).sum() / len(X)
        loss.backward()
        return loss

    opt.step(closure)
    return W.detach().numpy(), b.detach().numpy()


def cv_probe_accuracy(X: np.ndarray, y: np.ndarray, folds: int = 5, l2: float = 1.0,
                      seed: int = 0) -> float:
    """Stratified-ish k-fold mean held-out accuracy of an L2 linear probe."""
    import torch

    rng = np.random.default_rng(seed)
    n = len(X)
    classes = sorted(set(y.tolist()))
    n_classes = len(classes)
    remap = {c: i for i, c in enumerate(classes)}
    y = np.array([remap[v] for v in y])
    idx = rng.permutation(n)
    fold_ids = np.array_split(idx, folds)
    accs: List[float] = []
    for f in range(folds):
        test_i = fold_ids[f]
        train_i = np.concatenate([fold_ids[g] for g in range(folds) if g != f])
        if len(set(y[train_i].tolist())) < 2:
            continue
        Xtr, Xte = _zscore(X[train_i], X[test_i])
        W, b = _fit_logreg(Xtr, y[train_i], n_classes, l2=l2)
        logits = Xte @ W + b
        pred = logits.argmax(1)
        accs.append(float((pred == y[test_i]).mean()))
    return float(np.mean(accs)) if accs else 0.0


def concat(*mats: np.ndarray) -> np.ndarray:
    return np.concatenate(mats, axis=1)
