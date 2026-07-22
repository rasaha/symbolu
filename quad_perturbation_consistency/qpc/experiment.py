"""Orchestration: train each arm, evaluate the full benchmark, run guardrails, aggregate, test.

Benchmark suite and model/data configuration are the SAME as the previous studies (reused from
``qgr`` with the frozen bounded geometry), so results are directly comparable.  BD-A and BD-D
are produced by the unmodified prior package; the three consistency arms by ``train_sync``.
"""

from __future__ import annotations

import statistics
from typing import Dict, List, Optional

import torch

from . import _qgr_path  # noqa: F401
from qgr.experiment import (
    FrozenConfig, eval_model_on_conditions, eval_seqlen_curve, steps_to_threshold,
    hard_condition_cfgs_names, PREREGISTERED_HARD,
)
from qgr.train import train_arm
from qgr.metrics import evaluate
from qgr.causal import Ablator

from .train_sync import SyncTrainConfig, train_sync
from .perturbations import AugConfig
from .health import attention_health, stability, guardrail2_health
from .progressive import progressive_curve
from . import stats as qstats

ARMS = ["BD-A", "BD-D", "BD-Sync", "BD-Sync-Early", "BD-Shuffled"]
CONS_ARMS = ["BD-Sync", "BD-Sync-Early", "BD-Shuffled"]


def bounded_fc(alpha: float = 4.0) -> FrozenConfig:
    fc = FrozenConfig()
    fc.bounded = True
    fc.bound_alpha = alpha
    return fc


def _sync_cfg(fc: FrozenConfig, mode: str, seed: int, lam: float, cutoff: float,
              shuffled: bool, aug: AugConfig) -> SyncTrainConfig:
    return SyncTrainConfig(
        mode=("shuffled" if shuffled else "sync"),
        lambda_consistency=lam, tau=fc.tau, stop_grad_target=True,
        consistency_cutoff_frac=cutoff, steps=fc.steps, batch_size=fc.batch_size, lr=fc.lr,
        weight_decay=fc.weight_decay, warmup=fc.warmup, eval_every=fc.eval_every,
        eval_batches=fc.eval_batches, seed=seed, log_curves=True, aug=aug)


def train_labeled(label: str, fc: FrozenConfig, seed: int, lam: float, aug: AugConfig,
                  early_frac: float = 0.10):
    """Train one labeled arm; return (model, train_summary)."""
    if label == "BD-A":
        r = train_arm(fc.model_cfg(), fc.base_mqar(), fc.train_cfg("A", seed))
    elif label == "BD-D":
        r = train_arm(fc.model_cfg(), fc.base_mqar(), fc.train_cfg("D", seed))
    elif label == "BD-Sync":
        r = train_sync(fc.model_cfg(), fc.base_mqar(),
                       _sync_cfg(fc, "sync", seed, lam, 1.0, False, aug))
    elif label == "BD-Sync-Early":
        r = train_sync(fc.model_cfg(), fc.base_mqar(),
                       _sync_cfg(fc, "sync", seed, lam, early_frac, False, aug))
    elif label == "BD-Shuffled":
        r = train_sync(fc.model_cfg(), fc.base_mqar(),
                       _sync_cfg(fc, "sync", seed, lam, 1.0, True, aug))
    else:
        raise ValueError(label)
    return r["model"], r


@torch.no_grad()
def causal_necessity(model, fc: FrozenConfig, seed: int, n_batches=8) -> Dict[str, float]:
    """Guardrail 1: zeroing the Quad-retrieval (attention) output must collapse to chance."""
    mq = fc.base_mqar()
    clean = evaluate(model, mq, seed, "test", n_batches, fc.batch_size)["acc"]
    ab = Ablator(model); ab.ablate_attn([0, 1], "zero")
    try:
        zeroed = evaluate(model, mq, seed, "test", n_batches, fc.batch_size)["acc"]
    finally:
        ab.clear()
    # chance ~ 1 / (#candidate keys); base num_kv candidates
    chance = 1.0 / max(fc.num_kv, 2)
    return {"clean": clean, "attn_zero_all": zeroed, "retained": zeroed / max(clean, 1e-9),
            "chance": chance, "collapses_to_chance": bool(zeroed <= chance * 1.5)}


def evaluate_arm(label: str, model, fc: FrozenConfig, seed: int, aug: AugConfig,
                 with_progressive=True, with_causal=True) -> Dict:
    conds = eval_model_on_conditions(model, fc, seed)
    seqlen = eval_seqlen_curve(model, fc, seed)
    hlth = attention_health(model, fc.base_mqar(), seed)
    stab = stability(model, fc.base_mqar(), seed, aug)
    hlth = {**hlth, **stab}
    g2 = guardrail2_health(hlth)
    res = {
        "seed": seed, "conditions": conds, "seqlen_curve": seqlen,
        "health": hlth, "guardrail2": g2,
        "mean_hard": statistics.mean(conds[c] for c in PREREGISTERED_HARD),
        "in_distribution": conds["in_distribution"],
    }
    if with_causal:
        res["causal"] = causal_necessity(model, fc, seed)
    if with_progressive:
        res["progressive"] = progressive_curve(model, fc, seed)
    return res


# ------------------------------- aggregation --------------------------------------------

def _agg(vals: List[float]) -> Dict:
    vals = [v for v in vals if v == v]
    return {"mean": statistics.mean(vals) if vals else float("nan"),
            "std": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
            "min": min(vals) if vals else float("nan"),
            "max": max(vals) if vals else float("nan"), "values": list(vals)}


HEALTH_KEYS = ["attn_entropy_norm", "head_diversity_js", "head_specialization_sel_std",
               "head_specialization_ent_std", "headmean_select_acc", "best_head_select_acc",
               "perturb_stability", "retrieval_stability", "mean_perturb_js"]


def summarize(per_arm_seed: Dict[str, Dict[int, Dict]]) -> Dict:
    summ = {}
    for arm, seeds in per_arm_seed.items():
        s = sorted(seeds.keys())
        summ[arm] = {
            "in_distribution": _agg([seeds[x]["in_distribution"] for x in s]),
            "mean_hard": _agg([seeds[x]["mean_hard"] for x in s]),
            "conditions": {c: _agg([seeds[x]["conditions"][c] for x in s])
                           for c in hard_condition_cfgs_names()},
        }
        for k in HEALTH_KEYS:
            summ[arm][k] = _agg([seeds[x]["health"].get(k, float("nan")) for x in s])
    return summ


def aggregate_progressive(per_arm_seed: Dict[str, Dict[int, Dict]]) -> Dict[str, List[Dict]]:
    out = {}
    for arm, seeds in per_arm_seed.items():
        s = sorted(seeds.keys())
        if "progressive" not in seeds[s[0]]:
            continue
        n_levels = len(seeds[s[0]]["progressive"])
        curve = []
        for li in range(n_levels):
            rows = [seeds[x]["progressive"][li] for x in s]
            curve.append({
                "level": rows[0]["level"], "label": rows[0]["label"],
                "perturb_stability": statistics.mean(r["perturb_stability"] for r in rows),
                "retrieval_stability": statistics.mean(r["retrieval_stability"] for r in rows),
                "mean_js": statistics.mean(r["mean_js"] for r in rows),
                "accuracy": statistics.mean(r["accuracy"] for r in rows),
            })
        out[arm] = curve
    return out


def aggregate_causal(per_arm_seed: Dict[str, Dict[int, Dict]]) -> Dict:
    out = {"chance": None}
    for arm, seeds in per_arm_seed.items():
        s = sorted(seeds.keys())
        if "causal" not in seeds[s[0]]:
            continue
        out[arm] = {
            "clean": statistics.mean(seeds[x]["causal"]["clean"] for x in s),
            "attn_zero_all": statistics.mean(seeds[x]["causal"]["attn_zero_all"] for x in s),
            "retained": statistics.mean(seeds[x]["causal"]["retained"] for x in s),
            "all_collapse": all(seeds[x]["causal"]["collapses_to_chance"] for x in s),
        }
        out["chance"] = seeds[s[0]]["causal"]["chance"]
    return out


def paired_stats(per_arm_seed: Dict[str, Dict[int, Dict]]) -> Dict:
    """Paired significance of each consistency arm vs BD-A on mean-hard + per condition."""
    seeds = sorted(per_arm_seed["BD-A"].keys())
    base = [per_arm_seed["BD-A"][x]["mean_hard"] for x in seeds]
    out = {}
    for arm in ["BD-Sync", "BD-Sync-Early", "BD-Shuffled", "BD-D"]:
        if arm not in per_arm_seed:
            continue
        meth = [per_arm_seed[arm][x]["mean_hard"] for x in seeds]
        cmp = qstats.paired_comparison(meth, base, label=f"{arm}_vs_BD-A")
        cmp["per_condition"] = {}
        for c in PREREGISTERED_HARD:
            mb = [per_arm_seed["BD-A"][x]["conditions"][c] for x in seeds]
            mm = [per_arm_seed[arm][x]["conditions"][c] for x in seeds]
            cmp["per_condition"][c] = qstats.paired_comparison(mm, mb, label=f"{arm}_{c}")
        out[arm] = cmp
    return out


def verdict(summ: Dict, comparisons: Dict, causal: Dict,
            per_arm_seed: Dict[str, Dict[int, Dict]]) -> Dict:
    """Final verdict against the pre-registered success criterion (benchmark = BD-A)."""
    seeds = sorted(per_arm_seed["BD-A"].keys())
    sync = comparisons["BD-Sync"]
    # Guardrail 1: BD-Sync retains Quad causal necessity (collapses to chance).
    g1 = causal.get("BD-Sync", {}).get("all_collapse", False)
    # Guardrail 2: BD-Sync attention healthy on every seed.
    g2 = all(per_arm_seed["BD-Sync"][x]["guardrail2"]["healthy"] for x in seeds)
    beats_A = sync["significant_improvement_over_baseline"]
    # Shuffled control: did the semantic pairing matter?
    shuf = comparisons.get("BD-Shuffled", {})
    semantic_specific = (sync["mean_delta"] > shuf.get("mean_delta", -1) + 0.0)  # informational
    if not (g1 and g2):
        v = "INVALID_GUARDRAIL_FAILURE"
    elif beats_A:
        v = "NULL_REJECTED_CONSISTENCY_HELPS"
    else:
        v = "NULL_NOT_REJECTED_NO_BENEFIT_OVER_BD-A"
    return {
        "verdict": v,
        "guardrail1_causal_ok": bool(g1),
        "guardrail2_health_ok": bool(g2),
        "bd_sync_beats_bd_a_significant": bool(beats_A),
        "bd_sync_mean_delta_vs_A": sync["mean_delta"],
        "bd_sync_wilcoxon_p_greater": sync["wilcoxon"]["p_greater"],
        "bd_sync_bootstrap_ci95": sync["bootstrap_ci95"],
        "shuffled_control_mean_delta_vs_A": shuf.get("mean_delta"),
        "sync_exceeds_shuffled_control": bool(semantic_specific),
        "null_hypothesis": ("Task-only learning already discovers the best retrieval "
                            "organization; any explicit consistency objective reduces or does "
                            "not improve generalization vs BD-A."),
    }
