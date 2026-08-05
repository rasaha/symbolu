#!/usr/bin/env python3
"""Train an E1F cell under the EXACT frozen C1 recipe. Identical to temporal_train.train_e1 except the
model is E1F(factors=...) instead of the plain E1. Same optimizer, lr, steps, batch, tau, loss, and
per-seed batch sampling stream, so every cell sees identical training batches for a given seed."""
from __future__ import annotations

import hashlib
import pathlib
import random
import sys

import torch
import torch.nn.functional as F

TEMPORAL_DIR = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1_temporal"
if str(TEMPORAL_DIR) not in sys.path:
    sys.path.insert(0, str(TEMPORAL_DIR))
import temporal_task as T             # noqa: E402
from temporal_train import collate, set_determinism   # noqa: E402  (reuse frozen collate + determinism)

import factor_config as C             # noqa: E402
from factor_model import E1F          # noqa: E402

torch.set_num_threads(4)


def param_hash(model):
    h = hashlib.sha256()
    for n, p in sorted(model.named_parameters()):
        h.update(n.encode()); h.update(p.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def train_cell(train_eps, cell, seed):
    """Train the E1F for `cell` (a code in factor_config.CELLS) on `train_eps` with the frozen recipe."""
    factors = C.CELLS[cell]
    set_determinism(seed)
    m = E1F(d=C.D, vocab=T.VOCAB, factors=factors)
    opt = torch.optim.Adam(m.parameters(), lr=C.LR)
    rng = random.Random(seed ^ 0x51ED)                # identical batch stream across cells for this seed
    m.train()
    for _ in range(C.STEPS):
        idx = [rng.randrange(len(train_eps)) for _ in range(C.BATCH)]
        kt, qt, kv, ti, tv = collate([train_eps[i] for i in idx])
        K = kt.size(1)
        target = torch.where(ti >= 0, ti, torch.full_like(ti, K))
        loss = F.cross_entropy(m(kt, qt, C.TAU), target)
        opt.zero_grad(); loss.backward(); opt.step()
    return m


def factor_activity(model):
    """Report whether each enabled factor moved off its zero-initialised no-op state (learned an effect)."""
    act = {}
    if model.f1 is not None:
        act["F1"] = float(model.f1.out.weight.abs().sum().item() + model.f1.out.bias.abs().sum().item())
    if model.f2 is not None:
        act["F2"] = float(model.f2.gain.abs().item())
    if model.f3 is not None:
        act["F3"] = float(model.f3.gain.abs().item())
    return act
