#!/usr/bin/env python3
"""KVPro V3 Step-0 — Part H: two-half-kernel probe — is the INT4 decode "unzipper"
MEMORY-bound (fetching the scattered packed/scale/xmin/protect streams) or COMPUTE-bound
(the per-element dequant affine)? Answered WITHOUT `ncu` (counter-perm blocked:
ERR_NVGPUCTRPERM) by timing three specialisations of the SAME unzip inner loop:

  FETCH-only  — issue every load the full unzip issues (packed K/V nibbles, per-block
                K scale+xmin, per-token V scale+xmin, protected-K sidecar), unpack the
                nibbles, and reduce the raw loaded values. NO dequant affine, NO select.
                Isolates the HBM-fetch + unpack cost.
  MATH-only   — the dequant affine (`code*scale + xmin`) + protect `where`-select on
                REGISTER-resident operands (one real tile loaded once per (block,head),
                reused across the block with a per-token perturbation so the compiler
                cannot hoist). NO per-token HBM traffic. Isolates the un-zip arithmetic.
  FULL        — fetch + unpack + dequant affine + select (the real unzip).

Then (08_classify_unzip_bound.py):
  FULL ≈ FETCH (and FETCH ≫ MATH)  -> MEMORY-BOUND   (math hides under the fetch)
  FULL ≈ MATH  (and MATH ≫ FETCH)  -> COMPUTE-BOUND  (fetch hides under the math)
  FULL ≈ FETCH+MATH                -> BOTH-TIGHTENABLE (serial; neither hides the other)
cross-checked against an analytical roofline (measured GB/s vs A100 peak HBM; measured
GFLOP/s vs A100 peak) — the roofline needs peak assumptions, the three-times verdict does NOT.

The unzip is measured production-faithfully (compact bf16 protected sidecar, n_protect of D
channels — the 6c.3C stored layout, NOT simplified). A second FULL config with the
route-A full-fp16-K protect load (int4_fused_attention_kernel.py:140) is timed as the ONE
ablation: FULL_full − FULL_compact is the fp16-pool penalty (what a compact-protect read
kernel would remove). The attention matmuls (tl.dot) are deliberately NOT in scope — they
run at bf16 speed regardless of the format; the unzip is the format's tax.

POD-ONLY, HARDWARE-UNTESTED (needs a CUDA GPU + Triton). Writes label=UNAVAILABLE (never
fabricated) if GPU/Triton is missing. The byte/FLOP model + input geometry are CPU-testable
(test_unzip_probe_cpu.py) without a GPU.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                     # route_a_builder (writer-faithful packed view)

try:
    import torch
except Exception:  # pragma: no cover  - CPU model funcs below don't need torch
    torch = None  # type: ignore

try:
    import triton
    import triton.language as tl
    _HAVE_TRITON = True
except Exception:  # pragma: no cover
    triton = None  # type: ignore
    tl = None  # type: ignore
    _HAVE_TRITON = False


# ======================================================================== #
# Byte / FLOP model (pure python — CPU-testable, no GPU). Must match EXACTLY
# what the kernel below loads/computes, so the roofline uses real volumes.
# ======================================================================== #
def byte_flop_model(S, H, D, BS, n_protect, v_group_size, protect_mode):
    """Total HBM bytes fetched and dequant FLOPs performed by the FULL unzip over the
    whole (n_blocks x H) grid, for `protect_mode` in {"compact","full","none"}.

    Per (block, head): K scale+xmin loaded ONCE per block (production groups K per BS);
    per token: packed-K nibbles, protected-K sidecar, packed-V nibbles, V scale+xmin.
    Scales/xmin/protect are bf16 (2 B); packed nibbles are 1 B per 2 channels (D/2)."""
    DH = (D + 1) // 2
    VNG = D // v_group_size
    n_blocks = (S + BS - 1) // BS
    S_pad = n_blocks * BS
    if protect_mode == "compact":
        prot_b = 2 * n_protect             # bf16 sidecar, n_protect of D channels
    elif protect_mode == "full":
        prot_b = 2 * D                     # route-A full fp16 K load (all D channels)
    else:
        prot_b = 0
    # per-block (once): k_scale + k_xmin, each D bf16
    block_bytes = 2 * (2 * D)
    # per-token: packed K + protect + packed V + v_scale + v_xmin
    tok_bytes = DH + prot_b + DH + 2 * VNG + 2 * VNG
    total_bytes = n_blocks * H * block_bytes + S_pad * H * tok_bytes
    # dequant affine: K (mul+add) + V (mul+add) = 4 FLOP per (channel, token, head)
    total_flops = 4 * D * S_pad * H
    return {
        "protect_mode": protect_mode, "S": S, "S_padded": S_pad, "n_blocks": n_blocks,
        "H": H, "D": D, "DH": DH, "BS": BS, "n_protect": n_protect, "v_n_groups": VNG,
        "protect_bytes_per_tok_head": prot_b,
        "block_bytes_per_head": block_bytes, "tok_bytes_per_head": tok_bytes,
        "total_fetch_bytes": total_bytes, "total_dequant_flops": total_flops,
        "arithmetic_intensity_flop_per_byte": round(total_flops / max(total_bytes, 1), 5),
    }


# ---- MODE / PROTECT constants shared by the kernel + driver (kept in sync) ----
MODE_FETCH, MODE_MATH, MODE_FULL = 0, 1, 2
PROT_NONE, PROT_COMPACT, PROT_FULL = 0, 1, 2


if _HAVE_TRITON:

    @triton.jit
    def _unzip_probe_kernel(
        k_packed_ptr, k_scale_ptr, k_xmin_ptr,
        v_packed_ptr, v_scale_ptr, v_xmin_ptr,
        k_protect_ptr, protect_slot_ptr, k_fp16_ptr,
        out_ptr,
        S, H, n_protect,
        D: tl.constexpr, DH: tl.constexpr, BS: tl.constexpr,
        VNG: tl.constexpr, GS_v: tl.constexpr,
        MODE: tl.constexpr, PROTECT: tl.constexpr,
    ):
        # One program per (block, KV head). Native (S, H, *) buffers (no permute) — the
        # cache's own layout. A single 2D (BS tokens x D channels) tile per program, so the
        # per-token loads coalesce (faithful HBM behaviour for the roofline). The three MODEs
        # share this exact tile shape, so fetch/math/full process identical element counts.
        blk = tl.program_id(0)
        h = tl.program_id(1)
        d = tl.arange(0, D)                         # (D,)
        r = tl.arange(0, BS)                        # (BS,) token rows in the block
        s = blk * BS + r                            # (BS,) physical positions
        byte_col = d // 2
        is_high = d % 2
        gv = d // GS_v

        # per-BLOCK K scale/xmin (production groups K per BS -> ONE load per block) + the
        # static protect mask/slots for this head (all (D,), broadcast over the BS rows).
        ks_off = (blk * H + h) * D + d
        k_sc = tl.load(k_scale_ptr + ks_off).to(tl.float32)         # (D,)
        k_xm = tl.load(k_xmin_ptr + ks_off).to(tl.float32)          # (D,)
        slot = tl.load(protect_slot_ptr + h * D + d).to(tl.int32)   # (D,) slot or -1
        pm = slot >= 0                                              # (D,)

        if MODE == MODE_MATH:
            # ---- MATH-only: load ONE row's operands, broadcast to the (BS,D) tile, run the
            # affine perturbed per-row on a MULTIPLY operand (kt) so the compiler cannot hoist
            # the multiply out — the dequant mul is genuinely re-executed BS*D times. No
            # per-token HBM (one row amortised over BS). This UPPER-bounds the true compute.
            base = (blk * BS) * H + h
            kcode0 = ((tl.load(k_packed_ptr + base * DH + byte_col).to(tl.int32)
                       >> (4 * is_high)) & 0xF).to(tl.float32)      # (D,)
            kf0 = tl.load(k_fp16_ptr + base * D + d).to(tl.float32)          # (D,)
            vcode0 = ((tl.load(v_packed_ptr + base * DH + byte_col).to(tl.int32)
                       >> (4 * is_high)) & 0xF).to(tl.float32)      # (D,)
            v_sc = tl.load(v_scale_ptr + base * VNG + gv).to(tl.float32)     # (D,)
            v_xm = tl.load(v_xmin_ptr + base * VNG + gv).to(tl.float32)      # (D,)
            rf = r.to(tl.float32)                                            # (BS,)
            kt = kcode0[None, :] + rf[:, None]                     # (BS,D) per-row-distinct
            k_dq = kt * k_sc[None, :] + k_xm[None, :]              # mul+add re-run per row
            k_eff = tl.where(pm[None, :], kf0[None, :], k_dq)
            vt = vcode0[None, :] + rf[:, None]
            v_dq = vt * v_sc[None, :] + v_xm[None, :]
            r_out = k_eff + v_dq                                   # (BS,D)
        else:
            kp_off = (s[:, None] * H + h) * DH + byte_col[None, :]           # (BS,D)
            kcode = ((tl.load(k_packed_ptr + kp_off).to(tl.int32)
                      >> (4 * is_high[None, :])) & 0xF).to(tl.float32)
            if PROTECT == PROT_FULL:                   # route-A: full fp16 K, all D channels
                kf = tl.load(k_fp16_ptr + (s[:, None] * H + h) * D + d[None, :]).to(tl.float32)
            elif PROTECT == PROT_COMPACT:              # production: compact n_protect sidecar
                slot_idx = tl.where(pm, slot, 0)
                kf = tl.load(k_protect_ptr + (s[:, None] * H + h) * n_protect + slot_idx[None, :],
                             mask=pm[None, :], other=0.0).to(tl.float32)
            else:
                kf = tl.zeros((BS, D), tl.float32)
            vp_off = (s[:, None] * H + h) * DH + byte_col[None, :]
            vcode = ((tl.load(v_packed_ptr + vp_off).to(tl.int32)
                      >> (4 * is_high[None, :])) & 0xF).to(tl.float32)
            vs_off = (s[:, None] * H + h) * VNG + gv[None, :]
            v_sc = tl.load(v_scale_ptr + vs_off).to(tl.float32)
            v_xm = tl.load(v_xmin_ptr + vs_off).to(tl.float32)
            if MODE == MODE_FETCH:                      # loads + unpack + reduce (no affine/select)
                r_out = kcode + k_sc[None, :] + k_xm[None, :] + kf + vcode + v_sc + v_xm
            else:                                       # MODE_FULL: the real unzip
                k_dq = kcode * k_sc[None, :] + k_xm[None, :]
                k_eff = tl.where(pm[None, :], kf, k_dq)
                v_dq = vcode * v_sc + v_xm
                r_out = k_eff + v_dq
        tl.store(out_ptr + (blk * H + h), tl.sum(tl.sum(r_out, axis=0), axis=0))


def _to_native(view, K_fp, device):
    """From route_a_builder.build_packed_view (already native (S,H,*)): pull the probe's
    kernel tensors in the cache's stored dtypes (packed uint8; scale/xmin/protect bf16)."""
    dev = device
    k_packed = view["k_int4"][0].contiguous().to(dev)                       # (S,H,DH) uint8
    v_packed = view["v_int4"][0].contiguous().to(dev)
    k_scale = view["k_scale"][0].to(torch.bfloat16).contiguous().to(dev)    # (n_blocks,H,D)
    k_xmin = view["k_xmin"][0].to(torch.bfloat16).contiguous().to(dev)
    v_scale = view["v_scale"][0].to(torch.bfloat16).contiguous().to(dev)    # (S,H,VNG)
    v_xmin = view["v_xmin"][0].to(torch.bfloat16).contiguous().to(dev)
    k_protect = view["k_protect_bf16"][0].contiguous().to(dev)              # (S,H,n_protect)
    protect_slot = view["protect_slot"].to(torch.int32).contiguous().to(dev)  # (H,D)
    S, H, D = K_fp.shape
    k_fp16 = K_fp.to(torch.float16).contiguous().to(dev)                    # (S,H,D) route-A
    return dict(k_packed=k_packed, v_packed=v_packed, k_scale=k_scale, k_xmin=k_xmin,
                v_scale=v_scale, v_xmin=v_xmin, k_protect=k_protect,
                protect_slot=protect_slot, k_fp16=k_fp16)


def _build_inputs(context_len, H_kv, D, BS, v_group_size, n_protect, seed, device):
    """Production-faithful packed inputs via the writer contract (route_a_builder). Padded
    to full BS-blocks (timing needs no partial tails). Returns (tensors, geom)."""
    import route_a_builder as RB
    torch.manual_seed(seed)
    n_blocks = (context_len + BS - 1) // BS
    S = n_blocks * BS
    K_fp = torch.randn(S, H_kv, D)
    V_fp = torch.randn(S, H_kv, D)
    mask = torch.zeros(H_kv, D, dtype=torch.int8)
    for h in range(H_kv):
        mask[h, torch.randperm(D)[:n_protect]] = 1
    view = RB.build_packed_view(K_fp, V_fp, mask, BS=BS, v_group_size=v_group_size,
                                k_min=torch.full((H_kv, D), -3.0), k_max=torch.full((H_kv, D), 3.0))
    ten = _to_native(view, K_fp, device)
    geom = dict(S=S, H=H_kv, D=D, DH=(D + 1) // 2, BS=BS, VNG=D // v_group_size,
                GS_v=v_group_size, n_protect=int(view["n_protect"]), n_blocks=n_blocks)
    return ten, geom


def _launch(ten, geom, mode, protect):
    D, DH, BS, VNG, GS_v = geom["D"], geom["DH"], geom["BS"], geom["VNG"], geom["GS_v"]
    S, H, n_blocks = geom["S"], geom["H"], geom["n_blocks"]
    out = torch.empty(n_blocks * H, dtype=torch.float32, device=ten["k_packed"].device)
    grid = (n_blocks, H)
    _unzip_probe_kernel[grid](
        ten["k_packed"], ten["k_scale"], ten["k_xmin"],
        ten["v_packed"], ten["v_scale"], ten["v_xmin"],
        ten["k_protect"], ten["protect_slot"], ten["k_fp16"],
        out, S, H, geom["n_protect"],
        D=D, DH=DH, BS=BS, VNG=VNG, GS_v=GS_v, MODE=mode, PROTECT=protect,
    )
    return out


def _time_ms(fn, iters):
    for _ in range(5):
        fn()
    torch.cuda.synchronize()
    s = torch.cuda.Event(True); e = torch.cuda.Event(True)
    s.record()
    for _ in range(iters):
        fn()
    e.record(); torch.cuda.synchronize()
    return s.elapsed_time(e) / iters


def run_probe(contexts, iters, H_kv, D, BS, v_group_size, n_protect, seed=0):
    """Time FETCH / MATH / FULL(compact) / FULL(full-protect) per context. GPU-only."""
    per_ctx = {}
    for ctx in contexts:
        ten, geom = _build_inputs(ctx, H_kv, D, BS, v_group_size, n_protect, seed, "cuda")
        np_ = geom["n_protect"]
        t_fetch = _time_ms(lambda: _launch(ten, geom, MODE_FETCH, PROT_COMPACT), iters)
        t_math = _time_ms(lambda: _launch(ten, geom, MODE_MATH, PROT_COMPACT), iters)
        t_full_c = _time_ms(lambda: _launch(ten, geom, MODE_FULL, PROT_COMPACT), iters)
        t_full_f = _time_ms(lambda: _launch(ten, geom, MODE_FULL, PROT_FULL), iters)
        per_ctx[str(ctx)] = {
            "fetch_only_ms": round(t_fetch, 5), "math_only_ms": round(t_math, 5),
            "full_compact_ms": round(t_full_c, 5), "full_fullprotect_ms": round(t_full_f, 5),
            "S_padded": geom["S"], "n_blocks": geom["n_blocks"], "iters": iters,
            "model_compact": byte_flop_model(geom["S"], H_kv, D, BS, np_, v_group_size, "compact"),
            "model_fullprotect": byte_flop_model(geom["S"], H_kv, D, BS, np_, v_group_size, "full"),
        }
        print(f"  ctx={ctx:6} fetch={t_fetch:.4f} math={t_math:.4f} "
              f"full_compact={t_full_c:.4f} full_full={t_full_f:.4f} ms  (n_protect={np_})")
    return per_ctx


def _device_info():
    p = torch.cuda.get_device_properties(0)
    return {"name": p.name, "total_mem_gb": round(p.total_memory / 1e9, 1),
            "sm_count": p.multi_processor_count}


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 two-half-kernel unzip-bound probe")
    ap.add_argument("--contexts", default="4096 16384 32768")
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--h-kv", type=int, default=4)
    ap.add_argument("--head-dim", type=int, default=128)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--v-group-size", type=int, default=32)
    ap.add_argument("--n-protect", type=int, default=5)
    ap.add_argument("--out", default=os.path.join(_HERE, "runs", "unzip_bound.json"))
    a = ap.parse_args(argv)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)

    def bail(msg):
        json.dump({"label": "UNAVAILABLE", "error": msg, "per_ctx": {}}, open(a.out, "w"), indent=2)
        print(f"[UNAVAILABLE] {msg} -> {a.out}")
        return 3

    if torch is None:
        return bail("torch import failed")
    if not torch.cuda.is_available():
        return bail("no CUDA GPU")
    if not _HAVE_TRITON:
        return bail("Triton not available (GPU build) — probe cannot launch")
    ctxs = [int(c) for c in a.contexts.split()]
    try:
        per_ctx = run_probe(ctxs, a.iters, a.h_kv, a.head_dim, a.bs, a.v_group_size, a.n_protect)
    except Exception as e:  # noqa: BLE001
        return bail(f"probe launch failed: {e}")
    blob = {
        "label": "GPU-measured", "probe": "unzip_bound_two_half_kernel",
        "device": _device_info(),
        "geom": {"H_kv": a.h_kv, "D": a.head_dim, "BS": a.bs,
                 "v_group_size": a.v_group_size, "n_protect_requested": a.n_protect},
        "per_ctx": per_ctx,
        "note": ("Three specialisations of ONE unzip inner loop. FETCH=loads+unpack+reduce; "
                 "MATH=affine+select on register-resident operands (no per-token HBM); "
                 "FULL=fetch+unpack+affine+select. compact=production compact-protect sidecar; "
                 "fullprotect=route-A full-fp16-K load (int4_fused_attention_kernel.py:140). "
                 "Attention matmuls out of scope (bf16-speed regardless). MATH is an UPPER "
                 "bound on the true dequant compute (it re-fabricates the +token perturbation "
                 "the real kernel gets from loads)."),
    }
    json.dump(blob, open(a.out, "w"), indent=2)
    print(f"[GPU-measured] unzip-bound probe -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
