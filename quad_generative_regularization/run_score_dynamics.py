#!/usr/bin/env python
"""Quad score dynamics analysis (analysis-only; training/inference unchanged).

Instruments Arms A, C, D over the frozen protocol (3 seeds) with read-only snapshots of the
Quad score distribution, gradient norms, representation geometry, and an offline temperature
counterfactual. Writes RESULTS_DYNAMICS/. No losses/regularizers/temperature-scaling are added
to training; the analysis hook is verified bit-identical to an un-instrumented run
(tests/test_analysis.py).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import time

import torch

from qgr.experiment import FrozenConfig
from qgr.mqar import generate_batch, split_seed
from qgr.train import TrainConfig, train_arm
from qgr import analysis
from qgr import dynamics_plots

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "RESULTS_DYNAMICS")
SNAP_EVERY = 250


def run_arm(fc: FrozenConfig, arm: str, seed: int):
    """Train one arm with trajectory instrumentation; return (trajectory, final_snapshot)."""
    analysis_batch = generate_batch(fc.base_mqar(), split_seed(seed, "val", 777),
                                    fc.batch_size)
    traj = []

    def hook(step, model, relation_head, aux_active):
        model.eval()
        snap = analysis.full_snapshot(model, analysis_batch)
        snap["step"] = step
        snap["aux_active"] = aux_active
        traj.append(snap)
        model.train()

    tc = fc.train_cfg(arm, seed)
    r = train_arm(fc.model_cfg(), fc.base_mqar(), tc, analysis_hook=hook,
                  analysis_every=SNAP_EVERY)
    return traj, r["final_val"]["acc"]


def agg(vals):
    vals = [v for v in vals if v == v]
    if not vals:
        return {"mean": float("nan"), "std": 0.0}
    return {"mean": statistics.mean(vals),
            "std": statistics.pstdev(vals) if len(vals) > 1 else 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()

    fc = FrozenConfig()
    seeds = args.seeds if args.seeds is not None else fc.screen_seeds
    arms = ["A", "C", "D"]
    print(f"=== Quad score dynamics analysis (seeds={seeds}) ===")

    trajectories = {a: {} for a in arms}   # arm -> seed -> trajectory list
    final_acc = {a: {} for a in arms}
    for arm in arms:
        for seed in seeds:
            ts = time.time()
            traj, acc = run_arm(fc, arm, seed)
            trajectories[arm][seed] = traj
            final_acc[arm][seed] = acc
            last = traj[-1]
            print(f"  {arm} seed {seed}: acc={acc:.3f} margin={last['dyn_margin_mean']:.1f} "
                  f"entropy={last['dyn_entropy_mean']:.3f} "
                  f"|dL/dS|={last['grad_grad_wrt_score']:.4f}  ({time.time()-ts:.0f}s)")

    # ---- final-state aggregation across seeds ----
    final = {}
    metrics = ["dyn_margin_mean", "dyn_entropy_mean", "dyn_pos_score_mean",
               "dyn_neg_score_mean", "dyn_top1_prob_mean", "dyn_logit_variance_mean",
               "grad_grad_wrt_score", "grad_grad_wrt_hidden", "grad_grad_wrt_Wq",
               "grad_grad_wrt_Wk", "geom_hidden_cos_gap", "geom_proj_qk_cos_gap",
               "geom_hidden_cos_pos", "geom_hidden_cos_neg", "geom_proj_qk_cos_pos",
               "geom_proj_qk_cos_neg"]
    for arm in arms:
        final[arm] = {"final_acc": agg([final_acc[arm][s] for s in seeds])}
        for m in metrics:
            final[arm][m] = agg([trajectories[arm][s][-1][m] for s in seeds])
        # temperature counterfactual (final, mean over seeds)
        temps = list(trajectories[arm][seeds[0]][-1]["temp"]["by_temp"].keys())
        final[arm]["temp"] = {"max_entropy_uniform":
                              agg([trajectories[arm][s][-1]["temp"]["max_entropy_uniform"]
                                   for s in seeds])["mean"], "by_temp": {}}
        for T in temps:
            final[arm]["temp"]["by_temp"][T] = {
                "entropy_mean": agg([trajectories[arm][s][-1]["temp"]["by_temp"][T]["entropy_mean"]
                                     for s in seeds])["mean"],
                "entropy_frac_of_uniform": agg([trajectories[arm][s][-1]["temp"]["by_temp"][T]["entropy_frac_of_uniform"]
                                                for s in seeds])["mean"],
                "ranking_preserved": all(trajectories[arm][s][-1]["temp"]["by_temp"][T]["ranking_preserved"]
                                         for s in seeds),
            }

    print("\n=== FINAL-STATE SUMMARY (mean over seeds) ===")
    for arm in arms:
        f = final[arm]
        print(f"  {arm}: acc={f['final_acc']['mean']:.3f} margin={f['dyn_margin_mean']['mean']:.1f} "
              f"entropy={f['dyn_entropy_mean']['mean']:.3f} |dL/dS|={f['grad_grad_wrt_score']['mean']:.4f} "
              f"hidden_gap={f['geom_hidden_cos_gap']['mean']:.3f} proj_gap={f['geom_proj_qk_cos_gap']['mean']:.3f}")
    print("\n=== TEMPERATURE COUNTERFACTUAL (final, entropy as frac of uniform) ===")
    for arm in arms:
        row = " ".join(f"T{T}={final[arm]['temp']['by_temp'][T]['entropy_frac_of_uniform']:.2f}"
                       for T in final[arm]["temp"]["by_temp"])
        print(f"  {arm}: {row}")

    # ---- plots (seed 0 trajectories + aggregated finals) ----
    dynamics_plots.make_all(trajectories, final, seeds[0], os.path.join(OUT, "plots"))

    # ---- persist ----
    result = {
        "frozen_config": {k: (v if isinstance(v, (int, float, str, bool, list)) else str(v))
                          for k, v in fc.__dict__.items()},
        "snap_every": SNAP_EVERY, "seeds": seeds,
        "final": final,
        "trajectory_seed0": {a: trajectories[a][seeds[0]] for a in arms},
        "wall_clock_s": time.time() - t0,
    }
    with open(os.path.join(OUT, "dynamics_results.json"), "w") as f:
        json.dump(result, f, indent=2)
    _write_csv(trajectories, seeds, arms, os.path.join(OUT, "dynamics_trajectory.csv"))
    print(f"\nWrote RESULTS_DYNAMICS/  ({result['wall_clock_s']:.0f}s)")
    return result


def _write_csv(trajectories, seeds, arms, path):
    rows = []
    for arm in arms:
        for s in seeds:
            for snap in trajectories[arm][s]:
                rows.append({
                    "arm": arm, "seed": s, "step": snap["step"],
                    "aux_active": snap["aux_active"],
                    "margin": snap["dyn_margin_mean"], "entropy": snap["dyn_entropy_mean"],
                    "pos_score": snap["dyn_pos_score_mean"], "neg_score": snap["dyn_neg_score_mean"],
                    "logit_var": snap["dyn_logit_variance_mean"],
                    "grad_score": snap["grad_grad_wrt_score"],
                    "grad_hidden": snap["grad_grad_wrt_hidden"],
                    "grad_Wq": snap["grad_grad_wrt_Wq"], "grad_Wk": snap["grad_grad_wrt_Wk"],
                    "hidden_cos_gap": snap["geom_hidden_cos_gap"],
                    "proj_qk_cos_gap": snap["geom_proj_qk_cos_gap"],
                    "task_loss": snap["grad_task_loss"],
                })
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
