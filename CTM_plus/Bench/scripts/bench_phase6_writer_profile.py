#!/usr/bin/env python3
"""bench_phase6_writer_profile.py — break down PagedKVWriter.write overhead.

Phase 6 perf polish step 1 per the user's scope:
  "profile/break down PagedKVWriter overhead"

Measures wall time of `writer.write()` at varying T (token batch sizes)
to characterize where the per-token Python loop hurts.

We measure:
  - Pure writer.write() call latency (CUDA-synced) at T in {1, 8, 64,
    256, 512} — covers single-token decode through long prefills.
  - Per-token overhead derived as (writer_time - measurement_overhead) / T.
  - Comparison vs the "ideal lower bound" — the same K/V going through
    pack_k_for_phase2_4 + pack_v_for_phase2_6 (the batched reference
    packers from Phase 2.4 / 2.6). That's what the writer *should*
    approach after vectorization.

Output:
  - Per-T table: T / writer_total_ms / per_tok_us / ref_pack_ms
  - Breakdown of the writer's last (largest) call via cProfile, sorted
    by cumtime.

Run:
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/bench_phase6_writer_profile.py
"""
from __future__ import annotations

import argparse
import cProfile
import io
import os
import pstats
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Tuple

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))

import torch


# Qwen2.5-7B shapes — match production.
H_KV = 4
D    = 128
BS   = 32                     # block_size = group_size = kInt4GroupSize
N_PROTECT = 5
V_GROUP   = 32
NUM_LAYERS = 28


def _make_protect_artifact() -> str:
    """Synthetic per-model mask: first N_PROTECT channels protected/head."""
    mask = torch.zeros((H_KV, D), dtype=torch.int8)
    for h in range(H_KV):
        mask[h, :N_PROTECT] = 1
    full = mask.unsqueeze(0).repeat(NUM_LAYERS, 1, 1)
    fd, path = tempfile.mkstemp(suffix=".pt"); os.close(fd)
    torch.save(full, path)
    os.environ["PROTECT_MASK_PATH"] = path
    return path


def _time_writer(writer, kv_cache, key, value, slot_mapping, n_warmup=2, n_runs=5):
    """Return median wall-clock ms of writer.write across n_runs."""
    times = []
    for _ in range(n_warmup):
        writer.reset_sequence()
        kv_cache.zero_()
        writer.write(key, value, kv_cache, slot_mapping)
    for _ in range(n_runs):
        writer.reset_sequence()
        kv_cache.zero_()
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        writer.write(key, value, kv_cache, slot_mapping)
        torch.cuda.synchronize()
        times.append((time.perf_counter() - t0) * 1000.0)
    times.sort()
    return times[len(times) // 2]


def _time_ref_pack(key, value, n_warmup=2, n_runs=5):
    """Time pack_k_for_phase2_4 + pack_v_for_phase2_6 on the same K/V.

    These are the batched reference packers — they represent the
    'fully vectorized' baseline the writer should approach.
    """
    from kv_policy.phase2_4_packed_kv import pack_k_for_phase2_4
    from kv_policy.phase2_6_packed_v import pack_v_for_phase2_6

    T = key.shape[0]
    if T % BS != 0:
        # pack_k requires S % group_size == 0; round T up with a padded view.
        pad = BS - (T % BS)
        k_padded = torch.cat(
            [key, torch.zeros(pad, *key.shape[1:], dtype=key.dtype, device=key.device)],
            dim=0,
        )
    else:
        k_padded = key

    k_bf = k_padded.unsqueeze(0)  # (1, S, H, D)
    v_bf = value.unsqueeze(0)

    # Use a uniform first-N protect mask for fairness.
    mask = torch.zeros((H_KV, D), dtype=torch.int8, device=key.device)
    for h in range(H_KV):
        mask[h, :N_PROTECT] = 1

    for _ in range(n_warmup):
        _ = pack_k_for_phase2_4(k_bf, group_size=BS,
                                protect_fraction=N_PROTECT / D,
                                frozen_protect_mask=mask)
        _ = pack_v_for_phase2_6(v_bf, v_group_size=V_GROUP)
    times = []
    for _ in range(n_runs):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        _ = pack_k_for_phase2_4(k_bf, group_size=BS,
                                protect_fraction=N_PROTECT / D,
                                frozen_protect_mask=mask)
        _ = pack_v_for_phase2_6(v_bf, v_group_size=V_GROUP)
        torch.cuda.synchronize()
        times.append((time.perf_counter() - t0) * 1000.0)
    times.sort()
    return times[len(times) // 2]


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-T", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    if not torch.cuda.is_available():
        print("FAIL: needs CUDA"); return 1

    from kv_policy.phase5b_4c_paged_writer import PagedKVWriter

    print("=" * 78)
    print("Phase 6 perf — PagedKVWriter overhead profile")
    print("=" * 78)
    print(f"  device:    cuda")
    print(f"  H_kv:      {H_KV}")
    print(f"  D:         {D}")
    print(f"  BS:        {BS}")
    print(f"  N_PROTECT: {N_PROTECT}")
    print()

    artifact = _make_protect_artifact()
    try:
        NB = 256                                     # 256 * 32 = 8192 slots
        kv_cache = torch.zeros((2, NB, BS, H_KV, D), dtype=torch.uint8, device="cuda")
        writer = PagedKVWriter(layer_idx=0)
        writer._lazy_alloc(kv_cache)

        # T sweep covers single-decode (T=1), small batch (T=8),
        # short prefill (T=64), medium (T=256), long (T=512).
        T_list = [1, 8, 64, 256, 512]
        T_list = [t for t in T_list if t <= args.max_T]

        torch.manual_seed(args.seed)
        # Pre-allocate at max T then slice for each.
        max_T = max(T_list)
        k_full = torch.randn((max_T, H_KV, D), dtype=torch.bfloat16, device="cuda") * 0.5
        v_full = torch.randn((max_T, H_KV, D), dtype=torch.bfloat16, device="cuda") * 0.5
        slot_full = torch.arange(max_T, dtype=torch.long, device="cuda")

        print("Per-T latency (median of 5 runs, after 2 warmups):")
        print(f"  {'T':>4} | {'writer_ms':>10} | {'per_tok_us':>11} | "
              f"{'ref_pack_ms':>11} | {'overhead_x':>10}")
        print("  " + "-" * 60)

        results: List[Tuple[int, float, float]] = []
        for T in T_list:
            k = k_full[:T]
            v = v_full[:T]
            slot = slot_full[:T]
            writer_ms = _time_writer(writer, kv_cache, k, v, slot)
            ref_ms = _time_ref_pack(k, v) if T >= BS else 0.0
            per_tok_us = writer_ms * 1000.0 / T
            overhead_x = writer_ms / ref_ms if ref_ms > 0 else float("nan")
            print(f"  {T:>4} | {writer_ms:>10.3f} | {per_tok_us:>11.2f} | "
                  f"{ref_ms:>11.3f} | {overhead_x:>10.2f}")
            results.append((T, writer_ms, ref_ms))

        # cProfile breakdown on the largest T.
        print()
        print(f"cProfile breakdown of writer.write at T={max(T_list)} (1 invocation):")
        print("-" * 78)
        writer.reset_sequence(); kv_cache.zero_()
        T_big = max(T_list)
        k = k_full[:T_big]; v = v_full[:T_big]; slot = slot_full[:T_big]
        profiler = cProfile.Profile()
        torch.cuda.synchronize()
        profiler.enable()
        writer.write(k, v, kv_cache, slot)
        torch.cuda.synchronize()
        profiler.disable()
        ps = pstats.Stats(profiler).sort_stats(pstats.SortKey.CUMULATIVE)
        buf = io.StringIO()
        ps.stream = buf
        ps.print_stats(25)
        # Filter to relevant module + just hot lines.
        for line in buf.getvalue().splitlines():
            if "phase5b_4c_paged_writer" in line or "tottime" in line \
                    or "ncalls" in line or "function calls" in line:
                print(f"  {line}")

        print()
        print("Conclusions to watch for:")
        print("  - If per_tok_us is flat across T  -> CUDA launch / Python overhead dominant.")
        print("  - If overhead_x is large (>>1)    -> writer is far from the batched-pack ideal.")
        print("  - cProfile cumtime in 'write' itself = the for-t loop body.")
        print("  - V quant + K gather + slot writes are the per-token hot spots; all are")
        print("    structurally vectorizable.")
        return 0
    finally:
        if os.path.exists(artifact):
            os.remove(artifact)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
