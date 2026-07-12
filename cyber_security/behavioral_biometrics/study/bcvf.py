"""BCVF evaluation — uncertainty-normalized consistency between STRUCTURALLY DISTINCT
estimators of the SAME latent identity.

Narrowed, falsifiable form only. EXPLICITLY EXCLUDED: a second-order Δ²d primary
detector; treating fast/slow windows of one stream as independent estimators; any claim
that low disagreement means "safe"; challenge deferral based solely on smoothness.

Normalized disagreement:  q = (z1 − z2)² / (σ1² + σ2² + ε)
Optional robust accumulation:  M_t = η M_{t-1} + ψ(q − κ),  ψ = clipped positive part.

Fair, CAPACITY-MATCHED contrast:
  * MM_BCVF_NO_DISAGREEMENT — joint logistic on [z1, z2, σ1, σ2, noise]
  * MM_BCVF                  — same joint logistic on [z1, z2, σ1, σ2, q]
Only the 5th input differs (a matched noise feature vs the real disagreement), so BCVF
cannot win on capacity — only on the information in the disagreement.

Kill criterion: BCVF is unsupported unless it adds a preregistered practical AUC
improvement over the fair joint baseline WITHOUT worsening false challenges or
calibration.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from cyber_security.behavioral_biometrics.numerics import LogisticRegression, Standardizer, auc
from cyber_security.behavioral_biometrics.study import metrics, origin
from cyber_security.behavioral_biometrics.study.effects import DEFAULT, StudyEffects

BCVF_INCREMENTAL_VALUE_SUPPORTED = "BCVF_INCREMENTAL_VALUE_SUPPORTED"
BCVF_INCREMENTAL_VALUE_SMALL_EFFECT = "BCVF_INCREMENTAL_VALUE_SMALL_EFFECT"
BCVF_NO_INCREMENTAL_VALUE = "BCVF_NO_INCREMENTAL_VALUE"
BCVF_REGRESSES = "BCVF_REGRESSES"
BCVF_NOT_ELIGIBLE = "BCVF_NOT_ELIGIBLE"
BCVF_PATH_VERIFIED = "BCVF_PATH_VERIFIED"

# estimator kinds that are NOT structurally independent (forbidden as a BCVF pair)
_SAME_STREAM_FAMILY = {"ewma_fast", "ewma_slow", "window_fast", "window_slow"}


def normalized_disagreement(z1, z2, s1, s2, eps: float = 1e-3) -> np.ndarray:
    z1, z2, s1, s2 = map(lambda a: np.asarray(a, float), (z1, z2, s1, s2))
    return (z1 - z2) ** 2 / (s1 ** 2 + s2 ** 2 + eps)


def robust_accumulate(q: np.ndarray, *, eta: float = 0.9, kappa: float = 0.5,
                      clip: float = 5.0) -> np.ndarray:
    """M_t = η M_{t-1} + ψ(q−κ), ψ = clipped positive part. Temporal accumulation."""
    q = np.asarray(q, float)
    M = np.zeros(len(q))
    acc = 0.0
    for t in range(len(q)):
        acc = eta * acc + min(clip, max(0.0, q[t] - kappa))
        M[t] = acc
    return M


def estimator_pair_eligible(kind1: str, kind2: str) -> Tuple[bool, str]:
    if not kind1 or not kind2:
        return False, "missing_estimator_kind"
    if kind1 == kind2:
        return False, "same_estimator_kind (not structurally independent)"
    if kind1 in _SAME_STREAM_FAMILY and kind2 in _SAME_STREAM_FAMILY:
        return False, "fast/slow same-stream pair forbidden"
    return True, "ok"


def _clustered_split(groups: np.ndarray, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    uniq = np.unique(groups)
    rng = np.random.default_rng(seed)
    rng.shuffle(uniq)
    n_train = max(1, int(len(uniq) * 0.6))
    train_g = set(uniq[:n_train].tolist())
    train = np.array([g in train_g for g in groups])
    return train, ~train


def _fit_score(Xtr, ytr, Xte) -> np.ndarray:
    std = Standardizer.fit(Xtr)
    lr = LogisticRegression.fit(std.apply(Xtr), ytr)
    return lr.predict_proba(std.apply(Xte))


def evaluate_bcvf(rows: Dict[str, Any], *, estimator_kinds=("keyboard", "pointer"),
                  cfg: StudyEffects = DEFAULT, iters: Optional[int] = None,
                  seed: int = 0) -> Dict[str, Any]:
    iters = iters if iters is not None else cfg.bootstrap_iters
    z1 = np.asarray(rows["z1"], float); z2 = np.asarray(rows["z2"], float)
    s1 = np.asarray(rows["s1"], float); s2 = np.asarray(rows["s2"], float)
    labels = np.asarray(rows["labels"]); groups = np.asarray(rows["groups"])

    ok, why = estimator_pair_eligible(*estimator_kinds)
    e = cfg.effects
    tr, te = _clustered_split(groups, seed)
    # each estimator must independently show identity signal on held-out data
    auc1 = auc(z1[te], labels[te]) if len(set(labels[te].tolist())) > 1 else float("nan")
    auc2 = auc(z2[te], labels[te]) if len(set(labels[te].tolist())) > 1 else float("nan")
    both_signal = (auc1 == auc1 and auc2 == auc2 and auc1 > e.min_marginal_auc
                   and auc2 > e.min_marginal_auc)
    eligible = ok and both_signal

    q = normalized_disagreement(z1, z2, s1, s2)
    rng = np.random.default_rng(seed + 1)
    noise = rng.normal(0, 1, len(q))            # capacity-matching dummy feature
    base = np.column_stack([z1, z2, s1, s2])
    X_no = np.column_stack([base, noise])       # joint + matched noise
    X_bc = np.column_stack([base, q])           # joint + disagreement

    p_no = _fit_score(X_no[tr], labels[tr], X_no[te])
    p_bc = _fit_score(X_bc[tr], labels[tr], X_bc[te])
    yte, gte = labels[te], groups[te]
    gain = metrics.clustered_paired_auc_diff(p_bc, p_no, yte, gte, iters=iters,
                                             alpha=e.ci_alpha, seed=cfg.seed)
    fc_no = 1.0 - metrics.summary(p_no, yte, e.fixed_far)["tar_at_far"]
    fc_bc = 1.0 - metrics.summary(p_bc, yte, e.fixed_far)["tar_at_far"]
    brier_no = float(np.mean((p_no - yte) ** 2))
    brier_bc = float(np.mean((p_bc - yte) ** 2))
    return {"usable": True, "eligible": eligible, "eligibility_reason": why,
            "estimator_auc": {"z1": auc1, "z2": auc2}, "both_show_signal": both_signal,
            "auc_no_disagreement": auc(p_no, yte), "auc_bcvf": auc(p_bc, yte),
            "gain": gain, "false_challenge_increase": float(fc_bc - fc_no),
            "calibration_regression": float(brier_bc - brier_no)}


def classify_bcvf(r: Dict[str, Any], cfg: StudyEffects = DEFAULT) -> str:
    if not r.get("usable") or not r.get("eligible"):
        return BCVF_NOT_ELIGIBLE
    e = cfg.effects
    g = r["gain"]
    if (r["false_challenge_increase"] > e.max_false_challenge_regression
            or r["calibration_regression"] > e.min_ece_improvement):
        if g["lo"] <= 0.0:
            return BCVF_REGRESSES
    if g["hi"] <= 0.0:
        return BCVF_REGRESSES if g["point"] < 0 else BCVF_NO_INCREMENTAL_VALUE
    if g["lo"] <= 0.0:
        return BCVF_NO_INCREMENTAL_VALUE
    if g["lo"] > e.min_auc_improvement:
        return BCVF_INCREMENTAL_VALUE_SUPPORTED
    return BCVF_INCREMENTAL_VALUE_SMALL_EFFECT


def bcvf_verdict(records_or_rows, rows: Optional[Dict[str, Any]] = None, *,
                 estimator_kinds=("keyboard", "pointer"), cfg: StudyEffects = DEFAULT,
                 iters: Optional[int] = None) -> Dict[str, Any]:
    """Guarded BCVF verdict. ``records_or_rows`` supplies the origin (a list of records
    or a dict with an 'origin'); ``rows`` are the estimator rows."""
    if rows is None and isinstance(records_or_rows, dict) and "z1" in records_or_rows:
        rows, origin_records = records_or_rows, [{"meta": {"data_origin": records_or_rows.get(
            "origin", "MOCK_TEST_ONLY")}}]
    else:
        origin_records = (records_or_rows if isinstance(records_or_rows, list)
                          else [{"meta": {"data_origin": records_or_rows.get("origin")}}])
    r = evaluate_bcvf(rows, estimator_kinds=estimator_kinds, cfg=cfg, iters=iters)
    g = origin.guarded(origin_records, scientific=lambda: classify_bcvf(r, cfg),
                       path_verified=BCVF_PATH_VERIFIED + "_" + classify_bcvf(r, cfg),
                       eligible=r.get("eligible", False))
    g["analysis"] = r
    return g
