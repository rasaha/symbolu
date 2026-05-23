#!/usr/bin/env python3
"""verify_phase4.py — 6c.3C Phase 4 acceptance test.

Phase 4 adds the §20.4.3 protect-K algorithm in-kernel: the top-~4% K
channels by magnitude per (B, H_kv) are kept at BF16; the rest go
through the INT4 quant/dequant cycle. Expected to close most of the
cosine gap between Phase 2.3's unprotected ~0.9968 and stock FP16 FA
(target ~0.9999).

Mask provenance for this test:
  Compute the protect mask in Python from K's magnitudes. For each
  (b, h_kv) pair, select the top-4% (= 5 of 128) channels by per-channel
  L2 magnitude across the seq dimension. Pass as int8 tensor of shape
  (B, H_kv, D) with 1 = protected, 0 = quantize.

(Phase 5 will move this mask generation into vLLM at prefill-end.)

Initial gate: cosine >= 0.9990 (conservative; will tighten after
diagnose_phase4_drift.py establishes the PyTorch algorithm floor with
protection).

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
PROTECT_FRACTION = 0.04  # top-4% channels

COSINE_THRESHOLD = 0.9990
MAX_ABS_THRESHOLD = 1e-2

torch.manual_seed(42)
q = torch.randn(B, S_q, H_q, D, device=device, dtype=dtype)
k_cache = torch.randn(B, S_kv, H_kv, D, device=device, dtype=dtype)
v_cache = torch.randn(B, S_kv, H_kv, D, device=device, dtype=dtype)
cache_seqlens = torch.full((B,), S_kv, device=device, dtype=torch.int32)

# Compute protect mask: top-PROTECT_FRACTION channels by per-channel L2
# magnitude across the seq dim, per (B, H_kv).
# K shape: (B, S_kv, H_kv, D). Channel magnitude: L2 over S_kv per (B, H_kv, D).
ch_magnitude = k_cache.float().pow(2).sum(dim=1).sqrt()  # (B, H_kv, D)
n_protect = max(1, int(round(D * PROTECT_FRACTION)))
# topk indices per (B, H_kv) over the D axis.
_, topk_idx = ch_magnitude.topk(n_protect, dim=-1)  # (B, H_kv, n_protect)
protect_mask = torch.zeros((B, H_kv, D), dtype=torch.int8, device=device)
protect_mask.scatter_(-1, topk_idx, 1)

print(f"Phase 4 acceptance test (K + V transform + protect-K)")
print(f"  shapes: B={B} S_q={S_q} H_q={H_q} H_kv={H_kv} D={D} S_kv={S_kv}")
print(f"  protect: top-{PROTECT_FRACTION*100:.0f}% = {n_protect}/{D} channels per (B, H_kv)")
print(f"  gates:   cosine >= {COSINE_THRESHOLD}, max-abs <= {MAX_ABS_THRESHOLD}")
print()
print(f"  protect_mask: shape={tuple(protect_mask.shape)} "
      f"dtype={protect_mask.dtype} nonzero/total="
      f"{protect_mask.sum().item()}/{protect_mask.numel()}")
print()

out_stock = flash_attn_with_kvcache(
    q, k_cache, v_cache, cache_seqlens=cache_seqlens, causal=False,
)
out_int4 = flash_attn_with_int4_kvcache(
    q, k_cache, v_cache,
    cache_seqlens=cache_seqlens, causal=False,
    protect_mask=protect_mask,
    n_protect=n_protect,
)

if isinstance(out_stock, tuple): out_stock = out_stock[0]
if isinstance(out_int4, tuple):  out_int4  = out_int4[0]

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
print(f"  reference: Phase 2.3 (K only, no protect)    cosine 0.99684, max-abs 3.9e-3")
print(f"             Phase 3   (K + V, no protect)      see verify_phase3.py")
print(f"             Phase 4   (K + V + protect-K)     -> here")
print()

cos_pass = cos >= COSINE_THRESHOLD
max_pass = max_abs <= MAX_ABS_THRESHOLD

if cos_pass and max_pass:
    print(f"PASS: cosine {cos:.6f} >= {COSINE_THRESHOLD} AND "
          f"max-abs {max_abs:.4e} <= {MAX_ABS_THRESHOLD}")
    print()
    print("Phase 4: GREEN. §20.4.3 protect-K algorithm faithfully reproduced")
    print("in-kernel. Safe to proceed to Phase 5 (vLLM integration — move the")
    print("mask provenance from this test script into vLLM's prefill-end hook)")
    print("or Phase 2.4 (REAL INT4 K HBM read, the memory-savings step).")
    sys.exit(0)

print(f"FAIL: cosine_ok={cos_pass} max_abs_ok={max_pass}")
print()
print("Run diagnose_phase4_drift.py to determine algorithm floor vs CUDA bug.")
sys.exit(1)
