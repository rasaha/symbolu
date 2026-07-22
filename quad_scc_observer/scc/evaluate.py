"""Evaluation: arm AUROC/calibration, and incremental DeLong tests for each SCC term.

Every predictor uses cross-validated out-of-fold probabilities (no leakage). The central test is
whether adding an SCC term to a baseline improves AUROC (DeLong on the same samples), over three
bases: confidence, confidence+entailment (the intrinsic bar, no evidence lookup), and
confidence+entailment+grounding.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from use import predict, metrics, stats
from . import arms

MEANINGFUL = 0.005


def impute(pool: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    """Median-impute NaNs (T coverage <1 in rare multi-system token collisions)."""
    out = {}
    for k, v in pool.items():
        v = np.asarray(v, dtype=float)
        if np.isnan(v).any():
            med = np.nanmedian(v) if np.isfinite(np.nanmedian(v)) else 0.0
            v = np.where(np.isnan(v), med, v)
        out[k] = v
    return out


def _oof(pool, names, y, seed=0):
    return predict.oof_probabilities(pool, names, y, seed=seed)


def evaluate_pool(pool: Dict[str, np.ndarray], seed_cv=0) -> Dict:
    y = pool["label_failure"].astype(int)
    n = len(y); nf = int(y.sum())
    res = {"n": n, "n_failure": nf, "failure_rate": float(y.mean()) if n else float("nan")}
    if len(np.unique(y)) < 2 or min(np.bincount(y)) < 10:
        res["skipped"] = "insufficient class balance"
        return res
    P = impute(pool)

    # arm predictors
    arm_defs = arms.arm_definitions(P)
    res["arms"] = {}
    arm_probs = {}
    for name, feats in arm_defs.items():
        if not feats:
            continue
        pr = _oof(P, feats, y, seed_cv)
        arm_probs[name] = pr
        ci = stats.bootstrap_auroc_ci(y, pr, n_boot=1000)
        res["arms"][name] = {"auroc": metrics.auroc(y, pr), "auroc_ci": [ci["lo"], ci["hi"]],
                             "auprc": metrics.auprc(y, pr), **metrics.full_calibration(y, np.clip(pr, 0, 1))}

    # single-term-alone AUROC (oriented univariate combo)
    g = arms.group_names(P)
    res["term_alone"] = {}
    for t in arms.TERMS:
        if g[t]:
            pr = _oof(P, g[t], y, seed_cv)
            res["term_alone"][t] = metrics.auroc(y, pr)

    # incremental DeLong tests: base vs base+term, for each term and each base
    res["increments"] = {}
    base_defs = arms.bases(P)
    for t in arms.TERMS:
        if not g[t]:
            continue
        res["increments"][t] = {}
        for bname, bfeats in base_defs.items():
            base_pr = _oof(P, bfeats, y, seed_cv)
            comb_pr = _oof(P, bfeats + g[t], y, seed_cv)
            d = stats.delong_roc_test(y, comb_pr, base_pr)
            res["increments"][t][bname] = {
                "base_auroc": d["auc2"], "combined_auroc": d["auc1"],
                "delta_auroc": d["auc1"] - d["auc2"], "p_one_sided": d["p_one_sided_1_gt_2"],
                "significant_and_meaningful": bool(d["p_one_sided_1_gt_2"] < 0.05
                                                   and (d["auc1"] - d["auc2"]) >= MEANINGFUL),
            }
    return res


def run(bundle: Dict) -> Dict:
    data = bundle["data"]; seeds = bundle["seeds"]; conds = bundle["conditions"]
    keys = [k for k in data[seeds[0]][conds[0]].keys()]

    def pool(cond_list, seed_list):
        return {k: np.concatenate([data[s][c][k] for s in seed_list for c in cond_list])
                for k in keys}

    usable = [c for c in conds
              if 0.0 < pool([c], seeds)["label_failure"].mean() < 1.0
              and min(np.bincount(pool([c], seeds)["label_failure"].astype(int))) >= 10]
    out = {"per_condition": {}, "per_seed": {}, "usable_conditions": usable}
    for c in conds:
        out["per_condition"][c] = evaluate_pool(pool([c], seeds))
    out["pooled"] = evaluate_pool(pool(usable, seeds))
    for s in seeds:
        out["per_seed"][s] = evaluate_pool(pool(usable, [s]))
    out["verdict"] = verdict(out)
    return out


def verdict(out: Dict) -> Dict:
    """Classify per the required enum. Intrinsic bar = increment over confidence+entailment
    (no symbolic evidence lookup). Grounding is a closed-world near-oracle (verification), so
    'beating grounding' is not the meaningful bar for the intrinsic coherence terms."""
    usable = out["usable_conditions"]
    pooled = out["pooled"]

    def term_survives(term, base):
        """significant + meaningful over `base`, reproducible across seeds, majority of conditions."""
        if "increments" not in pooled or term not in pooled["increments"]:
            return {"survives": False}
        pinc = pooled["increments"][term][base]
        per_cond = sum(1 for c in usable
                       if out["per_condition"][c].get("increments", {}).get(term, {})
                       .get(base, {}).get("significant_and_meaningful", False))
        per_seed = sum(1 for s in out["per_seed"]
                       if out["per_seed"][s].get("increments", {}).get(term, {})
                       .get(base, {}).get("significant_and_meaningful", False))
        n_seed = len(out["per_seed"])
        survives = (pinc["significant_and_meaningful"]
                    and per_cond >= max(2, (len(usable) + 1) // 2)
                    and per_seed >= (n_seed + 1) // 2)
        return {"survives": bool(survives), "pooled_delta": pinc["delta_auroc"],
                "pooled_p": pinc["p_one_sided"], "n_conditions": per_cond,
                "n_conditions_total": len(usable), "n_seeds": per_seed, "n_seeds_total": n_seed}

    intrinsic = {t: term_survives(t, "over_conf_entail") for t in ["S", "R", "T"]}
    over_conf = {t: term_survives(t, "over_confidence") for t in ["S", "R", "T"]}
    over_all = {t: term_survives(t, "over_conf_entail_ground") for t in arms.TERMS}
    # grounding oracle check
    g_auroc = pooled["arms"].get("3_conf_ground", {}).get("auroc", float("nan"))
    conf_auroc = pooled["arms"].get("1_confidence", {}).get("auroc", float("nan"))
    grounding_is_oracle = g_auroc >= 0.95 or (g_auroc - conf_auroc) >= 0.05
    e_redundant_with_grounding = True  # E and C share the adjacency verifier by construction

    survivors_intrinsic = [t for t in ["S", "R", "T"] if intrinsic[t]["survives"]]
    survivors_over_conf = [t for t in ["S", "R", "T"] if over_conf[t]["survives"]]

    if survivors_intrinsic:
        v = "SCC_ADDS_INDEPENDENT_SIGNAL"
    elif survivors_over_conf and not survivors_intrinsic:
        # adds over confidence but explained once entailment is included
        v = "ENTAILMENT_REDESCRIPTION"
    elif grounding_is_oracle:
        v = "GROUNDING_ONLY"
    elif any(over_conf[t]["n_conditions"] >= 1 for t in ["S", "R", "T"]):
        v = "CONDITION_SPECIFIC_ONLY"
    elif conf_auroc >= 0.6:
        v = "CONFIDENCE_DOMINATES"
    else:
        v = "INCONCLUSIVE"

    return {
        "verdict": v,
        "intrinsic_survivors_over_conf_entail": survivors_intrinsic,
        "survivors_over_confidence": survivors_over_conf,
        "term_survival_over_conf_entail": intrinsic,
        "term_survival_over_confidence": over_conf,
        "term_survival_over_all_baselines": over_all,
        "grounding_auroc": g_auroc, "confidence_auroc": conf_auroc,
        "grounding_is_closed_world_oracle": bool(grounding_is_oracle),
        "E_redundant_with_grounding_by_construction": e_redundant_with_grounding,
        "null_hypothesis": ("SCC components carry no predictive information about correctness "
                            "beyond confidence, entailment, and grounding."),
    }
