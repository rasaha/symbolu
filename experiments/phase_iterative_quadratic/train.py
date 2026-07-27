"""
train.py — train the iterative hybrid (answer CE + per-hop routing ranking + query alignment).

Phase parameters stay frozen (PhaseFeature freezes its core). Only the router, bounded-attention
projections, query-update, and answer head are learned. Oracle/random/local/phase-zero/shuffle
arms are eval-time routing modes but are trained with the same objective under their mode.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from . import multihop_dataset as MD
from .config import TrainCfg


def collate_iter(batch, vocab, device="cpu"):
    ids = MD.collate(batch, vocab.PAD, device)
    B = len(batch); Ne = max(len(e["key_pos"]) for e in batch)
    event_pos = torch.zeros(B, Ne, dtype=torch.long)          # KEY token positions
    probe_pos = torch.zeros(B, dtype=torch.long)
    valid_len = torch.zeros(B, dtype=torch.long)
    answer = torch.zeros(B, dtype=torch.long)
    H = max(e["n_required"] for e in batch)
    req_full = torch.full((B, H), -1, dtype=torch.long)      # key token positions of required hops
    req_evidx = torch.full((B, H), -1, dtype=torch.long)     # indices into the event/key list
    for i, e in enumerate(batch):
        kp = e["key_pos"]; event_pos[i, :len(kp)] = torch.tensor(kp)
        probe_pos[i] = len(e["tokens"]) - 1
        valid_len[i] = len(e["tokens"]); answer[i] = e["answer"]
        for h, evidx in enumerate(e["req_evidx"]):
            req_evidx[i, h] = evidx
            req_full[i, h] = e["key_pos"][evidx]
    return (ids.to(device), event_pos.to(device), probe_pos.to(device), valid_len.to(device),
            answer.to(device), req_full.to(device), req_evidx.to(device))


def _route_loss(route_scores, req_evidx, margin):
    """Per hop, the required event's score must exceed the others by a margin."""
    losses = []
    for h, sc in enumerate(route_scores):                    # sc:[B,Ne]
        tgt = req_evidx[:, h] if h < req_evidx.shape[1] else torch.full((sc.shape[0],), -1, device=sc.device)
        for b in range(sc.shape[0]):
            if tgt[b] < 0:
                continue
            pos = sc[b, tgt[b]]
            neg = torch.cat([sc[b, :tgt[b]], sc[b, tgt[b] + 1:]])
            losses.append(F.relu(margin - pos + neg).mean())
    return torch.stack(losses).mean() if losses else torch.zeros((), device=route_scores[0].device)


def train_hybrid(model, gen_fn, vocab, cfg: TrainCfg, device="cpu"):
    opt = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=cfg.lr)
    model.train()
    rng = torch.Generator().manual_seed(cfg.seed + 1)
    for step in range(cfg.steps):
        data = gen_fn(cfg.batch_size, cfg.seed * 10000 + step)
        ids, ep, pp, vl, ans, reqf, reqe = collate_iter(data, vocab, device)
        out = model(ids, ep, pp, vl, required_hops=reqf)
        loss = F.cross_entropy(out["answer_logits"], ans)
        if model.routing_mode in ("learned", "phase_zero", "phase_shuffle"):
            loss = loss + cfg.lambda_route * _route_loss(out["route_scores"], reqe, cfg.margin)
        opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0); opt.step()
    model.eval()
    return {"final_loss": float(loss.item())}
