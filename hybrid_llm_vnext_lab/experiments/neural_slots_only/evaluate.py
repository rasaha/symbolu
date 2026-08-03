"""Evaluation + causal ablations for the slots-only (S) arm. Requires torch at call time.

Mirrors the historical eval suite (needle by distance, binding by k, supersession, source,
multihop, ppl) and adds the extended S ablations. Ablations that the incubated (byte-identical)
BindingSlots supports natively are used directly; the extended ones (write_gate_zero,
slot_keys_randomized) are applied via a thin wrapper that does NOT modify the incubated class.
"""
from __future__ import annotations

import math

import torch
import torch.nn.functional as F

import tasks_adapter as TA


@torch.no_grad()
def _ppl(model, stream, N, n=20, seed=0):
    model.eval(); rng = __import__("random").Random(seed); tot = 0.0
    for _ in range(n):
        x, y, _ = TA.lm_batch(stream, 8, N, rng)
        lo = model(x)
        tot += F.cross_entropy(lo.reshape(-1, lo.size(-1)), y.reshape(-1)).item()
    return math.exp(tot / n)


@torch.no_grad()
def _acc(model, X, P, Tg, bs=50):
    model.eval(); c = 0
    for i in range(0, len(X), bs):
        lo = model(X[i:i + bs])
        pred = lo[torch.arange(len(X[i:i + bs])), P[i:i + bs] - 1].argmax(-1)
        c += (pred == Tg[i:i + bs]).sum().item()
    return c / len(X)


@torch.no_grad()
def _supersession(model, X, P, Tg, stale, bs=50):
    model.eval(); cur = 0; st = 0
    for i in range(0, len(X), bs):
        lo = model(X[i:i + bs])
        pred = lo[torch.arange(len(X[i:i + bs])), P[i:i + bs] - 1].argmax(-1)
        cur += (pred == Tg[i:i + bs]).sum().item()
        st += (pred == stale[i:i + bs]).sum().item()
    return cur / len(X), st / len(X)


def eval_suite(model, vocab, stream):
    out = {"ppl": {str(N): _ppl(model, stream, N) for N in [256, 512]}, "needle_by_dist": {}}
    for dist in [16, 96, 220]:
        X, P, Tg, _ = TA.make_eval_set('needle', 256, vocab, 123, n=120, distance=dist)
        out["needle_by_dist"][str(dist)] = _acc(model, X, P, Tg)
    out["binding_by_k"] = {}
    for k in [2, 4, 8]:
        X, P, Tg, _ = TA.make_eval_set('binding', 256, vocab, 124, n=120, k=k)
        out["binding_by_k"][str(k)] = _acc(model, X, P, Tg)
    X, P, Tg, stale = TA.make_eval_set('supersession', 256, vocab, 128, n=120)
    cur, ste = _supersession(model, X, P, Tg, stale)
    out["supersession"] = {"current_acc": cur, "stale_error": ste}
    X, P, Tg, _ = TA.make_eval_set('multihop', 256, vocab, 125, n=120)
    out["multihop"] = _acc(model, X, P, Tg)
    X, P, Tg, _ = TA.make_eval_set('source', 256, vocab, 129, n=120)
    out["source"] = _acc(model, X, P, Tg)
    return out


def _set_ablate(slots, mode):
    for sm in slots:
        sm.ablate = mode


def s_ablations(model, vocab):
    """S-arm causal ablations on needle@d96. Native modes + extended (write-gate/keys)."""
    Xn, Pn, Tn, _ = TA.make_eval_set('needle', 256, vocab, 123, n=120, distance=96)
    slots = model.slot_mixers()
    res = {}

    def probe():
        return _acc(model, Xn, Pn, Tn)

    res["baseline"] = probe()
    if not slots:
        return res
    # native ablations supported by the incubated BindingSlots
    _set_ablate(slots, 'zero');         res["slots_off"] = probe()
    _set_ablate(slots, 'rand_keys');    res["randomized_address"] = probe()
    _set_ablate(slots, 'shuffle_val');  res["shuffle_values"] = probe()
    _set_ablate(slots, None)

    # extended ablations applied without modifying the incubated class:
    # write_gate_zero: force the write gate bias to -inf-equivalent by zeroing gate weight+bias
    saved = []
    for sm in slots:
        saved.append((sm.gate.weight.detach().clone(), sm.gate.bias.detach().clone()))
        with torch.no_grad():
            sm.gate.weight.zero_(); sm.gate.bias.fill_(-30.0)   # sigmoid(-30) ~ 0 -> no writes
    res["write_gate_zero"] = probe()
    for sm, (w, b) in zip(slots, saved):
        with torch.no_grad():
            sm.gate.weight.copy_(w); sm.gate.bias.copy_(b)

    # slot_keys_randomized: replace learned slot address keys with random unit vectors
    saved_keys = []
    for sm in slots:
        saved_keys.append(sm.slot_keys.detach().clone())
        with torch.no_grad():
            rk = torch.randn_like(sm.slot_keys)
            sm.slot_keys.copy_(F.normalize(rk, dim=-1))
    res["slot_keys_randomized"] = probe()
    for sm, k in zip(slots, saved_keys):
        with torch.no_grad():
            sm.slot_keys.copy_(k)

    res["slot_diagnostics"] = [sm.diag for sm in slots if hasattr(sm, "diag")]
    return res
