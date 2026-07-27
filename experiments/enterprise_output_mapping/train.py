"""train.py — train the structured reasoner (typed fields + O0 latent head) and the learned
mappers O3/O4 (over frozen typed fields). Field supervision uses the TRUE StructuredFinding; no
required-evidence labels or outcomes leak into the deterministic mappers at eval."""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from experiments.enterprise_slots_quadratic.schema import DomainCfg
from .structured_reasoning import StructuredReasoner, collate, FIELD_DIMS
from .learned_mapper import TypedMapper, HybridMapper, NON_GATED
from .constrained_mapper import hard_gate
from .policy_mapper import fields_argmax


def train_reasoner(model, gen_fn, cfg, K, steps=500, lr=2e-3, batch_size=16, seed=0, device="cpu"):
    opt = torch.optim.Adam(model.parameters(), lr=lr); model.train()
    for step in range(steps):
        batch = gen_fn(batch_size, seed * 100000 + step)
        inp, fields, outcome, _ = collate(batch, cfg, K, device)
        out = model(*inp)
        loss = F.cross_entropy(out["latent_outcome"], outcome)
        for k in FIELD_DIMS:
            loss = loss + F.cross_entropy(out["field_logits"][k], fields[k])
        opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
    model.eval(); return {"loss": float(loss.item())}


def train_typed_mapper(mapper, reasoner, gen_fn, cfg, K, steps=400, lr=2e-3, batch_size=16, seed=1, device="cpu"):
    opt = torch.optim.Adam(mapper.parameters(), lr=lr); mapper.train(); reasoner.eval()
    for step in range(steps):
        batch = gen_fn(batch_size, seed * 100000 + step)
        inp, fields, outcome, _ = collate(batch, cfg, K, device)
        with torch.no_grad():
            ro = reasoner(*inp)
        loss = F.cross_entropy(mapper(ro), outcome)
        opt.zero_grad(); loss.backward(); opt.step()
    mapper.eval(); return {"loss": float(loss.item())}


def train_hybrid_mapper(mapper, reasoner, gen_fn, cfg, K, steps=400, lr=2e-3, batch_size=16, seed=2, device="cpu"):
    """O4: learn to rank NON_GATED outcomes only, on examples the gates do not resolve."""
    opt = torch.optim.Adam(mapper.parameters(), lr=lr); mapper.train(); reasoner.eval()
    idx_of = {o: i for i, o in enumerate(NON_GATED)}
    for step in range(steps):
        batch = gen_fn(batch_size, seed * 100000 + step)
        inp, fields, outcome, meta = collate(batch, cfg, K, device)
        with torch.no_grad():
            ro = reasoner(*inp)
        rank = mapper.rank_logits(ro)
        fa = fields_argmax(ro["field_logits"])
        rows, tgt = [], []
        for i in range(len(batch)):
            if hard_gate(fa, i, meta[i]) is None and int(outcome[i]) in idx_of:
                rows.append(i); tgt.append(idx_of[int(outcome[i])])
        if not rows:
            continue
        loss = F.cross_entropy(rank[torch.tensor(rows)], torch.tensor(tgt))
        opt.zero_grad(); loss.backward(); opt.step()
    mapper.eval(); return {"loss": float(loss.item())}
