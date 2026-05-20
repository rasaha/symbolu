"""Triton fused protected-K INT4 decode-attention kernel — 6c.2.

Implementation of ``KERNEL_6C_BLUEPRINT.md`` §6-§7 with the §20.6.1
"6c.2 round" optimisations:

  1. ``tl.dot`` for the QKᵀ and PV matmuls — engages A100 tensor cores
     instead of the v1 elementwise multiply + ``tl.sum`` path.
  2. Split-K (FlashDecoding-style KV-sequence partitioning) — multiple
     Triton programs per (batch, KV head) cover different KV ranges
     for the same decode token, then a tiny combine kernel merges
     their partial (m, l, acc) via the online-softmax formula. Lifts
     SM occupancy beyond the v1 "28 programs on 108 SMs" ceiling.
  3. GQA grouping — one program handles the G query heads that share a
     KV head as the M dim of the matmuls (``M = G_PAD`` rows). v1 had
     M=1; here M≥16, which is the minimum useful tensor-core M tile.

Numerical oracle: ``fused_int4_attention_reference`` with ``k_fp16`` /
``k_protect_mask`` (in ``int4_fused_attention_sketch.py``). Validated
by ``Bench/scripts/kernel_6c_gpu_test.py`` (correctness, cosine ≥ 0.999)
and benchmarked by ``Bench/scripts/kernel_6c_throughput.py``.

STATUS: 6c.2 round 1. CANNOT be CPU-validated — needs a GPU with Triton.
Success gate (per §20.6.1): reach within ~2× of FP16 SDPA; >4× = stop
and document specialist-kernel work is required.
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


def _next_pow2(n: int) -> int:
    p = 1
    while p < n:
        p *= 2
    return p


if _HAVE_TRITON:

    @triton.jit
    def _fused_protected_k_decode_attn_splitk_kernel(
        q_ptr, k_packed_ptr, k_scale_ptr, k_offset_ptr, k_fp16_ptr,
        protect_mask_ptr, v_packed_ptr, v_scale_ptr, v_offset_ptr,
        m_scratch_ptr, l_scratch_ptr, acc_scratch_ptr,
        B, H_q, H_kv, S_kv, n_grp_k, n_grp_v,
        SPLIT_K, chunk_size,
        softmax_scale,
        G: tl.constexpr, G_PAD: tl.constexpr,
        D: tl.constexpr, DH: tl.constexpr,
        GS_k: tl.constexpr, GS_v: tl.constexpr,
        BLOCK_N: tl.constexpr, ASYMMETRIC: tl.constexpr,
    ):
        # One program per (batch, KV head, split). The G query heads
        # sharing this KV head are handled as the M dim of the matmuls.
        pid_bh = tl.program_id(0)
        pid_sk = tl.program_id(1)
        b = pid_bh // H_kv
        hkv = pid_bh % H_kv

        # KV range owned by this split.
        s_start = pid_sk * chunk_size
        s_end = tl.minimum(s_start + chunk_size, S_kv)

        d = tl.arange(0, D)                       # (D,) head-dim
        byte_col = d // 2
        is_high = d % 2
        g_q = tl.arange(0, G_PAD)                 # (G_PAD,) query rows
        g_valid = g_q < G                         # pad rows masked at store

        # ---- Q (G_PAD, D) fp16 — pad rows clamp to row 0 ----
        hq_idx = tl.where(g_valid, g_q, 0)
        hq_arr = hkv * G + hq_idx
        q_off = (b * H_q + hq_arr[:, None]) * D + d[None, :]
        q = tl.load(q_ptr + q_off).to(tl.float16)

        # ---- static protected-channel mask for this KV head (D,) ----
        pm = tl.load(protect_mask_ptr + hkv * D + d) != 0

        # ---- per-row online-softmax state (FP32) ----
        m_i = tl.full((G_PAD,), -float("inf"), tl.float32)
        l_i = tl.zeros((G_PAD,), tl.float32)
        acc = tl.zeros((G_PAD, D), tl.float32)

        n_tiles = tl.cdiv(s_end - s_start, BLOCK_N)
        for t in range(0, n_tiles):
            s = s_start + t * BLOCK_N + tl.arange(0, BLOCK_N)
            valid = s < s_end

            # ---- K tile: load packed bytes, unpack INT4, dequant ----
            kp_off = (((b * H_kv + hkv) * S_kv) + s[:, None]) * DH + byte_col[None, :]
            kbyte = tl.load(k_packed_ptr + kp_off, mask=valid[:, None], other=0).to(tl.int32)
            kiv = (((kbyte >> (4 * is_high[None, :])) & 0xF) - 8).to(tl.float32)
            gk = s // GS_k
            ks_off = (((b * n_grp_k + gk[:, None]) * H_kv) + hkv) * D + d[None, :]
            k_sc = tl.load(k_scale_ptr + ks_off, mask=valid[:, None], other=1.0).to(tl.float32)
            k_dq = kiv * k_sc
            if ASYMMETRIC:
                k_of = tl.load(k_offset_ptr + ks_off, mask=valid[:, None], other=0.0).to(tl.float32)
                k_dq = k_dq + k_of
            # protected-K overlay
            kf_off = (((b * H_kv + hkv) * S_kv) + s[:, None]) * D + d[None, :]
            k_f16 = tl.load(k_fp16_ptr + kf_off, mask=valid[:, None], other=0.0).to(tl.float32)
            k_eff = tl.where(pm[None, :], k_f16, k_dq).to(tl.float16)   # (BLOCK_N, D)

            # ---- QKᵀ via tl.dot (tensor cores): (G_PAD,D) · (D,BLOCK_N) -> (G_PAD,BLOCK_N) ----
            scores = tl.dot(q, tl.trans(k_eff), out_dtype=tl.float32) * softmax_scale
            scores = tl.where(valid[None, :], scores, -float("inf"))

            # ---- per-row online softmax (FP32) ----
            m_tile = tl.max(scores, axis=1)        # (G_PAD,)
            m_new = tl.maximum(m_i, m_tile)
            p = tl.exp(scores - m_new[:, None])    # (G_PAD, BLOCK_N)
            alpha = tl.exp(m_i - m_new)            # (G_PAD,)
            l_i = l_i * alpha + tl.sum(p, axis=1)

            # ---- V tile: load packed, unpack, dequant -> (BLOCK_N, D) fp16 ----
            vp_off = (((b * H_kv + hkv) * S_kv) + s[:, None]) * DH + byte_col[None, :]
            vbyte = tl.load(v_packed_ptr + vp_off, mask=valid[:, None], other=0).to(tl.int32)
            viv = (((vbyte >> (4 * is_high[None, :])) & 0xF) - 8).to(tl.float32)
            gv = d // GS_v
            vs_off = (((b * S_kv + s[:, None]) * H_kv) + hkv) * n_grp_v + gv[None, :]
            v_sc = tl.load(v_scale_ptr + vs_off, mask=valid[:, None], other=1.0).to(tl.float32)
            v_dq = viv * v_sc
            if ASYMMETRIC:
                v_of = tl.load(v_offset_ptr + vs_off, mask=valid[:, None], other=0.0).to(tl.float32)
                v_dq = v_dq + v_of
            v_dq_fp16 = v_dq.to(tl.float16)        # (BLOCK_N, D)

            # ---- PV via tl.dot (tensor cores): (G_PAD,BLOCK_N) · (BLOCK_N,D) -> (G_PAD,D) ----
            p_fp16 = p.to(tl.float16)
            acc = acc * alpha[:, None] + tl.dot(p_fp16, v_dq_fp16, out_dtype=tl.float32)
            m_i = m_new

        # ---- Write per-split (m, l, acc) for valid rows only ----
        # Layouts: m,l (B, H_q, SPLIT_K); acc (B, H_q, SPLIT_K, D).
        # Pad rows (g_q >= G) are masked out — they ran redundantly to
        # keep the matmul shape rectangular, but their results are not
        # stored.
        hq_real = hkv * G + g_q                         # (G_PAD,)
        ml_off = (b * H_q + hq_real) * SPLIT_K + pid_sk
        tl.store(m_scratch_ptr + ml_off, m_i, mask=g_valid)
        tl.store(l_scratch_ptr + ml_off, l_i, mask=g_valid)
        acc_off = ((b * H_q + hq_real[:, None]) * SPLIT_K + pid_sk) * D + d[None, :]
        tl.store(acc_scratch_ptr + acc_off, acc, mask=g_valid[:, None])

    @triton.jit
    def _combine_splits_kernel(
        m_scratch_ptr, l_scratch_ptr, acc_scratch_ptr, out_ptr,
        B, H_q, SPLIT_K,
        D: tl.constexpr,
    ):
        # One program per (batch, query head). Merge SPLIT_K partial
        # (m_local, l_local, acc_local) into the final attn output via
        # the online-softmax merge formula.
        pid = tl.program_id(0)            # b * H_q + hq
        d = tl.arange(0, D)

        m_g = tl.full((), -float("inf"), tl.float32)
        l_g = tl.zeros((), tl.float32)
        acc_g = tl.zeros((D,), tl.float32)

        for sk in range(0, SPLIT_K):
            ml_off = pid * SPLIT_K + sk
            m_i = tl.load(m_scratch_ptr + ml_off)
            l_i = tl.load(l_scratch_ptr + ml_off)
            acc_i = tl.load(acc_scratch_ptr + ml_off * D + d)
            m_new = tl.maximum(m_g, m_i)
            alpha_g = tl.exp(m_g - m_new)
            alpha_i = tl.exp(m_i - m_new)
            l_g = l_g * alpha_g + l_i * alpha_i
            acc_g = acc_g * alpha_g + acc_i * alpha_i
            m_g = m_new

        out = acc_g / l_g
        tl.store(out_ptr + pid * D + d, out.to(tl.float16))


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
    split_k: Optional[int] = None,
) -> "torch.Tensor":
    """Launch the 6c.2 fused protected-K INT4 decode-attention kernel
    (split-K + tl.dot + GQA-grouped). Same signature as the v1 wrapper —
    drop-in replacement.

    Shapes (all contiguous, on CUDA) — see KERNEL_6C_BLUEPRINT.md §3.
    ``split_k`` defaults to an adaptive value (~512 tokens per split,
    capped at 64); pass an int to override.
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

    G = H_q // H_kv
    # G_PAD = the M-dim of the matmuls. Minimum 16 to engage tensor
    # cores reliably; max with next-pow2(G) for groups bigger than 16.
    G_PAD = max(16, _next_pow2(G))

    if split_k is None:
        # Adaptive: ~512 tokens per split, capped at 64. Goal — SM
        # occupancy on common shapes without runaway per-program work.
        split_k = max(1, min(64, (S_kv + 511) // 512))
    chunk_size = (S_kv + split_k - 1) // split_k

    if softmax_scale is None:
        softmax_scale = 1.0 / math.sqrt(D)

    # Symmetric mode: kernel still needs valid offset pointers — pass
    # zero tensors; the ASYMMETRIC constexpr compiles the add out.
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

    # FP32 scratch for per-split (m, l, acc); FP16 final output.
    m_scratch = torch.empty((B, H_q, split_k), dtype=torch.float32, device=q.device)
    l_scratch = torch.empty((B, H_q, split_k), dtype=torch.float32, device=q.device)
    acc_scratch = torch.empty(
        (B, H_q, split_k, D), dtype=torch.float32, device=q.device,
    )
    out = torch.empty((B, H_q, D), dtype=torch.float16, device=q.device)

    # Pass 1: split-K fused decode. One program per (b, hkv, split).
    grid1 = (B * H_kv, split_k)
    _fused_protected_k_decode_attn_splitk_kernel[grid1](
        q, k_packed, k_scale, k_offset, k_fp16,
        protect_mask, v_packed, v_scale, v_offset,
        m_scratch, l_scratch, acc_scratch,
        B, H_q, H_kv, S_kv, n_grp_k, n_grp_v,
        split_k, chunk_size,
        softmax_scale,
        G=G, G_PAD=G_PAD, D=D, DH=DH,
        GS_k=group_size_k, GS_v=group_size_v,
        BLOCK_N=block_n, ASYMMETRIC=bool(asymmetric),
    )

    # Pass 2: combine the splits per (b, hq).
    grid2 = (B * H_q,)
    _combine_splits_kernel[grid2](
        m_scratch, l_scratch, acc_scratch, out,
        B, H_q, split_k,
        D=D,
    )
    return out
