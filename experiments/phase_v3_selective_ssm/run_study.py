"""
run_study.py — Phase v3 selective-SSM focus-retention study.

Cross-variant comparison (V1 / V2-S / V3-B / V3-AB / V3-ABC) in the main supervision
mode (B_annealed) across 3 seeds and distances 64…2048 (4096 for the primary trio). For
V3-ABC additionally: supervision modes A/B/C (§16.6), §14 causal ablations, §15 dynamics.
Plus a resource audit (§9/§18). Writes results/raw/*.json, aggregate.json, tables.md.
"""
from __future__ import annotations

import json
import statistics as st
import time
from pathlib import Path

import torch

from .config import (VARIANTS, SEEDS, TrainCfg, DataCfg, MAIN_MODE,
                     ACCEPT_STATE_MINUS_CONTROL, ACCEPT_ANNEAL_RETENTION)
from .dataset import build_vocab
from .train import FocusModel, train_focus
from .distance_eval import eval_distances, eval_distractor_robustness
from .ablations import run_ablations
from .dynamics_analysis import analyze
from .resource_audit import run_audit

HERE = Path(__file__).resolve().parent
RAW = HERE / "results" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

DIST_MAIN = (64, 128, 256, 512, 1024, 2048)
DIST_TRIO = (64, 128, 256, 512, 1024, 2048, 4096)
TRIO = ("V1", "V2-S", "V3-ABC")


def train_variant(name, seed, mode, vocab, dcfg):
    torch.manual_seed(seed)
    m = FocusModel(name, vocab.size)
    train_focus(m, vocab, TrainCfg(seed=seed), mode=mode, dcfg=dcfg)
    return m


def run(seeds=SEEDS, variants=VARIANTS):
    vocab = build_vocab(); dcfg = DataCfg()
    t0 = time.time()
    cells = {}       # (variant,mode) -> list over seeds of {distance dict, robustness}
    for name in variants:
        dists = DIST_TRIO if name in TRIO else DIST_MAIN
        per = []
        for seed in seeds:
            m = train_variant(name, seed, MAIN_MODE, vocab, dcfg)
            dev = eval_distances(m, vocab, dcfg, dists, seed=seed)
            rob = eval_distractor_robustness(m, vocab, dcfg, 512, seed=seed)
            rec = {"variant": name, "mode": MAIN_MODE, "seed": seed,
                   "distances": dev, "distractor_robust": rob}
            (RAW / f"{name}_{MAIN_MODE}_s{seed}.json").write_text(json.dumps(rec, indent=2, default=float))
            per.append(rec)
            longest = max(dev.keys(), key=int)
            print(f"[{name} s{seed}] d{longest}: state={dev[longest]['state_top1']:.3f} "
                  f"sel={dev[longest]['selective_top1']:.3f} "
                  f"ctrl={max(dev[longest]['shuffled_top1'], dev[longest]['random_top1']):.3f} "
                  f"({time.time()-t0:.0f}s)", flush=True)
        cells[(name, MAIN_MODE)] = per

    # V3-ABC supervision modes A and C (B already done above) — §16.6
    for mode in ("A_supervised", "C_scratch"):
        per = []
        for seed in seeds:
            m = train_variant("V3-ABC", seed, mode, vocab, dcfg)
            dev = eval_distances(m, vocab, dcfg, DIST_TRIO, seed=seed)
            rec = {"variant": "V3-ABC", "mode": mode, "seed": seed, "distances": dev}
            (RAW / f"V3-ABC_{mode}_s{seed}.json").write_text(json.dumps(rec, indent=2, default=float))
            per.append(rec)
            print(f"[V3-ABC {mode} s{seed}] done ({time.time()-t0:.0f}s)", flush=True)
        cells[("V3-ABC", mode)] = per

    # §14 ablations + §15 dynamics for V3-ABC (seed 0), reusing a fresh B-mode model
    m0 = train_variant("V3-ABC", 0, MAIN_MODE, vocab, dcfg)
    abl = run_ablations(m0, vocab, dcfg, distance=512, seed=0)
    dyn = analyze(m0, vocab, dcfg, distance=512, seed=0)
    (RAW / "ablations_V3-ABC_s0.json").write_text(json.dumps(abl, indent=2, default=float))
    (RAW / "dynamics_V3-ABC_s0.json").write_text(json.dumps(dyn, indent=2, default=float))
    print(f"[ablations+dynamics] done ({time.time()-t0:.0f}s)", flush=True)

    resources = run_audit()
    agg = aggregate(cells, seeds)
    agg["ablations_V3-ABC_s0"] = abl
    agg["dynamics_V3-ABC_s0"] = dyn
    agg["resources"] = resources
    (HERE / "results" / "aggregate.json").write_text(json.dumps(agg, indent=2, default=float))
    write_tables(agg)
    print(f"STUDY DONE {time.time()-t0:.0f}s", flush=True)
    return agg


def _mean(xs):
    return {"mean": st.mean(xs), "std": st.pstdev(xs) if len(xs) > 1 else 0.0, "raw": xs}


def aggregate(cells, seeds):
    out = {"by_variant": {}, "modes_V3-ABC": {}, "endpoints": {}}
    # per-variant per-distance means (main mode)
    for (name, mode), per in cells.items():
        dists = sorted({d for r in per for d in r["distances"]}, key=int)
        table = {}
        for d in dists:
            table[d] = {
                "state_top1": _mean([r["distances"][d]["state_top1"] for r in per if d in r["distances"]]),
                "selective_top1": _mean([r["distances"][d]["selective_top1"] for r in per if d in r["distances"]]),
                "control_top1": _mean([max(r["distances"][d]["shuffled_top1"],
                                           r["distances"][d]["random_top1"]) for r in per if d in r["distances"]]),
                "relevance_f1": _mean([r["distances"][d]["relevance_f1"] for r in per if d in r["distances"]]),
            }
        entry = {"distances": table}
        if mode == MAIN_MODE:
            out["by_variant"][name] = entry
        out["modes_V3-ABC"].setdefault(name, {})[mode] = entry if name == "V3-ABC" else None

    # endpoints (§16), evaluated at the longest common distance and at 2048
    def at(name, d, mode=MAIN_MODE):
        e = out["by_variant"].get(name) if mode == MAIN_MODE else None
        if e and d in e["distances"]:
            return e["distances"][d]
        return None

    for d in ("512", "1024", "2048"):
        v3 = at("V3-ABC", d); v1 = at("V1", d); v2 = at("V2-S", d)
        if v3 and v1:
            out["endpoints"][f"d{d}"] = {
                "V3ABC_state_minus_control": v3["state_top1"]["mean"] - v3["control_top1"]["mean"],
                "V3ABC_state_top1": v3["state_top1"]["mean"],
                "V3ABC_selective_top1": v3["selective_top1"]["mean"],
                "selective_ge_state": v3["selective_top1"]["mean"] >= v3["state_top1"]["mean"] - 0.02,
                "V3ABC_minus_V1_state": v3["state_top1"]["mean"] - v1["state_top1"]["mean"],
                "V3ABC_minus_V2S_state": (v3["state_top1"]["mean"] - v2["state_top1"]["mean"]) if v2 else None,
                "V3ABC_relF1": v3["relevance_f1"]["mean"],
                "V2S_relF1": v2["relevance_f1"]["mean"] if v2 else None,
                "state_control_gate_met": (v3["state_top1"]["mean"] - v3["control_top1"]["mean"]) >= ACCEPT_STATE_MINUS_CONTROL,
            }

    # §16.6 annealed retention: mode B / mode A at 2048
    modes = out["modes_V3-ABC"].get("V3-ABC", {})
    if modes.get("A_supervised") and modes.get("B_annealed"):
        a = modes["A_supervised"]["distances"].get("2048")
        b = modes["B_annealed"]["distances"].get("2048")
        if a and b and a["state_top1"]["mean"] > 1e-6:
            ratio = b["state_top1"]["mean"] / a["state_top1"]["mean"]
            out["endpoints"]["annealed_retention_ratio_d2048"] = {
                "ratio": ratio, "met": ratio >= ACCEPT_ANNEAL_RETENTION,
                "A_state": a["state_top1"]["mean"], "B_state": b["state_top1"]["mean"]}
    return out


def write_tables(agg):
    L = ["# Phase v3 selective-SSM — tables", ""]
    L += ["## Focus Top-1 by variant × distance (mode B_annealed, mean over seeds)",
          "| variant | " + " | ".join(f"d{d}" for d in DIST_TRIO) + " |",
          "|" + "---|" * (len(DIST_TRIO) + 1)]
    for name in VARIANTS:
        e = agg["by_variant"].get(name)
        if not e:
            continue
        cells = []
        for d in DIST_TRIO:
            c = e["distances"].get(str(d))
            cells.append(f"{c['state_top1']['mean']:.3f}" if c else "—")
        L.append(f"| {name} | " + " | ".join(cells) + " |")
    L += ["", "## Control separation (V3-ABC state − max(shuffled,random))"]
    for d, ep in agg.get("endpoints", {}).items():
        if isinstance(ep, dict) and "V3ABC_state_minus_control" in ep:
            L.append(f"- {d}: state {ep['V3ABC_state_top1']:.3f} − control {ep['V3ABC_state_top1']-ep['V3ABC_state_minus_control']:.3f} "
                     f"= **{ep['V3ABC_state_minus_control']:+.3f}** (gate {'MET' if ep['state_control_gate_met'] else 'not met'}); "
                     f"V3−V1 {ep['V3ABC_minus_V1_state']:+.3f}")
    ar = agg.get("endpoints", {}).get("annealed_retention_ratio_d2048")
    if ar:
        L += ["", f"## Annealed retention (d2048): B/A = {ar['ratio']:.2f} "
              f"({'MET' if ar['met'] else 'not met'} ≥0.80)"]
    (HERE / "results" / "tables.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    run()
