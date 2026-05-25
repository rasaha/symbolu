#!/usr/bin/env python3
"""bench_phase6_decode_profile.py — break down per-decode-step overhead.

Post-vectorization (commit 382db51) the writer is at the batched-pack
lower bound (1.14x of pack_k+pack_v at T=512). Bench shows int4_proto
decode_tps now sits at ~21.5 tok/s uniformly regardless of prompt
length — meaning the bottleneck has shifted from the WRITE path to the
DECODE READ path. Per-step latency is ~45 ms vs bf16 ~12 ms, so the
33 ms gap = ~1.18 ms per layer x 28 layers of Python orchestration in
_read_decode_packed (gather + splice + kernel call dispatch).

This script breaks down a single decode step's per-layer time across
the four phases:
  A. paged-block gather   (writer.get_packed_view)
  B. K-tail splice        (_splice_k_partial_tail when needed)
  C. bf16 backing slice   (writer.get_bf16_backing_slice)
  D. flash_attn_with_int4_kvcache call

Same fixture as verify_phase5b_4c_2_read T1: S=512 tokens cached,
one new decode query, packed kernel call. Measures wall time per
phase across N=200 iterations.

Run:
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/bench_phase6_decode_profile.py
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import List

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))

import torch


NUM_LAYERS = 28
H_KV       = 4
H_Q        = 28
D          = 128
BS         = 32
N_PROTECT  = 5
V_GROUP    = 32


def _make_protect_artifact() -> str:
    mask = torch.zeros((H_KV, D), dtype=torch.int8)
    for h in range(H_KV):
        mask[h, :N_PROTECT] = 1
    full = mask.unsqueeze(0).repeat(NUM_LAYERS, 1, 1)
    fd, path = tempfile.mkstemp(suffix=".pt"); os.close(fd)
    torch.save(full, path)
    os.environ["PROTECT_MASK_PATH"] = path
    return path


def _median_ms(times: List[float]) -> float:
    s = sorted(times)
    return s[len(s) // 2] * 1000.0


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-iters", type=int, default=200,
                        help="iterations per phase for timing.")
    parser.add_argument("--cache-tokens", type=int, default=512,
                        help="how many tokens of cache to populate.")
    args = parser.parse_args(argv)

    if not torch.cuda.is_available():
        print("FAIL: needs CUDA"); return 1

    from kv_policy.phase5b_4c_paged_writer import PagedKVWriter
    from kv_policy.phase5b_backend_install import _splice_k_partial_tail

    try:
        from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache
    except ImportError as e:
        print(f"FAIL: {e}"); return 1

    print("=" * 78)
    print("Phase 6 decode-step profile (post-vectorization)")
    print("=" * 78)
    print(f"  cache_tokens: {args.cache_tokens}")
    print(f"  iters:        {args.n_iters}")
    print(f"  H_q={H_Q}  H_kv={H_KV}  D={D}  BS={BS}")
    print()

    art = _make_protect_artifact()
    try:
        NB = max(16, args.cache_tokens // BS + 4)
        kv_cache = torch.zeros((2, NB, BS, H_KV, D), dtype=torch.uint8, device="cuda")
        writer = PagedKVWriter(layer_idx=0)
        writer._lazy_alloc(kv_cache)

        # Populate the cache with cache_tokens worth of K/V via the writer.
        torch.manual_seed(42)
        S = args.cache_tokens
        k_full = torch.randn((S, H_KV, D), dtype=torch.bfloat16, device="cuda") * 0.5
        v_full = torch.randn((S, H_KV, D), dtype=torch.bfloat16, device="cuda") * 0.5
        slot_mapping = torch.arange(S, dtype=torch.long, device="cuda")
        writer.write(k_full, v_full, kv_cache, slot_mapping)

        # Query for the decode step (1 new token).
        q = torch.randn((1, 1, H_Q, D), dtype=torch.bfloat16, device="cuda")
        cache_seqlens = torch.tensor([S], dtype=torch.int32, device="cuda")
        n_blocks_used = (S + BS - 1) // BS
        block_ids = torch.arange(n_blocks_used, dtype=torch.long, device="cuda")

        # ----- Phase A: paged-block gather (writer.get_packed_view) -----
        def phase_A():
            return writer.get_packed_view(block_ids, kv_cache)

        # ----- Phase B: K-tail splice (only when seqlen % BS != 0) -----
        def phase_B(view):
            if (S % BS) != 0:
                _splice_k_partial_tail(view, writer, last_block_idx=n_blocks_used - 1)

        # ----- Phase C: bf16 backing slice -----
        S_view = n_blocks_used * BS
        def phase_C():
            return writer.get_bf16_backing_slice(S_view)

        # ----- Phase D: flash_attn_with_int4_kvcache call -----
        view = writer.get_packed_view(block_ids, kv_cache)
        if (S % BS) != 0:
            _splice_k_partial_tail(view, writer, last_block_idx=n_blocks_used - 1)
        bf_k, bf_v = writer.get_bf16_backing_slice(S_view)
        protect_mask_bhd = writer.protect_mask.unsqueeze(0)

        def phase_D():
            return flash_attn_with_int4_kvcache(
                q, bf_k, bf_v,
                cache_seqlens=cache_seqlens,
                protect_mask=protect_mask_bhd,
                n_protect=writer.n_protect,
                softmax_scale=None,
                causal=False,
                k_packed_int4=view["k_int4"].contiguous(),
                k_packed_scale=view["k_scale"].contiguous(),
                k_packed_xmin=view["k_xmin"].contiguous(),
                k_packed_protect_bf16=view["k_protect_bf16"].contiguous(),
                k_packed_protect_slot=view["protect_slot"].contiguous(),
                packed_group_size=BS, packed_n_protect=writer.n_protect,
                v_packed_int4=view["v_int4"].contiguous(),
                v_packed_scale=view["v_scale"].contiguous(),
                v_packed_xmin=view["v_xmin"].contiguous(),
                v_packed_group_size=writer.v_group_size,
            )

        # Time each phase independently.
        phases = [
            ("A_gather_paged_view ", phase_A),
            ("B_splice_k_tail     ", lambda: phase_B(view)),
            ("C_bf16_backing_slice", phase_C),
            ("D_packed_kernel_call", phase_D),
        ]

        # Warmup.
        for _, fn in phases:
            for _ in range(5):
                fn()
        torch.cuda.synchronize()

        results = []
        for name, fn in phases:
            times = []
            for _ in range(args.n_iters):
                torch.cuda.synchronize()
                t0 = time.perf_counter()
                fn()
                torch.cuda.synchronize()
                times.append(time.perf_counter() - t0)
            median_ms = _median_ms(times)
            results.append((name, median_ms))

        print(f"  {'phase':<24} | {'median_ms':>10} | {'per_layer_us':>14}")
        print("  " + "-" * 60)
        total_ms = 0.0
        for name, ms in results:
            per_layer_us = ms * 1000.0  # this is 1 layer's time, so * 1000 to us
            total_ms += ms
            print(f"  {name} | {ms:>10.4f} | {per_layer_us:>14.2f}")
        print("  " + "-" * 60)
        print(f"  {'TOTAL (1 layer)':<24} | {total_ms:>10.4f} | {total_ms*1000:>14.2f}")
        print(f"  {'EXTRAPOLATED 28 layers':<24} | {total_ms*28:>10.4f} | "
              f"{total_ms*28000:>14.2f}")

        print()
        print("Reading:")
        print("  - 'per_layer_us' is the time for ONE LAYER's worth of that phase.")
        print("  - Real decode step runs 28 layers sequentially; multiply by 28 for")
        print("    the per-decode-step contribution from that phase.")
        print("  - vLLM decode steps also include the model's qkv proj, mlp,")
        print("    layernorm, etc. — measured per_decode_step ~45 ms total at")
        print("    int4_proto, ~12 ms at bf16.")
        print()
        print("  Bottleneck signal: the phase with the largest per_layer_us is the")
        print("  one to vectorize / fuse next. Likely candidates:")
        print("    - A_gather_paged_view  (advanced indexing + .contiguous + .view)")
        print("    - D_packed_kernel_call (kernel work itself; harder to shrink)")
        return 0
    finally:
        if os.path.exists(art):
            os.remove(art)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
