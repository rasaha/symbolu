#!/usr/bin/env python3
"""verify_phase1.py — 6c.3C Phase 1 acceptance test.

Phase 1.7 acceptance criterion from KERNEL_6C3C_RUNBOOK.md:

    flash_attn_with_int4_kvcache(q, k_bf16, v_bf16, cache_seqlens=csl)
    == flash_attn_with_kvcache(q, k_bf16, v_bf16, cache_seqlens=csl)
    BIT-FOR-BIT on Qwen2.5-7B shapes.

If this passes, Phase 1 is GREEN — additive scaffolding works and
the dev install is in a known-good state to start Phase 2 (clone
the kernel + new dispatch arm + actually modify the K read path).

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

# Import both functions. flash_attn_with_int4_kvcache should be
# re-exported from vllm.vllm_flash_attn after Phase 1 install.
try:
    from vllm.vllm_flash_attn import flash_attn_with_kvcache
except ImportError as e:
    print(f"FAIL: can't import flash_attn_with_kvcache: {e}")
    sys.exit(1)

try:
    from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache
except ImportError:
    # If not re-exported, try the direct path.
    try:
        from vllm.vllm_flash_attn.flash_attn_interface import (
            flash_attn_with_int4_kvcache,
        )
    except ImportError as e:
        print(f"FAIL: can't import flash_attn_with_int4_kvcache: {e}")
        print()
        print("Hint: check vllm/vllm_flash_attn/__init__.py for the re-export,")
        print("or that flash_attn_interface.py has the new function defined.")
        sys.exit(1)

# Qwen2.5-7B shapes. B=1, H_q=28, H_kv=4, D=128, S=16k.
# Layout: (B, S_q, H_q, D) for q, (B, S_kv, H_kv, D) for kcache/vcache.
device = "cuda"
dtype = torch.bfloat16
B, S_q, H_q, H_kv, D = 1, 1, 28, 4, 128
S_kv = 16384

torch.manual_seed(42)
q = torch.randn(B, S_q, H_q, D, device=device, dtype=dtype)
k_cache = torch.randn(B, S_kv, H_kv, D, device=device, dtype=dtype)
v_cache = torch.randn(B, S_kv, H_kv, D, device=device, dtype=dtype)
cache_seqlens = torch.full((B,), S_kv, device=device, dtype=torch.int32)

print(f"Phase 1 acceptance test")
print(f"  shapes: B={B} S_q={S_q} H_q={H_q} H_kv={H_kv} D={D} S_kv={S_kv}")
print(f"  dtype:  {dtype}")
print()

# Both calls take the same args; Phase 1 wrapper delegates.
out_stock = flash_attn_with_kvcache(
    q, k_cache, v_cache, cache_seqlens=cache_seqlens, causal=False,
)
out_int4 = flash_attn_with_int4_kvcache(
    q, k_cache, v_cache, cache_seqlens=cache_seqlens, causal=False,
)

# Tuple return (e.g. with softmax_lse)? Take first element.
if isinstance(out_stock, tuple):
    out_stock = out_stock[0]
if isinstance(out_int4, tuple):
    out_int4 = out_int4[0]

if torch.equal(out_stock, out_int4):
    print("PASS: flash_attn_with_int4_kvcache == flash_attn_with_kvcache "
          "(bit-equal)")
    print()
    print("Phase 1: GREEN. Safe to proceed to Phase 2.")
    sys.exit(0)

# Not bit-equal — report the diff.
diff = (out_stock.float() - out_int4.float()).abs()
print(f"FAIL: outputs differ")
print(f"  max-abs diff:   {diff.max().item():.6e}")
print(f"  mean-abs diff:  {diff.mean().item():.6e}")
cos = torch.nn.functional.cosine_similarity(
    out_stock.float().flatten(),
    out_int4.float().flatten(),
    dim=0,
).item()
print(f"  cosine:         {cos:.6f}")
print()
print("Phase 1 wrapper should be a no-op delegate; any drift means")
print("the patch is broken. Check apply_phase1_patches.py output.")
sys.exit(1)
