"""Does Deferred-Insight memory have a STRUCTURAL advantage over a pointwise FFN
on a task that requires long-range cross-time aggregation?

The capacity study found memory ~ FFN on the LM task — but that backbone has full
causal attention, which already provides cross-time mixing, making the memory
redundant there. This experiment ISOLATES the modules: NO attention. Each mini-model
is  embedding -> [module] -> linear head. The only cross-time mechanism is the module
itself, so the task cleanly separates "can aggregate across time" from "cannot".

Task "running_majority": per-position binary label = 1 if (#ones so far >= #zeros so
far) else 0, over a stream of 0/1 (+filler). This needs the WHOLE prefix; a pointwise
FFN (no time mixing) must score ~chance; the memory's causal decayed prefix-mean is
structurally suited to it; an attention block can also do it (reference upper bound).

Run:  python -m symbolu_neural.clean_softmax.run_recall_study --steps 600
"""
from __future__ import annotations

import argparse

import torch
import torch.nn as nn
import torch.nn.functional as F

from .backbone import CausalBlock
from .controls import PointwiseMemoryControl
from .augment import CausalPrefixMemory


def make_batch(B, L, gen, p_token=0.5):
    """tokens in {0,1,2=filler}; label = running majority of 1s vs 0s (filler ignored)."""
    r = torch.rand(B, L, generator=gen)
    x = torch.where(r < p_token / 2, 0, torch.where(r < p_token, 1, 2))  # 0,1,filler
    ones = (x == 1).cumsum(1)
    zeros = (x == 0).cumsum(1)
    y = (ones >= zeros).long()
    return x, y


class MiniModel(nn.Module):
    """embedding -> module -> head. NO attention unless module == 'attn'."""

    def __init__(self, kind, d=64, vocab=3, n_classes=2):
        super().__init__()
        self.kind = kind
        self.emb = nn.Embedding(vocab, d)
        self.pos = nn.Embedding(512, d)
        if kind == "ffn":
            self.mod = PointwiseMemoryControl(d)           # pointwise, no time mixing
        elif kind == "memory":
            self.mod = CausalPrefixMemory(d)               # causal decayed prefix-mean
        elif kind == "attn":
            self.mod = CausalBlock(d, n_heads=4, d_ff=4 * d)  # reference upper bound
        else:
            self.mod = None
        self.head = nn.Linear(d, n_classes)

    def forward(self, x):
        L = x.shape[1]
        h = self.emb(x) + self.pos(torch.arange(L, device=x.device).unsqueeze(0))
        if self.kind == "memory":
            h, _ = self.mod(h, torch.zeros(x.shape[0], L, 3, device=x.device))
        elif self.kind in ("ffn", "attn"):
            h = self.mod(h)
        return self.head(h)


def run(kind, d, L, steps, lr, seed, device, eval_tail=0.5):
    torch.manual_seed(seed)
    g = torch.Generator().manual_seed(seed)
    m = MiniModel(kind, d).to(device)
    opt = torch.optim.AdamW(m.parameters(), lr=lr)
    m.train()
    for _ in range(steps):
        x, y = make_batch(32, L, g)
        x, y = x.to(device), y.to(device)
        loss = F.cross_entropy(m(x).reshape(-1, 2), y.reshape(-1))
        opt.zero_grad(); loss.backward(); opt.step()
    m.eval()
    with torch.no_grad():
        ge = torch.Generator().manual_seed(seed + 100)
        x, y = make_batch(256, L, ge)
        x, y = x.to(device), y.to(device)
        pred = m(x).argmax(-1)
        acc = (pred == y).float().mean().item()
        tail = int(L * (1 - eval_tail))
        acc_tail = (pred[:, tail:] == y[:, tail:]).float().mean().item()  # late positions
    return {"acc": acc, "acc_late": acc_tail, "params": sum(p.numel() for p in m.parameters())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--d", type=int, default=64)
    ap.add_argument("--seq", type=int, default=128)
    ap.add_argument("--steps", type=int, default=600)
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"task=running_majority  seq={args.seq}  d={args.d}  steps={args.steps}  device={device}")
    print(f"{'module':>10}{'acc':>9}{'acc_late':>10}{'params':>9}   note")
    notes = {"none": "no cross-time (embed+head only) -> chance",
             "ffn": "pointwise FFN control (NO time mixing) -> should be ~chance",
             "memory": "Deferred-Insight memory (decayed prefix-mean) -> cross-time",
             "attn": "1 attention block (reference upper bound)"}
    res = {}
    for kind in ("none", "ffn", "memory", "attn"):
        r = run(kind, args.d, args.seq, args.steps, args.lr, args.seed, device)
        res[kind] = r
        print(f"{kind:>10}{r['acc']:9.3f}{r['acc_late']:10.3f}{r['params']:9d}   {notes[kind]}")

    print("\n================ VERDICT ================")
    ffn, mem, attn = res["ffn"]["acc_late"], res["memory"]["acc_late"], res["attn"]["acc_late"]
    if mem > ffn + 0.05:
        print(f"Memory BEATS the pointwise FFN on cross-time aggregation "
              f"(late-pos acc {mem:.3f} vs {ffn:.3f}). The Deferred-Insight memory has a "
              f"genuine STRUCTURAL advantage a pointwise FFN cannot reproduce — confirming "
              f"the capacity-study tie was because the LM backbone's attention already "
              f"provided cross-time mixing (so memory was redundant there, not useless).")
    else:
        print(f"Memory does NOT beat the FFN here (late-pos {mem:.3f} vs {ffn:.3f}). Even on a "
              f"cross-time task the decayed prefix-mean is too low-capacity to help — a more "
              f"honest negative for the memory module.")
    print(f"(attention reference: {attn:.3f}; if attn >> memory, memory is a weak substitute "
          f"for attention.)")


if __name__ == "__main__":
    main()
