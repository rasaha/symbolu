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
    hop_tgt = torch.full((B, H), -1, dtype=torch.long)       # per-hop target identity (event value)
    for i, e in enumerate(batch):
        kp = e["key_pos"]; event_pos[i, :len(kp)] = torch.tensor(kp)
        probe_pos[i] = len(e["tokens"]) - 1
        valid_len[i] = len(e["tokens"]); answer[i] = e["answer"]
        for h, evidx in enumerate(e["req_evidx"]):
            req_evidx[i, h] = evidx
            req_full[i, h] = e["key_pos"][evidx]
            hop_tgt[i, h] = e["events"][evidx]["value"]      # what this hop points to
    return (ids.to(device), event_pos.to(device), probe_pos.to(device), valid_len.to(device),
            answer.to(device), req_full.to(device), req_evidx.to(device), hop_tgt.to(device))


def _route_loss(route_scores, req_evidx, margin):
    """Per hop, the required event's score must exceed the others by a margin (vectorized)."""
    losses = []
    for h, sc in enumerate(route_scores):                    # sc:[B,Ne]
        if h >= req_evidx.shape[1]:
            continue
        tgt = req_evidx[:, h]                                 # [B]
        valid = tgt >= 0
        if not valid.any():
            continue
        t = tgt.clamp(min=0).unsqueeze(1)                    # [B,1]
        pos = sc.gather(1, t)                                 # [B,1]
        hinge = F.relu(margin - pos + sc)                    # [B,Ne]
        keep = torch.ones_like(sc, dtype=torch.bool).scatter(1, t, False)  # exclude target itself
        per_ex = (hinge * keep).sum(1) / keep.sum(1).clamp(min=1)          # [B]
        losses.append(per_ex[valid].mean())
    return torch.stack(losses).mean() if losses else torch.zeros((), device=route_scores[0].device)


def train_hybrid(model, gen_fn, vocab, cfg: TrainCfg, device="cpu"):
    opt = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=cfg.lr)
    model.train()
    rng = torch.Generator().manual_seed(cfg.seed + 1)
    for step in range(cfg.steps):
        data = gen_fn(cfg.batch_size, cfg.seed * 10000 + step)
        ids, ep, pp, vl, ans, reqf, reqe, hoptgt = collate_iter(data, vocab, device)
        out = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)
        loss = F.cross_entropy(out["answer_logits"], ans)
        # per-hop supervision (§13): each hop's attention output should predict that hop's target
        for h, hl in enumerate(out["hop_logits"]):
            if h < hoptgt.shape[1]:
                m = hoptgt[:, h] >= 0
                if m.any():
                    loss = loss + F.cross_entropy(hl[m], hoptgt[m, h])
        # structured-pointer supervision (§ query-update repair): the pointer after hop h must select
        # the hop-(h+1) required EVIDENCE event. Train-only; autonomous eval uses the predicted pointer.
        for h, pl in enumerate(out.get("pointer_logits", [])):
            if h + 1 < reqe.shape[1]:
                nxt = reqe[:, h + 1]; mm = nxt >= 0
                if mm.any():
                    loss = loss + F.cross_entropy(pl[mm], nxt[mm])
        # query-alignment fallback (only when the structured pointer is not used)
        if not out.get("pointer_logits"):
            ev = out["event_reps"]
            for h, qh in enumerate(out.get("queries", [])):
                if h + 1 < reqe.shape[1]:
                    nxt = reqe[:, h + 1]; mm = nxt >= 0
                    if mm.any():
                        tgt = ev[mm].gather(1, nxt[mm].clamp(min=0).view(-1, 1, 1).expand(-1, 1, ev.shape[-1])).squeeze(1)
                        loss = loss + (1.0 - F.cosine_similarity(qh[mm], tgt.detach(), dim=-1)).mean()
        if model.routing_mode in ("learned", "phase_zero", "phase_shuffle"):
            loss = loss + cfg.lambda_route * _route_loss(out["route_scores"], reqe, cfg.margin)
        opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0); opt.step()
    model.eval()
    return {"final_loss": float(loss.item())}
