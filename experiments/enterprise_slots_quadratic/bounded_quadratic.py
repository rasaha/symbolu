"""
bounded_quadratic.py — bounded reasoning over the working set (slots or fresh packet).

Two variants, both bounded by the working-set size K — NEVER over the full N-event workflow, never
an N×N tensor:
    QueryToSlot        — the query attends the ≤K working-set records once.  O(K·d)
    SlotSelfAttention  — the ≤K records self-attend (contradiction/version/chain comparison) then
                          the query reads out.  O(K²·d)
"""
from __future__ import annotations

import torch
import torch.nn as nn


class QueryToSlot(nn.Module):
    def __init__(self, D, heads):
        super().__init__()
        self.attn = nn.MultiheadAttention(D, heads, batch_first=True, dropout=0.0)

    def forward(self, query, ws, mask):
        # query:[B,1,D]; ws:[B,K,D]; mask:[B,K] (True=valid)
        kpm = ~mask
        kpm = kpm.masked_fill(mask.sum(-1, keepdim=True) == 0, False)   # avoid all-masked NaN
        o, _ = self.attn(query, ws, ws, key_padding_mask=kpm)
        return o[:, 0]                                                  # [B,D]


class SlotSelfAttention(nn.Module):
    def __init__(self, D, heads):
        super().__init__()
        self.layer = nn.TransformerEncoderLayer(D, heads, dim_feedforward=2 * D,
                                                batch_first=True, dropout=0.0)
        self.q2s = QueryToSlot(D, heads)

    def forward(self, query, ws, mask):
        B, K, D = ws.shape
        tokens = torch.cat([query, ws], dim=1)                         # [B,K+1,D]
        pad = torch.cat([torch.zeros(B, 1, dtype=torch.bool, device=ws.device), ~mask], dim=1)
        pad = pad.masked_fill(pad.all(-1, keepdim=True), False)
        h = self.layer(tokens, src_key_padding_mask=pad)               # bounded K+1 self-attention
        return h[:, 0]                                                 # query slot readout
