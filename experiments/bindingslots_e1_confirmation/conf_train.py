#!/usr/bin/env python3
"""Exact frozen C1 training recipe applied to the independent task's models (new vocab). Identical
optimizer / steps / lr / temperature / loss to the merged experiment; only the data and vocab differ."""
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
from models import E1, B0            # noqa: E402  (FROZEN architecture)
import conf_task as T               # noqa: E402
import conf_config as C             # noqa: E402
from conf_eval import collate       # noqa: E402

torch.set_num_threads(4)


def set_determinism(seed):
    random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


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
    last = None
    for _ in range(C.STEPS):
        idx = [rng.randrange(len(train_eps)) for _ in range(C.BATCH)]
        kt, kv, qt, ti, tv = collate([train_eps[i] for i in idx])
        logits = m(kt, qt, C.TAU)
        K = kt.size(1)
        target = torch.where(ti >= 0, ti, torch.full_like(ti, K))
        loss = F.cross_entropy(logits, target)
        opt.zero_grad(); loss.backward(); opt.step()
        last = float(loss.detach())
    return m, last


def train_b0(train_eps, seed):
    set_determinism(seed)
    m = B0(d=C.D, vocab=T.VOCAB, n_slots=T.KEYS_PER_EPISODE, n_values=T.N_VALUES)
    opt = torch.optim.Adam(m.parameters(), lr=C.LR)
    rng = random.Random(seed ^ 0x0B0)
    valid = [e for e in train_eps if e["target_index"] >= 0]
    m.train()
    last = None
    for _ in range(C.STEPS):
        idx = [rng.randrange(len(valid)) for _ in range(C.BATCH)]
        kt, kv, qt, ti, tv = collate([valid[i] for i in idx])
        logits = m(kt, qt)
        loss = F.cross_entropy(logits, tv)
        opt.zero_grad(); loss.backward(); opt.step()
        last = float(loss.detach())
    return m, last
