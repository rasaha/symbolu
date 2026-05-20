#!/usr/bin/env python3
"""Throughput micro-benchmark for the 6c.1 fused protected-K decode kernel.

Measures single-decode-step latency on a Qwen2.5-7B-shape attention layer
across a range of cached sequence lengths, for three paths:

  1. FP16 SDPA       — torch.nn.functional.scaled_dot_product_attention
                       on FP16 K/V. The production reference baseline
                       (dispatches to FlashAttention on supported GPUs).

  2. Naive route-A   — unpack INT4 → dequant → protected-K overlay →
                       SDPA. The "no kernel" fallback path the route-A
                       monkey-patch ships with — what the fused kernel
                       is supposed to beat.

  3. Kernel 6c.1     — fused_protected_k_decode_attention. The v1
                       (correctness-first, non-paged, single-token).

Layer-4 of the blueprint test pyramid. **Not** a full vLLM throughput
measurement (that needs 6c.3 route-A integration); this is the standalone
attention-layer latency — informs whether 6c.2 optimisation is critical.

Run:
    cd /workspace/symbolu/CTM_plus/Bench
    python scripts/kernel_6c_throughput.py

Skips cleanly (exit 0) when there is no CUDA or no Triton.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make kv_policy importable (KVPolicy is a sibling of Bench under CTM_plus).
_KV = Path(__file__).resolve().parents[2] / "KVPolicy"
if str(_KV) not in sys.path:
    sys.path.insert(0, str(_KV))


def _time_cuda(fn, n_warmup: int = 10, n_iter: int = 30) -> float:
    """Median latency in microseconds, GPU-event-timed."""
    import torch
    for _ in range(n_warmup):
        fn()
    torch.cuda.synchronize()
    times_ms = []
    for _ in range(n_iter):
        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)
        start.record()
        fn()
        end.record()
        torch.cuda.synchronize()
        times_ms.append(start.elapsed_time(end))
    times_ms.sort()
    median_ms = times_ms[len(times_ms) // 2]
    return median_ms * 1000.0  # → μs


def _build_inputs(B, H_q, H_kv, S_kv, D, gk, gv, asymmetric, protect_fraction, seed):
    """Build a single Qwen-shape throughput case on GPU."""
    import torch
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, quantize_per_token_int4, pack_int4,
    )
    g = torch.Generator().manual_seed(seed)
    k_fp16 = torch.randn(B, H_kv, S_kv, D, generator=g, dtype=torch.float16)
    v_fp16 = torch.randn(B, H_kv, S_kv, D, generator=g, dtype=torch.float16)
    q = torch.randn(B, H_q, D, generator=g, dtype=torch.float16)
    k_fp16[:, 0, :, 0] *= 40.0   # outlier (doesn't affect timing, exercises overlay)

    # Static protected-K mask.
    if protect_fraction <= 0.0:
        mask = torch.zeros(H_kv, D, dtype=torch.int8)
    elif protect_fraction >= 1.0:
        mask = torch.ones(H_kv, D, dtype=torch.int8)
    else:
        mag = k_fp16.abs().amax(dim=2).amax(dim=0)
        n = max(1, round(protect_fraction * H_kv * D))
        idx = torch.topk(mag.reshape(-1), n).indices
        flat = torch.zeros(H_kv * D, dtype=torch.int8); flat[idx] = 1
        mask = flat.reshape(H_kv, D)

    kp_l, ks_l, ko_l, vp_l, vs_l, vo_l = [], [], [], [], [], []
    for bi in range(B):
        kq, ks, ko = quantize_per_channel_int4(
            k_fp16[bi].transpose(0, 1).contiguous(), group_size=gk, asymmetric=asymmetric,
        )
        vq, vs, vo = quantize_per_token_int4(
            v_fp16[bi].transpose(0, 1).contiguous(), group_size=gv, asymmetric=asymmetric,
        )
        kp_l.append(pack_int4(kq).transpose(0, 1).contiguous())
        vp_l.append(pack_int4(vq).transpose(0, 1).contiguous())
        ks_l.append(ks)
        vs_l.append(vs)
        if asymmetric:
            ko_l.append(ko); vo_l.append(vo)

    out = dict(
        q=q.cuda(),
        k_packed=torch.stack(kp_l, 0).cuda(),
        v_packed=torch.stack(vp_l, 0).cuda(),
        k_scale=torch.stack(ks_l, 0).to(torch.float16).cuda(),
        v_scale=torch.stack(vs_l, 0).to(torch.float16).cuda(),
        k_offset=(torch.stack(ko_l, 0).to(torch.float16).cuda() if asymmetric else None),
        v_offset=(torch.stack(vo_l, 0).to(torch.float16).cuda() if asymmetric else None),
        k_fp16=k_fp16.cuda().contiguous(),
        v_fp16=v_fp16.cuda().contiguous(),
        mask=mask.cuda(),
        B=B, H_q=H_q, H_kv=H_kv, S_kv=S_kv, D=D, gk=gk, gv=gv,
        asymmetric=asymmetric,
    )
    return out


def _fp16_sdpa(q, k, v, H_q, H_kv):
    """FP16 SDPA with manual GQA broadcast — the production reference."""
    import torch
    import torch.nn.functional as F
    B, _, S_kv, D = k.shape
    G = H_q // H_kv
    k_b = k.unsqueeze(2).expand(B, H_kv, G, S_kv, D).reshape(B, H_q, S_kv, D)
    v_b = v.unsqueeze(2).expand(B, H_kv, G, S_kv, D).reshape(B, H_q, S_kv, D)
    out = F.scaled_dot_product_attention(
        q.unsqueeze(2), k_b, v_b, is_causal=False,
    )
    return out.squeeze(2)


def _naive_route_a_path(c):
    """Unpack INT4 → dequant → protected-K overlay → SDPA.

    Vectorised (no Python per-batch loop). Allocates fresh K/V FP16
    intermediates on every call — exactly what the fused kernel avoids.
    """
    import torch
    from kv_policy.int4_per_channel_kv import unpack_int4

    B, H_kv, S, D = c["B"], c["H_kv"], c["S_kv"], c["D"]
    gk, gv = c["gk"], c["gv"]
    dev = c["q"].device

    # K dequant.
    k_int4 = unpack_int4(c["k_packed"], target_n=D)           # (B,H_kv,S,D) int8
    grp_s = (torch.arange(S, device=dev) // gk).long()        # (S,)
    k_scale_s = c["k_scale"][:, grp_s, :, :].permute(0, 2, 1, 3).contiguous()
    k_dq = k_int4.float() * k_scale_s.float()
    if c["asymmetric"]:
        k_off_s = c["k_offset"][:, grp_s, :, :].permute(0, 2, 1, 3).contiguous()
        k_dq = k_dq + k_off_s.float()
    k_dq = k_dq.to(torch.float16)

    # V dequant.
    v_int4 = unpack_int4(c["v_packed"], target_n=D)
    grp_d = (torch.arange(D, device=dev) // gv).long()        # (D,)
    v_scale_d = c["v_scale"][..., grp_d].permute(0, 2, 1, 3).contiguous()
    v_dq = v_int4.float() * v_scale_d.float()
    if c["asymmetric"]:
        v_off_d = c["v_offset"][..., grp_d].permute(0, 2, 1, 3).contiguous()
        v_dq = v_dq + v_off_d.float()
    v_dq = v_dq.to(torch.float16)

    # Protected-K overlay.
    mask = c["mask"].to(torch.bool)
    k_dq = torch.where(mask[None, :, None, :], c["k_fp16"], k_dq)

    return _fp16_sdpa(c["q"], k_dq, v_dq, c["H_q"], c["H_kv"])


# Sweep — Qwen2.5-7B attention shape; cached lengths spanning short → 64k.
SWEEP_S_KV = [1024, 4096, 16384, 32768, 65536]
QWEN_CFG = dict(B=1, H_q=28, H_kv=4, D=128, gk=32, gv=32, asymmetric=True,
                protect_fraction=0.04)


def main() -> int:
    try:
        import torch
    except ImportError:
        print("torch not installed — skipping."); return 0
    if not torch.cuda.is_available():
        print("no CUDA device — skipping (this benchmark requires a GPU).")
        return 0
    try:
        import triton  # noqa: F401
    except ImportError:
        print("triton not installed — skipping."); return 0

    from kv_policy.int4_fused_attention_kernel import (
        fused_protected_k_decode_attention,
    )

    dev = torch.cuda.get_device_name(0)
    print("=" * 80)
    print(f"Kernel 6c.1 throughput micro-benchmark")
    print(f"  device:   {dev}")
    print(f"  shape:    Qwen2.5-7B (B=1, H_q=28, H_kv=4, D=128)")
    print(f"  config:   protected-K 4% static, asymmetric, group=32, BLOCK_N=64")
    print(f"  metric:   per-decode-step median latency (μs, lower is better)")
    print("=" * 80)
    hdr = (f"{'S_kv':>8} | {'FP16 SDPA':>12} {'naive R-A':>12} {'kernel 6c.1':>12} "
           f"| {'kernel/FP16':>14} {'kernel/naive':>14}")
    print(hdr)
    print("-" * len(hdr))

    for S_kv in SWEEP_S_KV:
        try:
            c = _build_inputs(S_kv=S_kv, seed=42, **QWEN_CFG)

            def run_fp16():
                return _fp16_sdpa(c["q"], c["k_fp16"], c["v_fp16"],
                                  c["H_q"], c["H_kv"])

            def run_naive():
                return _naive_route_a_path(c)

            def run_kernel():
                return fused_protected_k_decode_attention(
                    q=c["q"], k_packed=c["k_packed"], k_scale=c["k_scale"],
                    k_offset=c["k_offset"], k_fp16=c["k_fp16"],
                    protect_mask=c["mask"],
                    v_packed=c["v_packed"], v_scale=c["v_scale"],
                    v_offset=c["v_offset"],
                    group_size_k=c["gk"], group_size_v=c["gv"],
                    asymmetric=c["asymmetric"],
                )

            t_fp16 = _time_cuda(run_fp16)
            t_naive = _time_cuda(run_naive)
            t_kern = _time_cuda(run_kernel)
            r_kf = t_kern / t_fp16
            r_kn = t_kern / t_naive
            print(f"{S_kv:>8} | {t_fp16:>11.1f}μ {t_naive:>11.1f}μ {t_kern:>11.1f}μ "
                  f"| {r_kf:>13.2f}x {r_kn:>13.2f}x")

            # Release before the next (larger) cell.
            del c
            torch.cuda.empty_cache()
        except torch.cuda.OutOfMemoryError as exc:
            print(f"{S_kv:>8} | OOM — skipping ({exc})")
            torch.cuda.empty_cache()
        except Exception as exc:  # noqa: BLE001
            print(f"{S_kv:>8} | ERROR: {type(exc).__name__}: {exc}")

    print("-" * len(hdr))
    print()
    print("Reading the columns:")
    print("  kernel/FP16  < 1.10x   → kernel is competitive with FP16; 6c.2 less urgent")
    print("  kernel/FP16  > ~1.5x   → real optimisation room; 6c.2 worth investing in")
    print("  kernel/naive < 1.0x    → kernel already beats the route-A fallback (the floor)")
    print()
    print("Note: this measures one attention layer, not end-to-end model decode.")
    print("Full layer-4 (vs FP8 vLLM, end-to-end tokens/sec) is 6c.3 work.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
