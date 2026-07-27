"""
run_pointer_probe.py — is the residual grounded-D1 gap capacity/budget or mechanism?

grounded_D1 (oracle route + structured pointer) reached 0.74 with acc|correct-pointer=0.93, so
the query-update mechanism works; the cap is pointer top-1 precision. Probe whether more budget /
smaller N lifts pointer top-1 (and thus D1) past 0.85.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import torch

from .multihop_dataset import build_vocab, generate
from .config import TrainCfg
from .hybrid_model import IterativeHybrid
from .train import train_hybrid
from .evaluate import evaluate
from .run_pointer_ladder import pointer_metrics

HERE = Path(__file__).resolve().parent


def _run(N, steps):
    vocab = build_vocab(); nid = vocab.n_id
    torch.manual_seed(0)
    m = IterativeHybrid(vocab.size, nid, hops=2, routing_mode="oracle",
                        pointer_query=True, W=N, K=8)
    g = lambda bs, s: generate(vocab, N, 2, bs, s)
    train_hybrid(m, g, vocab, TrainCfg(seed=0, steps=steps))
    te = generate(vocab, N, 2, 300, 77000)
    acc = evaluate(m, te, vocab)["accuracy"]
    pm = pointer_metrics(m, te, vocab)
    return {"N": N, "steps": steps, "accuracy": acc, **pm}


def run():
    t0 = time.time(); res = []
    for N, steps in [(16, 3000), (32, 6000)]:
        r = _run(N, steps); res.append(r)
        print(f"N={N} steps={steps}: acc={r['accuracy']:.3f} ptr_top1={r['next_entity_top1']:.3f} "
              f"ptr_topk={r['next_entity_topk']:.3f} acc|cp={r['acc_given_correct_pointer']:.3f} "
              f"({time.time()-t0:.0f}s)", flush=True)
    (HERE / "results" / "pointer_probe.json").write_text(json.dumps(res, indent=2, default=float))
    print("POINTER_PROBE DONE", flush=True)
    return res


if __name__ == "__main__":
    run()
