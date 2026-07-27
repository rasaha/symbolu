"""
run_study.py — Phase v2 signal-retention study.

Trains V1 / V2-S / V2-SD / V2-M under e2e and gate-supervised modes across seeds,
then evaluates focus decoding (Phase-only vs local vs controls), the distance ladder,
the dilution ladder, gate ablations, and a resource audit. Writes results/raw/*.json,
aggregate.json, tables.md.
"""
from __future__ import annotations

import json
import statistics as st
import time
from pathlib import Path

import torch

from experiments.phase_guided_slots_v2.task_schema import build_vocab
from .focus_data import generate_focus
from .train import TrainCfg, train_focus
from .focus_probe import probe_focus
from .distance_eval import run_distance
from .dilution_eval import run_dilution
from .ablations import run_ablations
from .resource_audit import run_audit

HERE = Path(__file__).resolve().parent
RAW = HERE / "results" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

VARIANTS = ("V1", "V2-S", "V2-SD", "V2-M")
MODES = ("e2e", "gate_sup")
SEEDS = (0, 1)
TRAIN_LEN = 256
TRAIN_DISTRACTORS = 24
STEPS = 250


def train_one(variant, mode, seed, vocab):
    def gen_fn():
        return generate_focus(vocab, "train", seed, 300, TRAIN_DISTRACTORS, TRAIN_LEN)
    cfg = TrainCfg(steps=STEPS, mode=mode, rho=0.10, seed=seed)
    m, _ = train_focus(variant, gen_fn, vocab.pad_id, cfg, vocab.size)
    return m


def run():
    vocab = build_vocab()
    t_start = time.time()
    cells = {}
    for variant in VARIANTS:
        for mode in MODES:
            if variant == "V1" and mode == "gate_sup":
                continue           # V1 has no gate
            key = f"{variant}/{mode}"
            per_seed = []
            for seed in SEEDS:
                m = train_one(variant, mode, seed, vocab)
                te = generate_focus(vocab, "test", 100 + seed, 200, TRAIN_DISTRACTORS, TRAIN_LEN)
                pr = probe_focus(m, te, vocab.pad_id, feature="g")
                prl = probe_focus(m, te, vocab.pad_id, feature="h")
                rec = {"seed": seed,
                       "phase_top1": pr["main"]["top1"], "phase_top3": pr["main"]["topk"],
                       "shuffled_top1": pr["shuffled"]["top1"], "random_top1": pr["random"]["top1"],
                       "local_top1": prl["main"]["top1"], "chance": pr["chance"],
                       "distance": run_distance(m, vocab, seed=200 + seed)}
                if variant in ("V2-S", "V2-M"):
                    rec["dilution"] = run_dilution(m, vocab, seed=300 + seed)
                    rec["ablations"] = run_ablations(m, vocab, seed=400 + seed)
                per_seed.append(rec)
                (RAW / f"{variant}_{mode}_s{seed}.json").write_text(json.dumps(rec, indent=2, default=float))
                print(f"[{key} s{seed}] phase_top1={rec['phase_top1']:.3f} "
                      f"local={rec['local_top1']:.3f} shuf={rec['shuffled_top1']:.3f} "
                      f"chance={rec['chance']:.3f} ({time.time()-t_start:.0f}s)", flush=True)
            cells[key] = {
                "phase_top1": _agg([r["phase_top1"] for r in per_seed]),
                "local_top1": _agg([r["local_top1"] for r in per_seed]),
                "shuffled_top1": _agg([r["shuffled_top1"] for r in per_seed]),
                "chance": per_seed[0]["chance"],
                "distance": {L: _agg([r["distance"][L]["phase_top1"] for r in per_seed])
                             for L in per_seed[0]["distance"]},
                "seeds": per_seed,
            }
    resources = run_audit()
    agg = {"cells": cells, "resources": resources,
           "v1_phase_baseline": cells.get("V1/e2e", {}).get("phase_top1")}
    (HERE / "results" / "aggregate.json").write_text(json.dumps(agg, indent=2, default=float))
    write_tables(agg)
    print(f"STUDY DONE {time.time()-t_start:.0f}s", flush=True)
    return agg


def _agg(xs):
    return {"mean": st.mean(xs), "std": st.pstdev(xs) if len(xs) > 1 else 0.0, "raw": xs}


def write_tables(agg):
    L = ["# Phase v2 signal-retention — tables", ""]
    v1 = agg["cells"].get("V1/e2e", {}).get("phase_top1", {}).get("mean", float("nan"))
    L.append("## Focus decoding at train length (256); chance ≈ 0.025")
    L.append("| variant/mode | phase_top1 | local_top1 | shuffled | Δ vs V1 |")
    L.append("|---|---:|---:|---:|---:|")
    for k, c in agg["cells"].items():
        p = c["phase_top1"]["mean"]
        L.append(f"| {k} | {p:.3f} | {c['local_top1']['mean']:.3f} | "
                 f"{c['shuffled_top1']['mean']:.3f} | {p - v1:+.3f} |")
    L += ["", "## Distance ladder — phase_top1 by context length"]
    dists = sorted({d for c in agg["cells"].values() for d in c["distance"]}, key=int)
    L.append("| variant/mode | " + " | ".join(dists) + " |")
    L.append("|---" * (len(dists) + 1) + "|")
    for k, c in agg["cells"].items():
        L.append(f"| {k} | " + " | ".join(f"{c['distance'][d]['mean']:.3f}" for d in dists) + " |")
    L += ["", "## Resource audit"]
    L.append("| variant | phase_params | state_bytes(B1) | banks | tokens/sec | no N×N |")
    L.append("|---|---:|---:|---:|---:|:--:|")
    for name, r in agg["resources"].items():
        L.append(f"| {name} | {r['phase_params']} | {r['state_bytes_per_batch1']} | "
                 f"{r['banks']} | {r['tokens_per_sec']:.0f} | {'yes' if r['no_NxN_tensor'] else 'no'} |")
    (HERE / "results" / "tables.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    run()
