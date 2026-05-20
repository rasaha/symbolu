#!/usr/bin/env python3
"""Head-to-head microbench: route-A fused INT4 kernel vs FlashAttention.

Motivated by the 6c.3A v1 cell-D profile (Track-E §2024-11-XX): at
S=32k cell D runs at 0.55x of FP16 (cell A) end-to-end, and per-call
profiling showed kernel_call is 68% of the per-call cost (~0.78 ms).
That's slower than the FP16-FlashAttention baseline implied by cell A,
even though §20.6.2 single-layer microbench predicted 1.30x faster.

This microbench isolates the kernels — same B, H_q, H_kv, D, S; same
Q, K, V data; no vLLM, no wrapper. If our INT4 kernel is genuinely
slower than FA at S=32k, the bypass architecture has a kernel
optimisation gap that overhead-reduction can't close. If FA is
~the same speed or slower, the inflated 0.78 ms in cell D is coming
from somewhere else (cold caches, stream serialisation).

Compares two kernels:

* ``fused_protected_k_decode_attention`` (our route-A v1, FP16
  internally, INT4 packed KV with per-channel K scales)
* ``flash_attn_with_kvcache`` (vLLM's actual decode kernel) if
  available; otherwise ``F.scaled_dot_product_attention`` with the
  FlashAttention SDPA backend.

For each S in [2048, 8192, 16384, 32000]:

* Build inputs at Qwen2.5-7B shapes (B=1, H_q=28, H_kv=4, D=128)
* Warmup both kernels
* Time --iters calls of each via CUDA events, sorted -> p50 / p99
* Print one row per S with both timings and the ratio

Run:

    cd /workspace/symbolu/CTM_plus/Bench
    python scripts/kernel_int4_vs_fa_microbench.py \\
        --iters 200 --warmup 50 \\
        --output bench_out/kernel_int4_vs_fa.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_KV = Path(__file__).resolve().parents[2] / "KVPolicy"
if str(_KV) not in sys.path:
    sys.path.insert(0, str(_KV))


def _build_int4_inputs(B, H_q, H_kv, S, D, gk, gv, asymmetric, protect_fraction, seed):
    """Build our INT4 kernel inputs on GPU. Mirrors kernel_6c_gpu_test._build_inputs
    but stays on CPU only as long as needed, then moves to CUDA at the end."""
    import torch
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, quantize_per_token_int4, pack_int4,
    )

    g = torch.Generator().manual_seed(seed)
    k_fp16 = torch.randn(B, H_kv, S, D, generator=g, dtype=torch.float16)
    v_fp16 = torch.randn(B, H_kv, S, D, generator=g, dtype=torch.float16)
    q = torch.randn(B, H_q, D, generator=g, dtype=torch.float16)
    for h, d in [(0, 0), (min(2, H_kv - 1), 64), (min(1, H_kv - 1), 100)]:
        k_fp16[:, h, :, d] *= 40.0

    if protect_fraction <= 0.0:
        mask = torch.zeros(H_kv, D, dtype=torch.int8)
    elif protect_fraction >= 1.0:
        mask = torch.ones(H_kv, D, dtype=torch.int8)
    else:
        mag = k_fp16.abs().amax(dim=2).amax(dim=0)
        n = max(1, round(protect_fraction * H_kv * D))
        idx = torch.topk(mag.reshape(-1), n).indices
        flat = torch.zeros(H_kv * D, dtype=torch.int8)
        flat[idx] = 1
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

    k_packed = torch.stack(kp_l, 0).contiguous()
    v_packed = torch.stack(vp_l, 0).contiguous()
    k_scale = torch.stack(ks_l, 0).to(torch.float16).contiguous()
    v_scale = torch.stack(vs_l, 0).to(torch.float16).contiguous()
    k_offset = (torch.stack(ko_l, 0).to(torch.float16).contiguous()
                if asymmetric else None)
    v_offset = (torch.stack(vo_l, 0).to(torch.float16).contiguous()
                if asymmetric else None)

    dev = "cuda"
    return dict(
        q=q.to(dev), k_packed=k_packed.to(dev),
        k_scale=k_scale.to(dev),
        k_offset=(k_offset.to(dev) if k_offset is not None else None),
        k_fp16=k_fp16.to(dev).contiguous(),
        mask=mask.to(dev),
        v_packed=v_packed.to(dev), v_scale=v_scale.to(dev),
        v_offset=(v_offset.to(dev) if v_offset is not None else None),
        # FP16 originals for FA — kept on GPU at the canonical layout
        k_fp16_full=k_fp16.to(dev),
        v_fp16_full=v_fp16.to(dev),
        H_q=H_q, H_kv=H_kv, S=S, D=D, gk=gk, gv=gv, asymmetric=asymmetric,
    )


def _time_iters(fn, warmup, iters):
    """Run ``fn`` ``warmup + iters`` times, recording CUDA events on each
    timed call. Returns sorted list of per-call ms."""
    import torch
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    starts = [torch.cuda.Event(enable_timing=True) for _ in range(iters)]
    ends = [torch.cuda.Event(enable_timing=True) for _ in range(iters)]
    for i in range(iters):
        starts[i].record()
        fn()
        ends[i].record()
    torch.cuda.synchronize()
    times_ms = sorted(s.elapsed_time(e) for s, e in zip(starts, ends))
    return times_ms


def _summary(times_ms):
    n = len(times_ms)
    return {
        "n": n,
        "mean_ms": sum(times_ms) / n,
        "p50_ms": times_ms[n // 2],
        "p99_ms": times_ms[min(n - 1, int(0.99 * n))],
        "min_ms": times_ms[0],
        "max_ms": times_ms[-1],
    }


def _bench_one(S, args):
    import torch
    from kv_policy.int4_fused_attention_kernel import (
        fused_protected_k_decode_attention,
    )

    inputs = _build_int4_inputs(
        B=1, H_q=args.h_q, H_kv=args.h_kv, S=S, D=args.d,
        gk=args.gk, gv=args.gv, asymmetric=True,
        protect_fraction=args.protect_fraction, seed=args.seed,
    )

    # --- Our INT4 kernel ---
    q = inputs["q"]
    def call_ours():
        return fused_protected_k_decode_attention(
            q=q,
            k_packed=inputs["k_packed"], k_scale=inputs["k_scale"],
            k_offset=inputs["k_offset"], k_fp16=inputs["k_fp16"],
            protect_mask=inputs["mask"],
            v_packed=inputs["v_packed"], v_scale=inputs["v_scale"],
            v_offset=inputs["v_offset"],
            group_size_k=args.gk, group_size_v=args.gv, asymmetric=True,
        )

    ours_ms = _time_iters(call_ours, args.warmup, args.iters)
    ours = _summary(ours_ms)

    # --- FlashAttention baseline ---
    # Try flash_attn_with_kvcache first (what vLLM actually calls);
    # fall back to F.scaled_dot_product_attention on the FA backend.
    fa_kind = None
    fa_summary = None
    fa_error = None

    # Reshape K/V from (B, H_kv, S, D) -> (B, S, H_kv, D) for FA.
    k_for_fa = inputs["k_fp16_full"].permute(0, 2, 1, 3).contiguous()
    v_for_fa = inputs["v_fp16_full"].permute(0, 2, 1, 3).contiguous()
    # Reshape Q from (B, H_q, D) -> (B, 1, H_q, D).
    q_for_fa = q.unsqueeze(1).contiguous()

    try:
        from flash_attn import flash_attn_with_kvcache  # type: ignore
        cache_seqlens = torch.full(
            (1,), S, device="cuda", dtype=torch.int32,
        )
        def call_fa_kvcache():
            return flash_attn_with_kvcache(
                q=q_for_fa, k_cache=k_for_fa, v_cache=v_for_fa,
                cache_seqlens=cache_seqlens, causal=False,
            )
        fa_ms = _time_iters(call_fa_kvcache, args.warmup, args.iters)
        fa_summary = _summary(fa_ms)
        fa_kind = "flash_attn_with_kvcache"
    except Exception as e:  # noqa: BLE001
        fa_error = f"flash_attn_with_kvcache unavailable: {e!r}"

    if fa_summary is None:
        # Fallback: SDPA with the FA backend.
        try:
            import torch
            import torch.nn.functional as F
            # SDPA expects (B, H, L, D). Our Q is (1, H_q, D) -> (1, H_q, 1, D).
            q_sdpa = q.unsqueeze(2).contiguous()
            # SDPA k/v are (B, H, S, D); we already have that layout.
            k_sdpa = inputs["k_fp16_full"]
            v_sdpa = inputs["v_fp16_full"]
            if args.h_q != args.h_kv:
                rep = args.h_q // args.h_kv
                k_sdpa = k_sdpa.repeat_interleave(rep, dim=1)
                v_sdpa = v_sdpa.repeat_interleave(rep, dim=1)
            backends = getattr(torch.nn.attention, "sdpa_kernel", None)
            ctx = None
            if backends is not None:
                from torch.nn.attention import SDPBackend
                ctx = backends([SDPBackend.FLASH_ATTENTION])
            def call_fa_sdpa():
                if ctx is not None:
                    with ctx:
                        return F.scaled_dot_product_attention(
                            q_sdpa, k_sdpa, v_sdpa, is_causal=False,
                        )
                return F.scaled_dot_product_attention(
                    q_sdpa, k_sdpa, v_sdpa, is_causal=False,
                )
            fa_ms = _time_iters(call_fa_sdpa, args.warmup, args.iters)
            fa_summary = _summary(fa_ms)
            fa_kind = "sdpa_flash_attention"
        except Exception as e:  # noqa: BLE001
            fa_error = (fa_error or "") + f" ; sdpa fallback failed: {e!r}"

    return {
        "S": S,
        "H_q": args.h_q, "H_kv": args.h_kv, "D": args.d,
        "gk": args.gk, "gv": args.gv, "protect_fraction": args.protect_fraction,
        "ours": ours,
        "fa": fa_summary,
        "fa_kind": fa_kind,
        "fa_error": fa_error,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--seqlens", nargs="+", type=int,
                        default=[2048, 8192, 16384, 32000])
    parser.add_argument("--iters", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--h-q", type=int, default=28)
    parser.add_argument("--h-kv", type=int, default=4)
    parser.add_argument("--d", type=int, default=128)
    parser.add_argument("--gk", type=int, default=32)
    parser.add_argument("--gv", type=int, default=32)
    parser.add_argument("--protect-fraction", type=float, default=0.04)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    try:
        import torch  # noqa: F401
    except ImportError:
        print("torch not installed — skipping")
        return 0
    if not torch.cuda.is_available():
        print("no CUDA — skipping")
        return 0

    print(f"Bench: H_q={args.h_q} H_kv={args.h_kv} D={args.d} "
          f"gk={args.gk} gv={args.gv} protect={args.protect_fraction} "
          f"warmup={args.warmup} iters={args.iters}", flush=True)
    print(f"  {'S':>8} {'ours_p50':>10} {'fa_p50':>10} {'ratio':>8} "
          f"{'ours_p99':>10} {'fa_p99':>10}  fa_kind", flush=True)
    rows = []
    for S in args.seqlens:
        row = _bench_one(S, args)
        rows.append(row)
        ours_p50 = row["ours"]["p50_ms"]
        ours_p99 = row["ours"]["p99_ms"]
        if row["fa"] is not None:
            fa_p50 = row["fa"]["p50_ms"]
            fa_p99 = row["fa"]["p99_ms"]
            ratio = ours_p50 / fa_p50
            print(f"  {S:>8} {ours_p50:>10.4f} {fa_p50:>10.4f} "
                  f"{ratio:>8.2f}x {ours_p99:>10.4f} {fa_p99:>10.4f}  "
                  f"{row['fa_kind']}", flush=True)
        else:
            print(f"  {S:>8} {ours_p50:>10.4f} {'(FA n/a)':>10} "
                  f"{'-':>8} {ours_p99:>10.4f} {'-':>10}  "
                  f"err={row['fa_error']}", flush=True)

    out = {
        "config": {
            "h_q": args.h_q, "h_kv": args.h_kv, "d": args.d,
            "gk": args.gk, "gv": args.gv,
            "protect_fraction": args.protect_fraction,
            "warmup": args.warmup, "iters": args.iters,
        },
        "rows": rows,
    }
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(out, f, indent=2)
        print(f"Wrote {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
