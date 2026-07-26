"""
run_study.py — orchestrate the A/B/C/C-no-Phase natural-language study.

Trains each arm per seed, evaluates at multiple context lengths (incl. one beyond
the training length), runs Phase and slot ablations, and measures resources. Raw
per-(seed, arm) results are written immediately to results/raw/ so partial
progress is never lost. Aggregation happens at the end.

Usage:
    python -m experiments.lightweight_phase_natural_language.run_study
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import torch

from .datasets import build_tokenizer, generate_split, dataset_manifest
from .models import ModelConfig, build_model, ARMS
from .train import TrainConfig, train_model
from .evaluate import evaluate
from .ablations import phase_ablations, slot_ablations
from .resources import full_resource_report
from .analyze import aggregate, render_tables

HERE = Path(__file__).resolve().parent
RAW = HERE / "results" / "raw"

# --- study configuration (micro-scale, CPU) --------------------------------
STUDY = dict(
    embed_dim=96, num_heads=4, num_layers=2, local_window=16,
    num_slots=16, slot_top_k=4,
    tl_train=64, eval_lens=(48, 64, 96),   # 96 > tl_train (one length beyond training)
    per_task_train=120, per_task_test=30, per_task_val=8,
    steps=600, iso_steps=800, batch_size=16, lr=1e-3,
    seeds=(0, 1, 2),
)


def run():
    RAW.mkdir(parents=True, exist_ok=True)
    tok = build_tokenizer()
    cfg = ModelConfig(vocab_size=tok.vocab_size, embed_dim=STUDY["embed_dim"],
                      num_heads=STUDY["num_heads"], num_layers=STUDY["num_layers"],
                      local_window=STUDY["local_window"], num_slots=STUDY["num_slots"],
                      slot_top_k=STUDY["slot_top_k"], max_seq_len=max(STUDY["eval_lens"]) + 32)

    # dataset manifest
    (HERE / "DATASET_MANIFEST.json").write_text(json.dumps(
        {**dataset_manifest(tok, seed=0, per_task=STUDY["per_task_train"],
                            target_lens=list(STUDY["eval_lens"])),
         "tl_train": STUDY["tl_train"], "study": {k: v for k, v in STUDY.items()}},
        indent=2))

    t_start = time.time()
    for seed in STUDY["seeds"]:
        train_set = generate_split(tok, "train", seed, STUDY["per_task_train"], STUDY["tl_train"])
        val_set = generate_split(tok, "val", 500 + seed, STUDY["per_task_val"], STUDY["tl_train"])
        # pre-generate eval sets per length (fixed across arms for fairness)
        eval_sets = {L: generate_split(tok, "test", 1000 + seed, STUDY["per_task_test"], L)
                     for L in STUDY["eval_lens"]}
        for arm in ARMS:
            out_path = RAW / f"{arm}_seed{seed}.json"
            if out_path.exists():
                continue  # resume
            t0 = time.time()
            model = build_model(cfg, arm, seed)
            tr = train_model(model, train_set, tok, TrainConfig(
                steps=STUDY["steps"], batch_size=STUDY["batch_size"],
                lr=STUDY["lr"], seed=seed, eval_every=150), val=val_set)
            metrics_by_len = {}
            for L, es in eval_sets.items():
                metrics_by_len[str(L)] = evaluate(model, es, tok)
            # primary metrics at tl_train length for aggregation
            primary = metrics_by_len[str(STUDY["tl_train"])] if str(STUDY["tl_train"]) in metrics_by_len \
                else metrics_by_len[str(STUDY["eval_lens"][0])]
            rec = {
                "seed": seed, "arm": arm,
                "train_final": tr,
                "metrics": primary,
                "metrics_by_len": metrics_by_len,
                "train_seconds": round(time.time() - t0, 1),
            }
            out_path.write_text(json.dumps(rec, indent=2))
            print(f"[{time.time()-t_start:6.0f}s] {arm} seed{seed} done "
                  f"({rec['train_seconds']}s)  dist={primary['distant_fact']['accuracy']:.2f} "
                  f"bind={primary['entity_binding']['accuracy']:.2f}", flush=True)

    # isolated single-task transfer (clean Question A, no multitask interference)
    iso = {"task": "distant_fact", "steps": STUDY["iso_steps"], "rows": []}
    for seed in STUDY["seeds"]:
        tr_set = generate_split(tok, "train", seed, STUDY["per_task_train"] * 3,
                                STUDY["tl_train"], task_mix=["distant_fact"])
        te_set = generate_split(tok, "test", 1000 + seed, STUDY["per_task_test"] * 2,
                                STUDY["tl_train"], task_mix=["distant_fact"])
        iso_val = generate_split(tok, "val", 500 + seed, STUDY["per_task_val"] * 2,
                                 STUDY["tl_train"], task_mix=["distant_fact"])
        row = {"seed": seed}
        for arm in ("A", "B"):
            m = build_model(cfg, arm, seed)
            train_model(m, tr_set, tok, TrainConfig(steps=STUDY["iso_steps"],
                        batch_size=STUDY["batch_size"], lr=STUDY["lr"], seed=seed), val=iso_val)
            row[arm] = evaluate(m, te_set, tok)["distant_fact"]["accuracy"]
        iso["rows"].append(row)
        print(f"[iso] seed{seed} A={row['A']:.2f} B={row['B']:.2f}", flush=True)
    import statistics as _st
    iso["B_minus_A"] = _st.mean(r["B"] for r in iso["rows"]) - _st.mean(r["A"] for r in iso["rows"])
    (HERE / "results" / "isolated_transfer.json").write_text(json.dumps(iso, indent=2))

    # ablations (seed 0 only, primary length) --------------------------------
    seed = STUDY["seeds"][0]
    train_set = generate_split(tok, "train", seed, STUDY["per_task_train"], STUDY["tl_train"])
    val_set = generate_split(tok, "val", 500 + seed, STUDY["per_task_val"], STUDY["tl_train"])
    test_set = generate_split(tok, "test", 1000 + seed, STUDY["per_task_test"], STUDY["tl_train"])
    abl = {}
    for arm in ("B", "C"):
        m = build_model(cfg, arm, seed)
        train_model(m, train_set, tok, TrainConfig(steps=STUDY["steps"],
                    batch_size=STUDY["batch_size"], lr=STUDY["lr"], seed=seed), val=val_set)
        abl[f"phase_{arm}"] = phase_ablations(m, test_set, tok,
                                              ["distant_fact", "entity_binding", "source_attr"])
        if arm == "C":
            abl["slot_C"] = slot_ablations(m, test_set, tok,
                                           ["entity_binding", "source_attr", "supersession"])
    (HERE / "results" / "ablations.json").write_text(json.dumps(abl, indent=2))

    # resources --------------------------------------------------------------
    res = full_resource_report(cfg, seeds=(0,), seq_lens=list(STUDY["eval_lens"]))
    (HERE / "results" / "resources.json").write_text(json.dumps(res, indent=2))

    # aggregate --------------------------------------------------------------
    raw = [json.loads(p.read_text()) for p in sorted(RAW.glob("*.json"))]
    agg = aggregate(raw)
    agg["study"] = STUDY
    agg["total_seconds"] = round(time.time() - t_start, 1)
    (HERE / "results" / "aggregate.json").write_text(json.dumps(agg, indent=2))
    (HERE / "results" / "tables.md").write_text(render_tables(agg))
    print(f"DONE total {time.time()-t_start:.0f}s", flush=True)
    return agg


if __name__ == "__main__":
    run()
