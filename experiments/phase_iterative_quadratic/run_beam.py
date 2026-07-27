"""
run_beam.py — bounded top-3 pointer beam vs hard/soft/oracle decoders (item 5).

Trains the grounded_D1 arm ONCE (dim=64, oracle route, structured pointer, N=32, seed 0) and
decodes the identical eval set four ways. The beam is the permitted next test after width/head
scaling failed to lift grounded_D1. Success = beam materially closes the gap to oracle_ptr.
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
from .beam_search import decode

HERE = Path(__file__).resolve().parent
N = 32


def run(steps=3000):
    vocab = build_vocab(); nid = vocab.n_id; t0 = time.time()
    torch.manual_seed(0)
    m = IterativeHybrid(vocab.size, nid, hops=2, routing_mode="oracle",
                        pointer_query=True, W=N, K=8)
    g = lambda bs, s: generate(vocab, N, 2, bs, s)
    train_hybrid(m, g, vocab, TrainCfg(seed=0, steps=steps))
    te = generate(vocab, N, 2, 300, 77000)
    res = {}
    for mode in ["soft", "hard_top1", "beam3", "oracle_ptr"]:
        res[mode] = decode(m, te, vocab, mode=mode)
        print(f"{mode}: {res[mode]:.3f} ({time.time()-t0:.0f}s)", flush=True)
    res["beam_gain_over_soft"] = round(res["beam3"] - res["soft"], 3)
    res["gap_to_oracle_closed"] = round((res["beam3"] - res["soft"]) /
                                        max(1e-9, res["oracle_ptr"] - res["soft"]), 3)
    res["grounded_D1_beam_ge_0.85"] = res["beam3"] >= 0.85
    (HERE / "results" / "beam.json").write_text(json.dumps(res, indent=2, default=float))
    print("BEAM:", json.dumps(res, default=float), flush=True)
    print("BEAM DONE", flush=True)
    return res


if __name__ == "__main__":
    run()
