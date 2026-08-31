#!/usr/bin/env python3
"""E1F — the frozen E1 explicit-key dual encoder plus optional, minimal, query-conditioned residual
factors F1/F2/F3 for the T4 latest-state factorial.

BASE (never changed): shared embedding, key_head, query_head, learned null_key, cosine score / tau,
hard top-1 read. D = 64. No base capacity, depth, steps, lr, or temperature change.

Each factor adds only a SMALL side head producing a residual on the existing per-candidate scores. With
no factors enabled, E1F is byte-identical to the frozen `models.E1` (base params constructed first, in the
same order; factor params are appended and consume RNG only afterwards). Factor output gains are
zero-initialised so a fresh E1F starts identical to cell 000 and each factor must LEARN its effect.

Non-oracle contract (enforced structurally + proven in factor_leakage):
  * F1 (null gating): reads ONLY the query representation, the raw null score, and summary statistics of
    the existing real-candidate scores. Never the ground-truth match/answer, evaluator identity, correct
    entity, or correct position. It adds a correction to the NULL score only.
  * F2 (entity retrieval): a learned low-rank entity-matching residual between a query projection and a
    key projection (both from existing representations). Never uses evaluator entity labels, ground-truth
    entity restriction, correct position, or any external table. Applied to ALL real candidates.
  * F3 (temporal ranking): a query-conditioned gate ("does recency matter?") times a learned score of the
    candidate's own legitimate event-position token embedding. No hard-coded argmax-position, no correct
    entity filtering, no correct latest index, no answer value, no evaluator metadata. Applied to ALL real
    candidates.
"""
from __future__ import annotations

import pathlib
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F

E1_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1"
if str(E1_DIR) not in sys.path:
    sys.path.insert(0, str(E1_DIR))
from models import _masked_mean            # noqa: E402  (frozen masked-mean pooling)

import temporal_task as T                  # noqa: E402

D = 64                                     # frozen base dim (unchanged)
POS_SLOT = 3                               # key layout [E, E, EV, P]; the position token is slot 3
F1_HID = 8
F2_RANK = 8


class F1NullGate(nn.Module):
    """Minimal query-conditioned correction to the NULL score. Inputs: query repr + score summary stats
    (max/mean/logsumexp of real candidates, raw null). Output: a scalar added to the null candidate."""
    def __init__(self, d=D, hid=F1_HID):
        super().__init__()
        self.q_proj = nn.Linear(d, hid)
        self.stat_proj = nn.Linear(4, hid)
        self.out = nn.Linear(hid, 1)
        nn.init.zeros_(self.out.weight); nn.init.zeros_(self.out.bias)   # start as no-op

    def forward(self, q, real_scores, null_raw):
        mx = real_scores.max(dim=1).values
        mn = real_scores.mean(dim=1)
        lse = torch.logsumexp(real_scores, dim=1)
        stats = torch.stack([mx, mn, lse, null_raw], dim=1)              # [B,4]
        h = torch.tanh(self.q_proj(q) + self.stat_proj(stats))          # [B,hid]
        return self.out(h).squeeze(1)                                    # [B]


class F2EntityResidual(nn.Module):
    """Learned low-rank entity-matching residual added to each real candidate. entity_q from the query
    representation, entity_k from the key representation; residual = gain * cos(entity_q, entity_k)."""
    def __init__(self, d=D, rank=F2_RANK):
        super().__init__()
        self.q_ent = nn.Linear(d, rank)
        self.k_ent = nn.Linear(d, rank)
        self.gain = nn.Parameter(torch.zeros(1))                        # start as no-op

    def forward(self, q_repr, k_repr):
        eq = F.normalize(self.q_ent(q_repr), dim=-1).unsqueeze(1)       # [B,1,r]
        ek = F.normalize(self.k_ent(k_repr), dim=-1)                    # [B,K,r]
        return self.gain * (ek * eq).sum(-1)                            # [B,K]


class F3TemporalResidual(nn.Module):
    """Query-conditioned temporal-position residual added to each real candidate. gate(query) decides
    whether recency matters; pos_head scores the candidate's own event-position token embedding."""
    def __init__(self, d=D):
        super().__init__()
        self.gate = nn.Linear(d, 1)
        self.pos_head = nn.Linear(d, 1)
        self.gain = nn.Parameter(torch.zeros(1))                        # start as no-op

    def forward(self, q_repr, pos_emb):
        g = torch.sigmoid(self.gate(q_repr))                           # [B,1] in (0,1)
        ps = self.pos_head(pos_emb).squeeze(-1)                        # [B,K]
        return self.gain * g * ps                                      # [B,K]


class E1F(nn.Module):
    """Frozen E1 base + optional F1/F2/F3. `factors` is a subset of {"F1","F2","F3"}."""
    def __init__(self, d=D, vocab=T.VOCAB, factors=()):
        super().__init__()
        # ---- base (identical construction order to frozen models.E1) ----
        self.embed = nn.Embedding(vocab, d, padding_idx=T.PAD)
        self.key_head = nn.Linear(d, d)
        self.query_head = nn.Linear(d, d)
        self.null_key = nn.Parameter(torch.zeros(d))
        nn.init.normal_(self.null_key, std=0.02)
        # ---- factor side heads (constructed AFTER base so base init is unperturbed) ----
        self.factors = tuple(factors)
        self.f1 = F1NullGate(d) if "F1" in self.factors else None
        self.f2 = F2EntityResidual(d) if "F2" in self.factors else None
        self.f3 = F3TemporalResidual(d) if "F3" in self.factors else None

    # base encoders (unchanged)
    def _key_repr(self, key_tokens):
        return _masked_mean(self.embed(key_tokens), key_tokens)        # [B,K,d] (pre-head pooled)

    def encode_keys(self, key_tokens):
        return F.normalize(self.key_head(self._key_repr(key_tokens)), dim=-1)

    def _query_repr(self, query_tokens):
        return _masked_mean(self.embed(query_tokens), query_tokens)    # [B,d] (pre-head pooled)

    def encode_query(self, query_tokens):
        return F.normalize(self.query_head(self._query_repr(query_tokens)), dim=-1)

    def scores(self, key_tokens, query_tokens, tau):
        k = self.encode_keys(key_tokens)                               # [B,K,d]
        q = self.encode_query(query_tokens)                            # [B,d]
        nk = F.normalize(self.null_key, dim=-1).view(1, 1, -1).expand(k.size(0), 1, k.size(-1))
        allk = torch.cat([k, nk], dim=1)                               # [B,K+1,d], null = index K
        s = (allk * q.unsqueeze(1)).sum(-1) / tau                      # [B,K+1]
        K = k.size(1)
        real = s[:, :K]
        null = s[:, K]
        if not self.factors:
            return s                                                    # byte-identical to frozen E1
        q_repr = self._query_repr(query_tokens)                        # [B,d] pooled query (existing repr)
        # F2 / F3 residuals on real candidates (computed from existing reprs only)
        add = torch.zeros_like(real)
        if self.f2 is not None:
            add = add + self.f2(q_repr, self._key_repr(key_tokens))
        if self.f3 is not None:
            pos_emb = self.embed(key_tokens[:, :, POS_SLOT])           # [B,K,d] position-token embedding
            add = add + self.f3(q_repr, pos_emb)
        real = real + add
        # F1 correction on the null score, conditioned on the (post-F2/F3) real scores
        if self.f1 is not None:
            null = null + self.f1(q_repr, real, null)
        return torch.cat([real, null.unsqueeze(1)], dim=1)             # [B,K+1]

    def forward(self, key_tokens, query_tokens, tau):
        return self.scores(key_tokens, query_tokens, tau)

    # ---- reporting: added parameters per factor ----
    def factor_param_counts(self):
        def n(mod):
            return int(sum(p.numel() for p in mod.parameters())) if mod is not None else 0
        return {"F1": n(self.f1), "F2": n(self.f2), "F3": n(self.f3)}

    def base_param_count(self):
        base = [self.embed, self.key_head, self.query_head]
        return int(sum(p.numel() for m in base for p in m.parameters()) + self.null_key.numel())
