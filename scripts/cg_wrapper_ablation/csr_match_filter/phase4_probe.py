"""phase4_probe.py — Phase 4 Stage-A probe MATH (pure numpy, CPU-only, no torch).

Infrastructure for the hidden-state diagnostic probe described in
docs/CSR_MATCH_FILTER_PHASE4_HIDDEN_STATE_PROBE.md. This module is deliberately MODEL-FREE so it can be
unit-tested on synthetic activations without a GPU. It implements, with no sklearn/scipy dependency:

  - a small deterministic L2 logistic-regression linear probe,
  - rank-based AUROC (tie-aware),
  - group-by-term cross-validation (no term in both train and test),
  - a dimension-matched random-feature control (the "more features win for free" null),
  - effective rank / participation ratio for Bhava-collapse detection,
  - bootstrap AUROC-delta confidence intervals,
  - an incremental-value comparison (hidden_only vs hidden+extra vs hidden+random),
  - a leakage check, and
  - decide_phase4() mapping metrics to PHASE4_* labels.

NO Phase 4 claim is made here and nothing is run on real data — this is Stage-A plumbing only. No
Bhava/Guna/Vritti/JEPA logic, no generation, no change to any frozen scorer/prompt/rubric/audit rule.
"""

from __future__ import annotations

import numpy as np

# ---- linear probe ---------------------------------------------------------------------------------


def _standardize(X):
    mu = X.mean(0)
    sd = X.std(0)
    sd = np.where(sd < 1e-8, 1.0, sd)
    return mu, sd


def fit_logreg(X, y, l2: float = 1.0, n_iter: int = 400, lr: float = 0.5):
    """Deterministic L2-regularised logistic regression by full-batch gradient descent."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    mu, sd = _standardize(X)
    Xs = (X - mu) / sd
    n, d = Xs.shape
    w = np.zeros(d)
    b = 0.0
    for _ in range(n_iter):
        p = 1.0 / (1.0 + np.exp(-(Xs @ w + b)))
        gw = Xs.T @ (p - y) / n + l2 * w / n
        gb = float((p - y).mean())
        w -= lr * gw
        b -= lr * gb
    return {"w": w, "b": b, "mu": mu, "sd": sd}


def predict_proba(model, X):
    Xs = (np.asarray(X, float) - model["mu"]) / model["sd"]
    return 1.0 / (1.0 + np.exp(-(Xs @ model["w"] + model["b"])))


# ---- AUROC (tie-aware, no scipy) ------------------------------------------------------------------


def _rankdata(a):
    a = np.asarray(a, float)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), float)
    sa = a[order]
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and sa[j + 1] == sa[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0   # average rank for ties
        i = j + 1
    return ranks


def auroc(y, scores):
    y = np.asarray(y)
    scores = np.asarray(scores, float)
    npos = int((y == 1).sum())
    nneg = int((y == 0).sum())
    if npos == 0 or nneg == 0:
        return 0.5
    r = _rankdata(scores)
    return float((r[y == 1].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))


# ---- group-by-term cross-validation ---------------------------------------------------------------


def group_kfold_indices(groups, n_splits: int = 5, seed: int = 0):
    """Yield (train_idx, test_idx) where no group (term) appears in both splits."""
    groups = np.asarray(groups)
    uniq = np.array(sorted({g for g in groups.tolist()}), dtype=object)
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(uniq))
    uniq = uniq[perm]
    n_splits = max(2, min(n_splits, len(uniq)))
    folds = np.array_split(uniq, n_splits)
    out = []
    for f in folds:
        test_groups = set(f.tolist())
        test = np.array([i for i, g in enumerate(groups) if g in test_groups], dtype=int)
        train = np.array([i for i, g in enumerate(groups) if g not in test_groups], dtype=int)
        out.append((train, test))
    return out


def cv_oof_scores(X, y, groups, n_splits: int = 5, l2: float = 1.0, seed: int = 0):
    """Out-of-fold predicted scores under group-by-term CV (NaN where a fold could not be scored)."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    oof = np.full(len(y), np.nan)
    for tr, te in group_kfold_indices(groups, n_splits, seed):
        if len(tr) == 0 or len(te) == 0:
            continue
        if len(set(y[tr].tolist())) < 2:                      # degenerate (one class) -> prior
            oof[te] = float(y[tr].mean()) if len(tr) else 0.5
            continue
        m = fit_logreg(X[tr], y[tr], l2=l2)
        oof[te] = predict_proba(m, X[te])
    return oof


def evaluate_probe(X, y, groups, n_splits: int = 5, l2: float = 1.0, seed: int = 0):
    oof = cv_oof_scores(X, y, groups, n_splits=n_splits, l2=l2, seed=seed)
    mask = ~np.isnan(oof)
    y = np.asarray(y)
    return {"auroc": auroc(y[mask], oof[mask]) if mask.any() else 0.5, "oof": oof, "mask": mask}


# ---- controls & diagnostics -----------------------------------------------------------------------


def random_features(n, width, seed: int = 0):
    """Independent Gaussian noise columns — the dimension-matched 'more features for free' null."""
    return np.random.default_rng(seed).standard_normal((n, int(width)))


def effective_rank(M):
    """Participation ratio of the feature covariance eigenvalues, in [0, n_features].

    ~1 means the representation collapsed onto a single direction (Bhava collapse)."""
    M = np.asarray(M, float)
    if M.ndim != 2 or M.shape[0] < 2:
        return 0.0
    Mc = M - M.mean(0)
    cov = Mc.T @ Mc / (M.shape[0] - 1)
    ev = np.linalg.eigvalsh(cov)
    ev = ev[ev > 1e-12]
    if ev.size == 0:
        return 0.0
    return float((ev.sum() ** 2) / (ev ** 2).sum())


def bootstrap_auroc_delta(y, scores_a, scores_b, n_boot: int = 1000, seed: int = 0,
                          alpha: float = 0.05):
    """Bootstrap CI for AUROC(a) - AUROC(b) over paired predictions on the same examples."""
    y = np.asarray(y)
    a = np.asarray(scores_a, float)
    b = np.asarray(scores_b, float)
    base = auroc(y, a) - auroc(y, b)
    rng = np.random.default_rng(seed)
    n = len(y)
    deltas = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yy = y[idx]
        if len(set(yy.tolist())) < 2:
            continue
        deltas.append(auroc(yy, a[idx]) - auroc(yy, b[idx]))
    if not deltas:
        return {"delta": float(base), "ci_low": float("nan"), "ci_high": float("nan"),
                "excludes_zero": False}
    lo, hi = np.percentile(deltas, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"delta": float(base), "ci_low": float(lo), "ci_high": float(hi),
            "excludes_zero": bool(lo > 0.0 or hi < 0.0)}


def incremental_value(X_hidden, X_extra, y, groups, n_splits: int = 5, l2: float = 1.0,
                      seed: int = 0, n_boot: int = 1000):
    """Does X_extra (e.g. the Bhava read) add AUROC over hidden_only AND over a dimension-matched
    random-feature control? Returns the three AUROCs and the two bootstrap deltas."""
    X_hidden = np.asarray(X_hidden, float)
    X_extra = np.asarray(X_extra, float)
    y = np.asarray(y)
    width = X_extra.shape[1]
    X_he = np.hstack([X_hidden, X_extra])
    X_hr = np.hstack([X_hidden, random_features(len(y), width, seed=seed + 7)])

    S_h = cv_oof_scores(X_hidden, y, groups, n_splits, l2, seed)
    S_he = cv_oof_scores(X_he, y, groups, n_splits, l2, seed)
    S_hr = cv_oof_scores(X_hr, y, groups, n_splits, l2, seed)
    mask = ~(np.isnan(S_h) | np.isnan(S_he) | np.isnan(S_hr))
    ym = y[mask]
    return {
        "auroc_hidden": auroc(ym, S_h[mask]),
        "auroc_hidden_extra": auroc(ym, S_he[mask]),
        "auroc_hidden_random": auroc(ym, S_hr[mask]),
        "delta_vs_hidden": bootstrap_auroc_delta(ym, S_he[mask], S_h[mask], n_boot, seed),
        "delta_vs_random": bootstrap_auroc_delta(ym, S_he[mask], S_hr[mask], n_boot, seed),
    }


def leakage_check(X_extra, y, groups, threshold: float = 0.95, supervision=None,
                  n_splits: int = 5, seed: int = 0):
    """Flag suspected leakage: the extra (Bhava) features predict the target nearly perfectly on their
    own, or the Bhava SUPERVISION signal itself predicts the target (an orthogonality-control failure)."""
    extra_alone = evaluate_probe(np.asarray(X_extra, float), y, groups, n_splits=n_splits,
                                 seed=seed)["auroc"]
    flag = extra_alone >= threshold
    sup_auroc = None
    if supervision is not None:
        sup_auroc = auroc(np.asarray(y), np.asarray(supervision, float))
        flag = flag or (max(sup_auroc, 1.0 - sup_auroc) >= threshold)
    return {"extra_alone_auroc": float(extra_alone),
            "supervision_predicts_target_auroc": (None if sup_auroc is None else float(sup_auroc)),
            "leakage_suspected": bool(flag)}


# ---- decision (Stage-A: tested on synthetic only; NOT run on real data yet) ------------------------

PHASE4_LABELS = (
    "PHASE4_BHAVA_ADDS_SIGNAL", "PHASE4_HIDDEN_STATE_PREDICTIVE", "PHASE4_NOT_PREDICTIVE",
    "PHASE4_BHAVA_COLLAPSE", "PHASE4_BHAVA_LEAKAGE_SUSPECTED", "PHASE4_PILOT_INCONCLUSIVE",
)


def decide_phase4(auroc_hidden, delta_vs_hidden, delta_vs_random, effective_rank_bhava, leakage,
                  min_eff_rank: float = 3.0, min_delta: float = 0.05, hidden_floor: float = 0.55,
                  inconclusive: bool = False):
    """Map metrics to a PHASE4_* label per the design doc. Precedence: leakage > collapse >
    inconclusive > not-predictive > (adds-signal | hidden-predictive)."""
    if leakage:
        return "PHASE4_BHAVA_LEAKAGE_SUSPECTED"
    if effective_rank_bhava < min_eff_rank:
        return "PHASE4_BHAVA_COLLAPSE"
    if inconclusive:
        return "PHASE4_PILOT_INCONCLUSIVE"
    if auroc_hidden < hidden_floor:
        return "PHASE4_NOT_PREDICTIVE"
    adds = (delta_vs_hidden["delta"] >= min_delta and delta_vs_hidden["excludes_zero"]
            and delta_vs_random["delta"] >= min_delta and delta_vs_random["excludes_zero"])
    return "PHASE4_BHAVA_ADDS_SIGNAL" if adds else "PHASE4_HIDDEN_STATE_PREDICTIVE"
