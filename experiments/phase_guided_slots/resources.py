"""resources.py — no-quadratic proof + resource measurement for the guided arms."""

from __future__ import annotations

import time
from typing import Dict

import torch

from .guided_models import GCfg, build, ARMS
from .guided_slots import GuidedBoundedSlots
from symbolu.lightweight_phase.invariants import shape_audit


def no_quadratic(cfg: GCfg, arm: str, seq_lens=(64, 128, 256)) -> Dict:
    m = build(cfg, arm, 0).eval()
    peaks = {}
    for N in seq_lens:
        ids = torch.randint(0, cfg.vocab_size, (1, N))
        apos = torch.tensor([N - 1])
        with shape_audit(seq_len=N) as audit:   # raises on any two-sequence-axis tensor
            with torch.no_grad():
                m(ids, apos)
        peaks[N] = audit.peak_numel()
    return peaks


@torch.no_grad()
def latency(cfg: GCfg, arm: str, N=128, repeats=3) -> Dict:
    m = build(cfg, arm, 0).eval()
    ids = torch.randint(0, cfg.vocab_size, (1, N)); apos = torch.tensor([N - 1])
    m(ids, apos)
    t0 = time.time()
    for _ in range(repeats):
        m(ids, apos)
    dt = (time.time() - t0) / repeats
    return {"latency_ms": dt * 1000, "tokens_per_sec": N / dt}


def state_sizes(cfg: GCfg) -> Dict:
    # slot state O(M*D): keys(M*Ds)+values(M*D)+retain/usage/active(3M)
    slot = cfg.num_slots * (cfg.slot_key_dim + cfg.embed_dim) + 3 * cfg.num_slots
    H, Dh = cfg.num_heads, cfg.embed_dim // cfg.num_heads
    phase = 2 * H * Dh
    return {"phase_state_numel": phase, "slot_state_numel": slot}


def full_report(cfg: GCfg) -> Dict:
    rep = {"state_sizes": state_sizes(cfg), "arms": {}}
    for arm in ARMS:
        m = build(cfg, arm, 0)
        rep["arms"][arm] = {
            "params": m.num_parameters(),
            "no_quadratic_peak_numel": no_quadratic(cfg, arm),
            "latency_128": latency(cfg, arm),
        }
    return rep
