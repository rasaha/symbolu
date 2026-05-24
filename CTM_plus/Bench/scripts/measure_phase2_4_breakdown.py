#!/usr/bin/env python3
"""measure_phase2_4_breakdown.py — deep memory + per-token timing breakdown.

Goes beyond `measure_phase2_4_memory.py` by:
  1. Walking the llm object tree to find ALL large CUDA tensors (so we
     catch vLLM's paged KV cache wherever it actually lives — earlier
     probe missed it).
  2. Categorizing tensors as model weights / paged-K / paged-V /
     wrapper-K-sidecar / wrapper-V-sidecar / packed-* / other.
  3. Per-token timing via instrumented manager.time_block (added to
     phase5a_native_install.py and phase2_4_native_install.py).

Reports per the user's request:
  - vLLM paged BF16 K memory
  - vLLM paged BF16 V memory
  - packed INT4 K sidecar memory
  - protected-K BF16 sidecar memory
  - scale/xmin memory
  - k_fp16 staging sidecar memory
  - total peak GPU memory vs stock
  - per-token timing: full-K repack, cache.append, packed kernel, total decode

Decision rule:
  - vLLM paged BF16 K dominates → Phase 2.4.b is the priority
  - repack dominates           → Phase 2.4.1d is the priority
  - cache.append dominates     → Phase 5B native cache write is the priority
  - kernel dominates           → profile CUDA before integration

~5 min runtime (3 sequential vLLM loads + short generate each).
"""
from __future__ import annotations
import argparse
import gc
import json
import sys
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


def _bytes_mb(n: int) -> float:
    return n / 1024 / 1024


def _bytes_gb(n: int) -> float:
    return n / 1024 / 1024 / 1024


def _find_inner(llm):
    """Return the driver_worker (or whatever holds cache_engine + model_runner)."""
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker,
        lambda x: x.model_executor.driver_worker,
        lambda x: x.llm_engine.model_executor.workers[0],
    ]
    for fn in candidates:
        try:
            w = fn(llm)
            if w is not None:
                return w
        except (AttributeError, IndexError):
            pass
    return None


def deep_tensor_walk(root, max_depth: int = 8) -> list:
    """Walk an object tree finding all CUDA tensors >= 1 MB. Returns
    list of {path, shape, dtype, bytes}."""
    import torch
    out = []
    visited_ids: set = set()

    def walk(obj, path, depth):
        if depth > max_depth:
            return
        oid = id(obj)
        if oid in visited_ids:
            return
        # Don't visit huge generic objects twice.
        if isinstance(obj, (torch.Tensor, list, tuple, dict)):
            visited_ids.add(oid)
        if isinstance(obj, torch.Tensor):
            if obj.is_cuda:
                nbytes = obj.numel() * obj.element_size()
                if nbytes >= 1024 * 1024:  # >= 1 MB
                    out.append({
                        "path":  path,
                        "shape": tuple(obj.shape),
                        "dtype": str(obj.dtype).replace("torch.", ""),
                        "bytes": nbytes,
                    })
            return
        if isinstance(obj, (list, tuple)):
            for i, x in enumerate(obj):
                walk(x, f"{path}[{i}]", depth + 1)
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, f"{path}[{k!r}]", depth + 1)
            return
        # Object: walk public attributes.
        if hasattr(obj, "__dict__") or hasattr(obj, "__slots__"):
            for name in dir(obj):
                if name.startswith("_"):
                    continue
                # Skip known noisy attrs.
                if name in ("dtype", "device", "shape", "T", "data",
                            "grad", "grad_fn", "real", "imag"):
                    continue
                try:
                    v = getattr(obj, name)
                except Exception:
                    continue
                if callable(v):
                    continue
                if isinstance(v, (torch.Tensor, list, tuple, dict)):
                    walk(v, f"{path}.{name}", depth + 1)

    walk(root, "root", 0)
    return out


def _categorize(path: str, shape: tuple, dtype: str) -> str:
    """Heuristic categorization based on path/shape/dtype."""
    p = path.lower()
    if "k_fp16" in p:        return "wrapper_k_fp16"
    if "v_fp16" in p:        return "wrapper_v_fp16"
    if "k_int4" in p or "k_packed_int4" in p: return "packed_k_int4"
    if "k_scale" in p or "k_packed_scale" in p: return "packed_k_scale"
    if "k_xmin" in p or "k_packed_xmin" in p:   return "packed_k_xmin"
    if "k_protect" in p:     return "packed_k_protect_bf16"
    if "protect_slot" in p:  return "packed_protect_slot"
    if "protect_mask" in p:  return "wrapper_protect_mask"
    if "gpu_cache" in p or "kv_cache" in p:
        # vLLM paged cache. Layout (vLLM 0.7.x) typically:
        # (2, num_blocks, block_size, num_kv_heads, head_dim)
        # where leading 2 is K/V. Hard to split K vs V from shape alone
        # without unpacking the leading dim — label as combined for now.
        return "vllm_paged_kv"
    if "weight" in p or "weights" in p or "embed" in p:
        return "model_weights"
    if "buffer" in p:
        return "buffer"
    return "other"


def _summarize_categories(tensors: list) -> dict:
    by_cat: dict = {}
    for t in tensors:
        cat = _categorize(t["path"], t["shape"], t["dtype"])
        by_cat.setdefault(cat, {"bytes": 0, "count": 0, "examples": []})
        by_cat[cat]["bytes"] += t["bytes"]
        by_cat[cat]["count"] += 1
        if len(by_cat[cat]["examples"]) < 3:
            by_cat[cat]["examples"].append({
                "path":  t["path"],
                "shape": t["shape"],
                "dtype": t["dtype"],
                "bytes": t["bytes"],
            })
    return by_cat


def _snapshot(label: str) -> dict:
    import torch
    return {
        "label":            label,
        "max_allocated_GB": _bytes_gb(torch.cuda.max_memory_allocated()),
        "current_GB":       _bytes_gb(torch.cuda.memory_allocated()),
        "reserved_GB":      _bytes_gb(torch.cuda.memory_reserved()),
    }


def _print_snap(snap: dict) -> None:
    print(f"  [{snap['label']:30s}] max={snap['max_allocated_GB']:.3f} GB  "
          f"cur={snap['current_GB']:.3f} GB  reserved={snap['reserved_GB']:.3f} GB")


def _run_one(label: str, install_fn, args, *, enable_timing: bool) -> dict:
    import torch
    from vllm import LLM, SamplingParams

    print(f"\n========== {label} ==========")
    torch.cuda.reset_peak_memory_stats()
    _print_snap(_snapshot(f"{label} (pre-load)"))

    llm = LLM(
        model=args.model, max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
        enforce_eager=True,
    )
    _print_snap(_snapshot(f"{label} (model loaded)"))

    worker = _find_inner(llm)
    print(f"  driver_worker: {type(worker).__name__ if worker else 'NOT FOUND'}")

    # Deep tensor walk on the driver_worker (covers cache_engine + model_runner).
    tensors_pre_gen = deep_tensor_walk(worker, max_depth=8) if worker else []
    print(f"  found {len(tensors_pre_gen)} CUDA tensors >=1 MB before generate")

    manager = None
    teardown = None
    if install_fn is not None:
        manager, teardown = install_fn(
            worker.model_runner.model, enable_timing=enable_timing,
        )

    prompt = (
        "The secret code is XYZ123. Repeat the secret code in the next "
        "sentence.\nThe secret code is"
    )
    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)

    out = llm.generate([prompt], sampling)
    text = out[0].outputs[0].text

    snap_after = _snapshot(f"{label} (after generate)")
    _print_snap(snap_after)

    # Re-walk after generate (catches anything allocated lazily).
    tensors_post_gen = deep_tensor_walk(worker, max_depth=8) if worker else []
    # Also walk manager._caches to catch wrapper tensors.
    if manager is not None:
        wrapper_tensors = deep_tensor_walk(manager, max_depth=6)
        # Dedup by id (path will differ).
        seen = {(t["path"], t["bytes"]) for t in tensors_post_gen}
        for t in wrapper_tensors:
            key = (t["path"], t["bytes"])
            if key not in seen:
                tensors_post_gen.append(t)

    categories = _summarize_categories(tensors_post_gen)
    print(f"  Memory breakdown (post-generate, tensors >= 1 MB):")
    sorted_cats = sorted(categories.items(), key=lambda kv: -kv[1]["bytes"])
    for cat, info in sorted_cats:
        print(f"    {cat:25s} {_bytes_gb(info['bytes']):6.3f} GB  "
              f"({info['count']} tensors)")
        if info["count"] >= 1:
            ex = info["examples"][0]
            print(f"      e.g. {ex['path']}  {ex['shape']} {ex['dtype']}")

    # Timing summary (only if enabled).
    timing_summary = {}
    if manager is not None and hasattr(manager, "timing_summary"):
        timing_summary = manager.timing_summary()
        if timing_summary:
            print(f"  Per-token timing summary:")
            for ev, info in sorted(timing_summary.items()):
                print(f"    {ev:25s} count={info['count']:4d}  "
                      f"mean={info['mean_ms']:6.3f} ms  median={info['median_ms']:6.3f} ms  "
                      f"total={info['total_s']:.3f} s")

    stats = manager.stats() if manager else {}
    if stats:
        # Suppress _timings noise.
        clean = {k: v for k, v in stats.items() if k != "_timings"}
        print(f"  Stats: {clean}")

    if teardown is not None:
        teardown()
    del llm, worker, manager
    gc.collect()
    torch.cuda.empty_cache()

    return {
        "label":          label,
        "snap_after_GB":  snap_after["max_allocated_GB"],
        "categories":     {k: {"bytes": v["bytes"], "count": v["count"]}
                           for k, v in categories.items()},
        "timing_summary": timing_summary,
        "output_text":    text,
    }


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--protect-fraction", type=float, default=0.04)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--skip-stock", action="store_true",
                        help="Skip the stock baseline run.")
    args = parser.parse_args(argv)

    try:
        import torch  # noqa: F401
    except ImportError as e:
        print(f"FAIL: {e}")
        return 1

    from kv_policy.phase5a_native_install import install_phase5a_native
    from kv_policy.phase2_4_native_install import install_phase2_4_packed

    def install_5a(model, *, enable_timing):
        return install_phase5a_native(
            model, protect_fraction=args.protect_fraction,
            max_seqlen=args.max_model_len, enable_timing=enable_timing,
        )

    def install_24c(model, *, enable_timing):
        return install_phase2_4_packed(
            model, protect_fraction=args.protect_fraction,
            max_seqlen=args.max_model_len, enable_timing=enable_timing,
        )

    print("=" * 70)
    print("Phase 2.4 breakdown — deep memory + per-token timing")
    print("=" * 70)
    print(f"  model:            {args.model}")
    print(f"  max_model_len:    {args.max_model_len}")
    print(f"  protect_fraction: {args.protect_fraction}")
    print(f"  gpu_memory_util:  {args.gpu_memory_utilization}")
    print(f"  max_tokens:       {args.max_tokens}")

    results = []
    if not args.skip_stock:
        results.append(_run_one("stock vLLM", None, args, enable_timing=False))
    results.append(_run_one("Phase 5A install",     install_5a, args, enable_timing=True))
    results.append(_run_one("Phase 2.4.1c install", install_24c, args, enable_timing=True))

    # Decision summary.
    print()
    print("=" * 70)
    print("Decision-ready breakdown")
    print("=" * 70)
    p24 = next(r for r in results if "2.4.1c" in r["label"])
    if not args.skip_stock:
        stock = results[0]
        print(f"  Peak HBM:  stock {stock['snap_after_GB']:.3f} GB  "
              f"Phase 2.4.1c {p24['snap_after_GB']:.3f} GB  "
              f"delta {p24['snap_after_GB'] - stock['snap_after_GB']:+.3f} GB")

    cats = p24["categories"]
    print()
    print("  Category bytes (Phase 2.4.1c, GB):")
    for cat in ("vllm_paged_kv", "model_weights", "wrapper_k_fp16",
                "wrapper_v_fp16", "packed_k_int4", "packed_k_scale",
                "packed_k_xmin", "packed_k_protect_bf16", "packed_protect_slot",
                "wrapper_protect_mask", "buffer", "other"):
        b = cats.get(cat, {"bytes": 0})["bytes"]
        if b > 0:
            print(f"    {cat:30s} {_bytes_gb(b):6.3f} GB")

    tsum = p24["timing_summary"]
    if tsum:
        print()
        print("  Per-decode-step timing (Phase 2.4.1c, mean ms):")
        for ev in ("decode_append", "decode_repack", "decode_kernel"):
            if ev in tsum:
                m = tsum[ev]
                print(f"    {ev:25s} mean={m['mean_ms']:6.3f} ms  "
                      f"median={m['median_ms']:6.3f} ms  count={m['count']}")
        total_ms = sum(tsum[ev]["mean_ms"] for ev in ("decode_append", "decode_repack", "decode_kernel")
                       if ev in tsum)
        print(f"    {'(sum of measured)':25s} {total_ms:6.3f} ms")

    print()
    print("Decision rule:")
    print("  If vllm_paged_kv dominates  -> Phase 2.4.b priority (free vLLM cache)")
    print("  If wrapper_k_fp16 + repack dominate -> Phase 2.4.1d priority (incremental repack)")
    print("  If decode_append dominates  -> Phase 5B priority (native cache write)")
    print("  If decode_kernel dominates  -> profile CUDA (unlikely given Phase 2.4.1b numbers)")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results, indent=2, default=str))
        print(f"\nSnapshot: {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
