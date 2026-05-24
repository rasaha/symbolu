#!/usr/bin/env python3
"""verify_phase5b_4b_blocks.py — Phase 5B.4b acceptance.

5B.4b: STR_DTYPE_TO_TORCH_DTYPE["int4_protected"] -> torch.uint8.
Per-block bytes halve (1 byte/elem vs bf16's 2). vLLM's BlockManager
fills the same budget with TWICE as many blocks.

NOTE — what does NOT change at this sub-sub-phase:
  - The engine-init log line "the rest of the memory reserved for KV
    Cache is X GiB" stays the same. That's `gpu_memory_utilization *
    total_HBM - non_kv_mem`; it's a budget, not a usage figure. Total
    actual ALLOCATION is also the same (vLLM fills the budget with
    blocks regardless of block size).
  - To actually shrink the reserve line: patch profile_run to advertise
    a smaller gpu_memory_utilization (separate work; likely Phase 5C
    scope).

What DOES change at 5B.4b:
  - cache_engine[0].num_gpu_blocks roughly DOUBLES (twice as many
    half-bytes blocks fit in the same budget).
  - The gpu_cache tensor dtype is now uint8 instead of bf16.

What's INTENTIONALLY BROKEN at this sub-sub-phase:
  - Generation. The C++ reshape_and_cache_flash kernel writes bf16
    K/V into uint8 storage as if it were bf16 → corrupt output.
    Phase 5B.4c replaces this with our quantizing writer.

Gates (no generation):
  1. enable_int4_protected_backend runs.
  2. LLM(kv_cache_dtype="int4_protected") constructs.
  3. cache_engine[0].gpu_cache[0] is uint8 (dtype change took effect).
  4. cache_engine[0].num_gpu_blocks >= 1.5x the stock baseline at same
     gpu_memory_utilization (informational target: 2x; using 1.5x as
     gate to allow some slack for activation memory differences).
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


def _get_cache_engine(llm):
    worker = llm.llm_engine.model_executor.driver_worker
    ce_list = getattr(worker, "cache_engine", None)
    if isinstance(ce_list, list) and ce_list:
        return ce_list[0]
    return ce_list


def _num_gpu_blocks_and_dtype(llm):
    """Return (num_gpu_blocks, gpu_cache_dtype, total_kv_bytes_GB)."""
    ce = _get_cache_engine(llm)
    if ce is None:
        return (None, None, None)
    nb = getattr(ce, "num_gpu_blocks", None)
    gpu_cache = getattr(ce, "gpu_cache", None)
    if gpu_cache and len(gpu_cache) > 0 and hasattr(gpu_cache[0], "dtype"):
        dt = gpu_cache[0].dtype
        # Total bytes across all layers.
        total = sum(t.numel() * t.element_size() for t in gpu_cache
                    if hasattr(t, "numel"))
        total_gb = total / 1024 / 1024 / 1024
    else:
        dt = None
        total_gb = None
    return (nb, dt, total_gb)


def main() -> int:
    try:
        import torch
        from vllm import LLM
    except ImportError as e:
        print(f"FAIL: {e}")
        return 1
    if not torch.cuda.is_available():
        print("FAIL: needs CUDA")
        return 1

    from kv_policy.phase5b_backend_install import (
        enable_int4_protected_backend,
        disable_int4_protected_backend,
        Int4ProtectedAttentionBackend,
    )

    print("=" * 70)
    print("Phase 5B.4b — block-count + dtype verification (no generation)")
    print("=" * 70)

    # ---- Stock baseline ---------------------------------------
    print()
    print("[stock baseline — kv_cache_dtype=auto]")
    llm_stock = LLM(
        model="Qwen/Qwen2.5-7B-Instruct", max_model_len=2048,
        gpu_memory_utilization=0.3, enforce_eager=True,
    )
    nb_stock, dt_stock, gb_stock = _num_gpu_blocks_and_dtype(llm_stock)
    print(f"  num_gpu_blocks: {nb_stock}")
    print(f"  gpu_cache[0] dtype: {dt_stock}")
    print(f"  total kv_cache bytes: {gb_stock:.3f} GB")
    del llm_stock
    import gc; gc.collect(); torch.cuda.empty_cache()

    # ---- Phase 5B.4b install ----------------------------------
    print()
    print("[Phase 5B.4b — kv_cache_dtype=int4_protected (uint8 storage)]")
    enable_int4_protected_backend()
    llm = LLM(
        model="Qwen/Qwen2.5-7B-Instruct", max_model_len=2048,
        gpu_memory_utilization=0.3, enforce_eager=True,
        kv_cache_dtype="int4_protected",
    )
    nb_5b4b, dt_5b4b, gb_5b4b = _num_gpu_blocks_and_dtype(llm)
    print(f"  num_gpu_blocks: {nb_5b4b}")
    print(f"  gpu_cache[0] dtype: {dt_5b4b}")
    print(f"  total kv_cache bytes: {gb_5b4b:.3f} GB")
    print(f"  (Generation is INTENTIONALLY skipped — reshape_and_cache_flash "
          f"would corrupt uint8 storage when writing bf16 K/V.)")
    del llm
    gc.collect(); torch.cuda.empty_cache()

    disable_int4_protected_backend()

    # ---- Compute results --------------------------------------
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"  stock:        {nb_stock} blocks × {dt_stock} = {gb_stock:.3f} GB")
    print(f"  5B.4b:        {nb_5b4b} blocks × {dt_5b4b} = {gb_5b4b:.3f} GB")

    if nb_stock and nb_5b4b:
        ratio = nb_5b4b / nb_stock
        print(f"  block ratio:  {ratio:.2f}x  (target ~2x, gate ≥1.5x)")
    else:
        ratio = 0.0
        print("  block ratio: could not compute (missing num_gpu_blocks)")

    print()
    test1 = (dt_5b4b == torch.uint8)
    print(f"  [{'PASS' if test1 else 'FAIL'}] gpu_cache dtype is uint8 "
          f"(got {dt_5b4b})")

    test2 = (ratio >= 1.5)
    print(f"  [{'PASS' if test2 else 'FAIL'}] num_blocks ratio ≥ 1.5x "
          f"(got {ratio:.2f}x)")

    # The total kv_cache_bytes should be similar (vLLM fills the budget).
    if gb_stock and gb_5b4b:
        bytes_ratio = gb_5b4b / gb_stock
        print(f"  total kv bytes ratio: {bytes_ratio:.2f}x  "
              f"(expected ~1.0x — vLLM fills the budget either way)")

    all_ok = test1 and test2
    print()
    if all_ok:
        print("Phase 5B.4b: GREEN")
        print("  (per-block size halved; capacity doubled.")
        print("   Reserve LINE unchanged because budget = gpu_memory_utilization*HBM.")
        print("   Generation correctness comes in Phase 5B.4c.)")
        return 0
    print("Phase 5B.4b: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
