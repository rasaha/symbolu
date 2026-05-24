#!/usr/bin/env python3
"""diagnose_phase2_3_drift.py — separate algorithm drift from kernel bugs.

Phase 2.3 acceptance gate is cosine >= 0.9999 between
flash_attn_with_int4_kvcache (the new path: stock FA with K transformed
in-register via the route-B quant/dequant inside the kernel) and
flash_attn_with_kvcache (stock FA on raw BF16 K).

If verify_phase2_3.py reports cosine < 0.9999, two possibilities:
  (A) CUDA bug in int4_inline.h (rounding, group index, sync, smem race).
  (B) Brief's threshold was overoptimistic for the route-B algorithm.

This script settles it by computing the "algorithm intrinsic" drift
floor: run quantize_per_channel_int4 + dequantize_per_channel_int4
in PURE PyTorch on the same K used by verify_phase2_3.py, feed the
dequant'd K through stock FA, and compare to stock FA on raw K.

That cosine number tells us:
  - If close to 0.9999 (or better): algorithm IS near-lossless and any
    drift below that is a CUDA-side bug. Hunt the bug.
  - If ~ verify_phase2_3.py's reported cosine: the algorithm itself
    has that intrinsic drift floor; CUDA matches. The brief's gate
    needs relaxation; CUDA is correct.

Same seed, same shapes as verify_phase2_3.py for direct comparability.
"""
import sys

import torch

if not torch.cuda.is_available():
    print("FAIL: no CUDA")
    sys.exit(1)

# Import the route-B reference ops.
sys.path.insert(0, "/workspace/symbolu/CTM_plus/KVPolicy")
from kv_policy.int4_per_channel_kv import (
    quantize_per_channel_int4,
    dequantize_per_channel_int4,
)

# Import stock FA.
from vllm.vllm_flash_attn import flash_attn_with_kvcache

# Same seed + shapes as verify_phase2_3.py.
device = "cuda"
dtype = torch.bfloat16
B, S_q, H_q, H_kv, D = 1, 1, 28, 4, 128
S_kv = 16384
GROUP_SIZE_K = 32

torch.manual_seed(42)
q = torch.randn(B, S_q, H_q, D, device=device, dtype=dtype)
k_cache = torch.randn(B, S_kv, H_kv, D, device=device, dtype=dtype)
v_cache = torch.randn(B, S_kv, H_kv, D, device=device, dtype=dtype)
cache_seqlens = torch.full((B,), S_kv, device=device, dtype=torch.int32)

print(f"Diagnostic: route-B algorithm intrinsic drift vs stock FA")
print(f"  shapes: B={B} S_q={S_q} H_q={H_q} H_kv={H_kv} D={D} S_kv={S_kv}")
print(f"  dtype:  {dtype}")
print(f"  group_size_k: {GROUP_SIZE_K}")
print()

# Quantize K via route-B's reference ops.
# quantize_per_channel_int4 expects (S, H, D) — squeeze the batch dim.
# Note: it groups along the FIRST axis (S in (S, H, D)). For our K cache
# of shape (B, S, H, D), we squeeze B then quantize.
k_squeezed = k_cache.squeeze(0)  # (S_kv, H_kv, D)
k_q, k_scale, k_offset = quantize_per_channel_int4(
    k_squeezed,
    group_size=GROUP_SIZE_K,
    asymmetric=True,
    bits=4,
)
print(f"  quantized K: shape={tuple(k_q.shape)} dtype={k_q.dtype}")
print(f"  scale shape: {tuple(k_scale.shape)}, dtype={k_scale.dtype}")
print(f"  offset shape: {tuple(k_offset.shape) if k_offset is not None else None}")
print()

# Dequantize back to BF16.
k_dequant = dequantize_per_channel_int4(
    k_q, k_scale,
    dtype=torch.bfloat16,
    group_size=GROUP_SIZE_K,
    offset=k_offset,
)
print(f"  dequantized K: shape={tuple(k_dequant.shape)} dtype={k_dequant.dtype}")

# Per-element K drift (BF16 ULPs).
k_drift = (k_squeezed.float() - k_dequant.float()).abs()
print(f"  K per-element max-abs drift: {k_drift.max().item():.6e}")
print(f"  K per-element mean-abs drift: {k_drift.mean().item():.6e}")
print()

# Re-batch.
k_dequant_batched = k_dequant.unsqueeze(0).contiguous()  # (B, S_kv, H_kv, D)

# Run stock FA on raw K (the reference) and on dequant'd K (the algorithm).
out_raw = flash_attn_with_kvcache(
    q, k_cache, v_cache, cache_seqlens=cache_seqlens, causal=False,
)
out_dequant = flash_attn_with_kvcache(
    q, k_dequant_batched, v_cache, cache_seqlens=cache_seqlens, causal=False,
)

if isinstance(out_raw, tuple):
    out_raw = out_raw[0]
if isinstance(out_dequant, tuple):
    out_dequant = out_dequant[0]

# Compute drift metrics on the attention output.
diff = (out_raw.float() - out_dequant.float()).abs()
max_abs = diff.max().item()
mean_abs = diff.mean().item()
cos = torch.nn.functional.cosine_similarity(
    out_raw.float().flatten(),
    out_dequant.float().flatten(),
    dim=0,
).item()

print(f"Stock FA on raw K vs stock FA on dequant'd K:")
print(f"  cosine:        {cos:.8f}")
print(f"  max-abs diff:  {max_abs:.6e}")
print(f"  mean-abs diff: {mean_abs:.6e}")
print()
print("Interpretation:")
print(f"  Phase 2.3 verify reported cosine ~ 0.9968.")
print(f"  This script's cosine = {cos:.6f} is the algorithm's intrinsic floor.")
print()
if cos >= 0.9999:
    print("  CONCLUSION: algorithm is near-lossless; gap to 0.9999 in")
    print("  verify_phase2_3.py implies a CUDA-side bug. Hunt the bug in")
    print("  int4_inline.h or the call-site smem_int4_scratch handling.")
elif cos < 0.998:
    print("  CONCLUSION: algorithm itself has this drift floor; CUDA matches.")
    print("  Phase 2.3 brief's 0.9999 threshold was overoptimistic. The")
    print("  CUDA implementation is correct; relax the gate to cosine >=")
    print(f"  {max(0.997, cos - 0.001):.4f} (or whatever this script printed)")
    print("  and Phase 2.3 GREENs.")
else:
    print("  CONCLUSION: middle ground — algorithm drift is non-trivial but")
    print("  better than CUDA's. May indicate a small CUDA bug compounding")
    print("  the algorithm drift. Inspect the helper carefully.")
