"""
train.py — collate the bounded working set + multi-objective supervised training.

Objectives (separate heads): final decision (approval role incl. ABSTAIN), abstention, conflict,
active-version. Exact identity/joins stay deterministic (never trained from latent similarity).
The working set is chosen deterministically per arm before encoding.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .schema import DomainCfg, CAT_FIELDS
from .models import SlotQuadModel, working_set
from .dataset import ABSTAIN


def _feat(e, cfg):
    cats = {f: getattr(e, f) for f in CAT_FIELDS}
    num = [e.timestamp / 200.0, e.version / cfg.n_versions, float(e.source_authority),
           e.section_id / max(1, cfg.n_sections)]
    return cats, num


def collate_arm(batch, cfg: DomainCfg, arm, K, policy="P2", device="cpu"):
    B = len(batch)
    wss = [working_set(ex, arm, K, policy) for ex in batch]
    M = max(1, max(len(w["ids"]) for w in wss))
    ws_cats = {f: torch.zeros(B, M, dtype=torch.long, device=device) for f in CAT_FIELDS}
    ws_num = torch.zeros(B, M, 4, device=device)
    ws_mask = torch.zeros(B, M, dtype=torch.bool, device=device)
    q_cats = {f: torch.zeros(B, dtype=torch.long, device=device) for f in CAT_FIELDS}
    q_num = torch.zeros(B, 4, device=device)
    ans = torch.zeros(B, dtype=torch.long, device=device)
    conf = torch.zeros(B, device=device); abst = torch.zeros(B, device=device)
    ver = torch.zeros(B, dtype=torch.long, device=device)
    meta = []
    for i, (ex, w) in enumerate(zip(batch, wss)):
        id_of = {e.evidence_id: e for e in ex["events"]}
        for j, eid in enumerate(w["ids"][:M]):
            e = id_of.get(eid)
            if e is None:
                continue
            c, nu = _feat(e, cfg)
            for f in CAT_FIELDS:
                ws_cats[f][i, j] = c[f]
            ws_num[i, j] = torch.tensor(nu, device=device); ws_mask[i, j] = True
        qe = ex["events"][ex["query_pos"]]
        qc, qn = _feat(qe, cfg)
        for f in CAT_FIELDS:
            q_cats[f][i] = qc[f]
        q_num[i] = torch.tensor(qn, device=device)
        ans[i] = ex["answer_role"]; conf[i] = ex["conflict"]; abst[i] = ex["abstain"]
        ver[i] = ex["active_version"]
        # unauthorized inclusion: any working-set id NOT authorized in the ledger?
        unauth = any(not (id_of[eid].tenant_id == ex["tenant"] and id_of[eid].readable_by(ex["role_idx"]))
                     for eid in w["ids"] if eid in id_of)
        meta.append({"ids": w["ids"], "required_survived": w.get("required_survived", False),
                     "retrieval_calls": w.get("retrieval_calls", 0),
                     "records_encoded": w.get("records_encoded", len(w["ids"])),
                     "unauthorized_included": unauth, "ids_resolve": all(eid in id_of for eid in w["ids"])})
    labels = {"answer": ans, "conflict": conf, "abstain": abst, "version": ver}
    return (ws_cats, ws_num, ws_mask, q_cats, q_num), labels, meta


def train_model(model, gen_fn, cfg, arm, K, policy="P2", steps=500, lr=2e-3, batch_size=16,
                seed=0, device="cpu"):
    opt = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=lr)
    model.train()
    for step in range(steps):
        batch = gen_fn(batch_size, seed * 100000 + step)
        inp, labels, _ = collate_arm(batch, cfg, arm, K, policy, device)
        out = model(*inp)
        loss = (F.cross_entropy(out["answer"], labels["answer"])
                + F.binary_cross_entropy_with_logits(out["abstain"], labels["abstain"])
                + F.binary_cross_entropy_with_logits(out["conflict"], labels["conflict"])
                + F.cross_entropy(out["version"], labels["version"]))
        opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
        opt.step()
    model.eval()
    return {"final_loss": float(loss.item())}
