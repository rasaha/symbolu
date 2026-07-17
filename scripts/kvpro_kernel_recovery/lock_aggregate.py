#!/usr/bin/env python3
"""Lock the K2 aggregate from the whole-step decode profile.

Turns the whole-step torch.profiler CSVs (int4_captured vs bf16_stock) into the three
decision outputs for the K2 build gate, using the CORRECTED projection:

    X            = removable share OF THE WHOLE DECODE STEP
                 = (fuseable gather+copy self-CUDA) / (decode-step self-CUDA)
    speedup      = 1 / (1 - rho*X)              # relative decode speedup over current Route-C
    new_ratio    = base_ratio * speedup         # projected new KVPro/BF16 decode ratio

`speedup` (KVPro-over-KVPro) and `base_ratio` (KVPro-over-BF16) are DIFFERENT quantities;
the earlier `0.22/(1-X)` shorthand conflated them. `new_ratio = base * 1/(1-rho*X)` keeps
them separate (per the ChatGPT review).

Two data-hygiene rules the naive analyzer got wrong (see K2_AGGREGATE_LOCK_MEASURED.md):
  1. Sum LEAF device kernels (`void …`, `ampere_…`), NOT `aten::mm`/`aten::linear` parent
     rows — those include their child kernels and triple-count.
  2. Isolate DECODE from PREFILL by kernel identity: decode attention is the split-KV
     kv-cache kernel (`fwd_kvcache`/`flash_fwd_splitkv`); prefill attention is the varlen
     `flash_fwd_kernel`; the big `ampere_*s16816gemm*` are prefill-shaped.

Usage:
    python lock_aggregate.py --selftest
    python lock_aggregate.py --int4-csv int4_kernels.csv [--bf16-csv bf16_kernels.csv]
    python lock_aggregate.py --fuseable-ms 8181 --decode-step-ms 21645 --base-ratio 0.093
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Realizability: a fused in-kernel paged gather still does some in-register gather, so the
# realized removal is < the measured fuseable. Sweep a band; 0.75 is the headline.
RHO_BAND = (1.0, 0.85, 0.75, 0.7)
RHO_HEADLINE = 0.75
BUILD_GATE = 0.15  # relative decode improvement required to justify the K2 build


# ---------------------------------------------------------------------------
# CSV parsing — leaf-kernel self time, decode/prefill classification by name.
# ---------------------------------------------------------------------------
def is_device_kernel(name: str) -> bool:
    """True for a leaf CUDA kernel row, False for an aten/_C/_vllm operator row.

    Operator rows (`aten::mm`, `_vllm_fa2_C::fwd_kvcache_int4`, `vllm::unified_…`) carry
    device_time_total that INCLUDES their child kernels; summing them double-counts.
    Leaf kernels are CUDA templates (`void …<…>`) or named GEMM tiles (`ampere_…`,
    `cutlass…`, `sm80…`).
    """
    n = name.strip()
    if n.startswith(("void ", "ampere_", "ampere<", "cutlass", "sm80", "sm90")):
        return True
    if n.startswith(("aten::", "_C::", "_vllm_fa2_C::", "_vllm_fa3_C::")):
        return False
    if "::" in n and "<" not in n and "(" not in n:
        # bare "namespace::op" with no template/args -> operator wrapper (e.g.
        # vllm::unified_attention_with_output, cudaLaunchKernel).
        return False
    # A demangled template instantiation with <...> is a kernel; default: treat rows with
    # angle-bracket template params as kernels, everything else as operator noise.
    return "<" in n


def classify_kernel(name: str) -> str:
    """Bucket a LEAF device-kernel name into decode/prefill components."""
    n = name.lower()
    # decode attention: split-KV kv-cache path (fwd_kvcache -> flash_fwd_splitkv).
    if "splitkv" in n or "flash_fwd_splitkv" in n:
        return "decode_attn"
    # prefill attention: varlen flash_fwd (NOT splitkv).
    if "flash_fwd_kernel" in n or ("flash" in n and "fwd" in n and "split" not in n):
        return "prefill_attn"
    # gather: the paged int4 + 5-sidecar materialization (index_select / index kernels).
    if "index_elementwise" in n or "indexselect" in n or "index_select" in n:
        return "gather"
    # bf16-backing / prep copy / clone.
    if "elementwise_kernel" in n and "index" not in n:
        return "copy"
    if "s16816gemm" in n or "gemm" in n or n.startswith("ampere_") or "cutlass" in n:
        return "gemm"
    return "other"


def parse_leaf_kernels(path: Path):
    """Return list of (name, self_ns, bucket) for LEAF device kernels only."""
    rows = []
    with path.open() as f:
        reader = csv.reader(f)
        header = None
        for row in reader:
            if not row:
                continue
            if header is None:
                if any("Total Time" in c for c in row) or any(c.startswith("Time") for c in row):
                    header = [c.strip() for c in row]
                continue
            d = dict(zip(header, [c.strip() for c in row]))
            name = d.get("Name") or d.get("Kernel Name") or ""
            if not is_device_kernel(name):
                continue
            raw = (d.get("Total Time") or d.get("Time(ns)") or "").replace(",", "").replace("ns", "").strip()
            try:
                self_ns = float(raw) if raw else 0.0
            except ValueError:
                self_ns = 0.0
            rows.append((name, self_ns, classify_kernel(name)))
    return rows


def summarize_ms(rows):
    out = {}
    for _, ns, bucket in rows:
        out[bucket] = out.get(bucket, 0.0) + ns / 1e6
    return out


# ---------------------------------------------------------------------------
# Projection — the corrected ChatGPT formula.
# ---------------------------------------------------------------------------
def project(fuseable_ms, decode_step_ms, base_ratio, rho=RHO_HEADLINE):
    """Return the three K2 outputs for one realizability rho.

    fuseable_ms   : removable gather+copy self-CUDA over the decode step
    decode_step_ms: whole decode-step self-CUDA (read path + gemm + misc)
    base_ratio    : current KVPro/BF16 decode ratio (int4 tok/s ÷ bf16 tok/s), <1
    """
    X = fuseable_ms / decode_step_ms if decode_step_ms else 0.0
    removed = rho * X
    speedup = 1.0 / (1.0 - removed) if removed < 1.0 else float("inf")
    return {
        "rho": rho,
        "X_removable_share": X,
        "removed_effective": removed,
        "decode_speedup": speedup,            # output 1: KVPro-over-current-KVPro
        "rel_improvement": speedup - 1.0,     # output 1 as a %
        "new_bf16_ratio": base_ratio * speedup,  # output 2: KVPro-over-BF16
        "clears_build_gate": (speedup - 1.0) >= BUILD_GATE,  # output 3
    }


def analyze(fuseable_ms, decode_step_ms, base_ratio):
    return {rho: project(fuseable_ms, decode_step_ms, base_ratio, rho) for rho in RHO_BAND}


def _fmt_block(title, res_by_rho, base_ratio):
    lines = [title, "  rho   X      speedup   +rel     new/BF16   gate"]
    for rho in RHO_BAND:
        r = res_by_rho[rho]
        gate = "PASS" if r["clears_build_gate"] else "fail"
        lines.append(f"  {rho:<4.2f}  {r['X_removable_share']:.3f}  "
                     f"{r['decode_speedup']:.3f}x   {r['rel_improvement']*100:+5.1f}%  "
                     f"{r['new_bf16_ratio']:.3f}x    {gate}")
    lines.append(f"  (base KVPro/BF16 decode ratio = {base_ratio:.3f}x; "
                 f"build gate = +{BUILD_GATE*100:.0f}% decode)")
    return "\n".join(lines)


def _from_csv(int4_csv, bf16_csv):
    rows = parse_leaf_kernels(Path(int4_csv))
    s = summarize_ms(rows)
    decode_attn = s.get("decode_attn", 0.0)
    gather = s.get("gather", 0.0)
    copy = s.get("copy", 0.0)
    # decode GEMM+misc (ms) is not separable from prefill by name in a single mixed
    # profile; estimate it from the bf16 decode floor if given, else a small fixed pad.
    decode_misc = 900.0
    if bf16_csv:
        b = summarize_ms(parse_leaf_kernels(Path(bf16_csv)))
        # bf16 decode attention + its small decode gemm ~ the non-fuseable decode floor.
        bf16_decode = b.get("decode_attn", 0.0)
        decode_misc = max(500.0, min(2000.0, bf16_decode))  # bounded, ms
    fuseable = gather + copy
    decode_step = decode_attn + fuseable + decode_misc
    print("== leaf-kernel self-CUDA (int4, ms) ==")
    for k in ("decode_attn", "gather", "copy", "prefill_attn", "gemm", "other"):
        if k in s:
            print(f"  {k:<14} {s[k]:>10.1f}")
    print(f"\n  fuseable (gather+copy)    = {fuseable:8.1f} ms")
    print(f"  decode-attn (irreducible) = {decode_attn:8.1f} ms")
    print(f"  decode-misc (est)         = {decode_misc:8.1f} ms")
    print(f"  decode-step total         = {decode_step:8.1f} ms")
    if bf16_csv:
        # base ratio from decode-attn proxy (int4 vs bf16) is the cleanest available.
        b = summarize_ms(parse_leaf_kernels(Path(bf16_csv)))
        base = (b.get("decode_attn", 0.0) + 900.0) / decode_step if decode_step else 0.0
        print(f"  base KVPro/BF16 (decode)  = {base:8.3f}x  "
              f"(bf16 decode-attn {b.get('decode_attn', 0.0):.1f} ms)")
    else:
        base = 0.093
        print(f"  base KVPro/BF16 (decode)  = {base:8.3f}x  (default; pass --bf16-csv to measure)")
    print()
    print(_fmt_block("== K2 projection (corrected: new = base * 1/(1-rho*X)) ==",
                     analyze(fuseable, decode_step, base), base))


def _selftest() -> int:
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    # (A) ChatGPT's worked example: read-path 40% of step, fuseable 43.3% of read path ->
    # X=0.173, ideal speedup 1.209x, new ratio 0.22*1.209=0.266x.
    X = 0.40 * 0.433
    r = project(X * 100, 100.0, base_ratio=0.22, rho=1.0)  # fuseable=X*100 of 100 -> share=X
    check("ChatGPT example X≈0.173", abs(r["X_removable_share"] - 0.173) < 1e-3)
    check("ChatGPT example ideal speedup≈1.209x", abs(r["decode_speedup"] - 1.209) < 2e-3)
    check("ChatGPT example new ratio≈0.266x", abs(r["new_bf16_ratio"] - 0.266) < 2e-3)
    r75 = project(X * 100, 100.0, base_ratio=0.22, rho=0.75)
    check("ChatGPT example rho=0.75 gain in 14-17%",
          0.14 <= r75["rel_improvement"] <= 0.17)

    # (B) new_ratio is base*speedup, NOT 0.22/(1-X) as if speedup were the ratio.
    check("new_ratio = base*speedup (not conflated)",
          abs(r["new_bf16_ratio"] - 0.22 * r["decode_speedup"]) < 1e-9)

    # (C) the pod's MEASURED decode-step breakdown (2026-07-17, ctx≈14.7k, B=32).
    fuseable = 6521.0 + 1660.0          # gather + copy (ms)
    decode_step = 12464.0 + fuseable + 900.0   # + decode attn + misc
    base = 0.093                        # measured int4/bf16 decode ratio
    m = project(fuseable, decode_step, base, rho=RHO_HEADLINE)
    check("measured X in 0.35-0.40", 0.35 <= m["X_removable_share"] <= 0.40)
    check("measured decode speedup (rho=.75) in 1.35-1.45x",
          1.35 <= m["decode_speedup"] <= 1.45)
    check("measured clears build gate (>15%)", m["clears_build_gate"])
    check("measured new ratio still <0.15x (net loss vs bf16)", m["new_bf16_ratio"] < 0.15)
    mi = project(fuseable, decode_step, base, rho=1.0)
    check("measured ideal speedup in 1.55-1.65x", 1.55 <= mi["decode_speedup"] <= 1.65)

    # (D) classification / leaf filter.
    check("splitkv -> decode_attn",
          classify_kernel("void flash::flash_fwd_splitkv_kernel<Flash_fwd...>") == "decode_attn")
    check("varlen flash_fwd -> prefill_attn",
          classify_kernel("void flash::flash_fwd_kernel<Flash_fwd_kernel_traits...>") == "prefill_attn")
    check("index_elementwise -> gather",
          classify_kernel("void at::native::index_elementwise_kernel<128,4,...>") == "gather")
    check("ampere gemm -> gemm",
          classify_kernel("ampere_bf16_s16816gemm_bf16_128x256_ldg8_f2f_stages") == "gemm")
    check("aten::mm is NOT a leaf kernel", not is_device_kernel("aten::mm"))
    check("_vllm_fa2_C::fwd_kvcache_int4 is NOT a leaf", not is_device_kernel("_vllm_fa2_C::fwd_kvcache_int4"))
    check("vllm::unified_attention_with_output is NOT a leaf",
          not is_device_kernel("vllm::unified_attention_with_output"))
    check("void flash::… IS a leaf", is_device_kernel("void flash::flash_fwd_splitkv_kernel<...>"))
    check("ampere_… IS a leaf", is_device_kernel("ampere_bf16_s16816gemm_bf16_128x256_ldg8_f2f_stages"))

    print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAIL'}")
    return 0 if not fails else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lock the K2 aggregate from the whole-step profile")
    ap.add_argument("--int4-csv", type=str, default=None)
    ap.add_argument("--bf16-csv", type=str, default=None)
    ap.add_argument("--fuseable-ms", type=float, default=None,
                    help="removable gather+copy self-CUDA (ms) over the decode step")
    ap.add_argument("--decode-step-ms", type=float, default=None,
                    help="whole decode-step self-CUDA (ms)")
    ap.add_argument("--base-ratio", type=float, default=0.093,
                    help="current KVPro/BF16 decode ratio (int4 tok/s ÷ bf16 tok/s)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if args.int4_csv:
        _from_csv(args.int4_csv, args.bf16_csv)
        return 0
    if args.fuseable_ms and args.decode_step_ms:
        print(_fmt_block("== K2 projection (corrected: new = base * 1/(1-rho*X)) ==",
                         analyze(args.fuseable_ms, args.decode_step_ms, args.base_ratio),
                         args.base_ratio))
        return 0
    ap.error("need --selftest, or --int4-csv, or --fuseable-ms + --decode-step-ms")


if __name__ == "__main__":
    raise SystemExit(main())
