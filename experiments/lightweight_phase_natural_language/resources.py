"""
resources.py — resource + no-quadratic measurements per arm and context length.

Reports parameter counts, recurrent/slot state sizes, latency, throughput, peak
CPU memory, and runtime scaling with sequence length. Also provides the
no-quadratic proof by (a) running every arm under the frozen shape audit (raises
on any two-sequence-axis tensor) and (b) measuring that peak intermediate element
count and wall-time scale ~linearly, not quadratically, in N.
"""

from __future__ import annotations

import time
import tracemalloc
from typing import Dict, List

import torch

from .models import ExperimentLM, ModelConfig, build_model, ARMS
from symbolu.lightweight_phase.invariants import shape_audit


def no_quadratic_audit(model: ExperimentLM, seq_lens=(64, 128, 256)) -> Dict:
    """Run each length under the shape audit; return peak intermediate numel per N."""
    out = {}
    model.eval()
    for N in seq_lens:
        ids = torch.randint(0, model.cfg.vocab_size, (1, N))
        with shape_audit(seq_len=N) as audit:  # raises InvariantViolation on N×N
            with torch.no_grad():
                model(ids)
        out[N] = audit.peak_numel()
    return out


def state_sizes(model: ExperimentLM) -> Dict:
    cfg = model.cfg
    H, Dh = cfg.num_heads, cfg.embed_dim // cfg.num_heads
    per_layer_phase = 0
    per_layer_slot = 0
    for blk in model.blocks:
        if getattr(blk.spec, "use_phase", False):
            # complex_memory [H,Dh] + amplitude_sum [H,Dh] per batch element
            per_layer_phase = 2 * H * Dh
        if getattr(blk.spec, "use_slots", False):
            s = blk.slots
            per_layer_slot = s.num_slots * (s.Ds + s.Dv) + 4 * s.num_slots
    return {
        "phase_state_numel_per_layer_per_seq": per_layer_phase,
        "slot_state_numel_per_layer_per_seq": per_layer_slot,
        "num_layers": cfg.num_layers,
        "phase_state_total_per_seq": per_layer_phase * cfg.num_layers,
        "slot_state_total_per_seq": per_layer_slot * cfg.num_layers,
    }


@torch.no_grad()
def latency_throughput(model: ExperimentLM, N: int = 256, batch: int = 1,
                       repeats: int = 5) -> Dict:
    model.eval()
    ids = torch.randint(0, model.cfg.vocab_size, (batch, N))
    model(ids)  # warmup
    t0 = time.time()
    for _ in range(repeats):
        model(ids)
    dt = (time.time() - t0) / repeats
    return {
        "seq_len": N, "batch": batch,
        "forward_latency_ms": dt * 1000,
        "tokens_per_sec": batch * N / dt,
    }


@torch.no_grad()
def peak_memory(model: ExperimentLM, N: int = 256) -> Dict:
    model.eval()
    ids = torch.randint(0, model.cfg.vocab_size, (1, N))
    tracemalloc.start()
    model(ids)
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"seq_len": N, "peak_python_mem_mb": peak / 1e6}


def runtime_scaling(model: ExperimentLM, seq_lens=(128, 256, 512, 1024)) -> Dict:
    out = {}
    for N in seq_lens:
        out[N] = latency_throughput(model, N=N, batch=1, repeats=3)["forward_latency_ms"]
    # scaling exponent estimate between smallest and largest
    ns = sorted(out)
    import math
    lo, hi = ns[0], ns[-1]
    expo = math.log(out[hi] / out[lo]) / math.log(hi / lo) if out[lo] > 0 else float("nan")
    return {"latency_ms_by_N": out, "scaling_exponent": expo}


def full_resource_report(cfg: ModelConfig, seeds=(0,), seq_lens=(128, 256, 512)) -> Dict:
    report = {}
    for arm in ARMS:
        m = build_model(cfg, arm, seed=0).eval()
        report[arm] = {
            "params": m.num_parameters(),
            "state_sizes": state_sizes(m),
            "no_quadratic_peak_numel": no_quadratic_audit(m, seq_lens=seq_lens),
            "runtime_scaling": runtime_scaling(m, seq_lens=seq_lens),
            "latency_256": latency_throughput(m, N=256),
            "peak_mem_256": peak_memory(m, N=256),
        }
    return report
