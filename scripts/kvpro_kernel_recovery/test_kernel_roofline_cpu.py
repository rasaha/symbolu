#!/usr/bin/env python3
"""CPU self-checks for kernel_roofline.py (no GPU). Validates the byte/FLOP model
against the bf16 anchor and the int4 latency-bound verdict.

  python test_kernel_roofline_cpu.py   # -> "kernel_roofline CPU checks: N/N PASS"
"""
from __future__ import annotations

import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("kernel_roofline", os.path.join(_HERE, "kernel_roofline.py"))
KR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(KR)

_n = 0


def check(name, cond):
    global _n
    assert cond, f"FAIL: {name}"
    _n += 1
    print(f"  ok: {name}")


# (1) module selftest passes.
check("kernel_roofline --selftest returns 0", KR._selftest() == 0)

# (2) bf16 anchor: the model must reproduce a memory-bound, near-peak read, or the
# byte model is wrong and the int4 conclusion is untrustworthy.
rb = KR.roofline(32, 14745, KR.QWEN, "bf16", 0.58)
check("bf16 is MEMORY-BOUND", "MEMORY" in rb["bound"])
check("bf16 BW >= 70% peak", rb["bw_frac"] >= 0.70)

# (3) int4 verdict: latency/occupancy-bound with large recoverable headroom.
ri = KR.roofline(32, 14745, KR.QWEN, "int4", 6.955)
check("int4 is LATENCY/OCCUPANCY-BOUND", "LATENCY" in ri["bound"])
check("int4 BW << bf16 BW (same model)", ri["bw_frac"] < rb["bw_frac"] / 10)
check("int4 compressed: reads < bf16 bytes", ri["bytes"] < rb["bytes"])
check("int4 speedup ceiling > 10x", ri["speedup_ceiling"] > 10)

# (4) a hypothetical bandwidth-optimal int4 kernel would classify MEMORY-BOUND
# (proves the model doesn't force int4 to look bad — the time is what's bad).
opt = KR.roofline(32, 14745, KR.QWEN, "int4", ri["ideal_ms"])
check("bandwidth-optimal int4 -> MEMORY-BOUND", "MEMORY" in opt["bound"])

# (5) a compute-saturated hypothetical -> COMPUTE-BOUND (classifier not stuck on one label).
# Use int4's LOW byte count so bandwidth stays unsaturated while fp32 FLOP exceeds 0.55
# (bf16's large bytes would saturate BW at the same time — it is a balanced kernel).
f = KR.attn_flops(32, 14745, KR.QWEN)
t_compute_ms = (f / (KR.FP32_TFLOPs * 1e12)) * 1e3 / 0.6  # ~60% fp32
rc = KR.roofline(32, 14745, KR.QWEN, "int4", t_compute_ms)
check("compute-saturated hypothetical -> COMPUTE-BOUND", "COMPUTE" in rc["bound"])
check("compute case has unsaturated BW (isolated)", rc["bw_frac"] < 0.55)

# (6) context scaling: bytes and flops both grow with S.
check("int4 bytes grow with ctx",
      KR.kv_read_bytes(1, 32000, KR.QWEN, "int4") > KR.kv_read_bytes(1, 8000, KR.QWEN, "int4"))
check("flops grow with ctx",
      KR.attn_flops(1, 32000, KR.QWEN) > KR.attn_flops(1, 8000, KR.QWEN))

print(f"\nkernel_roofline CPU checks: {_n}/{_n} PASS")
