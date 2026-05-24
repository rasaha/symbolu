#!/usr/bin/env python3
"""measure_phase2_4_memory.py — 6c.3C Phase 2.4.b step 1: HBM accounting.

Measures `torch.cuda.max_memory_allocated()` and probes vLLM's internal
`kv_caches` structure across THREE configurations:

  1. Stock vLLM (no install)              — baseline
  2. Phase 5A install (FP16 sidecar)      — current routing+quality proof
  3. Phase 2.4.1c install (packed sidecar) — current packed-K install

For each: model load + one short generate + snapshot. Reports
per-stage deltas + the actual size of vLLM's allocated kv_caches.

The numbers from this script tell us the SHAPE of Phase 2.4.b:
  - How much would freeing vLLM's paged K cache save?
  - How much does our FP16 K sidecar cost (drop-target for Phase 2.4.1d)?
  - How big is the packed sidecar in practice?
  - Are we currently HIGHER than stock vLLM (paper claim alert)?

This script does NOT attempt to free anything. That's Phase 2.4.b step 2,
informed by these numbers.

Exit 0 (always). Reports go to stdout + an optional JSON snapshot.
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


def _find_inner_model(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner,
        lambda x: x.model_executor.driver_worker.model_runner,
    ]
    for fn in candidates:
        try:
            mr = fn(llm)
            if mr is not None and hasattr(mr, "model"):
                return mr
        except (AttributeError, IndexError):
            pass
    return None


def _probe_kv_caches(model_runner) -> dict:
    """Find and describe vLLM's paged kv_caches.

    vLLM 0.7.3: model_runner.kv_caches is a list of tensors, one per
    layer, of shape (2, num_blocks, block_size, num_kv_heads, head_dim)
    typically. The leading dim 2 splits K and V.
    """
    info = {"present": False, "layers": 0, "total_bytes": 0, "per_layer": None,
            "shape_first": None, "dtype": None}
    kvc = getattr(model_runner, "kv_caches", None)
    if kvc is None:
        return info
    if not isinstance(kvc, (list, tuple)) or len(kvc) == 0:
        return info
    info["present"] = True
    info["layers"] = len(kvc)
    total = 0
    first_shape = None
    first_dtype = None
    for t in kvc:
        if hasattr(t, "numel") and hasattr(t, "element_size"):
            nbytes = t.numel() * t.element_size()
            total += nbytes
            if first_shape is None:
                first_shape = tuple(t.shape)
                first_dtype = str(t.dtype)
    info["total_bytes"] = total
    info["shape_first"] = first_shape
    info["dtype"]       = first_dtype
    info["per_layer"]   = total // max(1, info["layers"])
    return info


def _snapshot(label: str) -> dict:
    import torch
    return {
        "label":              label,
        "max_allocated_GB":   _bytes_gb(torch.cuda.max_memory_allocated()),
        "current_GB":         _bytes_gb(torch.cuda.memory_allocated()),
        "reserved_GB":        _bytes_gb(torch.cuda.memory_reserved()),
    }


def _print_snap(snap: dict) -> None:
    print(f"  [{snap['label']:30s}] "
          f"max={snap['max_allocated_GB']:.3f} GB  "
          f"cur={snap['current_GB']:.3f} GB  "
          f"reserved={snap['reserved_GB']:.3f} GB")


def _print_kv(kv: dict) -> None:
    if not kv["present"]:
        print("    vLLM kv_caches: NOT FOUND (model_runner.kv_caches missing)")
        return
    print(f"    vLLM kv_caches: {kv['layers']} layers, "
          f"total {_bytes_gb(kv['total_bytes']):.3f} GB "
          f"({_bytes_mb(kv['per_layer']):.1f} MB/layer); "
          f"first-layer shape {kv['shape_first']} {kv['dtype']}")


def _run_one(label: str, install_fn, args) -> dict:
    """Load model, optionally install, run one generate, snapshot.

    install_fn: callable(model) -> (manager, teardown), or None for stock.
    """
    import torch, gc
    from vllm import LLM, SamplingParams

    print(f"\n========== {label} ==========")
    torch.cuda.reset_peak_memory_stats()
    snap_pre = _snapshot(f"{label} (pre-load)")
    _print_snap(snap_pre)

    llm = LLM(
        model=args.model, max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
        enforce_eager=True,
    )
    snap_loaded = _snapshot(f"{label} (model loaded)")
    _print_snap(snap_loaded)

    model_runner = _find_inner_model(llm)
    kv_info = _probe_kv_caches(model_runner) if model_runner else {"present": False}
    _print_kv(kv_info)

    manager = None
    teardown = None
    if install_fn is not None:
        manager, teardown = install_fn(model_runner.model)

    prompt = (
        "The secret code is XYZ123. Repeat the secret code in the next "
        "sentence.\nThe secret code is"
    )
    sampling = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)
    out = llm.generate([prompt], sampling)
    text = out[0].outputs[0].text

    snap_generated = _snapshot(f"{label} (after generate)")
    _print_snap(snap_generated)

    # Re-probe kv_caches AFTER generate — its size should be unchanged
    # (paged cache is preallocated at engine init), but content has updated.
    kv_info_after = _probe_kv_caches(model_runner) if model_runner else {"present": False}

    # Sidecar bytes: probe the manager if it's our wrapper.
    sidecar_bytes = 0
    sidecar_breakdown: dict = {}
    if manager is not None and hasattr(manager, "_caches"):
        for cid, cache in manager._caches.items():
            for attr in ("k_fp16", "v_fp16"):
                t = getattr(cache, attr, None)
                if t is not None and hasattr(t, "numel"):
                    nb = t.numel() * t.element_size()
                    sidecar_bytes += nb
                    sidecar_breakdown[attr] = sidecar_breakdown.get(attr, 0) + nb
            # Packed-side tensors (Phase 2.4.1c only).
            packed = getattr(cache, "packed", None)
            if packed is not None and isinstance(packed, dict):
                for k, v in packed.items():
                    if hasattr(v, "numel") and hasattr(v, "element_size"):
                        nb = v.numel() * v.element_size()
                        sidecar_bytes += nb
                        sidecar_breakdown[f"packed_{k}"] = sidecar_breakdown.get(f"packed_{k}", 0) + nb
    if sidecar_bytes > 0:
        print(f"    Phase wrapper sidecar total: {_bytes_gb(sidecar_bytes):.3f} GB")
        for k, v in sorted(sidecar_breakdown.items()):
            print(f"      {k:20s} {_bytes_mb(v):8.1f} MB")

    stats = manager.stats() if manager else {}
    if stats:
        print(f"    install stats: {stats}")

    if teardown is not None:
        teardown()
    del llm, model_runner, manager
    gc.collect()
    torch.cuda.empty_cache()

    return {
        "label":                label,
        "snap_loaded":          snap_loaded,
        "snap_generated":       snap_generated,
        "vllm_kv_caches_bytes": kv_info_after.get("total_bytes", 0),
        "wrapper_sidecar_bytes": sidecar_bytes,
        "wrapper_sidecar_breakdown": sidecar_breakdown,
        "output_text":          text,
    }


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--max-tokens",     type=int, default=32)
    parser.add_argument("--protect-fraction", type=float, default=0.04)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    parser.add_argument("--json-out", default=None,
                        help="Optional path to dump the snapshot dict as JSON.")
    args = parser.parse_args(argv)

    try:
        import torch  # noqa: F401
    except ImportError as e:
        print(f"FAIL: {e}")
        return 1

    from kv_policy.phase5a_native_install import install_phase5a_native
    from kv_policy.phase2_4_native_install import install_phase2_4_packed

    def install_5a(model):
        return install_phase5a_native(
            model, protect_fraction=args.protect_fraction,
            max_seqlen=args.max_model_len,
        )

    def install_24c(model):
        return install_phase2_4_packed(
            model, protect_fraction=args.protect_fraction,
            max_seqlen=args.max_model_len,
        )

    print("=" * 70)
    print("Phase 2.4.b step 1 — HBM measurement")
    print("=" * 70)
    print(f"  model:          {args.model}")
    print(f"  max_model_len:  {args.max_model_len}")
    print(f"  protect_fraction: {args.protect_fraction}")
    print(f"  gpu_memory_util:  {args.gpu_memory_utilization}")

    results = []
    results.append(_run_one("stock vLLM",          None,         args))
    results.append(_run_one("Phase 5A install",    install_5a,   args))
    results.append(_run_one("Phase 2.4.1c install", install_24c, args))

    # Summary table.
    print()
    print("=" * 70)
    print("Summary — peak HBM after generate")
    print("=" * 70)
    print(f"  {'Configuration':30s}  {'peak GB':>10s}  {'vLLM kv GB':>12s}  {'sidecar GB':>12s}")
    for r in results:
        print(f"  {r['label']:30s}  "
              f"{r['snap_generated']['max_allocated_GB']:>10.3f}  "
              f"{_bytes_gb(r['vllm_kv_caches_bytes']):>12.3f}  "
              f"{_bytes_gb(r['wrapper_sidecar_bytes']):>12.3f}")
    print()
    print("Phase 2.4.b interpretation:")
    p24 = results[2]
    stock = results[0]
    diff_vs_stock = (p24['snap_generated']['max_allocated_GB']
                     - stock['snap_generated']['max_allocated_GB'])
    print(f"  Phase 2.4.1c vs stock vLLM:  {diff_vs_stock:+.3f} GB peak")
    if p24["vllm_kv_caches_bytes"] > 0:
        print(f"  Freeing vLLM kv_caches would save up to "
              f"{_bytes_gb(p24['vllm_kv_caches_bytes']):.3f} GB.")
    print(f"  Wrapper sidecar (target for Phase 2.4.1d K-FP16 drop): "
          f"{_bytes_gb(p24['wrapper_sidecar_bytes']):.3f} GB")
    fp16k = p24.get("wrapper_sidecar_breakdown", {}).get("k_fp16", 0)
    if fp16k > 0:
        print(f"  Of which K FP16 sidecar (droppable after Phase 2.4.1d): "
              f"{_bytes_gb(fp16k):.3f} GB")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results, indent=2, default=str))
        print(f"\nSnapshot written: {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
