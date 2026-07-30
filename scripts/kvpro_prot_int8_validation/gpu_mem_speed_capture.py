"""KVPro prot-int8 — REAL GPU memory + read-path speed capture: BF16 vs INT8 protected sidecar.

Drives the PRODUCTION paged writer (phase5b_4c_paged_writer.PagedKVWriter) on CUDA, in the two
modes that differ ONLY in the protected-sidecar representation:

  B (BF16 protect): env INT4_PROTECTED_PROT_INT8 unset  -> k_protect_ext bf16, read = passthrough
  C (INT8 protect): env INT4_PROTECTED_PROT_INT8=1      -> k_protect_ext uint8, read = dequant->bf16

Everything else (int4 residual, scales, xmins, page geometry) is identical, so every delta is the
protected sidecar. Uses the real Mistral v2 mask (k_min/k_max) so C == the shipped Phase-6N math.

WHAT THIS MEASURES (MEASURED, real torch.cuda on the stated GPU):
  1. Stored sidecar bytes: k_protect_ext (+ int8 dequant constants) — the memory the claim is about.
  2. Peak GPU allocated during prefill write and during a decode read.
  3. Read-path latency: get_packed_view over the whole context, CUDA-event timed (this is where C
     adds the int8->bf16 dequant that B does not do).
  4. The transient bf16 materialization C creates on read (B returns a view; C allocates a temp).

WHAT THIS IS NOT: full end-to-end vLLM decode TPS. The production decode kernel is the external
forked-vLLM flash_attn_with_int4_kvcache (closed CUDA); this harness does not invoke it. These are
writer/read-path GPU numbers — the honest, reproducible slice that isolates the sidecar. Label them
MEASURED (read-path), not "production decode TPS".

Usage:
  python gpu_mem_speed_capture.py \
    --mask "$PROTECT_MASK_PATH" \
    --seqlens 512,2048,8192 --iters 100 \
    --out-mem  artifacts/prot_int8_mistral/memory_results.csv \
    --out-perf artifacts/prot_int8_mistral/performance_results.csv
"""
from __future__ import annotations

import argparse
import csv
import gc
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "CTM_plus" / "KVPolicy"))

BS = 32


def _fresh_writer_module():
    """Import (or re-import) the writer so the prot_int8 env flag is re-read at construction."""
    import importlib
    from kv_policy import phase5b_4c_paged_writer as pw
    importlib.reload(pw)
    return pw


def _build_and_measure(pw, torch, mask_hd, kmin_hd, kmax_hd, S, iters, device):
    """Return (mem_dict, perf_dict) for the CURRENT env (bf16 or int8)."""
    NB = (S + BS - 1) // BS
    H, D = mask_hd.shape

    gc.collect(); torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
    base = torch.cuda.memory_allocated()

    # protect_minmax MUST stay on CPU: the writer stores it as _protect_minmax_cpu and does an
    # internal .cpu() gather in _lazy_alloc; passing CUDA tensors triggers a device mismatch.
    w = pw.PagedKVWriter(layer_idx=0, protect_mask=mask_hd.to(device),
                         protect_minmax=(kmin_hd.cpu(), kmax_hd.cpu()))
    kv_cache = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8, device=device)
    w._lazy_alloc(kv_cache)

    g = torch.Generator(device="cpu").manual_seed(0)
    # keys in-range of the calibrated bounds (no clipping) so C is a fair round-trip
    lo = kmin_hd.unsqueeze(0); hi = kmax_hd.unsqueeze(0)
    key = (lo + torch.rand((S, H, D), generator=g) * (hi - lo)).to(torch.bfloat16).to(device)
    val = torch.randn((S, H, D), generator=g).to(torch.bfloat16).to(device)
    slot = torch.arange(S, device=device)

    torch.cuda.reset_peak_memory_stats()
    w.write(key, val, kv_cache, slot)
    torch.cuda.synchronize()
    peak_write = torch.cuda.max_memory_allocated() - base

    # stored sidecar bytes (the memory the claim is about)
    prot = w.k_protect_ext
    prot_bytes = prot.element_size() * prot.nelement()
    const_bytes = 0
    if getattr(w, "_prot_int8_active", False):
        const_bytes = (w._prot_qmin.element_size() * w._prot_qmin.nelement()
                       + w._prot_qscale.element_size() * w._prot_qscale.nelement())
    all_sidecars = sum(t.element_size() * t.nelement() for t in
                       (w.k_scale_ext, w.k_xmin_ext, w.k_protect_ext, w.v_scale_ext, w.v_xmin_ext))

    block_ids = torch.arange(NB, device=device)

    # transient allocated by ONE read (C makes a bf16 temp; B returns a view)
    torch.cuda.synchronize(); before = torch.cuda.memory_allocated()
    view = w.get_packed_view(block_ids, kv_cache)
    torch.cuda.synchronize(); read_transient = torch.cuda.memory_allocated() - before
    del view

    # read-path latency: get_packed_view over the whole context, CUDA-event timed
    for _ in range(10):                       # warmup
        w.get_packed_view(block_ids, kv_cache)
    torch.cuda.synchronize()
    times_ms = []
    start = torch.cuda.Event(enable_timing=True); end = torch.cuda.Event(enable_timing=True)
    for _ in range(iters):
        start.record()
        w.get_packed_view(block_ids, kv_cache)
        end.record(); torch.cuda.synchronize()
        times_ms.append(start.elapsed_time(end))
    times_ms.sort()
    p50 = times_ms[len(times_ms) // 2]
    p95 = times_ms[min(len(times_ms) - 1, int(0.95 * len(times_ms)))]

    mem = dict(prot_bytes=prot_bytes, const_bytes=const_bytes, prot_total=prot_bytes + const_bytes,
               all_sidecars=all_sidecars, peak_write=peak_write, read_transient=read_transient,
               prot_dtype=str(prot.dtype))
    perf = dict(read_p50_ms=round(p50, 4), read_p95_ms=round(p95, 4))
    del w, kv_cache, key, val
    gc.collect(); torch.cuda.empty_cache()
    return mem, perf


def main(argv=None):
    ap = argparse.ArgumentParser(description="Real GPU memory + read-path speed: BF16 vs INT8 protect")
    ap.add_argument("--mask", default=os.environ.get("PROTECT_MASK_PATH"))
    ap.add_argument("--layer", type=int, default=0)
    ap.add_argument("--seqlens", default="512,2048,8192")
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--out-mem", default=str(REPO / "artifacts/prot_int8_mistral/memory_results.csv"))
    ap.add_argument("--out-perf", default=str(REPO / "artifacts/prot_int8_mistral/performance_results.csv"))
    args = ap.parse_args(argv)

    import torch
    if not torch.cuda.is_available():
        print("[FAIL] no CUDA device — this capture is GPU-only (RESOURCE_BLOCKED without a GPU).",
              file=sys.stderr)
        return 2
    if not args.mask or not os.path.isfile(args.mask):
        print(f"[FAIL] mask missing: {args.mask!r}", file=sys.stderr)
        return 3
    device = torch.device("cuda")
    gpu_name = torch.cuda.get_device_name(0)

    blob = torch.load(args.mask, map_location="cpu", weights_only=False)
    mask3d = blob["mask"] if isinstance(blob, dict) else blob
    kmin3d, kmax3d = blob.get("k_min"), blob.get("k_max")
    if kmin3d is None:
        print("[FAIL] mask has no k_min/k_max (need the v2 calibrated artifact for INT8).",
              file=sys.stderr)
        return 4
    L = args.layer
    mask_hd = mask3d[L].to(torch.int8)
    kmin_hd = kmin3d[L].to(torch.float32)
    kmax_hd = kmax3d[L].to(torch.float32)
    n_protect = int(mask_hd.sum(-1).max().item())

    seqlens = [int(x) for x in args.seqlens.split(",")]
    mem_rows, perf_rows = [], []
    print(f"GPU: {gpu_name} | layer {L} | H,D={tuple(mask_hd.shape)} | n_protect={n_protect}\n")

    for S in seqlens:
        results = {}
        for mode, flag in (("B_bf16", None), ("C_int8", "1")):
            if flag is None:
                os.environ.pop("INT4_PROTECTED_PROT_INT8", None)
            else:
                os.environ["INT4_PROTECTED_PROT_INT8"] = flag
            pw = _fresh_writer_module()
            mem, perf = _build_and_measure(pw, torch, mask_hd, kmin_hd, kmax_hd, S, args.iters, device)
            results[mode] = (mem, perf)

        (mB, pB), (mC, pC) = results["B_bf16"], results["C_int8"]
        prot_saved = mB["prot_bytes"] - mC["prot_total"]
        prot_saved_pct = 100.0 * prot_saved / mB["prot_bytes"] if mB["prot_bytes"] else 0.0
        speed_x = pC["read_p50_ms"] / pB["read_p50_ms"] if pB["read_p50_ms"] else float("nan")

        mem_rows.append({
            "seqlen": S, "n_protect": n_protect, "gpu": gpu_name,
            "B_prot_dtype": mB["prot_dtype"], "C_prot_dtype": mC["prot_dtype"],
            "B_prot_bytes": mB["prot_bytes"], "C_prot_payload_bytes": mC["prot_bytes"],
            "C_int8_const_bytes": mC["const_bytes"], "C_prot_total_bytes": mC["prot_total"],
            "prot_saved_bytes": prot_saved, "prot_saved_pct": round(prot_saved_pct, 2),
            "B_all_sidecars_bytes": mB["all_sidecars"], "C_all_sidecars_bytes": mC["all_sidecars"],
            "B_peak_write_bytes": mB["peak_write"], "C_peak_write_bytes": mC["peak_write"],
            "B_read_transient_bytes": mB["read_transient"],
            "C_read_transient_bytes": mC["read_transient"],
            "classification": "MEASURED-GPU (writer/read-path; not full vLLM decode)",
        })
        perf_rows.append({
            "seqlen": S, "n_protect": n_protect, "gpu": gpu_name,
            "B_read_p50_ms": pB["read_p50_ms"], "B_read_p95_ms": pB["read_p95_ms"],
            "C_read_p50_ms": pC["read_p50_ms"], "C_read_p95_ms": pC["read_p95_ms"],
            "C_over_B_p50_x": round(speed_x, 3),
            "classification": "MEASURED-GPU (get_packed_view read+dequant; not full vLLM decode)",
        })
        print(f"S={S:6}  prot {mB['prot_bytes']//1024} KiB (bf16) -> "
              f"{mC['prot_total']//1024} KiB (int8+const)  saved {prot_saved_pct:5.1f}%  |  "
              f"read p50 B={pB['read_p50_ms']:.3f}ms C={pC['read_p50_ms']:.3f}ms  (C/B={speed_x:.2f}x)  |  "
              f"C read-temp={mC['read_transient']//1024} KiB vs B={mB['read_transient']//1024} KiB")

    for path, rows in ((args.out_mem, mem_rows), (args.out_perf, perf_rows)):
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print("wrote", path)

    print("\nINTERPRETATION: 'prot_saved_pct' = the real stored-sidecar reduction (int8 halves it, "
          "minus tiny per-model constants). 'C_over_B_p50_x' > 1 means int8 read is SLOWER (it adds a "
          "dequant); ~1 means neutral. 'C_read_transient' > B shows the bf16 buffer int8 materializes "
          "before the kernel — memory is saved in STORAGE, spent briefly on READ. This is the sidecar/"
          "read-path slice, not full production decode TPS (external kernel not invoked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
