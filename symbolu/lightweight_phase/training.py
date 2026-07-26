"""
training.py — Stage 7 training/validation harness (A vs B).

Synthetic "distant fact recall" (associative recall) task designed to isolate the
Phase contribution. Token ranges are disjoint so associations are unambiguous:

    id 0                          : reserved / pad
    [1 .. F]                      : FILLER symbols (noise; never keys or values)
    [F+1 .. F+K]                  : KEY symbols
    [F+K+1 .. F+2K]               : VALUE symbols
    F+2K+1                        : QUERY marker

Each example:  KEY VALUE  filler×gap  QUERY KEY   → predict VALUE at the last KEY.
When ``gap`` exceeds the local window, only a global memory (Phase) can bridge it;
local attention alone cannot. A near-gap variant (gap < window) is the control:
both configs should solve it, so a B−A difference on the far variant is
attributable to Phase, not to general capacity.

Two configurations share tokenizer, generator, parameter budget, optimizer,
schedule, seeds, and hardware:
    A. Sliding window only     (Phase path hard-disabled: alpha_phase = 0, frozen)
    B. Sliding window + Phase  (alpha_phase learnable, init 1.0)

Deliberately small so it runs on CPU. The full multi-seed real-corpus study is
out of scope here and is reported as deferred; ``run_ab`` returns real,
reproducible numbers at the tested scale.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Dict, List, Tuple

import torch

from .config import PhaseConfig, TransformerConfig
from .phase_block import LightweightPhaseTransformerLM


@dataclass
class TaskSpec:
    n_filler: int = 16
    n_keys: int = 8
    seq_len: int = 48
    local_window: int = 8
    far_gap: int = 20          # > local_window  → needs Phase
    near_gap: int = 3          # < local_window  → local can solve (control)

    @property
    def vocab_size(self) -> int:
        return 1 + self.n_filler + 2 * self.n_keys + 1

    @property
    def key_lo(self) -> int:
        return 1 + self.n_filler

    @property
    def val_lo(self) -> int:
        return 1 + self.n_filler + self.n_keys

    @property
    def query_marker(self) -> int:
        return self.vocab_size - 1


def make_batch(spec: TaskSpec, batch: int, gap: int, gen: torch.Generator):
    """Return (ids [B,N], target_pos [B], target_val [B]).

    Predict VALUE from the logits at the second KEY occurrence.
    """
    N = spec.seq_len
    # Fillers only (disjoint from keys/values), then implant the fact + query.
    ids = torch.randint(1, 1 + spec.n_filler, (batch, N), generator=gen)
    target_pos = torch.empty(batch, dtype=torch.long)
    target_val = torch.empty(batch, dtype=torch.long)
    for b in range(batch):
        key = spec.key_lo + torch.randint(0, spec.n_keys, (1,), generator=gen).item()
        val = spec.val_lo + torch.randint(0, spec.n_keys, (1,), generator=gen).item()
        start = torch.randint(0, max(1, N - gap - 4), (1,), generator=gen).item()
        ids[b, start] = key
        ids[b, start + 1] = val
        q = start + 2 + gap
        q = min(q, N - 2)
        ids[b, q] = spec.query_marker
        ids[b, q + 1] = key
        target_pos[b] = q + 1
        target_val[b] = val
    return ids, target_pos, target_val


@dataclass
class ABResult:
    config: str
    final_loss: float
    far_acc: float
    near_acc: float


def _build_model(spec: TaskSpec, use_phase: bool, seed: int) -> LightweightPhaseTransformerLM:
    torch.manual_seed(seed)
    tcfg = TransformerConfig(
        vocab_size=spec.vocab_size,
        phase=PhaseConfig(embed_dim=48, num_heads=4),
        num_layers=2, max_seq_len=spec.seq_len,
        use_local_window=True, local_window_size=spec.local_window,
        phase_alpha_init=1.0 if use_phase else 0.0,
    )
    model = LightweightPhaseTransformerLM(tcfg)
    if not use_phase:
        for blk in model.blocks:
            blk.alpha_phase.data.zero_()
            blk.alpha_phase.requires_grad_(False)
    return model


@torch.no_grad()
def _accuracy(model, spec, gap, gen, n=256) -> float:
    model.eval()
    ids, tpos, tval = make_batch(spec, n, gap, gen)
    logits, _ = model(ids)
    pred = logits[torch.arange(n), tpos].argmax(-1)
    return (pred == tval).float().mean().item()


def train_one(spec: TaskSpec, use_phase: bool, seed: int, steps: int = 400,
              batch: int = 64, lr: float = 3e-3) -> ABResult:
    gen = torch.Generator().manual_seed(1000 + seed)
    model = _build_model(spec, use_phase, seed)
    opt = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=lr)
    model.train()
    last = 0.0
    for step in range(steps):
        # train on the far task (the one that requires Phase)
        ids, tpos, tval = make_batch(spec, batch, spec.far_gap, gen)
        logits, _ = model(ids)
        loss = torch.nn.functional.cross_entropy(
            logits[torch.arange(batch), tpos], tval)
        opt.zero_grad(); loss.backward(); opt.step()
        last = loss.item()
    eg = torch.Generator().manual_seed(9999 + seed)
    far = _accuracy(model, spec, spec.far_gap, eg)
    near = _accuracy(model, spec, spec.near_gap, eg)
    return ABResult("B" if use_phase else "A", last, far, near)


def run_ab(spec: TaskSpec | None = None, seeds: List[int] = (0, 1, 2),
           steps: int = 400) -> Dict:
    spec = spec or TaskSpec()
    rows = []
    for s in seeds:
        a = train_one(spec, use_phase=False, seed=s, steps=steps)
        b = train_one(spec, use_phase=True, seed=s, steps=steps)
        rows.append({"seed": s,
                     "A_far": a.far_acc, "B_far": b.far_acc,
                     "A_near": a.near_acc, "B_near": b.near_acc,
                     "A_loss": a.final_loss, "B_loss": b.final_loss})
    a_far = [r["A_far"] for r in rows]; b_far = [r["B_far"] for r in rows]
    agg = {
        "A_far_mean": statistics.mean(a_far),
        "B_far_mean": statistics.mean(b_far),
        "B_minus_A_far": statistics.mean(b_far) - statistics.mean(a_far),
        "A_near_mean": statistics.mean(r["A_near"] for r in rows),
        "B_near_mean": statistics.mean(r["B_near"] for r in rows),
        "chance": 1.0 / spec.n_keys,
        "seeds": list(seeds), "steps": steps,
    }
    return {"rows": rows, "aggregate": agg, "spec": spec.__dict__}
