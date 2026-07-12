"""Signal-existence analysis harness (A–F).

Reports measured effects with bootstrap confidence intervals. It does NOT emit final
verdicts — that is ``verdicts.py``, which additionally enforces the synthetic-data
guard and minimum-sample requirements. All fits are train-only via ``splits`` /
``baselines`` (leakage discipline). Numeric-only; deterministic given the seed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from cyber_security.behavioral_biometrics import baselines, features, quality, splits
from cyber_security.behavioral_biometrics.config import DEFAULT, BiometricConfig
from cyber_security.behavioral_biometrics.numerics import Standardizer, auc


# ---------------------------------------------------------------------------
# bootstrap helpers (paired across arms: arms share the same test rows)
# ---------------------------------------------------------------------------

def _auc_ci(scores, labels, iters, alpha, seed):
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels)
    rng = np.random.default_rng(seed)
    n = len(scores)
    vals = []
    for _ in range(iters):
        idx = rng.integers(0, n, n)
        if len(set(labels[idx].tolist())) < 2:
            continue
        vals.append(auc(scores[idx], labels[idx]))
    if not vals:
        return {"point": auc(scores, labels), "lo": float("nan"), "hi": float("nan")}
    return {"point": auc(scores, labels), "lo": float(np.quantile(vals, alpha / 2)),
            "hi": float(np.quantile(vals, 1 - alpha / 2))}


def _paired_auc_diff_ci(scores_a, scores_b, labels, iters, alpha, seed):
    """CI of AUC(a) - AUC(b) where a and b are scores for the SAME test rows."""
    a = np.asarray(scores_a, dtype=float)
    b = np.asarray(scores_b, dtype=float)
    labels = np.asarray(labels)
    rng = np.random.default_rng(seed)
    n = len(a)
    diffs = []
    for _ in range(iters):
        idx = rng.integers(0, n, n)
        if len(set(labels[idx].tolist())) < 2:
            continue
        diffs.append(auc(a[idx], labels[idx]) - auc(b[idx], labels[idx]))
    point = auc(a, labels) - auc(b, labels)
    if not diffs:
        return {"point": point, "lo": float("nan"), "hi": float("nan")}
    return {"point": point, "lo": float(np.quantile(diffs, alpha / 2)),
            "hi": float(np.quantile(diffs, 1 - alpha / 2))}


# ---------------------------------------------------------------------------
# A. Instrument quality
# ---------------------------------------------------------------------------

def instrument_quality(quality_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(quality_summaries)
    counts = {quality.READY: 0, quality.DEGRADED: 0, quality.NOT_READY: 0}
    reasons: Dict[str, int] = {}
    for q in quality_summaries:
        counts[q.get("verdict", quality.NOT_READY)] += 1
        for r in q.get("reasons", []):
            reasons[r] = reasons.get(r, 0) + 1
    ready_frac = counts[quality.READY] / n if n else 0.0
    return {"analysis": "A_instrument_quality", "n_sessions": n, "counts": counts,
            "ready_fraction": ready_frac, "failure_reasons": reasons}


# ---------------------------------------------------------------------------
# B. Within-user repeatability
# ---------------------------------------------------------------------------

def within_user_repeatability(records: List[Dict[str, Any]], cfg: BiometricConfig = DEFAULT
                              ) -> Dict[str, Any]:
    genuine = [r for r in records if r["meta"].get("condition") in ("genuine", "unspecified")]
    names, X = features.vectorize([r for r in genuine], namespaces=("marginal",))
    if X.shape[0] < 4:
        return {"analysis": "B_within_user_repeatability", "usable": False, "reason": "too_few"}
    Xs = Standardizer.fit(X).apply(X)
    pids = [r["meta"]["participant_pseudonym"] for r in genuine]
    within, between = [], []
    for i in range(len(Xs)):
        for j in range(i + 1, len(Xs)):
            d = float(np.linalg.norm(Xs[i] - Xs[j]))
            (within if pids[i] == pids[j] else between).append(d)
    if not within or not between:
        return {"analysis": "B_within_user_repeatability", "usable": False, "reason": "no_pairs"}
    within = np.array(within)
    between = np.array(between)
    pooled = np.sqrt((within.var() + between.var()) / 2) or 1.0
    separation = float((between.mean() - within.mean()) / pooled)
    # AUC of same-user (label 1) vs different-user using -distance
    dist = np.concatenate([within, between])
    lab = np.concatenate([np.ones(len(within)), np.zeros(len(between))])
    ci = _auc_ci(-dist, lab, cfg.bootstrap_iters, cfg.effects.ci_alpha, cfg.master_seed)
    return {"analysis": "B_within_user_repeatability", "usable": True,
            "within_mean": float(within.mean()), "between_mean": float(between.mean()),
            "separation": separation, "same_vs_diff_auc": ci,
            "n_within": int(len(within)), "n_between": int(len(between))}


# ---------------------------------------------------------------------------
# C. Marginal identity signal
# ---------------------------------------------------------------------------

def marginal_identity(records: List[Dict[str, Any]], plan: splits.SplitPlan,
                      cfg: BiometricConfig = DEFAULT, model: str = "prototype") -> Dict[str, Any]:
    res = baselines.evaluate_identity(records, plan, baselines.build_marginal, model=model, cfg=cfg)
    out = {"analysis": "C_marginal_identity", "split": plan.name, "usable": res.get("usable", False)}
    if not res.get("usable"):
        out["reason"] = res.get("reason")
        return out
    ci = _auc_ci(res["scores"], res["labels"], cfg.bootstrap_iters, cfg.effects.ci_alpha,
                 cfg.master_seed)
    out.update({"auc": ci, "tpr_at_far": res["tpr_at_far"], "fixed_far": cfg.effects.fixed_far,
                "n_genuine": res["n_genuine"], "n_impostor": res["n_impostor"],
                "n_features": res["n_features"], "model": model})
    return out


# ---------------------------------------------------------------------------
# D. Coupling residual signal (the primary coupling contrast)
# ---------------------------------------------------------------------------

def coupling_residual(records: List[Dict[str, Any]], plan: splits.SplitPlan,
                      cfg: BiometricConfig = DEFAULT) -> Dict[str, Any]:
    arms = {
        "marginal": baselines.build_marginal,
        "plus_real": baselines.build_marginal_plus_coupling("real"),
        "plus_shuf": baselines.build_marginal_plus_coupling("shuf"),
        "plus_ctxm": baselines.build_marginal_plus_coupling("ctxm"),
    }
    results = {k: baselines.evaluate_identity(records, plan, b, cfg=cfg) for k, b in arms.items()}
    out = {"analysis": "D_coupling_residual", "split": plan.name}
    if not all(r.get("usable") for r in results.values()):
        out["usable"] = False
        out["reason"] = "arm_unusable"
        return out
    # arms share identical test rows/labels -> paired
    labels = results["marginal"]["labels"]
    out["usable"] = True
    out["auc"] = {k: auc(np.array(r["scores"]), np.array(labels)) for k, r in results.items()}
    seed = cfg.master_seed
    out["gain_vs_marginal"] = _paired_auc_diff_ci(results["plus_real"]["scores"],
                                                  results["marginal"]["scores"], labels,
                                                  cfg.bootstrap_iters, cfg.effects.ci_alpha, seed)
    out["gain_vs_shuffled"] = _paired_auc_diff_ci(results["plus_real"]["scores"],
                                                  results["plus_shuf"]["scores"], labels,
                                                  cfg.bootstrap_iters, cfg.effects.ci_alpha, seed + 1)
    out["gain_vs_context"] = _paired_auc_diff_ci(results["plus_real"]["scores"],
                                                 results["plus_ctxm"]["scores"], labels,
                                                 cfg.bootstrap_iters, cfg.effects.ci_alpha, seed + 2)
    # false-challenge change: genuine rejection at fixed FAR (higher == worse)
    fc_marginal = 1.0 - results["marginal"]["tpr_at_far"]
    fc_real = 1.0 - results["plus_real"]["tpr_at_far"]
    out["false_challenge_increase"] = float(fc_real - fc_marginal)
    out["n_genuine"] = results["marginal"]["n_genuine"]
    out["n_impostor"] = results["marginal"]["n_impostor"]
    return out


# ---------------------------------------------------------------------------
# E. Device-instance confound
# ---------------------------------------------------------------------------

def device_confound(records: List[Dict[str, Any]], cfg: BiometricConfig = DEFAULT) -> Dict[str, Any]:
    same = marginal_identity(records, splits.session_disjoint(records, seed=cfg.master_seed), cfg)
    dev_plan = splits.device_instance(records)
    cross = marginal_identity(records, dev_plan, cfg)
    out = {"analysis": "E_device_confound", "same_device": same}
    if not cross.get("usable"):
        out.update({"cross_device_assessable": False, "reason": dev_plan.notes or "no_second_device"})
        return out
    out.update({"cross_device_assessable": True, "cross_device": cross})
    if same.get("usable"):
        out["auc_drop_same_minus_cross"] = float(same["auc"]["point"] - cross["auc"]["point"])
    return out


# ---------------------------------------------------------------------------
# F. Task / context confound
# ---------------------------------------------------------------------------

def task_context_confound(records: List[Dict[str, Any]], plan: splits.SplitPlan,
                          cfg: BiometricConfig = DEFAULT) -> Dict[str, Any]:
    d = coupling_residual(records, plan, cfg)
    out = {"analysis": "F_task_context_confound", "split": plan.name}
    if not d.get("usable"):
        out["usable"] = False
        out["reason"] = d.get("reason")
        return out
    resid = [r["coupling"].get("resid_vs_ctxm", 0.0) for r in records
             if r.get("coupling", {}).get("coupling_available")]
    out["usable"] = True
    out["gain_vs_marginal"] = d["gain_vs_marginal"]      # coupling over marginal
    out["gain_vs_context"] = d["gain_vs_context"]        # coupling over context-matched control
    out["mean_resid_vs_ctxm"] = float(np.mean(resid)) if resid else 0.0
    # context artifact if the real-vs-context gain CI includes/below 0 while real-vs-marginal is +
    out["context_explains_gain"] = bool(d["gain_vs_context"]["lo"] <= 0.0
                                        and d["gain_vs_marginal"]["lo"] > 0.0)
    return out
