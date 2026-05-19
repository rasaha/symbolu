"""Triton fused protected-K INT4 decode-attention kernel — 6c.1.

Correctness-first implementation of ``KERNEL_6C_BLUEPRINT.md`` §6-§7.

v1 scope (6c.1): non-paged, single decode token (S_q = 1), option-A
protected-K overlay (full-D INT4 + FP16 side-tensor + static mask),
FP16 I/O, FP32 softmax accumulator, asymmetric + symmetric via a
constexpr flag, one Triton program per (batch, query-head).

Numerical oracle: ``fused_int4_attention_reference`` (with ``k_fp16`` /
``k_protect_mask``) in ``int4_fused_attention_sketch.py``. The GPU test
script ``Bench/scripts/kernel_6c_gpu_test.py`` validates against it.

STATUS: 6c.1 iteration. This CANNOT be CPU-validated — it needs a GPU
with Triton. Expect iteration: run the test script, feed back the
per-shape cosine / max-abs report.
"""

from __future__ import annotations

import math
from typing import Optional

try:
    import torch  # type: ignore
except ImportError:  # pragma: no cover
    torch = None  # type: ignore

try:
    import triton  # type: ignore
    import triton.language as tl  # type: ignore
    _HAVE_TRITON = True
except ImportError:  # pragma: no cover
    triton = None  # type: ignore
    tl = None  # type: ignore
    _HAVE_TRITON = False


if _HAVE_TRITON:

    @triton.jit
    def _fused_protected_k_decode_attn_kernel(
        q_ptr, k_packed_ptr, k_scale_ptr, k_offset_ptr, k_fp16_ptr,
        protect_mask_ptr, v_packed_ptr, v_scale_ptr, v_offset_ptr,
        out_ptr,
        B, H_q, H_kv, S_kv, n_grp_k, n_grp_v,
        softmax_scale,
        D: tl.constexpr, DH: tl.constexpr,
        GS_k: tl.constexpr, GS_v: tl.constexpr,
        BLOCK_N: tl.constexpr, ASYMMETRIC: tl.constexpr,
    ):
        # One program per (batch b, query head hq). Decode: S_q = 1.
        pid = tl.program_id(0)
        b = pid // H_q
        hq = pid % H_q
        G = H_q // H_kv
        hkv = hq // G                                  # GQA: KV head for hq

        d = tl.arange(0, D)                            # (D,) head-dim idx
        byte_col = d // 2                              # (D,) packed-byte col
        is_high = d % 2                                # (D,) low/high nibble

        # ---- Q (D,) — stays FP16, loaded once ----
        q = tl.load(q_ptr + (b * H_q + hq) * D + d).to(tl.float32)

        # ---- static protected-channel mask for this KV head (D,) ----
        pm = tl.load(protect_mask_ptr + hkv * D + d) != 0

        # ---- online-softmax state ----
        m_i = tl.full((), -float("inf"), tl.float32)
        l_i = tl.zeros((), tl.float32)
        acc = tl.zeros((D,), tl.float32)

        n_tiles = tl.cdiv(S_kv, BLOCK_N)
        for t in range(0, n_tiles):
            s = t * BLOCK_N + tl.arange(0, BLOCK_N)    # (BLOCK_N,) KV pos
            valid = s < S_kv

            # ---- K: load packed bytes, unpack INT4, dequant ----
            # k_packed: (B, H_kv, S_kv, DH) uint8
            kp_off = (((b * H_kv + hkv) * S_kv) + s[:, None]) * DH + byte_col[None, :]
            kbyte = tl.load(k_packed_ptr + kp_off, mask=valid[:, None], other=0).to(tl.int32)
            kiv = ((kbyte >> (4 * is_high[None, :])) & 0xF) - 8        # signed int4
            kiv = kiv.to(tl.float32)
            # k_scale / k_offset: (B, n_grp_k, H_kv, D), group = s // GS_k
            gk = s // GS_k
            ks_off = (((b * n_grp_k + gk[:, None]) * H_kv) + hkv) * D + d[None, :]
            k_sc = tl.load(k_scale_ptr + ks_off, mask=valid[:, None], other=1.0).to(tl.float32)
            k_dq = kiv * k_sc
            if ASYMMETRIC:
                k_of = tl.load(k_offset_ptr + ks_off, mask=valid[:, None], other=0.0).to(tl.float32)
                k_dq = k_dq + k_of
            # protected-K overlay: masked channels take the FP16 originals
            kf_off = (((b * H_kv + hkv) * S_kv) + s[:, None]) * D + d[None, :]
            k_f16 = tl.load(k_fp16_ptr + kf_off, mask=valid[:, None], other=0.0).to(tl.float32)
            k_eff = tl.where(pm[None, :], k_f16, k_dq)                # (BLOCK_N, D)

            # ---- scores = (Q · K_effᵀ) * softmax_scale ----
            scores = tl.sum(q[None, :] * k_eff, axis=1) * softmax_scale  # (BLOCK_N,)
            scores = tl.where(valid, scores, -float("inf"))

            # ---- online softmax ----
            m_new = tl.maximum(m_i, tl.max(scores, axis=0))
            p = tl.exp(scores - m_new)                                # (BLOCK_N,)
            alpha = tl.exp(m_i - m_new)
            l_i = l_i * alpha + tl.sum(p, axis=0)

            # ---- V: load packed bytes, unpack INT4, dequant ----
            vp_off = (((b * H_kv + hkv) * S_kv) + s[:, None]) * DH + byte_col[None, :]
            vbyte = tl.load(v_packed_ptr + vp_off, mask=valid[:, None], other=0).to(tl.int32)
            viv = (((vbyte >> (4 * is_high[None, :])) & 0xF) - 8).to(tl.float32)
            # v_scale / v_offset: (B, S_kv, H_kv, n_grp_v), group = d // GS_v
            gv = d // GS_v
            vs_off = (((b * S_kv + s[:, None]) * H_kv) + hkv) * n_grp_v + gv[None, :]
            v_sc = tl.load(v_scale_ptr + vs_off, mask=valid[:, None], other=1.0).to(tl.float32)
            v_dq = viv * v_sc
            if ASYMMETRIC:
                v_of = tl.load(v_offset_ptr + vs_off, mask=valid[:, None], other=0.0).to(tl.float32)
                v_dq = v_dq + v_of

            # ---- accumulate ----
            acc = acc * alpha + tl.sum(p[:, None] * v_dq, axis=0)     # (D,)
            m_i = m_new

        out = acc / l_i
        tl.store(out_ptr + (b * H_q + hq) * D + d, out.to(tl.float16))


def fused_protected_k_decode_attention(
    q: "torch.Tensor",
    k_packed: "torch.Tensor",
    k_scale: "torch.Tensor",
    k_offset: "Optional[torch.Tensor]",
    k_fp16: "torch.Tensor",
    protect_mask: "torch.Tensor",
    v_packed: "torch.Tensor",
    v_scale: "torch.Tensor",
    v_offset: "Optional[torch.Tensor]",
    *,
    group_size_k: int,
    group_size_v: int,
    asymmetric: bool,
    softmax_scale: Optional[float] = None,
    block_n: int = 64,
) -> "torch.Tensor":
    """Launch the 6c.1 fused protected-K INT4 decode-attention kernel.

    Shapes (all contiguous, on CUDA) — see KERNEL_6C_BLUEPRINT.md §3:
      q            (B, H_q, D)              fp16
      k_packed     (B, H_kv, S_kv, D//2)    uint8
      k_scale      (B, n_grp_k, H_kv, D)    fp16
      k_offset     (B, n_grp_k, H_kv, D)    fp16  or None (symmetric)
      k_fp16       (B, H_kv, S_kv, D)       fp16
      protect_mask (H_kv, D)                int8 (0/1)
      v_packed     (B, H_kv, S_kv, D//2)    uint8
      v_scale      (B, S_kv, H_kv, n_grp_v) fp16
      v_offset     (B, S_kv, H_kv, n_grp_v) fp16  or None (symmetric)
    Returns attn_out (B, H_q, D) fp16.
    """
    if torch is None:
        raise ImportError("fused_protected_k_decode_attention requires PyTorch.")
    if not _HAVE_TRITON:
        raise ImportError(
            "fused_protected_k_decode_attention requires Triton (GPU build)."
        )
    if not q.is_cuda:
        raise ValueError("inputs must be on CUDA.")

    B, H_q, D = q.shape
    _, H_kv, S_kv, DH = k_packed.shape
    n_grp_k = k_scale.shape[1]
    n_grp_v = v_scale.shape[3]
    assert DH == (D + 1) // 2, f"k_packed last dim {DH} != ceil(D/2) {(D + 1) // 2}"
    assert H_q % H_kv == 0, f"H_q {H_q} not divisible by H_kv {H_kv}"
    assert protect_mask.shape == (H_kv, D)

    if softmax_scale is None:
        softmax_scale = 1.0 / math.sqrt(D)

    # Symmetric mode: the kernel still needs valid offset pointers — pass
    # zero tensors; the ASYMMETRIC constexpr compiles the add out anyway.
    if k_offset is None:
        k_offset = torch.zeros_like(k_scale)
    if v_offset is None:
        v_offset = torch.zeros_like(v_scale)

    tensors = dict(
        q=q, k_packed=k_packed, k_scale=k_scale, k_offset=k_offset,
        k_fp16=k_fp16, protect_mask=protect_mask, v_packed=v_packed,
        v_scale=v_scale, v_offset=v_offset,
    )
    for name, t in tensors.items():
        if not t.is_contiguous():
            raise ValueError(f"{name} must be contiguous (v1 assumes C-order).")

    out = torch.empty((B, H_q, D), dtype=torch.float16, device=q.device)
    grid = (B * H_q,)
    _fused_protected_k_decode_attn_kernel[grid](
        q, k_packed, k_scale, k_offset, k_fp16,
        protect_mask, v_packed, v_scale, v_offset, out,
        B, H_q, H_kv, S_kv, n_grp_k, n_grp_v,
        softmax_scale,
        D=D, DH=DH,
        GS_k=group_size_k, GS_v=group_size_v,
        BLOCK_N=block_n, ASYMMETRIC=bool(asymmetric),
    )
    return out
