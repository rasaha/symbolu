"""
run_study.py — Phase-v2 oracle-retention study.

Arms C-oracle / D-v2 / D-zero / D-random / D-shuffled across seeds and pressures,
paired (identical data seeds). Reports target survival, accuracy, survival by target
position, the paired D-v2 − C endpoint, decision-trace causality, shortcut checks,
and a resource audit. Writes results/raw/*.json, aggregate.json, tables.md.
"""
from __future__ import annotations

import json
import statistics as st
import time
from pathlib import Path

import torch

from experiments.phase_guided_slots_v2.task_schema import build_vocab
from experiments.phase_guided_slots_v2 import datasets_pressure_v2 as D
from .retention_model import OCfg, RetentionModel
from .train_eval import TCfg, train_curriculum, evaluate
from .decision_trace import trace
from .shortcut_checks import run_checks
from .resource_audit import run_audit

HERE = Path(__file__).resolve().parent
RAW = HERE / "results" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

ARMS = ("C-oracle", "D-v2", "D-zero", "D-random", "D-shuffled")
SEEDS = (0, 1, 2)
PRESSURES = (12, 16)
LAMBDA = 0.25
STAGES = [(2, 100), (4, 120), (8, 150)]   # + (n_live, 180) appended per config


def train_arm(arm, n_live, seed, vocab):
    def gen_fn(nl): return D.generate(vocab, "train", seed, 300, nl, 8, focus_retention=True)
    torch.manual_seed(seed)
    m = RetentionModel(OCfg(vocab_size=vocab.size, lambda_fixed=LAMBDA), arm)
    stages = STAGES + [(n_live, 180)]
    train_curriculum(m, gen_fn, vocab.pad_id, stages, TCfg(seed=seed))
    return m


def run(arms=ARMS, seeds=SEEDS, pressures=PRESSURES):
    vocab = build_vocab()
    t0 = time.time()
    cells = {}
    for n_live in pressures:
        for arm in arms:
            per = []
            for seed in seeds:
                m = train_arm(arm, n_live, seed, vocab)
                te = D.generate(vocab, "test", 1000 + seed, 200, n_live, 8, focus_retention=True)
                ev = evaluate(m, te, vocab.pad_id)
                rec = {"arm": arm, "n_live": n_live, "seed": seed,
                       "survival": ev["target_survival_rate"], "acc": ev["answer_acc"],
                       "acc_given_survived": ev["acc_given_survived"],
                       "acc_given_evicted": ev["acc_given_evicted"],
                       "early_survival": ev["survival_by_target_position"]["early"],
                       "middle_survival": ev["survival_by_target_position"]["middle"],
                       "evictions": ev["evictions"]}
                if arm == "D-v2":
                    rec["decision_trace"] = trace(m, te[:120], vocab.pad_id)
                    rec["shortcut"] = run_checks(m, vocab, vocab.pad_id, n_live=n_live, seed=1000 + seed, n=120)
                (RAW / f"{arm}_L{n_live}_s{seed}.json").write_text(json.dumps(rec, indent=2, default=float))
                per.append(rec)
                print(f"[{arm} L{n_live} s{seed}] surv={rec['survival']:.3f} "
                      f"early={rec['early_survival']:.3f} acc={rec['acc']:.3f} "
                      f"({time.time()-t0:.0f}s)", flush=True)
            cells[f"{arm}_L{n_live}"] = per
    agg = aggregate(cells, seeds, pressures)
    agg["resources"] = run_audit()
    (HERE / "results" / "aggregate.json").write_text(json.dumps(agg, indent=2, default=float))
    write_tables(agg, pressures)
    print(f"STUDY DONE {time.time()-t0:.0f}s", flush=True)
    return agg


def aggregate(cells, seeds, pressures):
    def m(xs): return {"mean": st.mean(xs), "std": st.pstdev(xs) if len(xs) > 1 else 0.0, "raw": xs}
    out = {"cells": {}, "endpoints": {}}
    for k, per in cells.items():
        out["cells"][k] = {"survival": m([r["survival"] for r in per]),
                           "acc": m([r["acc"] for r in per]),
                           "early_survival": m([r["early_survival"] for r in per]),
                           "acc_given_survived": m([r["acc_given_survived"] for r in per]),
                           "acc_given_evicted": m([r["acc_given_evicted"] for r in per])}
    for n_live in pressures:
        c = cells.get(f"C-oracle_L{n_live}"); d = cells.get(f"D-v2_L{n_live}")
        if c and d:
            # paired per-seed differences
            dsurv = [dd["survival"] - cc["survival"] for cc, dd in zip(c, d)]
            dacc = [dd["acc"] - cc["acc"] for cc, dd in zip(c, d)]
            dearly = [dd["early_survival"] - cc["early_survival"] for cc, dd in zip(c, d)]
            out["endpoints"][f"L{n_live}"] = {
                "D-v2_minus_C_survival": m(dsurv),
                "D-v2_minus_C_acc": m(dacc),
                "D-v2_minus_C_early_survival": m(dearly)}
    return out


def write_tables(agg, pressures):
    L = ["# Phase-v2 oracle-retention — tables", ""]
    for n_live in pressures:
        L += [f"## Pressure n_live={n_live} (M=8)",
              "| arm | survival | early_surv | acc | acc|surv | acc|evict |",
              "|---|---:|---:|---:|---:|---:|"]
        for arm in ARMS:
            c = agg["cells"].get(f"{arm}_L{n_live}")
            if c:
                L.append(f"| {arm} | {c['survival']['mean']:.3f} | {c['early_survival']['mean']:.3f} | "
                         f"{c['acc']['mean']:.3f} | {c['acc_given_survived']['mean']:.3f} | "
                         f"{c['acc_given_evicted']['mean']:.3f} |")
        ep = agg["endpoints"].get(f"L{n_live}", {})
        if ep:
            L += ["", f"**D-v2 − C:** survival {ep['D-v2_minus_C_survival']['mean']:+.3f} "
                  f"± {ep['D-v2_minus_C_survival']['std']:.3f}; early-survival "
                  f"{ep['D-v2_minus_C_early_survival']['mean']:+.3f}; acc "
                  f"{ep['D-v2_minus_C_acc']['mean']:+.3f}", ""]
    (HERE / "results" / "tables.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    run()
