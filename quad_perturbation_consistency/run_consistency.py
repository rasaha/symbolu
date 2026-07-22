#!/usr/bin/env python
"""Confirmatory run: 5 arms x N seeds, full benchmark + guardrails + progressive + statistics.

Arms: BD-A (task-only baseline; the benchmark), BD-D (Quad auxiliary baseline), BD-Sync,
BD-Sync-Early, BD-Shuffled (generic-regularization control).  Uses the lambda frozen by the
pilot.  Writes RESULTS/consistency_results.json, consistency_results.csv, and plots/.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time

import torch

import qpc  # noqa: F401
from qpc.experiment import (
    ARMS, bounded_fc, train_labeled, evaluate_arm, summarize, aggregate_progressive,
    aggregate_causal, paired_stats, verdict,
)
from qpc.perturbations import AugConfig
from qgr.experiment import PREREGISTERED_HARD, hard_condition_cfgs_names
from qpc import plots

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "RESULTS")


def to_jsonable(o):
    if isinstance(o, dict):
        return {k: to_jsonable(v) for k, v in o.items()}
    if isinstance(o, list):
        return [to_jsonable(v) for v in o]
    if isinstance(o, (int, float, str, bool)) or o is None:
        return o
    return str(o)


def load_frozen_lambda(cli_lambda):
    if cli_lambda is not None:
        return cli_lambda
    p = os.path.join(OUT, "pilot.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)["frozen_lambda"]
    raise SystemExit("no frozen lambda: run run_pilot.py first or pass --lambda")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--seeds", type=int, nargs="*", default=[0, 1, 2, 3, 4, 5, 6, 7])
    ap.add_argument("--lambda", dest="lam", type=float, default=None)
    ap.add_argument("--quick", action="store_true", help="2 seeds, no progressive/causal (smoke)")
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    os.makedirs(OUT, exist_ok=True)
    seeds = [0, 1] if args.quick else args.seeds
    lam = load_frozen_lambda(args.lam)
    fc = bounded_fc()
    aug = AugConfig()
    with_extra = not args.quick
    t0 = time.time()
    print(f"=== CONFIRMATORY RUN (lambda={lam}, seeds={seeds}) ===")

    per_arm_seed = {a: {} for a in ARMS}
    for seed in seeds:
        for arm in ARMS:
            ts = time.time()
            model, tr = train_labeled(arm, fc, seed, lam, aug)
            ev = evaluate_arm(arm, model, fc, seed, aug,
                              with_progressive=with_extra, with_causal=with_extra)
            ev["final_train_acc"] = tr["final_val"]["acc"]
            ev["total_train_time"] = tr.get("total_train_time")
            per_arm_seed[arm][seed] = ev
            g2 = ev["guardrail2"]["healthy"]
            cz = ev.get("causal", {}).get("collapses_to_chance")
            print(f"  {arm:13s} seed {seed}: in={ev['in_distribution']:.3f} "
                  f"mean_hard={ev['mean_hard']:.3f} entropy={ev['health']['attn_entropy_norm']:.3f} "
                  f"stab={ev['health']['perturb_stability']:.3f} healthy={g2} "
                  f"causal_collapse={cz}  ({time.time()-ts:.0f}s)")

    summ = summarize(per_arm_seed)
    comparisons = paired_stats(per_arm_seed)
    causal = aggregate_causal(per_arm_seed)
    prog = aggregate_progressive(per_arm_seed)
    final = verdict(summ, comparisons, causal, per_arm_seed)

    # attach aggregated health/stability to summ for plotting (already in summ)
    print("\n=== GENERALIZATION (mean over seeds) ===")
    hdr = "  arm            in_dist  mean_hard  " + "  ".join(f"{c[:10]:>10s}" for c in PREREGISTERED_HARD)
    print(hdr)
    for a in ARMS:
        s = summ[a]
        print(f"  {a:13s}  {s['in_distribution']['mean']:.3f}    {s['mean_hard']['mean']:.3f}    "
              + "  ".join(f"{s['conditions'][c]['mean']:10.3f}" for c in PREREGISTERED_HARD))

    print("\n=== PAIRED SIGNIFICANCE vs BD-A (mean-hard) ===")
    for a in ["BD-Sync", "BD-Sync-Early", "BD-Shuffled", "BD-D"]:
        c = comparisons[a]
        wp = c["wilcoxon"]["p_greater"]
        print(f"  {a:13s}: delta={c['mean_delta']:+.3f} (median {c['median_delta']:+.3f}) "
              f"n+={c['n_positive']}/{c['n_seeds']} wilcoxon_p_greater="
              f"{'na' if wp is None else f'{wp:.4f}'} "
              f"ci95=[{c['bootstrap_ci95']['lo']:+.3f},{c['bootstrap_ci95']['hi']:+.3f}] "
              f"sig={c['significant_improvement_over_baseline']}")

    if causal.get("chance") is not None:
        print("\n=== GUARDRAIL 1 (Quad causal necessity) — attn zeroed -> chance ===")
        for a in ARMS:
            if a in causal:
                print(f"  {a:13s}: clean={causal[a]['clean']:.3f} "
                      f"zeroed={causal[a]['attn_zero_all']:.3f} "
                      f"retained={causal[a]['retained']:.3f} collapse={causal[a]['all_collapse']}")
        print(f"  chance level ~ {causal['chance']:.3f}")

    print(f"\n=== VERDICT: {final['verdict']} ===")
    print(f"  guardrails: causal={final['guardrail1_causal_ok']} health={final['guardrail2_health_ok']}")
    print(f"  BD-Sync significant over BD-A: {final['bd_sync_beats_bd_a_significant']} "
          f"(delta={final['bd_sync_mean_delta_vs_A']:+.3f}, "
          f"wilcoxon_p={final['bd_sync_wilcoxon_p_greater']})")

    if with_extra:
        plots.make_all(summ, comparisons, prog, causal, os.path.join(OUT, "plots"))

    result = {
        "lambda": lam, "seeds": seeds, "arms": ARMS,
        "summary": to_jsonable(summ), "comparisons": to_jsonable(comparisons),
        "causal_guardrail1": to_jsonable(causal), "progressive": to_jsonable(prog),
        "verdict": to_jsonable(final),
        "per_arm_seed": to_jsonable({a: {str(s): {k: v for k, v in per_arm_seed[a][s].items()
                                                  if k != "progressive"}
                                         for s in per_arm_seed[a]} for a in ARMS}),
        "progressive_per_seed": to_jsonable({a: {str(s): per_arm_seed[a][s].get("progressive")
                                                 for s in per_arm_seed[a]} for a in ARMS}),
        "wall_clock_s": time.time() - t0,
    }
    with open(os.path.join(OUT, "consistency_results.json"), "w") as f:
        json.dump(result, f, indent=2)
    _write_csv(per_arm_seed, os.path.join(OUT, "consistency_results.csv"))
    print(f"\nWrote RESULTS/  ({result['wall_clock_s']:.0f}s)")
    return result


def _write_csv(per_arm_seed, path):
    rows = []
    for arm in ARMS:
        for s in sorted(per_arm_seed[arm].keys()):
            d = per_arm_seed[arm][s]
            row = {"arm": arm, "seed": s, "in_distribution": d["in_distribution"],
                   "mean_hard": d["mean_hard"]}
            for c in hard_condition_cfgs_names():
                row[f"acc_{c}"] = d["conditions"][c]
            for k in ("attn_entropy_norm", "head_diversity_js", "head_specialization_sel_std",
                      "perturb_stability", "retrieval_stability", "headmean_select_acc"):
                row[k] = d["health"].get(k)
            row["healthy"] = d["guardrail2"]["healthy"]
            if "causal" in d:
                row["causal_retained"] = d["causal"]["retained"]
                row["causal_collapse"] = d["causal"]["collapses_to_chance"]
            rows.append(row)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
