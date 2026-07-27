"""
run_capacity_report.py — head-to-head capacity report for the structured-pointer grounded_D1 arm.

Two configurations, everything else identical (dataset, seed, N=32, candidate count, optimizer,
loss weights, evaluation examples):
    A: dim=64,  heads=4   (baseline)
    B: dim=128, heads=8   (2x width)

Per config reports: parameter count, training steps, training time, inference latency (per batch),
peak memory (tracemalloc), D0 accuracy, grounded_D1 accuracy, pointer top-1 / top-3, pointer
entropy, accuracy conditioned on correct pointer. This is the REPORTING pass for item 2 — not an
open-ended sweep. Run ONLY after the running capacity probe finishes.
"""
from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path

import torch

from .multihop_dataset import build_vocab, generate
from .config import TrainCfg
from .hybrid_model import IterativeHybrid
from .train import train_hybrid, collate_iter
from .evaluate import evaluate
from .run_pointer_ladder import pointer_metrics

HERE = Path(__file__).resolve().parent
N = 32
STEPS = 3000
SEED = 0


def _count_params(m):
    return int(sum(p.numel() for p in m.parameters()))


@torch.no_grad()
def _latency(m, te, vocab, reps=5):
    b = te[:64]
    ids, ep, pp, vl, ans, reqf, reqe, ht = collate_iter(b, vocab)
    m.eval()
    m(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)          # warmup
    t = time.perf_counter()
    for _ in range(reps):
        m(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)
    return (time.perf_counter() - t) / reps                        # s / 64-example batch


def _config(vocab, nid, dim, heads, g2, te2, d0=False):
    torch.manual_seed(SEED)
    kw = dict(hops=2, routing_mode="oracle", W=N, K=8, embed_dim=dim, num_heads=heads)
    if d0:
        kw["gt_query"] = True
    else:
        kw["pointer_query"] = True
    tracemalloc.start()
    m = IterativeHybrid(vocab.size, nid, **kw)
    params = _count_params(m)
    t0 = time.time()
    train_hybrid(m, g2, vocab, TrainCfg(seed=SEED, steps=STEPS))
    train_time = time.time() - t0
    _cur, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    acc = evaluate(m, te2, vocab)["accuracy"]
    out = {"dim": dim, "heads": heads, "params": params, "steps": STEPS,
           "train_time_s": round(train_time, 1), "peak_mem_mb": round(peak / 1e6, 1),
           "accuracy": acc}
    if not d0:
        out["latency_s_per_64"] = round(_latency(m, te2, vocab), 4)
        out.update(pointer_metrics(m, te2, vocab))
    return out


def run():
    vocab = build_vocab(); nid = vocab.n_id
    g2 = lambda bs, s: generate(vocab, N, 2, bs, s)
    te2 = generate(vocab, N, 2, 300, 77000)      # identical eval set for both configs
    res = {"N": N, "seed": SEED, "eval_n": len(te2), "configs": {}}
    for tag, dim, heads in [("dim64_h4", 64, 4), ("dim128_h8", 128, 8)]:
        d0 = _config(vocab, nid, dim, heads, g2, te2, d0=True)["accuracy"]
        c = _config(vocab, nid, dim, heads, g2, te2, d0=False)
        c["D0"] = d0
        res["configs"][tag] = c
        print(f"{tag}: params={c['params']} D0={d0:.3f} gD1={c['accuracy']:.3f} "
              f"ptr1={c['next_entity_top1']:.3f} ptr3={c['next_entity_topk']:.3f} "
              f"ent={c['pointer_entropy']:.3f} acc|cp={c['acc_given_correct_pointer']:.3f} "
              f"lat={c['latency_s_per_64']}s mem={c['peak_mem_mb']}MB t={c['train_time_s']}s",
              flush=True)
    a, b = res["configs"]["dim64_h4"], res["configs"]["dim128_h8"]
    res["comparison"] = {
        "grounded_D1_gain": round(b["accuracy"] - a["accuracy"], 3),
        "param_ratio": round(b["params"] / a["params"], 2),
        "latency_ratio": round(b["latency_s_per_64"] / a["latency_s_per_64"], 2),
        "mem_ratio": round(b["peak_mem_mb"] / max(1e-9, a["peak_mem_mb"]), 2),
        "grounded_D1_ge_0.85": b["accuracy"] >= 0.85 or a["accuracy"] >= 0.85,
        "capacity_justified": (b["accuracy"] - a["accuracy"]) >= 0.10,
    }
    (HERE / "results" / "capacity_report.json").write_text(json.dumps(res, indent=2, default=float))
    print("CAPACITY_REPORT:", json.dumps(res["comparison"], default=float), flush=True)
    print("CAPACITY_REPORT DONE", flush=True)
    return res


if __name__ == "__main__":
    run()
