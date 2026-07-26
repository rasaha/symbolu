"""
oracle_eval.py — training, evaluation, and memory trace for the oracle-addressed arms.

Provides oracle entity ids (entity_at_pos, query_entity) to the model, trains with
answer CE + per-fact write BCE, and reports answer accuracy plus — read straight
off the OracleSlotState — capacity metrics: occupancy, evictions, target survival
(overall and by target position), and the key baseline check acc ≈ survival with
acc(target-evicted) ≈ chance.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List, Optional

import torch
import torch.nn.functional as F

from experiments.phase_guided_slots_v2.task_schema import Example


@dataclass
class OTCfg:
    steps: int = 500
    batch_size: int = 16
    lr: float = 1e-3
    lambda_write: float = 0.5
    eval_every: int = 100
    seed: int = 0


def collate_oracle(batch: List[Example], pad_id: int, device):
    maxlen = max(len(e.tokens) for e in batch)
    B = len(batch)
    ids = torch.full((B, maxlen), pad_id, dtype=torch.long)
    wl = torch.full((B, maxlen), -100, dtype=torch.long)
    ent = torch.full((B, maxlen), -1, dtype=torch.long)     # oracle entity at anchors
    apos = torch.zeros(B, dtype=torch.long)
    aid = torch.zeros(B, dtype=torch.long)
    qent = torch.zeros(B, dtype=torch.long)
    for i, e in enumerate(batch):
        n = len(e.tokens)
        ids[i, :n] = torch.tensor(e.tokens)
        wl[i, :len(e.write_labels)] = torch.tensor(e.write_labels)
        anchors = [j for j, l in enumerate(e.write_labels) if l == 1]
        for k, j in enumerate(anchors):
            if k < len(e.facts):
                ent[i, j] = e.facts[k].entity_id
        apos[i] = e.answer_pos; aid[i] = e.answer_id
        qent[i] = e.gold_support_entity_ids[0]
    return (ids.to(device), wl.to(device), ent.to(device), apos.to(device),
            aid.to(device), qent.to(device))


def _losses(model, ids, wl, ent, apos, aid, qent, lambda_write):
    out = model(ids, apos, entity_at_pos=ent, query_entity=qent, write_labels=wl)
    ans_loss = F.cross_entropy(out["answer_logits"], aid)
    r = out["r_write"]; mask = wl != -100
    if mask.any():
        tgt = wl.clamp(min=0).float()
        npos = tgt[mask].sum().clamp(min=1.0); nneg = (mask.sum() - npos).clamp(min=1.0)
        pw = (nneg / npos).clamp(max=50.0)
        logit_r = torch.logit(r.clamp(1e-4, 1 - 1e-4))
        w_loss = F.binary_cross_entropy_with_logits(logit_r[mask], tgt[mask], pos_weight=pw)
    else:
        w_loss = torch.zeros((), device=ids.device)
    return ans_loss + lambda_write * w_loss, ans_loss, w_loss


@torch.no_grad()
def _val_acc(model, val, pad_id, device):
    model.eval(); correct = total = 0
    for i in range(0, len(val), 64):
        b = val[i:i + 64]
        ids, wl, ent, apos, aid, qent = collate_oracle(b, pad_id, device)
        pred = model(ids, apos, entity_at_pos=ent, query_entity=qent)["answer_logits"].argmax(-1)
        correct += (pred == aid).sum().item(); total += len(b)
    model.train(); return correct / max(1, total)


def train_oracle(model, data, pad_id, cfg: OTCfg, val=None, device="cpu"):
    torch.manual_seed(cfg.seed)
    rng = torch.Generator().manual_seed(cfg.seed + 3)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr); model.train()
    n = len(data); best, best_state = -1.0, None
    for step in range(cfg.steps):
        idx = torch.randint(0, n, (cfg.batch_size,), generator=rng).tolist()
        b = [data[i] for i in idx]
        ids, wl, ent, apos, aid, qent = collate_oracle(b, pad_id, device)
        loss, al, wlo = _losses(model, ids, wl, ent, apos, aid, qent, cfg.lambda_write)
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        if val is not None and (step + 1) % cfg.eval_every == 0:
            vacc = _val_acc(model, val, pad_id, device)
            if vacc > best:
                best = vacc; best_state = copy.deepcopy(model.state_dict())
    if best_state is not None:
        model.load_state_dict(best_state)
    return {"final_ans": al.item(), "final_write": wlo.item(), "best_val": best}


def train_oracle_curriculum(model, gen_fn, pad_id, stages, cfg: OTCfg, device="cpu"):
    torch.manual_seed(cfg.seed)
    rng = torch.Generator().manual_seed(cfg.seed + 3)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr); model.train()
    log = []
    for si, (n_live, steps) in enumerate(stages):
        data = gen_fn(n_live, 400); n = len(data)
        for step in range(steps):
            idx = torch.randint(0, n, (cfg.batch_size,), generator=rng).tolist()
            b = [data[i] for i in idx]
            ids, wl, ent, apos, aid, qent = collate_oracle(b, pad_id, device)
            loss, al, wlo = _losses(model, ids, wl, ent, apos, aid, qent, cfg.lambda_write)
            opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        log.append({"stage": si, "n_live": n_live, "steps": steps, "final_ans": al.item()})
    return {"curriculum": log}


@torch.no_grad()
def evaluate_oracle(model, data, pad_id, device="cpu"):
    model.eval()
    correct = total = 0
    # accuracy split by whether the target survived (found at read)
    surv_c = surv_t = ev_c = ev_t = 0
    by_pos = {p: [0, 0] for p in ("early", "middle", "late")}
    occ_sum = evict_sum = 0.0
    tgt_surv = 0; tgt_surv_pos = {p: [0, 0] for p in ("early", "middle", "late")}
    for i in range(0, len(data), 32):
        b = data[i:i + 32]
        ids, wl, ent, apos, aid, qent = collate_oracle(b, pad_id, device)
        out = model(ids, apos, entity_at_pos=ent, query_entity=qent)
        pred = out["answer_logits"].argmax(-1)
        found = out["found"]; state = out["state"]
        occ_sum += state.active.sum(dim=1).sum().item()
        evict_sum += state.n_evict.sum().item()
        for j, e in enumerate(b):
            ok = int(pred[j].item() == aid[j].item())
            correct += ok; total += 1
            by_pos[e.target_position][0] += ok; by_pos[e.target_position][1] += 1
            if found[j].item():
                surv_c += ok; surv_t += 1; tgt_surv += 1
                tgt_surv_pos[e.target_position][0] += 1
            else:
                ev_c += ok; ev_t += 1
            tgt_surv_pos[e.target_position][1] += 1
    return {
        "answer_acc": correct / max(1, total), "n": total,
        "mean_occupancy": occ_sum / max(1, total),
        "evictions": evict_sum / max(1, total),
        "target_survival_rate": tgt_surv / max(1, total),
        "acc_given_survived": surv_c / max(1, surv_t),
        "acc_given_evicted": ev_c / max(1, ev_t),
        "acc_by_target_position": {p: (c / t if t else None) for p, (c, t) in by_pos.items()},
        "survival_by_target_position": {p: (c / t if t else None) for p, (c, t) in tgt_surv_pos.items()},
    }
