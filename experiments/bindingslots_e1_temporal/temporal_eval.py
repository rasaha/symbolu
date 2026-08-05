#!/usr/bin/env python3
"""Independent evaluator for the temporal transfer test. Per split: E1 correct-key top-1 (addressing),
mean rank, E1 end-to-end (value) accuracy, B0 end-to-end accuracy; and for T8: no-match false-accept /
false-reject (paired with a valid split)."""
from __future__ import annotations

import torch

import temporal_task as T
from temporal_train import collate


@torch.no_grad()
def eval_e1(model, eps, tau):
    model.eval()
    kt, qt, kv, ti, tv = collate(eps)
    K = kt.size(1)
    scores = model.scores(kt, qt, tau)          # [B,K+1], null=K
    key_scores = scores[:, :K]
    pred_all = scores.argmax(-1)
    pred_key = key_scores.argmax(-1)
    valid = ti >= 0
    out = {"n": len(eps)}
    if valid.any():
        vi = ti[valid]
        out["addressing_top1"] = float((pred_key[valid] == vi).float().mean())
        cs = key_scores[valid].gather(1, vi.view(-1, 1)).squeeze(1)
        out["mean_correct_key_rank"] = float(((key_scores[valid] > cs.view(-1, 1)).sum(1) + 1).float().mean())
        pa = pred_all[valid]
        abst = pa == K
        chosen = kv[valid].gather(1, pa.clamp(max=K - 1).view(-1, 1)).squeeze(1)
        out["e2e"] = float(((~abst) & (chosen == tv[valid])).float().mean())
        out["false_reject"] = float(abst.float().mean())
    if (~valid).any():
        pa = pred_all[~valid]
        out["false_accept"] = float((pa != K).float().mean())
    return out


@torch.no_grad()
def eval_b0(model, eps):
    model.eval()
    kt, qt, kv, ti, tv = collate(eps)
    pred = model(kt, qt).argmax(-1)              # status index
    valid = ti >= 0
    out = {"n": len(eps)}
    if valid.any():
        out["e2e"] = float((pred[valid] == (tv[valid] - T._ST)).float().mean())
        out["addressing_top1"] = out["e2e"]
    if (~valid).any():
        out["false_accept"] = 1.0                # no abstention
    return out
