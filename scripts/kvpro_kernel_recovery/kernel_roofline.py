#!/usr/bin/env python3
"""Permission-free roofline for the int4 decode attention kernel (ncu blocked).

ncu is ERR_NVGPUCTRPERM-blocked, but we do NOT need it to classify the 12x int4
decode-attention kernel. We already MEASURED its per-call GPU self-time
(6.96 ms/call vs bf16 0.58 ms/call, K2_AGGREGATE_LOCK_MEASURED.md). A byte + FLOP
model of one decode-attention call, divided into that measured time, gives the
ACHIEVED HBM bandwidth and FLOP rate. Comparing to the A100 peaks classifies the
kernel as MEMORY-bound / COMPUTE-bound / LATENCY-OCCUPANCY-bound — the last is the
"stalled, saturating neither resource" regime that means the cost is recoverable.

The model is validated by the bf16 kernel: bf16 decode attention MUST come out
memory-bound at ~80% of HBM peak (it is a plain paged read); if the model says
otherwise the byte model is wrong. int4 is then read against the same model.

  python kernel_roofline.py                 # Qwen2.5-7B @ ctx14745 B=32, measured times
  python kernel_roofline.py --selftest      # CPU checks (no GPU)
  python kernel_roofline.py --ctx 32000 --batch 1 --int4-ms 2.1 --bf16-ms 0.9
"""
from __future__ import annotations

import argparse
import sys

# --- A100-SXM4-80GB peaks (sm_80) ---
HBM_GBs = 2039.0          # GB/s
FP32_TFLOPs = 19.5        # CUDA-core fp32 (the dequant ALU runs here, not tensor cores)
BF16_TENSOR_TFLOPs = 312.0

# --- Qwen2.5-7B-Instruct geometry ---
QWEN = dict(layers=28, q_heads=28, kv_heads=4, head_dim=128)

# int4_protected sidecar geometry
GROUP = 32       # per-block K/V quant group (= BS)
N_PROTECT = 5    # compact protected-K channels stored bf16


def kv_read_bytes(B, S, geom, dtype):
    """Bytes the decode-attention kernel reads from HBM for ONE layer, ONE step.

    Each of B sequences has its own S-token KV for this layer (kv_heads, head_dim).
    """
    kvh, hd = geom["kv_heads"], geom["head_dim"]
    elems_kv = B * S * kvh * hd            # per K, per V
    if dtype == "bf16":
        return elems_kv * 2 * 2            # 2 bytes, K+V
    # int4_protected:
    packed = elems_kv * 0.5 * 2           # 4-bit K+V
    groups = (S + GROUP - 1) // GROUP
    scale_xmin = B * groups * kvh * hd * 2 * 2   # (scale,xmin) x bf16, K+V
    protect = B * S * kvh * N_PROTECT * 2        # compact protected-K, bf16
    return packed + scale_xmin + protect


def attn_flops(B, S, geom):
    """QK^T + PV MACs for one decode-attention call (1 query token vs S keys)."""
    qh, hd = geom["q_heads"], geom["head_dim"]
    qk = B * qh * S * hd * 2      # QK^T
    pv = B * qh * S * hd * 2      # P@V
    return qk + pv               # softmax O(B*qh*S) is negligible


def roofline(B, S, geom, dtype, ms):
    """Return achieved BW / FLOP and the bound classification for one kernel."""
    t = ms * 1e-3
    b = kv_read_bytes(B, S, geom, dtype)
    f = attn_flops(B, S, geom)
    bw = b / t                                   # bytes/s
    fl = f / t                                   # flop/s
    bw_frac = bw / (HBM_GBs * 1e9)
    fp32_frac = fl / (FP32_TFLOPs * 1e12)
    tensor_frac = fl / (BF16_TENSOR_TFLOPs * 1e12)
    ideal_ms = (b / (HBM_GBs * 1e9)) * 1e3       # bandwidth-optimal time
    if bw_frac >= 0.55:
        bound = "MEMORY-BOUND (healthy — reads at HBM speed)"
    elif fp32_frac >= 0.55 or tensor_frac >= 0.55:
        bound = "COMPUTE-BOUND (ALU-saturated)"
    else:
        bound = "LATENCY/OCCUPANCY-BOUND (stalled — saturates NEITHER resource; recoverable)"
    return dict(dtype=dtype, ms=ms, bytes=b, flops=f, bw_GBs=bw / 1e9,
                bw_frac=bw_frac, fp32_frac=fp32_frac, tensor_frac=tensor_frac,
                ideal_ms=ideal_ms, speedup_ceiling=ms / ideal_ms if ideal_ms else 0.0,
                bound=bound)


def _fmt(r):
    return (f"  {r['dtype']:<6}  {r['ms']:>6.2f} ms/call   "
            f"{r['bytes']/1e6:>7.1f} MB   "
            f"BW {r['bw_GBs']:>7.1f} GB/s ({r['bw_frac']*100:>4.1f}% peak)   "
            f"FLOP {r['fp32_frac']*100:>4.1f}% fp32 / {r['tensor_frac']*100:>4.2f}% tc\n"
            f"          -> {r['bound']}\n"
            f"          -> bandwidth-optimal would be {r['ideal_ms']:.2f} ms "
            f"({r['speedup_ceiling']:.0f}x headroom)")


def analyze(B, S, geom, int4_ms, bf16_ms):
    ri = roofline(B, S, geom, "int4", int4_ms)
    rb = roofline(B, S, geom, "bf16", bf16_ms)
    print(f"decode-attention roofline — Qwen2.5-7B  ctx={S}  B={B}  (A100 HBM {HBM_GBs:.0f} GB/s)")
    print("=" * 96)
    print(_fmt(rb))
    print(_fmt(ri))
    print("=" * 96)
    # honest target: a competent int4 kernel pays some dequant ALU, ~1.5-2x bf16, not
    # the bandwidth-only floor. Report both the floor and the realistic target.
    realistic_ms = bf16_ms * 1.75
    print(f"VERDICT: int4 runs at {ri['bw_frac']*100:.1f}% of HBM bandwidth and "
          f"{ri['fp32_frac']*100:.1f}% of fp32 FLOP — {ri['bound'].split(' (')[0]}.")
    print(f"  The 12x is NOT inherent int4 cost: bf16 is memory-bound at "
          f"{rb['bw_frac']*100:.0f}% peak; int4 reads {rb['bytes']/ri['bytes']:.1f}x LESS data yet "
          f"costs {int4_ms/bf16_ms:.0f}x more.")
    print(f"  Realistic int4 target (~1.75x bf16, dequant included): ~{realistic_ms:.2f} ms/call "
          f"-> {int4_ms/realistic_ms:.0f}x kernel speedup available "
          f"(int4 decode {int4_ms/bf16_ms:.0f}x-slower -> ~{realistic_ms/bf16_ms:.1f}x-slower).")
    return ri, rb


def _selftest() -> int:
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    B, S = 32, 14745
    rb = roofline(B, S, QWEN, "bf16", 0.58)
    ri = roofline(B, S, QWEN, "int4", 6.955)

    # (A) model sanity: bf16 decode attention is memory-bound near HBM peak.
    check("bf16 K+V ~= 966 MB", abs(rb["bytes"] - 966e6) / 966e6 < 0.02)
    check("bf16 achieved BW in 70-95% peak", 0.70 <= rb["bw_frac"] <= 0.95)
    check("bf16 classified MEMORY-BOUND", "MEMORY" in rb["bound"])

    # (B) int4 reads less data but is latency/occupancy-bound.
    check("int4 reads LESS than bf16 (compressed)", ri["bytes"] < rb["bytes"])
    check("int4 read in 250-350 MB", 250e6 <= ri["bytes"] <= 350e6)
    check("int4 achieved BW < 5% peak", ri["bw_frac"] < 0.05)
    check("int4 achieved fp32 FLOP < 10% peak", ri["fp32_frac"] < 0.10)
    check("int4 classified LATENCY/OCCUPANCY-BOUND", "LATENCY" in ri["bound"])

    # (C) the recoverability claim: large speedup ceiling, not a fundamental wall.
    check("int4 bandwidth-optimal < bf16 time (compressed => faster ceiling)",
          ri["ideal_ms"] < 0.58)
    check("int4 speedup ceiling > 10x", ri["speedup_ceiling"] > 10)

    # (D) monotonic: longer context reads more bytes.
    check("bytes grow with context",
          kv_read_bytes(B, 32000, QWEN, "int4") > kv_read_bytes(B, 8000, QWEN, "int4"))

    print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAIL'}")
    return 0 if not fails else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Permission-free roofline for the int4 decode kernel")
    ap.add_argument("--ctx", type=int, default=14745)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--int4-ms", type=float, default=6.955, help="measured int4 attn ms/call")
    ap.add_argument("--bf16-ms", type=float, default=0.58, help="measured bf16 attn ms/call")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    analyze(args.batch, args.ctx, QWEN, args.int4_ms, args.bf16_ms)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
