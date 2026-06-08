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
        m_scratch_ptr, l_scratch_ptr, acc_scratch_ptr, gather_ptr,
        B, H_q, H_kv, S_kv, N_active, n_grp_k, n_grp_v,
        SPLIT_K, chunk_size,
        softmax_scale,
        G: tl.constexpr, G_PAD: tl.constexpr,
        D: tl.constexpr, DH: tl.constexpr,
        GS_k: tl.constexpr, GS_v: tl.constexpr,
        BLOCK_N: tl.constexpr, ASYMMETRIC: tl.constexpr,
        USE_GATHER: tl.constexpr,
    ):
        # One program per (batch, KV head, split). The G query heads
        # sharing this KV head are handled as the M dim of the matmuls.
        #
        # READ-SKIP Step 2 (USE_GATHER): the split iterates LOGICAL positions
        # [0, N_active); each logical position's PHYSICAL buffer row is looked up
        # from gather_ptr (the retained KV positions), so K/V are read in place
        # from the FULL cache buffers — no host index_select, no permute-copy. The
        # packed/fp16 buffers are then in NATIVE (S, H, *) layout (not permuted);
        # scales are native in BOTH paths. When USE_GATHER is False this compiles
        # to the original permuted-buffer path, byte-for-byte.
        pid_bh = tl.program_id(0)
        pid_sk = tl.program_id(1)
        b = pid_bh // H_kv
        hkv = pid_bh % H_kv

        # KV range owned by this split — over LOGICAL positions (== physical when
        # not gathering, since N_active == S_kv then).
        s_start = pid_sk * chunk_size
        s_end = tl.minimum(s_start + chunk_size, N_active)

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
            s = s_start + t * BLOCK_N + tl.arange(0, BLOCK_N)   # LOGICAL positions
            valid = s < s_end
            # Physical buffer row: gathered from the retained-position index when
            # skipping, else identity. Drives buffer offsets; `valid` stays logical.
            if USE_GATHER:
                ps = tl.load(gather_ptr + s, mask=valid, other=0)
            else:
                ps = s

            # ---- K tile: load packed bytes, unpack INT4, dequant ----
            if USE_GATHER:   # FULL buffers, NATIVE (S, H, DH): per-position stride H*DH
                kp_off = ((ps[:, None] * H_kv) + hkv) * DH + byte_col[None, :]
            else:            # compacted buffers, PERMUTED (H, S, DH): per-head stride S*DH
                kp_off = (((b * H_kv + hkv) * S_kv) + ps[:, None]) * DH + byte_col[None, :]
            kbyte = tl.load(k_packed_ptr + kp_off, mask=valid[:, None], other=0).to(tl.int32)
            kiv = (((kbyte >> (4 * is_high[None, :])) & 0xF) - 8).to(tl.float32)
            gk = ps // GS_k                                  # scales are native in both paths
            ks_off = (((b * n_grp_k + gk[:, None]) * H_kv) + hkv) * D + d[None, :]
            k_sc = tl.load(k_scale_ptr + ks_off, mask=valid[:, None], other=1.0).to(tl.float32)
            k_dq = kiv * k_sc
            if ASYMMETRIC:
                k_of = tl.load(k_offset_ptr + ks_off, mask=valid[:, None], other=0.0).to(tl.float32)
                k_dq = k_dq + k_of
            # protected-K overlay
            if USE_GATHER:
                kf_off = ((ps[:, None] * H_kv) + hkv) * D + d[None, :]
            else:
                kf_off = (((b * H_kv + hkv) * S_kv) + ps[:, None]) * D + d[None, :]
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
            if USE_GATHER:   # FULL native (S, H, DH)
                vp_off = ((ps[:, None] * H_kv) + hkv) * DH + byte_col[None, :]
            else:            # compacted permuted (H, S, DH)
                vp_off = (((b * H_kv + hkv) * S_kv) + ps[:, None]) * DH + byte_col[None, :]
            vbyte = tl.load(v_packed_ptr + vp_off, mask=valid[:, None], other=0).to(tl.int32)
            viv = (((vbyte >> (4 * is_high[None, :])) & 0xF) - 8).to(tl.float32)
            gv = d // GS_v
            # v_scale is native (S, H, n_grp_v) in both paths; S_kv == its S dim.
            vs_off = (((b * S_kv + ps[:, None]) * H_kv) + hkv) * n_grp_v + gv[None, :]
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
    # No gather: dummy index ptr, N_active == S_kv, USE_GATHER=False (compiles to
    # the original permuted-buffer path).
    dummy_gather = torch.empty(1, dtype=torch.int32, device=q.device)
    grid1 = (B * H_kv, split_k)
    _fused_protected_k_decode_attn_splitk_kernel[grid1](
        q, k_packed, k_scale, k_offset, k_fp16,
        protect_mask, v_packed, v_scale, v_offset,
        m_scratch, l_scratch, acc_scratch, dummy_gather,
        B, H_q, H_kv, S_kv, S_kv, n_grp_k, n_grp_v,
        split_k, chunk_size,
        softmax_scale,
        G=G, G_PAD=G_PAD, D=D, DH=DH,
        GS_k=group_size_k, GS_v=group_size_v,
        BLOCK_N=block_n, ASYMMETRIC=bool(asymmetric),
        USE_GATHER=False,
    )

    # Pass 2: combine the splits per (b, hq).
    grid2 = (B * H_q,)
    _combine_splits_kernel[grid2](
        m_scratch, l_scratch, acc_scratch, out,
        B, H_q, split_k,
        D=D,
    )
    return out


def fused_protected_k_decode_attention_gather(
    q: "torch.Tensor",
    k_packed: "torch.Tensor",
    k_scale: "torch.Tensor",
    k_offset: "Optional[torch.Tensor]",
    k_fp16: "torch.Tensor",
    protect_mask: "torch.Tensor",
    v_packed: "torch.Tensor",
    v_scale: "torch.Tensor",
    v_offset: "Optional[torch.Tensor]",
    gather_idx: "torch.Tensor",
    *,
    group_size_k: int,
    group_size_v: int,
    asymmetric: bool,
    softmax_scale: Optional[float] = None,
    block_n: int = 64,
    split_k: Optional[int] = None,
) -> "torch.Tensor":
    """READ-SKIP Step 2 — in-kernel gather decode (removes the host gather).

    Same attention as ``fused_protected_k_decode_attention`` over the retained
    positions ``gather_idx``, but the buffers are the cache's FULL, NATIVE,
    per-position buffers — NOT permute-copied and NOT index_select-compacted. The
    kernel reads K/V in place at ``gather_idx[logical]``:

      q        (B, H_q, D) fp16
      k_packed (S, H_kv, D//2) uint8      k_scale  (S, H_kv, D) fp16  (group=1)
      k_offset (S, H_kv, D)/None          k_fp16   (S, H_kv, D) fp16
      v_packed (S, H_kv, D//2) uint8      v_scale  (S, H_kv, n_grp_v) fp16
      v_offset (S, H_kv, n_grp_v)/None    protect_mask (H_kv, D)
      gather_idx (N_active,) int32        — retained KV positions (sorted, < S)

    Output ``(B, H_q, D)`` fp16 — identical to compacting to ``gather_idx`` then
    running the permuted kernel (the addressing equivalence is proven in numpy by
    ``_gather_addressing_selftest``; the attention math is the validated kernel,
    unchanged). ``group_size_k == 1`` (production K config).
    """
    if torch is None:
        raise ImportError("requires PyTorch.")
    if not _HAVE_TRITON:
        raise ImportError("requires Triton (GPU build).")
    if not q.is_cuda:
        raise ValueError("inputs must be on CUDA.")
    if group_size_k != 1:
        raise ValueError("gather decode assumes group_size_k == 1 (per-position K scale).")

    B, H_q, D = q.shape
    S_full, H_kv, DH = k_packed.shape
    assert DH == (D + 1) // 2
    assert H_q % H_kv == 0
    assert protect_mask.shape == (H_kv, D)
    n_grp_k = k_scale.shape[0]            # native (S, H, D): S-dim
    n_grp_v = v_scale.shape[2]            # native (S, H, n_grp_v)

    gather_idx = gather_idx.to(torch.int32).contiguous()
    N_active = int(gather_idx.numel())
    if N_active < 1:
        raise ValueError("gather_idx must be non-empty")

    G = H_q // H_kv
    G_PAD = max(16, _next_pow2(G))
    if split_k is None:
        split_k = max(1, min(64, (N_active + 511) // 512))
    chunk_size = (N_active + split_k - 1) // split_k
    if softmax_scale is None:
        softmax_scale = 1.0 / math.sqrt(D)
    if k_offset is None:
        k_offset = torch.zeros_like(k_scale)
    if v_offset is None:
        v_offset = torch.zeros_like(v_scale)

    for name, t in dict(q=q, k_packed=k_packed, k_scale=k_scale, k_offset=k_offset,
                        k_fp16=k_fp16, protect_mask=protect_mask, v_packed=v_packed,
                        v_scale=v_scale, v_offset=v_offset, gather_idx=gather_idx).items():
        if not t.is_contiguous():
            raise ValueError(f"{name} must be contiguous.")

    m_scratch = torch.empty((B, H_q, split_k), dtype=torch.float32, device=q.device)
    l_scratch = torch.empty((B, H_q, split_k), dtype=torch.float32, device=q.device)
    acc_scratch = torch.empty((B, H_q, split_k, D), dtype=torch.float32, device=q.device)
    out = torch.empty((B, H_q, D), dtype=torch.float16, device=q.device)

    grid1 = (B * H_kv, split_k)
    _fused_protected_k_decode_attn_splitk_kernel[grid1](
        q, k_packed, k_scale, k_offset, k_fp16,
        protect_mask, v_packed, v_scale, v_offset,
        m_scratch, l_scratch, acc_scratch, gather_idx,
        B, H_q, H_kv, S_full, N_active, n_grp_k, n_grp_v,
        split_k, chunk_size,
        softmax_scale,
        G=G, G_PAD=G_PAD, D=D, DH=DH,
        GS_k=group_size_k, GS_v=group_size_v,
        BLOCK_N=block_n, ASYMMETRIC=bool(asymmetric),
        USE_GATHER=True,
    )
    grid2 = (B * H_q,)
    _combine_splits_kernel[grid2](
        m_scratch, l_scratch, acc_scratch, out, B, H_q, split_k, D=D,
    )
    return out


# =========================================================================== #
# Read-skip STEP 1 — kernel-emitted block scores.
#
# Replaces ProtectedKINT4Cache.block_attention_scores' torch reconstruction
# (unpack_int4 + dequant + protect-overlay + matmul over the WHOLE K, in eager
# torch — the Phase-10 measured bottleneck whose cost grows with context) with a
# single fused Triton pass that reuses the SAME int4-unpack the decode kernel
# uses. The per-block softmax mass is computed block-locally (each block's own
# max + sum-exp) so there is NO online-softmax / split-K state to thread; a tiny
# host combine rescales by the per-head global max and normalises. This block
# decomposition is exactly equal to a direct softmax-then-block-sum (proven in
# numpy by ``_block_scores_selftest`` below), so the kernel is correct by
# construction; the GPU gate is byte-equality of its scores vs the torch path.
# =========================================================================== #

if _HAVE_TRITON:

    @triton.jit
    def _protected_k_block_scores_kernel(
        q_ptr, k_packed_ptr, k_scale_ptr, k_offset_ptr, k_fp16_ptr,
        protect_mask_ptr, blk_sum_ptr, blk_max_ptr,
        H_q, H_kv, S_kv, n_blocks,
        softmax_scale,
        G: tl.constexpr, D: tl.constexpr, DH: tl.constexpr,
        BLOCK: tl.constexpr, ASYMMETRIC: tl.constexpr,
    ):
        # One program per (KV head, read-skip block). B=1 (the cache is single-
        # sequence). Buffers are in the cache's NATIVE (S, H, *) layout — no
        # permute/copy. Emits this block's local (sum_exp, max); the host rescales.
        hkv = tl.program_id(0)
        blk = tl.program_id(1)

        d = tl.arange(0, D)
        byte_col = d // 2
        is_high = d % 2

        # GQA: mean-pool the G query heads sharing this KV head (matches the torch
        # block_attention_scores q_kv = q.view(H_kv, G, D).mean(1)).
        q_kv = tl.zeros((D,), tl.float32)
        for g in range(0, G):
            hq = hkv * G + g
            q_kv += tl.load(q_ptr + hq * D + d).to(tl.float32)
        q_kv = q_kv / G

        pm = tl.load(protect_mask_ptr + hkv * D + d) != 0

        s = blk * BLOCK + tl.arange(0, BLOCK)          # (BLOCK,) positions
        valid = s < S_kv

        # ---- K tile (BLOCK, D): unpack INT4, dequant, protect-overlay. Mirrors
        #      the decode kernel; native (S, H, *) layout; group_size_k == 1. ----
        kp_off = (s[:, None] * H_kv + hkv) * DH + byte_col[None, :]
        kbyte = tl.load(k_packed_ptr + kp_off, mask=valid[:, None], other=0).to(tl.int32)
        kiv = (((kbyte >> (4 * is_high[None, :])) & 0xF) - 8).to(tl.float32)
        sc_off = (s[:, None] * H_kv + hkv) * D + d[None, :]
        k_sc = tl.load(k_scale_ptr + sc_off, mask=valid[:, None], other=1.0).to(tl.float32)
        k_dq = kiv * k_sc
        if ASYMMETRIC:
            k_of = tl.load(k_offset_ptr + sc_off, mask=valid[:, None], other=0.0).to(tl.float32)
            k_dq = k_dq + k_of
        k_f16 = tl.load(k_fp16_ptr + sc_off, mask=valid[:, None], other=0.0).to(tl.float32)
        k_eff = tl.where(pm[None, :], k_f16, k_dq)     # (BLOCK, D)

        # logits = (k_eff · q_kv) / sqrt(D); masked positions -> -inf.
        logits = tl.sum(k_eff * q_kv[None, :], axis=1) * softmax_scale   # (BLOCK,)
        logits = tl.where(valid, logits, -float("inf"))

        m_blk = tl.max(logits, axis=0)                 # block-local max
        # exp(-inf - m) = 0 for masked / empty-block positions.
        s_blk = tl.sum(tl.exp(logits - m_blk), axis=0)

        out_off = hkv * n_blocks + blk
        tl.store(blk_sum_ptr + out_off, s_blk)
        tl.store(blk_max_ptr + out_off, m_blk)


def fused_protected_k_block_scores(
    q: "torch.Tensor",
    k_packed: "torch.Tensor",
    k_scale: "torch.Tensor",
    k_offset: "Optional[torch.Tensor]",
    k_fp16: "torch.Tensor",
    protect_mask: "torch.Tensor",
    *,
    num_kv_heads: int,
    head_dim: int,
    asymmetric: bool,
    block_size: int,
    seq_len: int,
    softmax_scale: Optional[float] = None,
):
    """Kernel-emitted read-skip block scores (Step 1). Inputs are the cache's
    NATIVE single-sequence buffers (no permute):

      q          (H_q, D)            fp16  — the decode query
      k_packed   (S, H_kv, D//2)     uint8
      k_scale    (S, H_kv, D)        fp16  — per-position (group_size_k == 1)
      k_offset   (S, H_kv, D)/None   fp16
      k_fp16     (S, H_kv, D)        fp16  — protected-K overlay
      protect_mask (H_kv, D)         int8/bool

    Returns ``(blk_sum, blk_max)`` each ``(H_kv, n_blocks)`` fp32 — this block's
    local sum-exp and max. Combine on the host with ``combine_block_scores`` to
    get the per-block softmax mass summed over KV heads (the
    ``block_attention_scores`` contract). Single Triton pass; reuses the decode
    kernel's int4 unpack; cost is O(s) read-only, no torch reconstruction.
    """
    if torch is None:
        raise ImportError("fused_protected_k_block_scores requires PyTorch.")
    if not _HAVE_TRITON:
        raise ImportError("fused_protected_k_block_scores requires Triton (GPU build).")
    if not q.is_cuda:
        raise ValueError("inputs must be on CUDA.")
    D = head_dim
    H_kv = num_kv_heads
    H_q = q.shape[-1] // D if q.ndim == 1 else q.numel() // D
    G = H_q // H_kv
    DH = (D + 1) // 2
    n_blocks = (seq_len + block_size - 1) // block_size
    if softmax_scale is None:
        softmax_scale = 1.0 / math.sqrt(D)
    if k_offset is None:
        k_offset = torch.zeros_like(k_scale)

    q2 = q.reshape(-1).contiguous()        # (H_q*D,)
    blk_sum = torch.empty((H_kv, n_blocks), dtype=torch.float32, device=q.device)
    blk_max = torch.empty((H_kv, n_blocks), dtype=torch.float32, device=q.device)
    grid = (H_kv, n_blocks)
    _protected_k_block_scores_kernel[grid](
        q2, k_packed, k_scale, k_offset, k_fp16, protect_mask,
        blk_sum, blk_max,
        H_q, H_kv, seq_len, n_blocks,
        float(softmax_scale),
        G=G, D=D, DH=DH, BLOCK=block_size, ASYMMETRIC=bool(asymmetric),
    )
    return blk_sum, blk_max


def combine_block_scores(blk_sum, blk_max):
    """Host combine for the kernel-emitted block scores: rescale each block's
    local sum-exp by ``exp(block_max - per_head_global_max)``, normalise per KV
    head (so each head's masses sum to 1 — a softmax), then sum over KV heads.
    Equals ``block_attention_scores``' ``softmax(logits).sum(heads)`` per block
    (proven in numpy by ``_block_scores_selftest``). Works on a torch tensor
    (GPU, production) or numpy array (CPU, test) — duck-typed on ``.exp``.

    ``blk_sum``/``blk_max``: ``(H_kv, n_blocks)``. Returns a length-n_blocks list.
    """
    if hasattr(blk_max, "exp"):  # torch
        M = blk_max.max(dim=-1, keepdim=True).values
        w = blk_sum * (blk_max - M).exp()
        Z = w.sum(dim=-1, keepdim=True).clamp_min(1e-20)
        return (w / Z).sum(dim=0).tolist()
    import numpy as _np      # numpy (CPU reference/test)
    M = blk_max.max(axis=-1, keepdims=True)
    w = blk_sum * _np.exp(blk_max - M)
    Z = _np.maximum(w.sum(axis=-1, keepdims=True), 1e-20)
    return (w / Z).sum(axis=0).tolist()


# --------------------------------------------------------------- CPU proof ----

def _block_scores_selftest() -> int:
    """Prove (in numpy, no torch/triton) that the kernel's block-local
    decomposition + host combine equals a DIRECT softmax-then-block-sum — i.e.
    the ``block_attention_scores`` semantic. This is the correctness contract the
    Triton kernel mirrors; the GPU gate is then just byte-eq vs the torch path."""
    import numpy as np
    rng = np.random.default_rng(0)
    for (s, H_kv, G, D, bs) in [(200, 4, 7, 128, 32), (256, 2, 1, 64, 32),
                                (97, 3, 2, 32, 16), (64, 1, 4, 16, 64)]:
        nb = (s + bs - 1) // bs
        H_q = H_kv * G
        q = rng.standard_normal((H_q, D)).astype(np.float32)
        k_eff = rng.standard_normal((s, H_kv, D)).astype(np.float32)
        scale = 1.0 / math.sqrt(D)
        q_kv = q.reshape(H_kv, G, D).mean(1)                       # (H_kv, D)
        logits = np.einsum("hd,shd->hs", q_kv, k_eff) * scale      # (H_kv, s)

        # DIRECT (the block_attention_scores math): softmax over positions per
        # head, sum over heads, sum per block.
        probs = np.exp(logits - logits.max(1, keepdims=True))
        probs = probs / probs.sum(1, keepdims=True)
        pos_mass = probs.sum(0)                                    # (s,)
        direct = np.zeros(nb, np.float64)
        for p in range(s):
            direct[p // bs] += pos_mass[p]

        # KERNEL path: per (head, block) local max + sum-exp, then host combine.
        blk_sum = np.zeros((H_kv, nb), np.float32)
        blk_max = np.full((H_kv, nb), -np.inf, np.float32)
        for h in range(H_kv):
            for blk in range(nb):
                lo, hi = blk * bs, min((blk + 1) * bs, s)
                lg = logits[h, lo:hi]
                m = lg.max()
                blk_max[h, blk] = m
                blk_sum[h, blk] = np.exp(lg - m).sum()
        got = combine_block_scores(blk_sum, blk_max)

        assert np.allclose(got, direct, atol=1e-5), (s, H_kv, G, D, bs,
                                                     np.abs(np.array(got) - direct).max())
        # sanity: a sharp needle concentrates mass in its block.
    # sharp-needle sanity (single head): one position dominates -> its block ~1.0
    s, bs = 320, 32
    lg = np.full((1, s), -10.0, np.float32); lg[0, 137] = 20.0
    bsum = np.zeros((1, s // bs), np.float32); bmax = np.full((1, s // bs), -np.inf, np.float32)
    for blk in range(s // bs):
        seg = lg[0, blk * bs:(blk + 1) * bs]
        bmax[0, blk] = seg.max(); bsum[0, blk] = np.exp(seg - seg.max()).sum()
    sc = combine_block_scores(bsum, bmax)
    assert sc[137 // bs] > 0.99 and sum(sc) - 1.0 < 1e-4, sc
    print("block-scores numpy proof (decomposition == direct softmax): PASS")
    return 0


def _gather_addressing_selftest() -> int:
    """Prove (numpy, no GPU) the Step-2 addressing equivalence: reading the FULL
    NATIVE buffer at physical row ``gather_idx[logical]`` picks the SAME element as
    the old path (index_select to ``gather_idx`` -> permute to (H, N, *)) reads at
    ``logical``. This is the only new risk surface — the native vs permuted offset
    arithmetic the kernel branches on; the attention math is the validated kernel,
    unchanged."""
    import numpy as np
    rng = np.random.default_rng(0)
    # packed/fp16/v_packed buffers: NATIVE (S, H, W). Scales are native in BOTH
    # paths, so only this layout branch needs proving.
    for (S, H, W) in [(50, 4, 64), (33, 2, 8), (128, 3, 16), (200, 4, 128)]:
        buf = rng.integers(0, 255, (S, H, W)).astype(np.int64)        # (S, H, W)
        gather = np.sort(rng.choice(S, size=max(1, S // 3), replace=False)).astype(np.int64)
        N = gather.size
        compact = buf[gather].transpose(1, 0, 2).copy()              # (H, N, W) permuted
        flat_native = buf.reshape(-1)
        flat_perm = compact.reshape(-1)
        for hkv in range(H):
            for logical in range(N):
                ps = int(gather[logical])
                w = int(rng.integers(0, W))
                native = flat_native[(ps * H + hkv) * W + w]          # kernel USE_GATHER offset
                permuted = flat_perm[(hkv * N + logical) * W + w]     # kernel non-gather offset
                assert native == permuted, (S, H, W, hkv, logical, w)
    print("gather addressing (native == permuted-compacted): PASS")
    return 0


if __name__ == "__main__":
    rc = _block_scores_selftest() or _gather_addressing_selftest()
    raise SystemExit(rc)
