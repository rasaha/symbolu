#!/usr/bin/env python3
"""Frozen temporal-E1 encoder + four readouts (R0-R3) for the frozen-representation diagnostic.

The encoder (embeddings, key_head, query_head, null_key) is FROZEN — every base parameter has
requires_grad=False and no optimizer touches it. Only readout-head parameters are trained. Each readout
produces per-candidate scores [B,K+1] (null = index K) that flow through the EXISTING frozen candidate
scoring (frozen key_head -> cosine vs frozen query encoding / tau, frozen null key) and the existing hard
top-1 value read at evaluation.

R0  frozen mean pooling                     — the existing C1 read; no new parameters.
R1  learned single-attention readout        — one additive-attention head over frozen key-token embeddings,
                                              conditioned on the frozen pooled query summary.
R2  learned dual-head readout               — two independent attention heads; pooled outputs concatenated
                                              and projected back to d; heads must discover any separation.
R3  structural token-role readout (upper bd)— dual-head where each head attends over FIXED schema-level key
                                              slots only (entity slots {0,1} / temporal slots {2,3}); a
                                              structural prior, diagnostic-only, never selectable as primary.

No readout reads ground-truth entity, correct latest position, answer value, evaluator slot/metadata, an
external table, or a hard-coded max-position rule. Additive-attention form (R1):
    a_i = v^T tanh(W_token * token_i + W_query * query_summary + b);  softmax over legitimate key tokens.
"""
from __future__ import annotations

import pathlib
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F

TEMPORAL_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1_temporal"
E1_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1"
for p in (str(TEMPORAL_DIR), str(E1_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)
import temporal_task as T           # noqa: E402
from models import _masked_mean     # noqa: E402  (frozen pooling)

import readout_config as C          # noqa: E402

D = C.D
ENTITY_SLOTS = (0, 1)               # key layout [E, E, EV, P]
TEMPORAL_SLOTS = (2, 3)             # event-type + position


def freeze_encoder(enc):
    for p in enc.parameters():
        p.requires_grad_(False)
    enc.eval()
    return enc


class _AttnHead(nn.Module):
    """Additive attention over key-token embeddings, conditioned on the (frozen) pooled query summary.
    slot_mask (optional) restricts attention to fixed schema slots (structural prior; R3 only)."""
    def __init__(self, d=D, hidden=32, slot_mask=None):
        super().__init__()
        self.W_token = nn.Linear(d, hidden, bias=False)
        self.W_query = nn.Linear(d, hidden, bias=True)
        self.v = nn.Linear(hidden, 1, bias=False)
        self.register_buffer("slot_mask", None if slot_mask is None
                             else torch.tensor(slot_mask, dtype=torch.bool), persistent=False)

    def forward(self, tok, q_summary, pad_mask):
        # tok [B,K,L,d]; q_summary [B,d]; pad_mask [B,K,L] True where valid
        B, K, L, d = tok.shape
        a = self.v(torch.tanh(self.W_token(tok) + self.W_query(q_summary).view(B, 1, 1, -1))).squeeze(-1)  # [B,K,L]
        valid = pad_mask
        if self.slot_mask is not None:
            valid = valid & self.slot_mask.view(1, 1, L)
        a = a.masked_fill(~valid, float("-inf"))
        alpha = torch.softmax(a, dim=-1)                       # [B,K,L]
        pooled = (alpha.unsqueeze(-1) * tok).sum(dim=2)        # [B,K,d]
        return pooled, alpha


class Readout(nn.Module):
    def __init__(self, enc, arm):
        super().__init__()
        self.enc = freeze_encoder(enc)          # frozen base
        self.arm = arm
        d = D
        if arm == "R0":
            pass
        elif arm == "R1":
            self.head = _AttnHead(d, C.R1_HIDDEN)
        elif arm == "R2":
            self.head_a = _AttnHead(d, C.R2_HIDDEN)
            self.head_b = _AttnHead(d, C.R2_HIDDEN)
            self.proj = nn.Linear(2 * d, d)
        elif arm == "R3":
            self.head_a = _AttnHead(d, C.R3_HIDDEN, slot_mask=[i in ENTITY_SLOTS for i in range(T.KLEN)])
            self.head_b = _AttnHead(d, C.R3_HIDDEN, slot_mask=[i in TEMPORAL_SLOTS for i in range(T.KLEN)])
            self.proj = nn.Linear(2 * d, d)
        else:
            raise ValueError(arm)

    # ---- frozen pieces ----
    def _q_summary(self, qt):
        return _masked_mean(self.enc.embed(qt), qt)             # [B,d] frozen pooled query

    def _key_tokens_emb(self, kt):
        return self.enc.embed(kt)                               # [B,K,KLEN,d] frozen token embeddings

    def _score_from_pooled(self, pooled_k, qt):
        k = F.normalize(self.enc.key_head(pooled_k), dim=-1)    # [B,K,d]
        q = self.enc.encode_query(qt)                          # [B,d] frozen
        nk = F.normalize(self.enc.null_key, dim=-1).view(1, 1, -1).expand(k.size(0), 1, k.size(-1))
        allk = torch.cat([k, nk], dim=1)                       # [B,K+1,d]
        return (allk * q.unsqueeze(1)).sum(-1) / C.TAU         # [B,K+1]

    def _pooled_keys(self, kt):
        tok = self._key_tokens_emb(kt)                         # [B,K,L,d]
        pad = (kt != T.PAD)                                    # [B,K,L]
        qs = self._q_summary_cache
        if self.arm == "R0":
            return _masked_mean(tok, kt)                       # frozen mean pooling
        if self.arm == "R1":
            pooled, _ = self.head(tok, qs, pad)
            return pooled
        # R2 / R3 dual-head
        pa, _ = self.head_a(tok, qs, pad)
        pb, _ = self.head_b(tok, qs, pad)
        return self.proj(torch.cat([pa, pb], dim=-1))

    def scores(self, key_tokens, query_tokens, tau=None):
        self._q_summary_cache = self._q_summary(query_tokens)
        pooled_k = self._pooled_keys(key_tokens)
        return self._score_from_pooled(pooled_k, query_tokens)

    def forward(self, key_tokens, query_tokens, tau=None):
        return self.scores(key_tokens, query_tokens)

    # ---- accounting ----
    def readout_named_parameters(self):
        return [(n, p) for n, p in self.named_parameters() if not n.startswith("enc.")]

    def added_params(self):
        return int(sum(p.numel() for _, p in self.readout_named_parameters()))

    def head_param_breakdown(self):
        out = {}
        for n, p in self.readout_named_parameters():
            top = n.split(".")[0]
            out[top] = out.get(top, 0) + int(p.numel())
        return out


def build_frozen_encoder(verify=True):
    """Reconstruct the merged temporal E1 checkpoint (seed 6140) and freeze it."""
    import temporal_train as TR
    import temporal_config as TCcfg
    eps = TCcfg.build_train_episodes()
    enc = TR.train_e1(eps, C.FROZEN_ENCODER_SEED)
    if verify:
        import json
        committed = {s["seed"]: s["e1_param_sha256"]
                     for s in json.loads((TEMPORAL_DIR / "results" / "per_seed.json").read_text())["per_seed"]}
        h = TR.param_hash(enc)
        assert h == committed[C.FROZEN_ENCODER_SEED], "frozen encoder hash != committed temporal evidence"
    return freeze_encoder(enc)
