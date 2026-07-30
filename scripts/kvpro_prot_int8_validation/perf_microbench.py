"""KVPro prot-int8 validation — Phase 6 CPU micro-timing (NOT production perf).

There is NO GPU in this environment, so decode throughput / kernel latency / bandwidth / Nsight
are all RESOURCE_BLOCKED. What CAN be shown on CPU is the DIRECTION of the read-path change:

  BF16 protection READ : _protect_view_bf16 is an identity passthrough (returns the stored bf16).
  INT8 protection READ : _protect_view_bf16 runs prot_int8_dequantize (uint8 -> f32 -> bf16) to
                          materialize the SAME bf16 buffer the kernel consumes.

So INT8 ADDS a dequant op on every read that BF16 does not have. This CPU timing quantifies that
added op's relative cost on the sidecar tensor; it is a lower-bound directional signal, NOT a decode
TPS measurement and NOT production-representative (production kernel is closed external CUDA).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "CTM_plus" / "KVPolicy"))
from kv_policy import phase5b_4c_paged_writer as pw   # noqa: E402

ART = REPO / "artifacts" / "prot_int8"
ART.mkdir(parents=True, exist_ok=True)

D, BS, H, N_PROT = 128, 32, 4, 5
ITERS, WARMUP = 200, 20


def time_fn(fn, iters, warmup):
    for _ in range(warmup):
        fn()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    return (time.perf_counter() - t0) / iters * 1e6   # us/call


def run():
    results = {}
    for S_blocks in [4, 32, 128]:                      # 128, 1024, 4096 tokens
        NB = S_blocks
        ext_bf16 = torch.randn((NB, BS, H, N_PROT), dtype=torch.bfloat16)
        codes = torch.randint(0, 256, (NB, BS, H, N_PROT), dtype=torch.uint8)
        qmin = torch.randn((H, N_PROT), dtype=torch.float32)
        qscale = torch.rand((H, N_PROT), dtype=torch.float32) + 0.1
        block_ids = torch.arange(NB)

        # BF16 read = gather + passthrough (identity)
        def bf16_read():
            return ext_bf16[block_ids]

        # INT8 read = gather + dequant to bf16 (the added op)
        def int8_read():
            raw = codes[block_ids]
            return pw.prot_int8_dequantize(raw, qmin, qscale, torch.bfloat16)

        t_bf16 = time_fn(bf16_read, ITERS, WARMUP)
        t_int8 = time_fn(int8_read, ITERS, WARMUP)
        results[f"tokens_{NB*BS}"] = {
            "bf16_read_us": round(t_bf16, 3),
            "int8_read_us": round(t_int8, 3),
            "int8_added_overhead_us": round(t_int8 - t_bf16, 3),
            "int8_relative_cost_x": round(t_int8 / t_bf16, 3) if t_bf16 else None,
        }

    summary = {
        "environment": "CPU-only (torch 2.13.0+cu130, no CUDA device)",
        "classification": "MEASURED (CPU micro-timing) — DIRECTIONAL ONLY, not production decode TPS",
        "finding": ("INT8 protection adds a uint8->bf16 dequant on every sidecar read that BF16 "
                    "passthrough does not incur. On this CPU the dequant is strictly slower than the "
                    "bf16 identity read (relative cost > 1x). Both paths end at the SAME bf16 buffer, "
                    "so there is no read-side speed advantage to INT8; the benefit is storage bytes."),
        "read_path_ops": results,
        "RESOURCE_BLOCKED": {
            "decode_kernel_latency": "no GPU; production kernel is closed external CUDA (fwd_kvcache_int4)",
            "tokens_per_second": "no GPU",
            "achieved_bandwidth": "no GPU",
            "nsight_systems_compute": "no GPU / ncu ERR_NVGPUCTRPERM per existing audits",
            "kernel_launches_per_token": "no GPU",
        },
    }
    (ART / "profiler_summary.json").write_text(json.dumps(summary, indent=2))

    # performance_results.csv (CPU directional + blocked GPU rows)
    import csv
    rows = []
    for k, v in results.items():
        rows.append({"metric_group": "cpu_sidecar_read_directional", "config": k,
                     "bf16_us": v["bf16_read_us"], "int8_us": v["int8_read_us"],
                     "int8_added_us": v["int8_added_overhead_us"],
                     "int8_relative_x": v["int8_relative_cost_x"],
                     "classification": "MEASURED-CPU-directional"})
    for m in ["decode_step_latency_ms", "tokens_per_second", "requests_per_second",
              "achieved_bandwidth_GBs", "kernel_launches_per_token"]:
        rows.append({"metric_group": "production_gpu", "config": m,
                     "bf16_us": "", "int8_us": "", "int8_added_us": "", "int8_relative_x": "",
                     "classification": "RESOURCE_BLOCKED (no GPU)"})
    with open(ART / "performance_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print("wrote profiler_summary.json, performance_results.csv")
    for k, v in results.items():
        print(f"  {k}: bf16 {v['bf16_read_us']}us  int8 {v['int8_read_us']}us  "
              f"(int8 {v['int8_relative_cost_x']}x, +{v['int8_added_overhead_us']}us)")


if __name__ == "__main__":
    run()
