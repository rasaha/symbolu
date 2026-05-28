"""Phase 6G Step 1 — sidecar memory audit.

Tensor-by-tensor measurement of the int4_protected writer's allocations.
Loads vLLM with int4_protected at a given max_model_len, fires a small
generate to trigger _lazy_alloc on every layer, then walks each writer
and reports the byte cost of every sidecar plus the CUDA-graph private-
pool overhead vLLM holds.

Strict scope per user spec:
  * NO implementation changes.
  * Audit only — produces a measured baseline against which diet options
    can later be evaluated.

Output: bench_out/phase6g_sidecar_audit/audit_mml{N}.json + a printed
table. Driver mode (default) runs the audit at max_model_len ∈
{8192, 16384, 32768} and aggregates into a single findings JSON.

Run:
  python CTM_plus/Bench/scripts/audit_phase6g_sidecar_overhead.py

Single mml (internal worker mode):
  python CTM_plus/Bench/scripts/audit_phase6g_sidecar_overhead.py \\
    --worker --max-model-len 16384 --output /tmp/audit_16k.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_CANDIDATES = [
    Path("/workspace/symbolu/CTM_plus"),
    Path("/home/user/symbolu/CTM_plus"),
    Path(__file__).resolve().parent.parent.parent,
]
for _root in ROOT_CANDIDATES:
    kvp = _root / "KVPolicy"
    if kvp.is_dir() and str(kvp) not in sys.path:
        sys.path.insert(0, str(kvp))
        break


# Sidecar tensors the writer allocates in _lazy_alloc. The audit walks
# each writer and reports the byte cost of every attribute in this list.
# (Name, accessor, scaling-law category)
#   Category meanings:
#     "per_token"   - bytes scale with NB * BS (total cache tokens)
#     "per_block"   - bytes scale with NB only
#     "per_slot"    - bytes scale with n_slots (max_active_slots)
#     "fixed"       - bytes are constant per layer (one-shot lookup tables)
SIDECAR_INVENTORY: List[Tuple[str, str, str]] = [
    ("v_scale_ext",             "v_scale_ext",             "per_token"),
    ("v_xmin_ext",              "v_xmin_ext",              "per_token"),
    ("k_protect_ext",           "k_protect_ext",           "per_token"),
    ("k_scale_ext",             "k_scale_ext",             "per_block"),
    ("k_xmin_ext",              "k_xmin_ext",              "per_block"),
    ("_k_stage_pool",           "_k_stage_pool",           "per_slot"),
    ("_k_stage_block_id_pool",  "_k_stage_block_id_pool",  "per_slot"),
    ("_k_stage_count_pool",     "_k_stage_count_pool",     "per_slot"),
    ("_seq_pos_pool",           "_seq_pos_pool",           "per_slot"),
    ("_bf16_k_backing_pool",    "_bf16_k_backing_pool",    "per_slot"),
    ("_bf16_v_backing_pool",    "_bf16_v_backing_pool",    "per_slot"),
    ("protect_mask",            "protect_mask",            "fixed"),
    ("protect_slot",            "protect_slot",            "fixed"),
    ("protected_d_per_head",    "protected_d_per_head",    "fixed"),
]


def _bytes_of(t) -> int:
    if t is None:
        return 0
    try:
        return t.numel() * t.element_size()
    except (AttributeError, RuntimeError):
        return 0


def _shape_of(t) -> Optional[List[int]]:
    if t is None:
        return None
    try:
        return list(t.shape)
    except (AttributeError, RuntimeError):
        return None


def _dtype_of(t) -> Optional[str]:
    if t is None:
        return None
    try:
        return str(t.dtype).replace("torch.", "")
    except (AttributeError, RuntimeError):
        return None


def _find_inner_model(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
        lambda x: x.model_executor.driver_worker.model_runner.model,
    ]
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None and hasattr(m, "named_modules"):
                return m
        except (AttributeError, IndexError):
            continue
    return None


def _collect_writers(inner) -> List[Any]:
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    out: List[Any] = []
    for _, sub in inner.named_modules():
        impl = getattr(sub, "impl", None)
        if not isinstance(impl, Int4ProtectedAttentionImpl):
            continue
        w = getattr(impl, "_phase5b_paged_writer", None)
        if w is not None:
            out.append(w)
    return out


def _kv_cache_summary(llm) -> Dict[str, Any]:
    import torch
    info: Dict[str, Any] = {
        "num_gpu_blocks":  None,
        "block_size":      None,
        "max_model_len":   None,
        "max_concurrency": None,
        "kv_cache_dtype":  None,
        "kv_cache_shape":  None,
        "kv_cache_dtype_runtime": None,
        "kv_cache_bytes":  None,
    }
    try:
        engine = llm.llm_engine
        cfg = engine.cache_config
        info["num_gpu_blocks"] = int(getattr(cfg, "num_gpu_blocks", 0) or 0)
        info["block_size"]     = int(getattr(cfg, "block_size", 0) or 0)
        info["kv_cache_dtype"] = str(getattr(cfg, "cache_dtype", "") or "")
        mcfg = getattr(engine, "model_config", None)
        if mcfg is not None:
            mml = getattr(mcfg, "max_model_len", None)
            if mml is not None:
                info["max_model_len"] = int(mml)
        if info["num_gpu_blocks"] and info["block_size"] and info["max_model_len"]:
            info["max_concurrency"] = (
                info["num_gpu_blocks"] * info["block_size"] / info["max_model_len"]
            )
        # Inspect actual kv_cache tensor (from the model_runner).
        try:
            kv_caches = engine.model_executor.driver_worker.cache_engine
            if isinstance(kv_caches, list):
                kv_caches = kv_caches[0]
            # cache_engine.gpu_cache is the list of per-layer (2, NB, BS, H, D) tensors.
            gpu_cache = getattr(kv_caches, "gpu_cache", None)
            if gpu_cache and len(gpu_cache) > 0:
                t0 = gpu_cache[0]
                info["kv_cache_shape"]       = list(t0.shape)
                info["kv_cache_dtype_runtime"] = str(t0.dtype).replace("torch.", "")
                info["kv_cache_bytes"]       = int(t0.numel() * t0.element_size())
        except (AttributeError, TypeError, IndexError):
            pass
    except (AttributeError, TypeError, ValueError):
        pass
    return info


def _hbm_snapshot() -> Dict[str, float]:
    import torch
    free, total = torch.cuda.mem_get_info()
    used = total - free
    allocated = torch.cuda.memory_allocated()
    reserved  = torch.cuda.memory_reserved()
    return {
        "allocated_gb":         allocated / (1024**3),
        "reserved_gb":          reserved  / (1024**3),
        "used_gb":              used      / (1024**3),
        "free_gb":              free      / (1024**3),
        "total_gb":             total     / (1024**3),
        # "other" = anything in GPU memory NOT tracked by PyTorch's caching
        # allocator. CUDA-graph private pools live here. Reported by the
        # CUDA OOM message earlier as "X GiB allocated in private pools
        # (e.g., CUDA Graphs)".
        "non_pytorch_gb":       (used - reserved) / (1024**3),
    }


def run_worker(
    max_model_len: int,
    output_path: Path,
    *,
    model: str,
    gpu_memory_utilization: float,
    max_num_seqs: int,
) -> int:
    os.environ["PHASE6E_FUSED_WRITER"] = "1"
    try:
        import torch
        from vllm import SamplingParams
    except ImportError as exc:
        print(f"FAIL: torch/vllm import failed: {exc}")
        return 2
    if not torch.cuda.is_available():
        print("FAIL: torch.cuda.is_available() is False")
        return 2

    # 1. Snapshot HBM at process start (before any allocation).
    torch.cuda.reset_peak_memory_stats()
    hbm_before_load = _hbm_snapshot()

    # 2. Load int4_protected.
    import kv_policy.int4_protected   # noqa: F401
    from kv_policy.int4_protected import Int4ProtectedLLM
    print(f"[mml={max_model_len}] Loading {model}...")
    t0 = time.time()
    llm = Int4ProtectedLLM(
        model=model,
        max_model_len=max_model_len,
        gpu_memory_utilization=gpu_memory_utilization,
        max_num_seqs=max_num_seqs,
    )
    torch.cuda.synchronize()
    t_load = time.time() - t0
    hbm_after_init = _hbm_snapshot()

    # 3. Trigger _lazy_alloc on every layer by running a small generate.
    print(f"[mml={max_model_len}] Warmup to trigger _lazy_alloc...")
    llm.generate(
        ["Hello"],
        SamplingParams(temperature=0.0, max_tokens=2),
    )
    torch.cuda.synchronize()
    hbm_after_warmup = _hbm_snapshot()

    # 4. Walk every writer; collect tensor-by-tensor bytes.
    inner = _find_inner_model(llm)
    if inner is None:
        print("FAIL: cannot locate inner model")
        return 2
    writers = _collect_writers(inner)
    if not writers:
        print("FAIL: no Int4ProtectedAttentionImpl writers found")
        return 2
    print(f"[mml={max_model_len}] Walking {len(writers)} writers (one per attention layer).")

    # Per-tensor accumulators across all layers.
    per_tensor: Dict[str, Dict[str, Any]] = {}
    for name, attr, scaling in SIDECAR_INVENTORY:
        per_tensor[name] = {
            "attr":          attr,
            "scaling":       scaling,
            "shapes":        [],     # one per layer (or one entry if shared)
            "dtypes":        [],
            "bytes_per_layer": [],
            "bytes_total":   0,
            "num_layers":    0,
        }

    # Walk each writer.
    for w in writers:
        for name, attr, scaling in SIDECAR_INVENTORY:
            t = getattr(w, attr, None)
            b = _bytes_of(t)
            s = _shape_of(t)
            d = _dtype_of(t)
            per_tensor[name]["shapes"].append(s)
            per_tensor[name]["dtypes"].append(d)
            per_tensor[name]["bytes_per_layer"].append(b)
            per_tensor[name]["bytes_total"] += b
            per_tensor[name]["num_layers"]  += 1

    # 5. Collect engine-level cache config.
    kv_cfg = _kv_cache_summary(llm)
    # kv_cache_bytes is per-layer (one tensor in the gpu_cache list per layer).
    # Total across N layers is kv_cache_bytes * num_layers.
    n_layers = len(writers)
    kv_cache_total_bytes = (kv_cfg.get("kv_cache_bytes") or 0) * n_layers

    # 6. Sum sidecars; rank.
    total_sidecar_bytes = sum(v["bytes_total"] for v in per_tensor.values())
    ranked: List[Dict[str, Any]] = []
    for name, info in per_tensor.items():
        share = (info["bytes_total"] / total_sidecar_bytes) if total_sidecar_bytes > 0 else 0.0
        ranked.append({
            "tensor":         name,
            "scaling":        info["scaling"],
            "per_layer_shape": info["shapes"][0] if info["shapes"] else None,
            "per_layer_dtype": info["dtypes"][0] if info["dtypes"] else None,
            "per_layer_bytes": info["bytes_per_layer"][0] if info["bytes_per_layer"] else 0,
            "num_layers":     info["num_layers"],
            "total_bytes":    info["bytes_total"],
            "total_mb":       info["bytes_total"] / (1024**2),
            "total_gb":       info["bytes_total"] / (1024**3),
            "share_of_sidecars": share,
        })
    ranked.sort(key=lambda r: r["total_bytes"], reverse=True)

    # 7. Aggregate by scaling-law category.
    by_category: Dict[str, int] = {"per_token": 0, "per_block": 0, "per_slot": 0, "fixed": 0}
    for r in ranked:
        by_category[r["scaling"]] = by_category.get(r["scaling"], 0) + r["total_bytes"]

    # 8. Compute per-cached-token costs (using NB * BS = total cache slots).
    NB = kv_cfg.get("num_gpu_blocks") or 0
    # NB BS here are determined by the writer (BS=32 always for int4_protected).
    BS = 32
    total_cache_tokens = NB * BS
    per_token_sidecar_bytes_per_layer = 0
    per_token_cache_bytes_per_layer   = 0
    if total_cache_tokens > 0 and n_layers > 0:
        per_token_sidecar_bytes_per_layer = (
            by_category["per_token"] / (total_cache_tokens * n_layers)
        )
        # Per-block sidecars amortize over BS tokens each:
        per_block_per_layer_per_token = (
            by_category["per_block"] / (total_cache_tokens * n_layers)
        )
        if kv_cfg.get("kv_cache_bytes"):
            per_token_cache_bytes_per_layer = (
                kv_cfg["kv_cache_bytes"] / total_cache_tokens
            )

    payload: Dict[str, Any] = {
        "model":              model,
        "max_model_len":      max_model_len,
        "gpu_memory_utilization": gpu_memory_utilization,
        "max_num_seqs":       max_num_seqs,
        "num_layers":         n_layers,
        "load_seconds":       t_load,
        "kv_cache_config":    kv_cfg,
        "kv_cache_total_bytes_all_layers": kv_cache_total_bytes,
        "kv_cache_total_gb_all_layers":    kv_cache_total_bytes / (1024**3),
        "hbm_before_load":    hbm_before_load,
        "hbm_after_init":     hbm_after_init,
        "hbm_after_warmup":   hbm_after_warmup,
        "sidecar_total_bytes_all_layers": total_sidecar_bytes,
        "sidecar_total_gb_all_layers":    total_sidecar_bytes / (1024**3),
        "sidecar_ranked":     ranked,
        "sidecar_by_category_bytes": by_category,
        "sidecar_by_category_gb": {
            k: v / (1024**3) for k, v in by_category.items()
        },
        "per_token_marginal_bytes": {
            "sidecar_per_token_per_layer": per_token_sidecar_bytes_per_layer,
            "cache_per_token_per_layer":   per_token_cache_bytes_per_layer,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    print(f"[mml={max_model_len}] Wrote {output_path}")
    _print_table(payload)
    return 0


def _print_table(payload: Dict[str, Any]) -> None:
    mml = payload["max_model_len"]
    NB  = payload["kv_cache_config"].get("num_gpu_blocks")
    bs  = payload["kv_cache_config"].get("block_size")
    mc  = payload["kv_cache_config"].get("max_concurrency")
    lines = []
    lines.append("=" * 84)
    lines.append(f"Phase 6G sidecar audit — max_model_len={mml}")
    lines.append("=" * 84)
    lines.append(
        f"vLLM cache: blocks={NB}  block_size={bs}  "
        f"max_concurrency={mc:.1f}" if mc else
        f"vLLM cache: blocks={NB}  block_size={bs}  max_concurrency=n/a"
    )
    lines.append(
        f"Layers: {payload['num_layers']}  "
        f"HBM after init: {payload['hbm_after_init']['used_gb']:.2f} GB  "
        f"after warmup: {payload['hbm_after_warmup']['used_gb']:.2f} GB"
    )
    lines.append(
        f"Non-PyTorch HBM (CUDA graphs etc.): "
        f"{payload['hbm_after_warmup']['non_pytorch_gb']:.2f} GB"
    )
    kv_gb = payload["kv_cache_total_gb_all_layers"]
    sc_gb = payload["sidecar_total_gb_all_layers"]
    lines.append(
        f"KV cache (vLLM-managed, all layers): {kv_gb:.2f} GB  |  "
        f"Sidecars (writer-allocated, all layers): {sc_gb:.2f} GB  |  "
        f"Sidecar overhead = {sc_gb / max(0.001, kv_gb) * 100:.1f}% of KV cache"
    )
    lines.append("")
    lines.append("Per-tensor inventory (ranked by total bytes across all layers):")
    lines.append(
        f"  {'Tensor':<26} | {'Scaling':<10} | {'Shape (per layer)':<28} | "
        f"{'Dtype':<8} | {'Bytes/layer':>12} | {'Total':>10} | {'Share':>6}"
    )
    lines.append("  " + "-" * 110)
    for r in payload["sidecar_ranked"]:
        shape_str = "x".join(str(x) for x in (r["per_layer_shape"] or [])) or "(none)"
        if len(shape_str) > 28:
            shape_str = shape_str[:25] + "..."
        bpl = r["per_layer_bytes"]
        bpl_str = (f"{bpl/(1024**2):>8.2f} MB" if bpl >= 1024*1024
                   else f"{bpl/1024:>8.2f} KB" if bpl >= 1024
                   else f"{bpl:>8d} B ")
        total_str = (f"{r['total_gb']:>7.3f} GB" if r['total_bytes'] >= 1024**3
                     else f"{r['total_mb']:>7.2f} MB" if r['total_bytes'] >= 1024**2
                     else f"{r['total_bytes']:>9d} B")
        share_str = f"{r['share_of_sidecars']*100:>5.1f}%"
        lines.append(
            f"  {r['tensor']:<26} | {r['scaling']:<10} | {shape_str:<28} | "
            f"{(r['per_layer_dtype'] or 'n/a'):<8} | {bpl_str:>12} | "
            f"{total_str:>10} | {share_str:>6}"
        )
    lines.append("")
    lines.append("Aggregated by scaling-law category:")
    by_cat_gb = payload["sidecar_by_category_gb"]
    for cat in ("per_token", "per_block", "per_slot", "fixed"):
        gb = by_cat_gb.get(cat, 0.0)
        pct = (gb / sc_gb * 100) if sc_gb > 0 else 0.0
        lines.append(f"  {cat:<12}: {gb:>6.3f} GB  ({pct:>4.1f}% of sidecars)")
    lines.append("")
    pm = payload["per_token_marginal_bytes"]
    lines.append(
        f"Per-cached-token costs (bytes per token per layer):"
    )
    lines.append(
        f"  sidecar overhead   = {pm['sidecar_per_token_per_layer']:>6.1f} bytes/token/layer"
    )
    lines.append(
        f"  vLLM KV cache      = {pm['cache_per_token_per_layer']:>6.1f} bytes/token/layer"
    )
    if pm["cache_per_token_per_layer"] > 0:
        ratio = pm["sidecar_per_token_per_layer"] / pm["cache_per_token_per_layer"]
        lines.append(
            f"  sidecar / cache    = {ratio:>6.3f}x  (sidecar adds {ratio*100:.1f}% on top "
            f"of every cached token)"
        )
    print("\n".join(lines))


def aggregate_report(
    audit_jsons: Dict[int, Path],
    report_json: Path,
    report_txt: Path,
) -> int:
    """Read per-mml audit JSONs, produce a single findings report
    showing scaling across max_model_lens + a ranked diet table.
    """
    loaded: Dict[int, Dict[str, Any]] = {}
    for mml, p in audit_jsons.items():
        if p.exists():
            loaded[mml] = json.loads(p.read_text())
    if not loaded:
        print("FAIL: no audit JSONs found.")
        return 1

    # Scaling table — for each tensor, show its size at each mml.
    tensor_names = sorted({r["tensor"]
                           for payload in loaded.values()
                           for r in payload["sidecar_ranked"]})
    scaling_rows: List[Dict[str, Any]] = []
    for name in tensor_names:
        row: Dict[str, Any] = {"tensor": name}
        for mml, payload in loaded.items():
            r = next((x for x in payload["sidecar_ranked"] if x["tensor"] == name), None)
            if r is not None:
                row[f"bytes_mml{mml}"] = r["total_bytes"]
                row[f"gb_mml{mml}"]    = r["total_gb"]
                row["scaling"] = r["scaling"]
        scaling_rows.append(row)
    # Sort by largest mml's size (most relevant for the diet decision).
    largest_mml = max(loaded.keys())
    scaling_rows.sort(key=lambda r: r.get(f"bytes_mml{largest_mml}", 0), reverse=True)

    # Diet-options table — uses measured sizes from the largest mml to
    # estimate savings. Quality risk estimates from the design doc;
    # implementation cost rough.
    largest = loaded[largest_mml]
    v_scale_gb = next((r["total_gb"] for r in largest["sidecar_ranked"]
                       if r["tensor"] == "v_scale_ext"), 0)
    v_xmin_gb = next((r["total_gb"] for r in largest["sidecar_ranked"]
                      if r["tensor"] == "v_xmin_ext"), 0)
    k_protect_gb = next((r["total_gb"] for r in largest["sidecar_ranked"]
                         if r["tensor"] == "k_protect_ext"), 0)
    k_scale_gb = next((r["total_gb"] for r in largest["sidecar_ranked"]
                       if r["tensor"] == "k_scale_ext"), 0)
    k_xmin_gb = next((r["total_gb"] for r in largest["sidecar_ranked"]
                      if r["tensor"] == "k_xmin_ext"), 0)
    v_grouped_gb = v_scale_gb + v_xmin_gb
    k_meta_gb    = k_scale_gb + k_xmin_gb
    total_sidecar_gb = largest["sidecar_total_gb_all_layers"]

    diet_options = [
        {
            "id": "A",
            "name": "Halve V quantization groups (v_n_groups: 4 → 2, group_size: 32 → 64)",
            "target_tensors": ["v_scale_ext", "v_xmin_ext"],
            "savings_gb": v_grouped_gb / 2,
            "savings_pct_of_total_sidecars": (v_grouped_gb / 2) / total_sidecar_gb * 100,
            "quality_risk": "Moderate — coarser V quantization. Acceptable if "
                            "per-channel V dynamic range is uniform; risky if a "
                            "few channels dominate. Mitigate via byte-eq A/B + "
                            "token-agreement benchmark.",
            "impl_cost": "~2 days. CUDA V kernel currently asserts group_size==32; "
                         "needs warp-pair reduction for group_size=64.",
        },
        {
            "id": "F",
            "name": "Reduce protected channels (n_protect: 5 → 3)",
            "target_tensors": ["k_protect_ext"],
            "savings_gb": k_protect_gb * (2 / 5),
            "savings_pct_of_total_sidecars": (k_protect_gb * (2/5)) / total_sidecar_gb * 100,
            "quality_risk": "Moderate — depends on calibration. The protect-mask "
                            "design selects the top-N most activation-heavy "
                            "channels per head; cutting from 5 to 3 keeps the "
                            "top-3 but loses the next two. Per-model calibration "
                            "data shows whether the 4th and 5th channels carry "
                            "material mass.",
            "impl_cost": "~1 day. Re-run Phase 5B.0 calibration with n_protect=3 "
                         "and regenerate the protect-mask artifact. No code "
                         "changes in the writer/kernel.",
        },
        {
            "id": "C",
            "name": "Quantize sidecars bf16 → fp8 (e4m3)",
            "target_tensors": ["v_scale_ext", "v_xmin_ext", "k_scale_ext",
                                "k_xmin_ext", "k_protect_ext"],
            "savings_gb": (v_grouped_gb + k_meta_gb + k_protect_gb) / 2,
            "savings_pct_of_total_sidecars": ((v_grouped_gb + k_meta_gb + k_protect_gb) / 2)
                                              / total_sidecar_gb * 100,
            "quality_risk": "High — fp8 has 3-bit mantissa; quantization noise on "
                            "the scale/xmin values compounds with the int4 cache "
                            "quantization noise. Total dequant error grows. "
                            "Mitigate via long-context quality A/B run.",
            "impl_cost": "~3 days. Kernel write-side: emit fp8 via "
                         "__nv_fp8_e4m3 intrinsics. Read-side (flash_attn): "
                         "add fp8 → bf16 dequant in the int4_packed template.",
        },
        {
            "id": "D",
            "name": "Eliminate k_protect_ext (inline protected dims into kv_cache)",
            "target_tensors": ["k_protect_ext"],
            "savings_gb": k_protect_gb,
            "savings_pct_of_total_sidecars": k_protect_gb / total_sidecar_gb * 100,
            "quality_risk": "Low (in principle — design preserves the protect-mask "
                            "semantics) but high implementation risk: the int4_packed "
                            "kernel's input layout would change.",
            "impl_cost": "~5 days. Kernel surgery on vllm-flash-attn-dev's "
                         "int4_packed template. Recommend skipping unless A+F+C "
                         "fall short.",
        },
    ]
    # Sort diet options by savings.
    diet_options.sort(key=lambda d: d["savings_gb"], reverse=True)

    # Combined-stack projection.
    stack_savings_gb = sum(d["savings_gb"] for d in diet_options[:3])  # A + F + C

    report = {
        "audit_runs": {str(mml): str(p) for mml, p in audit_jsons.items()},
        "model":      next(iter(loaded.values()))["model"],
        "max_model_lens_audited": sorted(loaded.keys()),
        "num_layers": next(iter(loaded.values()))["num_layers"],
        "scaling_table": scaling_rows,
        "totals_by_mml": {
            mml: {
                "kv_cache_total_gb":  payload["kv_cache_total_gb_all_layers"],
                "sidecar_total_gb":   payload["sidecar_total_gb_all_layers"],
                "hbm_after_warmup_gb": payload["hbm_after_warmup"]["used_gb"],
                "non_pytorch_gb":     payload["hbm_after_warmup"]["non_pytorch_gb"],
                "num_gpu_blocks":     payload["kv_cache_config"].get("num_gpu_blocks"),
                "max_concurrency":    payload["kv_cache_config"].get("max_concurrency"),
            }
            for mml, payload in loaded.items()
        },
        "by_category_at_largest_mml": loaded[largest_mml]["sidecar_by_category_gb"],
        "per_token_marginal_at_largest_mml": loaded[largest_mml]["per_token_marginal_bytes"],
        "diet_options_ranked": diet_options,
        "projected_stack_savings_gb_A_plus_F_plus_C": stack_savings_gb,
        "target_delta_to_close": 5.0,   # observed delta vs bf16 from the long-context bench
        "stack_closes_target":  stack_savings_gb >= 5.0,
    }
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, indent=2))

    lines: List[str] = []
    lines.append("=" * 84)
    lines.append("Phase 6G — Sidecar overhead audit (Step 1 deliverable)")
    lines.append("=" * 84)
    lines.append(f"Model: {report['model']}")
    lines.append(f"Layers audited: {report['num_layers']}")
    lines.append(f"Max model lens: {report['max_model_lens_audited']}")
    lines.append("")
    lines.append("Totals (all layers, after warmup):")
    lines.append(
        f"  {'mml':>6} | {'NB blocks':>10} | {'max_conc':>9} | "
        f"{'kv_cache GB':>12} | {'sidecar GB':>11} | {'non-PyTorch GB':>15} | {'HBM total GB':>13}"
    )
    lines.append("  " + "-" * 96)
    for mml in sorted(loaded.keys()):
        t = report["totals_by_mml"][mml]
        lines.append(
            f"  {mml:>6} | {t['num_gpu_blocks'] or 0:>10} | "
            f"{(t['max_concurrency'] or 0):>9.1f} | "
            f"{t['kv_cache_total_gb']:>12.3f} | {t['sidecar_total_gb']:>11.3f} | "
            f"{t['non_pytorch_gb']:>15.3f} | {t['hbm_after_warmup_gb']:>13.3f}"
        )
    lines.append("")
    lines.append("Scaling-law decomposition at largest mml "
                 f"({largest_mml}):")
    cat_gb = report["by_category_at_largest_mml"]
    sc_total = sum(cat_gb.values()) or 1
    for cat in ("per_token", "per_block", "per_slot", "fixed"):
        gb = cat_gb.get(cat, 0)
        pct = gb / sc_total * 100
        notes = {
            "per_token": "(scales with NB*BS — the cache token count)",
            "per_block": "(scales with NB only, amortized over BS=32 per block)",
            "per_slot":  "(scales with max_active_slots, ~16 — fixed at allocation)",
            "fixed":     "(per-model lookup tables — constant)",
        }[cat]
        lines.append(f"  {cat:<12}: {gb:>6.3f} GB  ({pct:>5.1f}%)  {notes}")
    lines.append("")
    lines.append("Per-cached-token marginal cost (bytes / token / layer):")
    pm = report["per_token_marginal_at_largest_mml"]
    sc_per_tok = pm["sidecar_per_token_per_layer"]
    cache_per_tok = pm["cache_per_token_per_layer"]
    lines.append(f"  sidecars  : {sc_per_tok:>7.1f}")
    lines.append(f"  KV cache  : {cache_per_tok:>7.1f}")
    if cache_per_tok > 0:
        lines.append(
            f"  ratio     : {(sc_per_tok / cache_per_tok):>7.3f}x  "
            f"(sidecars add {(sc_per_tok/cache_per_tok)*100:.1f}% overhead per cached token)"
        )
    lines.append("")
    lines.append("Per-tensor ranking at largest mml (top contributors first):")
    largest_payload = loaded[largest_mml]
    lines.append(
        f"  {'Tensor':<26} | {'Scaling':<10} | {'Total GB':>10} | "
        f"{'% of sidecars':>14}"
    )
    lines.append("  " + "-" * 70)
    for r in largest_payload["sidecar_ranked"]:
        if r["total_bytes"] < 1024 * 1024:
            continue  # hide tensors under 1 MB
        lines.append(
            f"  {r['tensor']:<26} | {r['scaling']:<10} | "
            f"{r['total_gb']:>10.3f} | {r['share_of_sidecars']*100:>13.1f}%"
        )
    lines.append("")
    lines.append("Scaling across max_model_lens:")
    lines.append(
        f"  {'Tensor':<26} | " +
        " | ".join(f"GB @ {m:>5}" for m in sorted(loaded.keys()))
    )
    lines.append("  " + "-" * 70)
    for row in report["scaling_table"]:
        if not any(row.get(f"bytes_mml{m}", 0) >= 1024*1024
                   for m in sorted(loaded.keys())):
            continue
        cells = " | ".join(
            f"{row.get(f'gb_mml{m}', 0):>8.3f}"
            for m in sorted(loaded.keys())
        )
        lines.append(f"  {row['tensor']:<26} | {cells}")
    lines.append("")
    lines.append("Diet options ranked by estimated savings (no implementation; "
                 "audit-only recommendation):")
    for d in report["diet_options_ranked"]:
        lines.append(f"  [{d['id']}] {d['name']}")
        lines.append(
            f"      Targets:        {', '.join(d['target_tensors'])}"
        )
        lines.append(
            f"      Est. savings:   {d['savings_gb']:.2f} GB  "
            f"({d['savings_pct_of_total_sidecars']:.1f}% of sidecars)"
        )
        lines.append(f"      Quality risk:  {d['quality_risk']}")
        lines.append(f"      Impl cost:     {d['impl_cost']}")
        lines.append("")
    lines.append(
        f"Projected combined savings (A + F + C stacked): "
        f"{report['projected_stack_savings_gb_A_plus_F_plus_C']:.2f} GB"
    )
    target = report["target_delta_to_close"]
    if report["stack_closes_target"]:
        lines.append(
            f"  Stack >= {target:.1f} GB target — projected to close the "
            f"+5 GB delta to bf16."
        )
    else:
        lines.append(
            f"  Stack < {target:.1f} GB target — stacking A + F + C alone "
            f"will NOT close the +5 GB delta. Recommend also evaluating "
            f"Option D (eliminate k_protect_ext) or accepting partial reduction."
        )
    lines.append("")
    lines.append("No code changes proposed yet. Per the Phase 6G design doc, the next "
                 "step is user approval of which diet option(s) to pursue.")

    report_txt.parent.mkdir(parents=True, exist_ok=True)
    report_txt.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--worker", action="store_true",
                   help="Internal: run a single mml audit.")
    p.add_argument("--max-model-len", type=int, default=None,
                   help="Worker mode: which mml to audit.")
    p.add_argument("--output", type=str,
                   help="Worker mode: JSON output path.")
    p.add_argument("--output-dir", type=str,
                   default="bench_out/phase6g_sidecar_audit",
                   help="Driver mode: directory for audit JSONs + report.")
    p.add_argument("--max-model-lens", default="8192,16384,32768",
                   help="Driver mode: comma-separated mml values to audit.")
    p.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    p.add_argument("--max-num-seqs", type=int, default=16)
    args = p.parse_args()

    if args.worker:
        if args.max_model_len is None or not args.output:
            print("FAIL: --worker requires --max-model-len and --output.")
            return 2
        return run_worker(
            max_model_len=args.max_model_len,
            output_path=Path(args.output),
            model=args.model,
            gpu_memory_utilization=args.gpu_memory_utilization,
            max_num_seqs=args.max_num_seqs,
        )

    mmls = [int(x) for x in args.max_model_lens.split(",") if x.strip()]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    audit_paths = {m: out_dir / f"audit_mml{m}.json" for m in mmls}

    common = [
        "--worker",
        "--model", args.model,
        "--gpu-memory-utilization", str(args.gpu_memory_utilization),
        "--max-num-seqs", str(args.max_num_seqs),
    ]
    for mml in mmls:
        out_path = audit_paths[mml]
        print()
        print(f"=== Driver: auditing mml={mml} ===")
        cmd = [sys.executable, __file__] + common + [
            "--max-model-len", str(mml),
            "--output", str(out_path),
        ]
        ret = subprocess.run(cmd, check=False)
        if ret.returncode != 0:
            print(f"WARN: worker mml={mml} exited code {ret.returncode} — "
                  f"continuing with the remaining mmls.")

    return aggregate_report(
        audit_jsons=audit_paths,
        report_json=out_dir / "sidecar_audit_report.json",
        report_txt=out_dir / "sidecar_audit_report.txt",
    )


if __name__ == "__main__":
    sys.exit(main())
