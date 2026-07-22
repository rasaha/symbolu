#!/usr/bin/env python
"""Main driver for the Quad Generative Regularization CPU screen.

Runs the frozen protocol end-to-end and writes machine-readable results, plots, and a
verdict to RESULTS/.  Usage:

    python run_screen.py            # 3-seed screen (+ confirmation/controls if PROMISING)
    python run_screen.py --quick    # smaller/faster smoke run for iteration
    python run_screen.py --no-confirm   # stop after the 3-seed screen

All settings come from the frozen config (qgr.experiment.FrozenConfig); nothing is tuned
after results are observed.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time

import torch

from qgr.experiment import (
    FrozenConfig, run_seed, aggregate, positive_signal_gate, grad_reaches_shared,
    check_a_vs_d0, classify_mechanism, classify_generalization, classify_economics,
    three_seed_verdict, five_seed_verdict, hard_condition_cfgs_names, PREREGISTERED_HARD,
    eval_seqlen_curve,
)
from qgr.quad_model import build_model
from qgr.mqar import MQARConfig, generate_batch
from qgr import plotting

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "RESULTS")


def leakage_check(fc: FrozenConfig) -> dict:
    """Runtime future-shuffle invariance check (spec section 9): shuffling tokens strictly
    after a query position must not change that query's Quad score row over j<=i."""
    torch.manual_seed(0)
    model = build_model(fc.model_cfg(), 0).eval()
    mq = fc.base_mqar()
    b = generate_batch(mq, seed=999, batch_size=4)
    N = b.tokens.shape[1]
    qp = int((b.key_pos >= 0).nonzero(as_tuple=False)[:, 1].min())
    with torch.no_grad():
        s0 = model(b.tokens, expose_quad=True)["quad_score"]
        toks2 = b.tokens.clone()
        if qp + 1 < N:
            g = torch.Generator().manual_seed(1)
            perm = torch.randperm(N - (qp + 1), generator=g)
            toks2[:, qp + 1:] = toks2[:, qp + 1:][:, perm]
        s1 = model(toks2, expose_quad=True)["quad_score"]
    max_diff = float((s0[:, :, qp, :qp + 1] - s1[:, :, qp, :qp + 1]).abs().max())
    return {"future_shuffle_invariant": max_diff < 1e-6, "max_diff": max_diff}


def inference_invariance_check(fc: FrozenConfig) -> dict:
    """Spec item 16: identical inference output before/after exposing aux-only objects."""
    model = build_model(fc.model_cfg(), 0).eval()
    toks = generate_batch(fc.base_mqar(), seed=7, batch_size=4).tokens
    with torch.no_grad():
        a = model(toks)["logits"]
        b = model(toks, expose_quad=True, expose_hidden=True)["logits"]
    return {"identical": bool(torch.equal(a, b))}


def to_jsonable(obj):
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    return str(obj)


def strip_models(per_seed):
    """Remove non-serializable and heavy fields for JSON dump (keep histories)."""
    out = {}
    for s, arms in per_seed.items():
        out[s] = {}
        for arm, d in arms.items():
            out[s][arm] = {k: v for k, v in d.items() if k not in ("model",)}
    return out


def write_csv(per_seed, path):
    rows = []
    for s in sorted(per_seed.keys()):
        for arm in per_seed[s]:
            d = per_seed[s][arm]
            row = {"seed": s, "arm": arm, "final_acc": d["final_acc"],
                   "final_seq_acc": d["final_seq_acc"], "final_task_loss": d["final_task_loss"],
                   "steps_to_threshold": d["steps_to_threshold"],
                   "mean_step_time_s": d["mean_step_time"],
                   "total_train_time_s": d["total_train_time"],
                   "num_params": d["num_params"]}
            for c in hard_condition_cfgs_names():
                row[f"acc_{c}"] = d["conditions"][c]
            rows.append(row)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--no-confirm", action="store_true")
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()
    torch.set_num_threads(args.threads)

    fc = FrozenConfig()
    if args.quick:
        fc.steps = 400; fc.eval_every = 100; fc.grad_diag_every = 200
        fc.screen_seeds = [0, 1]; fc.confirm_seeds = []
    os.makedirs(RESULTS, exist_ok=True)
    t_start = time.time()
    print(f"=== Quad Generative Regularization — CPU screen ===")
    print(f"frozen config: {fc.model_cfg()}")
    print(f"base MQAR: kv={fc.num_kv} q={fc.num_queries} vocab={fc.vocab_size} "
          f"steps={fc.steps} lambda={fc.lambda_aux} tau={fc.tau}")

    # ---- Phase 0B validations -------------------------------------------------------
    print("\n[Phase 0B] deterministic A vs D0 equivalence ...")
    equiv = check_a_vs_d0(fc)
    print(f"  A==D0 identical: {equiv['identical']} (max param diff {equiv['max_param_diff']:.2e})")
    print("[Phase 0B] leakage / future-shuffle invariance ...")
    leak = leakage_check(fc)
    print(f"  future-shuffle invariant: {leak['future_shuffle_invariant']} "
          f"(max diff {leak['max_diff']:.2e})")
    inv = inference_invariance_check(fc)
    print(f"  inference invariant w/ aux disabled: {inv['identical']}")
    equivalence_ok = equiv["identical"]
    leakage_ok = leak["future_shuffle_invariant"] and inv["identical"]

    # ---- Phase 2: 3-seed screen -----------------------------------------------------
    print(f"\n[Phase 2] initial screen, seeds={fc.screen_seeds} ...")
    per_seed = {}
    for seed in fc.screen_seeds:
        t0 = time.time()
        per_seed[seed] = run_seed(fc, seed)
        print(f"  seed {seed}: "
              + " ".join(f"{a}={per_seed[seed][a]['final_acc']:.3f}" for a in ("A", "C", "D"))
              + f"  ({time.time()-t0:.0f}s)")

    agg = aggregate(per_seed)
    grad_ok = grad_reaches_shared(per_seed)
    gate = positive_signal_gate(agg, per_seed, grad_ok)
    print(f"\n[Gate] mean A={gate['mean_A']:.3f} C={gate['mean_C']:.3f} D={gate['mean_D']:.3f}")
    print(f"[Gate] criteria: {gate['criteria']}")
    print(f"[Gate] label: {gate['label']}")

    # ---- Phase 3 + controls (conditional) -------------------------------------------
    shuffle_reproduces = None
    confirm_ran = False
    if gate["passed"] and not args.no_confirm and fc.confirm_seeds:
        print(f"\n[Phase 3] PROMISING -> confirmation seeds={fc.confirm_seeds} ...")
        for seed in fc.confirm_seeds:
            t0 = time.time()
            per_seed[seed] = run_seed(fc, seed)
            print(f"  seed {seed}: "
                  + " ".join(f"{a}={per_seed[seed][a]['final_acc']:.3f}" for a in ("A", "C", "D"))
                  + f"  ({time.time()-t0:.0f}s)")
        confirm_ran = True
        agg = aggregate(per_seed)
        grad_ok = grad_reaches_shared(per_seed)

        print("\n[Control 21.1] shuffled-label control (Arm D, seeds="
              f"{fc.screen_seeds}) ...")
        shuf = {}
        for seed in fc.screen_seeds:
            r = run_seed(fc, seed, arms=("D",), shuffle_d=True)
            shuf[seed] = r["D"]["final_acc"]
            print(f"  seed {seed}: D-shuffled={shuf[seed]:.3f} vs D={per_seed[seed]['D']['final_acc']:.3f}")
        # Does shuffling reproduce D's gain over A within uncertainty?
        import statistics as st
        d_gain = agg["D"]["final_acc"]["mean"] - agg["A"]["final_acc"]["mean"]
        shuf_gain = st.mean(shuf.values()) - agg["A"]["final_acc"]["mean"]
        shuffle_reproduces = shuf_gain >= 0.5 * d_gain
        print(f"  D gain={d_gain:.3f}, shuffled gain={shuf_gain:.3f} -> "
              f"reproduces={shuffle_reproduces}")

    # ---- Classification & verdict ---------------------------------------------------
    mechanism = classify_mechanism(agg, per_seed, shuffle_reproduces)
    generalization = classify_generalization(agg)
    economics = classify_economics(equal_wallclock_ran=False)
    v3 = three_seed_verdict(gate, equivalence_ok, leakage_ok)
    v5 = five_seed_verdict(mechanism, generalization, shuffle_reproduces,
                           equivalence_ok, leakage_ok, agg) if confirm_ran else None

    print(f"\n=== CLASSIFICATION ===")
    print(f"  mechanism:      {mechanism}")
    print(f"  generalization: {generalization}")
    print(f"  economics:      {economics}")
    print(f"  3-seed verdict: {v3}")
    if v5:
        print(f"  5-seed verdict: {v5}")

    # ---- Plots ----------------------------------------------------------------------
    plot_dir = os.path.join(RESULTS, "plots")
    per_arm_hist = {a: [per_seed[s][a]["history"] for s in sorted(per_seed)] for a in ("A", "C", "D")}
    per_arm_grad = {a: [per_seed[s][a]["grad_history"] for s in sorted(per_seed)] for a in ("C", "D")}
    plotting.plot_curves(per_arm_hist, plot_dir)
    plotting.plot_grad_norms(per_arm_grad, plot_dir)
    hard_for_plot = {a: {c: agg[a]["conditions"][c] for c in hard_condition_cfgs_names()}
                     for a in ("A", "C", "D")}
    plotting.plot_hard_conditions(hard_for_plot, plot_dir)
    seqlen_for_plot = {}
    for a in ("A", "C", "D"):
        lens = sorted(per_seed[sorted(per_seed)[0]][a]["seqlen_curve"].keys())
        seqlen_for_plot[a] = {L: {"mean": sum(per_seed[s][a]["seqlen_curve"][L] for s in per_seed)/len(per_seed),
                                   "std": 0.0} for L in lens}
    plotting.plot_seq_len_curve(seqlen_for_plot, plot_dir)
    plotting.plot_cpu_time({a: agg[a]["total_train_time"]["mean"] for a in ("A", "C", "D")}, plot_dir)

    # ---- Persist --------------------------------------------------------------------
    result = {
        "frozen_config": to_jsonable(fc.__dict__),
        "phase0b": {"a_vs_d0": equiv, "leakage": leak, "inference_invariance": inv,
                    "equivalence_ok": equivalence_ok, "leakage_ok": leakage_ok},
        "aggregate": to_jsonable(agg),
        "gate": to_jsonable(gate),
        "grad_reaches_shared": grad_ok,
        "shuffle_reproduces": shuffle_reproduces,
        "classification": {"mechanism": mechanism, "generalization": generalization,
                            "economics": economics},
        "verdict_3seed": v3,
        "verdict_5seed": v5,
        "per_seed": strip_models(per_seed),
        "wall_clock_s": time.time() - t_start,
    }
    with open(os.path.join(RESULTS, "results.json"), "w") as f:
        json.dump(to_jsonable(result), f, indent=2)
    write_csv(per_seed, os.path.join(RESULTS, "results.csv"))
    print(f"\nWrote RESULTS/results.json, results.csv, plots/  ({result['wall_clock_s']:.0f}s total)")
    return result


if __name__ == "__main__":
    main()
