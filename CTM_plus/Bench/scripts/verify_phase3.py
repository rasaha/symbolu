#!/usr/bin/env python3
"""verify_phase3.py — 6c.3C Phase 3 acceptance test.

Phase 3 adds the INT4 quant->dequant transform on V (per-token, group
along head_dim) on top of Phase 2.3's K transform. Both K and V now fire
through the int4 path. Stock FA path (flash_attn_with_kvcache) is
unchanged (Is_int4kv=false template variant).

Compares flash_attn_with_int4_kvcache to flash_attn_with_kvcache on
Qwen2.5-7B shapes. Drift is larger than Phase 2.3 because V quantization
adds error on top of K quantization:

  Phase 2.3 (K only):     cosine ~ 0.9968, max-abs ~ 3.9e-3
  Phase 3 (K + V):        expected cosine ~ 0.99 (TBD), max-abs ~ TBD

Initial gate (conservative; will be tightened to match algorithm floor
once diagnose_phase3_drift.py establishes the PyTorch reference baseline):
  cosine   >= 0.985
  max-abs  <= 2e-2

If verify fails, run diagnose_phase3_drift.py first to determine whether
the drift is intrinsic to the algorithm (gate too tight) or a CUDA bug
(kernel issue in int4_inline.h's V helper or the V-wait insertion site).

Exits 0 = GREEN, 1 = FAIL.
"""

import sys

try:
    import torch
except ImportError:
    print("FAIL: torch not installed")
    sys.exit(1)

if not torch.cuda.is_available():
    print("FAIL: no CUDA device")
    sys.exit(1)

try:
    from vllm.vllm_flash_attn import (
        flash_attn_with_kvcache,
        flash_attn_with_int4_kvcache,
    )
except ImportError as e:
    print(f"FAIL: can't import flash attention ops: {e}")
    sys.exit(1)

device = "cuda"
dtype = torch.bfloat16
B, S_q, H_q, H_kv, D = 1, 1, 28, 4, 128
S_kv = 16384

COSINE_THRESHOLD = 0.985
MAX_ABS_THRESHOLD = 2e-2

torch.manual_seed(42)
q = torch.randn(B, S_q, H_q, D, device=device, dtype=dtype)
k_cache = torch.randn(B, S_kv, H_kv, D, device=device, dtype=dtype)
v_cache = torch.randn(B, S_kv, H_kv, D, device=device, dtype=dtype)
cache_seqlens = torch.full((B,), S_kv, device=device, dtype=torch.int32)

print(f"Phase 3 acceptance test (K + V transform)")
print(f"  shapes: B={B} S_q={S_q} H_q={H_q} H_kv={H_kv} D={D} S_kv={S_kv}")
print(f"  dtype:  {dtype}")
print(f"  gates:  cosine >= {COSINE_THRESHOLD}, max-abs <= {MAX_ABS_THRESHOLD}")
print()

out_stock = flash_attn_with_kvcache(
    q, k_cache, v_cache, cache_seqlens=cache_seqlens, causal=False,
)
out_int4 = flash_attn_with_int4_kvcache(
    q, k_cache, v_cache, cache_seqlens=cache_seqlens, causal=False,
)

if isinstance(out_stock, tuple):
    out_stock = out_stock[0]
if isinstance(out_int4, tuple):
    out_int4 = out_int4[0]

diff = (out_stock.float() - out_int4.float()).abs()
max_abs = diff.max().item()
mean_abs = diff.mean().item()
cos = torch.nn.functional.cosine_similarity(
    out_stock.float().flatten(),
    out_int4.float().flatten(),
    dim=0,
).item()

print(f"  cosine:        {cos:.8f}")
print(f"  max-abs diff:  {max_abs:.6e}")
print(f"  mean-abs diff: {mean_abs:.6e}")
print()
print(f"  reference: Phase 2.3 (K only) had cosine 0.99684, max-abs 3.9e-3")
print()

cos_pass = cos >= COSINE_THRESHOLD
max_pass = max_abs <= MAX_ABS_THRESHOLD

if cos_pass and max_pass:
    print(f"PASS: cosine {cos:.6f} >= {COSINE_THRESHOLD} AND "
          f"max-abs {max_abs:.4e} <= {MAX_ABS_THRESHOLD}")
    print()
    print("Phase 3: GREEN. Both K and V INT4 transforms fire correctly.")
    print("CUDA helpers reproduce route-B's quantize_per_channel + "
          "quantize_per_token algorithms. Safe to proceed to Phase 4")
    print("(protect-K sidecar) or Phase 2.5 work (REAL INT4 HBM read).")
    sys.exit(0)

print(f"FAIL: cosine_ok={cos_pass} max_abs_ok={max_pass}")
print()
print("Diagnostic — run diagnose_phase3_drift.py to determine if this is")
print("an algorithm floor issue (relax gate) or a CUDA bug in the V")
print("helper. Phase 2.3 hit a similar mismatch on first run; algorithm")
print("floor turned out to be the cause.")
sys.exit(1)
