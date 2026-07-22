#!/usr/bin/env python
"""Pilot: fairly select and FREEZE the single consistency coefficient lambda BEFORE the
confirmatory run.  We give the method its best honest shot — pick the lambda with the highest
mean-hard generalization (subject to a health check) — then test whether even at its best it
beats BD-A.  Writes PILOT_RECORD.md and RESULTS/pilot.json.  Pilot uses 2 seeds; the frozen
lambda is then used unchanged in the multi-seed confirmatory run (run_consistency.py).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time

import torch

import qpc  # noqa: F401
from qgr.experiment import PREREGISTERED_HARD, eval_model_on_conditions
from qgr.train import train_arm
from qpc.experiment import bounded_fc, train_labeled
from qpc.health import attention_health, guardrail2_health
from qpc.perturbations import AugConfig

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "RESULTS")
# Pilot seeds are DISJOINT from the confirmatory seeds (0..N) to avoid selection bias:
# lambda is chosen on held-out seeds, then frozen and tested on the confirmatory seeds.
LAMBDAS = [0.03, 0.1, 0.3]
PILOT_SEEDS = [100, 101]


def mean_hard(conds):
    return statistics.mean(conds[c] for c in PREREGISTERED_HARD)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--seeds", type=int, nargs="*", default=PILOT_SEEDS)
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    os.makedirs(OUT, exist_ok=True)
    fc = bounded_fc()
    aug = AugConfig()
    t0 = time.time()
    print(f"=== PILOT: freeze lambda (grid {LAMBDAS}, seeds {args.seeds}) ===")

    # BD-A reference (mean-hard per seed)
    a_hard = {}
    for s in args.seeds:
        m, _ = train_labeled("BD-A", fc, s, 0.0, aug)
        a_hard[s] = mean_hard(eval_model_on_conditions(m, fc, s))
        print(f"  BD-A seed {s}: mean_hard={a_hard[s]:.3f}")

    grid = {}
    for lam in LAMBDAS:
        per_seed = {}
        for s in args.seeds:
            ts = time.time()
            m, _ = train_labeled("BD-Sync", fc, s, lam, aug)
            conds = eval_model_on_conditions(m, fc, s)
            h = attention_health(m, fc.base_mqar(), s, n_batches=4)
            g2 = guardrail2_health(h)
            per_seed[s] = {"mean_hard": mean_hard(conds), "in_dist": conds["in_distribution"],
                           "entropy": h["attn_entropy_norm"], "healthy": g2["healthy"],
                           "delta_vs_A": mean_hard(conds) - a_hard[s]}
            print(f"  lambda={lam} seed {s}: mean_hard={per_seed[s]['mean_hard']:.3f} "
                  f"(delta {per_seed[s]['delta_vs_A']:+.3f}) entropy={h['attn_entropy_norm']:.3f} "
                  f"healthy={g2['healthy']}  ({time.time()-ts:.0f}s)")
        grid[lam] = {
            "per_seed": per_seed,
            "mean_hard": statistics.mean(per_seed[s]["mean_hard"] for s in args.seeds),
            "mean_delta_vs_A": statistics.mean(per_seed[s]["delta_vs_A"] for s in args.seeds),
            "min_in_dist": min(per_seed[s]["in_dist"] for s in args.seeds),
            "all_healthy": all(per_seed[s]["healthy"] for s in args.seeds),
        }

    # choose: highest mean-hard among healthy lambdas that also learn the task (in-dist>=0.95).
    eligible = {lam: g for lam, g in grid.items()
                if g["all_healthy"] and g["min_in_dist"] >= 0.95}
    pool = eligible if eligible else grid
    frozen = max(pool, key=lambda l: pool[l]["mean_hard"])
    print(f"\n=== FROZEN lambda = {frozen} "
          f"(mean_hard={grid[frozen]['mean_hard']:.3f}, "
          f"delta_vs_A={grid[frozen]['mean_delta_vs_A']:+.3f}) ===")

    result = {"lambdas": LAMBDAS, "pilot_seeds": args.seeds, "bd_a_mean_hard": a_hard,
              "grid": grid, "frozen_lambda": frozen,
              "selection_rule": ("highest mean-hard among lambdas that are health-guardrail "
                                 "clean and reach >=0.95 in-distribution on both pilot seeds; "
                                 "chosen to give the method its most favorable fair configuration"),
              "wall_clock_s": time.time() - t0}
    with open(os.path.join(OUT, "pilot.json"), "w") as f:
        json.dump(result, f, indent=2)
    _write_record(result)
    print(f"Wrote RESULTS/pilot.json + PILOT_RECORD.md  ({result['wall_clock_s']:.0f}s)")
    return result


def _write_record(r):
    lines = ["# Pilot Record — Frozen Consistency Coefficient", "",
             f"Frozen **lambda = {r['frozen_lambda']}**.  Selection rule: {r['selection_rule']}.",
             "", "| lambda | mean-hard | delta vs BD-A | min in-dist | all healthy |",
             "|---:|---:|---:|---:|:--:|"]
    for lam in r["lambdas"]:
        g = r["grid"][lam]
        lines.append(f"| {lam} | {g['mean_hard']:.3f} | {g['mean_delta_vs_A']:+.3f} | "
                     f"{g['min_in_dist']:.3f} | {'yes' if g['all_healthy'] else 'no'} |")
    lines += ["", f"BD-A pilot mean-hard: " +
              ", ".join(f"seed {s}={v:.3f}" for s, v in r['bd_a_mean_hard'].items()),
              "", "The frozen lambda is used unchanged in the confirmatory multi-seed run.",
              "Even at the most favorable lambda the confirmatory test asks whether BD-Sync "
              "significantly beats BD-A; failing that, the null stands."]
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "PILOT_RECORD.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
