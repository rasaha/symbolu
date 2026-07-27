"""
query_update.py — derive q_(h+1) from the bounded-attention output o_h (§3 step 6).

The query must change after each hop: reading the hop-h link (whose value encodes the next
target) should move the query toward the next hop's key. Implemented as a gated residual update.
"""
from __future__ import annotations

import torch
import torch.nn as nn
from torch import Tensor


class QueryUpdate(nn.Module):
    def __init__(self, embed_dim):
        super().__init__()
        self.proj = nn.Linear(2 * embed_dim, embed_dim)
        self.gate = nn.Linear(2 * embed_dim, embed_dim)
        self.ln = nn.LayerNorm(embed_dim)

    def forward(self, q: Tensor, o: Tensor) -> Tensor:
        z = torch.cat([q, o], dim=-1)
        g = torch.sigmoid(self.gate(z))
        return self.ln(q + g * self.proj(z))
