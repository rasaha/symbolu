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
                 embed_dim=EMBED_DIM, num_heads=NUM_HEADS, gt_query=False):
        super().__init__()
        self.hops, self.iterative, self.routing_mode = hops, iterative, routing_mode
        self.use_phase, self.W, self.K = use_phase, W, K
        self.gt_query = gt_query        # D0: feed the ground-truth intermediate query (diagnostic)
        self.embed_dim = embed_dim
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.router = LearnedRouter(embed_dim, router_kind)
        self.qblock = BoundedRoutedSoftmaxAttention(embed_dim, num_heads)
        self.qupdate = QueryUpdate(embed_dim)
        self.val_bind = nn.Linear(embed_dim, embed_dim)     # local key↔value binding (minimal P mixing)
        self.answer_head = nn.Linear(2 * embed_dim, n_id)   # decode from [final query ; last attn output]
        self.hop_head = nn.Linear(embed_dim, n_id)          # per-hop target head (staged supervision §13)
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

    def forward(self, ids, event_pos, probe_pos, valid_len, required_hops=None, req_evidx=None,
                freeze_query=False, shuffle_query=False, shuffle_scores=False):
        """event_pos:[B,Ne] token positions of events; required_hops:[B,H] full-pos of the
        required event at each hop (for oracle routing + hop supervision); req_evidx:[B,H] indices
        into the event list (for D0 ground-truth intermediate query). May be −1."""
        B, N = ids.shape
        D = self.embed_dim
        reps = self.reps(ids)
        ar = torch.arange(B, device=ids.device)
        Ne = event_pos.shape[1]
        kp = event_pos.unsqueeze(-1).expand(B, Ne, D)
        key_x = reps.gather(1, kp)
        val_x = reps.gather(1, (event_pos + 1).unsqueeze(-1).expand(B, Ne, D))   # adjacent VALUE token
        ev = key_x + self.val_bind(val_x)                        # bind each key with its value
        reps = reps.scatter(1, kp, ev)                           # attention sees bound key reps
        q0 = reps[:, 0]                    # query CONTENT seeded from the focus (CUE at position 0)
        q = q0
        route_scores = []; hop_outputs = []; q_norms = []; queries = []
        for h in range(self.hops):
            # D0 diagnostic: overwrite the intermediate query with the ground-truth next entity
            if self.gt_query and h >= 1 and req_evidx is not None:
                gi = req_evidx[:, h].clamp(min=0).view(B, 1, 1).expand(B, 1, D)
                q = ev.gather(1, gi).squeeze(1)
            if shuffle_query and h >= 1:                               # control: scramble intermediate query
                q = q[torch.randperm(B, device=ids.device)]
            scores = self.router.score(q, ev)                          # [B,Ne]
            if shuffle_scores:                                         # control: scramble routing scores
                scores = scores[:, torch.randperm(scores.shape[1], device=ids.device)]
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
            hop_outputs.append(o)
            q_prev = q
            if freeze_query:                                          # control: never evolve the query
                q = q0
            elif self.iterative:
                q = self.qupdate(q, o)
            else:
                q = self.qupdate(q0, o) if h == 0 else q               # static: single update from q0
            q_norms.append((q - q_prev).norm(dim=-1).mean().item())    # §8 query-evolution diagnostic
            queries.append(q)                                          # updated query after hop h
        logits = self.answer_head(torch.cat([q, o], dim=-1))           # decode from query + last attn output
        hop_logits = [self.hop_head(oh) for oh in hop_outputs]         # per-hop target prediction (staged)
        return {"answer_logits": logits, "route_scores": route_scores, "event_reps": ev,
                "hop_logits": hop_logits, "query_update_norms": q_norms, "queries": queries}
