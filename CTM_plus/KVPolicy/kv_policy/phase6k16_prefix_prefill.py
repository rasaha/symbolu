"""Phase 6K.16 Tier 1 — dequant-context prefill for prefix caching (APC).

THE GAP THIS CLOSES (see PHASE6K16_PREFIX_CACHING_PLAN.md): with
``enable_prefix_caching=True`` a cache-hit prefill arrives with
``context_lens > 0`` — the cached prefix lives ONLY as int4-packed nibbles
in vLLM's paged cache + the writer's sidecars. Stock vLLM's prefix branch
passes the paged cache straight to ``flash_attn_varlen_func`` (sound for
bf16 caches, garbage for packed). This module rebuilds the context in bf16
on the host side and calls PLAIN varlen with explicit K/V — no kernel work.

WHY THE STORAGE INVERTS EXACTLY (the design locks that make this small):
  * K quant is block-local: ``group_size == block_size == BS == 32`` — a
    full cached block is exactly one K quant group, so
    ``k = q * k_scale_ext[blk,h,d] + k_xmin_ext[blk,h,d]`` needs nothing
    outside the block.
  * Protect channels are stored EXACTLY (bf16) in
    ``k_protect_ext[blk,pos,h,slot]``; scatter-merge restores them
    bit-perfect (the whole point of protect survives APC).
  * V is per-token per-group: ``v = q * v_scale_ext[blk,pos,h,g] + v_xmin``.
  * APC shares only FULL blocks => ``ctx_len % BS == 0`` => no partial-
    group reconstruction, and the writer's slot_mapping-derived scatter
    keeps all absolute positions correct with NO SeqState offset surgery
    (Gap 2 of the plan collapsed on inspection — see PLAN doc update).

SAFETY RAILS (enforced here):
  * ``ctx_len % BS == 0`` asserted per sequence (vLLM V0 guarantees it).
  * Legacy bf16-backing mode (``PHASE6C_BF16_BACKING_SKIP=0``) is REFUSED:
    its pool writes index by ``seq_pos`` (suffix-relative), which is wrong
    under APC. Default skip mode has no backing at all.

STATUS: CPU-selftested against a replica of the writer's exact quant math
(``--selftest``). GPU validation gates: ``Bench/scripts/phase6k16_prefix_gates.py``.
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore


# --------------------------------------------------------------------------- #
# Pure dequant pieces (mirror of phase5b_4c_paged_writer's quantizers).
# --------------------------------------------------------------------------- #

def unpack_nibbles(packed: "torch.Tensor") -> "torch.Tensor":
    """(..., D/2) uint8 -> (..., D) uint8. Even d = low nibble of byte
    d//2, odd d = high nibble — the writer's packing convention."""
    low = packed & 0x0F
    high = (packed >> 4) & 0x0F
    out = torch.stack((low, high), dim=-1)          # (..., D/2, 2)
    return out.view(*packed.shape[:-1], packed.shape[-1] * 2)


def dequant_k_blocks(
    packed_k: "torch.Tensor",          # (n_blk, BS, H, D/2) uint8
    k_scale: "torch.Tensor",           # (n_blk, H, D)
    k_xmin: "torch.Tensor",            # (n_blk, H, D)
    k_protect: "torch.Tensor",         # (n_blk, BS, H, n_protect) VALUES
    protected_d_per_head: "torch.Tensor",  # (H, n_protect) long
) -> "torch.Tensor":
    """Reconstruct bf16-equivalent K for full cached blocks.
    Returns (n_blk, BS, H, D) float32 (caller casts).

    ``k_protect`` must hold protect VALUES (bf16/float). Under prot-int8
    (Phase 6N) the sidecar stores uint8 codes — the caller dequantizes
    first (writer._protect_view_bf16); scattering raw codes would be
    silent corruption, so refuse them loudly here.
    """
    if k_protect.dtype == torch.uint8:
        raise RuntimeError(
            "dequant_k_blocks received raw prot-int8 codes (uint8); the "
            "caller must dequantize first (writer._protect_view_bf16)."
        )
    q = unpack_nibbles(packed_k).float()                       # (n_blk, BS, H, D)
    k = q * k_scale.float().unsqueeze(1) + k_xmin.float().unsqueeze(1)
    # Protect merge: protected channels carry their stored values (exact
    # bf16 by default; int8-roundtripped under prot-int8).
    n_blk, BS, H, _ = q.shape
    idx = protected_d_per_head.long().view(1, 1, H, -1).expand(n_blk, BS, H, -1)
    k.scatter_(-1, idx, k_protect.float())
    return k


def dequant_v_blocks(
    packed_v: "torch.Tensor",          # (n_blk, BS, H, D/2) uint8
    v_scale: "torch.Tensor",           # (n_blk, BS, H, n_groups)
    v_xmin: "torch.Tensor",            # (n_blk, BS, H, n_groups)
    v_group_size: int,
) -> "torch.Tensor":
    """Reconstruct V for full cached blocks. (n_blk, BS, H, D) float32."""
    q = unpack_nibbles(packed_v).float()                       # (n_blk, BS, H, D)
    n_blk, BS, H, D = q.shape
    n_groups = D // v_group_size
    qg = q.view(n_blk, BS, H, n_groups, v_group_size)
    v = qg * v_scale.float().unsqueeze(-1) + v_xmin.float().unsqueeze(-1)
    return v.view(n_blk, BS, H, D)


def gather_context_kv(
    kv_cache: "torch.Tensor",          # (2, NB, BS, H, D) uint8
    writer: Any,                       # PagedKVWriter (this layer's)
    block_table_row: "torch.Tensor",   # (max_blocks,) int — this seq's row
    ctx_len: int,
    out_dtype: "torch.dtype",
) -> Tuple["torch.Tensor", "torch.Tensor"]:
    """Dequantize one sequence's cached context. Returns K_ctx, V_ctx of
    shape (ctx_len, H, D) in ``out_dtype``."""
    BS = writer.BS
    if ctx_len % BS != 0:
        raise RuntimeError(
            f"prefix context_len={ctx_len} is not a multiple of "
            f"block_size={BS}; vLLM V0 APC shares only full blocks, so "
            f"this indicates a metadata bug or an unsupported scheduler "
            f"path (chunked prefill?)."
        )
    n_blk = ctx_len // BS
    blocks = block_table_row[:n_blk].long()
    half_D = writer.D // 2

    packed_k = kv_cache[0, blocks, :, :, :half_D]              # (n_blk, BS, H, D/2)
    packed_v = kv_cache[1, blocks, :, :, :half_D]
    # Phase 6N: under prot-int8 the protect sidecar holds uint8 codes —
    # dequant to values before the scatter-merge. getattr keeps older /
    # minimal writer stand-ins (no 6N surface) on the raw-bf16 path.
    k_prot = writer.k_protect_ext[blocks]
    _prot_dq = getattr(writer, "_protect_view_bf16", None)
    if _prot_dq is not None:
        k_prot = _prot_dq(k_prot)
    k = dequant_k_blocks(
        packed_k,
        writer.k_scale_ext[blocks],
        writer.k_xmin_ext[blocks],
        k_prot,
        writer.protected_d_per_head,
    )
    v = dequant_v_blocks(
        packed_v,
        writer.v_scale_ext[blocks],
        writer.v_xmin_ext[blocks],
        writer.v_group_size,
    )
    H, D = writer.H, writer.D
    return (k.view(n_blk * BS, H, D).to(out_dtype),
            v.view(n_blk * BS, H, D).to(out_dtype))


def build_prefix_varlen_inputs(
    new_k: "torch.Tensor",             # (sum_q, H, D) — suffix K, all seqs
    new_v: "torch.Tensor",
    ctx_kv: List[Tuple[Optional["torch.Tensor"], Optional["torch.Tensor"]]],
    query_start_loc: "torch.Tensor",   # (B+1,) cumulative NEW-token offsets
) -> Tuple["torch.Tensor", "torch.Tensor", "torch.Tensor", int]:
    """Interleave [ctx_i || new_i] per sequence into one varlen K/V.

    ``ctx_kv[i]`` is (K_ctx, V_ctx) or (None, None) for cache-miss seqs.
    Returns (k_full, v_full, cu_seqlens_k int32, max_seqlen_k).
    Pure torch — CPU-testable.
    """
    qsl = query_start_loc.long().tolist()
    B = len(qsl) - 1
    if len(ctx_kv) != B:
        raise ValueError(f"ctx_kv has {len(ctx_kv)} entries, expected B={B}")
    k_parts, v_parts, lens = [], [], []
    for i in range(B):
        s, e = qsl[i], qsl[i + 1]
        k_ctx, v_ctx = ctx_kv[i]
        n_ctx = 0 if k_ctx is None else k_ctx.shape[0]
        if n_ctx:
            k_parts.append(k_ctx)
            v_parts.append(v_ctx)
        k_parts.append(new_k[s:e])
        v_parts.append(new_v[s:e])
        lens.append(n_ctx + (e - s))
    k_full = torch.cat(k_parts, dim=0).contiguous()
    v_full = torch.cat(v_parts, dim=0).contiguous()
    cu = torch.zeros(B + 1, dtype=torch.int32, device=new_k.device)
    cu[1:] = torch.cumsum(
        torch.tensor(lens, dtype=torch.int32, device=new_k.device), dim=0)
    return k_full, v_full, cu, max(lens) if lens else 0


def check_writer_apc_compatible(writer: Any) -> None:
    """Refuse configurations whose bookkeeping is suffix-relative."""
    if not getattr(writer, "_bf16_backing_skipped", True):
        raise RuntimeError(
            "prefix caching requires the Phase 6C backing-skip mode "
            "(PHASE6C_BF16_BACKING_SKIP=1, the default): the legacy bf16 "
            "backing pool indexes by seq_pos, which is suffix-relative "
            "under APC and would corrupt the backing for cache-hit "
            "sequences."
        )


def run_prefix_prefill(
    *,
    query: "torch.Tensor",
    new_key: "torch.Tensor",
    new_value: "torch.Tensor",
    kv_cache: "torch.Tensor",
    writer: Any,
    prefill_meta: Any,
    flash_attn_varlen_func: Any,
    softmax_scale: float,
    window_size: Any,
    alibi_slopes: Any,
    logits_soft_cap: Any,
    out: "torch.Tensor",
    fa_version: Any,
) -> None:
    """Orchestrate the dequant-context varlen prefill for one layer.

    Replaces the unsound ``flash_attn_varlen_func(q, key_cache, value_cache,
    block_table=...)`` call: K/V context is dequantized to ``query.dtype``
    and passed EXPLICITLY (no block_table), with the same bottom-right-
    aligned causal semantics the stock prefix path relies on.
    """
    check_writer_apc_compatible(writer)
    if not writer._allocated:
        # First-ever forward can't have cached context; but be safe.
        writer._lazy_alloc(kv_cache)

    ctx_lens = prefill_meta.context_lens_tensor
    if ctx_lens is None:
        raise RuntimeError("prefix prefill without context_lens_tensor")
    ctx_list = ctx_lens.long().tolist()
    bt = prefill_meta.block_tables

    import os as _os
    _debug = _os.environ.get("INT4_PROTECTED_PREFIX_DEBUG", "").strip() in (
        "1", "true", "yes")

    ctx_kv: List[Tuple[Optional["torch.Tensor"], Optional["torch.Tensor"]]] = []
    for i, c in enumerate(ctx_list):
        if c <= 0:
            ctx_kv.append((None, None))
        else:
            ctx_kv.append(gather_context_kv(
                kv_cache, writer, bt[i], int(c), query.dtype))
            if _debug:
                # Triage prints (first hit seq is usually enough; cheap and
                # env-gated). Scales ~1e-8 ==> ctx blocks were NEVER
                # finalized by the writer (cache content is not what we
                # think); sane scales + sane norms ==> suspect the varlen
                # call itself.
                blk0 = int(bt[i][0].item())
                s = writer.k_scale_ext[blk0].float()
                kc, vc = ctx_kv[-1]
                print(f"[p6k16-dbg] seq{i}: ctx={c} blocks={bt[i][:max(1, int(c)//writer.BS)].tolist()} "
                      f"k_scale[blk{blk0}] mean={s.mean().item():.3e} "
                      f"min={s.min().item():.3e} max={s.max().item():.3e} | "
                      f"|K_ctx|={kc.float().norm().item():.1f} "
                      f"|V_ctx|={vc.float().norm().item():.1f}", flush=True)

    k_full, v_full, cu_k, max_k = build_prefix_varlen_inputs(
        new_key, new_value, ctx_kv, prefill_meta.query_start_loc)

    if _debug:
        qsl = prefill_meta.query_start_loc.tolist()
        print(f"[p6k16-dbg] B={len(ctx_list)} ctx={ctx_list} "
              f"cu_q={qsl[:8]} cu_k={cu_k.tolist()[:8]} "
              f"max_q={prefill_meta.max_query_len} max_k={max_k} "
              f"q={tuple(query.shape)} k_full={tuple(k_full.shape)} "
              f"|new_k|={new_key.float().norm().item():.1f}", flush=True)

    flash_attn_varlen_func(
        q=query,
        k=k_full,
        v=v_full,
        cu_seqlens_q=prefill_meta.query_start_loc,
        cu_seqlens_k=cu_k,
        max_seqlen_q=prefill_meta.max_query_len,
        max_seqlen_k=max_k,
        softmax_scale=softmax_scale,
        causal=True,
        window_size=window_size,
        alibi_slopes=alibi_slopes,
        softcap=logits_soft_cap,
        out=out,
        fa_version=fa_version,
    )


# --------------------------------------------------------------------------- #
# CPU selftest — quantize with a REPLICA of the writer's exact math, then
# dequantize with the helpers above and assert reconstruction properties.
# --------------------------------------------------------------------------- #

_ASYM_DIV = 15.0      # mirror of phase5b_4c_paged_writer
_SCALE_CLAMP = 1e-8


def _writer_module():
    """The paged-writer module (Phase 6N prot-int8 helpers live there —
    single source of truth for the quant math). Package import first;
    sibling import covers running this file as a script (selftest)."""
    try:
        from kv_policy import phase5b_4c_paged_writer as pw
    except ImportError:                                # pragma: no cover
        import phase5b_4c_paged_writer as pw           # type: ignore
    return pw


def _ref_quant_k_block(k_block, protected_d):                   # (BS,H,D)
    f = k_block.float()
    x_max, x_min = f.amax(dim=0), f.amin(dim=0)                 # (H,D)
    scale = ((x_max - x_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)
    q = ((f - x_min) / scale).round().clamp(0, 15).to(torch.uint8)
    packed = (q[..., 0::2] & 0x0F) | ((q[..., 1::2] & 0x0F) << 4)
    protect = torch.gather(
        k_block, -1,
        protected_d.view(1, *protected_d.shape).expand(k_block.shape[0], -1, -1))
    return packed, scale, x_min, protect


def _ref_quant_v_block(v_block, G):                              # (BS,H,D)
    BS, H, D = v_block.shape
    g = v_block.float().view(BS, H, D // G, G)
    v_max, v_min = g.amax(dim=-1), g.amin(dim=-1)
    scale = ((v_max - v_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)
    q = ((g - v_min.unsqueeze(-1)) / scale.unsqueeze(-1)).round().clamp(0, 15)
    q = q.to(torch.uint8).view(BS, H, D)
    packed = (q[..., 0::2] & 0x0F) | ((q[..., 1::2] & 0x0F) << 4)
    return packed, scale, v_min


class _FakeWriter:
    """Minimal stand-in exposing the attrs gather_context_kv uses.

    ``prot_minmax=(k_min, k_max)`` (each (H, D)) switches the protect
    sidecar to Phase 6N prot-int8 mode: uint8 codes + the writer module's
    exact quant/dequant helpers (single source of truth for the math).
    """

    def __init__(self, NB, BS, H, D, n_protect, G, device="cpu",
                 prot_minmax=None):
        self.NB, self.BS, self.H, self.D = NB, BS, H, D
        self.v_group_size = G
        self.n_protect = n_protect
        self._allocated = True
        self._bf16_backing_skipped = True
        dt = torch.bfloat16
        self.k_scale_ext = torch.zeros((NB, H, D), dtype=dt)
        self.k_xmin_ext = torch.zeros((NB, H, D), dtype=dt)
        self.v_scale_ext = torch.zeros((NB, BS, H, D // G), dtype=dt)
        self.v_xmin_ext = torch.zeros((NB, BS, H, D // G), dtype=dt)
        self.protected_d_per_head = torch.stack(
            [torch.randperm(D)[:n_protect].sort().values for _ in range(H)])
        self._prot_int8_active = prot_minmax is not None
        if self._prot_int8_active:
            pw = _writer_module()
            k_min, k_max = prot_minmax
            self._prot_qmin, self._prot_qscale = pw.prot_int8_constants(
                torch.gather(k_min.float(), 1, self.protected_d_per_head),
                torch.gather(k_max.float(), 1, self.protected_d_per_head))
            self.k_protect_ext = torch.zeros(
                (NB, BS, H, n_protect), dtype=torch.uint8)
        else:
            self.k_protect_ext = torch.zeros((NB, BS, H, n_protect), dtype=dt)

    def _protect_store(self, k_protect):
        if not self._prot_int8_active:
            return k_protect
        return _writer_module().prot_int8_quantize(
            k_protect, self._prot_qmin, self._prot_qscale)

    def _protect_view_bf16(self, raw):
        if not self._prot_int8_active:
            return raw
        return _writer_module().prot_int8_dequantize(
            raw, self._prot_qmin, self._prot_qscale, torch.bfloat16)


def selftest() -> int:
    if torch is None:
        print("FAIL: selftest requires torch")
        return 1
    torch.manual_seed(0)
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    print("phase6k16_prefix_prefill selftest")
    NB, BS, H, D, n_p, G = 8, 32, 4, 128, 5, 32
    w = _FakeWriter(NB, BS, H, D, n_p, G)
    kv_cache = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8)

    # 1) nibble round-trip is exact.
    q = torch.randint(0, 16, (3, BS, H, D), dtype=torch.uint8)
    packed = (q[..., 0::2] & 0x0F) | ((q[..., 1::2] & 0x0F) << 4)
    check("nibble pack/unpack exact", bool((unpack_nibbles(packed) == q).all()))

    # 2) write 4 blocks with the replica quantizer, dequant, compare.
    ctx_blocks = [2, 5, 6, 1]          # deliberately non-contiguous ids
    k_true = torch.randn(len(ctx_blocks) * BS, H, D, dtype=torch.bfloat16) * 3
    v_true = torch.randn(len(ctx_blocks) * BS, H, D, dtype=torch.bfloat16)
    ks_f32, kx_f32 = [], []
    for j, b in enumerate(ctx_blocks):
        kb = k_true[j * BS:(j + 1) * BS]
        vb = v_true[j * BS:(j + 1) * BS]
        pk, ks, kx, kp = _ref_quant_k_block(kb, w.protected_d_per_head)
        pv, vs, vx = _ref_quant_v_block(vb, G)
        kv_cache[0, b, :, :, :D // 2] = pk
        kv_cache[1, b, :, :, :D // 2] = pv
        w.k_scale_ext[b] = ks.to(torch.bfloat16)
        w.k_xmin_ext[b] = kx.to(torch.bfloat16)
        w.k_protect_ext[b] = kp
        w.v_scale_ext[b] = vs.to(torch.bfloat16)
        w.v_xmin_ext[b] = vx.to(torch.bfloat16)
        ks_f32.append(ks)
        kx_f32.append(kx)

    bt_row = torch.tensor(ctx_blocks + [0] * 4, dtype=torch.int32)
    ctx_len = len(ctx_blocks) * BS
    k_dq, v_dq = gather_context_kv(kv_cache, w, bt_row, ctx_len, torch.bfloat16)
    check("context shapes", k_dq.shape == (ctx_len, H, D) and v_dq.shape == (ctx_len, H, D))

    # K reconstruction bound, term by term (writer stores scale/xmin in
    # BF16, so the bound is NOT just scale/2):
    #   |err| <= scale_f32/2                (nibble rounding)
    #          + 15 * |scale_bf16-scale_f32| (q up to 15 times scale delta)
    #          + |xmin_bf16-xmin_f32|        (xmin delta)
    #          + bf16 eps of the final cast.
    blocks_l = torch.tensor(ctx_blocks).long()
    s_f32 = torch.stack(ks_f32)                                   # (n_blk, H, D)
    x_f32 = torch.stack(kx_f32)
    s_b = w.k_scale_ext[blocks_l].float()
    x_b = w.k_xmin_ext[blocks_l].float()
    tol_hd = 0.5 * s_f32 + 15.0 * (s_b - s_f32).abs() + (x_b - x_f32).abs()
    tol = tol_hd.unsqueeze(1).expand(-1, BS, -1, -1).reshape(ctx_len, H, D) \
        + 0.005 * k_dq.float().abs() + 1e-3
    k_err = (k_dq.float() - k_true.float()).abs()
    check("K dequant within quant tolerance", bool((k_err <= tol).all()))

    # Protect channels are EXACT (bf16-bit-equal).
    idx = w.protected_d_per_head                                  # (H, n_p)
    k_dq_p = torch.gather(k_dq.view(ctx_len, H, D), -1,
                          idx.view(1, H, n_p).expand(ctx_len, -1, -1))
    k_tr_p = torch.gather(k_true.view(ctx_len, H, D), -1,
                          idx.view(1, H, n_p).expand(ctx_len, -1, -1))
    check("protect channels EXACT", bool((k_dq_p == k_tr_p).all()))

    # V reconstruction within per-group tolerance.
    vs_full = w.v_scale_ext[torch.tensor(ctx_blocks).long()].float() \
        .reshape(ctx_len, H, D // G)
    v_err = (v_dq.float() - v_true.float()).abs().view(ctx_len, H, D // G, G)
    v_tol = vs_full.unsqueeze(-1) * 0.5 + 0.05 * v_true.float().abs().view(
        ctx_len, H, D // G, G) + 1e-2
    check("V dequant within quant tolerance", bool((v_err <= v_tol).all()))

    # 3) varlen assembly: B=3, ctx lens (2 blocks, 0, 1 block).
    new_lens = [7, 5, 9]
    qsl = torch.tensor([0, 7, 12, 21], dtype=torch.int32)
    new_k = torch.randn(sum(new_lens), H, D, dtype=torch.bfloat16)
    new_v = torch.randn(sum(new_lens), H, D, dtype=torch.bfloat16)
    c0 = (k_dq[:2 * BS], v_dq[:2 * BS])
    c2 = (k_dq[2 * BS:3 * BS], v_dq[2 * BS:3 * BS])
    k_full, v_full, cu_k, max_k = build_prefix_varlen_inputs(
        new_k, new_v, [c0, (None, None), c2], qsl)
    exp_lens = [2 * BS + 7, 5, BS + 9]
    check("cu_seqlens_k cumulative", cu_k.tolist() == [0] + list(
        torch.cumsum(torch.tensor(exp_lens), 0).tolist()))
    check("max_seqlen_k", max_k == max(exp_lens))
    check("k_full total", k_full.shape[0] == sum(exp_lens))
    # spot-check interleave: seq0 = [ctx0 || new0]; seq1 starts right after.
    check("seq0 ctx prefix in place", bool((k_full[:2 * BS] == c0[0]).all()))
    check("seq0 new suffix in place",
          bool((k_full[2 * BS:2 * BS + 7] == new_k[:7]).all()))
    check("seq1 (no ctx) in place",
          bool((k_full[exp_lens[0]:exp_lens[0] + 5] == new_k[7:12]).all()))

    # 4) rails: non-block-aligned ctx refused; legacy backing refused.
    try:
        gather_context_kv(kv_cache, w, bt_row, ctx_len - 3, torch.bfloat16)
        check("non-aligned ctx refused", False)
    except RuntimeError:
        check("non-aligned ctx refused", True)
    w._bf16_backing_skipped = False
    try:
        check_writer_apc_compatible(w)
        check("legacy backing refused", False)
    except RuntimeError:
        check("legacy backing refused", True)
    w._bf16_backing_skipped = True

    # 5) Phase 6N prot-int8: same blocks, protect sidecar at uint8 codes.
    k_min = k_true.float().amin(dim=0)                 # (H, D) same-corpus
    k_max = k_true.float().amax(dim=0)
    w8 = _FakeWriter(NB, BS, H, D, n_p, G, prot_minmax=(k_min, k_max))
    w8.protected_d_per_head = w.protected_d_per_head   # same channels
    pw = _writer_module()
    w8._prot_qmin, w8._prot_qscale = pw.prot_int8_constants(
        torch.gather(k_min, 1, w8.protected_d_per_head),
        torch.gather(k_max, 1, w8.protected_d_per_head))
    for j, b in enumerate(ctx_blocks):
        kb = k_true[j * BS:(j + 1) * BS]
        vb = v_true[j * BS:(j + 1) * BS]
        pk, ks, kx, kp = _ref_quant_k_block(kb, w8.protected_d_per_head)
        pv, vs, vx = _ref_quant_v_block(vb, G)
        kv_cache[0, b, :, :, :D // 2] = pk
        kv_cache[1, b, :, :, :D // 2] = pv
        w8.k_scale_ext[b] = ks.to(torch.bfloat16)
        w8.k_xmin_ext[b] = kx.to(torch.bfloat16)
        w8.k_protect_ext[b] = w8._protect_store(kp)    # uint8 codes
        w8.v_scale_ext[b] = vs.to(torch.bfloat16)
        w8.v_xmin_ext[b] = vx.to(torch.bfloat16)
    check("prot-int8 sidecar is uint8 (half bytes)",
          w8.k_protect_ext.dtype == torch.uint8
          and w8.k_protect_ext.element_size() == 1)
    k_dq8, _ = gather_context_kv(kv_cache, w8, bt_row, ctx_len, torch.bfloat16)
    k_dq8_p = torch.gather(k_dq8.view(ctx_len, H, D), -1,
                           idx.view(1, H, n_p).expand(ctx_len, -1, -1))
    # Protected channels: no longer bit-exact, but within the static-
    # scale int8 step (scale/2 rounding + bf16 cast of the dequant).
    tol8 = (w8._prot_qscale * 0.5).view(1, H, n_p) \
        + 0.01 * k_tr_p.float().abs() + 1e-3
    err8 = (k_dq8_p.float() - k_tr_p.float()).abs()
    check("prot-int8 protect within scale/2 of true",
          bool((err8 <= tol8).all()))
    # And EXACTLY equal to the explicit dequant of the stored codes —
    # the read path adds no extra error beyond the quantizer itself.
    codes = torch.stack([w8.k_protect_ext[b] for b in ctx_blocks])
    expect = w8._protect_view_bf16(codes).view(ctx_len, H, n_p)
    check("prot-int8 read == dequant(stored codes) bit-exact",
          bool((k_dq8_p == expect).all()))
    # Rail: raw codes refused by dequant_k_blocks.
    try:
        dequant_k_blocks(
            kv_cache[0, blocks_l, :, :, :D // 2],
            w8.k_scale_ext[blocks_l], w8.k_xmin_ext[blocks_l],
            w8.k_protect_ext[blocks_l], w8.protected_d_per_head)
        check("raw uint8 codes refused", False)
    except RuntimeError:
        check("raw uint8 codes refused", True)

    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
