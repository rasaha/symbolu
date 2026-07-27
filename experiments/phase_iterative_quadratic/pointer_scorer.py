"""
pointer_scorer.py — explicit candidate-conditioned next-hop pointer scorers (authorized repair).

Sole job: rank the correct next evidence event first among the runtime candidate set (not a fixed
global 32-class head). For hop output `o` and each candidate event e_i, score using EXPLICIT
structured features derived from the tokens already in context:

    query side (from o + hop): what the current hop read = the next entity/relation to find
    candidate side: key entity, key relation, value, source position, consumed status

Kinds:
    "bilinear" — relation-aware bilinear: q·(A·c) with c a learned combination of the candidate's
                 entity/relation/value/pos/consumed feature embeddings (relation enters explicitly).
    "mlp"      — candidate-conditioned MLP over [q, c, q⊙c, |q−c|] → scalar per candidate.

Scores are produced PER RUNTIME CANDIDATE, so the same module ranks whatever events are present;
identity ids only enter through learned feature embeddings, verified non-memorizing by the
identity-renaming control. Source position is included but is a controlled feature (events are
permuted; the shuffled-order control checks it is not a shortcut).
"""
from __future__ import annotations

import torch
import torch.nn as nn


class NextHopScorer(nn.Module):
    def __init__(self, D, n_ent, n_rel, n_id, kind="bilinear"):
        super().__init__()
        self.kind = kind
        self.ent_emb = nn.Embedding(n_ent, D)
        self.rel_emb = nn.Embedding(n_rel, D)
        self.val_emb = nn.Embedding(n_id, D)
        self.consumed_emb = nn.Embedding(2, D)
        self.hop_emb = nn.Embedding(8, D)
        self.pos_proj = nn.Linear(1, D)               # source position (controlled feature)
        self.q_proj = nn.Linear(D, D)                 # query from the hop output
        self.cand_proj = nn.Linear(5 * D, D)          # combine candidate structured features
        if kind == "bilinear":
            self.A = nn.Linear(D, D, bias=False)      # relation-aware bilinear form q^T A c
        elif kind == "mlp":
            self.mlp = nn.Sequential(nn.Linear(4 * D, D), nn.ReLU(), nn.Linear(D, 1))
        else:
            raise ValueError(kind)

    def candidate_features(self, o, feats, consumed, hop):
        """feats: dict entity/relation/value [B,Ne] long, pos [B,Ne] float(normalized).
        Returns q:[B,D], c:[B,Ne,D]."""
        B, Ne = feats["entity"].shape
        c = self.cand_proj(torch.cat([
            self.ent_emb(feats["entity"]),
            self.rel_emb(feats["relation"]),
            self.val_emb(feats["value"]),
            self.pos_proj(feats["pos"].unsqueeze(-1)),
            self.consumed_emb(consumed.long()),
        ], dim=-1))                                    # [B,Ne,D]
        hop_id = torch.full((B,), min(hop, 7), device=o.device, dtype=torch.long)
        q = self.q_proj(o) + self.hop_emb(hop_id)      # [B,D]
        return q, c

    def forward(self, o, feats, consumed, hop):
        q, c = self.candidate_features(o, feats, consumed, hop)
        if self.kind == "bilinear":
            return torch.einsum("bd,bnd->bn", self.A(q), c)          # [B,Ne]
        qx = q.unsqueeze(1).expand_as(c)
        h = torch.cat([qx, c, qx * c, (qx - c).abs()], dim=-1)       # [B,Ne,4D]
        return self.mlp(h).squeeze(-1)                               # [B,Ne]
