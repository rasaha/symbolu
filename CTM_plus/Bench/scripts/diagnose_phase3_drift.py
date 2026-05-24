#!/usr/bin/env python3
"""diagnose_phase3_drift.py — algorithm floor for combined K + V int4.

Mirror of diagnose_phase2_3_drift.py but applies BOTH the per-channel K
quantization and the per-token V quantization (route-B reference ops),
then runs stock FA on the dequant'd K + V vs raw K + V.

Use to establish the Phase 3 algorithm floor cosine. Compare against
verify_phase3.py's measured value:
  - If the diagnostic cosine is ~= the verify cosine: CUDA helper is
    correct, gate threshold is too tight.
  - If the diagnostic cosine is materially higher than verify: CUDA
    has a bug in the V helper or its V-wait insertion site.

Same seed and shapes as verify_phase3.py for direct comparison.
"""
import sys

import torch

if not torch.cuda.is_available():
    print("FAIL: no CUDA")
    sys.exit(1)

sys.path.insert(0, "/workspace/symbolu/CTM_plus/KVPolicy")
from kv_policy.int4_per_channel_kv import (
    quantize_per_channel_int4,
    dequantize_per_channel_int4,
    quantize_per_token_int4,
    dequantize_per_token_int4,
)

from vllm.vllm_flash_attn import flash_attn_with_kvcache

device = "cuda"
dtype = torch.bfloat16
B, S_q, H_q, H_kv, D = 1, 1, 28, 4, 128
S_kv = 16384
GROUP_SIZE_K = 32
GROUP_SIZE_V = 32

torch.manual_seed(42)
q = torch.randn(B, S_q, H_q, D, device=device, dtype=dtype)
k_cache = torch.randn(B, S_kv, H_kv, D, device=device, dtype=dtype)
v_cache = torch.randn(B, S_kv, H_kv, D, device=device, dtype=dtype)
cache_seqlens = torch.full((B,), S_kv, device=device, dtype=torch.int32)

print(f"Diagnostic: route-B algorithm intrinsic drift for K + V quant")
print(f"  shapes: B={B} S_q={S_q} H_q={H_q} H_kv={H_kv} D={D} S_kv={S_kv}")
print(f"  group_size_k={GROUP_SIZE_K} (along seq)  "
      f"group_size_v={GROUP_SIZE_V} (along head_dim)")
print()

# Quantize K via route-B's per-channel reference.
k_squeezed = k_cache.squeeze(0)  # (S_kv, H_kv, D)
k_q, k_scale, k_offset = quantize_per_channel_int4(
    k_squeezed, group_size=GROUP_SIZE_K, asymmetric=True, bits=4,
)
k_dequant = dequantize_per_channel_int4(
    k_q, k_scale, dtype=torch.bfloat16,
    group_size=GROUP_SIZE_K, offset=k_offset,
).unsqueeze(0).contiguous()

# Quantize V via route-B's per-token reference.
v_squeezed = v_cache.squeeze(0)  # (S_kv, H_kv, D)
v_q, v_scale, v_offset = quantize_per_token_int4(
    v_squeezed, group_size=GROUP_SIZE_V, asymmetric=True, bits=4,
)
v_dequant = dequantize_per_token_int4(
    v_q, v_scale, dtype=torch.bfloat16,
    group_size=GROUP_SIZE_V, offset=v_offset,
).unsqueeze(0).contiguous()

# Per-element drift.
k_drift = (k_squeezed.float() - k_dequant.squeeze(0).float()).abs()
v_drift = (v_squeezed.float() - v_dequant.squeeze(0).float()).abs()
print(f"  K per-element drift: max={k_drift.max().item():.4e}  mean={k_drift.mean().item():.4e}")
print(f"  V per-element drift: max={v_drift.max().item():.4e}  mean={v_drift.mean().item():.4e}")
print()

# Run stock FA on raw vs dequant'd K+V.
out_raw = flash_attn_with_kvcache(
    q, k_cache, v_cache, cache_seqlens=cache_seqlens, causal=False,
)
out_dequant_both = flash_attn_with_kvcache(
    q, k_dequant, v_dequant, cache_seqlens=cache_seqlens, causal=False,
)

# Also run with only-K-dequant and only-V-dequant to attribute the drift.
out_dequant_k_only = flash_attn_with_kvcache(
    q, k_dequant, v_cache, cache_seqlens=cache_seqlens, causal=False,
)
out_dequant_v_only = flash_attn_with_kvcache(
    q, k_cache, v_dequant, cache_seqlens=cache_seqlens, causal=False,
)

if isinstance(out_raw, tuple):           out_raw = out_raw[0]
if isinstance(out_dequant_both, tuple):  out_dequant_both = out_dequant_both[0]
if isinstance(out_dequant_k_only, tuple): out_dequant_k_only = out_dequant_k_only[0]
if isinstance(out_dequant_v_only, tuple): out_dequant_v_only = out_dequant_v_only[0]

def metrics(a, b, label):
    diff = (a.float() - b.float()).abs()
    cos = torch.nn.functional.cosine_similarity(
        a.float().flatten(), b.float().flatten(), dim=0,
    ).item()
    print(f"  {label:24s}: cosine={cos:.6f}  max-abs={diff.max().item():.4e}  mean-abs={diff.mean().item():.4e}")
    return cos

print("Algorithm-floor cosines (stock FA on raw vs dequant'd):")
c_k = metrics(out_raw, out_dequant_k_only,  "K dequant only")
c_v = metrics(out_raw, out_dequant_v_only,  "V dequant only")
c_kv = metrics(out_raw, out_dequant_both,   "K + V both dequant")
print()
print(f"Interpretation: Phase 3 should drift between {c_kv:.4f} (combined")
print(f"algorithm floor) and Phase 2.3's measured ~0.9968. Combined drift")
print(f"shape matches sequentially-applied error model:")
print(f"  1 - c_kv ~ (1 - c_k) + (1 - c_v) = "
      f"{(1-c_k)+(1-c_v):.6f} (expected) vs {1-c_kv:.6f} (actual)")
print()
print(f"verify_phase3.py gate is cosine >= 0.985.")
if c_kv >= 0.985:
    print(f"  Algorithm floor {c_kv:.4f} >= 0.985, gate should hold "
          f"for a correct CUDA implementation.")
else:
    print(f"  Algorithm floor {c_kv:.4f} < 0.985. Need to relax gate to "
          f"~ {max(0.97, c_kv - 0.005):.4f} (with margin).")
