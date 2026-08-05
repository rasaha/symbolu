#!/usr/bin/env python3
"""Independently-implemented evaluation path for the confirmation. Reuses the FROZEN model architecture
(models.E1 / models.B0 from the merged experiment) but re-derives every metric here from raw scores —
it does not call the original engine's eval functions."""
from __future__ import annotations

import pathlib
import sys

import torch

E1_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1"
if str(E1_DIR) not in sys.path:
    sys.path.insert(0, str(E1_DIR))
import conf_task as T   # noqa: E402


def collate(eps):
    kt = torch.tensor([e["key_tokens"] for e in eps], dtype=torch.long)
    kv = torch.tensor([e["key_values"] for e in eps], dtype=torch.long)
    qt = torch.tensor([e["query_tokens"] for e in eps], dtype=torch.long)
    ti = torch.tensor([e["target_index"] for e in eps], dtype=torch.long)
    tv = torch.tensor([e["target_value"] for e in eps], dtype=torch.long)
    return kt, kv, qt, ti, tv


@torch.no_grad()
def eval_e1_split(model, eps, tau):
    model.eval()
    kt, kv, qt, ti, tv = collate(eps)
    K = kt.size(1)
    scores = model.scores(kt, qt, tau)          # [B,K+1]; null = index K
    key_scores = scores[:, :K]
    pred_all = scores.argmax(-1)
    pred_key = key_scores.argmax(-1)
    valid = ti >= 0
    nm = ~valid
    out = {}
    if valid.any():
        vi = ti[valid]
        out["addressing_top1"] = float((pred_key[valid] == vi).float().mean())
        cs = key_scores[valid].gather(1, vi.view(-1, 1)).squeeze(1)
        out["mean_correct_key_rank"] = float(((key_scores[valid] > cs.view(-1, 1)).sum(1) + 1).float().mean())
        top2 = key_scores[valid].topk(2, 1).values
        out["mean_top1_margin"] = float((top2[:, 0] - top2[:, 1]).mean())
        pa = pred_all[valid]
        abst = pa == K
        chosen = kv[valid].gather(1, pa.clamp(max=K - 1).view(-1, 1)).squeeze(1)
        out["e2e"] = float(((~abst) & (chosen == tv[valid])).float().mean())
        out["false_reject"] = float(abst.float().mean())
        out["answer_availability"] = float((~abst).float().mean())
        oracle = kv[valid].gather(1, vi.view(-1, 1)).squeeze(1)
        out["oracle_key_value_accuracy"] = float((oracle == tv[valid]).float().mean())
    if nm.any():
        pa = pred_all[nm]
        fa = pa != K
        out["false_accept"] = float(fa.float().mean())
        s = scores[nm]; top2 = s.topk(2, 1).values; marg = top2[:, 0] - top2[:, 1]
        out["confident_false_accept"] = float((fa & (marg > marg.median())).float().mean())
    return out


@torch.no_grad()
def eval_b0_split(model, eps):
    model.eval()
    kt, kv, qt, ti, tv = collate(eps)
    logits = model(kt, qt)                       # [B, n_values]
    pred = logits.argmax(-1)
    valid = ti >= 0
    out = {}
    if valid.any():
        acc = float((pred[valid] == tv[valid]).float().mean())
        out["e2e"] = acc
        out["addressing_top1"] = acc             # B0 has no separable key signal
    if (~valid).any():
        out["false_accept"] = 1.0                # no abstention -> always emits a (wrong) value
    return out
