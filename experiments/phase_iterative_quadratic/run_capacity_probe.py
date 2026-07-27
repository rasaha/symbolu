"""
run_capacity_probe.py — does more matcher capacity (embed_dim/heads) lift one-hop oracle and
grounded_D1 together at N=32? Diagnosis: residual grounded_D1 gap is next-event discrimination
capacity (acc|correct-pointer already 0.93-0.97). If so, dim 64->128 should raise BOTH the
one-hop retrieval ceiling and grounded_D1 past their gates, with the pointer mechanism unchanged.
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


def _train(vocab, nid, gen, steps, **kw):
    torch.manual_seed(0)
    m = IterativeHybrid(vocab.size, nid, **kw)
    train_hybrid(m, gen, vocab, TrainCfg(seed=0, steps=steps))
    return m


def run(N=32, steps=3000, dim=128, heads=8):
    vocab = build_vocab(); nid = vocab.n_id; t0 = time.time(); res = {"dim": dim, "heads": heads}
    # one-hop oracle ceiling at higher capacity
    g1 = lambda bs, s: generate(vocab, N, 1, bs, s); te1 = generate(vocab, N, 1, 300, 77000)
    m1 = _train(vocab, nid, g1, steps, hops=1, routing_mode="oracle", W=N, K=8,
                embed_dim=dim, num_heads=heads)
    res["one_hop_oracle"] = evaluate(m1, te1, vocab)["accuracy"]
    print(f"one_hop_oracle(dim={dim})={res['one_hop_oracle']:.3f} ({time.time()-t0:.0f}s)", flush=True)
    # grounded_D1 with structured pointer at higher capacity
    g2 = lambda bs, s: generate(vocab, N, 2, bs, s); te2 = generate(vocab, N, 2, 300, 77000)
    m2 = _train(vocab, nid, g2, steps, hops=2, routing_mode="oracle", pointer_query=True, W=N, K=8,
                embed_dim=dim, num_heads=heads)
    acc = evaluate(m2, te2, vocab)["accuracy"]; pm = pointer_metrics(m2, te2, vocab)
    res["grounded_D1"] = {"accuracy": acc, **pm}
    print(f"grounded_D1(dim={dim})={acc:.3f} ptr_top1={pm['next_entity_top1']:.3f} "
          f"acc|cp={pm['acc_given_correct_pointer']:.3f} ({time.time()-t0:.0f}s)", flush=True)
    res["gate"] = {"one_hop_oracle_ge_0.90": res["one_hop_oracle"] >= 0.90,
                   "grounded_D1_ge_0.85": acc >= 0.85}
    (HERE / "results" / "capacity_probe.json").write_text(json.dumps(res, indent=2, default=float))
    print("CAPACITY_PROBE DONE", flush=True)
    return res


if __name__ == "__main__":
    run()
