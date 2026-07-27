"""
train.py — train a learned admission router (frozen Phase arch) via relevance ranking.

Matchers (cosine/bilinear) train with pairwise ranking on the match score (relevant events >
hard/ordinary distractors). token/COND train the gate with BCE (relevant→1, else→0). Training
uses a mix of candidate counts so the router generalizes across the capacity ladder. The Phase
recurrence is untouched; only the router's projections/gate are learned.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from . import capacity_dataset as CD
from .config import TrainCfg, DataCfg
from .routers import MODE

TRAIN_NS = (16, 32, 64)


def _labels(batch, device):
    """Per-event relevance label (1 relevant/required, 0 hard/ordinary/stale) at event positions."""
    return [[1.0 if (ev["category"] == "relevant" or ev["required"]) else 0.0 for ev in e["events"]]
            for e in batch]


def train_router(model, arm, vocab, cfg: TrainCfg, dcfg: DataCfg, device="cpu"):
    mode = MODE[arm]
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    model.train()
    rng = torch.Generator().manual_seed(cfg.seed + 1)
    for step in range(cfg.steps):
        N = TRAIN_NS[step % len(TRAIN_NS)]
        batch = CD.generate(vocab, dcfg, N, max(2, N // 8), cfg.batch_size, cfg.seed * 10000 + step)
        ids = CD.collate(batch, vocab.PAD, device)
        labels = _labels(batch, device)
        if mode in ("cosine", "bilinear"):
            s = model.match_score(ids)                                  # [B,N]
            loss = _rank_loss(s, batch, labels, cfg.margin)
        else:
            g = torch.sigmoid(model.gate_logit(ids)).mean(-1)           # [B,N]
            loss = _bce_loss(g, batch, labels)
        opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
    model.eval()
    return {"final_loss": float(loss.item())}


def _rank_loss(s, batch, labels, margin):
    losses = []
    for j, e in enumerate(batch):
        pos = [s[j, p] for k, p in enumerate(e["event_pos"]) if labels[j][k] > 0.5]
        neg = [s[j, p] for k, p in enumerate(e["event_pos"]) if labels[j][k] < 0.5]
        if pos and neg:
            pos = torch.stack(pos); neg = torch.stack(neg)
            losses.append(F.relu(margin - pos.unsqueeze(1) + neg.unsqueeze(0)).mean())
    return torch.stack(losses).mean() if losses else torch.zeros((), requires_grad=True)


def _bce_loss(g, batch, labels):
    vals, tgts = [], []
    for j, e in enumerate(batch):
        for k, p in enumerate(e["event_pos"]):
            vals.append(g[j, p]); tgts.append(labels[j][k])
    vals = torch.stack(vals).clamp(1e-4, 1 - 1e-4); tgts = torch.tensor(tgts, device=g.device)
    return F.binary_cross_entropy(vals, tgts)
