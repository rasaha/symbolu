#!/usr/bin/env python
"""Bounded Quad retrieval geometry — 3-seed experiment.

Tests whether L2-normalizing the projected Quad query/key and applying a fixed scale alpha
(|S^Q| <= alpha) prevents unlimited margin growth while preserving early binding and improving
generalization. Reuses frozen A / C / D-full / D-10; adds bounded BD-A / BD-D / BD-D10.
Frozen alpha = 4 (pilot: alpha=2 -> acc .965/entropy .82, alpha=4 -> 1.0/.15, alpha=8 -> 1.0/.008;
alpha=8 fails the avoid-near-zero-entropy rule, alpha=4 is the lowest scale that RELIABLY reaches
100% while keeping entropy well above zero). Writes RESULTS_BOUNDED/.
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
from qgr.mqar import generate_batch, split_seed
from qgr.train import TrainConfig, train_arm
from qgr import analysis, bounded_plots

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "RESULTS")
SCHED = os.path.join(HERE, "RESULTS_SCHEDULE")
OUT = os.path.join(HERE, "RESULTS_BOUNDED")
ALPHA = 4.0
SNAP_EVERY = 250

# (arm-label, base-arm, aux_cutoff_frac)
BOUNDED_ARMS = [("BD-A", "A", 1.0), ("BD-D", "D", 1.0), ("BD-D10", "D", 0.10)]


def bounded_fc() -> FrozenConfig:
    fc = FrozenConfig()
    fc.bounded = True
    fc.bound_alpha = ALPHA
    return fc


def run_bounded_arm(label, base_arm, frac, seed):
    fc = bounded_fc()
    analysis_batch = generate_batch(fc.base_mqar(), split_seed(seed, "val", 777), fc.batch_size)
    traj = []

    def hook(step, model, rh, active):
        model.eval(); snap = analysis.full_snapshot(model, analysis_batch)
        snap["step"] = step; snap["aux_active"] = active; traj.append(snap); model.train()

    tc = fc.train_cfg(base_arm, seed)
    tc.aux_cutoff_frac = frac
    r = train_arm(fc.model_cfg(), fc.base_mqar(), tc, analysis_hook=hook, analysis_every=SNAP_EVERY)
    model = r["model"]
    return {
        "seed": seed, "final_acc": r["final_val"]["acc"],
        "steps_to_threshold": steps_to_threshold(r["history"], fc.acc_threshold),
        "conditions": eval_model_on_conditions(model, fc, seed),
        "mechanism": quad_mechanism(model, fc.base_mqar(), seed, "test", 6, fc.batch_size),
        "final_snapshot": traj[-1], "trajectory": traj, "history": r["history"],
        "mean_step_time": r["mean_step_time"], "total_train_time": r["total_train_time"],
    }


def load_reused():
    with open(os.path.join(RESULTS, "results.json")) as f:
        scr = json.load(f)["per_seed"]
    with open(os.path.join(SCHED, "schedule_results.json")) as f:
        sch = json.load(f)["per_seed"]
    reused = {"A": {}, "C": {}, "D-full": {}, "D-10": {}}
    for s in scr:
        seed = int(s)
        reused["A"][seed] = scr[s]["A"]
        reused["C"][seed] = scr[s]["C"]
        reused["D-full"][seed] = scr[s]["D"]
    for s in sch["D-10"]:
        reused["D-10"][int(s)] = sch["D-10"][s]
    return reused


def agg(vals):
    vals = [v for v in vals if v == v]
    return {"mean": statistics.mean(vals) if vals else float("nan"),
            "std": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
            "min": min(vals) if vals else float("nan"), "values": list(vals)}


def summarize(per_seed, arm_label):
    seeds = sorted(per_seed.keys())
    acc = [per_seed[s]["final_acc"] for s in seeds]
    def mech(metric):
        return [per_seed[s]["mechanism"].get(metric, float("nan")) for s in seeds
                if "mechanism" in per_seed[s]]
    conds = {c: agg([per_seed[s]["conditions"][c] for s in seeds])
             for c in hard_condition_cfgs_names()}
    out = {"final_acc": agg(acc), "conditions": conds}
    if "mechanism" in per_seed[seeds[0]]:
        out["entropy"] = agg(mech("cand_entropy"))
        out["margin"] = agg(mech("pos_neg_margin"))
        out["select_acc"] = agg(mech("internal_select_acc"))
    return out


def classify(summ):
    dfull = summ["D-full"]; C = summ["C"]
    dfull_hard = {c: dfull["conditions"][c]["mean"] for c in PREREGISTERED_HARD}
    res = {}
    for label in ("BD-D", "BD-D10"):
        s = summ[label]
        all95 = s["final_acc"]["min"] >= 0.95
        no_collapse = s["final_acc"]["min"] >= 0.80
        higher_entropy = s["entropy"]["mean"] > dfull["entropy"]["mean"] + 0.05
        finite_margin = s["margin"]["mean"] <= ALPHA + 0.5
        hard_improved = [c for c in PREREGISTERED_HARD
                         if s["conditions"][c]["mean"] > dfull_hard[c] + 0.05]
        not_worse_than_C = all(
            s["conditions"][c]["mean"] >= C["conditions"][c]["mean"] - 0.05
            for c in PREREGISTERED_HARD)
        res[label] = {
            "reaches_95_all_seeds": bool(all95), "no_seed_collapse": bool(no_collapse),
            "entropy_higher_than_Dfull": bool(higher_entropy), "finite_margin": bool(finite_margin),
            "hard_improved_over_Dfull": hard_improved, "n_hard_improved": len(hard_improved),
            "not_worse_than_C_on_hard": bool(not_worse_than_C),
        }
    # category from the best of BD-D / BD-D10
    def learns(v, s):
        return v["no_seed_collapse"]
    any_learns = any(res[l]["no_seed_collapse"] for l in res)
    if not any_learns:
        category = "BOUND_PREVENTS_LEARNING"
    else:
        supported = [l for l in res if res[l]["reaches_95_all_seeds"]
                     and res[l]["entropy_higher_than_Dfull"] and res[l]["finite_margin"]
                     and res[l]["n_hard_improved"] >= 2]
        binding_ok = [l for l in res if res[l]["reaches_95_all_seeds"]
                      and res[l]["entropy_higher_than_Dfull"] and res[l]["finite_margin"]]
        controls_magnitude_no_gen = [l for l in binding_ok if res[l]["n_hard_improved"] == 0]
        if supported:
            category = "BOUNDED_QUAD_SUPPORTED"
        elif binding_ok and all(res[l]["n_hard_improved"] == 0 for l in binding_ok):
            category = "NORMALIZATION_DOES_NOT_FIX_GENERALIZATION"
        elif binding_ok:
            category = "BINDING_RETAINED_GENERALIZATION_LIMITED"
        else:
            category = "NO_RELIABLE_EFFECT"
    best = None
    ranked = sorted(res, key=lambda l: (res[l]["n_hard_improved"],
                                        summ[l]["final_acc"]["min"]), reverse=True)
    if ranked:
        best = ranked[0]
    return {"category": category, "per_arm": res, "best": best}


def offline_temperature_control():
    """Phase 9: post-hoc temperature on the unbounded D-full logits (from RESULTS_DYNAMICS)
    matched to the bounded alpha scale. Temperature can match ENTROPY but is ranking-invariant,
    so it cannot change D-full's hard-condition accuracy — any BD-D hard-condition difference is
    therefore a training-time effect, not rescaling."""
    path = os.path.join(HERE, "RESULTS_DYNAMICS", "dynamics_results.json")
    if not os.path.exists(path):
        return {"available": False}
    with open(path) as f:
        dyn = json.load(f)
    dtemp = dyn["final"]["D"]["temp"]
    # D-full margin ~46; bounded alpha=4 -> matching temperature ~ margin/alpha
    dmargin = dyn["final"]["D"]["dyn_margin_mean"]["mean"]
    T_match = dmargin / ALPHA
    # nearest tabulated temperature entropy
    temps = sorted(float(t) for t in dtemp["by_temp"])
    nearest = min(temps, key=lambda t: abs(t - T_match))
    return {
        "available": True, "Dfull_margin": dmargin, "alpha": ALPHA,
        "matching_temperature": T_match, "nearest_tabulated_T": nearest,
        "Dfull_entropy_frac_at_matching_T":
            dtemp["by_temp"][str(nearest)]["entropy_frac_of_uniform"],
        "ranking_preserved": dtemp["by_temp"][str(nearest)]["ranking_preserved"],
        "note": ("Temperature ~%.1f softens D-full to bounded-like entropy but preserves its "
                 "ranking, so D-full's hard-condition accuracy is unchanged; compare to BD-D's "
                 "hard conditions to isolate the training-time effect." % T_match),
    }


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
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    fc = bounded_fc()
    print(f"=== Bounded Quad retrieval geometry (alpha={ALPHA}, seeds={fc.screen_seeds}) ===")

    reused = load_reused()
    all_arms = dict(reused)
    trajectories = {}
    for label, base_arm, frac in BOUNDED_ARMS:
        all_arms[label] = {}
        trajectories[label] = {}
        for seed in fc.screen_seeds:
            ts = time.time()
            d = run_bounded_arm(label, base_arm, frac, seed)
            all_arms[label][seed] = d
            trajectories[label][seed] = d["trajectory"]
            print(f"  {label} seed {seed}: acc={d['final_acc']:.3f} "
                  f"entropy={d['mechanism']['cand_entropy']:.3f} "
                  f"margin={d['mechanism']['pos_neg_margin']:.2f}  ({time.time()-ts:.0f}s)")

    summ = {a: summarize(all_arms[a], a) for a in all_arms}
    outcome = classify(summ)
    temp_ctrl = offline_temperature_control()

    print("\n=== IN-DISTRIBUTION (acc mean/min, entropy, margin) ===")
    for a in ("A", "C", "D-full", "D-10", "BD-A", "BD-D", "BD-D10"):
        s = summ[a]
        ent = s.get("entropy", {}).get("mean", float("nan"))
        mar = s.get("margin", {}).get("mean", float("nan"))
        print(f"  {a:7s}: acc={s['final_acc']['mean']:.3f} (min {s['final_acc']['min']:.3f}) "
              f"entropy={ent:.3f} margin={mar:.2f}")
    print("\n=== HARD CONDITIONS (mean acc) ===")
    for c in PREREGISTERED_HARD:
        print(f"  {c:18s}: " + " ".join(
            f"{a}={summ[a]['conditions'][c]['mean']:.3f}"
            for a in ("A", "C", "D-full", "D-10", "BD-A", "BD-D", "BD-D10")))
    print(f"\n=== OUTCOME: {outcome['category']} (best bounded arm: {outcome['best']}) ===")
    for a, v in outcome["per_arm"].items():
        print(f"  {a}: reaches95={v['reaches_95_all_seeds']} entropy>Dfull={v['entropy_higher_than_Dfull']} "
              f"finite_margin={v['finite_margin']} hard_improved={v['hard_improved_over_Dfull']} "
              f"not_worse_than_C={v['not_worse_than_C_on_hard']}")
    if temp_ctrl.get("available"):
        print(f"\n[offline temp control] T~{temp_ctrl['matching_temperature']:.1f} matches entropy, "
              f"ranking_preserved={temp_ctrl['ranking_preserved']} -> post-hoc rescaling can't "
              f"change D-full hard-condition accuracy.")

    bounded_plots.make_all(all_arms, summ, trajectories, fc.screen_seeds[0], ALPHA,
                           os.path.join(OUT, "plots"))

    result = {
        "alpha": ALPHA, "seeds": fc.screen_seeds,
        "pilot": {"alpha_2": {"acc": 0.965, "entropy": 0.815, "margin": 2.27},
                  "alpha_4": {"acc": 1.000, "entropy": 0.150, "margin": 4.79},
                  "alpha_8": {"acc": 1.000, "entropy": 0.008, "margin": 8.50},
                  "frozen": ALPHA,
                  "rule": "alpha=8 fails avoid-near-zero-entropy; alpha=4 is the lowest scale "
                          "that reliably reaches 100% while keeping entropy well above zero."},
        "summary": to_jsonable(summ), "outcome": to_jsonable(outcome),
        "offline_temperature_control": to_jsonable(temp_ctrl),
        "bounded_per_seed": to_jsonable({a: {str(s): {k: v for k, v in all_arms[a][s].items()
                                                      if k != "trajectory"}
                                             for s in all_arms[a]}
                                         for a, _, _ in [(l, b, f) for l, b, f in BOUNDED_ARMS]}),
        "wall_clock_s": time.time() - t0,
    }
    with open(os.path.join(OUT, "bounded_results.json"), "w") as f:
        json.dump(result, f, indent=2)
    _write_csv(all_arms, summ, os.path.join(OUT, "bounded_results.csv"))
    print(f"\nWrote RESULTS_BOUNDED/  ({result['wall_clock_s']:.0f}s)")
    return result


def _write_csv(all_arms, summ, path):
    rows = []
    for arm in ("A", "C", "D-full", "D-10", "BD-A", "BD-D", "BD-D10"):
        for s in sorted(all_arms[arm].keys()):
            d = all_arms[arm][s]
            row = {"arm": arm, "seed": s, "final_acc": d["final_acc"]}
            mech = d.get("mechanism", {})
            row["entropy"] = mech.get("cand_entropy")
            row["margin"] = mech.get("pos_neg_margin")
            row["select_acc"] = mech.get("internal_select_acc")
            for c in hard_condition_cfgs_names():
                row[f"acc_{c}"] = d["conditions"][c]
            rows.append(row)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
