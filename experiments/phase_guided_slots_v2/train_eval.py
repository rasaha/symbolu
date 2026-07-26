"""
train_eval.py — v2 training (answer CE + per-fact write BCE) and metrics.

Loss L = L_answer + lambda_write * L_write, where
  L_answer : CE at <A> for the queried answer token.
  L_write  : BCE pushing the write gate → 1 at every fact anchor (fill memory so
             capacity saturates and eviction is forced). Retention/key/value/read
             are learned end-to-end from L_answer — under eviction the answer loss
             can only reward retaining answer-relevant facts, but relevance depends
             on the DISTANT focus header, which a local-only arm cannot see at write
             time. That is the intended capacity failure for C.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List, Optional

import torch
import torch.nn.functional as F

from experiments.phase_guided_slots_v2.task_schema import Example


@dataclass
class TCfg:
    steps: int = 400
    batch_size: int = 16
    lr: float = 1e-3
    lambda_write: float = 0.5
    eval_every: int = 100
    seed: int = 0


def collate(batch: List[Example], pad_id: int, device):
    maxlen = max(len(e.tokens) for e in batch)
    B = len(batch)
    ids = torch.full((B, maxlen), pad_id, dtype=torch.long)
    wl = torch.full((B, maxlen), -100, dtype=torch.long)
    apos = torch.zeros(B, dtype=torch.long)
    aid = torch.zeros(B, dtype=torch.long)
    for i, e in enumerate(batch):
        n = len(e.tokens)
        ids[i, :n] = torch.tensor(e.tokens)
        wl[i, :len(e.write_labels)] = torch.tensor(e.write_labels)
        apos[i] = e.answer_pos; aid[i] = e.answer_id
    return ids.to(device), wl.to(device), apos.to(device), aid.to(device)


def _losses(model, ids, wl, apos, aid, lambda_write):
    out = model(ids, apos, write_labels=wl)
    ans_loss = F.cross_entropy(out["answer_logits"], aid)
    r = out["r_write"]
    mask = wl != -100
    if mask.any():
        tgt = wl.clamp(min=0).float()
        # balance the many non-anchor 0s against the few anchor 1s so the gate learns
        # to fire at fact anchors (write once per fact) without collapsing to all-0.
        npos = tgt[mask].sum().clamp(min=1.0)
        nneg = (mask.sum() - npos).clamp(min=1.0)
        pos_weight = (nneg / npos).clamp(max=50.0)
        logit_r = torch.logit(r.clamp(1e-4, 1 - 1e-4))
        w_loss = F.binary_cross_entropy_with_logits(
            logit_r[mask], tgt[mask], pos_weight=pos_weight)
    else:
        w_loss = torch.zeros((), device=ids.device)
    return ans_loss + lambda_write * w_loss, ans_loss, w_loss


@torch.no_grad()
def _val_acc(model, val, pad_id, device):
    model.eval(); correct = total = 0
    for i in range(0, len(val), 64):
        b = val[i:i + 64]
        ids, wl, apos, aid = collate(b, pad_id, device)
        out = model(ids, apos)
        correct += (out["answer_logits"].argmax(-1) == aid).sum().item(); total += len(b)
    model.train()
    return correct / max(1, total)


def train(model, data: List[Example], pad_id: int, cfg: TCfg,
          val: Optional[List[Example]] = None, device="cpu") -> dict:
    torch.manual_seed(cfg.seed)
    rng = torch.Generator().manual_seed(cfg.seed + 3)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    model.train()
    n = len(data)
    best, best_state = -1.0, None
    for step in range(cfg.steps):
        idx = torch.randint(0, n, (cfg.batch_size,), generator=rng).tolist()
        b = [data[i] for i in idx]
        ids, wl, apos, aid = collate(b, pad_id, device)
        loss, al, wlo = _losses(model, ids, wl, apos, aid, cfg.lambda_write)
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if val is not None and (step + 1) % cfg.eval_every == 0:
            v = _val_acc(model, val, pad_id, device)
            if v > best:
                best = v; best_state = copy.deepcopy(model.state_dict())
    if best_state is not None:
        model.load_state_dict(best_state)
    return {"final_ans": al.item(), "final_write": wlo.item(), "best_val": best}


@torch.no_grad()
def evaluate(model, data: List[Example], pad_id: int, device="cpu") -> dict:
    model.eval()
    correct = total = 0
    by_pos = {p: [0, 0] for p in ("early", "middle", "late")}
    by_qt = {}
    for i in range(0, len(data), 32):
        b = data[i:i + 32]
        ids, wl, apos, aid = collate(b, pad_id, device)
        pred = model(ids, apos)["answer_logits"].argmax(-1)
        for j, e in enumerate(b):
            ok = int(pred[j].item() == aid[j].item())
            correct += ok; total += 1
            by_pos[e.target_position][0] += ok; by_pos[e.target_position][1] += 1
            q = by_qt.setdefault(e.query_type, [0, 0]); q[0] += ok; q[1] += 1
    return {
        "answer_acc": correct / max(1, total), "n": total,
        "acc_by_target_position": {p: (c / t if t else None) for p, (c, t) in by_pos.items()},
        "acc_by_query_type": {q: (c / t if t else None) for q, (c, t) in by_qt.items()},
    }
