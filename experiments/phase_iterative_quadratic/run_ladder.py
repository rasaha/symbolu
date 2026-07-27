"""
run_ladder.py — §6 one-hop oracle + §10 diagnostic ladder (D0/D1/D2). Audit gate.

    one-hop oracle              : correct event routed → correct value decoded (≥0.90)
    D0 = oracle route + GT query : isolates attention/binding/decoder (≥0.95 required)
    D1 = oracle route + learned q: isolates the query update (≥0.85 required)
    D2 = learned iterative       : the full autonomous arm
Do not compare Phase vs COND until D1 passes.
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

HERE = Path(__file__).resolve().parent


def _train_eval(vocab, nid, gen, te, steps, **kw):
    torch.manual_seed(0)
    m = IterativeHybrid(vocab.size, nid, **kw)
    train_hybrid(m, gen, vocab, TrainCfg(seed=0, steps=steps))
    return m, evaluate(m, te, vocab)["accuracy"]


def run(N=32, steps=3000):
    vocab = build_vocab(); nid = vocab.n_id; t0 = time.time()
    res = {}
    # §6 one-hop oracle
    g1 = lambda bs, s: generate(vocab, N, 1, bs, s); te1 = generate(vocab, N, 1, 300, 77000)
    _, a = _train_eval(vocab, nid, g1, te1, steps, hops=1, routing_mode="oracle", W=N, K=8)
    res["one_hop_oracle"] = a; print(f"one-hop oracle: {a:.3f} ({time.time()-t0:.0f}s)", flush=True)
    # §10 ladder (2-hop)
    g2 = lambda bs, s: generate(vocab, N, 2, bs, s); te2 = generate(vocab, N, 2, 300, 77000)
    for name, kw in [("D0", dict(hops=2, routing_mode="oracle", gt_query=True, W=N, K=8)),
                     ("D1", dict(hops=2, routing_mode="oracle", W=N, K=8)),
                     ("D2", dict(hops=2, routing_mode="learned", router_kind="cond", W=N, K=8)),
                     ("static", dict(hops=1, routing_mode="learned", iterative=False, W=N, K=8))]:
        _, a = _train_eval(vocab, nid, g2, te2, steps, **kw)
        res[name] = a; print(f"{name}: {a:.3f} ({time.time()-t0:.0f}s)", flush=True)
    res["gate"] = {
        "one_hop_oracle_ge_0.90": res["one_hop_oracle"] >= 0.90,
        "D0_ge_0.95": res["D0"] >= 0.95, "D1_ge_0.85": res["D1"] >= 0.85,
        "ladder_pass": res["one_hop_oracle"] >= 0.90 and res["D0"] >= 0.95 and res["D1"] >= 0.85,
        "bottleneck": ("attention/binding/decoder" if res["D0"] < 0.95 else
                       "query_update" if res["D1"] < 0.85 else
                       "routing" if res["D2"] < 0.5 else "none"),
    }
    (HERE / "results" / "ladder.json").write_text(json.dumps(res, indent=2, default=float))
    print("LADDER:", json.dumps(res["gate"], indent=1, default=float), flush=True)
    print("LADDER DONE", flush=True)
    return res


if __name__ == "__main__":
    run()
