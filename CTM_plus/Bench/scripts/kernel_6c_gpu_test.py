#!/usr/bin/env python3
"""GPU correctness test for the 6c.1 fused protected-K decode kernel.

Validates ``fused_protected_k_decode_attention`` against the numerical
oracle ``fused_int4_attention_reference`` (with k_fp16 / k_protect_mask)
— KERNEL_6C_BLUEPRINT.md §8 / §10. Layer-1 + a few layer-2 edge cases.

Run on the GPU pod (venv-hf or any env with torch + triton):

    cd /workspace/symbolu/CTM_plus/Bench
    python scripts/kernel_6c_gpu_test.py

Exits 0 if every case passes (cosine >= 0.999), 1 otherwise. Skips
cleanly (exit 0) when there is no CUDA or no Triton.

This is iteration round 1 — if cases fail, paste the per-case table
back and the kernel gets fixed.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make kv_policy importable (KVPolicy is a sibling of Bench under CTM_plus).
_KV = Path(__file__).resolve().parents[2] / "KVPolicy"
if str(_KV) not in sys.path:
    sys.path.insert(0, str(_KV))


def _build_inputs(B, H_q, H_kv, S_kv, D, gk, gv, asymmetric, protect_fraction, seed):
    """Build one test case on CPU. Returns a dict of tensors plus meta."""
    import torch
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, quantize_per_token_int4, pack_int4,
    )

    g = torch.Generator().manual_seed(seed)
    k_fp16 = torch.randn(B, H_kv, S_kv, D, generator=g, dtype=torch.float16)
    v_fp16 = torch.randn(B, H_kv, S_kv, D, generator=g, dtype=torch.float16)
    q = torch.randn(B, H_q, D, generator=g, dtype=torch.float16)
    # Inject magnitude outliers so the protected-K path is exercised.
    for h, d in [(0, 0), (min(2, H_kv - 1), 64), (min(1, H_kv - 1), 100)]:
        k_fp16[:, h, :, d] *= 40.0

    # Static protected-channel mask (H_kv, D), int8 0/1.
    if protect_fraction <= 0.0:
        mask = torch.zeros(H_kv, D, dtype=torch.int8)
    elif protect_fraction >= 1.0:
        mask = torch.ones(H_kv, D, dtype=torch.int8)
    else:
        mag = k_fp16.abs().amax(dim=2).amax(dim=0)          # (H_kv, D)
        n = max(1, round(protect_fraction * H_kv * D))
        idx = torch.topk(mag.reshape(-1), n).indices
        flat = torch.zeros(H_kv * D, dtype=torch.int8)
        flat[idx] = 1
        mask = flat.reshape(H_kv, D)

    # Quantize K/V per batch via the route-B ops.
    kp_l, ks_l, ko_l, vp_l, vs_l, vo_l = [], [], [], [], [], []
    for bi in range(B):
        kq, ks, ko = quantize_per_channel_int4(
            k_fp16[bi].transpose(0, 1).contiguous(),         # (S, H_kv, D)
            group_size=gk, asymmetric=asymmetric,
        )
        vq, vs, vo = quantize_per_token_int4(
            v_fp16[bi].transpose(0, 1).contiguous(),
            group_size=gv, asymmetric=asymmetric,
        )
        kp_l.append(pack_int4(kq).transpose(0, 1).contiguous())  # (H_kv, S, D//2)
        vp_l.append(pack_int4(vq).transpose(0, 1).contiguous())
        ks_l.append(ks)                                          # (n_grp_k, H_kv, D)
        vs_l.append(vs)                                          # (S, H_kv, n_grp_v)
        if asymmetric:
            ko_l.append(ko)
            vo_l.append(vo)

    k_packed = torch.stack(kp_l, 0).contiguous()                 # (B,H_kv,S,D//2)
    v_packed = torch.stack(vp_l, 0).contiguous()
    k_scale = torch.stack(ks_l, 0).to(torch.float16).contiguous()  # (B,n_grp_k,H_kv,D)
    v_scale = torch.stack(vs_l, 0).to(torch.float16).contiguous()  # (B,S,H_kv,n_grp_v)
    k_offset = (torch.stack(ko_l, 0).to(torch.float16).contiguous()
                if asymmetric else None)
    v_offset = (torch.stack(vo_l, 0).to(torch.float16).contiguous()
                if asymmetric else None)

    return dict(
        q=q, k_packed=k_packed, k_scale=k_scale, k_offset=k_offset,
        k_fp16=k_fp16.contiguous(), mask=mask, v_packed=v_packed,
        v_scale=v_scale, v_offset=v_offset,
        B=B, H_q=H_q, H_kv=H_kv, S_kv=S_kv, D=D, gk=gk, gv=gv,
        asymmetric=asymmetric,
    )


def _run_case(c):
    """Run reference + kernel for one case; return (cosine, max_abs)."""
    import torch
    from kv_policy.int4_fused_attention_sketch import (
        fused_int4_attention_reference, FusedAttentionSpec,
    )
    from kv_policy.int4_fused_attention_kernel import (
        fused_protected_k_decode_attention,
    )

    dev = "cuda"
    cu = {k: (v.to(dev) if hasattr(v, "to") else v) for k, v in c.items()}

    spec = FusedAttentionSpec(
        B=c["B"], H_q=c["H_q"], H_kv=c["H_kv"], S_q=1, S_kv=c["S_kv"],
        D=c["D"], block_size=16, group_size_k=c["gk"], group_size_v=c["gv"],
        asymmetric=c["asymmetric"],
    )
    out_ref = fused_int4_attention_reference(
        q=cu["q"].unsqueeze(2),                       # (B,H_q,1,D)
        k_packed=cu["k_packed"], k_scale=cu["k_scale"], k_offset=cu["k_offset"],
        v_packed=cu["v_packed"], v_scale=cu["v_scale"], v_offset=cu["v_offset"],
        spec=spec, k_fp16=cu["k_fp16"], k_protect_mask=cu["mask"],
    ).squeeze(2)                                       # (B,H_q,D)

    out_k = fused_protected_k_decode_attention(
        q=cu["q"], k_packed=cu["k_packed"], k_scale=cu["k_scale"],
        k_offset=cu["k_offset"], k_fp16=cu["k_fp16"], protect_mask=cu["mask"],
        v_packed=cu["v_packed"], v_scale=cu["v_scale"], v_offset=cu["v_offset"],
        group_size_k=c["gk"], group_size_v=c["gv"], asymmetric=c["asymmetric"],
    )

    a = out_ref.flatten().float()
    b = out_k.flatten().float()
    cos = float(torch.nn.functional.cosine_similarity(a, b, dim=0))
    max_abs = float((out_ref - out_k).abs().max())
    return cos, max_abs


CASES = [
    # name,                B, H_q, H_kv, S_kv, D,  gk, gv, asym,  protect
    ("qwen_asym_s64",       1, 28,  4,    64,   128, 32, 32, True,  0.04),
    ("qwen_sym_s64",        1, 28,  4,    64,   128, 32, 32, False, 0.04),
    ("qwen_asym_s16",       1, 28,  4,    16,   128, 32, 32, True,  0.04),
    ("qwen_asym_s200",      1, 28,  4,    200,  128, 32, 32, True,  0.04),
    ("qwen_asym_b2_s64",    2, 28,  4,    64,   128, 32, 32, True,  0.04),
    ("mistral_asym_s64",    1, 32,  8,    64,   128, 32, 32, True,  0.04),
    ("qwen_protect0_s64",   1, 28,  4,    64,   128, 32, 32, True,  0.00),
    ("qwen_protectall_s64", 1, 28,  4,    64,   128, 32, 32, True,  1.00),
]


def main() -> int:
    try:
        import torch
    except ImportError:
        print("torch not installed — skipping (test needs a GPU env).")
        return 0
    if not torch.cuda.is_available():
        print("no CUDA device — skipping (this test requires a GPU).")
        return 0
    try:
        import triton  # noqa: F401
    except ImportError:
        print("triton not installed — skipping.")
        return 0

    print("=" * 72)
    print("Kernel 6c.1 — fused protected-K decode attention vs reference")
    print("=" * 72)
    print(f"{'case':<22} {'cosine':>10} {'max_abs':>12}  result")
    print("-" * 72)

    all_pass = True
    for i, (name, B, H_q, H_kv, S_kv, D, gk, gv, asym, prot) in enumerate(CASES):
        try:
            c = _build_inputs(B, H_q, H_kv, S_kv, D, gk, gv, asym, prot, seed=100 + i)
            cos, max_abs = _run_case(c)
            ok = cos >= 0.999
            all_pass &= ok
            print(f"{name:<22} {cos:>10.6f} {max_abs:>12.6f}  "
                  f"{'PASS' if ok else 'FAIL'}")
        except Exception as exc:  # noqa: BLE001 — report, don't abort the matrix
            all_pass = False
            print(f"{name:<22} {'—':>10} {'—':>12}  ERROR: "
                  f"{type(exc).__name__}: {exc}")

    print("-" * 72)
    print("ALL PASS" if all_pass else "SOME CASES FAILED — paste this table back")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
