#!/usr/bin/env python
"""Main driver: build the per-query dataset, evaluate USE vs baselines, ablate, save RESULTS/.

Trains and freezes the bounded task-only Quad model (BD-A) per seed via the unmodified prior
package, observes completed inferences read-only, computes USE (U1-U5) signals and confidence
baselines, and tests whether USE adds predictive value for failure detection beyond confidence.
"""

from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np
import torch

import use  # noqa: F401
from use.dataset import build_all
from use.experiment import run_all, _pool
from use import ablation as abl_mod
from use import failure_analysis, plots

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "RESULTS")


def to_jsonable(o):
    if isinstance(o, dict):
        return {str(k): to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_jsonable(v) for v in o]
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    if isinstance(o, (int, float, str, bool)) or o is None:
        return o
    return str(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--seeds", type=int, nargs="*", default=[0, 1, 2])
    ap.add_argument("--n-batches", type=int, default=40)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    os.makedirs(OUT, exist_ok=True)
    seeds = args.seeds[:1] if args.quick else args.seeds
    nb = 8 if args.quick else args.n_batches
    t0 = time.time()
    print(f"=== USE study: seeds={seeds} n_batches={nb} ===")

    bundle = build_all(seeds, n_batches=nb)
    print(f"[data built in {time.time()-t0:.0f}s]")

    results = run_all(bundle)

    # ablation + failure analysis on the pooled-usable dataset
    usable = results["pooled_conditions_used"]
    data = bundle["data"]; keys = data[seeds[0]][usable[0]].keys()
    all_pool = {k: np.concatenate([data[s][c][k] for s in seeds for c in usable]) for k in keys}
    y = all_pool["label_failure"].astype(int)
    ablation = abl_mod.full_ablation(all_pool, y)
    fail = failure_analysis.analyze(all_pool)

    # ---- console summary ----
    print("\n=== FAILURE-DETECTION AUROC BY CONDITION (pooled over seeds) ===")
    print("  condition           n   fail%   token_prob  base_combo  use_best  use_all  combined")
    for c, r in results["per_condition"].items():
        if "predictors" not in r:
            print(f"  {c:18s} n={r['n']:5d} fail%={r['failure_rate']:.2f}  [skipped: {r.get('skipped','')}]")
            continue
        p = r["predictors"]
        print(f"  {c:18s} n={r['n']:5d} fail%={r['failure_rate']:.2f}  "
              f"{p['token_prob_only']['auroc']:.3f}      {p['baseline_combo']['auroc']:.3f}      "
              f"{p['use_best']['auroc']:.3f}    {p['use_all']['auroc']:.3f}   {p['combined_base_use']['auroc']:.3f}")

    po = results["pooled_all"]
    if "tests" in po:
        print("\n=== POOLED OMNIBUS (all usable conditions) ===")
        p = po["predictors"]
        for name in ["token_prob_only", "baseline_combo", "use_best", "use_all", "combined_base_use", "random"]:
            d = p[name]
            print(f"  {name:20s} AUROC={d['auroc']:.3f} CI=[{d['auroc_ci'][0]:.3f},{d['auroc_ci'][1]:.3f}] "
                  f"AUPRC={d['auprc']:.3f}")
        t = po["tests"]
        print(f"  best USE config: {po['use_best_config']}")
        print(f"  DeLong use_best vs baseline_combo: dAUC={t['use_best_vs_baseline_combo']['auc1']-t['use_best_vs_baseline_combo']['auc2']:+.3f} p1={t['use_best_vs_baseline_combo']['p_one_sided_1_gt_2']:.4f}")
        print(f"  DeLong combined(all USE) vs baseline: dAUC={t['combined_vs_baseline_combo']['auc1']-t['combined_vs_baseline_combo']['auc2']:+.3f} p1={t['combined_vs_baseline_combo']['p_one_sided_1_gt_2']:.4f}")
        print(f"  DeLong combined(best USE, parsimonious) vs baseline: dAUC={t['combined_best_vs_baseline']['auc1']-t['combined_best_vs_baseline']['auc2']:+.3f} p1={t['combined_best_vs_baseline']['p_one_sided_1_gt_2']:.4f}")

    print("\n=== ABLATION: channel-set combined AUROC (pooled) ===")
    for cs, v in sorted(ablation["channel_set"].items(), key=lambda kv: -kv[1]):
        print(f"  {cs:16s} {v:.3f}")
    print("=== ABLATION: phase-mapping combined AUROC ===")
    for mp, v in ablation["mapping"].items():
        print(f"  {mp:22s} {v:.3f}")

    print(f"\n=== VERDICT: {results['verdict']['verdict']} ===")
    v = results["verdict"]
    print(f"  reject_null={v['reject_null']} n_incr={v['n_conditions_incremental']}/{v['n_conditions_usable']} "
          f"pooled_incr={v['pooled_incremental_significant']} reproducible={v['reproducible_across_seeds']}")

    plots.make_all(results, ablation, os.path.join(OUT, "plots"))

    payload = {"config": {k: bundle[k] for k in ("seeds", "conditions", "W", "alpha",
                                                 "n_batches", "batch_size")},
               "model_acc": bundle["model_acc"], "results": results,
               "ablation": ablation, "failure_analysis": fail,
               "wall_clock_s": time.time() - t0}
    with open(os.path.join(OUT, "use_results.json"), "w") as f:
        json.dump(to_jsonable(payload), f, indent=2)
    print(f"\nWrote RESULTS/use_results.json + plots  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
