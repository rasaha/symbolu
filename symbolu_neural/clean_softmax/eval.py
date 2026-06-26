"""Evaluate a saved checkpoint: val loss/ppl/ECE/entropy-corr + a generation sample.

    python -m symbolu_neural.clean_softmax.eval --corpus data/clean_lm/corpus.txt \
        --ckpt runs/clean/entropy_refine/ckpt.pt --sample
"""
from __future__ import annotations

import argparse

import torch

from .data import CharTokenizer, load_corpus, split_ids
from .model import SymbolUSoftmaxModel
from .metrics import val_loss_ppl, ece_and_entropy_corr, sample


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/clean_lm/corpus.txt")
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--block", type=int, default=128)
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--prompt", default="The ")
    args = ap.parse_args()

    ck = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    text = load_corpus(args.corpus)
    tok = CharTokenizer(text)
    # align tokenizer to the checkpoint's vocab mapping
    tok.stoi = ck["stoi"]; tok.itos = {i: c for c, i in tok.stoi.items()}
    tok.vocab_size = len(tok.stoi)
    ids = tok.encode(text); _, va = split_ids(ids, 0.1)

    model = SymbolUSoftmaxModel(ck["cfg"]); model.load_state_dict(ck["model"]); model.eval()
    fwd = lambda x: model(x)["logits"]
    m = val_loss_ppl(fwd, va, args.block, args.batch)
    m.update(ece_and_entropy_corr(fwd, va, args.block, args.batch))
    print(f"ablation={ck['ablation']}")
    for k, v in m.items():
        print(f"  {k}: {v}")
    if args.sample:
        print("sample:", repr(sample(fwd, tok, args.prompt, n=200, block=args.block)))


if __name__ == "__main__":
    main()
