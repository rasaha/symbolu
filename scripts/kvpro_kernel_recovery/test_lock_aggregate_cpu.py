#!/usr/bin/env python3
"""CPU self-checks for lock_aggregate.py (no GPU). Wraps its --selftest plus a few
end-to-end CSV-parse checks (leaf filter must reject double-counting parent rows).

  python test_lock_aggregate_cpu.py   # -> "lock_aggregate CPU checks: N/N PASS"
"""
from __future__ import annotations

import importlib.util
import os
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("lock_aggregate", os.path.join(_HERE, "lock_aggregate.py"))
LA = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(LA)

_n = 0


def check(name, cond):
    global _n
    assert cond, f"FAIL: {name}"
    _n += 1
    print(f"  ok: {name}")


# (1) the module's own selftest must pass (ChatGPT example + measured pod numbers + classify).
check("lock_aggregate --selftest returns 0", LA._selftest() == 0)

# (2) the CSV path rejects parent (double-counting) rows and keeps leaf kernels.
CSV = """Time(%),Total Time,Instances,Avg,Min,Max,StdDev,Name
39.33,22387000000,8160,2743000,0,0,0,aten::mm
26.21,14918000000,1792,8325000,0,0,0,ampere_bf16_s16816gemm_bf16_128x256_ldg8_f2f_stages
21.90,12464000000,1792,6955000,0,0,0,void flash::flash_fwd_splitkv_kernel<Flash_fwd_kernel_traits>
12.13,6906000000,896,7708000,0,0,0,void flash::flash_fwd_kernel<Flash_fwd_kernel_traits>
11.46,6521000000,8064,808000,0,0,0,void at::native::index_elementwise_kernel<128,4,at::native>
2.92,1660000000,3584,463000,0,0,0,void at::native::elementwise_kernel<128,4,at::native>
0.00,30456000000,2688,11330000,0,0,0,vllm::unified_attention_with_output
0.00,12477000000,1792,6963000,0,0,0,_vllm_fa2_C::fwd_kvcache_int4
"""
with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
    f.write(CSV)
    path = f.name
try:
    from pathlib import Path
    rows = LA.parse_leaf_kernels(Path(path))
    names = {n for n, _, _ in rows}
    s = LA.summarize_ms(rows)
    check("parent aten::mm dropped", "aten::mm" not in names)
    check("parent _vllm_fa2_C::fwd_kvcache_int4 dropped",
          "_vllm_fa2_C::fwd_kvcache_int4" not in names)
    check("parent vllm::unified_… dropped",
          "vllm::unified_attention_with_output" not in names)
    check("leaf splitkv kept -> decode_attn≈12464ms", abs(s.get("decode_attn", 0) - 12464.0) < 1)
    check("leaf gather kept -> gather≈6521ms", abs(s.get("gather", 0) - 6521.0) < 1)
    check("leaf copy kept -> copy≈1660ms", abs(s.get("copy", 0) - 1660.0) < 1)
    check("prefill varlen -> prefill_attn (excluded from decode)",
          abs(s.get("prefill_attn", 0) - 6906.0) < 1)
    check("ampere gemm -> gemm (excluded from decode read path)",
          abs(s.get("gemm", 0) - 14918.0) < 1)
    # decode step should NOT include prefill_attn or the big prefill gemm.
    fuseable = s.get("gather", 0) + s.get("copy", 0)
    decode_step = s.get("decode_attn", 0) + fuseable + 900.0
    check("decode step excludes prefill (≈21.5s, not ~40s)",
          20000 < decode_step < 23000)
    X = fuseable / decode_step
    check("removable share X in 0.35-0.40", 0.35 <= X <= 0.40)
finally:
    os.unlink(path)

# (3) projection invariants.
p = LA.project(fuseable_ms=8181.0, decode_step_ms=21545.0, base_ratio=0.093, rho=0.75)
check("decode speedup > 1 (a speedup, not a ratio)", p["decode_speedup"] > 1.0)
check("new_bf16_ratio = base * speedup", abs(p["new_bf16_ratio"] - 0.093 * p["decode_speedup"]) < 1e-9)
check("still net loss vs bf16 (<1x)", p["new_bf16_ratio"] < 1.0)
check("clears 15% build gate", p["clears_build_gate"])
# monotonic in rho: more realizable removal -> more speedup.
lo = LA.project(8181.0, 21545.0, 0.093, rho=0.5)["decode_speedup"]
hi = LA.project(8181.0, 21545.0, 0.093, rho=1.0)["decode_speedup"]
check("speedup monotonic in rho", hi > lo)

print(f"\nlock_aggregate CPU checks: {_n}/{_n} PASS")
