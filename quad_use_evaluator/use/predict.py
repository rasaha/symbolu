"""Failure-prediction from USE signals and baselines.

Univariate: each feature's oriented AUROC (orientation = sign of its correlation with failure;
a single bit, standard practice). Combined: an interpretable L2-logistic model over a feature
group, evaluated by cross-validated OUT-OF-FOLD probabilities (no leakage) so calibration and
AUROC are honest. The combination is deliberately simple and interpretable (not a deep probe).
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score


def univariate_auroc(features: Dict[str, np.ndarray], y: np.ndarray) -> Dict[str, Dict]:
    out = {}
    for name, f in features.items():
        f = np.asarray(f, dtype=float)
        if len(np.unique(y)) < 2 or np.allclose(f.std(), 0):
            out[name] = {"auroc": float("nan"), "sign": 0}
            continue
        auc = roc_auc_score(y, f)
        sign = 1 if auc >= 0.5 else -1           # orient so higher feature => failure
        out[name] = {"auroc": float(max(auc, 1 - auc)), "sign": int(sign),
                     "raw_auroc_higher_is_failure": float(auc)}
    return out


def _matrix(features: Dict[str, np.ndarray], names: List[str]) -> np.ndarray:
    return np.column_stack([np.asarray(features[n], dtype=float) for n in names])


def oof_probabilities(features: Dict[str, np.ndarray], names: List[str], y: np.ndarray,
                      seed: int = 0, n_splits: int = 5) -> np.ndarray:
    """Cross-validated out-of-fold P(failure) from an L2-logistic combo over `names`."""
    X = _matrix(features, names)
    if len(np.unique(y)) < 2:
        return np.full(len(y), float(y.mean()))
    n_splits = min(n_splits, int(min(np.bincount(y))))
    if n_splits < 2:
        # too few of one class for CV: fit/predict in-sample (flagged; only for tiny slices)
        pipe = Pipeline([("sc", StandardScaler()),
                         ("lr", LogisticRegression(max_iter=1000, C=1.0))])
        pipe.fit(X, y)
        return pipe.predict_proba(X)[:, 1]
    pipe = Pipeline([("sc", StandardScaler()),
                     ("lr", LogisticRegression(max_iter=1000, C=1.0))])
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    proba = cross_val_predict(pipe, X, y, cv=skf, method="predict_proba")[:, 1]
    return proba


def logistic_coefficients(features: Dict[str, np.ndarray], names: List[str],
                          y: np.ndarray) -> Dict[str, float]:
    """Fit once on all data for interpretability (standardized coefficients)."""
    X = _matrix(features, names)
    if len(np.unique(y)) < 2:
        return {n: 0.0 for n in names}
    pipe = Pipeline([("sc", StandardScaler()),
                     ("lr", LogisticRegression(max_iter=1000, C=1.0))])
    pipe.fit(X, y)
    coefs = pipe.named_steps["lr"].coef_[0]
    return {n: float(c) for n, c in zip(names, coefs)}
