"""Phase 6 v2 Option B pre-flight (B-pre-4) — pointer stability audit.

Logs the `data_ptr()` of every tensor that flows into the attention
kernel call across multiple decode steps, then reports which are
stable across calls (graph-capturable) vs which churn (need a buffer
fix before graph capture).

Why this matters:

CUDA graph capture records ADDRESSES of input tensors at capture time.
At replay time, the graph reads from those exact addresses. If a tensor
was freshly allocated per call (different address every time), the
captured graph reads from stale memory and produces garbage (or
crashes).

For graph capture (B-1) to work, every tensor passed to
flash_attn_with_int4_kvcache must be at a stable address across calls
within a given (B, n_blocks_max) shape bucket.

This audit instruments `flash_attn_with_int4_kvcache` itself (via
monkey-patching) to record each argument's data_ptr() per call. After
running a B=8 decode, it reports per-tensor:
  - n_unique_addrs: how many distinct addresses we saw across calls
  - stable: n_unique_addrs == 1 (good — captured once, replayed many)
  - churn: n_unique_addrs > 1 (bad — allocates per call, breaks capture)

Run on the pod:
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/audit_phase6_b_pre4_pointer_stability.py
"""
from __future__ import annotations

import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


PROMPT = (
    "Below is a paragraph about a small fictional town. After it, "
    "answer the question concisely.\n\n"
    "Greendell is nestled between two rivers and has a population of "
    "just over four thousand. Its main industries are pottery, honey "
    "production, and the seasonal wool trade. The annual harvest "
    "festival in early autumn draws visitors from across the region. "
    "The oldest building in town is a stone library founded in 1742.\n\n"
    "Question: What year was the oldest building in Greendell founded?\n"
    "Answer:"
)


# Per-(B, n_blocks_max) bucket -> per-arg -> list of (call_idx, data_ptr).
# We bucket by the (B, n_blocks_max) shape because graph capture also
# happens per-shape-bucket. A tensor only needs stable address WITHIN a
# bucket, not across buckets.
_KERNEL_CALL_LOG: Dict[tuple, Dict[str, List[tuple]]] = defaultdict(
    lambda: defaultdict(list),
)
_CALL_COUNT = [0]


def _install_kernel_arg_audit():
    """Monkey-patch flash_attn_with_int4_kvcache to log every argument's
    data_ptr() before forwarding to the real kernel."""
    import torch
    from vllm import vllm_flash_attn as _vfa

    orig_fn = _vfa.flash_attn_with_int4_kvcache

    def _instrumented(*args, **kwargs):
        # Positional: (query_q, bf16_k_batch, v_for_kernel)
        # Keyword: cache_seqlens, protect_mask, k_packed_*, v_packed_*, ...
        # We need B and n_blocks_max from the shapes.
        q = args[0]
        bf16_k = args[1] if len(args) > 1 else kwargs.get("k_cache")
        v_arg  = args[2] if len(args) > 2 else kwargs.get("v_cache")
        B = q.shape[0]
        S_padded = bf16_k.shape[1] if bf16_k is not None and bf16_k.dim() >= 2 else 0
        # n_blocks_max isn't passed explicitly; derive from S_padded if we
        # know BS. The packed kernel uses k_packed_int4 of shape
        # (B, S_padded, H, half_D). S_padded // BS = n_blocks_max.
        k_packed = kwargs.get("k_packed_int4")
        BS = kwargs.get("packed_group_size", 32)
        n_blocks_max = (k_packed.shape[1] // BS) if k_packed is not None else 0
        bucket = (B, n_blocks_max)

        log = _KERNEL_CALL_LOG[bucket]
        call_idx = _CALL_COUNT[0]
        _CALL_COUNT[0] += 1

        def _record(name, t):
            if t is None or not isinstance(t, torch.Tensor):
                return
            log[name].append((call_idx, t.data_ptr(), tuple(t.shape), str(t.dtype)))

        _record("query_q",                  q)
        _record("bf16_k_batch",             bf16_k)
        _record("v_for_kernel",             v_arg)
        _record("cache_seqlens",            kwargs.get("cache_seqlens"))
        _record("protect_mask",             kwargs.get("protect_mask"))
        _record("k_packed_int4",            kwargs.get("k_packed_int4"))
        _record("k_packed_scale",           kwargs.get("k_packed_scale"))
        _record("k_packed_xmin",            kwargs.get("k_packed_xmin"))
        _record("k_packed_protect_bf16",    kwargs.get("k_packed_protect_bf16"))
        _record("k_packed_protect_slot",    kwargs.get("k_packed_protect_slot"))
        _record("v_packed_int4",            kwargs.get("v_packed_int4"))
        _record("v_packed_scale",           kwargs.get("v_packed_scale"))
        _record("v_packed_xmin",            kwargs.get("v_packed_xmin"))

        return orig_fn(*args, **kwargs)

    _vfa.flash_attn_with_int4_kvcache = _instrumented
    return orig_fn


def _reset_seq_states(model):
    import torch
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    with torch.inference_mode():
        for _, sub in model.named_modules():
            impl = getattr(sub, "impl", None)
            if isinstance(impl, Int4ProtectedAttentionImpl):
                w = getattr(impl, "_phase5b_paged_writer", None)
                if w is not None:
                    w.reset_sequence("all")


def _find_inner_model(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
    ]
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None and hasattr(m, "named_modules"):
                return m
        except (AttributeError, IndexError):
            continue
    raise RuntimeError("Could not locate inner model.")


def _report():
    """Print per-(B, n_blocks_max) bucket, per-tensor stability summary."""
    print()
    print("=" * 96)
    print("Pointer stability audit — flash_attn_with_int4_kvcache arguments")
    print("=" * 96)
    if not _KERNEL_CALL_LOG:
        print("No kernel calls intercepted — was the int4_protected backend active?")
        return

    # Sort buckets by (B, n_blocks_max).
    for bucket in sorted(_KERNEL_CALL_LOG.keys()):
        B, n_blocks_max = bucket
        log = _KERNEL_CALL_LOG[bucket]
        n_calls_in_bucket = max(
            (len(v) for v in log.values()), default=0,
        )
        print()
        print(f"Bucket: B={B}, n_blocks_max={n_blocks_max}   "
              f"({n_calls_in_bucket} kernel calls)")
        print(f"  {'arg':<26} {'n_addrs':>8} {'shape':<28} "
              f"{'dtype':<12} {'status'}")
        print("  " + "-" * 90)
        for name in sorted(log.keys()):
            entries = log[name]              # list of (call_idx, ptr, shape, dtype)
            unique_addrs = sorted(set(e[1] for e in entries))
            shapes  = sorted(set(e[2] for e in entries))
            dtypes  = sorted(set(e[3] for e in entries))
            n_uniq  = len(unique_addrs)
            shape_str = str(shapes[0]) if len(shapes) == 1 else f"(varies: {len(shapes)})"
            dtype_str = dtypes[0] if len(dtypes) == 1 else f"varies"
            if n_uniq == 1:
                status = "STABLE"
            elif n_uniq <= 4:
                # Sometimes a tiny pool of addresses cycles — still bad
                # for capture but slightly different mode (e.g., 2 alternating
                # buffers from a ring allocator).
                status = f"CYCLE-{n_uniq}"
            else:
                status = "CHURN"
            print(f"  {name:<26} {n_uniq:>8} {shape_str:<28} "
                  f"{dtype_str:<12} {status}")

    print()
    print("=" * 96)
    print("Interpretation:")
    print("  STABLE   — tensor lives at the same address across all calls in")
    print("             this bucket. Graph-capturable as-is.")
    print("  CYCLE-N  — tensor rotates through a small pool of N addresses.")
    print("             Still graph-hostile (graph wants ONE address per slot).")
    print("  CHURN    — fresh allocation per call. Definitely graph-hostile.")
    print()
    print("For B-1 (graph capture enable), every CHURN/CYCLE arg needs to be")
    print("either (a) pre-allocated and written into via .copy_(), or (b)")
    print("handled by vLLM's graph capture machinery (which manages output")
    print("addresses for ops captured inside torch.cuda.graph()).")


def main():
    import argparse, torch
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",          default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len",          type=int,   default=4096)
    parser.add_argument("--max-tokens",             type=int,   default=32)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    parser.add_argument("--batch-size",             type=int,   default=8)
    parser.add_argument("--n-runs",                 type=int,   default=2)
    args = parser.parse_args()

    try:
        from vllm import SamplingParams
        import kv_policy.int4_protected
        from kv_policy.int4_protected import Int4ProtectedLLM
    except ImportError as e:
        print(f"FAIL: import error ({e})."); return 1

    mask_path = os.environ.get(
        "PROTECT_MASK_PATH",
        "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt",
    )
    if not os.path.exists(mask_path):
        print(f"FAIL: protect_mask not found at '{mask_path}'."); return 1

    print("Installing kernel-arg audit (monkey-patch on flash_attn_with_int4_kvcache)...")
    orig = _install_kernel_arg_audit()

    print(f"Loading int4_protected LLM at B={args.batch_size}...")
    llm = Int4ProtectedLLM(
        model=args.model, max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
    )
    model = _find_inner_model(llm)
    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)

    # Warmup (already collects some bucket data, but we drop it via reset).
    print("Warmup...")
    llm.generate([PROMPT], sampling)
    _reset_seq_states(model)
    _KERNEL_CALL_LOG.clear()
    _CALL_COUNT[0] = 0

    print(f"Running {args.n_runs} × B={args.batch_size} generation runs...")
    for run in range(args.n_runs):
        _reset_seq_states(model)
        llm.generate([PROMPT] * args.batch_size, sampling)
        torch.cuda.synchronize()
        print(f"  run {run+1}: kernel calls so far = {_CALL_COUNT[0]}")

    _report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
