"""TIER5A.4 diagnostic — dump vLLM block_manager structure.

The TIER5A.3 first green run showed G3 RED with
``cpu_swap_pool_used_blocks_peak=0 of 0``. The swap-in latency
probe DID fire (call_count=20) — the resolver gap is in
``read_cpu_swap_pool`` /
``swap_telemetry._read_allocator_block_counts``: the attribute
names the walker tries don't match what vLLM 0.7.3's V0 engine
exposes on its block_manager / block_allocator / per-device
allocator hierarchy.

This script initializes a minimal vLLM engine and dumps every
attribute path the resolver could plausibly use. Operator runs
this on the GPU pod and pastes the output back; we then extend
``_read_allocator_block_counts`` with the exact attribute names
that DO exist on this build.

Usage (on the GPU pod, after `source /workspace/venv-vllm/bin/activate`):
    python -m ctm_bench.scripts.tier5a_v0_engine_inspect

Optional args (defaults match the working TIER5A.3 cell B config):
    --model Qwen/Qwen2.5-7B-Instruct
    --gpu-mem-util 0.20
    --max-model-len 1024
    --swap-space-gb 8

Wall time: ~30 seconds on warm pod (one engine init, no decode).
Cost: negligible (~$0.02 at H100/A100 spot rates).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, List, Tuple


def _safe_repr(obj: Any, depth: int = 0) -> str:
    """Bounded repr — won't blow up on giant tensors / dicts."""
    if depth >= 2:
        return f"<{type(obj).__name__} ...>"
    try:
        if isinstance(obj, (int, float, bool, type(None))):
            return repr(obj)
        if isinstance(obj, str):
            return repr(obj if len(obj) < 80 else obj[:77] + "...")
        if isinstance(obj, (list, tuple)):
            if len(obj) <= 5:
                inner = ", ".join(_safe_repr(x, depth + 1) for x in obj)
                return f"[{inner}]"
            return f"[{len(obj)} items: {_safe_repr(obj[0], depth + 1)}, ...]"
        if isinstance(obj, dict):
            keys = list(obj.keys())[:5]
            return (
                f"{{{len(obj)} keys: "
                + ", ".join(repr(k) for k in keys)
                + (", ...}" if len(obj) > 5 else "}")
            )
        s = repr(obj)
        if len(s) > 100:
            return s[:97] + "..."
        return s
    except Exception as e:
        return f"<repr failed: {type(e).__name__}>"


def _probe(obj: Any, name: str) -> Tuple[bool, str, str]:
    """Returns (exists, type_label, value_repr)."""
    if not hasattr(obj, name):
        return (False, "-", "-")
    try:
        v = getattr(obj, name)
    except Exception as e:
        return (True, "ERROR", f"<getattr raised: {type(e).__name__}>")
    if callable(v) and not isinstance(v, type):
        try:
            result = v()
            return (True, "method()", _safe_repr(result))
        except TypeError as e:
            return (True, "method(args)", f"<requires args: {e}>")
        except Exception as e:
            return (
                True, "method()",
                f"<call raised: {type(e).__name__}: {e}>",
            )
    return (True, type(v).__name__, _safe_repr(v))


def _list_public_attrs(obj: Any) -> List[str]:
    return sorted(a for a in dir(obj) if not a.startswith("_"))


def _print_probes(obj: Any, prefix: str, candidates: List[str]) -> None:
    for name in candidates:
        exists, typ, val = _probe(obj, name)
        marker = "FOUND " if exists else "miss  "
        print(f"  {marker} {prefix}.{name}: type={typ}  value={val}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dump vLLM block_manager structure for TIER5A.4 resolver fix.",
    )
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--gpu-mem-util", type=float, default=0.20)
    parser.add_argument("--max-model-len", type=int, default=1024)
    parser.add_argument("--swap-space-gb", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    try:
        import vllm
    except ImportError as e:
        print(
            "ERROR: vllm not importable. Run on the GPU pod with "
            "the forked vLLM build activated.",
            file=sys.stderr,
        )
        print(f"detail: {e}", file=sys.stderr)
        return 2

    print(f"=== vllm version: {vllm.__version__} ===")
    print(f"loading {args.model} at gpu_mem_util={args.gpu_mem_util}, "
          f"max_model_len={args.max_model_len}...")
    engine_args = vllm.AsyncEngineArgs(
        model=args.model,
        gpu_memory_utilization=args.gpu_mem_util,
        max_model_len=args.max_model_len,
        swap_space=args.swap_space_gb,
        preemption_mode="swap",
        enforce_eager=True,
        seed=args.seed,
    )
    engine = vllm.AsyncLLMEngine.from_engine_args(engine_args)

    inner = getattr(engine, "engine", engine)
    sched_attr = getattr(inner, "scheduler", None)
    if sched_attr is None:
        print("ERROR: engine has no .scheduler attribute", file=sys.stderr)
        return 3
    scheduler = (
        sched_attr[0] if isinstance(sched_attr, list) else sched_attr
    )
    bm = getattr(scheduler, "block_manager", None)
    if bm is None:
        print("ERROR: scheduler has no .block_manager attribute", file=sys.stderr)
        return 3

    print(f"\n=== block_manager ===")
    print(f"  type:    {type(bm).__name__}")
    print(f"  module:  {type(bm).__module__}")
    print(f"  block_size attr: ", _probe(bm, "block_size"))

    print(f"\n  all public attrs ({len([a for a in _list_public_attrs(bm)])}):")
    for a in _list_public_attrs(bm):
        exists, typ, val = _probe(bm, a)
        print(f"    {a}: type={typ} value={val}")

    # Swap entry point candidates (probe wrap target — KNOWN GOOD on
    # first green run; included for completeness).
    print(f"\n  swap-entry candidates (TIER5A.3 known good):")
    _print_probes(
        bm, "bm",
        ["swap_in", "swap_out", "swap_in_blocks", "swap_blocks_in",
         "_swap_in", "swap"],
    )

    # ---- block_allocator ----
    ba = getattr(bm, "block_allocator", None)
    print(f"\n=== block_allocator (bm.block_allocator) ===")
    if ba is None:
        print("  NOT PRESENT")
    else:
        print(f"  type:    {type(ba).__name__}")
        print(f"  module:  {type(ba).__module__}")
        print(f"\n  all public attrs ({len([a for a in _list_public_attrs(ba)])}):")
        for a in _list_public_attrs(ba):
            exists, typ, val = _probe(ba, a)
            print(f"    {a}: type={typ} value={val}")

        # Per-device allocator paths
        print(f"\n  per-device allocator candidates:")
        _print_probes(
            ba, "ba",
            ["cpu_allocator", "gpu_allocator", "_allocators", "swap"],
        )

        # If _allocators is a dict, dump each per-device allocator's
        # count-reading surface.
        allocators = getattr(ba, "_allocators", None)
        if isinstance(allocators, dict):
            print(f"\n  ba._allocators keys: {[str(k) for k in allocators.keys()]}")
            for key, alloc in allocators.items():
                print(f"\n  === ba._allocators[{key!r}] ===")
                print(f"    type:   {type(alloc).__name__}")
                print(f"    module: {type(alloc).__module__}")
                print(f"    public attrs:")
                for a in _list_public_attrs(alloc):
                    exists, typ, val = _probe(alloc, a)
                    print(f"      {a}: type={typ} value={val}")
                print(f"    count-reading candidates:")
                _print_probes(
                    alloc, f"[{key}]",
                    [
                        "num_total_blocks", "_num_total_blocks",
                        "num_blocks", "_num_blocks",
                        "total_blocks", "_total_blocks",
                        "get_num_total_blocks",
                        "get_num_free_blocks", "num_free_blocks",
                        "_num_free_blocks", "free_blocks",
                        "get_num_used_blocks", "num_used_blocks",
                        "_num_used_blocks",
                    ],
                )

        # CpuGpuBlockAllocator may expose device-keyed counts directly
        print(f"\n  ba device-arg count candidates:")
        for name in ("get_num_total_blocks", "get_num_free_blocks"):
            exists, _, _ = _probe(ba, name)
            if not exists:
                print(f"    miss   ba.{name}: NOT PRESENT")
                continue
            print(f"    FOUND  ba.{name}: trying with Device.CPU/Device.GPU args...")
            try:
                from vllm.utils import Device
                cpu_val = getattr(ba, name)(Device.CPU)
                gpu_val = getattr(ba, name)(Device.GPU)
                print(f"      [CPU] = {cpu_val!r}")
                print(f"      [GPU] = {gpu_val!r}")
            except Exception as e:
                print(f"      <call with Device enum raised: {type(e).__name__}: {e}>")
                # Try with string keys
                try:
                    cpu_val = getattr(ba, name)("cpu")
                    print(f"      ['cpu'] = {cpu_val!r}")
                except Exception:
                    pass

    # ---- V1 direct paths on block_manager ----
    print(f"\n=== V1-direct allocator paths on block_manager ===")
    _print_probes(bm, "bm", ["cpu_allocator", "gpu_allocator"])

    # ---- engine-level counts (vLLM logs '# CPU blocks: N' at init) ----
    print(f"\n=== engine-level cache_config + capacity attrs ===")
    cache_config = getattr(inner, "cache_config", None)
    if cache_config is None:
        print("  no inner.cache_config")
    else:
        for a in ("num_gpu_blocks", "num_cpu_blocks", "block_size",
                  "swap_space_bytes"):
            exists, typ, val = _probe(cache_config, a)
            marker = "FOUND " if exists else "miss  "
            print(f"  {marker} cache_config.{a}: type={typ}  value={val}")

    print(f"\n=== inspect complete ===")
    print("Paste the entire output above into the conversation; the")
    print("targeted resolver fix will follow.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
