"""
run_study.py — Phase-guided-slot study: A/C/D + ablations across slot pressure.

Decisive comparison D - C (Phase guidance value beyond ordinary slots) at each
pressure ratio, plus causal ablations (D-no-guid, D-random, D-write-only,
D-query-only). Writes raw per-(seed,arm,pressure) results immediately; aggregates
at the end. Reports write-F1 (Stage 1) and answer accuracy (Stage 2+).
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import torch

from .datasets_pressure import build_pressure_tokenizer, generate_pressure
from .guided_models import GCfg, build, ARMS
from .train_eval import TCfg, train, evaluate

HERE = Path(__file__).resolve().parent
RAW = HERE / "results" / "raw"

STUDY = dict(
    embed_dim=96, num_heads=4, local_window=16, num_slots=8, top_k=4,
    target_len=180,
    pressures={"1x": 8, "3x": 24},   # n_candidate facts (slots=8): no-pressure vs pressure
    n_train=400, n_val=60, n_test=100,
    steps=350, batch_size=16, lr=1e-3,
    arms=("A", "C", "D", "D-no-guid", "D-random"),   # decisive core set
    seeds=(0, 1, 2),
)


def run():
    RAW.mkdir(parents=True, exist_ok=True)
    tok = build_pressure_tokenizer()
    pad = tok.pad_id
    cfg = GCfg(vocab_size=tok.vocab_size, embed_dim=STUDY["embed_dim"],
               num_heads=STUDY["num_heads"], local_window=STUDY["local_window"],
               num_slots=STUDY["num_slots"], top_k=STUDY["top_k"],
               max_seq_len=STUDY["target_len"] * 3)
    t_start = time.time()
    for seed in STUDY["seeds"]:
        for pname, ncand in STUDY["pressures"].items():
            tr = generate_pressure(tok, "train", seed, STUDY["n_train"], ncand, STUDY["target_len"])
            va = generate_pressure(tok, "val", 500 + seed, STUDY["n_val"], ncand, STUDY["target_len"])
            te = generate_pressure(tok, "test", 1000 + seed, STUDY["n_test"], ncand, STUDY["target_len"])
            for arm in STUDY["arms"]:
                out_path = RAW / f"{arm}_p{pname}_s{seed}.json"
                if out_path.exists():
                    continue
                t0 = time.time()
                m = build(cfg, arm, seed)
                trlog = train(m, tr, pad, TCfg(steps=STUDY["steps"], batch_size=STUDY["batch_size"],
                              lr=STUDY["lr"], seed=seed, eval_every=100), val=va)
                metrics = evaluate(m, te, pad)
                rec = {"seed": seed, "arm": arm, "pressure": pname, "n_candidates": ncand,
                       "train": trlog, "metrics": metrics, "seconds": round(time.time() - t0, 1)}
                out_path.write_text(json.dumps(rec, indent=2))
                print(f"[{time.time()-t_start:6.0f}s] {arm:12s} p{pname} s{seed} "
                      f"ans={metrics['answer_acc']:.2f} wF1={metrics['write_f1']:.2f} "
                      f"({rec['seconds']}s)", flush=True)
    aggregate()
    print(f"DONE {time.time()-t_start:.0f}s", flush=True)


def aggregate():
    raw = [json.loads(p.read_text()) for p in sorted(RAW.glob("*.json"))]
    arms = sorted({r["arm"] for r in raw})
    pressures = sorted({r["pressure"] for r in raw})
    agg = {"arms": arms, "pressures": pressures, "cells": {}, "deltas": {}}
    def cell(arm, p, key):
        xs = [r["metrics"][key] for r in raw if r["arm"] == arm and r["pressure"] == p]
        if not xs:
            return None
        return {"mean": statistics.mean(xs), "std": statistics.pstdev(xs) if len(xs) > 1 else 0.0,
                "raw": xs}
    for arm in arms:
        agg["cells"][arm] = {}
        for p in pressures:
            agg["cells"][arm][p] = {k: cell(arm, p, k) for k in
                                    ("answer_acc", "write_f1", "write_precision", "write_recall")}
    # decisive deltas D - C and D - D-no-guid per pressure
    for p in pressures:
        def m(arm, key):
            c = agg["cells"].get(arm, {}).get(p, {}).get(key)
            return c["mean"] if c else float("nan")
        agg["deltas"][p] = {
            "D_minus_C_answer": m("D", "answer_acc") - m("C", "answer_acc"),
            "D_minus_C_writeF1": m("D", "write_f1") - m("C", "write_f1"),
            "D_minus_Dnoguid_answer": m("D", "answer_acc") - m("D-no-guid", "answer_acc"),
            "C_minus_A_answer": m("C", "answer_acc") - m("A", "answer_acc"),
        }
    (HERE / "results" / "aggregate.json").write_text(json.dumps(agg, indent=2))
    return agg


if __name__ == "__main__":
    run()
