"""
run_study.py — Phase-as-admission-router study.

Trains the 5 learned routers per seed (Phase frozen), evaluates all 12 arms across the
capacity ladder on the single-hop task and the multi-hop task (3 seeds), runs causal controls
on the selected matcher, the multi-hop admission breakdown, and a resource audit. Writes
results/raw/*.json, aggregate.json, tables.md. The saturation gate (§11) is evaluated from the
per-arm results (COND vs random vs oracle).
"""
from __future__ import annotations

import json
import statistics as st
import time
from pathlib import Path

import torch

from .config import (ROUTERS, LEARNED, LADDER, SEEDS, DataCfg, TrainCfg,
                     SAT_RANDOM_MAX, SAT_COND_LO, SAT_COND_HI, SAT_ORACLE_MIN,
                     ACCEPT_ADMISSION_GAIN, ACCEPT_ACC_GAIN)
from .capacity_dataset import build_vocab, generate
from .routers import build_router, MODE
from .train import train_router
from .evaluate import evaluate_arm
from .causal_controls import run_controls
from .multihop_eval import eval_multihop
from .resource_audit import run_audit
from .hard_negatives import hard_cfg

HERE = Path(__file__).resolve().parent
RAW = HERE / "results" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
BEST = "R-bilinear-hard"          # strongest explicit matcher (cosine≈bilinear; bilinear wins raw AUROC)
EVAL_N = 200


def train_learned(seed, vocab):
    single = DataCfg(family="single"); models = {}
    cfgt = TrainCfg(seed=seed, steps=600)
    for arm in LEARNED:
        m = build_router(arm, vocab, seed)
        dcfg = hard_cfg(single) if arm == "R-bilinear-hard" else single
        train_router(m, arm, vocab, cfgt, dcfg)
        models[arm] = m
    # shuffled/removed reuse the bilinear-hard model
    models["R-shuffled"] = models[BEST]; models["R-removed"] = models[BEST]
    return models


def run(seeds=SEEDS):
    vocab = build_vocab(); t0 = time.time()
    single = DataCfg(family="single"); multi = DataCfg(family="multihop", multihop_depth=2)
    cells = {}     # (arm, family, regime) -> list over seeds
    controls_all, multihop_all = [], []
    for seed in seeds:
        models = train_learned(seed, vocab)
        print(f"[seed {seed}] trained learned routers ({time.time()-t0:.0f}s)", flush=True)
        for fam, dcfg in (("single", single), ("multihop", multi)):
            for N, Ks in LADDER:
                for K in Ks:
                    te = generate(vocab, dcfg, N, K, EVAL_N, 9000 + seed)
                    for arm in ROUTERS:
                        m = models.get(arm)
                        r = evaluate_arm(arm, m, te, vocab, K)
                        cells.setdefault((arm, fam, f"N{N}_K{K}"), []).append(r)
        # causal controls (best matcher) + multihop breakdown, seed-level
        te_mh = generate(vocab, multi, 128, 8, EVAL_N, 9000 + seed)
        controls_all.append(run_controls(models[BEST], BEST, te_mh, vocab, 8))
        mh = {arm: eval_multihop(arm, models.get(arm), te_mh, vocab, 8)
              for arm in ("R-random", "R-COND", BEST, "R-oracle")}
        multihop_all.append(mh)
        print(f"[seed {seed}] controls + multihop done ({time.time()-t0:.0f}s)", flush=True)

    agg = aggregate(cells)
    agg["controls_best"] = {k: st.mean([c[k] for c in controls_all]) for k in controls_all[0]}
    agg["multihop_breakdown"] = {arm: {k: st.mean([m[arm][k] for m in multihop_all]) for k in multihop_all[0][arm]}
                                 for arm in multihop_all[0]}
    agg["resources"] = run_audit()
    agg["saturation"] = saturation(agg)
    agg["endpoints"] = endpoints(agg)
    (HERE / "results" / "aggregate.json").write_text(json.dumps(agg, indent=2, default=float))
    write_tables(agg)
    print(f"STUDY DONE {time.time()-t0:.0f}s", flush=True)
    return agg


def _m(xs):
    return {"mean": st.mean(xs), "std": st.pstdev(xs) if len(xs) > 1 else 0.0, "min": min(xs), "raw": xs}


def aggregate(cells):
    out = {"cells": {}}
    for (arm, fam, reg), lst in cells.items():
        out["cells"].setdefault(fam, {}).setdefault(reg, {})[arm] = {
            "accuracy": _m([r["accuracy"] for r in lst]),
            "relevant_recall": _m([r["relevant_recall"] for r in lst]),
            "hard_false_admit": _m([r["hard_false_admit"] for r in lst]),
        }
    return out


def saturation(agg):
    """§11: is any single-hop regime non-saturated (random low, COND mid, oracle high)?"""
    windows = {}
    for reg, arms in agg["cells"]["single"].items():
        rnd = arms["R-random"]["accuracy"]["mean"]; cond = arms["R-COND"]["accuracy"]["mean"]
        orc = arms["R-oracle"]["accuracy"]["mean"]
        windows[reg] = {"random": rnd, "cond": cond, "oracle": orc,
                        "cond_in_window": SAT_COND_LO <= cond <= SAT_COND_HI,
                        "valid_nonsaturated": rnd <= SAT_RANDOM_MAX and orc >= SAT_ORACLE_MIN and SAT_COND_LO <= cond <= SAT_COND_HI}
    any_window = any(w["valid_nonsaturated"] for w in windows.values())
    return {"per_regime": windows, "any_cond_in_window": any_window}


def endpoints(agg):
    """Δacc and Δadmission (bilinear-hard − COND) per single-hop regime, + oracle-gap closure."""
    ep = {}
    for reg, arms in agg["cells"]["single"].items():
        b = arms[BEST]; c = arms["R-COND"]; o = arms["R-oracle"]
        dacc = b["accuracy"]["mean"] - c["accuracy"]["mean"]
        drec = b["relevant_recall"]["mean"] - c["relevant_recall"]["mean"]
        gap = o["accuracy"]["mean"] - c["accuracy"]["mean"]
        ep[reg] = {"delta_acc_best_minus_cond": dacc, "delta_admission_best_minus_cond": drec,
                   "oracle_gap": gap, "oracle_gap_closure": (dacc / gap) if gap > 1e-6 else 0.0}
    return ep


def write_tables(agg):
    L = ["# Phase capacity-router — tables", ""]
    for fam in ("single", "multihop"):
        L += [f"## {fam}: exact-answer accuracy by arm × regime (3-seed mean)"]
        regs = sorted(agg["cells"][fam].keys())
        L += ["| arm | " + " | ".join(regs) + " |", "|" + "---|" * (len(regs) + 1)]
        for arm in ROUTERS:
            row = [f"{agg['cells'][fam][r][arm]['accuracy']['mean']:.3f}" if arm in agg['cells'][fam][r] else "—" for r in regs]
            L.append(f"| {arm} | " + " | ".join(row) + " |")
        L.append("")
    sat = agg["saturation"]
    L += ["## Saturation (§11)", f"Any non-saturated regime with COND in [0.35,0.75]: **{sat['any_cond_in_window']}**"]
    for reg, w in sat["per_regime"].items():
        L.append(f"- single {reg}: random {w['random']:.3f} / COND {w['cond']:.3f} / oracle {w['oracle']:.3f} "
                 f"→ valid={w['valid_nonsaturated']}")
    L += ["", "## Endpoint Δ (R-bilinear-hard − R-COND), single-hop"]
    for reg, e in agg["endpoints"].items():
        L.append(f"- {reg}: Δacc {e['delta_acc_best_minus_cond']:+.3f}, Δadmission "
                 f"{e['delta_admission_best_minus_cond']:+.3f}, oracle-gap-closure {e['oracle_gap_closure']:+.2f}")
    c = agg["controls_best"]
    L += ["", "## Causal controls (best matcher, multihop N128 K8)",
          f"intact {c['intact']:.3f} / summary_removed {c['summary_removed']:.3f} / "
          f"summary_shuffled {c['summary_shuffled']:.3f} / score_shuffled {c['score_shuffled']:.3f} "
          f"/ causal_delta {c['causal_delta']:+.3f}"]
    mh = agg["multihop_breakdown"]
    L += ["", "## Multi-hop breakdown (N128 K8)",
          "| arm | acc | P(all req admitted) | acc|all-admitted |", "|---|---:|---:|---:|"]
    for arm, v in mh.items():
        L.append(f"| {arm} | {v['accuracy']:.3f} | {v['P_all_admitted']:.3f} | {v['acc_given_all_admitted']:.3f} |")
    (HERE / "results" / "tables.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    run()
