"""Phase 5B.4c.1 — paged KV writer.

Replaces vLLM's `reshape_and_cache_flash` for the int4_protected backend.

Architecture lock (see KERNEL_6C3C_PHASE5B4C_DESIGN.md):
  - vLLM paged uint8 cache holds ONLY nibbles (first D/2 bytes of each
    128-byte slot per K|V dim).
  - Scale, xmin, K-protect tensors live in EXTERNAL per-layer tensors
    keyed by global block_id.
  - K uses a 16-token staging buffer (= block_size = group_size); quantize
    on group fill.
  - V is quantized per-token along head_dim (v_group_size=32, n_groups=4).

batch=1 v1: one staging buffer per layer. Multi-batch is Phase 5B.5+.

The numerical convention matches Phase 2.4.0 / Phase 2.6.0:
  scale = max((x_max - x_min) / 15.0, 1e-8)
  q     = round((x - x_min) / scale).clamp(0, 15)
  Even d -> low nibble, odd d -> high nibble of byte[d/2].
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore

logger = logging.getLogger(__name__)

# Matches Phase 2.4.0 / Phase 2.6.0 conventions.
_ASYM_DIV    = 15.0
_SCALE_CLAMP = 1e-8

# Default v_group_size from Phase 2.6 design.
_DEFAULT_V_GROUP_SIZE = 32

# Phase 5B.4c.3 fix (a): parallel BF16 K/V backing.
# The packed kernel at small S=128 (n_block_max=1) does not fully
# override the cp.async'd bf16 K/V in smem before the GEMMs consume.
# Bisection cells E_zero (cos=0), E_rand (cos=0.04) vs E_real (cos=1.0)
# proved bf16 backing CONTENT matters at small S. F_zero (S=512) PASSES,
# so the dependence vanishes at larger S — but our Qwen decode runs at
# S ~25-60, exclusively in the broken regime.
# Workaround: writer maintains a per-layer bf16 K/V cache and the impl
# passes the relevant slice to the kernel as positional args. Defeats
# part of the per-token memory savings (~224 MB / model at max_seqlen=
# 4096) but unblocks v1 end-to-end without a kernel rebuild.
_BF16_BACKING_MAX_SEQLEN_ENV = "PHASE5B_4C_BF16_BACKING_MAX_SEQLEN"
_DEFAULT_BF16_BACKING_MAX_SEQLEN = 4096

# Phase 6 v2 Option B pre-flight (B-pre-1): per-(layer) seq state lives
# in fixed-size pool tensors so the read path can gather via a single
# device-indexed op (a slot-int tensor) instead of a Python loop with
# dict lookups. Pool size caps how many sequences can be concurrently
# active on this writer; default 8 matches the current B=8 ship target
# and the existing per-seq lazy-alloc memory cost. Bump via env if
# heavier concurrency is needed.
_MAX_ACTIVE_SLOTS_ENV = "PHASE6_MAX_ACTIVE_SLOTS"
_DEFAULT_MAX_ACTIVE_SLOTS = 8

# Phase 6K.14: slot lifecycle. The B-pre-1 pool gave the writer a fixed
# slot cap but two pieces were never wired:
#   1. The cap defaulted to 8 and was only bumpable via env, so high
#      concurrency (B>=9) hit "slot pool exhausted" before any work ran.
#   2. evict_sequence (which frees a slot) was only called at the prefill
#      boundary / on hard reset — never when a sequence COMPLETES. So slots
#      leaked one-per-distinct-seq_id across decode waves until exhaustion,
#      even when only a few sequences were ever concurrently active.
# Fixed by (1) auto-bumping the cap to vLLM's max_num_seqs when the env is
# unset, and (2) gc_completed_slots(), called each pure-decode step with the
# running set so finished sequences' slots return to the pool.
_AUTOBUMP_SLOTS_ENV = "PHASE6K14_AUTOBUMP_SLOTS"   # 0 -> keep fixed default
_EVICT_ON_DECODE_ENV = "PHASE6K14_EVICT_ON_DECODE"  # 0 -> disable GC (A/B)

# Debug flag to bypass V packing (writer stashes bf16 V in a parallel
# sidecar; read path passes it as v_cache positional). Used to isolate
# V packed-path correctness vs K packed-path correctness.
_BF16_V_ENV = "PHASE5B_4C_BF16_V"

# Phase 6C: skip the full-history bf16 K/V backing pool. The
# int4_packed kernel (Is_int4kv_packed=true) verified to never read
# from bf16_k_batch / bf16_v_batch — it loads int4 directly via
# int4_packed_load_{K,V}_block in flash_fwd_kernel.h. The bf16 backing
# was therefore dead memory + bandwidth. When this flag is set, we
# allocate a tiny (1, 1, H, D) stub pool and skip all writes; the
# read path returns a stride-0 broadcast view of the stub that the
# kernel sees as logical shape (B, S_padded, H, D) at near-zero memory
# cost. Set PHASE6C_BF16_BACKING_SKIP=0 to revert to the legacy
# full-history pool for A/B comparison.
_BF16_BACKING_SKIP_ENV = "PHASE6C_BF16_BACKING_SKIP"
_BF16_BACKING_SKIP_DEFAULT = "1"   # NEW default — skip the pool.

# Phase 6E: switch the writer's per-decode-step captured region from
# the current Python op chain (~30 small CUDA kernel launches per
# layer per step) to a future fused CUDA kernel. While the CUDA
# kernel is under development, PHASE6E_FUSED_WRITER=1 routes through
# the byte-identical Python reference (_phase6e_fused_decode_write_
# python_ref) that defines the contract any CUDA implementation must
# satisfy. Default is 0 (off) until the CUDA kernel is GPU-verified;
# the CPU verifier (verify_phase6e_fused_byte_eq.py) proves the
# Python ref is byte-equivalent to the current inline op chain.
_FUSED_WRITER_ENV     = "PHASE6E_FUSED_WRITER"
_FUSED_WRITER_DEFAULT = "0"   # OFF by default until CUDA kernel ships.


def _bf16_v_mode() -> bool:
    return os.environ.get(_BF16_V_ENV, "").strip() in ("1", "true", "True", "yes")


def _bf16_backing_skip() -> bool:
    """Phase 6C: when True, the writer allocates a tiny stub for the
    bf16 backing pool and skips all writes (kernel doesn't read it).
    Default is True; set PHASE6C_BF16_BACKING_SKIP=0 to opt out.
    """
    raw = os.environ.get(_BF16_BACKING_SKIP_ENV, _BF16_BACKING_SKIP_DEFAULT)
    return raw.strip() in ("1", "true", "True", "yes")


def _fused_writer_enabled() -> bool:
    """Phase 6E: when True, route write_decode_batched's captured
    region through the fused entry point. Returns False until the
    CUDA kernel is GPU-verified."""
    raw = os.environ.get(_FUSED_WRITER_ENV, _FUSED_WRITER_DEFAULT)
    return raw.strip() in ("1", "true", "True", "yes")


# Phase 6E: optional CUDA-only acceleration. When PHASE6E_FUSED_WRITER=1
# AND the int4_protected_C extension is built AND the tensors live on
# CUDA, route through the fused custom CUDA kernels instead of the
# Python op chain. Falls back to the byte-identical Python reference
# silently when the extension is missing or tensors are on CPU.
_FUSED_CUDA_DISABLE_ENV     = "PHASE6E_FUSED_WRITER_DISABLE_CUDA"
_FUSED_CUDA_DISABLE_DEFAULT = "0"

# Module-level cache for the imported extension. Populated lazily on
# first call so import errors don't blow up Python startup.
_int4_protected_C = None       # type: Any
_int4_protected_C_probed = False


def _fused_cuda_disabled() -> bool:
    """When True, force the Python fallback even if the CUDA extension
    is available. Lets the CPU verifier exercise the Python reference
    explicitly without rebuilding."""
    raw = os.environ.get(_FUSED_CUDA_DISABLE_ENV, _FUSED_CUDA_DISABLE_DEFAULT)
    return raw.strip() in ("1", "true", "True", "yes")


def _try_load_int4_protected_C():
    """Import the CUDA extension lazily, exactly once. Returns the
    module or None if it can't be loaded (e.g., extension not built,
    no CUDA runtime).

    IMPORT ORDER: `import torch` MUST come first because the .so
    depends on libc10.so. The caller of this function is in this
    module, which already imports torch at the top, so the order is
    guaranteed.
    """
    global _int4_protected_C, _int4_protected_C_probed
    if _int4_protected_C_probed:
        return _int4_protected_C
    _int4_protected_C_probed = True
    try:
        import int4_protected_C as _mod   # type: ignore
        _int4_protected_C = _mod
    except Exception as exc:               # noqa: BLE001
        logger.debug(
            "Phase 6E CUDA extension not available (%s: %s); "
            "fused writer will use the Python reference.",
            type(exc).__name__, exc,
        )
        _int4_protected_C = None
    return _int4_protected_C



def _bf16_backing_max_seqlen() -> int:
    raw = os.environ.get(_BF16_BACKING_MAX_SEQLEN_ENV, "").strip()
    if not raw:
        return _DEFAULT_BF16_BACKING_MAX_SEQLEN
    try:
        return int(raw)
    except ValueError:
        return _DEFAULT_BF16_BACKING_MAX_SEQLEN


def _autobump_slots_enabled() -> bool:
    """Phase 6K.14: whether to auto-bump the slot cap to vLLM's
    max_num_seqs when $PHASE6_MAX_ACTIVE_SLOTS is unset. Default on."""
    raw = os.environ.get(_AUTOBUMP_SLOTS_ENV, "1").strip().lower()
    return raw not in ("0", "false", "no")


def _evict_on_decode_enabled() -> bool:
    """Phase 6K.14: whether gc_completed_slots actually evicts. Default
    on; set $PHASE6K14_EVICT_ON_DECODE=0 to reproduce the pre-fix leak
    for A/B comparison."""
    raw = os.environ.get(_EVICT_ON_DECODE_ENV, "1").strip().lower()
    return raw not in ("0", "false", "no")


def _vllm_max_num_seqs() -> Optional[int]:
    """Best-effort read of vLLM's scheduler ``max_num_seqs`` — the upper
    bound on concurrently-running sequences, hence the largest decode
    batch and the right slot-pool size.

    Returns None when vLLM isn't importable, no config is active, or the
    value can't be read. Fully guarded so CPU tests (no vLLM) and any
    non-vLLM caller never break.
    """
    if torch is None:
        return None
    try:
        from vllm.config import get_current_vllm_config  # type: ignore
    except Exception:
        return None
    try:
        cfg = get_current_vllm_config()
    except Exception:
        return None
    if cfg is None:
        return None
    try:
        n = int(cfg.scheduler_config.max_num_seqs)
    except Exception:
        return None
    return n if n > 0 else None


def _max_active_slots() -> int:
    """Resolve the active-slot pool cap.

    Precedence (Phase 6K.14):
      1. Explicit $PHASE6_MAX_ACTIVE_SLOTS — always wins (pins the cap,
         disables auto-bump). Saturation/bench runs set this to B.
      2. Auto-bump to vLLM's max_num_seqs (best-effort) when the env is
         unset and $PHASE6K14_AUTOBUMP_SLOTS != 0 — keeps the pool large
         enough for the max concurrent decode batch in production.
      3. Legacy fixed default (8).
    """
    raw = os.environ.get(_MAX_ACTIVE_SLOTS_ENV, "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    if _autobump_slots_enabled():
        auto = _vllm_max_num_seqs()
        if auto is not None and auto > 0:
            return auto
    return _DEFAULT_MAX_ACTIVE_SLOTS


def _leaked_seq_ids(assigned_seq_ids: "Any", active_seq_ids: "Any") -> list:
    """Pure decision helper for gc_completed_slots (torch-free, unit-
    testable on CPU): the seq_ids that currently hold a slot but are
    ABSENT from the active (current pure-decode) set — i.e. completed or
    recompute-preempted, hence safe to evict. Order-preserving over
    ``assigned_seq_ids`` so eviction order is deterministic.
    """
    active = active_seq_ids if isinstance(active_seq_ids, (set, frozenset)) \
        else set(active_seq_ids)
    return [sid for sid in assigned_seq_ids if sid not in active]


def _in_cuda_graph_capture() -> bool:
    """Phase 6B.3 (Option X) — detect whether the current CUDA stream
    is in graph capture. Returns False if CUDA isn't available or
    there is no current stream.

    Capture-safe code paths must skip ALL host syncs (.cpu(), .item(),
    .tolist()) and Python dict lookups when this is True. The captured
    graph records ops as data-flow over device tensors; the host work
    can fire at production-eager runtime instead (via the 6B.2 pre-
    capture hook for captured shapes; or in-line for non-captured
    shapes that fall back to eager).
    """
    if torch is None:
        return False
    try:
        if not torch.cuda.is_available():
            return False
        return bool(torch.cuda.is_current_stream_capturing())
    except (RuntimeError, AssertionError):
        # is_current_stream_capturing can raise on platforms without
        # a current stream (e.g., cold-boot CPU PyTorch).
        return False

# Env var for the per-model protect mask artifact (calibration output
# from Phase 5B.0). Override via PROTECT_MASK_PATH=...
_PROTECT_MASK_ENV = "PROTECT_MASK_PATH"
_PROTECT_MASK_DEFAULT = "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt"


# ----------------------------------------------------------------------
# Protect-mask helpers (mirror PartialGroupQuantizer's setup).
# ----------------------------------------------------------------------

def _build_protect_tables(
    protect_mask: "torch.Tensor",
    n_protect: int,
) -> Tuple["torch.Tensor", "torch.Tensor"]:
    """Build (protect_slot, protected_d_per_head) from a (H, D) int8 mask.

    protect_slot[h, d]      = slot index in [0, n_protect) if protected, else -1.
    protected_d_per_head[h] = (n_protect,) long, sorted ascending d-indices.
    """
    H, D = protect_mask.shape
    device = protect_mask.device
    slot = torch.full((H, D), -1, dtype=torch.int8, device=device)
    protected_d = torch.zeros((H, n_protect), dtype=torch.long, device=device)
    for h in range(H):
        idx = torch.nonzero(protect_mask[h] >= 1, as_tuple=True)[0]
        n_actual = len(idx)
        slot[h, idx] = torch.arange(n_actual, dtype=torch.int8, device=device)
        protected_d[h, :n_actual] = idx
        # If a head has fewer protected channels than n_protect (shouldn't
        # happen with the calibrator but we're defensive), the tail of
        # protected_d[h] stays 0 — those slots remain unused in protect_ext.
    return slot, protected_d


def load_protect_mask_for_layer(layer_idx: int) -> "torch.Tensor":
    """Load the frozen per-model protect-mask artifact and return the
    slice for `layer_idx`. The artifact is shape (num_layers, H_kv, D) int8.

    Supported on-disk formats (Phase 5B.0 calibrator + variants):
      - bare Tensor of shape (num_layers, H_kv, D)
      - dict with key "mask" (Phase 5B.0 default) or "protect_mask"
        holding the same tensor
      - dict keyed by layer index (int or str) → (H_kv, D) tensor each

    Path is taken from $PROTECT_MASK_PATH (default Qwen2.5-7B path).
    """
    path = os.environ.get(_PROTECT_MASK_ENV, _PROTECT_MASK_DEFAULT)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Protect mask artifact not found at '{path}'. Set ${_PROTECT_MASK_ENV} "
            f"or run Phase 5B.0 calibration."
        )
    # weights_only=False because the Phase 5B.0 artifact is a dict with
    # plain Python types (str, int, list) alongside the mask tensor.
    # The file is local + trusted (we wrote it ourselves).
    raw = torch.load(path, map_location="cpu", weights_only=False)

    # Case A: bare tensor (num_layers, H, D).
    if isinstance(raw, torch.Tensor):
        return _slice_mask_for_layer(raw, layer_idx, path)

    # Case B: dict format.
    if isinstance(raw, dict):
        # B1: dict with a 'mask' or 'protect_mask' key.
        for key in ("mask", "protect_mask"):
            v = raw.get(key)
            if isinstance(v, torch.Tensor):
                return _slice_mask_for_layer(v, layer_idx, path)
        # B2: dict keyed by layer index (int or str).
        for k in (layer_idx, str(layer_idx)):
            v = raw.get(k)
            if isinstance(v, torch.Tensor):
                if v.ndim != 2:
                    raise ValueError(
                        f"Per-layer mask at '{path}'[{k!r}] has shape "
                        f"{tuple(v.shape)}; expected (H_kv, D)"
                    )
                return v.to(torch.int8)
        raise TypeError(
            f"Protect mask dict at '{path}' has no 'mask'/'protect_mask' key "
            f"and no entry at {layer_idx}. Keys present: {sorted(raw.keys())[:8]}"
        )

    raise TypeError(
        f"Protect mask artifact at '{path}' is {type(raw).__name__}; expected "
        f"Tensor or dict"
    )


def _slice_mask_for_layer(mask: "torch.Tensor", layer_idx: int, path: str) -> "torch.Tensor":
    if mask.ndim != 3:
        raise ValueError(
            f"Protect mask shape {tuple(mask.shape)} at '{path}' != (num_layers, H_kv, D)"
        )
    num_layers = mask.shape[0]
    if layer_idx < 0 or layer_idx >= num_layers:
        raise IndexError(
            f"layer_idx={layer_idx} out of range for protect mask num_layers={num_layers}"
        )
    return mask[layer_idx].to(torch.int8)


# ----------------------------------------------------------------------
# Phase 6E — fused decode write reference implementation.
#
# This is the EXACT Python op chain currently in
# write_decode_batched's captured region (lines starting after
# "CAPTURED-REGION-START"), packaged as a standalone function. It is
# byte-equivalent to the inline code by construction.
#
# Purpose:
#   1. Define the BEHAVIORAL CONTRACT that a future fused CUDA kernel
#      must satisfy. The CPU verifier (verify_phase6e_fused_byte_eq.py)
#      asserts byte-equality between the inline path and this reference;
#      when the CUDA kernel replaces this function's body, the same
#      verifier catches any divergence.
#
#   2. Provide a single point of integration. The dispatch fork in
#      write_decode_batched checks _fused_writer_enabled() and routes
#      to this function instead of the inline code. Today both paths
#      produce identical state mutations; when the CUDA kernel ships,
#      enabling PHASE6E_FUSED_WRITER=1 flips production to the
#      fused implementation atomically.
#
#   3. Document the input/output contract for the CUDA implementation:
#        - Inputs (read-only): key, value, slot_idx_t, slot_mapping,
#          writer-side per-layer sidecars and pool tensors.
#        - Outputs (in-place mutations): kv_cache, k/v_scale_ext,
#          k/v_xmin_ext, k_protect_ext, _k_stage_pool,
#          _k_stage_block_id_pool, _k_stage_count_pool, _seq_pos_pool,
#          (and _bf16_k/v_backing_pool unless 6C-skipped).
#
# Phase 6E will replace this function's body with two CUDA kernel
# calls (fused_decode_write_v + fused_decode_write_k). The function
# signature, mutation contract, and semantic correctness invariants
# stay the same — only the implementation changes.
# ----------------------------------------------------------------------


def _phase6e_fused_decode_write_python_ref(
    writer,
    key,           # (B, H, D) bf16 -- new K tokens this step
    value,         # (B, H, D) bf16 -- new V tokens this step
    slot_idx_t,    # (B,) long      -- pool slot per batch position (from hook or self-resolve)
    slot_mapping,  # (B,) long      -- vLLM cache slot per batch position
    kv_cache,      # (2, NB, BS, H, D) uint8 (in-place writeback)
):
    """Phase 6E Python reference for the fused decode write.

    Byte-equivalent to write_decode_batched's captured region (lines
    1217-1372 in this file as of Phase 6C). Now also routes through
    the custom CUDA kernels (`fused_decode_write_v`, `fused_decode_write_k`)
    when the int4_protected_C extension is built and the tensors live
    on CUDA — falling back to the Python op chain otherwise.

    Returns nothing; all state mutations are in-place on the writer's
    pool tensors and the kv_cache.
    """
    dtype = writer.sidecar_dtype
    BS = writer.BS
    D = writer.D
    H = writer.H
    half_D = D // 2
    B = key.shape[0]

    if key.dtype != dtype:
        key = key.to(dtype)
    if value.dtype != dtype:
        value = value.to(dtype)

    slot_mapping = slot_mapping.long()
    active_mask_t = (slot_mapping >= 0)                       # (B,) bool device

    safe_slot_mapping = torch.where(
        active_mask_t, slot_mapping, torch.zeros_like(slot_mapping),
    )
    block_ids = safe_slot_mapping // BS                       # (B,) long
    positions = safe_slot_mapping %  BS                       # (B,) long

    # Decide CUDA-kernel eligibility ONCE per call. The CUDA kernels
    # don't model bf16_v_mode (an artifact of an old fallback path) or
    # the bf16 backing pool (Phase 6C made it dead memory by default).
    # Whenever either Python-only mode is active we keep the full
    # Python path so byte equivalence is preserved.
    _ext = _try_load_int4_protected_C() if not _fused_cuda_disabled() else None
    _use_cuda = (
        _ext is not None
        and key.is_cuda
        and value.is_cuda
        and kv_cache.is_cuda
        and writer._bf16_backing_skipped      # CUDA path assumes skip mode.
        and not _bf16_v_mode()                # CUDA V kernel handles int4 only.
    )

    # ===== BF16 K/V backing scatter (skipped in 6C default) =====
    if not writer._bf16_backing_skipped:
        seq_pos_t = writer._seq_pos_pool[slot_idx_t].long()   # (B,) long
        writer._bf16_k_backing_pool[slot_idx_t, seq_pos_t] = key
        writer._bf16_v_backing_pool[slot_idx_t, seq_pos_t] = value
    if not _use_cuda:
        # Python path owns the seq_pos increment. CUDA path defers the
        # increment to fused_decode_write_k so the K kernel can update
        # all four pool tensors atomically.
        writer._seq_pos_pool.index_add_(
            0, slot_idx_t, active_mask_t.to(torch.int32),
        )

    # ===== V quantization vectorized over B (same math as legacy) =====
    if _bf16_v_mode():
        if getattr(writer, "_v_bf16_ext", None) is None:
            writer._v_bf16_ext = torch.zeros(
                (writer.NB, BS, H, D), dtype=dtype, device=kv_cache.device,
            )
        writer._v_bf16_ext[block_ids, positions] = value
    elif _use_cuda:
        # Production vLLM passes views (e.g. from the QKV split) that are
        # not always contiguous; the CUDA kernel requires contig inputs.
        # A no-op when value is already contiguous (the verifier case).
        v_ctg = value.contiguous() if not value.is_contiguous() else value
        _ext.fused_decode_write_v(
            v_ctg,
            slot_mapping,
            kv_cache[1],
            writer.v_scale_ext,
            writer.v_xmin_ext,
            int(writer.v_group_size),
        )
    else:
        v_grouped = value.float().view(
            B, H, writer.v_n_groups, writer.v_group_size,
        )
        v_max = v_grouped.amax(dim=-1)
        v_min = v_grouped.amin(dim=-1)
        v_scale = ((v_max - v_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)
        q_v = ((v_grouped - v_min.unsqueeze(-1)) / v_scale.unsqueeze(-1)) \
            .round().clamp(0, 15).to(torch.uint8)
        q_v_flat = q_v.view(B, H, D)
        v_packed = (q_v_flat[..., 0::2] & 0x0F) | ((q_v_flat[..., 1::2] & 0x0F) << 4)
        kv_cache[1, block_ids, positions, :, :half_D] = v_packed
        writer.v_scale_ext[block_ids, positions] = v_scale.to(dtype)
        writer.v_xmin_ext [block_ids, positions] = v_min.to(dtype)

    if _use_cuda:
        # The K CUDA kernel handles protect gather + stage update +
        # block-full finalize + bookkeeping (incl. seq_pos increment)
        # in one launch. Contig-guard same as for value above; vLLM
        # sometimes passes a non-contig key/value view.
        k_ctg = key.contiguous() if not key.is_contiguous() else key
        _ext.fused_decode_write_k(
            k_ctg,
            slot_idx_t.long(),
            slot_mapping,
            writer.protect_mask,
            writer.protected_d_per_head,
            writer._k_stage_pool,
            writer._k_stage_block_id_pool,
            writer._k_stage_count_pool,
            writer._seq_pos_pool,
            kv_cache[0],
            writer.k_scale_ext,
            writer.k_xmin_ext,
            writer.k_protect_ext,
        )
        return

    # ===== K protect gather + scatter =====
    protect_idx = writer.protected_d_per_head.unsqueeze(0).expand(B, -1, -1)
    k_protect = torch.gather(key, dim=-1, index=protect_idx)
    writer.k_protect_ext[block_ids, positions] = k_protect

    # ===== K staging: unconditional update + conditional finalize =====
    prior_block_id = writer._k_stage_block_id_pool[slot_idx_t]
    is_new_block = (block_ids != prior_block_id)

    keep_mask = (~is_new_block).view(B, 1, 1, 1)
    current_k_stage = writer._k_stage_pool[slot_idx_t]
    cleared_k_stage = torch.where(
        keep_mask, current_k_stage, torch.zeros_like(current_k_stage),
    )
    batch_arange = torch.arange(B, device=kv_cache.device)
    cleared_k_stage[batch_arange, positions] = key
    writer._k_stage_pool[slot_idx_t] = cleared_k_stage

    new_block_id = torch.where(
        active_mask_t, block_ids, writer._k_stage_block_id_pool[slot_idx_t],
    )
    writer._k_stage_block_id_pool[slot_idx_t] = new_block_id
    new_count = (positions + 1).to(torch.int32)
    cur_count = writer._k_stage_count_pool[slot_idx_t]
    writer._k_stage_count_pool[slot_idx_t] = torch.where(
        active_mask_t, new_count, cur_count,
    )

    # ===== Re-quantize the staging pool for all B slots =====
    buf_f = cleared_k_stage.float()
    x_max = buf_f.amax(dim=1)
    x_min = buf_f.amin(dim=1)
    scale = ((x_max - x_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)
    q = ((buf_f - x_min.unsqueeze(1)) / scale.unsqueeze(1)) \
        .round().clamp(0, 15).to(torch.uint8)
    packed = (q[..., 0::2] & 0x0F) | ((q[..., 1::2] & 0x0F) << 4)

    block_full_mask = ((positions + 1) == BS) & active_mask_t
    full_mask_kv = block_full_mask.view(B, 1, 1, 1)
    full_mask_ext = block_full_mask.view(B, 1, 1)

    current_kv_packed = kv_cache[0, block_ids][..., :half_D]
    new_kv_packed = torch.where(full_mask_kv, packed, current_kv_packed)
    kv_cache[0, block_ids, :, :, :half_D] = new_kv_packed

    current_k_scale = writer.k_scale_ext[block_ids]
    current_k_xmin  = writer.k_xmin_ext [block_ids]
    scale_dt = scale.to(dtype)
    xmin_dt  = x_min.to(dtype)
    writer.k_scale_ext[block_ids] = torch.where(
        full_mask_ext, scale_dt, current_k_scale,
    )
    writer.k_xmin_ext [block_ids] = torch.where(
        full_mask_ext, xmin_dt,  current_k_xmin,
    )

    writer._k_stage_count_pool[slot_idx_t] = torch.where(
        block_full_mask,
        torch.zeros_like(writer._k_stage_count_pool[slot_idx_t]),
        writer._k_stage_count_pool[slot_idx_t],
    )


# ----------------------------------------------------------------------
# Phase 5B.6 step 1: per-sequence state container.
# ----------------------------------------------------------------------

class SeqState:
    """Per-sequence streaming state for a PagedKVWriter.

    Phase 6 v2 Option B pre-flight (B-pre-1): tensor fields are now
    VIEWS into per-writer pool tensors (`_k_stage_pool`,
    `_bf16_k_backing_pool`, `_bf16_v_backing_pool`), indexed by this
    SeqState's `slot_idx`. Per-instance fields are just the Python int
    counters (`k_stage_count`, `k_stage_block_id`, `seq_pos`).

    The pool layout is what unlocks graph-friendly reads: instead of
    `[state.bf16_k_backing for state in states]` (a Python loop over
    dict-resolved tensors at unstable addresses) the read path uses
    `writer._bf16_k_backing_pool[slot_idx_tensor]` — a single device
    gather from a stable-address pool tensor.

    The external API (state.k_stage, state.bf16_k_backing, etc.) is
    UNCHANGED so the write path and any legacy single-seq callers keep
    working without modification.

    Per-LAYER state (k_scale_ext, k_xmin_ext, k_protect_ext,
    v_scale_ext, v_xmin_ext) remains on the writer — shared across
    sequences via global block_id indexing.
    """

    __slots__ = (
        "_writer",            # PagedKVWriter — for pool tensor access
        "slot_idx",           # int — this seq's index into the writer's pools
        "k_stage_count",      # int 0..BS
        "k_stage_block_id",   # int — block being filled
        "seq_pos",            # int — non-padding tokens written so far in this seq
    )

    def __init__(self, writer: "PagedKVWriter", slot_idx: int) -> None:
        if torch is None:
            raise RuntimeError("SeqState requires torch")
        self._writer = writer
        self.slot_idx = slot_idx
        self.k_stage_count = 0
        self.k_stage_block_id = -1
        self.seq_pos = 0

    # Tensor accessors — views into writer-level pools. Reading these
    # returns a tensor at a stable address (the pool slice never moves).
    @property
    def k_stage(self) -> "torch.Tensor":
        # (BS, H, D) — view into _k_stage_pool[slot_idx, :, :, :]
        return self._writer._k_stage_pool[self.slot_idx]

    @property
    def bf16_k_backing(self) -> Optional["torch.Tensor"]:
        # (1, max_S, H, D) — preserves the historical leading-1 batch
        # dim that callers slice as state.bf16_k_backing[0, :S, ...].
        # Phase 6C: returns None when the writer is in skip mode (the
        # backing pool is a (1, 1, H, D) stub; callers must guard via
        # `if state.bf16_k_backing is not None:`).
        if getattr(self._writer, "_bf16_backing_skipped", False):
            return None
        s = self.slot_idx
        return self._writer._bf16_k_backing_pool[s:s + 1]

    @property
    def bf16_v_backing(self) -> Optional["torch.Tensor"]:
        if getattr(self._writer, "_bf16_backing_skipped", False):
            return None
        s = self.slot_idx
        return self._writer._bf16_v_backing_pool[s:s + 1]

    def reset(self) -> None:
        """Clear streaming state for a fresh sequence. Zeros THIS slot's
        k_stage entry in the pool and resets the Python counters.
        Backing pool entries [seq_pos, max_S) are unread (cache_seqlens
        masks them in the kernel), so we don't zero them.

        Does NOT free the slot back to the pool — call
        writer.evict_sequence(seq_id) for that.
        """
        # In-place zero via the property view — writes into the pool.
        self.k_stage.zero_()
        self.k_stage_count = 0
        self.k_stage_block_id = -1
        self.seq_pos = 0


# ----------------------------------------------------------------------
# PagedKVWriter — per-layer quantizing writer.
# ----------------------------------------------------------------------

class PagedKVWriter:
    """Per-layer streaming KV quantizer that writes to vLLM's paged
    uint8 cache + external sidecar tensors.

    Lazy-allocates sidecars on first `write()` (needs kv_cache shape).

    Phase 5B.6 step 1: per-sequence state lives in `_seq_states` dict
    keyed by an opaque seq_id. v1 batch=1 callers always use
    `DEFAULT_SEQ_ID = 0`; multi-batch callers pass real seq_ids per
    sequence via `write_for_seq` / `read_for_seq` (lands in step 2/3).

    For backward compatibility, the legacy attributes (`self.k_stage`,
    `self.k_stage_count`, `self.k_stage_block_id`, `self.bf16_k_backing`,
    `self.bf16_v_backing`, `self.seq_pos`) PROXY to the default
    SeqState. Tensors are shared by reference (no copies); ints go
    through Python @property.

    Per-LAYER state (k_scale_ext, k_xmin_ext, k_protect_ext, v_scale_ext,
    v_xmin_ext) remains on `self` — shared across sequences via global
    block_id indexing.

    Construction is cheap — no device-bound state. The expensive
    allocations happen in `_lazy_alloc()` on first write.
    """

    # Default sequence id used by single-seq callers (v1 batch=1).
    DEFAULT_SEQ_ID = 0

    def __init__(
        self,
        layer_idx: int,
        *,
        protect_mask: Optional["torch.Tensor"] = None,
        v_group_size: int = _DEFAULT_V_GROUP_SIZE,
        sidecar_dtype: "torch.dtype" = None,
    ) -> None:
        if torch is None:
            raise RuntimeError("PagedKVWriter requires torch")
        if sidecar_dtype is None:
            sidecar_dtype = torch.bfloat16
        self.layer_idx = layer_idx
        self.v_group_size = v_group_size
        self.sidecar_dtype = sidecar_dtype
        # protect_mask supplied or load lazily on first write.
        self._protect_mask_cpu: Optional[torch.Tensor] = protect_mask

        # Device-bound state — populated by _lazy_alloc.
        self._allocated = False
        self.NB: int = -1
        self.BS: int = -1
        self.H: int = -1
        self.D: int = -1
        self.n_protect: int = -1
        self.v_n_groups: int = -1

        self.protect_mask: Optional[torch.Tensor] = None       # (H, D) int8 on device
        self.protect_slot: Optional[torch.Tensor] = None       # (H, D) int8
        self.protected_d_per_head: Optional[torch.Tensor] = None  # (H, n_protect) long

        # Per-LAYER (shared across sequences via block_id indexing).
        self.k_scale_ext: Optional[torch.Tensor] = None   # (NB, H, D) bf16
        self.k_xmin_ext:  Optional[torch.Tensor] = None   # (NB, H, D) bf16
        self.k_protect_ext: Optional[torch.Tensor] = None # (NB, BS, H, n_protect) bf16
        self.v_scale_ext: Optional[torch.Tensor] = None   # (NB, BS, H, v_n_groups) bf16
        self.v_xmin_ext:  Optional[torch.Tensor] = None   # (NB, BS, H, v_n_groups) bf16

        # Per-SEQUENCE state container. seq_id -> SeqState. Created
        # lazily on first write to each sequence. The default seq
        # (DEFAULT_SEQ_ID = 0) is allocated by _lazy_alloc so legacy
        # single-seq access works immediately.
        #
        # Phase 6 v2 Option B pre-flight (B-pre-1): each SeqState's
        # tensor fields are now views into per-writer POOL tensors
        # (_k_stage_pool / _bf16_k_backing_pool / _bf16_v_backing_pool)
        # indexed by a small int slot. _slot_map tracks seq_id -> slot
        # assignments; _free_slots is the unused-slot pool.
        self._seq_states: Dict[Any, SeqState] = {}
        self._slot_map: Dict[Any, int] = {}
        self._free_slots: List[int] = []           # populated in _lazy_alloc

        # Phase 5B.4c.3 fix (a) backing-tensor sizing — pulled from env.
        self._bf16_backing_max_seqlen = _bf16_backing_max_seqlen()
        # Phase 6 v2 (B-pre-1) — pool capacity for active sequences.
        self._max_active_slots: int = _max_active_slots()

        # Pool tensors — allocated by _lazy_alloc (need device + shapes).
        self._k_stage_pool: Optional["torch.Tensor"] = None
        self._bf16_k_backing_pool: Optional["torch.Tensor"] = None
        self._bf16_v_backing_pool: Optional["torch.Tensor"] = None

        # Phase 6B.1 — device-side per-slot counter pools for the
        # graph-capture-friendly write_decode_batched path. These shadow
        # the Python ints on SeqState (which stay in place for the
        # legacy per-seq write path). Sync from SeqState happens at
        # write_decode_batched entry; after that, the captured region
        # operates exclusively on these device tensors.
        self._seq_pos_pool: Optional["torch.Tensor"] = None         # (max_slots,) int32
        self._k_stage_count_pool: Optional["torch.Tensor"] = None   # (max_slots,) int32
        self._k_stage_block_id_pool: Optional["torch.Tensor"] = None  # (max_slots,) int64; -1 sentinel

    # ------------------------------------------------------------------
    # Phase 5B.6 step 1: per-sequence state lookups + lifecycle.
    # ------------------------------------------------------------------

    def get_seq_state(self, seq_id: Any) -> "SeqState":
        """Return the SeqState for `seq_id`, raising KeyError if not yet
        created. Use `ensure_seq_state` to allocate on demand."""
        s = self._seq_states.get(seq_id)
        if s is None:
            raise KeyError(
                f"no SeqState for seq_id={seq_id!r}. Call write_for_seq "
                f"(which allocates lazily) before reading state."
            )
        return s

    def ensure_seq_state(self, seq_id: Any, device: "torch.device") -> "SeqState":
        """Return the SeqState for `seq_id`, allocating a slot if needed.

        Phase 6 v2 Option B pre-flight (B-pre-1): slots are popped from
        `_free_slots`. Cap is `_max_active_slots` (configurable via
        $PHASE6_MAX_ACTIVE_SLOTS, default 8). Raises a clear error if
        exhausted — callers should `evict_sequence(...)` on finished
        sequences to free slots.

        The `device` argument is retained for API stability but no
        longer used (pool tensors live on the writer; their device was
        set at `_lazy_alloc` time).
        """
        s = self._seq_states.get(seq_id)
        if s is not None:
            return s
        if not self._allocated:
            raise RuntimeError(
                "PagedKVWriter not yet _lazy_alloc'd; can't create SeqState."
            )
        if not self._free_slots:
            raise RuntimeError(
                f"PagedKVWriter slot pool exhausted "
                f"(max_active_slots={self._max_active_slots}). "
                f"Bump ${_MAX_ACTIVE_SLOTS_ENV} or call evict_sequence "
                f"on finished sequences. Currently assigned: "
                f"{list(self._slot_map.keys())}"
            )
        slot_idx = self._free_slots.pop(0)
        s = SeqState(self, slot_idx)
        self._seq_states[seq_id] = s
        self._slot_map[seq_id] = slot_idx
        return s

    def evict_sequence(self, seq_id: Any) -> None:
        """Drop a sequence's state, freeing its slot back to the pool.
        Called when a sequence finishes generation.

        Phase 6 v2 (B-pre-1): also returns the slot index to
        `_free_slots` so it can be reused by a future sequence. Does NOT
        zero the pool entry — the next `ensure_seq_state` reset() (or
        write through that slot) will overwrite the stale data.
        """
        self._seq_states.pop(seq_id, None)
        slot = self._slot_map.pop(seq_id, None)
        if slot is not None:
            self._free_slots.append(slot)
            # Phase 6B.1 — also reset the device-side pool counters for
            # the freed slot so a future sequence allocated to this slot
            # starts from a clean device-side state. Idempotent before
            # _lazy_alloc (pools are None).
            #
            # Phase 6B.3 fix: pool tensors carry the "inference tensor"
            # attribute (allocated inside _lazy_alloc which fires during
            # the first forward pass — inside vLLM's @torch.inference_
            # mode() decorator). External callers (e.g., the GPU smoke
            # driver resetting state between generate() calls) run
            # OUTSIDE inference_mode and would be rejected. Same pattern
            # as the 6B.2 hook's pool mutations in _resolve_and_stash.
            if self._seq_pos_pool is not None:
                with torch.inference_mode():
                    self._seq_pos_pool[slot] = 0
                    self._k_stage_count_pool[slot] = 0
                    self._k_stage_block_id_pool[slot] = -1

    def gc_completed_slots(self, active_seq_ids: "Any") -> int:
        """Phase 6K.14: free slots whose seq_id is no longer running.

        ``active_seq_ids`` is the set of seq_ids in the CURRENT pure-decode
        batch. In vLLM V0 the decode batch contains exactly the running
        sequences, so any assigned slot whose seq_id is absent here has
        either completed or been recompute-preempted — in both cases the
        next time we see that seq_id it must start from fresh state, so
        evicting now is correct AND returns the slot to ``_free_slots``.

        Without this call, ``ensure_seq_state`` leaks one slot per distinct
        seq_id across decode waves / completed requests until the pool
        exhausts ("slot pool exhausted" at high B) — the Phase 6K.13
        finding. Returns the number of slots freed.

        MUST be called only on PURE-DECODE steps. On a prefill-only step
        the batch is just the newly-added sequences and the running decode
        seqs are absent, so GC there would wrongly evict live sequences.
        (The prefill boundary has its own 6K.9 evict for stale recycled
        state.)

        Caveat: assumes recompute-style preemption (KV dropped and
        re-prefilled), not swap-to-CPU. This backend doesn't migrate its
        sidecars on swap, so swap preemption must stay off regardless.

        Self-gated by $PHASE6K14_EVICT_ON_DECODE so an A/B run can
        reproduce the pre-fix leak without touching call sites.
        """
        if not _evict_on_decode_enabled():
            return 0
        leaked = _leaked_seq_ids(list(self._slot_map.keys()), active_seq_ids)
        for sid in leaked:
            self.evict_sequence(sid)
        return len(leaked)

    # ------------------------------------------------------------------
    # Phase 6 v2 Option B pre-flight (B-pre-1): slot-tensor-based read
    # API for the captured-graph-friendly read path. Resolves seq_id ->
    # slot Python-side (pre-capture); the captured region uses the slot
    # tensor for device-indexed gathers into the pool tensors.
    # ------------------------------------------------------------------

    def slot_indices_for(self, seq_ids: "list") -> "list":
        """Resolve a list of seq_ids to a list of slot ints.

        KeyErrors here mean a sequence has writes but no allocated slot
        — should never happen if ensure_seq_state was called before.
        """
        try:
            return [self._slot_map[sid] for sid in seq_ids]
        except KeyError as e:
            raise RuntimeError(
                f"seq_id {e.args[0]!r} has no slot assignment; "
                f"slot_map keys: {list(self._slot_map.keys())}"
            )

    def get_bf16_backing_batched_by_slots(
        self,
        slot_idx_tensor: "torch.Tensor",   # (B,) long, on device
        S_padded: int,
    ):
        """Device-indexed gather of bf16 K/V backings for the batched
        decode read.

        Phase 6C: kernel verification confirmed the int4_packed
        flash_attn template never reads from these tensors — they're
        accepted as positional args for shape inference only. In skip
        mode we return a stride-0 broadcast view of a (1,1,H,D) stub,
        so the kernel sees logical shape (B, S_padded, H, D) with the
        right contiguous-last-dim invariant, at ~1KB total memory cost.

        Returns (B, S_padded, H, D), (B, S_padded, H, D) — both bf16.
        """
        if not self._allocated:
            raise RuntimeError("get_bf16_backing_batched_by_slots before _lazy_alloc")
        B = slot_idx_tensor.shape[0]
        H = self.H
        D = self.D
        if self._bf16_backing_skipped:
            # Stub pool is (1, 1, H, D). Broadcast to (B, S_padded, H, D)
            # via expand — last-dim stride stays 1 (passes the kernel's
            # contiguous-last-dim assert); seq/batch dims have stride 0.
            # The int4_packed kernel only uses these args for stride
            # parameter setup; never dereferences the underlying memory.
            stub_k = self._bf16_k_backing_pool                 # (1, 1, H, D)
            stub_v = self._bf16_v_backing_pool                 # (1, 1, H, D)
            bf16_k = stub_k.expand(B, S_padded, H, D)
            bf16_v = stub_v.expand(B, S_padded, H, D)
            return bf16_k, bf16_v
        max_S = self._bf16_k_backing_pool.shape[1]
        if S_padded > max_S:
            raise RuntimeError(f"S_padded={S_padded} > max_seqlen={max_S}")
        # Pool shape: (n_slots, max_S, H, D). Indexing by slot tensor
        # (B,) and slicing the seq dim gives (B, S_padded, H, D) in one
        # advanced-index op.
        bf16_k = self._bf16_k_backing_pool[slot_idx_tensor, :S_padded]
        bf16_v = self._bf16_v_backing_pool[slot_idx_tensor, :S_padded]
        return bf16_k, bf16_v

    def get_k_stage_by_slots(
        self,
        slot_idx_tensor: "torch.Tensor",   # (A,) long, on device
    ) -> "torch.Tensor":
        """Device-indexed gather of K staging buffers, for the
        vectorized splice. Returns (A, BS, H, D) — sidecar_dtype.

        `slot_idx_tensor` is typically the ACTIVE subset (sequences
        with non-zero tail length); caller is responsible for masking.
        """
        if not self._allocated:
            raise RuntimeError("get_k_stage_by_slots before _lazy_alloc")
        return self._k_stage_pool[slot_idx_tensor]

    @property
    def _default_state(self) -> Optional["SeqState"]:
        """The SeqState bound to DEFAULT_SEQ_ID. None before _lazy_alloc."""
        return self._seq_states.get(self.DEFAULT_SEQ_ID)

    # ------------------------------------------------------------------
    # Backward-compat properties — proxy legacy `self.x` attribute access
    # to the default SeqState. New code should pass an explicit SeqState
    # via write_for_seq / get_seq_state.
    # ------------------------------------------------------------------

    @property
    def k_stage(self) -> Optional["torch.Tensor"]:
        s = self._default_state
        return s.k_stage if s is not None else None

    @property
    def k_stage_count(self) -> int:
        s = self._default_state
        return s.k_stage_count if s is not None else 0

    @k_stage_count.setter
    def k_stage_count(self, value: int) -> None:
        s = self._default_state
        if s is None:
            return  # pre-alloc; ignore (matches old field-default behavior)
        s.k_stage_count = value

    @property
    def k_stage_block_id(self) -> int:
        s = self._default_state
        return s.k_stage_block_id if s is not None else -1

    @k_stage_block_id.setter
    def k_stage_block_id(self, value: int) -> None:
        s = self._default_state
        if s is None:
            return
        s.k_stage_block_id = value

    @property
    def bf16_k_backing(self) -> Optional["torch.Tensor"]:
        s = self._default_state
        return s.bf16_k_backing if s is not None else None

    @property
    def bf16_v_backing(self) -> Optional["torch.Tensor"]:
        s = self._default_state
        return s.bf16_v_backing if s is not None else None

    @property
    def seq_pos(self) -> int:
        s = self._default_state
        return s.seq_pos if s is not None else 0

    @seq_pos.setter
    def seq_pos(self, value: int) -> None:
        s = self._default_state
        if s is None:
            return
        s.seq_pos = value

    # ------------------------------------------------------------------
    # Lazy allocation.
    # ------------------------------------------------------------------

    def _lazy_alloc(self, kv_cache: "torch.Tensor") -> None:
        """Allocate sidecars + staging buffer using kv_cache shape.

        kv_cache shape after Phase 5B.4b: (2, NB, BS, H_kv, D) uint8.
        """
        if self._allocated:
            return

        # Phase 6K.14: re-resolve the pool cap now that we're inside a real
        # forward — vLLM's config is live here, so the auto-bump path can
        # read max_num_seqs (it may have been unavailable at __init__ time).
        # An explicit $PHASE6_MAX_ACTIVE_SLOTS still wins; the env-set tests
        # see the same value they set.
        self._max_active_slots = _max_active_slots()

        if kv_cache.ndim != 5 or kv_cache.shape[0] != 2:
            raise ValueError(
                f"kv_cache shape {tuple(kv_cache.shape)} != (2, NB, BS, H_kv, D)"
            )
        _, NB, BS, H, D = kv_cache.shape
        device = kv_cache.device

        if D != 128:
            raise NotImplementedError(
                f"PagedKVWriter v1 only supports D=128; got D={D}"
            )
        if BS % 2 != 0:
            raise ValueError(f"block_size BS={BS} must be even")
        if D % 2 != 0:
            raise ValueError(f"head_dim D={D} must be even for nibble packing")
        if D % self.v_group_size != 0:
            raise ValueError(
                f"head_dim D={D} must be divisible by v_group_size={self.v_group_size}"
            )

        # group_size = block_size = kInt4GroupSize = 32. The kernel's
        # kInt4GroupSize is a compile-time constexpr (not runtime), so
        # block_size MUST be 32 to match. PHASE5B4C_DESIGN.md has the
        # full constraint trace. Caller must pass block_size=32 to
        # vLLM at LLM(...) construction.
        if BS != 32:
            raise RuntimeError(
                f"PagedKVWriter requires block_size=32 (kernel kInt4GroupSize "
                f"constexpr); got block_size={BS}. Pass block_size=32 to "
                f"LLM(...) at construction."
            )

        # Load + slice protect mask for this layer.
        if self._protect_mask_cpu is None:
            self._protect_mask_cpu = load_protect_mask_for_layer(self.layer_idx)
        if self._protect_mask_cpu.shape != (H, D):
            raise ValueError(
                f"protect_mask shape {tuple(self._protect_mask_cpu.shape)} != ({H}, {D})"
            )
        self.protect_mask = self._protect_mask_cpu.to(device=device, dtype=torch.int8)
        # n_protect = uniform row count (assumed equal across heads).
        n_protect = max(1, int(self.protect_mask.sum(dim=-1).max().item()))
        self.protect_slot, self.protected_d_per_head = _build_protect_tables(
            self.protect_mask, n_protect,
        )

        v_n_groups = D // self.v_group_size

        # External sidecars.
        dtype = self.sidecar_dtype
        self.k_scale_ext   = torch.zeros((NB, H, D),                 dtype=dtype, device=device)
        self.k_xmin_ext    = torch.zeros((NB, H, D),                 dtype=dtype, device=device)
        self.k_protect_ext = torch.zeros((NB, BS, H, n_protect),     dtype=dtype, device=device)
        self.v_scale_ext   = torch.zeros((NB, BS, H, v_n_groups),    dtype=dtype, device=device)
        self.v_xmin_ext    = torch.zeros((NB, BS, H, v_n_groups),    dtype=dtype, device=device)

        self.NB, self.BS, self.H, self.D = NB, BS, H, D
        self.n_protect = n_protect
        self.v_n_groups = v_n_groups

        # Phase 6 v2 Option B pre-flight (B-pre-1): allocate the per-
        # sequence state POOL tensors. Each slot owns one (BS, H, D)
        # k_stage entry and two (max_S, H, D) bf16 backing entries.
        # Memory cost at default _max_active_slots=8 matches the
        # current per-seq lazy-alloc footprint (~256 MB per writer at
        # max_S=4096).
        max_S = self._bf16_backing_max_seqlen
        n_slots = self._max_active_slots
        self._k_stage_pool = torch.zeros(
            (n_slots, BS, H, D), dtype=dtype, device=device,
        )
        # Phase 6C: kernel verification (vllm-flash-attn-dev, packed
        # path, flash_fwd_kernel.h L962-985 / L1073-1100) confirmed
        # bf16_k_batch / bf16_v_batch are not read in the int4_packed
        # kernel template. Allocate a (1, 1, H, D) stub when skipping
        # (~1KB/layer/pool vs ~500MB/layer/pool at max_S=4096); the
        # read path broadcasts to (B, S_padded, H, D) via stride-0
        # expand for kernel shape compatibility, at no extra memory.
        self._bf16_backing_skipped = _bf16_backing_skip()
        if self._bf16_backing_skipped:
            self._bf16_k_backing_pool = torch.zeros(
                (1, 1, H, D), dtype=torch.bfloat16, device=device,
            )
            self._bf16_v_backing_pool = torch.zeros(
                (1, 1, H, D), dtype=torch.bfloat16, device=device,
            )
        else:
            self._bf16_k_backing_pool = torch.zeros(
                (n_slots, max_S, H, D), dtype=torch.bfloat16, device=device,
            )
            self._bf16_v_backing_pool = torch.zeros(
                (n_slots, max_S, H, D), dtype=torch.bfloat16, device=device,
            )
        # Phase 6B.1 — per-slot counter pools (device-side; ~160 B total).
        # Sentinel: k_stage_block_id_pool starts at -1 so the FIRST
        # write_decode_batched call for a slot detects "new block"
        # (matching legacy SeqState.k_stage_block_id = -1 init).
        self._seq_pos_pool = torch.zeros(
            (n_slots,), dtype=torch.int32, device=device,
        )
        self._k_stage_count_pool = torch.zeros(
            (n_slots,), dtype=torch.int32, device=device,
        )
        self._k_stage_block_id_pool = torch.full(
            (n_slots,), -1, dtype=torch.int64, device=device,
        )
        # Slots are handed out via ensure_seq_state. ALL slots are free
        # at alloc time — the default seq is no longer pre-reserved
        # (B-pre-1 lesson: pre-reserving cost 1 slot of capacity, which
        # surfaced as pool exhaustion at the documented B=8 ship target
        # when none of vLLM's 8 fresh seq_ids happened to equal 0).
        # First write through ensure_seq_state(DEFAULT_SEQ_ID) allocates
        # it lazily, like any other seq.
        self._free_slots = list(range(n_slots))
        self._allocated = True

        logger.info(
            "PagedKVWriter layer=%d allocated: NB=%d BS=%d H=%d D=%d "
            "n_protect=%d v_n_groups=%d max_active_slots=%d",
            self.layer_idx, NB, BS, H, D,
            n_protect, v_n_groups, n_slots,
        )

    def reset_sequence(self, seq_id: Any = None) -> None:
        """Reset streaming state for one sequence (default seq if None)
        or ALL sequences (seq_id='all').

        Per-LAYER sidecar tensors (k_scale_ext etc.) are kept — they're
        large and reusable; positions of dropped sequences will be
        overwritten by future writes.

        Phase 6 v2 Option B pre-flight (B-pre-1): `seq_id='all'` now
        evicts EVERY sequence (including DEFAULT_SEQ_ID if it was
        lazy-allocated). The intent of "all" is a hard reset between
        workloads — the writer's slot pool returns to fully free, ready
        for whatever seq_ids the next workload brings.

        Without this, a workload that ran a sequence with seq_id=0
        (block_id 0 as first block) would leave the default slot
        occupied across resets, eating one slot of pool capacity and
        causing exhaustion at high-B on subsequent runs.

        Legacy single-seq callers use `reset_sequence()` (no args) which
        resets the default's streaming state in place — slot retained.
        """
        if seq_id == "all":
            # Evict EVERY seq — restores pool to fully free.
            for sid in list(self._seq_states.keys()):
                self.evict_sequence(sid)
            return
        target = self.DEFAULT_SEQ_ID if seq_id is None else seq_id
        s = self._seq_states.get(target)
        if s is not None:
            s.reset()

    # ------------------------------------------------------------------
    # Write path.
    # ------------------------------------------------------------------

    def write(
        self,
        key: "torch.Tensor",            # (T, H_kv, D) bf16
        value: "torch.Tensor",          # (T, H_kv, D) bf16
        kv_cache: "torch.Tensor",       # (2, NB, BS, H_kv, D) uint8
        slot_mapping: "torch.Tensor",   # (T,) long
        *,
        seq_id: Any = None,
    ) -> None:
        """Phase 6 vectorized write into paged cache + external sidecars.

        Phase 5B.6 step 2: now accepts an explicit `seq_id`. If omitted,
        routes through DEFAULT_SEQ_ID (= 0) for v1 batch=1 callers — no
        behavior change from the prior single-seq write.

        For multi-batch (Phase 5B.6): the caller partitions slot_mapping
        by sequence and calls write() once per sequence with that seq's
        id. Each seq's K staging + bf16 backing live in its own
        SeqState (allocated on first write).

        Pipeline (unchanged):
          1. Filter -1 padding slots (vLLM uses -1 for "do not write").
          2. BF16 K/V backing append at [state.seq_pos : ...+n_real].
          3. V quantization VECTORIZED over n_real (one set of CUDA ops).
          4. V scatter into kv_cache[1] + v_scale_ext + v_xmin_ext via
             advanced indexing — one op each instead of T per-token writes.
          5. K protect gather VECTORIZED -> scatter into k_protect_ext.
          6. K staging: split unique blocks into FULL (count==BS, batch-
             finalize all at once) vs PARTIAL (count<BS, through this
             SeqState's staging buffer).

        Bit-equivalent to the prior per-token implementation; verified
        by verify_phase5b_4c_1_write.py + verify_phase5b_4c_2_read.py.
        """
        if not self._allocated:
            self._lazy_alloc(kv_cache)

        if seq_id is None:
            seq_id = self.DEFAULT_SEQ_ID
        state = self.ensure_seq_state(seq_id, kv_cache.device)
        self._write_into_state(state, key, value, kv_cache, slot_mapping)

    def _write_into_state(
        self,
        state: "SeqState",
        key: "torch.Tensor",
        value: "torch.Tensor",
        kv_cache: "torch.Tensor",
        slot_mapping: "torch.Tensor",
    ) -> None:
        """Internal: same vectorized write as before, but operating on
        an explicit SeqState (`state`) for per-seq fields instead of
        the legacy `self.*` proxies. Per-LAYER state (k_scale_ext etc.)
        remains on `self`.
        """
        if key.shape != value.shape:
            raise ValueError(
                f"key shape {tuple(key.shape)} != value shape {tuple(value.shape)}"
            )
        if key.ndim != 3 or key.shape[1:] != (self.H, self.D):
            raise ValueError(
                f"key shape {tuple(key.shape)} != expected (T, {self.H}, {self.D})"
            )
        if slot_mapping.ndim != 1 or slot_mapping.shape[0] != key.shape[0]:
            raise ValueError(
                f"slot_mapping shape {tuple(slot_mapping.shape)} != ({key.shape[0]},)"
            )

        T = key.shape[0]
        dtype = self.sidecar_dtype
        BS = self.BS
        D = self.D
        H = self.H
        half_D = D // 2

        if key.dtype != dtype:
            key = key.to(dtype)
        if value.dtype != dtype:
            value = value.to(dtype)

        # Move slot_mapping to the same device as key (it's typically GPU
        # already but be defensive). Filter -1 padding.
        if slot_mapping.device != key.device:
            slot_mapping = slot_mapping.to(key.device)
        slot_mapping = slot_mapping.long()
        non_padding_gpu = (slot_mapping >= 0)
        # Single CPU sync to learn how many real tokens we have. This is
        # also implicitly needed to size downstream tensors.
        n_real = int(non_padding_gpu.sum().item())
        if n_real == 0:
            return

        if n_real == T:
            real_key = key
            real_value = value
            real_slots = slot_mapping
        else:
            real_key   = key[non_padding_gpu]            # (n_real, H, D)
            real_value = value[non_padding_gpu]
            real_slots = slot_mapping[non_padding_gpu]

        # ===== BF16 K/V backing (Phase 5B.4c.3 fix-a; per-seq) =====
        # `state` is THIS sequence's SeqState; bf16 backing is per-seq.
        # Phase 6C: when bf16_k_backing returns None (skip mode), don't
        # write to the (deallocated) backing pool — the int4_packed
        # kernel doesn't read it. seq_pos still advances so the rest
        # of the writer state (k_stage, sentinel pools) stays correct.
        if state.bf16_k_backing is not None:
            if state.seq_pos + n_real > state.bf16_k_backing.shape[1]:
                raise RuntimeError(
                    f"bf16 backing overflow: seq_pos={state.seq_pos} + "
                    f"n_real={n_real} > max_seqlen="
                    f"{state.bf16_k_backing.shape[1]}. Set "
                    f"{_BF16_BACKING_MAX_SEQLEN_ENV} to a larger value."
                )
            state.bf16_k_backing[0, state.seq_pos:state.seq_pos + n_real] = real_key
            state.bf16_v_backing[0, state.seq_pos:state.seq_pos + n_real] = real_value
        state.seq_pos += n_real

        block_ids = real_slots // BS                     # (n_real,) long
        positions = real_slots %  BS

        # ===== V quantization, fully vectorized over n_real =====
        if _bf16_v_mode():
            # Debug bf16-V mode (used in 5B.4c.3 V isolation).
            if getattr(self, "_v_bf16_ext", None) is None:
                self._v_bf16_ext = torch.zeros(
                    (self.NB, self.BS, H, D),
                    dtype=dtype, device=kv_cache.device,
                )
            self._v_bf16_ext[block_ids, positions] = real_value
        else:
            v_grouped = real_value.float().view(
                n_real, H, self.v_n_groups, self.v_group_size,
            )
            v_max = v_grouped.amax(dim=-1)                              # (n_real, H, n_g)
            v_min = v_grouped.amin(dim=-1)
            v_scale = ((v_max - v_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)
            q_v = ((v_grouped - v_min.unsqueeze(-1)) / v_scale.unsqueeze(-1)) \
                .round().clamp(0, 15).to(torch.uint8)                   # (n_real, H, n_g, G)
            q_v_flat = q_v.view(n_real, H, D)
            v_packed = (q_v_flat[..., 0::2] & 0x0F) | ((q_v_flat[..., 1::2] & 0x0F) << 4)
            # v_packed: (n_real, H, D/2)

            kv_cache[1, block_ids, positions, :, :half_D] = v_packed
            self.v_scale_ext[block_ids, positions] = v_scale.to(dtype)
            self.v_xmin_ext [block_ids, positions] = v_min.to(dtype)

        # ===== K protect gather, vectorized =====
        protect_idx = self.protected_d_per_head.unsqueeze(0).expand(n_real, -1, -1)
        # (n_real, H, n_protect) long
        k_protect = torch.gather(real_key, dim=-1, index=protect_idx)
        self.k_protect_ext[block_ids, positions] = k_protect

        # ===== K staging + finalize =====
        # Identify unique blocks and which are FULL (count == BS) vs PARTIAL.
        # FULL blocks bypass the staging buffer (we have all BS tokens for
        # them already in real_key, so finalize directly in one batched op).
        # PARTIAL blocks go through the staging buffer (state carries
        # across write() calls).
        unique_blocks, inverse, counts = torch.unique(
            block_ids, return_inverse=True, return_counts=True,
        )
        full_mask = (counts == BS)
        n_full_blocks = int(full_mask.sum().item())

        if n_full_blocks > 0:
            self._finalize_k_full_blocks_batched(
                state=state,
                kv_cache=kv_cache,
                real_key=real_key,
                block_ids=block_ids,
                positions=positions,
                inverse=inverse,
                unique_blocks=unique_blocks,
                full_mask=full_mask,
                n_full_blocks=n_full_blocks,
            )

        if n_full_blocks < unique_blocks.shape[0]:
            # At least one PARTIAL block; route those through THIS seq's
            # staging buffer. Process in SEQUENCE ORDER (appearance order)
            # so state.k_stage_block_id ends pointing at the seq's last
            # block (where the next decode write will continue).
            self._stage_k_partial_blocks(
                state=state,
                kv_cache=kv_cache,
                real_key=real_key,
                block_ids=block_ids,
                positions=positions,
                unique_blocks=unique_blocks,
                full_mask=full_mask,
            )

    # ------------------------------------------------------------------
    # Phase 6B.1 — graph-capture-friendly decode write path.
    # ------------------------------------------------------------------

    def _sync_pool_counters_from_states(self, slot_idx_list: list) -> None:
        """Phase 6B.1 / 6B.2 — copy per-slot SeqState Python int counters
        into the device-side counter pools, but ONLY for slots that
        haven't been touched by the decode write path yet (sentinel:
        `_k_stage_block_id_pool[slot] == -1`).

        Why sentinel-gated:
        * In the 6B.1 self-resolve path, this sync runs BEFORE each
          captured-region invocation paired with a post-writeback that
          flushes the pool back to SeqState. Sync + writeback are
          symmetrical; sync runs once and subsequent calls have no-op
          values because SeqState was just updated.
        * In the 6B.2 hook path, the writer's pool is the source of
          truth and SeqState ints may go stale (writeback skipped).
          Re-syncing unconditionally would REGRESS the pool to the
          stale SeqState value. Sentinel-gating restricts the sync to
          the one-time prefill->decode transition (when the pool is
          still at its initial -1 sentinel) and skips it on subsequent
          decode steps where the pool is the canonical state.

        Pre-capture-hoistable. Runs OUTSIDE the captured region of
        write_decode_batched; 6B.2's vLLM hook calls it on every writer
        at step entry (sentinel-gated; cheap when no slots are pristine).
        """
        if self._seq_pos_pool is None:
            raise RuntimeError(
                "_sync_pool_counters_from_states before _lazy_alloc"
            )
        # Resolve slot -> seq_state by scanning the dict (slot count
        # is bounded by _max_active_slots ~ 8, so this is cheap).
        slot_to_state = {}
        for sid, st in self._seq_states.items():
            slot_to_state[st.slot_idx] = st
        for slot in slot_idx_list:
            slot_int = int(slot)
            st = slot_to_state.get(slot_int)
            if st is None:
                # Slot pool entry without a SeqState shouldn't happen for
                # a valid decode call (the impl resolved slot from a live
                # seq_id). Defensive: skip; the next legacy write would
                # repopulate.
                continue
            # Sentinel gate: only sync when the slot's decode-side state
            # is pristine. -1 in k_stage_block_id_pool == "decode hasn't
            # written this slot yet"; we copy the prefill state in once
            # at the transition.
            if int(self._k_stage_block_id_pool[slot_int].item()) != -1:
                continue
            self._seq_pos_pool[slot_int] = int(st.seq_pos)
            self._k_stage_count_pool[slot_int] = int(st.k_stage_count)
            self._k_stage_block_id_pool[slot_int] = int(st.k_stage_block_id)

    def _writeback_pool_counters_to_states(self, slot_idx_list: list) -> None:
        """Phase 6B.1 — opposite direction: pull device-side counters
        BACK to SeqState Python ints, so legacy paths (verify scripts,
        introspection) read up-to-date values.

        Pre-capture-hoistable. The captured region writes to the pool
        tensors in-place; this just exposes those updates to legacy
        callers. For graph-capture (6B.3) this can be moved into a
        post-capture hook or skipped entirely if no legacy read fires.
        """
        if self._seq_pos_pool is None:
            return
        slot_to_state = {}
        for sid, st in self._seq_states.items():
            slot_to_state[st.slot_idx] = st
        # Single CPU sync per pool tensor (one .cpu().tolist() each),
        # not per slot.
        seq_pos_cpu = self._seq_pos_pool.cpu().tolist()
        k_stage_count_cpu = self._k_stage_count_pool.cpu().tolist()
        k_stage_block_id_cpu = self._k_stage_block_id_pool.cpu().tolist()
        for slot in slot_idx_list:
            st = slot_to_state.get(int(slot))
            if st is None:
                continue
            st.seq_pos = int(seq_pos_cpu[int(slot)])
            st.k_stage_count = int(k_stage_count_cpu[int(slot)])
            st.k_stage_block_id = int(k_stage_block_id_cpu[int(slot)])

    def write_decode_batched(
        self,
        key: "torch.Tensor",            # (B, H, D) bf16
        value: "torch.Tensor",          # (B, H, D) bf16
        kv_cache: "torch.Tensor",       # (2, NB, BS, H, D) uint8
        slot_mapping: "torch.Tensor",   # (B,) long — global slots
        slot_idx_t: "torch.Tensor",     # (B,) long — pool slots, pre-resolved
        *,
        pre_synced: bool = False,
    ) -> None:
        """Phase 6B.1 — graph-capture-friendly decode write.

        Processes ALL B sequences uniformly. ONE new token per sequence
        (the standard decode shape). No `.item()` calls in the captured
        region. No per-call dict lookups. Pool counters live on device.

        Pipeline:
          1. (PRE-CAPTURE) Sync per-slot SeqState ints -> device pools
             — SKIPPED when pre_synced=True (Phase 6B.2 hook owns it).
          2. (CAPTURED) BF16 K/V backing scatter via advance indexing.
          3. (CAPTURED) V quantization vectorized over B.
          4. (CAPTURED) K protect channel gather + scatter.
          5. (CAPTURED) K staging unconditional update + re-quantize.
             Block-full mask gates kv_cache + k_scale/k_xmin scatter
             via torch.where read-modify-write.
          6. (PRE-CAPTURE) Sync device pools -> SeqState ints for
             legacy introspection — SKIPPED when pre_synced=True
             (callers that want introspection trigger it explicitly).

        Math is bit-equivalent to looped `writer.write(seq_id=...)` for
        the decode shape. Verified by
        verify_phase6_b_pre5_write_equiv.py.

        Args:
          pre_synced: Phase 6B.2 — when True, the caller (the install_
            int4_protected_precapture_hook) has already synced this
            writer's pool counters from SeqState ints for this step.
            The method skips its own pre/post sync. Captured region
            is the same op chain; only the bookkeeping wrappers differ.
        """
        if not self._allocated:
            self._lazy_alloc(kv_cache)
        if key.shape != value.shape:
            raise ValueError(
                f"key shape {tuple(key.shape)} != value shape {tuple(value.shape)}"
            )
        if key.ndim != 3 or key.shape[1:] != (self.H, self.D):
            raise ValueError(
                f"key shape {tuple(key.shape)} != expected (B, {self.H}, {self.D})"
            )
        B = key.shape[0]
        if slot_mapping.shape != (B,):
            raise ValueError(
                f"slot_mapping shape {tuple(slot_mapping.shape)} != ({B},)"
            )
        if slot_idx_t.shape != (B,):
            raise ValueError(
                f"slot_idx_t shape {tuple(slot_idx_t.shape)} != ({B},)"
            )

        # =============== PRE-CAPTURE REGION (host-sync OK) ================
        # The pre-capture region performs Python-side resolution (seq_id ->
        # slot, overflow guard) and is HOISTABLE OUTSIDE the captured
        # graph by 6B.2's vLLM hook. The AST + runtime capture-safety
        # checker treats this region as exempt from the "no host sync"
        # rule.
        #
        # Phase 6B.2: when pre_synced=True the caller has already synced
        # this writer's pool counters AND ensured SeqStates exist. We
        # still need slot_idx_list for the overflow guard, but the
        # _sync_pool_counters_from_states + _writeback calls are skipped.
        # The captured region's op chain is unchanged.
        #
        # Phase 6B.3 (Option X) — Capture-safe gating:
        # vLLM 0.7.3 V0's `model_runner.capture_model` captures the
        # ENTIRE forward inside graph context, bypassing our 6B.2 hook
        # which only wraps `execute_model` (the production-runtime
        # entry point). During the V0 capture phase, this code runs
        # INSIDE the captured stream, so host syncs are forbidden.
        # We gate ALL pre-capture / post-capture host work on
        # `_in_cuda_graph_capture()`:
        #   - capture mode (engine init synthetic forwards):
        #     skip slot_idx_list materialization; skip sync; skip
        #     overflow guard; skip writeback. Persistent buffer
        #     addresses are stable; values populated by the hook
        #     at production replay time.
        #   - production-eager mode: full pre/post host work as
        #     before. Bit-equivalent to 6B.1 + 6B.2 production.
        in_capture = _in_cuda_graph_capture()
        slot_idx_list = None  # only used in non-capture path
        if not in_capture:
            # CAPTURE-EXEMPT: pre-capture-hoistable slot-idx materialization.
            slot_idx_list = slot_idx_t.cpu().tolist()  # B small ints; coalesced
            if not pre_synced:
                self._sync_pool_counters_from_states(slot_idx_list)

            # Overflow guard runs Python-side from the synced SeqState ints
            # (cheap dict lookup; no captured-region access). Pre-capture-
            # hoistable.
            # Phase 6C: skip mode has a (1,1,H,D) stub pool — the overflow
            # check would always fire. The kernel doesn't read the pool
            # anyway, so there's nothing to overflow. Skip the guard.
            if not self._bf16_backing_skipped:
                max_S = self._bf16_k_backing_pool.shape[1]
                for _slot in slot_idx_list:
                    # CAPTURE-EXEMPT: pre-capture overflow guard.
                    if int(self._seq_pos_pool[_slot].item()) >= max_S:
                        raise RuntimeError(
                            f"bf16 backing overflow at slot={_slot}: "
                            f"seq_pos={int(self._seq_pos_pool[_slot].item())} "
                            f">= max_seqlen={max_S}. Bump "
                            f"${_BF16_BACKING_MAX_SEQLEN_ENV}."
                        )

        # ================ CAPTURED REGION (no host sync) =================
        # Every op below this marker MUST be device-only. The AST + runtime
        # capture-safety verifier asserts zero .item() / .cpu() / .tolist()
        # / Python dict-lookup occurrences in this region.
        # CAPTURED-REGION-START

        # Phase 6E dispatch: when PHASE6E_FUSED_WRITER=1, route to the
        # fused implementation (currently a byte-identical Python
        # reference; future a custom CUDA kernel) and skip the inline
        # op chain. Both paths produce identical state mutations on
        # kv_cache + writer pools — verified in
        # verify_phase6e_fused_byte_eq.py.
        _phase6e_use_fused = _fused_writer_enabled()
        if _phase6e_use_fused:
            _phase6e_fused_decode_write_python_ref(
                self, key, value, slot_idx_t, slot_mapping, kv_cache,
            )

        dtype = self.sidecar_dtype
        BS = self.BS
        D = self.D
        H = self.H
        half_D = D // 2

        if _phase6e_use_fused:
            # Fused path already wrote everything — skip the inline op chain.
            pass
        else:
            self._write_decode_batched_captured_inline_body(
                key, value, slot_idx_t, slot_mapping, kv_cache, B,
            )

        # CAPTURED-REGION-END
        # ============== POST-CAPTURE REGION (host-sync OK) ===============
        # (continued below; unchanged)

        # CAPTURE-EXEMPT: post-capture writeback.
        if not in_capture and not pre_synced:
            self._writeback_pool_counters_to_states(slot_idx_list)
        return

    def _write_decode_batched_captured_inline_body(
        self, key, value, slot_idx_t, slot_mapping, kv_cache, B,
    ):
        """Phase 6E factor: the original inline captured region body
        (lines 1217-1372 in this file as of Phase 6C). Kept verbatim
        for the PHASE6E_FUSED_WRITER=0 fallback path and as the
        byte-equality reference the CPU verifier compares against.

        State mutations are identical to
        _phase6e_fused_decode_write_python_ref. The two functions
        should produce byte-equal results for identical inputs.
        """
        dtype = self.sidecar_dtype
        BS = self.BS
        D = self.D
        H = self.H
        half_D = D // 2

        if key.dtype != dtype:
            key = key.to(dtype)
        if value.dtype != dtype:
            value = value.to(dtype)

        slot_mapping = slot_mapping.long()
        active_mask_t = (slot_mapping >= 0)                       # (B,) bool device

        # For inactive (-1) slots, we still need valid indices for the
        # advance-indexed scatters to not crash; we clamp the slot/pos
        # to 0 and rely on torch.where masking to make the writes no-ops.
        # In practice decode never has -1 padding in V0 (block_tables
        # has one row per active seq), but this preserves graph safety.
        safe_slot_mapping = torch.where(
            active_mask_t, slot_mapping, torch.zeros_like(slot_mapping),
        )
        block_ids = safe_slot_mapping // BS                       # (B,) long
        positions = safe_slot_mapping %  BS                       # (B,) long

        # ===== BF16 K/V backing scatter (per-seq, indexed by slot_idx + seq_pos) =====
        # Phase 6C: kernel-verified that the int4_packed flash_attn path
        # never reads bf16_k_batch / bf16_v_batch; the pool was dead
        # memory + scatter-bandwidth on every decode step. Skip the
        # scatters in skip mode; seq_pos_pool still increments so the
        # rest of the state stays correct.
        if not self._bf16_backing_skipped:
            seq_pos_t = self._seq_pos_pool[slot_idx_t].long()     # (B,) long
            # Advance-indexed scatter — same bytes as legacy
            # state.bf16_k_backing[0, seq_pos] = real_key for each slot.
            # Inactive rows still write but to position 0 of slot 0
            # (harmless under matched active_mask gating on the read side).
            self._bf16_k_backing_pool[slot_idx_t, seq_pos_t] = key
            self._bf16_v_backing_pool[slot_idx_t, seq_pos_t] = value
        # Update seq_pos counter (active mask gates inactive seqs).
        self._seq_pos_pool.index_add_(
            0, slot_idx_t, active_mask_t.to(torch.int32),
        )

        # ===== V quantization vectorized over B (same math as legacy) =====
        if _bf16_v_mode():
            if getattr(self, "_v_bf16_ext", None) is None:
                self._v_bf16_ext = torch.zeros(
                    (self.NB, BS, H, D), dtype=dtype, device=kv_cache.device,
                )
            self._v_bf16_ext[block_ids, positions] = value
        else:
            v_grouped = value.float().view(
                B, H, self.v_n_groups, self.v_group_size,
            )
            v_max = v_grouped.amax(dim=-1)
            v_min = v_grouped.amin(dim=-1)
            v_scale = ((v_max - v_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)
            q_v = ((v_grouped - v_min.unsqueeze(-1)) / v_scale.unsqueeze(-1)) \
                .round().clamp(0, 15).to(torch.uint8)
            q_v_flat = q_v.view(B, H, D)
            v_packed = (q_v_flat[..., 0::2] & 0x0F) | ((q_v_flat[..., 1::2] & 0x0F) << 4)
            kv_cache[1, block_ids, positions, :, :half_D] = v_packed
            self.v_scale_ext[block_ids, positions] = v_scale.to(dtype)
            self.v_xmin_ext [block_ids, positions] = v_min.to(dtype)

        # ===== K protect gather + scatter (same as legacy) =====
        protect_idx = self.protected_d_per_head.unsqueeze(0).expand(B, -1, -1)
        k_protect = torch.gather(key, dim=-1, index=protect_idx)
        self.k_protect_ext[block_ids, positions] = k_protect

        # ===== K staging: unconditional update + conditional finalize =====
        # Detect block boundary via device tensor compare.
        prior_block_id = self._k_stage_block_id_pool[slot_idx_t]   # (B,) long
        is_new_block = (block_ids != prior_block_id)               # (B,) bool

        # Unconditional masked-zero of the staging slice on new-block
        # transition. keep_mask = ~is_new_block; where keep_mask is
        # True, preserve current k_stage; else zero.
        keep_mask = (~is_new_block).view(B, 1, 1, 1)               # (B,1,1,1)
        current_k_stage = self._k_stage_pool[slot_idx_t]           # (B, BS, H, D)
        cleared_k_stage = torch.where(
            keep_mask, current_k_stage, torch.zeros_like(current_k_stage),
        )
        # Place new token at this seq's position within the block.
        batch_arange = torch.arange(B, device=kv_cache.device)
        cleared_k_stage[batch_arange, positions] = key
        # Scatter back to the pool — pool now reflects the new state.
        self._k_stage_pool[slot_idx_t] = cleared_k_stage

        # Update bookkeeping (in-place, device-side).
        # For inactive slots, keep prior values via masked update.
        new_block_id = torch.where(
            active_mask_t, block_ids, self._k_stage_block_id_pool[slot_idx_t],
        )
        self._k_stage_block_id_pool[slot_idx_t] = new_block_id
        new_count = (positions + 1).to(torch.int32)
        cur_count = self._k_stage_count_pool[slot_idx_t]
        self._k_stage_count_pool[slot_idx_t] = torch.where(
            active_mask_t, new_count, cur_count,
        )

        # Unconditional re-quantize the staging pool for all B slots.
        # For partial blocks: scale/xmin include the unfilled zeros
        # (matching legacy _splice_k_partial_tail_batched_*).
        # For full blocks (positions == BS-1, count==BS after write):
        # the staging pool holds all BS real tokens accumulated over
        # BS decode steps; scale/xmin equal what legacy
        # _finalize_k_group_from_state would compute.
        buf_f = cleared_k_stage.float()                            # (B, BS, H, D)
        x_max = buf_f.amax(dim=1)                                  # (B, H, D)
        x_min = buf_f.amin(dim=1)
        scale = ((x_max - x_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)
        q = ((buf_f - x_min.unsqueeze(1)) / scale.unsqueeze(1)) \
            .round().clamp(0, 15).to(torch.uint8)                  # (B, BS, H, D)
        packed = (q[..., 0::2] & 0x0F) | ((q[..., 1::2] & 0x0F) << 4)  # (B, BS, H, half_D)

        # Block-full detection: this write completed the block iff
        # positions[i] == BS-1 AND active. Only on full do we commit
        # to kv_cache + k_scale_ext + k_xmin_ext.
        block_full_mask = ((positions + 1) == BS) & active_mask_t  # (B,) bool

        # Read-modify-write under block_full_mask. Inactive / partial:
        # writes back current value (no-op). Full: writes packed.
        full_mask_kv = block_full_mask.view(B, 1, 1, 1)            # for kv_cache packed
        full_mask_ext = block_full_mask.view(B, 1, 1)              # for (H, D) externals

        current_kv_packed = kv_cache[0, block_ids][..., :half_D]   # (B, BS, H, half_D) uint8
        new_kv_packed = torch.where(full_mask_kv, packed, current_kv_packed)
        kv_cache[0, block_ids, :, :, :half_D] = new_kv_packed

        current_k_scale = self.k_scale_ext[block_ids]              # (B, H, D)
        current_k_xmin  = self.k_xmin_ext [block_ids]
        scale_dt = scale.to(dtype)
        xmin_dt  = x_min.to(dtype)
        self.k_scale_ext[block_ids] = torch.where(
            full_mask_ext, scale_dt, current_k_scale,
        )
        self.k_xmin_ext [block_ids] = torch.where(
            full_mask_ext, xmin_dt,  current_k_xmin,
        )

        # When the block fills, legacy sets state.k_stage_count = 0.
        # The pool counter equivalent: set to 0 for slots whose
        # block_full_mask fired.
        self._k_stage_count_pool[slot_idx_t] = torch.where(
            block_full_mask,
            torch.zeros_like(self._k_stage_count_pool[slot_idx_t]),
            self._k_stage_count_pool[slot_idx_t],
        )
        # End of inline body. Post-capture writeback is handled by the
        # caller (write_decode_batched) outside this function.

    def _finalize_k_full_blocks_batched(
        self,
        *,
        state: "SeqState",
        kv_cache,
        real_key,
        block_ids,
        positions,
        inverse,
        unique_blocks,
        full_mask,
        n_full_blocks,
    ):
        """Batch-finalize all blocks for which this write() supplied
        the full BS tokens. Equivalent to running _finalize_k_group N
        times but in one set of CUDA ops.

        `state` is THIS seq's SeqState — used only to detect if any
        of the just-finalized blocks was the staging block for this seq
        (in which case the staging count is reset to 0).
        """
        BS = self.BS
        H = self.H
        D = self.D
        half_D = D // 2
        dtype = self.sidecar_dtype

        full_block_ids = unique_blocks[full_mask]                    # (n_full,) sorted ascending
        in_full_mask = full_mask[inverse]                            # (n_real,) bool
        keys_for_full = real_key[in_full_mask]                       # (n_full * BS, H, D)
        block_ids_for_full = block_ids[in_full_mask]
        positions_for_full = positions[in_full_mask]

        # Sort by (block_id, position) so the BS tokens of each full
        # block end up contiguous and slot-ordered.
        # combined_key = block_id * BS + position
        combined = block_ids_for_full * BS + positions_for_full
        sort_idx = combined.argsort()
        keys_sorted = keys_for_full[sort_idx]                        # (n_full * BS, H, D)
        keys_grouped = keys_sorted.view(n_full_blocks, BS, H, D)

        # Quantization math, vectorized across all full blocks.
        buf_f = keys_grouped.float()
        x_max = buf_f.amax(dim=1)                                    # (n_full, H, D)
        x_min = buf_f.amin(dim=1)
        scale = ((x_max - x_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)
        q = ((buf_f - x_min.unsqueeze(1)) / scale.unsqueeze(1)) \
            .round().clamp(0, 15).to(torch.uint8)                    # (n_full, BS, H, D)
        packed = (q[..., 0::2] & 0x0F) | ((q[..., 1::2] & 0x0F) << 4)
        # packed: (n_full, BS, H, D/2)

        kv_cache[0, full_block_ids, :, :, :half_D] = packed
        self.k_scale_ext[full_block_ids] = scale.to(dtype)
        self.k_xmin_ext [full_block_ids] = x_min.to(dtype)

        # If THIS seq's staging buffer was tracking one of these now-
        # finalized blocks, mark its count as 0 (block is done; next
        # partial fills state.k_stage afresh). Done on CPU because
        # state.k_stage_block_id is a Python int.
        if state.k_stage_block_id in full_block_ids.cpu().tolist():
            state.k_stage_count = 0

    def _stage_k_partial_blocks(
        self,
        *,
        state: "SeqState",
        kv_cache,
        real_key,
        block_ids,
        positions,
        unique_blocks,
        full_mask,
    ):
        """Place tokens belonging to partial (count < BS) blocks into THIS
        seq's staging buffer (`state.k_stage`). Process partial blocks in
        sequence (first-appearance) order so state.k_stage_block_id ends
        at the seq's true last block.

        In practice the partial-block count per write() is small:
          - 1 (the sequence's current trailing partial)
          - sometimes 2 (one continuing from prior staging + one new tail)
        So this small Python loop is not the bottleneck.
        """
        BS = self.BS
        partial_set = set(unique_blocks[~full_mask].cpu().tolist())
        if not partial_set:
            return

        # Walk block_ids in appearance order to find unique partials.
        block_ids_cpu = block_ids.cpu().tolist()
        positions_cpu = positions.cpu()

        seen: set = set()
        ordered_partials: list = []
        for b in block_ids_cpu:
            if b in seen:
                continue
            seen.add(b)
            if b in partial_set:
                ordered_partials.append(b)

        for pb in ordered_partials:
            # Mask within real_key for this partial block.
            pb_mask = (block_ids == pb)
            keys_for_pb = real_key[pb_mask]                          # (cnt, H, D)
            positions_for_pb = positions[pb_mask]                    # (cnt,) long

            # Block-boundary detection in THIS seq's staging.
            if pb != state.k_stage_block_id:
                state.k_stage_block_id = pb
                state.k_stage.zero_()
                state.k_stage_count = 0

            # Place these tokens at their intra-block positions.
            state.k_stage[positions_for_pb] = keys_for_pb
            max_pos = int(positions_for_pb.max().item()) + 1
            if max_pos > state.k_stage_count:
                state.k_stage_count = max_pos

            # If now full, finalize from this seq's staging buffer.
            if state.k_stage_count == BS:
                self._finalize_k_group_from_state(state, kv_cache, pb)
                state.k_stage_count = 0

    def _finalize_k_group(
        self,
        kv_cache: "torch.Tensor",
        block_id: int,
    ) -> None:
        """Legacy single-seq finalizer. Routes through the default
        SeqState's k_stage. Kept for backward compat with any external
        callers; internal helpers now use _finalize_k_group_from_state.
        """
        s = self._seq_states.get(self.DEFAULT_SEQ_ID)
        if s is None:
            raise RuntimeError("_finalize_k_group called before _lazy_alloc")
        self._finalize_k_group_from_state(s, kv_cache, block_id)

    def _finalize_k_group_from_state(
        self,
        state: "SeqState",
        kv_cache: "torch.Tensor",
        block_id: int,
    ) -> None:
        """Quantize the full staging buffer (BS, H, D) on `state.k_stage`
        and write packed nibbles + scale + xmin to the cache + externals
        for `block_id`."""
        D = self.D
        half_D = D // 2

        buf_f = state.k_stage.float()                   # (BS, H, D)
        x_max = buf_f.amax(dim=0)                       # (H, D)
        x_min = buf_f.amin(dim=0)
        scale = ((x_max - x_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)

        q = ((buf_f - x_min.unsqueeze(0)) / scale.unsqueeze(0)) \
            .round().clamp(0, 15).to(torch.uint8)       # (BS, H, D)
        packed = (q[..., 0::2] & 0x0F) | ((q[..., 1::2] & 0x0F) << 4)  # (BS, H, D/2)

        # Write nibbles to all BS slots of this block.
        kv_cache[0, block_id, :, :, :half_D] = packed
        # Write per-(h, d) scale + xmin to externals (per-layer, shared).
        self.k_scale_ext[block_id] = scale.to(self.sidecar_dtype)
        self.k_xmin_ext [block_id] = x_min.to(self.sidecar_dtype)

    # ------------------------------------------------------------------
    # Introspection helpers (for verify scripts).
    # ------------------------------------------------------------------

    def get_bf16_backing_slice(self, S: int, *, seq_id: Any = None):
        """Phase 5B.4c.3 fix (a): return (bf16_K, bf16_V) of shape
        (1, S, H, D) for the kernel's positional K/V args.

        Phase 5B.6 step 2: optional `seq_id` selects which sequence's
        backing to slice. Default = DEFAULT_SEQ_ID (legacy single-seq).

        Positions [0..seq_pos-1] hold the real bf16 K/V values written
        so far in this sequence. Positions [seq_pos..S-1] are zeros
        (initialized) and unattended (cache_seqlens masks them).

        Phase 6C: skip mode returns a stride-0 broadcast view of the
        (1, 1, H, D) stub — kernel sees logical (1, S, H, D); never
        reads since Is_int4kv_packed=true.
        """
        if seq_id is None:
            seq_id = self.DEFAULT_SEQ_ID
        if self._bf16_backing_skipped:
            stub_k = self._bf16_k_backing_pool                # (1, 1, H, D)
            stub_v = self._bf16_v_backing_pool                # (1, 1, H, D)
            return stub_k.expand(1, S, self.H, self.D), stub_v.expand(1, S, self.H, self.D)
        state = self._seq_states.get(seq_id)
        if state is None or state.bf16_k_backing is None:
            raise RuntimeError(
                f"bf16 backing not allocated for seq_id={seq_id!r}. "
                f"Call write() first."
            )
        if S > state.bf16_k_backing.shape[1]:
            raise RuntimeError(
                f"requested backing slice S={S} > allocated {state.bf16_k_backing.shape[1]}"
            )
        return state.bf16_k_backing[:, :S], state.bf16_v_backing[:, :S]

    def get_state(self) -> Dict[str, Any]:
        """Snapshot of allocator + streaming state. Used by 5B.4c.1
        verify to assert correct sidecar population without running the
        read path."""
        return {
            "layer_idx":         self.layer_idx,
            "allocated":         self._allocated,
            "NB":                self.NB,
            "BS":                self.BS,
            "H":                 self.H,
            "D":                 self.D,
            "n_protect":         self.n_protect,
            "v_group_size":      self.v_group_size,
            "v_n_groups":        self.v_n_groups,
            "k_stage_count":     self.k_stage_count,
            "k_stage_block_id":  self.k_stage_block_id,
            "seq_pos":           self.seq_pos,
        }

    def get_packed_view(
        self,
        block_ids: "torch.Tensor",   # (n_blocks,) long
        kv_cache: "torch.Tensor",    # (2, NB, BS, H, D) uint8
    ) -> Dict[str, Any]:
        """Build a contiguous packed-K + packed-V view from the gathered
        blocks. Used by the 5B.4c.2 read path (and 5B.4c.1 verify) to
        prep the kernel input.

        Does NOT include the hybrid partial-tail splice — that's
        applied by the read path after this returns the gathered view.
        """
        if not self._allocated:
            raise RuntimeError("PagedKVWriter.get_packed_view called before any write()")
        BS = self.BS
        D = self.D
        half_D = D // 2

        # Gather paged blocks: (n, BS, H, D) uint8.
        k_blocks = kv_cache[0][block_ids]
        v_blocks = kv_cache[1][block_ids]
        n_blocks = block_ids.shape[0]
        S = n_blocks * BS

        # Extract nibbles (first D/2 bytes of each slot).
        k_nibbles = k_blocks[..., :half_D].contiguous().view(1, S, self.H, half_D)
        v_nibbles = v_blocks[..., :half_D].contiguous().view(1, S, self.H, half_D)

        # Gather externals.
        k_scale = self.k_scale_ext[block_ids].unsqueeze(0)         # (1, n, H, D)
        k_xmin  = self.k_xmin_ext [block_ids].unsqueeze(0)
        k_prot  = self.k_protect_ext[block_ids].view(1, S, self.H, self.n_protect)
        v_scale = self.v_scale_ext[block_ids].view(1, S, self.H, self.v_n_groups)
        v_xmin  = self.v_xmin_ext [block_ids].view(1, S, self.H, self.v_n_groups)

        result: Dict[str, Any] = {
            "k_int4":         k_nibbles,
            "k_scale":        k_scale,
            "k_xmin":         k_xmin,
            "k_protect_bf16": k_prot,
            "protect_slot":   self.protect_slot,
            "n_protect":      self.n_protect,
            "group_size":     BS,
            "v_int4":         v_nibbles,
            "v_scale":        v_scale,
            "v_xmin":         v_xmin,
            "v_group_size":   self.v_group_size,
            "n_blocks":       n_blocks,
            "S":              S,
        }
        # Debug bf16-V mode: surface the gathered bf16 V too. The read path
        # uses it instead of v_int4/v_scale/v_xmin when this is set.
        if _bf16_v_mode() and getattr(self, "_v_bf16_ext", None) is not None:
            result["v_bf16"] = self._v_bf16_ext[block_ids].view(1, S, self.H, self.D)
        return result

    def get_packed_view_batched(
        self,
        block_ids_batched: "torch.Tensor",   # (B, n_blocks_max) long; padded slots = 0
        kv_cache: "torch.Tensor",            # (2, NB, BS, H, D) uint8
    ) -> Dict[str, Any]:
        """Phase 6 v2 (Option A): batched-gather for multi-seq decode.

        Replaces B separate `get_packed_view` calls with ONE set of CUDA
        advanced-index ops that gathers ALL B sequences' paged blocks +
        sidecars simultaneously.

        Per-seq sequences may have different `n_blocks_used`. The caller
        pads `block_ids_batched[i]` to a common `n_blocks_max` length —
        unused trailing slots should point at block 0 (or any valid
        block) since `cache_seqlens` masks the padded positions in the
        kernel anyway.

        Returns:
          dict with batched tensors of shapes:
            k_int4:         (B, S, H, D/2)             uint8
            k_scale:        (B, n_blocks_max, H, D)    bf16
            k_xmin:         (B, n_blocks_max, H, D)    bf16
            k_protect_bf16: (B, S, H, n_protect)       bf16
            protect_slot:   (H, D)                     int8 (shared)
            v_int4:         (B, S, H, D/2)             uint8
            v_scale:        (B, S, H, v_n_groups)      bf16
            v_xmin:         (B, S, H, v_n_groups)      bf16
          where S = n_blocks_max * BS.

        The caller still applies the K partial-tail splice per-seq
        (one per sequence with a trailing partial group) on this
        batched view, writing into the corresponding slice.
        """
        if not self._allocated:
            raise RuntimeError("get_packed_view_batched before _lazy_alloc")
        if block_ids_batched.ndim != 2:
            raise ValueError(
                f"block_ids_batched shape {tuple(block_ids_batched.shape)} != (B, n_blocks_max)"
            )
        B, n_blocks_max = block_ids_batched.shape
        BS = self.BS
        D = self.D
        half_D = D // 2
        H = self.H
        S = n_blocks_max * BS

        block_ids_long = block_ids_batched.long()

        # Gather paged blocks in ONE shot.
        # kv_cache[0]: (NB, BS, H, D). Indexed with (B, n_blocks_max) →
        # (B, n_blocks_max, BS, H, D).
        k_blocks = kv_cache[0][block_ids_long]
        v_blocks = kv_cache[1][block_ids_long]

        # Slice nibbles (first D/2 bytes per slot) and flatten block+slot
        # dims to S.
        k_nibbles = k_blocks[..., :half_D].contiguous().view(B, S, H, half_D)
        v_nibbles = v_blocks[..., :half_D].contiguous().view(B, S, H, half_D)

        # Gather sidecars in ONE shot too.
        k_scale = self.k_scale_ext[block_ids_long]                              # (B, n_blocks_max, H, D)
        k_xmin  = self.k_xmin_ext [block_ids_long]                              # (B, n_blocks_max, H, D)
        k_prot  = self.k_protect_ext[block_ids_long].view(B, S, H, self.n_protect)
        v_scale = self.v_scale_ext[block_ids_long].view(B, S, H, self.v_n_groups)
        v_xmin  = self.v_xmin_ext [block_ids_long].view(B, S, H, self.v_n_groups)

        result: Dict[str, Any] = {
            "k_int4":         k_nibbles,
            "k_scale":        k_scale,
            "k_xmin":         k_xmin,
            "k_protect_bf16": k_prot,
            "protect_slot":   self.protect_slot,
            "n_protect":      self.n_protect,
            "group_size":     BS,
            "v_int4":         v_nibbles,
            "v_scale":        v_scale,
            "v_xmin":         v_xmin,
            "v_group_size":   self.v_group_size,
            "n_blocks_max":   n_blocks_max,
            "S":              S,
        }
        if _bf16_v_mode() and getattr(self, "_v_bf16_ext", None) is not None:
            result["v_bf16"] = self._v_bf16_ext[block_ids_long].view(B, S, H, D)
        return result

    def get_bf16_backing_batched(
        self,
        seq_ids: "list",     # list of seq_id, length B
        S_padded: int,
    ):
        """Phase 6 v2: backed bf16 K/V batched for the kernel.

        Phase 6 v2 Option B pre-flight (B-pre-1): now resolves seq_ids
        to slot indices (Python-side dict lookup) and delegates to
        `get_bf16_backing_batched_by_slots`, which does ONE device
        gather from the pool tensors. Output is shape-identical to the
        prior torch.stack path; the new path is graph-capture-friendly
        (the captured region only sees the device-side slot tensor +
        the single gather).
        """
        if not self._allocated:
            raise RuntimeError("get_bf16_backing_batched before _lazy_alloc")
        if not seq_ids:
            raise ValueError("get_bf16_backing_batched needs B >= 1 seq_ids")
        slot_idx_list = self.slot_indices_for(seq_ids)
        slot_idx_t = torch.tensor(
            slot_idx_list,
            dtype=torch.long,
            device=self._bf16_k_backing_pool.device,
        )
        return self.get_bf16_backing_batched_by_slots(slot_idx_t, S_padded)
