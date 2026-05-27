"""Phase 6D — analyzer for nsys stats output from bench_phase6_d_profile_gpu.py.

Reads two `nsys stats --report cuda_gpu_kern_sum --format csv` outputs
(int4_captured vs bf16_stock) and produces a side-by-side comparison
mapping each kernel to one of eight candidate bottleneck buckets:

  1. packed_int4_load — load of int4-packed K/V from HBM
  2. scale_xmin_load  — load of bf16 scale + xmin sidecars
  3. dequant          — int4 -> bf16 dequant in registers/shared
  4. protect_splice   — protected-dim bf16 splice into the K tile
  5. gemm_tc          — Q@K and P@V tensor-core GEMM
  6. mem_other        — memory ops that don't map to (1-4)
  7. graph_overhead   — kernel launches outside the main attention kernel
  8. other            — anything we can't classify (residual)

The classifier maps known kernel-name substrings to buckets. Anything
unrecognized lands in "other" and is listed so we can update the map.

Usage:
  # On the pod, after running both profile cells:
  nsys stats --report cuda_gpu_kern_sum --format csv \
      phase6d_int4.nsys-rep > int4_kernels.csv
  nsys stats --report cuda_gpu_kern_sum --format csv \
      phase6d_bf16.nsys-rep > bf16_kernels.csv

  # Then analyze:
  python CTM_plus/Bench/scripts/analyze_phase6d_profile.py \
      --int4-csv int4_kernels.csv \
      --bf16-csv bf16_kernels.csv \
      --out phase6d_kernel_diff.txt

The output report identifies WHICH bucket(s) account for the
int4-vs-bf16 throughput gap. The bucket with the biggest absolute
delta in wall time is the Phase 6D priority target.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


# Kernel-name -> bucket map. Substrings are matched case-insensitively
# against the demangled kernel name; first match wins. This is a best-
# effort initial map; unrecognized kernels land in "other" and will
# need to be classified by extending this dict.
#
# Convention: keys are substrings; values are bucket names.
BUCKET_MAP: List[Tuple[str, str]] = [
    # The main int4_protected flash-attn kernel — does its own internal
    # int4 load, dequant, GEMM. We can't split it without ncu. nsys
    # gives us its total time.
    ("flash::fwd_kernel",              "main_attn_kernel"),
    ("Flash::flash_fwd",               "main_attn_kernel"),
    ("flash_fwd_kernel",               "main_attn_kernel"),
    ("flash_attn_kernel",              "main_attn_kernel"),
    ("flash_kernel",                   "main_attn_kernel"),
    ("int4_packed_load",               "packed_int4_load"),
    ("int4_quant_dequant",             "dequant"),

    # Python-side: splice + sidecar prep ops (Phase 6 v2 Option B path)
    ("scatter_add",                    "mem_other"),
    ("index_select",                   "mem_other"),
    ("gather",                         "mem_other"),
    ("masked_scatter",                 "protect_splice"),
    ("index_put",                      "mem_other"),
    ("native::index",                  "mem_other"),
    ("at::native::index",              "mem_other"),
    ("copy_",                          "mem_other"),
    ("aten::copy",                     "mem_other"),

    # Quantization helpers (in our writer's splice path)
    ("amax_",                          "protect_splice"),
    ("amin_",                          "protect_splice"),
    ("clamp_min",                      "protect_splice"),
    ("clamp_max",                      "protect_splice"),
    ("round_",                         "protect_splice"),
    ("to_copy",                        "mem_other"),

    # vLLM / model components — these are common to BOTH cells and
    # should net out in the diff.
    ("LayerNorm",                      "model_other"),
    ("RMSNorm",                        "model_other"),
    ("matmul",                         "model_other"),
    ("gemm",                           "gemm_tc"),
    ("hgemm",                          "gemm_tc"),
    ("ampere_",                        "gemm_tc"),
    ("cublas",                         "gemm_tc"),
    ("cutlass",                        "gemm_tc"),
    ("rotary",                         "model_other"),
    ("silu",                           "model_other"),
    ("softmax",                        "model_other"),
    ("reshape_and_cache",              "kv_write"),
    ("topk",                           "sampling"),
    ("sample",                         "sampling"),

    # Memory allocation / graph machinery
    ("memcpy",                         "graph_overhead"),
    ("memset",                         "graph_overhead"),
    ("nccl",                           "graph_overhead"),
]


def classify(kernel_name: str) -> str:
    lname = kernel_name.lower()
    for pat, bucket in BUCKET_MAP:
        if pat.lower() in lname:
            return bucket
    return "other"


def _parse_nsys_csv(path: Path) -> List[Dict[str, object]]:
    """Read an `nsys stats --format csv` output.

    Schema (typical fields):
        Time(%), Total Time, Instances, Avg, Min, Max, StdDev, Name

    Total Time is in nanoseconds. We collect (name, total_ns, instances).
    """
    rows = []
    with path.open() as f:
        # nsys may emit a few header lines before the CSV header; skip
        # blank lines and find the row that starts with "Time(%)" or
        # has "Total Time" as a column.
        reader = csv.reader(f)
        header_idx = None
        header_cols = None
        for line_no, row in enumerate(reader):
            if not row:
                continue
            if header_idx is None:
                if any("Total Time" in c for c in row) or any(c.startswith("Time") for c in row):
                    header_idx = line_no
                    header_cols = [c.strip() for c in row]
                continue
            # Data row
            if header_cols is None:
                continue
            data = dict(zip(header_cols, [c.strip() for c in row]))
            # Coerce total time (handle commas + units like "ns")
            total_str = (data.get("Total Time") or data.get("Time(ns)") or
                         data.get("Total Time(ns)") or "")
            total_str = total_str.replace(",", "").replace("ns", "").strip()
            try:
                total_ns = float(total_str) if total_str else 0.0
            except ValueError:
                total_ns = 0.0
            instances_str = (data.get("Instances") or data.get("Calls") or "0")
            instances_str = instances_str.replace(",", "").strip()
            try:
                instances = int(float(instances_str))
            except ValueError:
                instances = 0
            name = data.get("Name") or data.get("Kernel Name") or ""
            rows.append({
                "name": name,
                "total_ns": total_ns,
                "instances": instances,
                "bucket": classify(name),
            })
    return rows


def _bucket_summary(rows: List[Dict[str, object]]) -> Dict[str, Tuple[float, int]]:
    """Return {bucket: (total_ns, n_kernels)}."""
    out = defaultdict(lambda: [0.0, 0])
    for r in rows:
        out[r["bucket"]][0] += r["total_ns"]
        out[r["bucket"]][1] += 1
    return {k: tuple(v) for k, v in out.items()}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--int4-csv", type=Path, required=True,
                   help="nsys stats output for the int4_captured cell")
    p.add_argument("--bf16-csv", type=Path, required=True,
                   help="nsys stats output for the bf16_stock cell")
    p.add_argument("--out", type=Path,
                   default=Path("bench_out/phase6d_kernel_diff.txt"))
    p.add_argument("--top-n-other", type=int, default=20,
                   help="In the 'unclassified' section, list this many "
                        "kernels by total time so we can extend BUCKET_MAP")
    args = p.parse_args()

    int4_rows = _parse_nsys_csv(args.int4_csv)
    bf16_rows = _parse_nsys_csv(args.bf16_csv)

    if not int4_rows:
        print(f"WARN: no rows parsed from {args.int4_csv}")
    if not bf16_rows:
        print(f"WARN: no rows parsed from {args.bf16_csv}")

    int4_buckets = _bucket_summary(int4_rows)
    bf16_buckets = _bucket_summary(bf16_rows)

    all_buckets = sorted(set(int4_buckets.keys()) | set(bf16_buckets.keys()))

    lines = []
    lines.append("=" * 78)
    lines.append("Phase 6D — Kernel-bucket diff: int4_captured vs bf16_stock")
    lines.append("=" * 78)
    lines.append(f"int4_csv: {args.int4_csv}")
    lines.append(f"bf16_csv: {args.bf16_csv}")
    lines.append("")
    int4_total = sum(t for t, _ in int4_buckets.values())
    bf16_total = sum(t for t, _ in bf16_buckets.values())
    lines.append(f"Total kernel time: int4={int4_total/1e6:.1f} ms   "
                 f"bf16={bf16_total/1e6:.1f} ms   "
                 f"int4/bf16 = {int4_total/bf16_total if bf16_total else 0:.2f}x")
    lines.append("")
    lines.append(f"{'Bucket':<22s} | {'int4 ms':>10s} | {'bf16 ms':>10s} | "
                 f"{'delta ms':>10s} | {'int4 share':>11s}")
    lines.append("-" * 78)

    rows_for_sort = []
    for b in all_buckets:
        i_ns, i_n = int4_buckets.get(b, (0.0, 0))
        f_ns, f_n = bf16_buckets.get(b, (0.0, 0))
        delta = i_ns - f_ns
        share = i_ns / int4_total if int4_total else 0
        rows_for_sort.append((b, i_ns, f_ns, delta, share, i_n, f_n))

    # Print in two passes: highlight the biggest int4-vs-bf16 deltas first.
    rows_for_sort.sort(key=lambda r: -r[3])  # delta desc
    lines.append("")
    lines.append("Buckets ranked by absolute int4 - bf16 time delta "
                 "(biggest = where the gap lives):")
    lines.append("")
    for b, i_ns, f_ns, delta, share, i_n, f_n in rows_for_sort:
        lines.append(f"{b:<22s} | {i_ns/1e6:>9.2f}  | {f_ns/1e6:>9.2f}  | "
                     f"{delta/1e6:>+9.2f}  | {share*100:>9.1f}%")

    lines.append("")
    lines.append("Top unclassified kernels (extend BUCKET_MAP if these "
                 "matter):")
    other_int4 = sorted(
        [r for r in int4_rows if r["bucket"] == "other"],
        key=lambda r: -r["total_ns"],
    )[:args.top_n_other]
    for r in other_int4:
        lines.append(f"  {r['total_ns']/1e6:>9.2f} ms  ({r['instances']:>5d} calls)  {r['name']}")

    out_path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nReport written to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
