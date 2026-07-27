"""
train_eval.py — collate, curriculum training, and evaluation for the Phase-v2
oracle-retention experiment.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List

import torch

from experiments.phase_guided_slots_v2.task_schema import VENDORS
from .retention_losses import (answer_loss, write_gate_loss, phase_gate_loss,
                               retention_hinge)


@dataclass
class TCfg:
    lr: float = 1e-3
    batch_size: int = 16
    lambda_write: float = 0.5
    lambda_gatephase: float = 0.5
    lambda_retain: float = 1.0
    seed: int = 0


def collate(batch, pad_id, device):
    maxlen = max(len(e.tokens) for e in batch)
    B = len(batch)
    ids = torch.full((B, maxlen), pad_id, dtype=torch.long)
    ent = torch.full((B, maxlen), -1, dtype=torch.long)
    anchor = torch.zeros(B, maxlen, dtype=torch.bool)
    focus_anchor = torch.zeros(B, maxlen, dtype=torch.bool)
    distr_anchor = torch.zeros(B, maxlen, dtype=torch.bool)
    gate_tgt = torch.full((B, maxlen), -1.0)
    apos = torch.zeros(B, dtype=torch.long)
    aid = torch.zeros(B, dtype=torch.long)
    qent = torch.zeros(B, dtype=torch.long)
    for i, e in enumerate(batch):
        n = len(e.tokens); ids[i, :n] = torch.tensor(e.tokens)
        focus_vendor = e.meta["focus_vendor"]
        anchors = [j for j, l in enumerate(e.write_labels) if l == 1]
        gate_tgt[i, :e.header_end + 1 if hasattr(e, "header_end") else 4] = 1.0  # header
        for k, j in enumerate(anchors):
            if k >= len(e.facts):
                continue
            f = e.facts[k]
            ent[i, j] = f.entity_id
            anchor[i, j] = True
            rel = (f.vendor == focus_vendor)
            (focus_anchor if rel else distr_anchor)[i, j] = True
            gate_tgt[i, j] = 1.0 if rel else 0.0
        apos[i] = e.answer_pos; aid[i] = e.answer_id
        qent[i] = e.gold_support_entity_ids[0]
    dev = device
    return (ids.to(dev), ent.to(dev), anchor.to(dev), focus_anchor.to(dev),
            distr_anchor.to(dev), gate_tgt.to(dev), apos.to(dev), aid.to(dev), qent.to(dev))


def _step_loss(model, b, pad_id, cfg, device):
    ids, ent, anchor, fa, da, gt, apos, aid, qent = collate(b, pad_id, device)
    out = model(ids, apos, ent, qent)
    loss = answer_loss(out["answer_logits"], aid)
    loss = loss + cfg.lambda_write * write_gate_loss(out["gate"], anchor)
    loss = loss + cfg.lambda_retain * retention_hinge(out["r_final"], fa, da)
    if model.use_phase and model.arm != "D-v1":
        w = model.gate_values(ids).mean(-1)         # [B,N]
        loss = loss + cfg.lambda_gatephase * phase_gate_loss(w, gt)
    return loss


def train_curriculum(model, gen_fn, pad_id, stages, cfg: TCfg, device="cpu"):
    """stages = [(n_live, steps), ...]. gen_fn(n_live) -> list[FocusExample-like]."""
    torch.manual_seed(cfg.seed)
    rng = torch.Generator().manual_seed(cfg.seed + 1)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    model.train()
    log = []
    for si, (n_live, steps) in enumerate(stages):
        data = gen_fn(n_live); n = len(data)
        for step in range(steps):
            idx = torch.randint(0, n, (cfg.batch_size,), generator=rng).tolist()
            b = [data[i] for i in idx]
            loss = _step_loss(model, b, pad_id, cfg, device)
            opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        log.append({"stage": si, "n_live": n_live, "loss": float(loss.item())})
    model.eval()
    return log


@torch.no_grad()
def evaluate(model, data, pad_id, device="cpu"):
    model.eval()
    correct = total = 0
    surv_c = surv_t = ev_c = ev_t = tgt_surv = 0
    by_pos = {p: [0, 0] for p in ("early", "middle", "late")}
    surv_by_pos = {p: [0, 0] for p in ("early", "middle", "late")}
    occ = evict = 0.0
    for i in range(0, len(data), 32):
        b = data[i:i + 32]
        ids, ent, anchor, fa, da, gt, apos, aid, qent = collate(b, pad_id, device)
        out = model(ids, apos, ent, qent)
        pred = out["answer_logits"].argmax(-1); found = out["found"]; state = out["state"]
        occ += state.active.sum(dim=1).sum().item(); evict += state.n_evict.sum().item()
        for j, e in enumerate(b):
            ok = int(pred[j].item() == aid[j].item()); correct += ok; total += 1
            by_pos[e.target_position][0] += ok; by_pos[e.target_position][1] += 1
            if found[j].item():
                surv_c += ok; surv_t += 1; tgt_surv += 1
                surv_by_pos[e.target_position][0] += 1
            else:
                ev_c += ok; ev_t += 1
            surv_by_pos[e.target_position][1] += 1
    return {
        "answer_acc": correct / max(1, total), "n": total,
        "target_survival_rate": tgt_surv / max(1, total),
        "acc_given_survived": surv_c / max(1, surv_t),
        "acc_given_evicted": ev_c / max(1, ev_t),
        "mean_occupancy": occ / max(1, total), "evictions": evict / max(1, total),
        "acc_by_target_position": {p: (c / t if t else None) for p, (c, t) in by_pos.items()},
        "survival_by_target_position": {p: (c / t if t else None) for p, (c, t) in surv_by_pos.items()},
    }
