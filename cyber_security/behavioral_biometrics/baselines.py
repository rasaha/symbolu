"""Strong, interpretable identity baselines + a temporal observer + fair fusion.

Marginal baselines (per participant, enroll-fit):
  * prototype        — negative Euclidean distance to the enrolled centroid (== nearest-centroid);
  * mahalanobis      — negative Mahalanobis distance to an enrolled Gaussian (ridge-regularized);
  * logistic         — a calibrated monotone map of the prototype distance (same AUC ranking).

Temporal baseline:
  * kalman_llt_cusum — local-linear-trend Kalman normalized innovation + CUSUM over a
                       per-window rate series (a transparent state-space observer).

Fusion:
  * quality_weighted_fusion — per-modality prototype scores fused by availability weight;
                              a FAIR all-modalities baseline that uses NO coupling features.

LEAKAGE DISCIPLINE: the standardizer and every model parameter are fit on the split's
TRAIN (enroll) records only, then applied to test. Test records never influence a fit.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from cyber_security.behavioral_biometrics import coupling, features
from cyber_security.behavioral_biometrics.config import DEFAULT, BiometricConfig
from cyber_security.behavioral_biometrics.numerics import (
    GaussianPrototype,
    Standardizer,
    auc,
    tpr_at_fixed_far,
)
from cyber_security.behavioral_biometrics.splits import SplitPlan

FeatureBuilder = Callable[[Dict[str, Any]], Dict[str, float]]


# ---- feature builders (choose the model surface; identifiers never included) ----

def build_marginal(record: Dict[str, Any]) -> Dict[str, float]:
    return dict(record.get("marginal", {}))


def build_modality(record: Dict[str, Any], modality: str) -> Dict[str, float]:
    pref = modality + "."
    return {k: v for k, v in record.get("marginal", {}).items() if k.startswith(pref)}


def build_marginal_plus_coupling(arm: str) -> FeatureBuilder:
    def builder(record: Dict[str, Any]) -> Dict[str, float]:
        out = dict(record.get("marginal", {}))
        out.update(coupling.coupling_view(record, arm))
        return out
    return builder


# ---- core identity evaluation (per-participant enroll-fit prototype) ----

def _fit_proto(model: str, Xe: np.ndarray, ridge: float):
    if model == "mahalanobis":
        return ("maha", GaussianPrototype.fit(Xe, ridge=ridge))
    return ("proto", Xe.mean(axis=0))


def _score(model, proto, X: np.ndarray) -> np.ndarray:
    kind, obj = proto
    if kind == "maha":
        return -obj.mahalanobis(X)
    return -np.linalg.norm(X - obj, axis=1)


def evaluate_identity(records: List[Dict[str, Any]], plan: SplitPlan,
                      builder: FeatureBuilder = build_marginal, model: str = "prototype",
                      cfg: BiometricConfig = DEFAULT) -> Dict[str, Any]:
    """Pooled genuine-vs-impostor scoring under a split. Returns scores/labels + AUC +
    TPR@FAR. Empty/degenerate splits return NaN metrics with ``usable=False``."""
    train_idx = plan.all_train_indices()
    if not train_idx or not plan.labeled_test():
        return {"usable": False, "reason": "empty_split", "n": 0}
    train_dicts = [builder(records[i]) for i in train_idx]
    names, Xtr = features.vectorize_dicts(train_dicts)
    if Xtr.shape[1] == 0:
        return {"usable": False, "reason": "no_features", "n": 0}
    std = Standardizer.fit(Xtr)

    protos = {}
    for pid, idxs in plan.enroll.items():
        Xe = std.apply(features.project_dicts([builder(records[i]) for i in idxs], names))
        if Xe.shape[0] >= 1:
            protos[pid] = _fit_proto(model, Xe, cfg.features.ridge)

    scores, labels, groups = [], [], []
    for row in plan.labeled_test():
        pid = row["pid"]
        if pid not in protos:
            continue
        X = std.apply(features.project_dicts([builder(records[row["idx"]])], names))
        scores.append(float(_score(model, protos[pid], X)[0]))
        labels.append(row["label"])
        groups.append(pid)
    if not scores or len(set(labels)) < 2:
        return {"usable": False, "reason": "insufficient_labels", "n": len(scores)}
    scores = np.array(scores)
    labels = np.array(labels)
    return {
        "usable": True,
        "model": model,
        "n_features": len(names),
        "n_genuine": int((labels == 1).sum()),
        "n_impostor": int((labels == 0).sum()),
        "auc": auc(scores, labels),
        "tpr_at_far": tpr_at_fixed_far(scores, labels, cfg.effects.fixed_far),
        "scores": scores.tolist(),
        "labels": labels.tolist(),
        "groups": groups,
    }


# ---- quality-weighted multimodal fusion (fair, NO coupling) ----

def quality_weighted_fusion(records: List[Dict[str, Any]], plan: SplitPlan,
                            cfg: BiometricConfig = DEFAULT,
                            modalities=("kbd", "ptr")) -> Dict[str, Any]:
    """Fuse per-modality prototype scores weighted by per-record modality availability.
    Uses only marginals — the fair all-modalities baseline the coupling arm must beat."""
    per_mod = {}
    for m in modalities:
        per_mod[m] = evaluate_identity(records, plan, lambda r, mm=m: build_modality(r, mm), cfg=cfg)
    # align on the labeled-test order
    rows = plan.labeled_test()
    rows = [r for r in rows if r["pid"] in plan.enroll]
    fused, labels = [], []
    # rebuild aligned scores
    aligned = {m: _aligned_scores(per_mod[m], records, plan) for m in modalities}
    avail_key = {"kbd": "q.kbd_available", "ptr": "q.ptr_available",
                 "touch": "q.touch_available", "motion": "q.motion_available"}
    for k, row in enumerate(rows):
        num, den = 0.0, 0.0
        for m in modalities:
            s = aligned[m].get(k)
            if s is None:
                continue
            w = float(records[row["idx"]].get("quality", {}).get(avail_key.get(m, ""), 1.0))
            num += w * s
            den += w
        if den > 0:
            fused.append(num / den)
            labels.append(row["label"])
    if len(set(labels)) < 2:
        return {"usable": False, "reason": "insufficient_labels"}
    fused = np.array(fused)
    labels = np.array(labels)
    return {"usable": True, "model": "quality_weighted_fusion",
            "auc": auc(fused, labels), "tpr_at_far": tpr_at_fixed_far(fused, labels, cfg.effects.fixed_far),
            "scores": fused.tolist(), "labels": labels.tolist()}


def _aligned_scores(result: Dict[str, Any], records, plan) -> Dict[int, float]:
    """Map labeled-test row index -> score for a completed evaluate_identity result."""
    if not result.get("usable"):
        return {}
    return {k: s for k, s in enumerate(result["scores"])}


# ---- temporal observer: local-linear-trend Kalman + CUSUM ----

def kalman_llt_cusum(series: np.ndarray, q_level: float = 1e-3, q_trend: float = 1e-4,
                     r_obs: float = 1.0, cusum_k: float = 0.5) -> Dict[str, np.ndarray]:
    """Local-linear-trend Kalman filter; returns normalized innovations and a one-sided
    CUSUM of |normalized innovation|. Transparent, standard machinery."""
    y = np.asarray(series, dtype=float)
    n = len(y)
    x = np.array([y[0] if n else 0.0, 0.0])  # [level, trend]
    P = np.eye(2)
    F = np.array([[1.0, 1.0], [0.0, 1.0]])
    Q = np.diag([q_level, q_trend])
    H = np.array([[1.0, 0.0]])
    innov = np.zeros(n)
    cusum = np.zeros(n)
    acc = 0.0
    for t in range(n):
        x = F @ x
        P = F @ P @ F.T + Q
        S = float((H @ P @ H.T)[0, 0] + r_obs)
        e = float(y[t] - (H @ x)[0])
        ne = e / np.sqrt(max(S, 1e-9))
        innov[t] = ne
        K = (P @ H.T / S).ravel()
        x = x + K * e
        P = (np.eye(2) - np.outer(K, H)) @ P
        acc = max(0.0, acc + abs(ne) - cusum_k)
        cusum[t] = acc
    return {"innovation": innov, "cusum": cusum,
            "anomaly": float(np.mean(np.abs(innov))) if n else 0.0,
            "cusum_max": float(cusum.max()) if n else 0.0}


def session_rate_series(session: Dict[str, Any], bin_s: float = 1.0) -> np.ndarray:
    """Per-bin keyboard+pointer event rate — the observable the temporal baseline runs on."""
    t = sorted(float(e.get("t_source", 0.0)) for e in session.get("events", []))
    if len(t) < 2:
        return np.array([0.0])
    lo, hi = t[0], t[-1]
    nb = max(1, int((hi - lo) / bin_s))
    counts, _ = np.histogram(t, bins=nb, range=(lo, hi))
    return counts.astype(float)
