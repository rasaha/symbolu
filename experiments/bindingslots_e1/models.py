#!/usr/bin/env python3
"""B0 (anonymous-slot memory) and E1 (explicit-key dual-encoder) for the capability probe.

Both consume identical episodes. B0 reads via soft content-addressed slots with NO explicit-key
supervision and NO abstention (the frozen anonymous-slot recipe on the shared task). E1 matches a query
encoder against per-episode key encoders by cosine, with a learned null key for abstention, and reads
the hard-top-1 key's value at inference (no soft value mixing).
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

import task as T

D = 64                  # embedding / model dim (frozen)


def _masked_mean(emb, tokens):
    """Mean over non-PAD tokens. emb [...,L,d], tokens [...,L] -> [...,d]."""
    mask = (tokens != T.PAD).float().unsqueeze(-1)
    s = (emb * mask).sum(-2)
    n = mask.sum(-2).clamp_min(1.0)
    return s / n


class E1(nn.Module):
    """Explicit-key dual encoder. Shared embedding table; separate key/query heads; cosine score;
    learned null key; hard top-1 value read at inference."""
    def __init__(self, d=D, vocab=T.VOCAB):
        super().__init__()
        self.embed = nn.Embedding(vocab, d, padding_idx=T.PAD)
        self.key_head = nn.Linear(d, d)
        self.query_head = nn.Linear(d, d)
        self.null_key = nn.Parameter(torch.zeros(d))
        nn.init.normal_(self.null_key, std=0.02)

    def encode_keys(self, key_tokens):        # [B,K,KLEN] -> [B,K,d] normalized
        e = self.embed(key_tokens)
        k = self.key_head(_masked_mean(e, key_tokens))
        return F.normalize(k, dim=-1)

    def encode_query(self, query_tokens):     # [B,QLEN] -> [B,d] normalized
        e = self.embed(query_tokens)
        q = self.query_head(_masked_mean(e, query_tokens))
        return F.normalize(q, dim=-1)

    def scores(self, key_tokens, query_tokens, tau):
        k = self.encode_keys(key_tokens)                       # [B,K,d]
        q = self.encode_query(query_tokens)                    # [B,d]
        nk = F.normalize(self.null_key, dim=-1).view(1, 1, -1)  # [1,1,d]
        nk = nk.expand(k.size(0), 1, k.size(-1))               # [B,1,d]
        allk = torch.cat([k, nk], dim=1)                       # [B,K+1,d]  (null = index K)
        return (allk * q.unsqueeze(1)).sum(-1) / tau           # [B,K+1]

    def forward(self, key_tokens, query_tokens, tau):
        return self.scores(key_tokens, query_tokens, tau)


class B0(nn.Module):
    """Anonymous content-addressed slot memory. Soft write + soft read over N slots; decode value.
    No explicit key, no address supervision, no abstention."""
    def __init__(self, d=D, vocab=T.VOCAB, n_slots=T.KEYS_PER_EPISODE, n_values=T.N_VALUES):
        super().__init__()
        self.embed = nn.Embedding(vocab, d, padding_idx=T.PAD)
        self.slot_keys = nn.Parameter(torch.zeros(n_slots, d))
        nn.init.normal_(self.slot_keys, std=0.02)
        self.value_write = nn.Linear(d, d)
        self.fact_proj = nn.Linear(d, d)
        self.query_proj = nn.Linear(d, d)
        self.value_decoder = nn.Linear(d, n_values)
        self.n_slots = n_slots

    def _write(self, key_tokens):
        e = self.embed(key_tokens)                       # [B,K,KLEN,d]
        fact = self.fact_proj(_masked_mean(e, key_tokens))   # [B,K,d]
        addr = torch.softmax(fact @ self.slot_keys.t(), dim=-1)   # [B,K,N] soft write address
        val = self.value_write(fact)                     # [B,K,d]
        # soft distributed write: M[b,n] = sum_k addr[b,k,n] * val[b,k]
        M = torch.einsum("bkn,bkd->bnd", addr, val)      # [B,N,d]
        return M

    def forward(self, key_tokens, query_tokens):
        M = self._write(key_tokens)                      # [B,N,d]
        e = self.embed(query_tokens)
        q = self.query_proj(_masked_mean(e, query_tokens))   # [B,d]
        raddr = torch.softmax(q @ self.slot_keys.t(), dim=-1)    # [B,N] soft read address
        u = torch.einsum("bn,bnd->bd", raddr, M)         # [B,d]
        return self.value_decoder(u)                     # [B, n_values]
