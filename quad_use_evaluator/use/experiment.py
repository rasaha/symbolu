"""Orchestration: pool data, fit predictors (OOF), compare USE vs baselines, verdict.

Central falsification test: does USE add predictive value for failure detection BEYOND standard
confidence baselines? We test (a) best-USE vs the baseline combo, and (b) the incremental value
of USE on top of baselines (baseline+USE vs baseline), via the DeLong test on the same samples,
per condition and pooled, requiring reproducibility across model seeds.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from .channels import CHANNEL_SETS
from .phases import MAPPINGS
from .use_signals import SIGNAL_NAMES
from .baselines import BASELINE_NAMES
from . import predict, metrics, stats

BASE_CONF = ["token_prob", "logprob", "neg_entropy", "margin", "seq_confidence", "attn_neg_entropy"]


def _pool(data: Dict, seeds: List[int], condition: str) -> Dict[str, np.ndarray]:
    """Concatenate a condition's arrays across seeds."""
    keys = data[seeds[0]][condition].keys()
    out = {}
    for k in keys:
        out[k] = np.concatenate([data[s][condition][k] for s in seeds])
    return out


def _feat(pool: Dict[str, np.ndarray], names: List[str]) -> Dict[str, np.ndarray]:
    return {n: pool[n] for n in names}


def use_group_names(cs: str, mp: str) -> List[str]:
    return [f"USE::{cs}::{mp}::{s}" for s in SIGNAL_NAMES]


def all_use_names(pool: Dict[str, np.ndarray]) -> List[str]:
    return [k for k in pool if k.startswith("USE::")]


def base_names() -> List[str]:
    return [f"BASE::{b}" for b in BASE_CONF]


def evaluate_condition(pool: Dict[str, np.ndarray], seed_cv: int = 0) -> Dict:
    y = pool["label_failure"].astype(int)
    n = len(y); n_fail = int(y.sum())
    res = {"n": n, "n_failure": n_fail, "failure_rate": float(y.mean()) if n else float("nan")}
    if len(np.unique(y)) < 2 or min(np.bincount(y)) < 10:
        res["skipped"] = "insufficient class balance for reliable AUROC"
        return res

    # --- univariate AUROC (USE signals + baselines) ---
    uni_feats = {k: pool[k] for k in pool if k.startswith(("USE::", "BASE::"))}
    res["univariate"] = predict.univariate_auroc(uni_feats, y)

    # --- combined predictors (OOF probabilities) ---
    groups = {
        "baseline_combo": base_names(),
        "use_all": all_use_names(pool),
        "use_quad": [k for k in pool if k.startswith("USE::quad_heads::")],
        "combined_base_use": base_names() + all_use_names(pool),
    }
    # best single USE (channel_set,mapping) group by OOF AUROC
    best_cfg, best_auc, best_probs = None, -1, None
    for cs in CHANNEL_SETS:
        for mp in MAPPINGS:
            names = use_group_names(cs, mp)
            if not all(k in pool for k in names):
                continue
            probs = predict.oof_probabilities(pool, names, y, seed=seed_cv)
            auc = metrics.auroc(y, probs)
            if auc == auc and auc > best_auc:
                best_auc, best_cfg, best_probs = auc, (cs, mp), probs
    # parsimonious incremental: baselines + only the single best USE group (avoids the
    # high-dimensional artifact of dumping all ~270 USE features into one logistic).
    best_group_names = use_group_names(*best_cfg) if best_cfg else []
    groups["combined_base_usebest"] = base_names() + best_group_names
    groups["combined_base_usequad"] = base_names() + [k for k in pool if k.startswith("USE::quad_heads::")]
    groups_probs = {g: predict.oof_probabilities(pool, names, y, seed=seed_cv)
                    for g, names in groups.items()}
    groups_probs["use_best"] = best_probs
    # single best baseline (token_prob) oriented
    tp = pool["BASE::token_prob"]
    tp_score = -tp  # higher => failure
    random_score = pool["BASE::random"]

    # --- metrics per predictor ---
    def pack(probs_or_score, is_prob=True):
        auc = metrics.auroc(y, probs_or_score)
        ci = stats.bootstrap_auroc_ci(y, probs_or_score)
        out = {"auroc": auc, "auroc_ci": [ci["lo"], ci["hi"]],
               "auprc": metrics.auprc(y, probs_or_score)}
        if is_prob:
            out.update(metrics.full_calibration(y, np.clip(probs_or_score, 0, 1)))
            out.update(metrics.prf1(y, np.clip(probs_or_score, 0, 1)))
        return out

    res["predictors"] = {g: pack(p) for g, p in groups_probs.items()}
    res["predictors"]["token_prob_only"] = pack(tp_score, is_prob=False)
    res["predictors"]["random"] = pack(random_score, is_prob=False)
    res["use_best_config"] = best_cfg

    # --- DeLong tests (same samples) ---
    res["tests"] = {
        "use_best_vs_baseline_combo":
            stats.delong_roc_test(y, groups_probs["use_best"], groups_probs["baseline_combo"]),
        "use_all_vs_baseline_combo":
            stats.delong_roc_test(y, groups_probs["use_all"], groups_probs["baseline_combo"]),
        "combined_vs_baseline_combo":     # incremental value of ALL USE on top of baselines (high-dim)
            stats.delong_roc_test(y, groups_probs["combined_base_use"], groups_probs["baseline_combo"]),
        "combined_best_vs_baseline":      # parsimonious incremental (baseline + best USE group)
            stats.delong_roc_test(y, groups_probs["combined_base_usebest"], groups_probs["baseline_combo"]),
        "combined_quad_vs_baseline":      # incremental of Quad-native USE on top of baselines
            stats.delong_roc_test(y, groups_probs["combined_base_usequad"], groups_probs["baseline_combo"]),
        "use_best_vs_token_prob":
            stats.delong_roc_test(y, groups_probs["use_best"], tp_score),
    }
    res["logistic_coefficients_combined"] = predict.logistic_coefficients(
        pool, base_names() + all_use_names(pool), y)
    return res


def run_all(bundle: Dict) -> Dict:
    data = bundle["data"]; seeds = bundle["seeds"]; conds = bundle["conditions"]
    results = {"per_condition": {}, "per_seed_condition": {}}
    # pooled across seeds
    for c in conds:
        pool = _pool(data, seeds, c)
        results["per_condition"][c] = evaluate_condition(pool, seed_cv=0)
    # pooled across ALL conditions with adequate failures (the primary omnibus test)
    all_pool = {}
    keys = data[seeds[0]][conds[0]].keys()
    usable = [c for c in conds
              if _pool(data, seeds, c)["label_failure"].mean() not in (0.0, 1.0)]
    for k in keys:
        all_pool[k] = np.concatenate([data[s][c][k] for s in seeds for c in usable])
    results["pooled_all"] = evaluate_condition(all_pool, seed_cv=0)
    results["pooled_conditions_used"] = usable
    # per-seed reproducibility (pooled over conditions within each seed)
    for s in seeds:
        sp = {}
        for k in keys:
            sp[k] = np.concatenate([data[s][c][k] for c in usable])
        results["per_seed_condition"][s] = evaluate_condition(sp, seed_cv=0)
    results["verdict"] = verdict(results)
    return results


def verdict(results: Dict) -> Dict:
    """Reject the null only if USE adds statistically significant, reproducible predictive value
    over the confidence baselines across multiple conditions."""
    conds = results["per_condition"]
    usable = [c for c, r in conds.items() if "tests" in r]
    def sig_incremental(r):
        # Require BOTH the full-USE and the parsimonious (best-group) incremental to be
        # significant, so a ~270-feature high-dimensional overfit alone cannot reject the null.
        tf = r["tests"]["combined_vs_baseline_combo"]
        tp = r["tests"]["combined_best_vs_baseline"]
        full_ok = tf["p_one_sided_1_gt_2"] < 0.05 and tf["auc1"] > tf["auc2"] + 0.005
        pars_ok = tp["p_one_sided_1_gt_2"] < 0.05 and tp["auc1"] > tp["auc2"] + 0.005
        return full_ok and pars_ok
    def use_beats_base(r):
        t = r["tests"]["use_best_vs_baseline_combo"]
        return t["p_one_sided_1_gt_2"] < 0.05 and t["auc1"] > t["auc2"]
    incr = {c: sig_incremental(conds[c]) for c in usable}
    ubb = {c: use_beats_base(conds[c]) for c in usable}
    pooled = results["pooled_all"]
    pooled_incr = ("tests" in pooled and sig_incremental(pooled))
    n_incr = sum(incr.values())
    # reproducible across seeds: incremental significant in majority of seeds
    seed_incr = {s: (("tests" in r) and sig_incremental(r))
                 for s, r in results["per_seed_condition"].items()}
    reproducible = sum(seed_incr.values()) >= (len(seed_incr) + 1) // 2
    reject_null = (n_incr >= max(2, (len(usable) + 1) // 2)) and pooled_incr and reproducible
    return {
        "reject_null": bool(reject_null),
        "verdict": ("USE_ADDS_PREDICTIVE_VALUE" if reject_null
                    else "NULL_NOT_REJECTED_USE_NO_VALUE_BEYOND_CONFIDENCE"),
        "incremental_significant_per_condition": incr,
        "use_beats_baseline_per_condition": ubb,
        "n_conditions_incremental": n_incr, "n_conditions_usable": len(usable),
        "pooled_incremental_significant": bool(pooled_incr),
        "reproducible_across_seeds": bool(reproducible),
        "per_seed_incremental_significant": seed_incr,
        "null_hypothesis": ("Internal semantic-coherence measurements contain no additional "
                            "predictive information beyond standard model confidence measures."),
    }
