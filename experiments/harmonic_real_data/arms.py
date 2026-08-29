"""Reader arms S / HS / SR / HR: shared quadratic transformer over summary
(+retrieval) tokens, parameter-matched to <1% via FFN width. Deterministic
baselines live in features.baseline_preds.
"""
from __future__ import annotations

import torch
import torch.nn as nn

from .features import FEAT, HARM_PERIODS, HORIZONS, N_RETRIEVAL_ANOM, STAT_GAMMAS

D_MODEL = 64
N_HEADS = 4
N_LAYERS = 2
QUERY_FEAT = 3

ARM_TOKENS = {
    "stats_reader": len(STAT_GAMMAS),
    "harmonic_reader": len(STAT_GAMMAS) + len(HARM_PERIODS),
    "stats_retrieval": len(STAT_GAMMAS) + 2 + N_RETRIEVAL_ANOM,
    "harmonic_retrieval": len(STAT_GAMMAS) + len(HARM_PERIODS) + 2 + N_RETRIEVAL_ANOM,
}
READER_ARMS = list(ARM_TOKENS)


class Block(nn.Module):
    def __init__(self, ffn: int):
        super().__init__()
        self.ln1 = nn.LayerNorm(D_MODEL)
        self.attn = nn.MultiheadAttention(D_MODEL, N_HEADS, batch_first=True)
        self.ln2 = nn.LayerNorm(D_MODEL)
        self.ffn = nn.Sequential(nn.Linear(D_MODEL, ffn), nn.GELU(),
                                 nn.Linear(ffn, D_MODEL))

    def forward(self, h):
        hn = self.ln1(h)
        a, _ = self.attn(hn, hn, hn, need_weights=False)
        h = h + a
        return h + self.ffn(self.ln2(h))


class Reader(nn.Module):
    def __init__(self, arm: str, ffn: int):
        super().__init__()
        self.arm = arm
        n_tok = ARM_TOKENS[arm]
        self.tok_proj = nn.Linear(FEAT, D_MODEL)
        self.slot_emb = nn.Parameter(torch.zeros(n_tok, D_MODEL))
        self.query_proj = nn.Linear(QUERY_FEAT, D_MODEL)
        self.blocks = nn.ModuleList([Block(ffn) for _ in range(N_LAYERS)])
        self.ln_out = nn.LayerNorm(D_MODEL)
        self.head = nn.Linear(D_MODEL, len(HORIZONS))

    def forward(self, tokens, query):
        """tokens [B, n_tok, FEAT]; query [B, QUERY_FEAT] -> [B, 3]."""
        h = self.tok_proj(tokens) + self.slot_emb
        q = self.query_proj(query).unsqueeze(1)
        h = torch.cat([h, q], dim=1)
        for blk in self.blocks:
            h = blk(h)
        return self.head(self.ln_out(h[:, -1]))

    def n_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def build_matched(arm: str, verbose: bool = False) -> Reader:
    base = 128
    target = max(Reader(a, base).n_params() for a in READER_ARMS)
    lo, hi = base, 2048
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        n = Reader(arm, mid).n_params()
        if best is None or abs(n - target) < abs(best[1] - target):
            best = (mid, n)
        if n < target:
            lo = mid + 1
        else:
            hi = mid - 1
    ffn, n = best
    assert abs(n - target) / target < 0.01, (arm, n, target)
    model = Reader(arm, ffn)
    if verbose:
        print(f"arm={arm} ffn={ffn} params={n} target={target} "
              f"delta={(n - target) / target:+.4%}", flush=True)
    return model
