"""Shared quadratic reader and parameter-matched full models.

Summary arms (A-E, G): token projection -> 2 pre-norm transformer encoder
layers (d=64, 4 heads, GELU FFN) -> the query token's output embedding ->
forecast head (H values) + event logit, evaluated at arbitrary cutoff lists.

Arm F (raw_quad, Amendment 2): a CAUSAL transformer over raw tokens with
multi-frequency sinusoidal time features (the clock-bank periods 4->128) and a
per-position head taking [h_t ; future offsets] -> forecast + event logit,
supervised densely at every position during training.

Total trainable parameters are matched across all seven arms to <1% by tuning
the FFN width.
"""
from __future__ import annotations

import math

import torch
import torch.nn as nn

from .collectors import SUMMARY_ARMS
from .signals import CLOCK_PERIODS, H, T

D_MODEL = 64
N_HEADS = 4
N_LAYERS = 2
QUERY_FEAT = H + 1  # future time offsets + bias flag
RAW_LEN = 248       # positions 0..247 cover every supervised target index


class Block(nn.Module):
    def __init__(self, ffn: int):
        super().__init__()
        self.ln1 = nn.LayerNorm(D_MODEL)
        self.attn = nn.MultiheadAttention(D_MODEL, N_HEADS, batch_first=True)
        self.ln2 = nn.LayerNorm(D_MODEL)
        self.ffn = nn.Sequential(nn.Linear(D_MODEL, ffn), nn.GELU(),
                                 nn.Linear(ffn, D_MODEL))

    def forward(self, h, pad_mask=None, attn_mask=None):
        hn = self.ln1(h)
        a, _ = self.attn(hn, hn, hn, key_padding_mask=pad_mask,
                         attn_mask=attn_mask, need_weights=False)
        h = h + a
        return h + self.ffn(self.ln2(h))


class ArmModel(nn.Module):
    """Summary-collector arm: collector tokens + query token -> reader."""

    def __init__(self, arm: str, ffn: int):
        super().__init__()
        self.arm = arm
        self.collector = SUMMARY_ARMS[arm]()
        self.tok_proj = nn.Linear(self.collector.feat_dim, D_MODEL)
        self.query_proj = nn.Linear(QUERY_FEAT, D_MODEL)
        self.blocks = nn.ModuleList([Block(ffn) for _ in range(N_LAYERS)])
        self.ln_out = nn.LayerNorm(D_MODEL)
        self.forecast = nn.Linear(D_MODEL, H)
        self.event = nn.Linear(D_MODEL, 1)
        self.collector_learned = any(p.requires_grad for p in self.collector.parameters())

    def forward_at(self, x, dt, tau, future_off, cuts):
        """future_off: [B, C, H] for the given cutoff list. -> ([B,C,H], [B,C])."""
        if self.collector_learned:
            toks = self.collector(x, dt, tau, cuts)
        else:
            with torch.no_grad():
                toks = self.collector(x, dt, tau, cuts)
        B, C, n_tok, _ = toks.shape
        h = self.tok_proj(toks.reshape(B * C, n_tok, -1))
        q_feat = torch.cat([future_off / 16.0,
                            torch.ones(B, C, 1, device=x.device)], dim=-1)
        q = self.query_proj(q_feat.reshape(B * C, 1, QUERY_FEAT))
        h = torch.cat([h, q], dim=1)
        for blk in self.blocks:
            h = blk(h)
        z = self.ln_out(h[:, -1])
        return (self.forecast(z).view(B, C, H),
                self.event(z).view(B, C))

    def state_floats(self, tc: int) -> int:
        return self.collector.state_floats(tc)

    def n_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def _time_features(tau: torch.Tensor) -> torch.Tensor:
    """Multi-frequency sinusoidal features of tau at the clock-bank periods."""
    feats = [tau.unsqueeze(-1) / T]
    for P in CLOCK_PERIODS:
        ang = 2 * math.pi * tau / P
        feats.append(torch.cos(ang).unsqueeze(-1))
        feats.append(torch.sin(ang).unsqueeze(-1))
    return torch.cat(feats, dim=-1)  # [B, T, 1 + 2K]


class CausalRawModel(nn.Module):
    """Arm F: causal transformer over raw history (quadratic upper reference)."""
    RAW_FEAT = 2 + 1 + 2 * len(CLOCK_PERIODS)

    def __init__(self, ffn: int):
        super().__init__()
        self.arm = "raw_quad"
        self.in_proj = nn.Linear(self.RAW_FEAT, D_MODEL)
        self.blocks = nn.ModuleList([Block(ffn) for _ in range(N_LAYERS)])
        self.ln_out = nn.LayerNorm(D_MODEL)
        self.head = nn.Sequential(nn.Linear(D_MODEL + H, D_MODEL), nn.GELU(),
                                  nn.Linear(D_MODEL, H + 1))
        mask = torch.triu(torch.ones(RAW_LEN, RAW_LEN, dtype=torch.bool), diagonal=1)
        self.register_buffer("causal_mask", mask)

    def _encode(self, x, dt, tau):
        feats = torch.cat([torch.stack([x, dt], dim=-1)[:, :RAW_LEN],
                           _time_features(tau)[:, :RAW_LEN]], dim=-1)
        h = self.in_proj(feats)
        for blk in self.blocks:
            h = blk(h, attn_mask=self.causal_mask)
        return self.ln_out(h)  # [B, RAW_LEN, D]

    def _head(self, z, future_off):
        out = self.head(torch.cat([z, future_off / 16.0], dim=-1))
        return out[..., :H], out[..., H]

    def forward_at(self, x, dt, tau, future_off, cuts):
        """Same contract as ArmModel.forward_at (position t_c - 1 per cutoff)."""
        z = self._encode(x, dt, tau)
        idx = torch.tensor([tc - 1 for tc in cuts], device=x.device)
        return self._head(z.index_select(1, idx), future_off)

    def forward_dense(self, x, dt, tau, future_off_dense, positions):
        """Dense supervision: predictions at every position index in `positions`
        (last-observed indices). future_off_dense: [B, P, H]."""
        z = self._encode(x, dt, tau)
        idx = torch.tensor(positions, device=x.device)
        return self._head(z.index_select(1, idx), future_off_dense)

    def state_floats(self, tc: int) -> int:
        return tc * 2  # raw (x, dt) history carried to the reader

    def n_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def _make(arm: str, ffn: int):
    return CausalRawModel(ffn) if arm == "raw_quad" else ArmModel(arm, ffn)


def build_matched(arm: str, verbose: bool = False):
    """Match total params across all seven arms to <1% by tuning FFN width."""
    base_ffn = 128
    all_arms = list(SUMMARY_ARMS) + ["raw_quad"]
    target = max(_make(a, base_ffn).n_params() for a in all_arms)
    lo, hi = base_ffn, 2048
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        n = _make(arm, mid).n_params()
        if best is None or abs(n - target) < abs(best[1] - target):
            best = (mid, n)
        if n < target:
            lo = mid + 1
        else:
            hi = mid - 1
    ffn, n = best
    assert abs(n - target) / target < 0.01, (arm, n, target)
    model = _make(arm, ffn)
    if verbose:
        print(f"arm={arm} ffn={ffn} params={n} target={target} "
              f"delta={(n - target) / target:+.4%}")
    return model
