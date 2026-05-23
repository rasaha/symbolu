#!/usr/bin/env python3
"""diagnose_phase4_drift.py — protect-K algorithm floor.

Establishes the route-B algorithm intrinsic floor for:
  stock FA on raw K vs stock FA on (INT4-then-restored-top-4% K) + INT4 V.

Use to calibrate verify_phase4.py's cosine gate. Same seed and shapes as
verify_phase4.py for direct comparison.

Decomposes the drift into:
  cos_unprotected_KV  — K (no protect) + V both quantized (Phase 3 floor)
  cos_protected_K_V   — K (protect top-4%) + V quantized (Phase 4 floor)
The gap cos_protected_K_V - cos_unprotected_KV is the §20.4.3 quality
recovery from protect-K.
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
PROTECT_FRACTION = 0.04

torch.manual_seed(42)
q = torch.randn(B, S_q, H_q, D, device=device, dtype=dtype)
k_cache = torch.randn(B, S_kv, H_kv, D, device=device, dtype=dtype)
v_cache = torch.randn(B, S_kv, H_kv, D, device=device, dtype=dtype)
cache_seqlens = torch.full((B,), S_kv, device=device, dtype=torch.int32)

# Compute protect mask: top-4% by channel L2 per (B, H_kv).
ch_magnitude = k_cache.float().pow(2).sum(dim=1).sqrt()
n_protect = max(1, int(round(D * PROTECT_FRACTION)))
_, topk_idx = ch_magnitude.topk(n_protect, dim=-1)  # (B, H_kv, n_protect)
protect_mask = torch.zeros((B, H_kv, D), dtype=torch.bool, device=device)
protect_mask.scatter_(-1, topk_idx, True)

print(f"Diagnostic: protect-K algorithm floor")
print(f"  protect: top-{PROTECT_FRACTION*100:.0f}% = {n_protect}/{D} per (B, H_kv)")
print()

# Quantize K per-channel, group=32.
k_squeezed = k_cache.squeeze(0)
k_q, k_scale, k_offset = quantize_per_channel_int4(
    k_squeezed, group_size=GROUP_SIZE_K, asymmetric=True, bits=4,
)
k_dq_unprot = dequantize_per_channel_int4(
    k_q, k_scale, dtype=torch.bfloat16,
    group_size=GROUP_SIZE_K, offset=k_offset,
)  # (S_kv, H_kv, D)

# Apply protect: restore original BF16 values for protected channels.
# protect_mask shape (B, H_kv, D) -> for our squeezed K (S_kv, H_kv, D),
# broadcast across S_kv.
mask_bcast = protect_mask.squeeze(0).unsqueeze(0)  # (1, H_kv, D)
k_dq_prot = torch.where(mask_bcast, k_squeezed, k_dq_unprot)

# Quantize V per-token, group=32.
v_squeezed = v_cache.squeeze(0)
v_q, v_scale, v_offset = quantize_per_token_int4(
    v_squeezed, group_size=GROUP_SIZE_V, asymmetric=True, bits=4,
)
v_dq = dequantize_per_token_int4(
    v_q, v_scale, dtype=torch.bfloat16,
    group_size=GROUP_SIZE_V, offset=v_offset,
)

k_dq_unprot_b = k_dq_unprot.unsqueeze(0).contiguous()
k_dq_prot_b   = k_dq_prot.unsqueeze(0).contiguous()
v_dq_b        = v_dq.unsqueeze(0).contiguous()

out_raw = flash_attn_with_kvcache(
    q, k_cache, v_cache, cache_seqlens=cache_seqlens, causal=False,
)
out_unprot = flash_attn_with_kvcache(
    q, k_dq_unprot_b, v_dq_b, cache_seqlens=cache_seqlens, causal=False,
)
out_prot = flash_attn_with_kvcache(
    q, k_dq_prot_b, v_dq_b, cache_seqlens=cache_seqlens, causal=False,
)

if isinstance(out_raw, tuple):    out_raw    = out_raw[0]
if isinstance(out_unprot, tuple): out_unprot = out_unprot[0]
if isinstance(out_prot, tuple):   out_prot   = out_prot[0]

def metrics(a, b, label):
    diff = (a.float() - b.float()).abs()
    cos = torch.nn.functional.cosine_similarity(
        a.float().flatten(), b.float().flatten(), dim=0,
    ).item()
    print(f"  {label:30s}: cosine={cos:.6f}  max-abs={diff.max().item():.4e}  mean-abs={diff.mean().item():.4e}")
    return cos

print("Algorithm-floor cosines (stock FA on raw vs dequant'd K/V):")
c_unprot = metrics(out_raw, out_unprot, "K dequant + V dequant")
c_prot   = metrics(out_raw, out_prot,   "K dequant w/ protect + V dequant")
recovery = c_prot - c_unprot
print()
print(f"Protect-K recovery: cosine +{recovery:+.6f}  "
      f"({c_unprot:.4f} -> {c_prot:.4f})")
print()
print(f"verify_phase4.py gate: cosine >= 0.9990")
if c_prot >= 0.9990:
    print(f"  Algorithm floor {c_prot:.4f} >= 0.9990  "
          f"=> gate should hold for a correct CUDA implementation.")
else:
    print(f"  Algorithm floor {c_prot:.4f} < 0.9990  "
          f"=> relax gate to ~ {max(0.99, c_prot - 0.001):.4f}")
