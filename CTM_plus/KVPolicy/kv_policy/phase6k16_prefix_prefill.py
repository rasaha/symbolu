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
  * ``ctx_len % BS == 0`` asserted per sequence UNLESS the caller is
    chunked-armed (Phase 6K.18 ``allow_tail``): chunk 2+ of a chunked
    prompt legally ends mid-block; the trailing ``ctx_len % BS`` K rows
    are spliced EXACT (bf16) from that sequence's staging buffer
    (``state.k_stage``) when still staged, or dequantized from the
    finalized boundary block when this step's write completed it. A tail
    block that is NEITHER staged NOR finalized = broken identity chain ->
    loud refusal. See PHASE6K18_CHUNKED_PREFILL_DESIGN.md (D1/D2).
  * Legacy bf16-backing mode (``PHASE6C_BF16_BACKING_SKIP=0``) is REFUSED:
    its pool writes index by ``seq_pos`` (suffix-relative), which is wrong
    under APC. Default skip mode has no backing at all.

STATUS: CPU-selftested against a replica of the writer's exact quant math
(``--selftest``). GPU validation gates: ``Bench/scripts/phase6k16_prefix_gates.py``.
Chunked-prefill pod gates (NOT yet run): PHASE6K18_CHUNKED_PREFILL_DESIGN.md.
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


def _dequant_full_blocks(
    kv_cache: "torch.Tensor",
    writer: Any,
    blocks: "torch.Tensor",            # (n_blk,) long — FINALIZED block ids
) -> Tuple["torch.Tensor", "torch.Tensor"]:
    """Dequantize finalized blocks. Returns K, V (n_blk, BS, H, D) f32."""
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
    return k, v


def gather_context_kv(
    kv_cache: "torch.Tensor",          # (2, NB, BS, H, D) uint8
    writer: Any,                       # PagedKVWriter (this layer's)
    block_table_row: "torch.Tensor",   # (max_blocks,) int — this seq's row
    ctx_len: int,
    out_dtype: "torch.dtype",
    *,
    state: Any = None,                 # this seq's SeqState (rid-resolved)
    allow_tail: bool = False,          # Phase 6K.18: chunked-armed callers
) -> Tuple["torch.Tensor", "torch.Tensor"]:
    """Dequantize one sequence's cached context. Returns K_ctx, V_ctx of
    shape (ctx_len, H, D) in ``out_dtype``.

    Phase 6K.18 (chunked prefill, design D1): ``ctx_len % BS != 0`` is
    legal iff ``allow_tail`` (the caller is chunked-armed) — the trailing
    ``tail = ctx_len % BS`` rows are the part of the BOUNDARY block
    written by prior chunks. The forward() order is write-then-attend, so
    by attention time the current chunk's write has already run and the
    boundary block is in exactly one of two sound states:

      1. STILL STAGED — the current chunk did not complete it: its K rows
         live ONLY in this seq's staging buffer (cache nibbles for the
         block are not yet written). Splice ``state.k_stage[:tail]`` —
         exact bf16, bit-equal to what monolithic attention would see.
      2. FINALIZED — the current chunk completed it (staging moved on):
         cache nibbles + scale/xmin are valid for the whole block.
         Dequantize and slice ``[:tail]`` — quantized, the same bounded
         S3 residual class as the full APC context blocks.

    Neither staged NOR ever-finalized (k_scale still zero-init) means the
    identity chain is broken (the tail rows were staged under a different
    SeqState) — REFUSE loudly; reading the cache there would be silent
    garbage. V and protect tail rows need no staging: both are written
    per token (valid for partial blocks by construction).

    Without ``allow_tail`` a non-aligned ctx_len keeps the 6K.16 refusal
    VERBATIM: under pure APC it indicates a metadata bug, never a legal
    shape.
    """
    BS = writer.BS
    H, D = writer.H, writer.D
    tail = ctx_len % BS
    if tail and not allow_tail:
        raise RuntimeError(
            f"prefix context_len={ctx_len} is not a multiple of "
            f"block_size={BS}; vLLM V0 APC shares only full blocks, so "
            f"this indicates a metadata bug or an unsupported scheduler "
            f"path (chunked prefill?)."
        )
    n_blk = ctx_len // BS

    k_parts: List["torch.Tensor"] = []
    v_parts: List["torch.Tensor"] = []
    if n_blk:
        blocks = block_table_row[:n_blk].long()
        k, v = _dequant_full_blocks(kv_cache, writer, blocks)
        k_parts.append(k.view(n_blk * BS, H, D).to(out_dtype))
        v_parts.append(v.view(n_blk * BS, H, D).to(out_dtype))

    if tail:
        tb = int(block_table_row[n_blk].item())
        tb_t = torch.tensor([tb], dtype=torch.long,
                            device=block_table_row.device)
        # K tail: staged (exact) -> finalized (quantized) -> refuse.
        staged = (
            state is not None
            and getattr(state, "k_stage_block_id", -1) == tb
            and getattr(state, "k_stage_count", 0) >= tail
        )
        if staged:
            k_parts.append(state.k_stage[:tail].to(out_dtype))
        else:
            if not bool((writer.k_scale_ext[tb_t].float() != 0).any()):
                raise RuntimeError(
                    f"int4_protected chunked prefill: boundary block {tb} "
                    f"(ctx_len={ctx_len}, tail={tail}) was never finalized "
                    f"AND is not in this sequence's staging buffer "
                    f"(staged block="
                    f"{getattr(state, 'k_stage_block_id', None)}, count="
                    f"{getattr(state, 'k_stage_count', None)}) — the tail "
                    f"rows were staged under a different SeqState, i.e. "
                    f"the rid identity chain is broken. Refusing rather "
                    f"than reading uninitialized cache (contract C-ID, "
                    f"PHASE6K18_CHUNKED_PREFILL_DESIGN.md D1/D2)."
                )
            k_tail_blk, _ = _dequant_full_blocks(kv_cache, writer, tb_t)
            k_parts.append(k_tail_blk[0, :tail].to(out_dtype))
        # V tail: per-token quant — sidecars are valid for rows < tail
        # regardless of K finalization; dequant the block, slice the tail.
        half_D = D // 2
        v_tail_blk = dequant_v_blocks(
            kv_cache[1, tb_t, :, :, :half_D],
            writer.v_scale_ext[tb_t],
            writer.v_xmin_ext[tb_t],
            writer.v_group_size,
        )
        v_parts.append(v_tail_blk[0, :tail].to(out_dtype))

    if len(k_parts) == 1:
        return k_parts[0], v_parts[0]
    return torch.cat(k_parts, dim=0), torch.cat(v_parts, dim=0)


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
    attn_metadata: Any = None,
) -> None:
    """Orchestrate the dequant-context varlen prefill for one layer.

    Replaces the unsound ``flash_attn_varlen_func(q, key_cache, value_cache,
    block_table=...)`` call: K/V context is dequantized to ``query.dtype``
    and passed EXPLICITLY (no block_table), with the same bottom-right-
    aligned causal semantics the stock prefix path relies on.

    Phase 6K.18: ``attn_metadata`` (the FULL step metadata, not the
    prefill slice) carries the 6B.2 prefill rid stash. It is consulted
    ONLY when a segment's ctx_len is non-block-aligned (a chunk-2+
    boundary) — the staged K tail lives in that seq's SeqState, so per-
    seq identity is REQUIRED there (contract C-ID, extended by 6K.18 D2:
    refuse loudly without the stash). Block-aligned batches (pure APC)
    never touch the stash here — zero behavior change.
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

    # ---- Phase 6K.18 (D1/D2): resolve per-seq SeqStates for tail splices.
    pw = _writer_module()
    tail_idx = [i for i, c in enumerate(ctx_list)
                if c > 0 and int(c) % writer.BS != 0]
    states: List[Any] = [None] * len(ctx_list)
    allow_tail = False
    if tail_idx:
        allow_tail = pw.chunked_active() or pw.allow_chunked_prefill_override()
        # If not chunked-armed, leave allow_tail False: gather_context_kv
        # raises the original 6K.16 alignment rail (a non-aligned ctx
        # under pure APC is a metadata bug, not a legal shape).
        if allow_tail:
            rids = pw.stashed_real_seq_ids(
                attn_metadata, len(ctx_list), prefill=True)
            if rids is None:
                raise RuntimeError(
                    "int4_protected chunked prefill: real-seq-id stash "
                    "unavailable for a %d-segment prefill-with-context "
                    "with non-block-aligned ctx (segments %s) — the staged "
                    "K tail can only be located via stable per-seq "
                    "identity. Construct via Int4ProtectedLLM("
                    "enable_chunked_prefill=True), which installs the 6B.2 "
                    "rid-stash hook (contract C-ID, "
                    "PHASE6K16_APC_CONTRACT.md §3, extended by 6K.18 D2)."
                    % (len(ctx_list), tail_idx[:8]))
            for i in tail_idx:
                st = writer._seq_states.get(rids[i])
                if st is None:
                    raise RuntimeError(
                        "int4_protected chunked prefill: no SeqState for "
                        "rid=%r (segment %d, ctx_len=%d) — chunk 1's write "
                        "must have created it under this rid; the identity "
                        "chain is broken (contract C-ID / 6K.18 D2)."
                        % (rids[i], i, int(ctx_list[i])))
                states[i] = st

    ctx_kv: List[Tuple[Optional["torch.Tensor"], Optional["torch.Tensor"]]] = []
    for i, c in enumerate(ctx_list):
        if c <= 0:
            ctx_kv.append((None, None))
        else:
            ctx_kv.append(gather_context_kv(
                kv_cache, writer, bt[i], int(c), query.dtype,
                state=states[i], allow_tail=allow_tail))
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

    # 6) Phase 6K.18 (D1) — chunked tail splice. Context = 2 full blocks
    #    + a 12-row tail on a boundary block, the three tail states:
    #    staged (exact bf16), finalized (quantized), neither (refused).
    class _FakeState:
        def __init__(self, BS, H, D):
            self.k_stage = torch.zeros((BS, H, D), dtype=torch.bfloat16)
            self.k_stage_block_id = -1
            self.k_stage_count = 0

    TAIL, TB = 12, 4                       # boundary block id 4 (unused above)
    bt_tail = torch.tensor([2, 5, TB, 0, 0, 0, 0, 0], dtype=torch.int32)
    ctx_t = 2 * BS + TAIL
    k_tail_true = torch.randn(BS, H, D, dtype=torch.bfloat16) * 3
    v_tail_true = torch.randn(BS, H, D, dtype=torch.bfloat16)
    # V/protect tail rows are per-token: sidecars valid for rows < TAIL
    # even though K is not finalized. (The replica's V quant is per-token
    # per-group, so writing the full block's V is the same math.)
    pv_t, vs_t, vx_t = _ref_quant_v_block(v_tail_true, G)
    kv_cache[1, TB, :, :, :D // 2] = pv_t
    w.v_scale_ext[TB] = vs_t.to(torch.bfloat16)
    w.v_xmin_ext[TB] = vx_t.to(torch.bfloat16)

    # 6a) STAGED leg: boundary block lives only in this seq's staging.
    st = _FakeState(BS, H, D)
    st.k_stage[:TAIL] = k_tail_true[:TAIL]
    st.k_stage_block_id = TB
    st.k_stage_count = TAIL
    k_c, v_c = gather_context_kv(kv_cache, w, bt_tail, ctx_t,
                                 torch.bfloat16, state=st, allow_tail=True)
    check("tail: shapes (2*BS+tail)", k_c.shape == (ctx_t, H, D)
          and v_c.shape == (ctx_t, H, D))
    check("tail: staged K rows EXACT (bf16 bit-equal)",
          bool((k_c[2 * BS:] == k_tail_true[:TAIL]).all()))
    check("tail: full blocks unchanged by tail path",
          bool((k_c[:2 * BS] == k_dq[:2 * BS]).all()))
    v_err_t = (v_c[2 * BS:].float() - v_tail_true[:TAIL].float()).abs() \
        .view(TAIL, H, D // G, G)
    v_tol_t = vs_t[:TAIL].unsqueeze(-1) * 0.5 \
        + 0.05 * v_tail_true[:TAIL].float().abs().view(TAIL, H, D // G, G) \
        + 1e-2
    check("tail: V rows within per-token quant tolerance",
          bool((v_err_t <= v_tol_t).all()))

    # 6b) pure-tail context (ctx_len < BS — a tiny chunk budget).
    st_small = _FakeState(BS, H, D)
    st_small.k_stage[:7] = k_tail_true[:7]
    st_small.k_stage_block_id = TB
    st_small.k_stage_count = 7
    k_c7, v_c7 = gather_context_kv(
        kv_cache, w, torch.tensor([TB, 0, 0, 0], dtype=torch.int32), 7,
        torch.bfloat16, state=st_small, allow_tail=True)
    check("tail: pure-tail ctx (< BS) exact",
          k_c7.shape == (7, H, D)
          and bool((k_c7 == k_tail_true[:7]).all()))

    # 6c) FINALIZED leg: this step's write completed the boundary block —
    #     staging moved on (count reset / other block); cache is valid.
    pk_t, ks_t, kx_t, kp_t = _ref_quant_k_block(
        k_tail_true, w.protected_d_per_head)
    kv_cache[0, TB, :, :, :D // 2] = pk_t
    w.k_scale_ext[TB] = ks_t.to(torch.bfloat16)
    w.k_xmin_ext[TB] = kx_t.to(torch.bfloat16)
    w.k_protect_ext[TB] = kp_t
    st_done = _FakeState(BS, H, D)
    st_done.k_stage_block_id = TB
    st_done.k_stage_count = 0            # finalize resets the count
    k_cf, _ = gather_context_kv(kv_cache, w, bt_tail, ctx_t,
                                torch.bfloat16, state=st_done,
                                allow_tail=True)
    expect_tail = dequant_k_blocks(
        kv_cache[0, TB:TB + 1, :, :, :D // 2],
        w.k_scale_ext[TB:TB + 1], w.k_xmin_ext[TB:TB + 1],
        w.k_protect_ext[TB:TB + 1], w.protected_d_per_head,
    )[0, :TAIL].to(torch.bfloat16)
    check("tail: finalized-block leg == block dequant (bit-exact)",
          bool((k_cf[2 * BS:] == expect_tail).all()))
    tol_t = (0.5 * ks_t + 1e-3).unsqueeze(0) \
        + 0.01 * k_tail_true[:TAIL].float().abs() + 1e-2
    err_t = (k_cf[2 * BS:].float() - k_tail_true[:TAIL].float()).abs()
    check("tail: finalized leg within quant tolerance of true",
          bool((err_t <= tol_t).all()))
    # state=None (e.g. APC+chunked seq whose stage moved on) also lands
    # on the finalized leg — same result.
    k_cn, _ = gather_context_kv(kv_cache, w, bt_tail, ctx_t,
                                torch.bfloat16, state=None, allow_tail=True)
    check("tail: finalized leg with state=None identical",
          bool((k_cn[2 * BS:] == expect_tail).all()))

    # 6d) NEITHER staged nor finalized -> loud refusal (broken identity).
    NEVER = 7                              # block never written/finalized
    bt_never = torch.tensor([2, 5, NEVER, 0], dtype=torch.int32)
    try:
        gather_context_kv(kv_cache, w, bt_never, ctx_t, torch.bfloat16,
                          state=None, allow_tail=True)
        check("tail: unfinalized+unstaged refused", False)
    except RuntimeError as e:
        check("tail: unfinalized+unstaged refused",
              "never finalized" in str(e))

    # 6e) default callers (allow_tail omitted) keep the 6K.16 rail even
    #     with a staged state present.
    try:
        gather_context_kv(kv_cache, w, bt_tail, ctx_t, torch.bfloat16,
                          state=st)
        check("tail: refused without allow_tail (APC rail verbatim)", False)
    except RuntimeError:
        check("tail: refused without allow_tail (APC rail verbatim)", True)

    # 6f) prot-int8 (6N) interaction: finalized boundary block under
    #     uint8 protect codes — the tail dequant routes through
    #     _protect_view_bf16 like full blocks (no raw codes leak).
    pk8, ks8, kx8, kp8 = _ref_quant_k_block(
        k_tail_true, w8.protected_d_per_head)
    kv_cache[0, TB, :, :, :D // 2] = pk8
    w8.k_scale_ext[TB] = ks8.to(torch.bfloat16)
    w8.k_xmin_ext[TB] = kx8.to(torch.bfloat16)
    w8.k_protect_ext[TB] = w8._protect_store(kp8)
    kv_cache[1, TB, :, :, :D // 2] = pv_t
    w8.v_scale_ext[TB] = vs_t.to(torch.bfloat16)
    w8.v_xmin_ext[TB] = vx_t.to(torch.bfloat16)
    k_c8, _ = gather_context_kv(kv_cache, w8, bt_tail, ctx_t,
                                torch.bfloat16, state=None, allow_tail=True)
    codes_t = w8.k_protect_ext[TB:TB + 1]
    expect_p8 = w8._protect_view_bf16(codes_t)[0, :TAIL]
    got_p8 = torch.gather(
        k_c8[2 * BS:].view(TAIL, H, D), -1,
        w8.protected_d_per_head.view(1, H, n_p).expand(TAIL, -1, -1))
    check("tail: prot-int8 protect == dequant(stored codes) bit-exact",
          bool((got_p8 == expect_p8).all()))

    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
