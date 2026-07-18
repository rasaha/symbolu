"""Train a single ablation and save a checkpoint.

    python -m symbolu_neural.clean_softmax.train --corpus data/clean_lm/corpus.txt \
        --ablation entropy_refine --steps 300 --out runs/clean/entropy_refine
"""
from __future__ import annotations

import argparse
import json
import os

import torch

from .config import get_ablation
from .data import CharTokenizer, load_corpus, split_ids
from .trainer import train_and_eval


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/clean_lm/corpus.txt")
    ap.add_argument("--ablation", default="baseline")
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--block", type=int, default=128)
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--d-model", type=int, default=128)
    ap.add_argument("--layers", type=int, default=2)
    ap.add_argument("--heads", type=int, default=4)
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="runs/clean/run")
    args = ap.parse_args()

    text = load_corpus(args.corpus)
    tok = CharTokenizer(text)
    ids = tok.encode(text)
    tr, va = split_ids(ids, 0.1)

    cfg = get_ablation(args.ablation)
    cfg.backbone.vocab_size = tok.vocab_size
    cfg.backbone.d_model = args.d_model
    cfg.backbone.n_layers = args.layers
    cfg.backbone.n_heads = args.heads
    cfg.backbone.max_seq = args.block

    m, model = train_and_eval(cfg, tr, va, args.block, args.batch, args.steps,
                              args.lr, args.seed, log_every=max(1, args.steps // 5))
    print(f"[{args.ablation}] " + " ".join(f"{k}={v}" for k, v in m.items()))

    os.makedirs(args.out, exist_ok=True)
    torch.save({"model": model.state_dict(), "ablation": args.ablation,
                "cfg": cfg, "stoi": tok.stoi, "metrics": m},
               os.path.join(args.out, "ckpt.pt"))
    with open(os.path.join(args.out, "metrics.json"), "w") as f:
        json.dump(m, f, indent=2)
    print(f"saved -> {os.path.join(args.out, 'ckpt.pt')}")


if __name__ == "__main__":
    main()
