#!/usr/bin/env python3
"""verify_phase5b_4c_3_e2e.py — Phase 5B.4c.3 end-to-end smoke test.

Loads Qwen2.5-7B-Instruct with the int4_protected backend
(kv_cache_dtype="int4_protected", block_size=32) and runs a needle-
style generation. Confirms:

  1. Backend installs at engine init (CacheConfig accepts the dtype,
     Int4ProtectedAttentionImpl swapped in on all 28 layers).
  2. Generation produces non-empty coherent text.
  3. Decode goes through the packed kernel (decode_calls_packed > 0,
     decode_calls_fallback == 0).
  4. Write path uses PagedKVWriter (write_path_calls > 0,
     write_path_fallback == 0).
  5. Needle retrieval: model recalls the XYZ123 secret.
  6. Output diff vs stock vLLM is informational — outputs may differ
     in late tokens because of accumulated quantization drift, but
     greedy decode should agree on the early prefix.

Pre-reqs on the pod:
  - venv-vllm active.
  - vllm_flash_attn dev build with Phase 2.4.1b + 2.6.2 patches applied.
  - PROTECT_MASK_PATH env or default
    /workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt exists.

Exit 0 = GREEN, 1 = FAIL.
"""
from __future__ import annotations

import argparse
import gc
import os
import sys
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


def _find_inner_model(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
        lambda x: x.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.workers[0].model_runner.model,
    ]
    last_err = None
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None and hasattr(m, "named_modules"):
                return m
        except (AttributeError, IndexError) as e:
            last_err = e
    raise RuntimeError(f"Could not locate the inner nn.Module. Last: {last_err}")


def _run_stock_vllm(prompt, sampling, args):
    """Run the same prompt through stock vLLM (kv_cache_dtype=auto)
    for reference output diff. Returns decoded text."""
    import torch
    from vllm import LLM
    print("[1/2] Stock vLLM reference run (kv_cache_dtype=auto)")
    llm = LLM(
        model=args.model,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
        block_size=args.block_size,
        enforce_eager=True,
    )
    out = llm.generate([prompt], sampling)
    text = out[0].outputs[0].text
    del llm
    gc.collect(); torch.cuda.empty_cache()
    return text


def _run_int4_protected(prompt, sampling, args):
    """Run through the int4_protected backend. Returns (text, stats)."""
    import torch
    from vllm import LLM
    from kv_policy.phase5b_backend_install import (
        enable_int4_protected_backend,
        install_int4_protected_backend,
        count_int4_protected_impls,
        Int4ProtectedAttentionImpl,
    )

    print("[2/2] int4_protected backend run")
    enable_int4_protected_backend()
    Int4ProtectedAttentionImpl.reset_call_stats()

    llm = LLM(
        model=args.model,
        max_model_len=args.max_model_len,
        kv_cache_dtype="int4_protected",
        block_size=args.block_size,
        gpu_memory_utilization=args.gpu_memory_utilization,
        enforce_eager=True,
    )
    model = _find_inner_model(llm)
    print(f"  located inner model: {type(model).__name__}")

    # Install assigns _phase5b_layer_idx per layer (parses model.layers.<N>.
    # Idempotent — if engine init already constructed our impl class via the
    # backend selector, the class-swap loop just confirms.
    manager, teardown = install_int4_protected_backend(model)
    install_stats = manager.stats()
    print(f"  install: swapped={install_stats['swapped_impls']} "
          f"fallback={install_stats['fallback_forward_swap']} "
          f"skipped_no_impl={install_stats.get('skipped_no_impl_attr', 0)}")

    n_ours, n_total = count_int4_protected_impls(model)
    print(f"  layer impls: {n_ours}/{n_total} use Int4ProtectedAttentionImpl")

    out = llm.generate([prompt], sampling)
    text = out[0].outputs[0].text
    call_stats = Int4ProtectedAttentionImpl.get_call_stats()

    teardown()
    del llm, model
    gc.collect(); torch.cuda.empty_cache()
    return text, install_stats, call_stats, n_ours, n_total


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len",         type=int,   default=4096)
    parser.add_argument("--max-tokens",            type=int,   default=32)
    parser.add_argument("--block-size",            type=int,   default=32,
                        help="Must be 32 (kernel kInt4GroupSize constraint).")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    parser.add_argument("--no-stock-compare", action="store_true",
                        help="Skip the stock-vLLM diff run.")
    parser.add_argument("--needle", default="XYZ123",
                        help="Secret code embedded in the prompt; model must recall it.")
    args = parser.parse_args(argv)

    if args.block_size != 32:
        print(f"FAIL: --block-size must be 32 (got {args.block_size}); kernel kInt4GroupSize is 32.")
        return 1

    try:
        import torch  # noqa: F401
        from vllm import SamplingParams
    except ImportError as e:
        print(f"FAIL: import error ({e}). Run inside venv-vllm.")
        return 1

    prompt = (
        f"The secret code is {args.needle}. Repeat the secret code in the next "
        f"sentence.\nThe secret code is"
    )
    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens, stop=None)

    print("=" * 70)
    print("Phase 5B.4c.3 end-to-end verify")
    print("=" * 70)
    print(f"  model:             {args.model}")
    print(f"  max_model_len:     {args.max_model_len}")
    print(f"  block_size:        {args.block_size}")
    print(f"  gpu_mem_util:      {args.gpu_memory_utilization}")
    print(f"  needle:            {args.needle}")
    mask_path = os.environ.get(
        "PROTECT_MASK_PATH",
        "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt",
    )
    print(f"  protect_mask path: {mask_path}")
    print(f"  prompt: {prompt!r}")
    print()

    if not os.path.exists(mask_path):
        print(f"FAIL: protect_mask not found at '{mask_path}'. Run Phase 5B.0 calibration.")
        return 1

    # ----- Optional stock vLLM reference -----
    stock_text = ""
    if not args.no_stock_compare:
        stock_text = _run_stock_vllm(prompt, sampling, args)
        print(f"  stock output: {stock_text!r}")
        print()

    # ----- int4_protected run -----
    int4_text, install_stats, call_stats, n_ours, n_total = (
        _run_int4_protected(prompt, sampling, args)
    )

    print()
    print("=" * 70)
    print("Results")
    print("=" * 70)
    print(f"  int4_protected output: {int4_text!r}")
    print()
    print("  install stats:")
    for k, v in install_stats.items():
        print(f"    {k}: {v}")
    print()
    print("  call stats (across all 28 layers, summed over forward calls):")
    for k, v in call_stats.items():
        print(f"    {k}: {v}")
    print()

    # ----- Diff vs stock -----
    if stock_text and int4_text:
        common = 0
        for a, b in zip(stock_text, int4_text):
            if a != b:
                break
            common += 1
        ratio = common / max(1, min(len(stock_text), len(int4_text)))
        print(f"  stock-vs-int4_protected common prefix: {common} chars "
              f"({ratio*100:.0f}% of shorter output)")
        print()

    # ----- Gates -----
    ok = True
    reasons = []

    if not int4_text or not int4_text.strip():
        ok = False
        reasons.append("int4_protected produced empty output")

    if n_ours == 0:
        ok = False
        reasons.append(f"no layers swapped (n_ours={n_ours}/{n_total})")
    elif n_ours != n_total:
        ok = False
        reasons.append(
            f"partial layer swap: {n_ours}/{n_total} use Int4ProtectedAttentionImpl"
        )

    if call_stats["write_path_calls"] == 0:
        ok = False
        reasons.append("write_path_calls == 0 (PagedKVWriter never fired)")
    if call_stats["write_path_fallback"] > 0:
        ok = False
        reasons.append(
            f"write_path_fallback = {call_stats['write_path_fallback']} > 0"
        )

    if call_stats["decode_calls_packed"] == 0:
        ok = False
        reasons.append("decode_calls_packed == 0 (packed kernel never fired)")
    if call_stats["decode_calls_fallback"] > 0:
        ok = False
        reasons.append(
            f"decode_calls_fallback = {call_stats['decode_calls_fallback']} > 0"
        )

    # Needle test: the secret code must appear in the generated text.
    if args.needle and args.needle not in int4_text:
        ok = False
        reasons.append(f"needle {args.needle!r} not found in int4_protected output")
    elif args.needle:
        print(f"  needle {args.needle!r}: FOUND in int4_protected output ✓")

    print()
    if ok:
        print("Phase 5B.4c.3 E2E: GREEN")
        print(f"  - all {n_total}/{n_total} layers using Int4ProtectedAttentionImpl")
        print(f"  - write path: {call_stats['write_path_calls']} calls, "
              f"0 fallbacks")
        print(f"  - packed decode: {call_stats['decode_calls_packed']} calls, "
              f"0 fallbacks")
        print(f"  - needle retrieved")
        return 0

    print("Phase 5B.4c.3 E2E: FAIL")
    for r in reasons:
        print(f"  - {r}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
