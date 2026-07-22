#!/usr/bin/env python
"""Causal localization of associative binding (read-only).

Reproduces the frozen trained checkpoints DETERMINISTICALLY (same config+seed -> bit-identical
params, verified by tests/test_equivalence.py + test_bounded), then runs, as read-only
inference analyses: pathway ablation (Phase 1-2), linear probes (Phase 3), integrated gradients
(Phase 4), activation patching / mediation (Phase 5), and RSA. No retraining, no optimizer /
architecture / loss changes; the only optimization is small EXTERNAL linear probes.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import time

import torch

from qgr.experiment import FrozenConfig, hard_condition_cfgs, PREREGISTERED_HARD
from qgr.train import TrainConfig, train_arm
from qgr import causal, causal_plots

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "RESULTS_CAUSAL")

# label -> (bounded, base_arm, aux_cutoff_frac)
ARMS = {
    "C": (False, "C", 1.0),
    "D-full": (False, "D", 1.0),
    "BD-A": (True, "A", 1.0),
    "BD-D": (True, "D", 1.0),
    "BD-D10": (True, "D", 0.10),
}
CONDS = ["in_distribution"] + PREREGISTERED_HARD


def build_arm(label, seed):
    bounded, base_arm, frac = ARMS[label]
    fc = FrozenConfig()
    if bounded:
        fc.bounded = True
        fc.bound_alpha = 4.0
    tc = fc.train_cfg(base_arm, seed)
    tc.aux_cutoff_frac = frac
    r = train_arm(fc.model_cfg(), fc.base_mqar(), tc)
    return r["model"], fc, r["final_val"]["acc"]


def ablation_suite(aux):
    return {
        "clean": (lambda ab: None),
        "attn_zero_aux": (lambda ab: ab.ablate_attn([aux], "zero")),
        "attn_mean_aux": (lambda ab: ab.ablate_attn([aux], "mean")),
        "attn_shuffle_aux": (lambda ab: ab.ablate_attn([aux], "shuffle")),
        "attn_zero_L0": (lambda ab: ab.ablate_attn([0], "zero")),
        "attn_zero_all": (lambda ab: ab.ablate_attn([0, 1], "zero")),
        "ff_zero_aux": (lambda ab: ab.ablate_ff([aux], "zero")),
        "ff_zero_all": (lambda ab: ab.ablate_ff([0, 1], "zero")),
    }


def analyze_arm(label, seed, full=False):
    model, fc, acc = build_arm(label, seed)
    aux = model._aux_layer
    mq = fc.base_mqar()
    res = {"final_acc": acc, "ablation": {}}
    for name, fn in ablation_suite(aux).items():
        res["ablation"][name] = causal.eval_conditions_ablated(model, fc, seed, fn, n_batches=8)
    if full:
        res["probe"] = {feat: causal.linear_probe(model, mq, seed, fc.vocab_size, feat,
                                                   n_train=20, n_test=8, steps=300)
                        for feat in ("hidden", "proj_q", "proj_k")}
        res["patching"] = causal.activation_patching(model, mq, seed, layer=aux, n_batches=6)
        res["ig"] = causal.integrated_gradients_pathways(model, mq, seed, layer=aux,
                                                         steps=16, batch_size=16)
        res["rsa"] = causal.rsa_quad_vs_hidden(model, mq, seed)
    return res


def collapses(clean, ablated, thr=0.5):
    """A pathway ablation 'collapses' a condition if accuracy falls by >= thr*clean toward
    chance. Reported as the relative retained fraction."""
    return ablated / max(clean, 1e-9)


def classify(per_arm_seed0):
    """Outcome category from the aux-layer attention ablation (Quad retrieval)."""
    def retained(label):
        c = per_arm_seed0[label]["ablation"]["clean"]["in_distribution"]
        z = per_arm_seed0[label]["ablation"]["attn_zero_all"]["in_distribution"]
        return z / max(c, 1e-9)
    r = {l: retained(l) for l in ARMS}
    # "depends on Quad" if zeroing attention retains < 40% of clean accuracy
    depends = {l: r[l] < 0.40 for l in ARMS}
    if all(depends.values()):
        cat = "QUAD_IS_CAUSAL"
    elif not any(depends.values()):
        cat = "QUAD_IS_REFLECTIVE"
    elif depends["BD-D"] and depends["D-full"] and not depends["BD-A"]:
        cat = "MIXED_DEPENDENCY"
    else:
        cat = "MIXED_DEPENDENCY"
    return {"category": cat, "retained_frac_attn_zero_all": r, "depends_on_quad": depends}


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
    ap.add_argument("--seeds", type=int, nargs="*", default=[0, 1, 2])
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    print(f"=== Causal localization of associative binding (seeds={args.seeds}) ===")

    data = {l: {} for l in ARMS}
    for seed in args.seeds:
        for label in ARMS:
            ts = time.time()
            data[label][seed] = analyze_arm(label, seed, full=(seed == args.seeds[0]))
            abl = data[label][seed]["ablation"]
            print(f"  {label} seed {seed}: clean={abl['clean']['in_distribution']:.3f} "
                  f"attn_zero_all={abl['attn_zero_all']['in_distribution']:.3f} "
                  f"ff_zero_all={abl['ff_zero_all']['in_distribution']:.3f}  ({time.time()-ts:.0f}s)")

    seed0 = args.seeds[0]
    per_arm_seed0 = {l: data[l][seed0] for l in ARMS}
    outcome = classify(per_arm_seed0)

    # aggregate ablation over seeds (mean retained fraction per condition)
    agg = {}
    for label in ARMS:
        agg[label] = {}
        for abname in ablation_suite(0):
            agg[label][abname] = {}
            for cond in CONDS:
                clean = statistics.mean(data[label][s]["ablation"]["clean"][cond] for s in args.seeds)
                val = statistics.mean(data[label][s]["ablation"][abname][cond] for s in args.seeds)
                agg[label][abname][cond] = {"acc": val, "retained": collapses(clean, val)}

    print("\n=== Quad-retrieval (attention) ablation — in-distribution accuracy (mean seeds) ===")
    for label in ARMS:
        a = agg[label]
        print(f"  {label:7s}: clean={a['clean']['in_distribution']['acc']:.3f} "
              f"zero_aux={a['attn_zero_aux']['in_distribution']['acc']:.3f} "
              f"zero_all={a['attn_zero_all']['in_distribution']['acc']:.3f} "
              f"shuffle={a['attn_shuffle_aux']['in_distribution']['acc']:.3f} "
              f"ff_zero_all={a['ff_zero_all']['in_distribution']['acc']:.3f}")
    print("\n=== Probes / patching / IG / RSA (seed %d) ===" % seed0)
    for label in ARMS:
        d = per_arm_seed0[label]
        pr = d.get("probe", {}); pt = d.get("patching", {}); ig = d.get("ig", {}); rs = d.get("rsa", {})
        print(f"  {label:7s}: probe(hidden)={pr.get('hidden',float('nan')):.3f} "
              f"probe(proj_q)={pr.get('proj_q',float('nan')):.3f} "
              f"patch_recovery={pt.get('recovery',float('nan')):.3f} "
              f"IG_attn_frac={ig.get('attn_frac',float('nan')):.3f} "
              f"RSA(hid~quad)={rs.get('rdm_correlation_hidden_vs_quad',float('nan')):.3f}")
    print(f"\n=== OUTCOME: {outcome['category']} ===")
    print(f"  retained accuracy under attn_zero_all: "
          + ", ".join(f"{l}={outcome['retained_frac_attn_zero_all'][l]:.2f}" for l in ARMS))

    causal_plots.make_all(agg, per_arm_seed0, CONDS, os.path.join(OUT, "plots"))

    result = {"seeds": args.seeds, "outcome": to_jsonable(outcome),
              "aggregate_ablation": to_jsonable(agg),
              "seed0_detail": to_jsonable(per_arm_seed0),
              "wall_clock_s": time.time() - t0}
    with open(os.path.join(OUT, "causal_results.json"), "w") as f:
        json.dump(result, f, indent=2)
    _write_csv(agg, os.path.join(OUT, "causal_ablation.csv"))
    print(f"\nWrote RESULTS_CAUSAL/  ({result['wall_clock_s']:.0f}s)")
    return result


def _write_csv(agg, path):
    rows = []
    for label in ARMS:
        for abname in agg[label]:
            row = {"arm": label, "ablation": abname}
            for cond in CONDS:
                row[f"acc_{cond}"] = agg[label][abname][cond]["acc"]
                row[f"retained_{cond}"] = agg[label][abname][cond]["retained"]
            rows.append(row)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
