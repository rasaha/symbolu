"""Shared quadratic reader and parameter-matched full models.

The reader is identical across arms: token projection -> 2 pre-norm transformer
encoder layers (d=64, 4 heads, GELU FFN) -> the query token's output embedding
-> forecast head (H values) + event logit. Total trainable parameters are
matched across arms to <1% by tuning the FFN width.
"""
from __future__ import annotations

import torch
import torch.nn as nn

from .collectors import ARMS
from .signals import H

D_MODEL = 64
N_HEADS = 4
N_LAYERS = 2
QUERY_FEAT = H + 1  # future time offsets + bias flag


class Block(nn.Module):
    def __init__(self, ffn: int):
        super().__init__()
        self.ln1 = nn.LayerNorm(D_MODEL)
        self.attn = nn.MultiheadAttention(D_MODEL, N_HEADS, batch_first=True)
        self.ln2 = nn.LayerNorm(D_MODEL)
        self.ffn = nn.Sequential(nn.Linear(D_MODEL, ffn), nn.GELU(),
                                 nn.Linear(ffn, D_MODEL))

    def forward(self, h, pad_mask):
        hn = self.ln1(h)
        a, _ = self.attn(hn, hn, hn, key_padding_mask=pad_mask, need_weights=False)
        h = h + a
        return h + self.ffn(self.ln2(h))


class ArmModel(nn.Module):
    def __init__(self, arm: str, ffn: int):
        super().__init__()
        self.arm = arm
        self.collector = ARMS[arm]()
        self.tok_proj = nn.Linear(self.collector.feat_dim, D_MODEL)
        self.query_proj = nn.Linear(QUERY_FEAT, D_MODEL)
        self.blocks = nn.ModuleList([Block(ffn) for _ in range(N_LAYERS)])
        self.ln_out = nn.LayerNorm(D_MODEL)
        self.forecast = nn.Linear(D_MODEL, H)
        self.event = nn.Linear(D_MODEL, 1)
        self.collector_learned = any(p.requires_grad for p in self.collector.parameters())

    def forward(self, x, dt, tau, future_off):
        """future_off: [B, C, H]. Returns forecast [B, C, H], event_logit [B, C]."""
        if self.collector_learned:
            out = self.collector(x, dt, tau)
        else:
            with torch.no_grad():
                out = self.collector(x, dt, tau)
        toks, pad = (out if isinstance(out, tuple) else (out, None))
        B, C, n_tok, _ = toks.shape
        h = self.tok_proj(toks.reshape(B * C, n_tok, -1))
        q_feat = torch.cat([future_off / 16.0,
                            torch.ones(B, C, 1, device=x.device)], dim=-1)
        q = self.query_proj(q_feat.reshape(B * C, 1, QUERY_FEAT))
        h = torch.cat([h, q], dim=1)
        if pad is not None:
            pad = torch.cat([pad.reshape(B * C, n_tok),
                             torch.zeros(B * C, 1, dtype=torch.bool, device=x.device)],
                            dim=1)
        for blk in self.blocks:
            h = blk(h, pad)
        z = self.ln_out(h[:, -1])
        return (self.forecast(z).view(B, C, H),
                self.event(z).view(B, C))

    def n_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def build_matched(arm: str, verbose: bool = False) -> ArmModel:
    """Match total params across arms to <1% by tuning FFN width.

    Target = params of the largest arm at base width; smaller arms widen the FFN.
    """
    base_ffn = 128
    target = max(ArmModel(a, base_ffn).n_params() for a in ARMS)
    lo, hi = base_ffn, 2048
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        m = ArmModel(arm, mid)
        n = m.n_params()
        if best is None or abs(n - target) < abs(best[1] - target):
            best = (mid, n)
        if n < target:
            lo = mid + 1
        else:
            hi = mid - 1
    ffn, n = best
    assert abs(n - target) / target < 0.01, (arm, n, target)
    model = ArmModel(arm, ffn)
    if verbose:
        print(f"arm={arm} ffn={ffn} params={n} target={target} "
              f"delta={(n - target) / target:+.4%}")
    return model
