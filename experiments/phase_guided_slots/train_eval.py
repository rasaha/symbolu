"""
train_eval.py — training (answer + write-worthiness losses) and metrics.

Loss: L = L_answer + lambda_write * L_write
  L_answer : cross-entropy at <A> for the queried topic value.
  L_write  : BCE on the guidance write signal r_write at labeled fact-value
             positions (1 topic / 0 distractor). Applied identically to C and D;
             it is the Stage-1 relevance supervision.

Validation-based early stopping (best answer accuracy). Metrics: answer accuracy,
write precision/recall/F1, and useful-slot survival proxy.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List, Optional

import torch
import torch.nn.functional as F

from .datasets_pressure import PExample
from .guided_models import GuidedSlotLM


@dataclass
class TCfg:
    steps: int = 500
    batch_size: int = 16
    lr: float = 1e-3
    lambda_write: float = 1.0
    eval_every: int = 100
    seed: int = 0


def _collate(batch: List[PExample], pad_id: int, device):
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
    r = out["r_write"]                                  # [B,N]
    mask = wl != -100
    if mask.any():
        tgt = wl.clamp(min=0).float()
        w_loss = F.binary_cross_entropy(r[mask], tgt[mask])
    else:
        w_loss = torch.zeros((), device=ids.device)
    return ans_loss + lambda_write * w_loss, ans_loss, w_loss, out


@torch.no_grad()
def _val_acc(model, val, pad_id, device):
    model.eval()
    correct = total = 0
    for i in range(0, len(val), 64):
        b = val[i:i + 64]
        ids, wl, apos, aid = _collate(b, pad_id, device)
        out = model(ids, apos)
        correct += (out["answer_logits"].argmax(-1) == aid).sum().item(); total += len(b)
    model.train()
    return correct / max(1, total)


def train(model: GuidedSlotLM, data: List[PExample], pad_id: int, cfg: TCfg,
          val: Optional[List[PExample]] = None, device="cpu") -> dict:
    torch.manual_seed(cfg.seed)
    rng = torch.Generator().manual_seed(cfg.seed + 3)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    model.train()
    n = len(data)
    best, best_state = -1.0, None
    for step in range(cfg.steps):
        idx = torch.randint(0, n, (cfg.batch_size,), generator=rng).tolist()
        b = [data[i] for i in idx]
        ids, wl, apos, aid = _collate(b, pad_id, device)
        loss, al, wlo, _ = _losses(model, ids, wl, apos, aid, cfg.lambda_write)
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
def evaluate(model: GuidedSlotLM, data: List[PExample], pad_id: int, device="cpu") -> dict:
    model.eval()
    correct = total = 0
    tp = fp = fn = tn = 0
    for i in range(0, len(data), 32):
        b = data[i:i + 32]
        ids, wl, apos, aid = _collate(b, pad_id, device)
        out = model(ids, apos)
        pred = out["answer_logits"].argmax(-1)
        correct += (pred == aid).sum().item(); total += len(b)
        r = out["r_write"]
        mask = wl != -100
        pos = (r >= 0.5) & mask
        tp += ((pos) & (wl == 1)).sum().item()
        fp += ((pos) & (wl == 0)).sum().item()
        fn += ((~pos) & (wl == 1) & mask).sum().item()
        tn += ((~pos) & (wl == 0) & mask).sum().item()
    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn)
    f1 = 2 * prec * rec / max(1e-9, prec + rec)
    return {
        "answer_acc": correct / max(1, total),
        "write_precision": prec, "write_recall": rec, "write_f1": f1,
        "false_write_rate": fp / max(1, fp + tn),
        "n": total,
    }
