#!/usr/bin/env python3
"""Readout-only training on a FROZEN temporal-E1 encoder. The optimizer receives ONLY readout parameters;
every base parameter stays frozen (requires_grad=False) and its hash is verified unchanged before/after.
Same loss / batch size / optimizer family / lr / step count as the frozen C1 recipe; identical per-seed
batch stream across arms. R0 has no parameters and is not trained."""
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
from temporal_train import collate, set_determinism   # noqa: E402

import readout_config as C            # noqa: E402
from readout_model import Readout, build_frozen_encoder   # noqa: E402

torch.set_num_threads(4)


def _hash_params(named):
    h = hashlib.sha256()
    for n, p in sorted(named):
        h.update(n.encode()); h.update(p.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def param_hash(model):
    return _hash_params(list(model.named_parameters()))


def readout_hash(model):
    return _hash_params(model.readout_named_parameters())


def base_hash(model):
    return _hash_params([(n, p) for n, p in model.named_parameters() if n.startswith("enc.")])


def train_readout(enc, arm, train_eps, seed):
    """Train the readout `arm` on the frozen `enc`. Returns (model, base_hash_before, base_hash_after)."""
    set_determinism(seed)
    m = Readout(enc, arm)
    b_before = base_hash(m)
    if arm == "R0":                                   # no parameters to train
        return m, b_before, base_hash(m)
    params = [p for _, p in m.readout_named_parameters()]
    opt = torch.optim.Adam(params, lr=C.LR)
    rng = random.Random(seed ^ 0x51ED)                # identical batch stream across arms for this seed
    m.train(); m.enc.eval()                           # keep frozen encoder in eval mode
    for _ in range(C.STEPS):
        idx = [rng.randrange(len(train_eps)) for _ in range(C.BATCH)]
        kt, qt, kv, ti, tv = collate([train_eps[i] for i in idx])
        K = kt.size(1)
        target = torch.where(ti >= 0, ti, torch.full_like(ti, K))
        loss = F.cross_entropy(m(kt, qt), target)
        opt.zero_grad(); loss.backward(); opt.step()
    return m, b_before, base_hash(m)


def readout_activity(model):
    """Magnitude of trained readout weights (must be off the initial state and non-degenerate)."""
    if model.arm == "R0":
        return {"sum_abs": 0.0}
    return {"sum_abs": float(sum(p.abs().sum().item() for _, p in model.readout_named_parameters()))}
