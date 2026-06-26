"""Generation smoke test for the clean-softmax Symbol-U model.

Loads a trained checkpoint and generates text autoregressively. This ONLY checks
that the model can load and emit tokens end-to-end. It is not a quality benchmark
and makes no claim of improvement over any baseline.

Example:
    # train a tiny checkpoint first (see README), then:
    python -m symbolu_neural.clean_softmax.generate \
        --ckpt runs/clean/full/ckpt.pt --prompt "The model " \
        --max-new-tokens 200 --temperature 0.8 --top-k 40 --seed 0
"""
from __future__ import annotations

import argparse

import torch
import torch.nn.functional as F

from .model import SymbolUSoftmaxModel
from .data import CharTokenizer


def _filter_logits(logits: torch.Tensor, top_k: int = 0, top_p: float = 0.0):
    """Apply top-k then top-p (nucleus) filtering to a [V] logits vector."""
    logits = logits.clone()
    if top_k and top_k < logits.numel():
        kth = torch.topk(logits, top_k).values[-1]
        logits[logits < kth] = float("-inf")
    if top_p and 0.0 < top_p < 1.0:
        s, idx = torch.sort(logits, descending=True)
        probs = s.softmax(-1).cumsum(-1)
        remove = probs > top_p
        remove[1:] = remove[:-1].clone()           # keep first token over the cutoff
        remove[0] = False
        logits[idx[remove]] = float("-inf")
    return logits


@torch.no_grad()
def generate(model, tok, prompt, max_new_tokens=200, temperature=0.8,
             top_k=0, top_p=0.0, seed=0):
    g = torch.Generator().manual_seed(seed)
    block = model.cfg.backbone.max_seq
    # encode prompt; if a char is OOV for this checkpoint, drop it
    ids = tok.encode(prompt).unsqueeze(0)
    if ids.numel() == 0:                            # empty/all-OOV prompt -> seed a token
        ids = torch.zeros(1, 1, dtype=torch.long)
    for _ in range(max_new_tokens):
        logits = model(ids[:, -block:])["logits"][0, -1]
        if temperature <= 0:                        # greedy
            nxt = logits.argmax().view(1, 1)
        else:
            logits = _filter_logits(logits / temperature, top_k, top_p)
            probs = logits.softmax(-1)
            nxt = torch.multinomial(probs, 1, generator=g).view(1, 1)
        ids = torch.cat([ids, nxt], dim=1)
    return tok.decode(ids[0].tolist())


def load_checkpoint(path: str):
    ck = torch.load(path, map_location="cpu", weights_only=False)
    tok = CharTokenizer.__new__(CharTokenizer)      # build tokenizer from saved vocab
    tok.stoi = ck["stoi"]
    tok.itos = {i: c for c, i in tok.stoi.items()}
    tok.vocab_size = len(tok.stoi)
    model = SymbolUSoftmaxModel(ck["cfg"])
    model.load_state_dict(ck["model"])
    model.eval()
    return model, tok, ck.get("ablation", "?")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--prompt", default="The ")
    ap.add_argument("--max-new-tokens", type=int, default=200)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--top-k", type=int, default=0)
    ap.add_argument("--top-p", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    model, tok, ablation = load_checkpoint(args.ckpt)
    out = generate(model, tok, args.prompt, args.max_new_tokens,
                   args.temperature, args.top_k, args.top_p, args.seed)
    gen_only = out[len(args.prompt):] if out.startswith(args.prompt) else out

    print("=" * 60)
    print(f"ablation     : {ablation}")
    print(f"checkpoint   : {args.ckpt}")
    print(f"settings     : max_new={args.max_new_tokens} temp={args.temperature} "
          f"top_k={args.top_k} top_p={args.top_p} seed={args.seed}")
    print("-" * 60)
    print(f"prompt       : {args.prompt!r}")
    print(f"generated    : {gen_only!r}")
    print("-" * 60)
    print("full text    :")
    print(out)
    print("=" * 60)
    print("NOTE: generation smoke test only — not a quality benchmark, no claim of "
          "improvement over any baseline.")


if __name__ == "__main__":
    main()
