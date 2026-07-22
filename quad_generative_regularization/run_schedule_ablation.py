#!/usr/bin/env python
"""Early-only auxiliary schedule ablation.

Hypothesis: Quad-native supervision is useful for establishing associative binding EARLY,
but continuing the auxiliary pressure after binding is learned over-sharpens the Quad score
and harms generalization.

Reuses existing Arm A / Arm C / Arm D-full results from RESULTS/results.json (frozen; not
re-run). Adds Arm D-10 / D-25 / D-50 (auxiliary active for the first 10/25/50% of steps, then
hard-zeroed) on the same three seeds, same frozen config. Writes RESULTS_SCHEDULE/.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import time

import torch

from qgr.experiment import (
    FrozenConfig, eval_model_on_conditions, eval_seqlen_curve, steps_to_threshold,
    hard_condition_cfgs_names, PREREGISTERED_HARD,
)
from qgr.metrics import quad_mechanism
from qgr.train import TrainConfig, train_arm
from qgr import plotting

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "RESULTS")
OUT = os.path.join(HERE, "RESULTS_SCHEDULE")

SCHEDULE_ARMS = {"D-10": 0.10, "D-25": 0.25, "D-50": 0.50}


def train_scheduled_D(fc: FrozenConfig, seed: int, frac: float) -> dict:
    """Train an early-only Arm D (Quad aux for first `frac` of steps) and summarize."""
    tc = fc.train_cfg("D", seed)
    tc.aux_cutoff_frac = frac
    r = train_arm(fc.model_cfg(), fc.base_mqar(), tc)
    model = r["model"]
    return {
        "seed": seed,
        "aux_cutoff_frac": frac,
        "cutoff_step": r["cutoff_step"],
        "final_acc": r["final_val"]["acc"],
        "final_seq_acc": r["final_val"]["seq_acc"],
        "final_task_loss": r["final_val"]["task_loss"],
        "steps_to_threshold": steps_to_threshold(r["history"], fc.acc_threshold),
        "conditions": eval_model_on_conditions(model, fc, seed),
        "seqlen_curve": eval_seqlen_curve(model, fc, seed),
        "mechanism": quad_mechanism(model, fc.base_mqar(), seed, "test", 6, fc.batch_size),
        "history": r["history"],
        "grad_history": r["grad_history"],
        "mean_step_time": r["mean_step_time"],
        "total_train_time": r["total_train_time"],
        "num_params": r["num_params"],
    }


def load_existing(fc: FrozenConfig) -> dict:
    """Load reused Arm A / C / D-full per-seed results from the completed screen."""
    with open(os.path.join(RESULTS, "results.json")) as f:
        d = json.load(f)
    ps = d["per_seed"]
    out = {"A": {}, "C": {}, "D-full": {}}
    for s in ps:
        seed = int(s)
        out["A"][seed] = ps[s]["A"]
        out["C"][seed] = ps[s]["C"]
        out["D-full"][seed] = ps[s]["D"]
        out["D-full"][seed]["cutoff_step"] = fc.steps  # aux active throughout
    return out


def agg_stat(vals):
    return {"mean": statistics.mean(vals),
            "std": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
            "values": list(vals)}


def summarize_arm(per_seed_arm: dict) -> dict:
    seeds = sorted(per_seed_arm.keys())
    accs = [per_seed_arm[s]["final_acc"] for s in seeds]
    ent = [per_seed_arm[s]["mechanism"].get("cand_entropy", float("nan")) for s in seeds]
    sel = [per_seed_arm[s]["mechanism"].get("internal_select_acc", float("nan")) for s in seeds]
    margin = [per_seed_arm[s]["mechanism"].get("pos_neg_margin", float("nan")) for s in seeds]
    conds = {c: agg_stat([per_seed_arm[s]["conditions"][c] for s in seeds])
             for c in hard_condition_cfgs_names()}
    return {
        "final_acc": agg_stat(accs),
        "min_seed_acc": min(accs),
        "cand_entropy": agg_stat([e for e in ent if e == e]) if any(e == e for e in ent) else None,
        "internal_select_acc": agg_stat([x for x in sel if x == x]) if any(x == x for x in sel) else None,
        "pos_neg_margin": agg_stat([m for m in margin if m == m]) if any(m == m for m in margin) else None,
        "conditions": conds,
    }


def classify_outcome(summ: dict, d_full: dict) -> dict:
    """Map the schedule ablation to one outcome category."""
    dfull_acc = d_full["final_acc"]["mean"]
    dfull_hard = {c: d_full["conditions"][c]["mean"] for c in PREREGISTERED_HARD}
    baseline_acc = summ["A"]["final_acc"]["mean"]

    per_arm = {}
    for arm in SCHEDULE_ARMS:
        s = summ[arm]
        retains_acc = s["final_acc"]["mean"] >= dfull_acc - 0.05
        reliable = s["min_seed_acc"] >= 0.80          # no seed collapse
        hard_improved = [c for c in PREREGISTERED_HARD
                         if s["conditions"][c]["mean"] > dfull_hard[c] + 0.05]
        ent = s["cand_entropy"]["mean"] if s["cand_entropy"] else float("nan")
        avoids_collapse = ent > 0.10                  # well above D-full's ~0.0
        falls_back = s["final_acc"]["mean"] <= baseline_acc + 0.15
        per_arm[arm] = {
            "retains_acc": bool(retains_acc), "reliable": bool(reliable),
            "hard_improved": hard_improved, "n_hard_improved": len(hard_improved),
            "cand_entropy": ent, "avoids_collapse": bool(avoids_collapse),
            "falls_back_to_baseline": bool(falls_back),
        }

    # Category logic.
    supported = [a for a, v in per_arm.items()
                 if v["retains_acc"] and v["reliable"] and v["n_hard_improved"] >= 2
                 and v["avoids_collapse"]]
    binding_kept = [a for a, v in per_arm.items() if v["retains_acc"] and v["reliable"]]
    all_fall_back = all(v["falls_back_to_baseline"] for v in per_arm.values())

    if supported:
        category = "EARLY_ONLY_SUPPORTED"
    elif all_fall_back:
        category = "AUXILIARY_REQUIRED_THROUGHOUT"
    elif binding_kept and not any(v["n_hard_improved"] >= 2 for v in per_arm.values()):
        category = "BINDING_GAIN_BUT_GENERALIZATION_NOT_RECOVERED"
    else:
        category = "NO_RELIABLE_SCHEDULE_EFFECT"
    return {"category": category, "per_arm": per_arm,
            "best_early_only": (supported[0] if supported else
                                (binding_kept[0] if binding_kept else None))}


def to_jsonable(o):
    if isinstance(o, dict):
        return {k: to_jsonable(v) for k, v in o.items()}
    if isinstance(o, list):
        return [to_jsonable(v) for v in o]
    if isinstance(o, (int, float, str, bool)) or o is None:
        return o
    return str(o)


def write_csv(all_arms: dict, path: str):
    rows = []
    for arm, per_seed in all_arms.items():
        for s in sorted(per_seed.keys()):
            d = per_seed[s]
            row = {"arm": arm, "seed": s, "cutoff_step": d.get("cutoff_step"),
                   "final_acc": d["final_acc"], "final_task_loss": d["final_task_loss"],
                   "steps_to_threshold": d.get("steps_to_threshold"),
                   "cand_entropy": d["mechanism"].get("cand_entropy"),
                   "internal_select_acc": d["mechanism"].get("internal_select_acc"),
                   "pos_neg_margin": d["mechanism"].get("pos_neg_margin")}
            for c in hard_condition_cfgs_names():
                row[f"acc_{c}"] = d["conditions"][c]
            rows.append(row)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()

    fc = FrozenConfig()
    print("=== Early-only auxiliary schedule ablation ===")
    print(f"frozen config unchanged; cutoffs: "
          + ", ".join(f"{a}={int(f*fc.steps)}" for a, f in SCHEDULE_ARMS.items()))

    existing = load_existing(fc)
    all_arms = {"A": existing["A"], "C": existing["C"], "D-full": existing["D-full"]}

    for arm, frac in SCHEDULE_ARMS.items():
        all_arms[arm] = {}
        for seed in fc.screen_seeds:
            ts = time.time()
            all_arms[arm][seed] = train_scheduled_D(fc, seed, frac)
            print(f"  {arm} seed {seed}: acc={all_arms[arm][seed]['final_acc']:.3f} "
                  f"entropy={all_arms[arm][seed]['mechanism'].get('cand_entropy', float('nan')):.3f} "
                  f"cutoff={all_arms[arm][seed]['cutoff_step']}  ({time.time()-ts:.0f}s)")

    summ = {arm: summarize_arm(per_seed) for arm, per_seed in all_arms.items()}
    outcome = classify_outcome(summ, summ["D-full"])

    print("\n=== SUMMARY (in-distribution) ===")
    for arm in ("A", "C", "D-full", "D-10", "D-25", "D-50"):
        s = summ[arm]
        ent = s["cand_entropy"]["mean"] if s["cand_entropy"] else float("nan")
        print(f"  {arm:6s}: acc={s['final_acc']['mean']:.3f}±{s['final_acc']['std']:.3f} "
              f"min_seed={s['min_seed_acc']:.3f} entropy={ent:.3f}")
    print("\n=== HARD CONDITIONS (mean acc) ===")
    for c in PREREGISTERED_HARD:
        print(f"  {c:18s}: " + " ".join(
            f"{a}={summ[a]['conditions'][c]['mean']:.3f}" for a in
            ("A", "C", "D-full", "D-10", "D-25", "D-50")))
    print(f"\n=== OUTCOME: {outcome['category']} (best early-only: {outcome['best_early_only']}) ===")
    for a, v in outcome["per_arm"].items():
        print(f"  {a}: retains_acc={v['retains_acc']} reliable={v['reliable']} "
              f"hard_improved={v['hard_improved']} avoids_collapse={v['avoids_collapse']}")

    # ---- plots with cutoff markers ----
    plot_dir = os.path.join(OUT, "plots")
    plot_schedule(all_arms, summ, fc, plot_dir)

    # ---- persist ----
    result = {
        "frozen_config": to_jsonable(fc.__dict__),
        "schedule_arms": SCHEDULE_ARMS,
        "summary": to_jsonable(summ),
        "outcome": to_jsonable(outcome),
        "per_seed": to_jsonable({a: {str(s): {k: v for k, v in all_arms[a][s].items()}
                                     for s in all_arms[a]} for a in all_arms}),
        "wall_clock_s": time.time() - t0,
    }
    with open(os.path.join(OUT, "schedule_results.json"), "w") as f:
        json.dump(result, f, indent=2)
    write_csv(all_arms, os.path.join(OUT, "schedule_results.csv"))
    print(f"\nWrote RESULTS_SCHEDULE/schedule_results.json, .csv, plots/  ({result['wall_clock_s']:.0f}s)")
    return result


def plot_schedule(all_arms, summ, fc, plot_dir):
    """Accuracy, entropy, and margin vs steps with cutoff markers; hard-condition bars."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    os.makedirs(plot_dir, exist_ok=True)
    colors = {"A": "#444444", "C": "#1f77b4", "D-full": "#d62728",
              "D-10": "#2ca02c", "D-25": "#ff7f0e", "D-50": "#9467bd"}
    order = ["A", "C", "D-full", "D-10", "D-25", "D-50"]

    def mean_curve(arm, key):
        hs = [all_arms[arm][s]["history"] for s in sorted(all_arms[arm].keys())]
        steps = [h["step"] for h in hs[0]]
        return steps, [sum(h[i].get(key, 0.0) for h in hs) / len(hs) for i in range(len(steps))]

    def cutoffs(arm):
        return [all_arms[arm][s].get("cutoff_step") for s in sorted(all_arms[arm].keys())]

    # accuracy vs steps + cutoff markers
    for key, fname, ylab, title in [
        ("val_acc", "accuracy_vs_steps.png", "val accuracy", "Accuracy vs steps (cutoffs marked)"),
        ("mech_cand_entropy", "entropy_vs_steps.png", "Quad candidate entropy",
         "Quad candidate entropy vs steps (cutoffs marked)"),
        ("mech_pos_neg_margin", "margin_vs_steps.png", "correct−incorrect Quad margin",
         "Quad pos−neg margin vs steps (cutoffs marked)"),
    ]:
        plt.figure(figsize=(7.5, 4.8))
        for arm in order:
            s, v = mean_curve(arm, key)
            plt.plot(s, v, marker="o", ms=3, color=colors[arm], label=arm)
            if arm in SCHEDULE_ARMS:
                cs = cutoffs(arm)[0]
                plt.axvline(cs, color=colors[arm], ls=":", alpha=0.6)
        plt.xlabel("training step"); plt.ylabel(ylab); plt.title(title)
        plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
        plt.savefig(os.path.join(plot_dir, fname), dpi=110); plt.close()

    # hard-condition grouped bars
    conds = ["in_distribution"] + PREREGISTERED_HARD
    x = np.arange(len(conds)); w = 0.8 / len(order)
    plt.figure(figsize=(9, 4.8))
    for j, arm in enumerate(order):
        means = [summ[arm]["conditions"][c]["mean"] for c in conds]
        errs = [summ[arm]["conditions"][c]["std"] for c in conds]
        plt.bar(x + j * w, means, w, yerr=errs, capsize=2, color=colors[arm], label=arm)
    plt.xticks(x + w * (len(order) - 1) / 2, conds, rotation=15, ha="right", fontsize=8)
    plt.ylabel("exact-match accuracy"); plt.title("Accuracy by condition (mean ± sd, 3 seeds)")
    plt.legend(fontsize=8, ncol=2); plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, "hard_conditions.png"), dpi=110); plt.close()

    # final candidate entropy bar (the over-sharpening summary)
    plt.figure(figsize=(6.5, 4))
    ents = [summ[a]["cand_entropy"]["mean"] if summ[a]["cand_entropy"] else 0.0
            for a in order]
    plt.bar(order, ents, color=[colors[a] for a in order])
    plt.ylabel("final Quad candidate entropy"); plt.title("Score sharpening (lower = sharper)")
    plt.grid(alpha=0.3, axis="y"); plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, "final_entropy.png"), dpi=110); plt.close()


if __name__ == "__main__":
    main()
