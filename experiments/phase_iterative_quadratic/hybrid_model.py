"""
hybrid_model.py — iterative Phase-routed bounded-softmax hybrid (pilot: H hops of P→Q).

Per hop: route candidate events by the current query → bounded exact softmax over
(local window ∪ routed events) → update the query from the attention output. Static arms skip
the query update (one static routing set). The answer is decoded from the final query. Only the
routed-event selection uses Phase; Q/K/V/logits/identities are never touched by Phase.
"""
from __future__ import annotations

import math
import torch
import torch.nn as nn
from torch import Tensor

from experiments.phase_v3_selective_ssm.train import sinusoidal
from .config import EMBED_DIM, NUM_HEADS, W_WINDOW, K_ROUTED
from .bounded_attention import BoundedRoutedSoftmaxAttention
from .iterative_router import LearnedRouter
from .query_update import QueryUpdate
from .hybrid_blocks import PhaseFeature


class IterativeHybrid(nn.Module):
    def __init__(self, vocab_size, n_id, hops=2, router_kind="cond", use_phase=False,
                 iterative=True, routing_mode="learned", W=W_WINDOW, K=K_ROUTED,
                 embed_dim=EMBED_DIM, num_heads=NUM_HEADS):
        super().__init__()
        self.hops, self.iterative, self.routing_mode = hops, iterative, routing_mode
        self.use_phase, self.W, self.K = use_phase, W, K
        self.embed_dim = embed_dim
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.router = LearnedRouter(embed_dim, router_kind)
        self.qblock = BoundedRoutedSoftmaxAttention(embed_dim, num_heads)
        self.qupdate = QueryUpdate(embed_dim)
        self.answer_head = nn.Linear(embed_dim, n_id)
        if use_phase:
            self.phase = PhaseFeature(embed_dim, num_heads)
        self.phase_zero = routing_mode == "phase_zero"
        self.phase_shuffle = routing_mode == "phase_shuffle"
        nn.init.normal_(self.token_embed.weight, std=0.02)

    def reps(self, ids):
        x = self.token_embed(ids) + sinusoidal(ids.shape[1], self.embed_dim, ids.device).unsqueeze(0)
        if self.use_phase:
            x = x + self.phase(x, zero=self.phase_zero, shuffle=self.phase_shuffle)
        return x

    def forward(self, ids, event_pos, probe_pos, valid_len, required_hops=None):
        """event_pos:[B,Ne] token positions of events; required_hops:[B,H] full-pos of the
        required event at each hop (for oracle routing + hop supervision); may be −1."""
        B, N = ids.shape
        reps = self.reps(ids)
        ar = torch.arange(B, device=ids.device)
        ev = reps.gather(1, event_pos.unsqueeze(-1).expand(B, event_pos.shape[1], self.embed_dim))
        q0 = reps[:, 0]                    # query CONTENT seeded from the focus (CUE at position 0)
        q = q0
        route_scores = []
        for h in range(self.hops):
            scores = self.router.score(q, ev)                          # [B,Ne]
            route_scores.append(scores)
            if self.routing_mode == "random":
                sel = torch.rand_like(scores)
            elif self.routing_mode == "oracle" and required_hops is not None:
                # score the h-th required event's slot high
                req = required_hops[:, h] if h < required_hops.shape[1] else torch.full((B,), -1, device=ids.device)
                sel = torch.zeros_like(scores)
                match = (event_pos == req.unsqueeze(1))
                sel = sel + match.float() * 10.0 + torch.rand_like(scores) * 0.01
            else:
                sel = scores
            if self.routing_mode == "local" or self.K == 0:
                routed_full = torch.full((B, 0), -1, dtype=torch.long, device=ids.device)
            else:
                topk = sel.topk(min(self.K, scores.shape[1]), dim=-1).indices    # [B,K] into events
                rk = event_pos.gather(1, topk)                         # KEY token positions
                routed_full = torch.cat([rk, rk + 1], dim=1)           # include each key's VALUE token
            o = self.qblock(q.unsqueeze(1), reps, probe_pos.unsqueeze(1), routed_full,
                            self.W, valid_len)[:, 0]
            if self.iterative:
                q = self.qupdate(q, o)
            else:
                q = self.qupdate(q0, o) if h == 0 else q               # static: single update from q0
        logits = self.answer_head(q)
        return {"answer_logits": logits, "route_scores": route_scores, "event_reps": ev}
