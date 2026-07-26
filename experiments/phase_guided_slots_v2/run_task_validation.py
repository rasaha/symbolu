"""
run_task_validation.py — Stage A: validate that the redesigned task creates genuine
bounded-memory pressure and that plain-slot C fails through real eviction.

Runs A (local only) and C (local + slots) across seeds at one or more pressure
configs, records the full memory-trace metrics + answer accuracy, runs shortcut
controls on C, and evaluates the validity gate. Phase arms (D) are NOT run here —
per the redesign rule, D may not be evaluated until Stage A PASSES.

Writes results/raw/<tag>.json and results/stageA_summary.json.
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

import torch

from experiments.phase_guided_slots_v2.task_validator import PCfg, train_arm, gate
from experiments.phase_guided_slots_v2.datasets_pressure_v2 import generate
from experiments.phase_guided_slots_v2.task_schema import build_vocab
from experiments.phase_guided_slots_v2.shortcut_checks import run_checks

HERE = Path(__file__).resolve().parent
RAW = HERE / "results" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

# candidate pressure configs (M, top_k, n_live). Pressure = n_live / M.
CONFIGS = [
    dict(M=8, top_k=2, n_live=16),   # 2x
    dict(M=8, top_k=2, n_live=32),   # 4x
    dict(M=8, top_k=2, n_live=64),   # 8x
]
SEEDS = (0, 1, 2)


def run(configs=None, seeds=SEEDS, steps=400):
    configs = configs or CONFIGS
    vocab = build_vocab()
    summary = {"configs": [], "seeds": list(seeds)}
    for c in configs:
        pc = PCfg(M=c["M"], top_k=c["top_k"], n_live=c["n_live"], steps=steps)
        cell = {"config": c, "pressure": pc.pressure, "seeds": {}}
        for seed in seeds:
            # A baseline (no slots) — sanity that memory is needed
            _, _, ameta, atag = train_arm("A", pc, seed)
            # C (the arm under test)
            cm, _, cmeta, ctag = train_arm("C", pc, seed)
            g = gate(cmeta)
            # shortcut controls on C (single seed pass over test set)
            te = generate(vocab, "test", 1000 + seed, 120, pc.n_live, pc.M)
            checks = run_checks(cm, te, vocab.pad_id)
            rec = {"A_acc": ameta["metrics"]["answer_acc"],
                   "C_acc": cmeta["metrics"]["answer_acc"],
                   "C_by_pos": cmeta["metrics"]["acc_by_target_position"],
                   "trace": cmeta["trace"], "gate": g, "shortcut": checks}
            (RAW / f"stageA_{ctag}.json").write_text(json.dumps(rec, indent=2, default=float))
            cell["seeds"][seed] = rec
            print(f"[{ctag}] pressure={pc.pressure:.0f}x  A={rec['A_acc']:.2f} C={rec['C_acc']:.2f} "
                  f"occ={g['capacity_saturation']:.2f} evict={g['evictions']:.1f} "
                  f"earlySurv={g['early_target_survival']:.2f} topkRec={g['topk_support_recall']:.2f} "
                  f"PASS={g['PASS']}", flush=True)
        # aggregate across seeds
        def agg(key_fn):
            xs = [key_fn(cell["seeds"][s]) for s in seeds if s in cell["seeds"]]
            return {"mean": st.mean(xs), "std": st.pstdev(xs) if len(xs) > 1 else 0.0, "raw": xs}
        cell["agg"] = {
            "C_acc": agg(lambda r: r["C_acc"]),
            "capacity_saturation": agg(lambda r: r["trace"]["capacity_saturation_rate"]),
            "evictions": agg(lambda r: r["trace"]["evictions"]),
            "target_survival": agg(lambda r: r["trace"]["target_survival_rate"]),
            "early_target_survival": agg(lambda r: r["trace"]["by_target_position"]["early"]["target_survival_rate"]),
            "topk_support_recall": agg(lambda r: r["trace"]["topk_support_recall"]),
            "merge_of_distinct_rate": agg(lambda r: r["trace"]["merge_of_distinct_rate"]),
        }
        cell["PASS_all_seeds"] = all(cell["seeds"][s]["gate"]["PASS"] for s in seeds if s in cell["seeds"])
        summary["configs"].append(cell)
    (HERE / "results" / "stageA_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    print("wrote results/stageA_summary.json")
    return summary


if __name__ == "__main__":
    run()
