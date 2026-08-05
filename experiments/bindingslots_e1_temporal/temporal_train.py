#!/usr/bin/env python3
"""Exact frozen C1 training recipe applied to the temporal-task models (temporal vocab). Reuses the
FROZEN models.E1 / models.B0; only data/vocab differ. No retuning."""
from __future__ import annotations

import hashlib
import pathlib
import random
import sys

import torch
import torch.nn.functional as F

E1_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1"
if str(E1_DIR) not in sys.path:
    sys.path.insert(0, str(E1_DIR))
from models import E1, B0            # noqa: E402 (FROZEN architecture)
import temporal_task as T           # noqa: E402
import temporal_config as C         # noqa: E402

torch.set_num_threads(4)


def set_determinism(seed):
    random.seed(seed); torch.manual_seed(seed); torch.use_deterministic_algorithms(True)


def collate(eps):
    kt = torch.tensor([e["key_tokens"] for e in eps], dtype=torch.long)
    qt = torch.tensor([e["query_tokens"] for e in eps], dtype=torch.long)
    kv = torch.tensor([e["key_values"] for e in eps], dtype=torch.long)
    ti = torch.tensor([e["target_index"] for e in eps], dtype=torch.long)
    tv = torch.tensor([e["target_value"] for e in eps], dtype=torch.long)   # status token id (or -1)
    return kt, qt, kv, ti, tv


def param_hash(model):
    h = hashlib.sha256()
    for n, p in sorted(model.named_parameters()):
        h.update(n.encode()); h.update(p.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def train_e1(train_eps, seed):
    set_determinism(seed)
    m = E1(d=C.D, vocab=T.VOCAB)
    opt = torch.optim.Adam(m.parameters(), lr=C.LR)
    rng = random.Random(seed ^ 0x51ED)
    m.train()
    for _ in range(C.STEPS):
        idx = [rng.randrange(len(train_eps)) for _ in range(C.BATCH)]
        kt, qt, kv, ti, tv = collate([train_eps[i] for i in idx])
        K = kt.size(1)
        target = torch.where(ti >= 0, ti, torch.full_like(ti, K))
        loss = F.cross_entropy(m(kt, qt, C.TAU), target)
        opt.zero_grad(); loss.backward(); opt.step()
    return m


def train_b0(train_eps, seed):
    set_determinism(seed)
    m = B0(d=C.D, vocab=T.VOCAB, n_slots=T.KEYS_PER_EPISODE, n_values=T.STATUS_VALUES)
    opt = torch.optim.Adam(m.parameters(), lr=C.LR)
    rng = random.Random(seed ^ 0x0B0)
    valid = [e for e in train_eps if e["target_index"] >= 0]
    m.train()
    for _ in range(C.STEPS):
        idx = [rng.randrange(len(valid)) for _ in range(C.BATCH)]
        kt, qt, kv, ti, tv = collate([valid[i] for i in idx])
        status = tv - T._ST                       # status index target
        loss = F.cross_entropy(m(kt, qt), status)
        opt.zero_grad(); loss.backward(); opt.step()
    return m
