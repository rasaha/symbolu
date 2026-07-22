#!/usr/bin/env python
"""Perturbation-consistency study driver (5 arms x 5 seeds). Imports qgr read-only.

Trains BD-A / BD-D / BD-Sync / BD-Sync-Early / Shuffled-Pair, evaluates the standard benchmarks
+ an OOD suite, records attention-organization diagnostics and the progressive-perturbation
degradation curve, checks both guardrails, runs the exact paired sign-permutation significance
test of BD-Sync vs BD-A, and assigns one decision category. Writes RESULTS_SYNC/.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import statistics
import sys
import time

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, os.pardir, "quad_generative_regularization"))

from qgr.mqar import MQARConfig
from qgr.experiment import FrozenConfig, eval_model_on_conditions, PREREGISTERED_HARD
from qgr.metrics import evaluate
from qgr import causal
from qpc.train_sync import SyncConfig, train_sync_arm, ARMS
from qpc import diagnostics
from qpc import sync_plots

OUT = os.path.join(HERE, "RESULTS_SYNC")
ALPHA = 4.0
LAM_SYNC = 0.5   # frozen in the pilot (seed-0: lam 0.5 -> gen 0.647 best & in-dist 0.997;
                 # lam 1.0 -> 0.617; smaller coefficient both most conservative and best-performing)

OOD_SUITE = {
    "ood_more_assoc": MQARConfig(num_kv=6, num_queries=2, vocab_size=32),
    "ood_heavy_distract": MQARConfig(num_kv=4, num_queries=2, num_distractors=12, vocab_size=32),
    "ood_long_distract": MQARConfig(num_kv=4, num_queries=2, num_distractors=24, vocab_size=32),
}


def bounded_fc():
    fc = FrozenConfig(); fc.bounded = True; fc.bound_alpha = ALPHA
    return fc


def gen_score(conds):
    return statistics.mean(conds[c] for c in PREREGISTERED_HARD)


def ood_score(ood):
    return statistics.mean(ood.values())


def analyze(arm, seed, cfg, full):
    r = train_sync_arm(arm, seed, cfg)
    model = r["model"]
    fc = bounded_fc()
    conds = eval_model_on_conditions(model, fc, seed)
    ood = {name: evaluate(model, mq, seed, "test", 10, cfg.batch_size)["acc"]
           for name, mq in OOD_SUITE.items()}
    hd = diagnostics.head_diagnostics(model, cfg.mqar(), seed)
    out = {"final_acc": r["final_val"]["acc"], "conditions": conds, "ood": ood,
           "gen_score": gen_score(conds), "ood_score": ood_score(ood),
           "diagnostics": hd, "history": r["history"],
           "mean_step_time": r["mean_step_time"]}
    if full:
        # Guardrail 1: causal necessity (zero all attention -> retained fraction)
        clean = causal.eval_conditions_ablated(model, fc, seed, lambda ab: None, n_batches=8)
        zeroed = causal.eval_conditions_ablated(
            model, fc, seed, lambda ab: ab.ablate_attn([0, 1], "zero"), n_batches=8)
        out["guardrail_causal"] = {
            "clean_indist": clean["in_distribution"], "zeroed_indist": zeroed["in_distribution"],
            "retained_frac": zeroed["in_distribution"] / max(clean["in_distribution"], 1e-9)}
        out["stability_curve"] = diagnostics.perturbation_stability_curve(model, cfg.mqar(), seed)
    return out


def sign_permutation_test(diffs):
    """Exact two-sided paired sign-permutation p-value for the mean of paired differences."""
    n = len(diffs)
    obs = abs(statistics.mean(diffs))
    count = 0
    for signs in itertools.product([1, -1], repeat=n):
        m = statistics.mean(s * d for s, d in zip(signs, diffs))
        if abs(m) >= obs - 1e-12:
            count += 1
    return count / (2 ** n)


def classify(agg, per_seed, seeds):
    bd_a = agg["BD-A"]; bd_sync = agg["BD-Sync"]
    # Guardrails on BD-Sync (seed 0 detail)
    gc = per_seed["BD-Sync"][seeds[0]].get("guardrail_causal", {})
    hd = bd_sync["diagnostics"]
    binding_causal = gc.get("retained_frac", 1.0) < 0.40
    healthy = (hd["entropy"]["mean"] > 0.05
               and not (hd["cross_head_diversity"]["mean"] < 0.005
                        and hd["head_specialization"]["mean"] < 0.02))
    if not binding_causal:
        return {"category": "SYNC_BREAKS_BINDING", "reason": gc}
    if not healthy:
        return {"category": "SYNC_COLLAPSES_ATTENTION", "reason": {
            "entropy": hd["entropy"]["mean"], "diversity": hd["cross_head_diversity"]["mean"],
            "specialization": hd["head_specialization"]["mean"]}}
    diffs = [per_seed["BD-Sync"][s]["gen_score"] - per_seed["BD-A"][s]["gen_score"] for s in seeds]
    p = sign_permutation_test(diffs)
    mean_diff = statistics.mean(diffs)
    wins = sum(1 for d in diffs if d > 0)
    if p < 0.05 and mean_diff > 0:
        cat = "SYNC_OUTPERFORMS_BD_A"
    elif p < 0.05 and mean_diff < 0:
        cat = "SYNC_BELOW_BD_A"
    else:
        cat = "SYNC_MATCHES_BD_A"
    return {"category": cat, "mean_gen_diff_vs_BD_A": mean_diff, "p_value": p,
            "per_seed_diffs": diffs, "wins_of_5": wins,
            "binding_causal": binding_causal, "attention_healthy": healthy}


def agg_stat(vals):
    vals = [v for v in vals if v == v]
    return {"mean": statistics.mean(vals) if vals else float("nan"),
            "std": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
            "min": min(vals) if vals else float("nan"), "values": list(vals)}


def aggregate(per_seed, seeds):
    agg = {}
    for arm in ARMS:
        d = {"final_acc": agg_stat([per_seed[arm][s]["final_acc"] for s in seeds]),
             "gen_score": agg_stat([per_seed[arm][s]["gen_score"] for s in seeds]),
             "ood_score": agg_stat([per_seed[arm][s]["ood_score"] for s in seeds]),
             "conditions": {}, "ood": {}, "diagnostics": {}}
        for c in ["in_distribution"] + PREREGISTERED_HARD:
            d["conditions"][c] = agg_stat([per_seed[arm][s]["conditions"][c] for s in seeds])
        for c in OOD_SUITE:
            d["ood"][c] = agg_stat([per_seed[arm][s]["ood"][c] for s in seeds])
        for k in per_seed[arm][seeds[0]]["diagnostics"]:
            d["diagnostics"][k] = agg_stat([per_seed[arm][s]["diagnostics"][k] for s in seeds])
        agg[arm] = d
    return agg


def to_jsonable(o):
    if isinstance(o, dict):
        return {k: to_jsonable(v) for k, v in o.items()}
    if isinstance(o, list):
        return [to_jsonable(v) for v in o]
    if isinstance(o, (int, float, str, bool)) or o is None:
        return o
    return str(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--seeds", type=int, nargs="*", default=[0, 1, 2, 3, 4])
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    cfg = SyncConfig(alpha=ALPHA, lam_sync=LAM_SYNC)
    seeds = args.seeds
    if args.quick:
        cfg.steps = 200; cfg.eval_every = 100; seeds = [0, 1]
    print(f"=== Perturbation-consistency study (alpha={ALPHA}, lam_sync={LAM_SYNC}, seeds={seeds}) ===")

    per_seed = {a: {} for a in ARMS}
    for arm in ARMS:
        for seed in seeds:
            ts = time.time()
            per_seed[arm][seed] = analyze(arm, seed, cfg, full=(seed == seeds[0]))
            d = per_seed[arm][seed]
            print(f"  {arm:14s} seed {seed}: acc={d['final_acc']:.3f} gen={d['gen_score']:.3f} "
                  f"ood={d['ood_score']:.3f} entropy={d['diagnostics']['entropy']:.2f} "
                  f"({time.time()-ts:.0f}s)")

    agg = aggregate(per_seed, seeds)
    decision = classify(agg, per_seed, seeds)

    print("\n=== GENERALIZATION (mean over seeds) ===")
    for arm in ARMS:
        a = agg[arm]
        print(f"  {arm:14s}: in-dist={a['conditions']['in_distribution']['mean']:.3f} "
              f"gen={a['gen_score']['mean']:.3f}±{a['gen_score']['std']:.3f} "
              f"ood={a['ood_score']['mean']:.3f} entropy={a['diagnostics']['entropy']['mean']:.2f} "
              f"xhead_div={a['diagnostics']['cross_head_diversity']['mean']:.3f}")
    print("\n=== HARD CONDITIONS (mean) ===")
    for c in PREREGISTERED_HARD:
        print(f"  {c:18s}: " + " ".join(f"{arm}={agg[arm]['conditions'][c]['mean']:.3f}"
                                        for arm in ARMS))
    print(f"\n=== DECISION: {decision['category']} ===")
    print(f"  {json.dumps({k: v for k, v in decision.items() if k != 'per_seed_diffs'}, default=str)}")

    sync_plots.make_all(agg, per_seed, seeds, PREREGISTERED_HARD, list(OOD_SUITE),
                        os.path.join(OUT, "plots"))

    result = {"alpha": ALPHA, "lam_sync": LAM_SYNC, "seeds": seeds,
              "decision": to_jsonable(decision), "aggregate": to_jsonable(agg),
              "per_seed": to_jsonable({a: {str(s): {k: v for k, v in per_seed[a][s].items()
                                                    if k != "history"}
                                           for s in seeds} for a in ARMS}),
              "wall_clock_s": time.time() - t0}
    with open(os.path.join(OUT, "sync_results.json"), "w") as f:
        json.dump(result, f, indent=2)
    _write_csv(per_seed, seeds, os.path.join(OUT, "sync_results.csv"))
    print(f"\nWrote RESULTS_SYNC/  ({result['wall_clock_s']:.0f}s)")
    return result


def _write_csv(per_seed, seeds, path):
    rows = []
    for arm in ARMS:
        for s in seeds:
            d = per_seed[arm][s]
            row = {"arm": arm, "seed": s, "final_acc": d["final_acc"],
                   "gen_score": d["gen_score"], "ood_score": d["ood_score"]}
            for c in ["in_distribution"] + PREREGISTERED_HARD:
                row[f"acc_{c}"] = d["conditions"][c]
            for k, v in d["diagnostics"].items():
                row[f"diag_{k}"] = v
            rows.append(row)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
