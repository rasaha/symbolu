#!/usr/bin/env python3
"""Deterministic training + evaluation engine for B0 and E1 (CPU fp32, threads=4).

Both models train on the SAME valid episodes; E1 additionally trains on no-match episodes to learn its
null key (part of the E1 bundle; B0 has no abstention by design). All metrics keep addressing, no-match,
end-to-end, and stability separate.
"""
from __future__ import annotations

import hashlib
import random

import torch
import torch.nn.functional as F

import task as T
from models import B0, E1

torch.set_num_threads(4)


def set_determinism(seed):
    random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def collate(eps):
    kt = torch.tensor([e["key_tokens"] for e in eps], dtype=torch.long)      # [B,K,KLEN]
    kv = torch.tensor([e["key_values"] for e in eps], dtype=torch.long)      # [B,K]
    qt = torch.tensor([e["query_tokens"] for e in eps], dtype=torch.long)    # [B,QLEN]
    ti = torch.tensor([e["target_index"] for e in eps], dtype=torch.long)    # [B] (-1 no-match)
    tv = torch.tensor([e["target_value"] for e in eps], dtype=torch.long)    # [B] (-1 no-match)
    return kt, kv, qt, ti, tv


def param_hash(model):
    h = hashlib.sha256()
    for n, p in sorted(model.named_parameters()):
        h.update(n.encode()); h.update(p.detach().cpu().numpy().tobytes())
    return h.hexdigest()


# ------------------------------------------------------------------ training
def train_e1(train_eps, steps, batch, lr, tau, seed):
    set_determinism(seed)
    m = E1()
    opt = torch.optim.Adam(m.parameters(), lr=lr)
    rng = random.Random(seed ^ 0x51ED)
    losses = []
    m.train()
    for step in range(steps):
        idx = [rng.randrange(len(train_eps)) for _ in range(batch)]
        kt, kv, qt, ti, tv = collate([train_eps[i] for i in idx])
        logits = m(kt, qt, tau)                    # [B,K+1]
        K = kt.size(1)
        target = torch.where(ti >= 0, ti, torch.full_like(ti, K))   # no-match -> null index K
        loss = F.cross_entropy(logits, target)
        opt.zero_grad(); loss.backward(); opt.step()
        losses.append(float(loss.detach()))
    return m, losses


def train_b0(train_eps, steps, batch, lr, seed):
    set_determinism(seed)
    m = B0()
    opt = torch.optim.Adam(m.parameters(), lr=lr)
    rng = random.Random(seed ^ 0x0B0)
    # B0 trains on valid episodes only (no abstention target exists)
    valid = [e for e in train_eps if e["target_index"] >= 0]
    losses = []
    m.train()
    for step in range(steps):
        idx = [rng.randrange(len(valid)) for _ in range(batch)]
        kt, kv, qt, ti, tv = collate([valid[i] for i in idx])
        logits = m(kt, qt)                          # [B, n_values]
        loss = F.cross_entropy(logits, tv)
        opt.zero_grad(); loss.backward(); opt.step()
        losses.append(float(loss.detach()))
    return m, losses


# ------------------------------------------------------------------ evaluation
@torch.no_grad()
def eval_e1(m, eps, tau):
    m.eval()
    kt, kv, qt, ti, tv = collate(eps)
    K = kt.size(1)
    logits = m(kt, qt, tau)                          # [B,K+1]
    key_logits = logits[:, :K]                       # exclude null
    pred_all = logits.argmax(-1)                     # over K+1 (null=K)
    pred_key = key_logits.argmax(-1)                 # addressing (ignore null)
    is_nm = (ti < 0)
    valid = ~is_nm
    out = {"n": len(eps), "n_valid": int(valid.sum()), "n_nomatch": int(is_nm.sum())}

    # addressing (valid only): correct key outscores other keys
    if valid.any():
        addr_correct = (pred_key[valid] == ti[valid])
        out["addressing_top1"] = float(addr_correct.float().mean())
        # correct-key rank + margin
        sc = key_logits[valid]
        ci = ti[valid]
        correct_score = sc.gather(1, ci.view(-1, 1)).squeeze(1)
        ranks = (sc > correct_score.view(-1, 1)).sum(1) + 1
        out["mean_correct_key_rank"] = float(ranks.float().mean())
        top2 = sc.topk(2, dim=1).values
        out["mean_top1_margin"] = float((top2[:, 0] - top2[:, 1]).mean())
        # end-to-end (with null): abstain if null wins; else value of chosen key
        pa = pred_all[valid]
        abstained = (pa == K)
        chosen_val = kv[valid].gather(1, pa.clamp(max=K - 1).view(-1, 1)).squeeze(1)
        e2e_correct = (~abstained) & (chosen_val == tv[valid])
        out["e2e_retrieval_accuracy"] = float(e2e_correct.float().mean())
        out["false_reject_rate"] = float(abstained.float().mean())
        out["answer_availability"] = float((~abstained).float().mean())
        # oracle-key value accuracy (diagnostic; value path is a lookup -> ~1.0 for E1)
        oracle_val = kv[valid].gather(1, ti[valid].view(-1, 1)).squeeze(1)
        out["oracle_key_value_accuracy"] = float((oracle_val == tv[valid]).float().mean())
    # no-match (G6): correct = abstain (pred==null)
    if is_nm.any():
        pa = pred_all[is_nm]
        false_accept = (pa != K)
        out["false_accept_rate"] = float(false_accept.float().mean())
        out["nomatch_accuracy"] = float((~false_accept).float().mean())
        # confidently-wrong nearest-key: false-accept with high top-1 margin
        sc = logits[is_nm]
        top2 = sc.topk(2, dim=1).values
        marg = (top2[:, 0] - top2[:, 1])
        out["nomatch_confident_falseaccept_rate"] = float((false_accept & (marg > marg.median())).float().mean())
    return out


@torch.no_grad()
def eval_b0(m, eps):
    m.eval()
    kt, kv, qt, ti, tv = collate(eps)
    logits = m(kt, qt)                                # [B, n_values]
    pred_val = logits.argmax(-1)
    is_nm = (ti < 0)
    valid = ~is_nm
    out = {"n": len(eps)}
    if valid.any():
        out["e2e_retrieval_accuracy"] = float((pred_val[valid] == tv[valid]).float().mean())
        # addressing proxy: B0 has no explicit key; addressing == value-correct (no separable key signal)
        out["addressing_top1"] = out["e2e_retrieval_accuracy"]
    if is_nm.any():
        # B0 has no abstention -> always emits a value -> cannot be correct on no-match
        out["false_accept_rate"] = 1.0
        out["nomatch_accuracy"] = 0.0
    return out
