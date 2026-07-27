"""
baselines.py — matched non-Phase temporal aggregators over the full O(N) ordered stream.

Each maps an event-embedding stream [B,N,D] to a fixed temporal summary [B,T] read at the query
position, matching the Phase auxiliary dimension T and (approximately) its trainable-parameter
budget. These are the honest controls for "does Phase's specific recurrence beat a plain temporal
state?": mean pooling (no recurrence), EMA (fixed-decay recurrence), small GRU (learned recurrence).
None forms an N×N tensor.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class MeanPool(nn.Module):
    def __init__(self, D, T):
        super().__init__()
        self.proj = nn.Linear(D, T)

    def forward(self, x, query_pos, valid_len):
        B, N, D = x.shape
        mask = (torch.arange(N, device=x.device).unsqueeze(0) <= query_pos.unsqueeze(1)).float()
        pooled = (x * mask.unsqueeze(-1)).sum(1) / mask.sum(1, keepdim=True).clamp(min=1)
        return self.proj(pooled)


class EMA(nn.Module):
    """Exponential moving average with a learned per-dim decay; O(N) chunked prefix, no N×N."""
    def __init__(self, D, T):
        super().__init__()
        self.proj = nn.Linear(D, T)
        self.logit_decay = nn.Parameter(torch.zeros(D))          # sigmoid → decay in (0,1)

    def forward(self, x, query_pos, valid_len):
        B, N, D = x.shape
        g = torch.sigmoid(self.logit_decay)                      # [D]
        # e_t = g*e_{t-1} + (1-g)*x_t ; compute via decayed cumulative sum (bounded, O(N))
        idx = torch.arange(N, device=x.device).float()
        # weight of x_j at time t is (1-g)*g^(t-j); read at query_pos t=q per example
        q = query_pos.view(B, 1).float()
        expo = (q - idx.view(1, N)).clamp(min=-1e9)              # [B,N] (t-j); negatives = future
        valid = (idx.view(1, N) <= q).float()                    # causal mask
        # g^(t-j) per dim: [B,N,D]
        gpow = g.view(1, 1, D) ** expo.clamp(min=0).unsqueeze(-1)
        w = (1 - g).view(1, 1, D) * gpow * valid.unsqueeze(-1)
        e = (w * x).sum(1)                                        # [B,D]
        return self.proj(e)


class SmallGRU(nn.Module):
    """Single-layer GRU over the stream; temporal state read at the query position. O(N)."""
    def __init__(self, D, T):
        super().__init__()
        self.gru = nn.GRU(D, T, batch_first=True)

    def forward(self, x, query_pos, valid_len):
        B, N, D = x.shape
        out, _ = self.gru(x)                                     # [B,N,T]
        return out.gather(1, query_pos.view(B, 1, 1).expand(B, 1, out.shape[-1])).squeeze(1)


def make_temporal(kind, D, T):
    return {"mean": MeanPool, "ema": EMA, "gru": SmallGRU}[kind](D, T)
