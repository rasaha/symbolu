"""
train.py — per-target supervised training for the information-health heads.

One BCE head per Phase-plausible target (persistence / unresolved_recurrence / context_shift /
sequence_anomaly). Identical labels and examples across arms. No next-token / LM / Phase-routing /
answer-generation loss. Phase core stays frozen; only encoder, quadratic, adapters, temporal
baselines, and heads learn.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .dataset import (Schema, encode_categoricals, deterministic_quality_features,
                      deterministic_packet, CAT_FIELDS, TARGETS)


def collate(batch, schema: Schema, device="cpu"):
    B = len(batch); N = batch[0]["N"]; K = schema.packet_K
    cats = {f: torch.zeros(B, N, dtype=torch.long, device=device) for f in CAT_FIELDS}
    num = torch.zeros(B, N, 3, device=device)
    det = torch.zeros(B, 9, device=device)
    qp = torch.zeros(B, dtype=torch.long, device=device)
    packet = torch.zeros(B, K, dtype=torch.long, device=device)
    vl = torch.full((B,), N, dtype=torch.long, device=device)
    labels = {t: torch.zeros(B, device=device) for t in TARGETS}
    for i, ex in enumerate(batch):
        c, nnum = encode_categoricals(ex, schema, device)
        for f in CAT_FIELDS:
            cats[f][i] = c[f]
        num[i] = nnum
        det[i] = deterministic_quality_features(ex, schema, device)
        qp[i] = ex["query_pos"]
        pk = deterministic_packet(ex, schema)
        pk = pk + [ex["query_pos"]] * (K - len(pk))          # pad with query pos (dedup-safe)
        packet[i] = torch.tensor(pk[:K], device=device)
        for t in TARGETS:
            labels[t][i] = ex["labels"][t]
    return cats, num, det, qp, packet, vl, labels


def train_health(model, gen_fn, schema, steps=400, lr=2e-3, batch_size=16, seed=0, device="cpu"):
    opt = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=lr)
    model.train()
    for step in range(steps):
        batch = gen_fn(batch_size, seed * 100000 + step)
        cats, num, det, qp, packet, vl, labels = collate(batch, schema, device)
        logits, _ = model(cats, num, det, qp, packet, vl)
        loss = sum(F.binary_cross_entropy_with_logits(logits[t], labels[t]) for t in TARGETS)
        opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
        opt.step()
    model.eval()
    return {"final_loss": float(loss.item())}
