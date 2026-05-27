"""Phase 5B.2/5B.3 — Int4Protected attention backend + impl.

5B.2 v0: post-init class-swap install (KEPT as fallback).
5B.3a v0: init-time selection via CacheConfig + get_attn_backend hooks.

Behavior is still pure DELEGATE at this phase — Phase 5B.4 will insert
real packed-K kernel calls. The goal of 5B.2/5B.3a is to prove we can
plug into vLLM's attention pipeline at the right places (impl class +
backend class + config validation) without breaking generation.

Scope clarification vs the design doc:
  - Design doc Phase 5B.2 envisioned "register a new attention backend
    with vLLM's backend selection". The probe at commit 946dcd5
    revealed that `kv_cache_dtype="int4_protected"` is rejected by
    `CacheConfig` validation. Patching that validation is more invasive
    than the 5B.2 skeleton needs. Moved to Phase 5C.
  - 5B.2 instead: subclass `FlashAttentionImpl`, install via post-init
    class swap on each layer's `.impl` instance. Gets us the same
    surface for Phase 5B.4 work without touching CacheConfig.

Probe evidence (commit 946dcd5):
  - vLLM 0.7.3 FA backend: `vllm.attention.backends.flash_attn.FlashAttentionImpl`
  - Each leaf Attention layer has `.impl: FlashAttentionImpl` (28 instances on Qwen2.5-7B)
  - FlashAttentionImpl MRO: [FlashAttentionImpl, AttentionImpl, ABC, Generic, object]
  - No `__slots__` apparent → instance-level `__class__` swap is safe.

Install pattern: same shape as Phase 5A's wrap_attention_forward, but
operates on `module.impl` not `module.forward`. RAII-style teardown.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore

# vLLM imports may be unavailable in some test environments — guard them.
try:
    from vllm.attention.backends.flash_attn import (
        FlashAttentionBackend,
        FlashAttentionImpl,
    )
    _VLLM_FA_AVAILABLE = True
except ImportError:  # pragma: no cover
    FlashAttentionBackend = None  # type: ignore
    FlashAttentionImpl = None  # type: ignore
    _VLLM_FA_AVAILABLE = False

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Decode-path profiler (Phase 6 v2 Option D step 3 prep).
#
# Off by default. A bench harness sets `_DECODE_PROFILER = DecodeProfiler()`
# before generation; the read-path wraps each phase with `_maybe_region`,
# which is a no-op singleton context when the profiler is None.
#
# Records BOTH CPU (perf_counter) and GPU (cuda events) timings per phase.
# - CPU time captures Python dispatch overhead + any implicit host syncs
#   (.item(), .cpu(), .tolist()).
# - GPU time (after a final synchronize) captures actual kernel latency.
# - If cpu_us >> gpu_us, the phase is Python-bound (target for fusion).
# - If cpu_us ≈ gpu_us, the phase is GPU-bound (target for kernel work).
# ----------------------------------------------------------------------

import time as _time_mod


class _NullRegion:
    """Singleton no-op context. Used when profiling is disabled — keeps
    the production path at a single None check + one attribute load
    per phase."""
    def __enter__(self):  return self
    def __exit__(self, *a):  return None

_NULL_REGION = _NullRegion()


class DecodeProfiler:
    """Records per-phase CPU + GPU timings across all calls to the
    instrumented decode read path. Bench harness lifecycle:
        prof = DecodeProfiler()
        backend_install._DECODE_PROFILER = prof
        llm.generate(...)
        backend_install._DECODE_PROFILER = None
        print(prof.summarize())
    """
    def __init__(self) -> None:
        # phase_name -> list[(cpu_us, ev_start, ev_end)]
        self.records: Dict[str, list] = {}

    def reset(self) -> None:
        self.records = {}

    def region(self, name: str) -> "_TimedRegion":
        return _TimedRegion(self, name)

    def _record(self, name: str, cpu_us: float, ev_start, ev_end) -> None:
        self.records.setdefault(name, []).append((cpu_us, ev_start, ev_end))

    def summarize(self) -> Dict[str, Dict[str, float]]:
        """Materialize per-phase aggregates. Syncs once to make all
        cuda events available for elapsed_time()."""
        if torch is not None and torch.cuda.is_available():
            torch.cuda.synchronize()
        out: Dict[str, Dict[str, float]] = {}
        for name, rec_list in self.records.items():
            if not rec_list:
                continue
            cpu = [r[0] for r in rec_list]
            gpu = [r[1].elapsed_time(r[2]) * 1e3 for r in rec_list]  # ms -> us
            out[name] = {
                "n_calls":      len(cpu),
                "cpu_us_total": sum(cpu),
                "cpu_us_mean":  sum(cpu) / len(cpu),
                "gpu_us_total": sum(gpu),
                "gpu_us_mean":  sum(gpu) / len(gpu),
                "cpu_us_max":   max(cpu),
                "gpu_us_max":   max(gpu),
            }
        return out


class _TimedRegion:
    """Context manager that records CPU wall + GPU latency for one phase
    invocation into a DecodeProfiler."""
    __slots__ = ("prof", "name", "t0", "ev_start", "ev_end")
    def __init__(self, prof: DecodeProfiler, name: str) -> None:
        self.prof = prof
        self.name = name
        self.t0 = 0.0
        self.ev_start = None
        self.ev_end = None
    def __enter__(self):
        self.ev_start = torch.cuda.Event(enable_timing=True)
        self.ev_end   = torch.cuda.Event(enable_timing=True)
        self.ev_start.record()
        self.t0 = _time_mod.perf_counter()
        return self
    def __exit__(self, *exc):
        cpu_us = (_time_mod.perf_counter() - self.t0) * 1e6
        self.ev_end.record()
        self.prof._record(self.name, cpu_us, self.ev_start, self.ev_end)
        return None


# Module-level toggle. None = profiling off (no overhead beyond an
# attribute load per phase). Bench harness flips this.
_DECODE_PROFILER: Optional[DecodeProfiler] = None


def _maybe_region(name: str):
    """Return either a real timed region (profiling on) or the singleton
    no-op (profiling off). One attribute load + one None check on the
    hot path."""
    p = _DECODE_PROFILER
    return p.region(name) if p is not None else _NULL_REGION


# ----------------------------------------------------------------------
# Int4ProtectedAttentionImpl — subclass with delegated forward.
# ----------------------------------------------------------------------

if _VLLM_FA_AVAILABLE:

    # 5B.4c.1: import PagedKVWriter lazily inside forward — keeps the
    # backend installable in environments where kv_policy is on PYTHONPATH
    # but the writer module has issues unrelated to the backend skeleton.

    class Int4ProtectedAttentionImpl(FlashAttentionImpl):
        """Phase 5B.2 skeleton subclass of FlashAttentionImpl.

        Phase 5B.4a-b: forward replication + uint8 storage shape.
        Phase 5B.4c.1: quantizing write path via PagedKVWriter (replaces
                       reshape_and_cache_flash). Read path still stock
                       FA → generation BROKEN. 5B.4c.2 restores it.

        We do NOT override __init__ — that lets the install function
        do an in-place class swap on existing FA-impl instances, which
        preserves all the state (head_size, num_heads, scale, etc.)
        that the engine wired up at init time.

        Per-instance attributes set by the installer:
          _phase5b_layer_idx: int — sequential index used to slice the
            per-model protect mask artifact.
        Per-instance attributes set lazily on first forward():
          _phase5b_paged_writer: PagedKVWriter — owns external sidecars
            and the K staging buffer for this layer.
        """

        # Sentinel for verify scripts to check. Bumped each sub-sub-phase.
        _phase5b_backend_marker = "5B.4c.3"

        # Class-level call counters (aggregate across all layer instances).
        # Reset via Int4ProtectedAttentionImpl.reset_call_stats().
        _call_stats: Dict[str, int] = {
            "prefill_calls":                          0,
            "decode_calls_packed":                    0,
            "decode_calls_fallback":                  0,
            "write_path_calls":                       0,
            "write_path_fallback":                    0,
            "write_decode_batched_calls":             0,  # Phase 6B.1 — refactored decode write path fired
            "write_decode_batched_via_hook_calls":    0,  # Phase 6B.2 — slot_idx_t came from pre-capture hook stash
            "write_decode_batched_via_capture_calls": 0,  # Phase 6B.3 Option X — call fired inside torch.cuda.graph() capture
            "write_legacy_loop_calls":                0,  # Phase 6B.1 — legacy partition+loop path fired
            "spec_decode_calls":                      0,
        }

        @classmethod
        def reset_call_stats(cls) -> None:
            for k in cls._call_stats:
                cls._call_stats[k] = 0

        @classmethod
        def get_call_stats(cls) -> Dict[str, int]:
            return dict(cls._call_stats)

        # Phase 6 v2 Option B pre-flight (B-pre-4): persistent index/scratch
        # buffers for the read path. Pre-allocated once per impl instance,
        # grown lazily if a larger B comes through. Pre-allocation makes
        # these tensors live at stable addresses across decode calls —
        # captured graphs can record those addresses once and replay.
        #
        # The buffers are populated each call via .copy_() (small DtoD copy
        # from a fresh fancy-indexed tensor) so the underlying memory is
        # the same; the values change per call but the address doesn't.
        def _ensure_index_bufs(self, B: int, device, dtype_long, dtype_i32):
            """Grow / allocate the persistent index buffers if needed.

            Returns the (B,)-sized slices ready for use this call. Slices
            are views into a (max_B,) backing buffer; max_B grows to the
            largest B ever seen on this impl (typically 8 at the ship
            target, ramping to vLLM's max-concurrency cap).
            """
            cur = getattr(self, "_phase5b_idx_max_B", 0)
            # NB: use `!=` (value equality), NOT `is not` (object identity).
            # `block_table.device` can return a fresh torch.device object per
            # call even when the actual device is the same — `is not` would
            # always be True and trigger a reallocation on EVERY call,
            # defeating the whole point of pre-allocation.
            existing_dev = getattr(self, "_phase5b_idx_dev", None)
            if cur < B or existing_dev is None or existing_dev != device:
                # (Re-)allocate. Pick a generous cap to avoid frequent regrowth.
                new_max = max(B, cur, 16)
                self._phase5b_slot_idx_buf      = torch.zeros(
                    (new_max,), dtype=dtype_long, device=device,
                )
                self._phase5b_batch_idx_arange  = torch.arange(
                    new_max, dtype=dtype_long, device=device,
                )
                self._phase5b_cache_seqlens_i32 = torch.zeros(
                    (new_max,), dtype=dtype_i32, device=device,
                )
                self._phase5b_idx_max_B  = new_max
                self._phase5b_idx_dev    = device
            return (
                self._phase5b_slot_idx_buf[:B],
                self._phase5b_batch_idx_arange[:B],
                self._phase5b_cache_seqlens_i32[:B],
            )

        def _ensure_protect_mask_bhd(self, B: int, writer):
            """(Re-)allocate the (B, H, D) int8 protect_mask buffer if
            needed. Content is per-model-frozen (writer.protect_mask is
            populated at _lazy_alloc), so we can fill it ONCE per max-B
            grow and never touch it again. Stable address across calls.
            """
            cur = getattr(self, "_phase5b_protect_mask_bhd_max_B", 0)
            existing_buf = getattr(self, "_phase5b_protect_mask_bhd_buf", None)
            need_realloc = (
                cur < B
                or existing_buf is None
                or existing_buf.device != writer.protect_mask.device
            )
            if need_realloc:
                new_max = max(B, cur, 16)
                self._phase5b_protect_mask_bhd_buf = (
                    writer.protect_mask.unsqueeze(0)
                    .expand(new_max, -1, -1)
                    .contiguous()
                )
                self._phase5b_protect_mask_bhd_max_B = new_max
            return self._phase5b_protect_mask_bhd_buf[:B]

        def _get_paged_writer(self, layer=None):
            """Lazy-construct the PagedKVWriter for this layer. The writer
            doesn't allocate sidecars at construction — that happens on
            its first write() call when kv_cache shape is known.

            layer_idx resolution order (first wins):
              1. _phase5b_layer_idx already set on this instance
                 (assigned by install_int4_protected_backend at post-init swap).
              2. Parsed from layer.prefix (vLLM 0.7+ Attention layers carry
                 a 'prefix' string like 'model.layers.<N>.self_attn.attn').
              3. RuntimeError — no way to slice the per-model protect mask.
            """
            existing = getattr(self, "_phase5b_paged_writer", None)
            if existing is not None:
                return existing
            from kv_policy.phase5b_4c_paged_writer import PagedKVWriter
            layer_idx = getattr(self, "_phase5b_layer_idx", None)
            if layer_idx is None and layer is not None:
                prefix = getattr(layer, "prefix", None) or getattr(layer, "layer_name", None)
                if isinstance(prefix, str):
                    layer_idx = _parse_layer_idx_from_name(prefix)
                    if layer_idx is not None:
                        # Cache on the impl so subsequent calls skip the parse.
                        self._phase5b_layer_idx = layer_idx
            if layer_idx is None:
                raise RuntimeError(
                    "Cannot determine _phase5b_layer_idx for this impl instance. "
                    "Either run install_int4_protected_backend(model) AFTER LLM(...) "
                    "to assign indices via named_modules walk, or set the "
                    "layer's .prefix attribute to a name containing 'layers.<N>'."
                )
            writer = PagedKVWriter(layer_idx=layer_idx)
            self._phase5b_paged_writer = writer
            return writer

        def _read_decode_packed(self, query_q, kv_cache, decode_meta, layer):
            """Phase 5B.4c.2 / 5B.6 step 3: packed decode read path.
            Now handles batch>=1 by looping over sequences.

            query_q     : (B, S_q=1, H_q, D) bf16
            kv_cache    : (2, NB, BS, H_kv, D) uint8
            decode_meta : attn_metadata.decode_metadata (vLLM)
            layer       : the Attention layer module

            Returns: (B, S_q=1, H_q, D) bf16
            """
            writer = self._get_paged_writer(layer=layer)
            block_table = decode_meta.block_tables           # (B, max_blocks) int
            cache_seqlens_orig = decode_meta.seq_lens_tensor # (B,) int
            B = block_table.shape[0]

            from kv_policy.phase5b_4c_paged_writer import _in_cuda_graph_capture
            if B == 1 and not _in_cuda_graph_capture():
                # B=1 fast path (eager only): avoids the batched gather +
                # pad machinery for the common single-sequence case.
                # During capture the batched path handles B=1 too (it's a
                # degenerate case); `_read_decode_packed_one` has .item()
                # calls that are forbidden inside torch.cuda.graph context.
                return self._read_decode_packed_one(
                    query_q, kv_cache, layer, writer,
                    bt=block_table[0],
                    seqlen=int(cache_seqlens_orig[0].item()),
                    seq_id=_seq_id_from_block_table_row(block_table[0]),
                )

            # Multi-batch path (Phase 6 v2 Option A): ONE batched kernel
            # call. Gather all B seqs' paged blocks + sidecars in one
            # advanced-index op, splice each seq's K tail (small per-seq
            # work), stack bf16 backings, then dispatch the kernel with
            # B>1.
            return self._read_decode_packed_batched(
                query_q, kv_cache, layer, writer,
                block_table=block_table,
                cache_seqlens_orig=cache_seqlens_orig,
            )

        def _read_decode_packed_batched(
            self, query_q, kv_cache, layer, writer, *,
            block_table, cache_seqlens_orig,
        ):
            """Multi-seq packed decode in a SINGLE kernel call.

            Pads each seq's gathered tensors to a common n_blocks_max
            (= max over seqs). Padded positions have block_id=0 and
            are masked by cache_seqlens in the kernel — they don't
            affect output.
            """
            from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache

            B = block_table.shape[0]
            BS = writer.BS
            device = block_table.device

            with _maybe_region("batched.seqids_blockids"):
                # Phase 6 v2 Option B pre-flight (B-pre-2 + B-pre-3
                # bundled): keep the working coalesced CPU sync for
                # seqlens + seq_ids (n_blocks_max stays a Python int
                # for the slice; n_blocks_per_seq stays a Python list
                # for the n_blocks_max derivation). The lesson from
                # the reverted B-pre-2 attempt: splitting these into
                # separate .item() / .tolist() calls costs ~50 µs
                # per layer at B=8 because PyTorch can't pipeline them.
                #
                # In addition, compute device-side metadata
                # (last_block_indices_t, active_mask_t) — these are
                # cheap fused ops that don't add a sync, and they're
                # what the unconditional splice path (below) consumes
                # without any data-dependent indexing.
                #
                # Phase 6B.3 (Option X) — capture-safe gating:
                # .cpu().tolist() is a host sync forbidden inside a
                # CUDA graph capture stream. During capture, use
                # block_table.shape[1] as n_blocks_max (the full
                # block budget width that vLLM allocates; padded
                # positions are masked to 0 by pad_mask below, which
                # uses only device-side tensor ops). seqlens_cpu and
                # seq_ids are only used for n_blocks_max derivation
                # and slot resolution; both are skipped during capture.
                from kv_policy.phase5b_4c_paged_writer import (
                    _in_cuda_graph_capture,
                )
                _in_capture_read = _in_cuda_graph_capture()
                if not _in_capture_read:
                    # CAPTURE-EXEMPT: pre-capture host sync.
                    _seqlens_and_seqids = torch.stack([
                        cache_seqlens_orig.long(),
                        block_table[:, 0].long(),
                    ], dim=0).cpu().tolist()             # one sync, two rows
                    seqlens_cpu = _seqlens_and_seqids[0]
                    seq_ids     = _seqlens_and_seqids[1]
                    n_blocks_per_seq = [(s + BS - 1) // BS for s in seqlens_cpu]
                    n_blocks_max = max(n_blocks_per_seq)
                else:
                    # Capture path: use full block budget width. Padded
                    # positions are zeroed by pad_mask (device op below).
                    n_blocks_max = block_table.shape[1]
                    seq_ids      = None   # not used in captured ops
                S_padded = n_blocks_max * BS

                # Device-side metadata for the unconditional splice. No
                # extra sync — these are fused element-wise ops on the
                # already-on-device cache_seqlens_orig.
                cache_seqlens_long_t = cache_seqlens_orig.long()
                n_blocks_per_seq_t   = (cache_seqlens_long_t + (BS - 1)) // BS  # (B,)
                last_block_indices_t = n_blocks_per_seq_t - 1                   # (B,)
                active_mask_t        = (cache_seqlens_long_t % BS) != 0         # (B,) bool

                # Build (B, n_blocks_max) block_ids via slice + mask.
                block_ids_batched = block_table[:, :n_blocks_max].long().contiguous()
                pos = torch.arange(n_blocks_max, device=device).unsqueeze(0)
                pad_mask = pos >= n_blocks_per_seq_t.unsqueeze(1)
                block_ids_batched.masked_fill_(pad_mask, 0)

            with _maybe_region("batched.view_gather"):
                # ONE batched gather covering all B seqs.
                view = writer.get_packed_view_batched(block_ids_batched, kv_cache)

            # Phase 6 v2 Option B pre-flight (B-pre-1 + B-pre-4): resolve
            # seq_ids to slot indices ONCE, and write the result into the
            # PERSISTENT slot-index buffer (stable address across calls).
            # batch_idx_t is also pulled from a persistent arange buffer.
            slot_idx_t, batch_idx_t, _cache_seqlens_i32_buf = \
                self._ensure_index_bufs(
                    B, device, dtype_long=torch.long, dtype_i32=torch.int32,
                )
            if not _in_capture_read:
                # CAPTURE-EXEMPT: pre-capture slot resolution + buffer
                # population. During capture the buffer address is stable
                # (it's the persistent buffer from _ensure_index_bufs);
                # the 6B.2 hook populates its values at production replay
                # time. Skip the dict lookup and .copy_() here.
                slot_idx_list = writer.slot_indices_for(seq_ids)
                # In-place .copy_() from a small fresh tensor — the
                # destination buffer's address is preserved.
                slot_idx_t.copy_(
                    torch.tensor(slot_idx_list, dtype=torch.long, device=device),
                    non_blocking=True,
                )

            with _maybe_region("batched.splice"):
                # Phase 6 v2 Option B pre-flight (B-pre-3): unconditional
                # splice — always processes all B seqs uniformly. Inactive
                # positions (full last block, no partial tail) read-modify-
                # write to themselves under the active_mask_t, preserving
                # their previously-finalized block contents.
                #
                # Eliminates the prior path's data-dependent control flow
                # (`if any_active:`) and the 3 bool-indexing implicit syncs
                # (slot_idx_t[mask], last_block_indices_t[mask], arange[mask]).
                # Captured-graph friendly: same op chain runs regardless of
                # how many seqs are active.
                _splice_k_partial_tail_batched_unconditional(
                    view, writer,
                    slot_idx_t=slot_idx_t,
                    batch_idx_t=batch_idx_t,
                    last_block_indices_t=last_block_indices_t,
                    active_mask_t=active_mask_t,
                )

            with _maybe_region("batched.bf16_backing"):
                # Phase 6 v2 (B-pre-1): single device gather from the
                # writer's bf16 backing pools using the resolved slot
                # tensor. Replaces torch.stack over B per-seq backings.
                bf16_k_batch, bf16_v_batch = \
                    writer.get_bf16_backing_batched_by_slots(
                        slot_idx_t, S_padded,
                    )

            with _maybe_region("batched.kernel_prep"):
                # B-pre-4: persistent (max_B, H, D) protect_mask buffer —
                # content is per-model-frozen so we populate it once at
                # first allocation and reuse across all calls. Stable
                # address.
                protect_mask_bhd = self._ensure_protect_mask_bhd(B, writer)

                # B-pre-4: persistent (max_B,) int32 cache_seqlens buffer.
                # Populate via .copy_() from the (possibly-int32) source —
                # writes into the same backing memory each call.
                cache_seqlens_i32 = _cache_seqlens_i32_buf
                cache_seqlens_i32.copy_(
                    cache_seqlens_orig.to(torch.int32), non_blocking=True,
                )

                v_bf16 = view.get("v_bf16")
                if v_bf16 is not None:
                    v_for_kernel = v_bf16.contiguous()
                    packed_v_kwargs = {}
                else:
                    v_for_kernel = bf16_v_batch
                    packed_v_kwargs = dict(
                        v_packed_int4=view["v_int4"].contiguous(),
                        v_packed_scale=view["v_scale"].contiguous(),
                        v_packed_xmin=view["v_xmin"].contiguous(),
                        v_packed_group_size=writer.v_group_size,
                    )

            with _maybe_region("batched.kernel"):
                out = flash_attn_with_int4_kvcache(
                    query_q,
                    bf16_k_batch, v_for_kernel,
                    cache_seqlens=cache_seqlens_i32,
                    protect_mask=protect_mask_bhd,
                    n_protect=writer.n_protect,
                    softmax_scale=self.scale,
                    causal=False,
                    window_size=self.sliding_window,
                    alibi_slopes=self.alibi_slopes,
                    softcap=self.logits_soft_cap,
                    k_packed_int4=view["k_int4"].contiguous(),
                    k_packed_scale=view["k_scale"].contiguous(),
                    k_packed_xmin=view["k_xmin"].contiguous(),
                    k_packed_protect_bf16=view["k_protect_bf16"].contiguous(),
                    k_packed_protect_slot=view["protect_slot"].contiguous(),
                    packed_group_size=BS,
                    packed_n_protect=writer.n_protect,
                    **packed_v_kwargs,
                )
            return out

        def _read_decode_packed_one(
            self, query_q, kv_cache, layer, writer, *, bt, seqlen, seq_id,
        ):
            """Single-sequence packed decode read. Caller passes the
            per-seq block_table row and cache seqlen explicitly.

            query_q: (1, S_q=1, H_q, D) bf16
            bt:      (max_blocks,) int — the row of decode_meta.block_tables
                     for this sequence
            seqlen:  int — this sequence's cached token count
            seq_id:  identifier into writer._seq_states
            """
            from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache

            BS = writer.BS

            with _maybe_region("one.view_gather"):
                n_blocks_used = (seqlen + BS - 1) // BS
                block_ids = bt[:n_blocks_used].long()
                S = n_blocks_used * BS
                view = writer.get_packed_view(block_ids, kv_cache)

            with _maybe_region("one.splice"):
                tail_len = seqlen % BS
                if tail_len != 0:
                    seq_state = writer.get_seq_state(seq_id)
                    _splice_k_partial_tail(
                        view, writer, last_block_idx=n_blocks_used - 1,
                        state=seq_state,
                    )

            with _maybe_region("one.bf16_backing"):
                bf16_k_backing, bf16_v_backing = writer.get_bf16_backing_slice(
                    S, seq_id=seq_id,
                )
                dummy = bf16_k_backing

            with _maybe_region("one.kernel_prep"):
                cache_seqlens_i32 = torch.tensor(
                    [seqlen], dtype=torch.int32, device=query_q.device,
                )
                protect_mask_bhd = writer.protect_mask.unsqueeze(0)
                v_bf16 = view.get("v_bf16")
                if v_bf16 is not None:
                    v_for_kernel = v_bf16.contiguous()
                    packed_v_kwargs = {}
                else:
                    v_for_kernel = bf16_v_backing
                    packed_v_kwargs = dict(
                        v_packed_int4=view["v_int4"].contiguous(),
                        v_packed_scale=view["v_scale"].contiguous(),
                        v_packed_xmin=view["v_xmin"].contiguous(),
                        v_packed_group_size=writer.v_group_size,
                    )

            with _maybe_region("one.kernel"):
                out = flash_attn_with_int4_kvcache(
                    query_q,
                    dummy, v_for_kernel,
                    cache_seqlens=cache_seqlens_i32,
                    protect_mask=protect_mask_bhd,
                    n_protect=writer.n_protect,
                    softmax_scale=self.scale,
                    causal=False,
                    window_size=self.sliding_window,
                    alibi_slopes=self.alibi_slopes,
                    softcap=self.logits_soft_cap,
                    k_packed_int4=view["k_int4"].contiguous(),
                    k_packed_scale=view["k_scale"].contiguous(),
                    k_packed_xmin=view["k_xmin"].contiguous(),
                    k_packed_protect_bf16=view["k_protect_bf16"].contiguous(),
                    k_packed_protect_slot=view["protect_slot"].contiguous(),
                    packed_group_size=BS,
                    packed_n_protect=writer.n_protect,
                    **packed_v_kwargs,
                )
            return out

        def _ensure_dummy_kv(self, S, H, D, device):
            """Allocate or grow the dummy bf16 K/V buffer for the kernel's
            shape contract. Only seqlen matters; content is unused on
            the packed path — verify_phase5b_4c_2_read confirmed cosine
            is identical with zero, random, or real bf16 content.

            We use zeros (not empty) because the alloc happens once per
            impl lifetime; the cost of memset is amortized to zero across
            all decode steps that reuse the buffer.
            """
            existing = getattr(self, "_phase5b_dummy_kv", None)
            if (existing is not None
                    and existing.shape[1] >= S
                    and existing.shape[2] == H
                    and existing.shape[3] == D
                    and existing.device == device):
                return
            self._phase5b_dummy_kv = torch.zeros(
                (1, S, H, D), dtype=torch.bfloat16, device=device,
            )

        def forward(
            self,
            layer,
            query,
            key,
            value,
            kv_cache,
            attn_metadata,
            output=None,
        ):
            """Phase 5B.4a: REPLICATE FlashAttentionImpl.forward in our
            subclass. Same code paths, same output, but we control every
            call site. This sets up the surface for Phase 5B.4b (shape
            shrink) and 5B.4c (read/write path replacement).

            The replication MUST stay bit-equivalent to FlashAttentionImpl.
            Verified by verify_phase5b_4a_forward.py (output == stock
            generation, char-for-char on greedy decode).

            We import the helper functions from FA at call time to avoid
            ImportError at module-load time if vLLM is missing.
            """
            # Lazy imports — these are private to vllm.attention.backends.flash_attn
            # and may not exist in all vLLM versions. ImportError here means
            # we should fall back to super().forward(), which will hit the
            # 5B.3a-style kv_cache_dtype swap path.
            try:
                from vllm.attention.backends.flash_attn import (
                    AttentionType,
                    flash_attn_varlen_func,
                    flash_attn_with_kvcache,
                    get_num_prefill_decode_query_kv_tokens,
                    get_seq_len_block_table_args,
                    _get_query_key_seq_metadata,
                    _get_causal_option,
                )
            except ImportError:
                # Fallback: delegate with dtype swap (5B.3a behavior).
                saved = getattr(self, "kv_cache_dtype", None)
                if saved == "int4_protected":
                    self.kv_cache_dtype = "auto"
                    try:
                        return super().forward(
                            layer, query, key, value, kv_cache,
                            attn_metadata, output,
                        )
                    finally:
                        self.kv_cache_dtype = saved
                return super().forward(
                    layer, query, key, value, kv_cache,
                    attn_metadata, output,
                )

            # ---- Header validations (copied verbatim from FA forward) ----
            assert layer._k_scale_float == 1.0 and layer._v_scale_float == 1.0, (
                "key/v_scale is not supported in FlashAttention.")
            assert output is not None, "Output tensor must be provided."

            attn_type = self.attn_type
            if (attn_type == AttentionType.ENCODER
                    and (not attn_metadata.is_all_encoder_attn_metadata_set)):
                raise AttributeError("Encoder attention requires setting "
                                     "encoder metadata attributes.")
            elif (attn_type == AttentionType.ENCODER_DECODER
                  and (not attn_metadata.is_all_cross_attn_metadata_set)):
                raise AttributeError("Encoder/decoder cross-attention "
                                     "requires setting cross-attention "
                                     "metadata attributes.")

            # ---- Extract per-impl params ----
            kv_cache_dtype: str = self.kv_cache_dtype
            softmax_scale: float = self.scale
            window_size = self.sliding_window
            alibi_slopes = self.alibi_slopes
            logits_soft_cap = self.logits_soft_cap

            # 5B.4c.1: the kv_cache layout is now uint8 D=128 (from 5B.4b)
            # and reshape_and_cache_flash would treat its bytes as bf16 →
            # corrupted writes. Replace the call with PagedKVWriter which
            # quantizes K + V before writing the right slot regions.
            # The legacy "auto" swap below is still kept for the FALLBACK
            # path (e.g., when kv_policy isn't importable).
            use_paged_writer = (kv_cache_dtype == "int4_protected")
            if not use_paged_writer:
                # Defensive: if a stock dtype somehow reached here, fall
                # back to the legacy behavior.
                if kv_cache_dtype == "int4_protected":
                    kv_cache_dtype = "auto"

            # ---- Cache write ----
            if kv_cache.numel() > 0:
                key_cache = kv_cache[0]
                value_cache = kv_cache[1]
                if (attn_type != AttentionType.ENCODER) and (key is not None) and (
                        value is not None):
                    if attn_type == AttentionType.ENCODER_DECODER:
                        updated_slot_mapping = attn_metadata.cross_slot_mapping
                    else:
                        updated_slot_mapping = attn_metadata.slot_mapping
                    if use_paged_writer:
                        writer = self._get_paged_writer(layer=layer)
                        slot_mapping_flat = updated_slot_mapping.flatten()

                        # Phase 5B.6 step 3 (fixed): partition ALL writes
                        # by sequence — prefill AND decode — so each
                        # seq's SeqState (bf16 backing, K staging) is
                        # populated under the SAME seq_id that the read
                        # path will later use.
                        #
                        # Earlier version had a bug: prefill wrote with
                        # DEFAULT_SEQ_ID=0 and decode read from
                        # block_tables[i, 0]; the prefill bf16 backing
                        # ended up in the wrong SeqState and decode read
                        # zeros for the prompt's K/V (triggering the
                        # small-S kernel zero-output behavior). 5B.6
                        # batch verify hit common-prefix=4 chars on both
                        # prompts because of this.
                        BS = int(kv_cache.shape[2]) if kv_cache.numel() > 0 else 32

                        # Phase 6B.1 — dispatch on pure-decode vs mixed.
                        # Pure decode (1 new token per active seq, no
                        # prefill rows) routes through the graph-capture-
                        # friendly write_decode_batched. Mixed / prefill
                        # / spec-decode-style writes stay on the legacy
                        # partition + per-seq write loop (eager only;
                        # vLLM 0.7.3 V0 doesn't graph-capture prefill).
                        T_total = int(key.shape[0])
                        _pure_decode = _is_pure_decode_write(attn_metadata, T_total)
                        if _pure_decode:
                            dec_meta = attn_metadata.decode_metadata
                            B_decode = int(dec_meta.block_tables.shape[0])
                            # Phase 6B.2: prefer the hook-stashed
                            # slot_idx_t if present. The hook resolves
                            # seq_id -> slot ONCE per step BEFORE the
                            # captured forward (vs once-per-layer here);
                            # when installed, the captured region runs
                            # with zero host syncs. When NOT installed,
                            # the dispatch falls back to 6B.1's per-
                            # layer self-resolve path below (strictly
                            # additive — CPU tests + pre-hook
                            # deployments stay unchanged).
                            from kv_policy.phase6b2_precapture_hook import (
                                read_stash as _read_precapture_stash,
                            )
                            from kv_policy.phase5b_4c_paged_writer import (
                                _in_cuda_graph_capture,
                            )
                            # Phase 6B.3 (Option X) — lazy-alloc writer
                            # BEFORE any path that might call
                            # ensure_seq_state OR rely on the persistent
                            # _phase5b_slot_idx_buf. vLLM 0.7.3 V0's
                            # graph_runner.capture() runs the model ONCE
                            # eagerly (outside torch.cuda.graph()) to
                            # populate state, THEN re-runs inside capture
                            # context. The eager warmup hits the self-
                            # resolve path (is_current_stream_capturing
                            # is False) and would crash on
                            # ensure_seq_state if the writer wasn't
                            # allocated. Synthetic warmup inputs have
                            # block_tables = zeros, so seq_ids resolves
                            # to all zeros — ensure_seq_state(0) consumes
                            # one slot total. Production decode calls
                            # would also already have the writer allocated
                            # by prefill, so this guard is a no-op there.
                            if not writer._allocated:
                                writer._lazy_alloc(kv_cache)
                            # Phase 6B.3 (Option X) — capture-phase handling:
                            # vLLM 0.7.3 V0's capture_model runs synthetic
                            # decode forwards INSIDE graph context, bypassing
                            # the 6B.2 execute_model hook. During capture,
                            # we must NOT host-sync; we must NOT consume real
                            # slot pool entries (capture B can exceed
                            # max_active_slots); we must lazy-alloc the
                            # writer because no prior writer.write() has
                            # fired to trigger it.
                            _in_capture = _in_cuda_graph_capture()
                            if _in_capture:
                                # Writer was lazy-alloc'd by the hoisted
                                # guard above (warmup forward fired
                                # eagerly first; capture forward sees an
                                # allocated writer).
                                # Use the persistent slot-idx buffer from
                                # B-pre-4 (already at stable address +
                                # initialized to zeros). Captured ops
                                # index into pool tensors at addresses
                                # that match production replay; the
                                # production-runtime hook populates the
                                # buffer's values before each captured
                                # graph replay.
                                slot_idx_t, _, _ = self._ensure_index_bufs(
                                    B_decode, kv_cache.device,
                                    dtype_long=torch.long,
                                    dtype_i32=torch.int32,
                                )
                                # Skip pool counter sync; pre_synced=True
                                # tells write_decode_batched to skip
                                # ALL host-sync work too (it also detects
                                # in_capture independently).
                                _pre_synced = True
                                Int4ProtectedAttentionImpl._call_stats[
                                    "write_decode_batched_via_capture_calls"
                                ] += 1
                            else:
                                _stash = _read_precapture_stash(attn_metadata)
                                if _stash is not None and "slot_idx_t" in _stash:
                                    # Hook is installed. Use the stashed
                                    # slot_idx_t; the hook also already
                                    # synced pool counters across ALL
                                    # writers for this step.
                                    slot_idx_t = _stash["slot_idx_t"]
                                    _pre_synced = True
                                    Int4ProtectedAttentionImpl._call_stats[
                                        "write_decode_batched_via_hook_calls"
                                    ] += 1
                                else:
                                    # Hook NOT installed (CPU tests, pre-
                                    # hook deployments). Self-resolve as
                                    # in 6B.1. The seq_id derivation
                                    # mirrors _derive_write_partitions's
                                    # decode branch (block_tables[i, 0]).
                                    seq_ids = dec_meta.block_tables[:, 0] \
                                        .cpu().tolist()
                                    # Ensure SeqState exists for each decode
                                    # seq (allocates a pool slot lazily on
                                    # first write).
                                    for sid in seq_ids:
                                        writer.ensure_seq_state(sid, kv_cache.device)
                                    slot_idx_list = writer.slot_indices_for(seq_ids)
                                    # Phase 6B.3 (Option X): use the
                                    # persistent buffer (stable address)
                                    # instead of fresh torch.tensor(...)
                                    # allocation. Required so the
                                    # captured-graph replay reads
                                    # slot_idx_t from the SAME address
                                    # the eager calls wrote to.
                                    _slot_idx_buf, _, _ = self._ensure_index_bufs(
                                        B_decode, kv_cache.device,
                                        dtype_long=torch.long,
                                        dtype_i32=torch.int32,
                                    )
                                    _slot_idx_buf.copy_(
                                        torch.tensor(
                                            slot_idx_list, dtype=torch.long,
                                            device=kv_cache.device,
                                        ),
                                        non_blocking=True,
                                    )
                                    slot_idx_t = _slot_idx_buf
                                    _pre_synced = False
                            writer.write_decode_batched(
                                key=key,
                                value=value,
                                kv_cache=kv_cache,
                                slot_mapping=slot_mapping_flat,
                                slot_idx_t=slot_idx_t,
                                pre_synced=_pre_synced,
                            )
                            Int4ProtectedAttentionImpl._call_stats[
                                "write_decode_batched_calls"
                            ] += 1
                        else:
                            # Legacy partition + per-seq write (eager).
                            partitions = _derive_write_partitions(
                                attn_metadata, slot_mapping_flat, BS,
                            )
                            for seq_id, sl in partitions:
                                writer.write(
                                    key=key[sl],
                                    value=value[sl],
                                    kv_cache=kv_cache,
                                    slot_mapping=slot_mapping_flat[sl],
                                    seq_id=seq_id,
                                )
                            Int4ProtectedAttentionImpl._call_stats[
                                "write_legacy_loop_calls"
                            ] += 1
                        Int4ProtectedAttentionImpl._call_stats["write_path_calls"] += 1
                    else:
                        Int4ProtectedAttentionImpl._call_stats["write_path_fallback"] += 1
                        torch.ops._C_cache_ops.reshape_and_cache_flash(
                            key, value, kv_cache[0], kv_cache[1],
                            updated_slot_mapping.flatten(),
                            kv_cache_dtype,
                            layer._k_scale, layer._v_scale,
                        )

            # ---- Token routing ----
            (num_prefill_query_tokens, num_prefill_kv_tokens,
             num_decode_query_tokens) = \
                get_num_prefill_decode_query_kv_tokens(attn_metadata, attn_type)
            decode_query = query[num_prefill_query_tokens:]
            decode_output = output[num_prefill_query_tokens:]
            query = query[:num_prefill_query_tokens]
            prefill_output = output[:num_prefill_query_tokens]
            assert query.shape[0] == num_prefill_query_tokens
            assert decode_query.shape[0] == num_decode_query_tokens

            # ---- Prefill attention (5B.4c will replace inner kernel call) ----
            if prefill_meta := attn_metadata.prefill_metadata:
                Int4ProtectedAttentionImpl._call_stats["prefill_calls"] += 1
                if (kv_cache.numel() == 0 or prefill_meta.block_tables is None
                        or prefill_meta.block_tables.numel() == 0):
                    # Normal varlen attention (no paged cache yet).
                    q_seq_start_loc, q_seq_len, k_seq_start_loc, k_seq_len = \
                        _get_query_key_seq_metadata(prefill_meta, True, attn_type)
                    key = key[:num_prefill_kv_tokens]
                    value = value[:num_prefill_kv_tokens]
                    flash_attn_varlen_func(
                        q=query, k=key, v=value,
                        cu_seqlens_q=q_seq_start_loc,
                        cu_seqlens_k=k_seq_start_loc,
                        max_seqlen_q=q_seq_len,
                        max_seqlen_k=k_seq_len,
                        softmax_scale=softmax_scale,
                        causal=_get_causal_option(attn_type),
                        window_size=window_size,
                        alibi_slopes=alibi_slopes,
                        softcap=logits_soft_cap,
                        out=prefill_output,
                        fa_version=self.vllm_flash_attn_version,
                    )
                else:
                    # Prefix-enabled attention (Q current, K/V from cache).
                    assert attn_type == AttentionType.DECODER, (
                        "Only decoder-only models support prefix caching")
                    assert prefill_meta.seq_lens is not None
                    max_seq_len = max(prefill_meta.seq_lens)
                    flash_attn_varlen_func(
                        q=query, k=key_cache, v=value_cache,
                        cu_seqlens_q=prefill_meta.query_start_loc,
                        max_seqlen_q=prefill_meta.max_query_len,
                        seqused_k=prefill_meta.seq_lens_tensor,
                        max_seqlen_k=max_seq_len,
                        softmax_scale=softmax_scale,
                        causal=True,
                        window_size=window_size,
                        alibi_slopes=alibi_slopes,
                        block_table=prefill_meta.block_tables,
                        softcap=logits_soft_cap,
                        out=prefill_output,
                        fa_version=self.vllm_flash_attn_version,
                    )

            # ---- Decode attention (5B.4c will replace inner kernel call) ----
            if decode_meta := attn_metadata.decode_metadata:
                assert decode_meta.max_decode_query_len is not None
                if decode_meta.max_decode_query_len > 1:
                    # Speculative-decode-style varlen path.
                    assert attn_type == AttentionType.DECODER, (
                        "Only decoder-only models support max_decode_query_len > 1")
                    Int4ProtectedAttentionImpl._call_stats["spec_decode_calls"] += 1
                    flash_attn_varlen_func(
                        q=decode_query, k=key_cache, v=value_cache,
                        cu_seqlens_q=decode_meta.query_start_loc,
                        max_seqlen_q=decode_meta.max_decode_query_len,
                        seqused_k=decode_meta.seq_lens_tensor,
                        max_seqlen_k=decode_meta.max_decode_seq_len,
                        softmax_scale=softmax_scale,
                        causal=True,
                        window_size=window_size,
                        alibi_slopes=alibi_slopes,
                        softcap=logits_soft_cap,
                        block_table=decode_meta.block_tables,
                        out=decode_output,
                        fa_version=self.vllm_flash_attn_version,
                    )
                else:
                    # Standard decode path (the common case).
                    if use_paged_writer:
                        # 5B.4c.2: packed read via gather + packed kernel.
                        Int4ProtectedAttentionImpl._call_stats["decode_calls_packed"] += 1
                        out_packed = self._read_decode_packed(
                            query_q=decode_query.unsqueeze(1),
                            kv_cache=kv_cache,
                            decode_meta=decode_meta,
                            layer=layer,
                        )
                        decode_output.copy_(out_packed.squeeze(1))
                    else:
                        Int4ProtectedAttentionImpl._call_stats["decode_calls_fallback"] += 1
                        seq_lens_arg, _, block_tables_arg = (
                            get_seq_len_block_table_args(decode_meta, False, attn_type)
                        )
                        flash_attn_with_kvcache(
                            q=decode_query.unsqueeze(1),
                            k_cache=key_cache, v_cache=value_cache,
                            block_table=block_tables_arg,
                            cache_seqlens=seq_lens_arg,
                            softmax_scale=softmax_scale,
                            causal=True,
                            window_size=window_size,
                            alibi_slopes=alibi_slopes,
                            softcap=logits_soft_cap,
                            out=decode_output.unsqueeze(1),
                            fa_version=self.vllm_flash_attn_version,
                        )
            return output

else:

    class Int4ProtectedAttentionImpl:  # type: ignore[no-redef]
        """Placeholder for environments without vLLM. Raises on use."""
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError(
                "Int4ProtectedAttentionImpl requires vllm.attention.backends.flash_attn"
            )


# ----------------------------------------------------------------------
# Int4ProtectedAttentionBackend — subclass of FlashAttentionBackend
# for Phase 5B.3a init-time selection.
# ----------------------------------------------------------------------

if _VLLM_FA_AVAILABLE:

    class Int4ProtectedAttentionBackend(FlashAttentionBackend):
        """Phase 5B.3a backend class. Returned by our patched
        get_attn_backend_cls when kv_cache_dtype="int4_protected".

        Inherits all of FlashAttentionBackend's methods (kv_cache_shape,
        copy_blocks, swap_blocks, etc.), but overrides get_impl_cls()
        to return Int4ProtectedAttentionImpl so each attention layer
        constructs with our impl from the start (no post-init swap
        needed).

        Phase 5B.4 will additionally override get_kv_cache_shape AND
        the byte-cost calculation for actual memory savings. v0 here
        keeps stock memory layout — only the dispatch class changes.
        """

        _phase5b_backend_marker = "5B.3a"

        @staticmethod
        def get_name() -> str:
            return "INT4_PROTECTED"

        @staticmethod
        def get_impl_cls():
            return Int4ProtectedAttentionImpl

else:

    class Int4ProtectedAttentionBackend:  # type: ignore[no-redef]
        """Placeholder when vLLM unavailable."""
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError(
                "Int4ProtectedAttentionBackend requires vllm.attention.backends.flash_attn"
            )


# ----------------------------------------------------------------------
# Manager — tracks swap state for teardown.
# ----------------------------------------------------------------------

class Int4ProtectedBackendManager:
    """Tracks which Attention.impl instances we swapped, for teardown.

    Each entry is (impl_instance, original_class) so we can restore
    the original class on teardown. We swap __class__ in place rather
    than substituting a different instance — instance state is preserved
    (which is critical: the engine sets up head_size, scale, num_heads,
    etc. on the original instance during init, and we want to inherit
    all of that).
    """

    def __init__(self) -> None:
        # (impl_instance, original_class) pairs.
        self.swapped: List[Tuple[Any, type]] = []
        # Per-swap stats.
        self._stats: Dict[str, int] = {
            "swapped_impls":         0,
            "skipped_not_FA_impl":   0,
            "skipped_no_impl_attr":  0,
            "fallback_forward_swap": 0,
        }

    def stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "installer": "phase5b_backend_skeleton",
            "phase":     "5B.2",
        }


# ----------------------------------------------------------------------
# Attention layer detection (same heuristic as Phase 5A).
# ----------------------------------------------------------------------


def _is_pure_decode_write(attn_metadata: Any, T_total: int) -> bool:
    """Phase 6B.1 — dispatch gate: True iff the current forward() write
    is a pure decode (one new token per active seq, no prefill rows).

    A pure decode call satisfies ALL of:
      1. `decode_metadata` is set with non-empty `block_tables`.
      2. `prefill_metadata` is None or has zero query tokens.
      3. `max_decode_query_len == 1` (rules out spec-decode style multi-
         token-per-seq writes).
      4. Total write rows `T_total` == number of decode sequences B.

    When True, the dispatch routes through
    `PagedKVWriter.write_decode_batched` (graph-capture-friendly).
    When False, the legacy partition + per-seq `writer.write(seq_id=...)`
    loop runs (prefill / spec-decode / mixed). Prefill is NOT graph-
    captured by vLLM 0.7.3 V0 so eager-only handling is fine.

    Override: set env `PHASE6B1_USE_DECODE_BATCHED=0` to disable the
    new path entirely (always returns False). Used by the Phase 6B.1
    GPU smoke to capture a "pre-refactor reference" cell from the
    same process tree where the refactored cell runs.
    """
    if os.environ.get("PHASE6B1_USE_DECODE_BATCHED", "1").strip() == "0":
        return False
    dec_meta = getattr(attn_metadata, "decode_metadata", None)
    if dec_meta is None:
        return False
    block_tables = getattr(dec_meta, "block_tables", None)
    if block_tables is None or block_tables.numel() == 0:
        return False
    max_decode_q = getattr(dec_meta, "max_decode_query_len", None)
    if max_decode_q is not None and max_decode_q > 1:
        return False
    pre_meta = getattr(attn_metadata, "prefill_metadata", None)
    if pre_meta is not None:
        n_prefill_q = getattr(pre_meta, "num_prefill_tokens", None)
        if n_prefill_q is None:
            # Older vLLM shape — fall back to checking query_start_loc.
            qsl = getattr(pre_meta, "query_start_loc", None)
            if qsl is not None and qsl.numel() > 0:
                n_prefill_q = int(qsl[-1].item())
        if n_prefill_q is not None and n_prefill_q > 0:
            return False
    B_decode = int(block_tables.shape[0])
    if T_total != B_decode:
        return False
    return True


def _derive_write_partitions(attn_metadata: Any, slot_mapping_flat: "torch.Tensor", BS: int):
    """Phase 5B.6 step 3 fix: partition a multi-token write call across
    sequences so each seq's SeqState (bf16 backing, K staging) receives
    its own data.

    Returns: list of (seq_id, slice) tuples. The seq_id derivation
    matches how _read_decode_packed_one identifies sequences:
      - PREFILL:  seq_id = slot_mapping[seq_start] // BS
                  (= the seq's FIRST BLOCK, which equals what decode
                  later sees as block_tables[i, 0])
      - DECODE:   seq_id = decode_meta.block_tables[i, 0]

    Both forms collapse to `block_table[0]` for any given sequence —
    stable across that sequence's lifetime in vLLM 0.7.3 V0.
    """
    dec_meta = getattr(attn_metadata, "decode_metadata", None)
    pre_meta = getattr(attn_metadata, "prefill_metadata", None)

    if (dec_meta is not None
            and getattr(dec_meta, "block_tables", None) is not None
            and dec_meta.block_tables.numel() > 0):
        B = dec_meta.block_tables.shape[0]
        return [
            (_seq_id_from_block_table_row(dec_meta.block_tables[i]), slice(i, i + 1))
            for i in range(B)
        ]

    if pre_meta is not None:
        # Multi-seq prefill (rare in V0 default; happens with batched
        # prefill / chunked prefill). Partition via query_start_loc.
        qsl = getattr(pre_meta, "query_start_loc", None)
        if qsl is not None and qsl.shape[0] > 2:
            qsl_cpu = qsl.cpu().tolist()
            partitions = []
            for i in range(len(qsl_cpu) - 1):
                start, end = qsl_cpu[i], qsl_cpu[i + 1]
                if end <= start:
                    continue
                first_slot = int(slot_mapping_flat[start].item())
                if first_slot < 0:
                    # All padding for this seg; skip.
                    continue
                partitions.append((first_slot // BS, slice(start, end)))
            if partitions:
                return partitions
        # Single-seq prefill. Derive from the first non-padding slot.
        first_slot = -1
        n = int(slot_mapping_flat.shape[0])
        for j in range(n):
            v = int(slot_mapping_flat[j].item())
            if v >= 0:
                first_slot = v
                break
        if first_slot >= 0:
            return [(first_slot // BS, slice(0, n))]

    # Fallback: no metadata, no valid slots. Use the default seq.
    return [(0, slice(0, int(slot_mapping_flat.shape[0])))]


def _seq_id_from_block_table_row(bt_row: "torch.Tensor") -> int:
    """Phase 5B.6 step 3: per-sequence identifier derived from the
    first block in this sequence's block_table row.

    vLLM 0.7.3's BlockManager doesn't reallocate a sequence's first
    block across its lifetime (only adds new blocks as the sequence
    grows). So block_table[i, 0] is a stable fingerprint across decode
    steps of the same sequence — suitable as the seq_id key into
    PagedKVWriter._seq_states.

    Caveat: when a sequence finishes and its blocks return to the pool,
    a future sequence MAY get the same first block. Callers should
    `writer.evict_sequence(seq_id)` on completion to drop stale state.
    """
    return int(bt_row[0].item())


def _splice_k_partial_tail_batched_row(
    view: Dict[str, Any], writer: Any, *, batch_idx: int,
    last_block_idx: int, state: Any,
) -> None:
    """Phase 6 v2: K-tail splice for one batch row inside a batched view.

    Same math as `_splice_k_partial_tail` but writes into the
    `batch_idx`-th slice of view's batched tensors (k_int4, k_scale,
    k_xmin shaped (B, ...)) rather than the (1, ...) single-seq view.
    """
    BS = writer.BS
    D  = writer.D
    half_D = D // 2

    buf_f = state.k_stage.float()
    x_max = buf_f.amax(dim=0)
    x_min = buf_f.amin(dim=0)
    scale = ((x_max - x_min) / 15.0).clamp(min=1e-8)

    q = ((buf_f - x_min.unsqueeze(0)) / scale.unsqueeze(0)) \
        .round().clamp(0, 15).to(torch.uint8)
    packed = (q[..., 0::2] & 0x0F) | ((q[..., 1::2] & 0x0F) << 4)  # (BS, H, D/2)

    bstart = last_block_idx * BS
    view["k_int4"][batch_idx, bstart:bstart + BS] = packed
    view["k_scale"][batch_idx, last_block_idx]    = scale.to(writer.sidecar_dtype)
    view["k_xmin"] [batch_idx, last_block_idx]    = x_min.to(writer.sidecar_dtype)


def _splice_k_partial_tail_batched_vectorized(
    view: Dict[str, Any], writer: Any, *,
    seq_states_list: list = None, last_block_indices: list = None,
    active_mask: list = None,
    active_slot_idx_t: "torch.Tensor" = None,
    active_batch_idx_t: "torch.Tensor" = None,
    active_last_block_t: "torch.Tensor" = None,
) -> None:
    """Phase 6 v2 Option D step 1 + Option B pre-flight (B-pre-1):
    vectorized batched K-tail splice.

    Two calling conventions:

    1. Legacy (D step 1) — pass `seq_states_list`, `last_block_indices`,
       `active_mask` (all Python lists). The helper builds the active
       subset and gathers k_stage via `torch.stack`. Kept for any
       external callers and the bit-equivalence verify.

    2. Pre-flight (B-pre-1) — pass `active_slot_idx_t`,
       `active_batch_idx_t`, `active_last_block_t` (all device long
       tensors of the same length A). The helper gathers k_stage in
       ONE op via `writer.get_k_stage_by_slots(slot_idx_t)` — fully
       device-indexed, no Python loop, no dict lookup. This is the
       captured-graph-friendly path.

    Math is bit-identical between the two paths (same element-wise
    quantize+pack chain). The only difference is HOW the (A, BS, H, D)
    k_stage tensor is materialized:
      - legacy: `torch.stack([state.k_stage for state in active])`
      - preflight: `writer._k_stage_pool[active_slot_idx_t]`

    Verified by `verify_phase6_d_step1_splice_equiv.py` (legacy) and
    `verify_phase6_b_pre1_splice_slots_equiv.py` (preflight).
    """
    BS = writer.BS
    D  = writer.D
    H  = writer.H
    half_D = D // 2

    if active_slot_idx_t is not None:
        # Preflight path: caller already has the active subset as device
        # tensors. Gather k_stage in ONE op from the slot pool.
        if active_slot_idx_t.numel() == 0:
            return
        if active_batch_idx_t is None or active_last_block_t is None:
            raise ValueError(
                "preflight call needs active_batch_idx_t + active_last_block_t"
            )
        k_stage_stack = writer.get_k_stage_by_slots(active_slot_idx_t)  # (A, BS, H, D)
        device = k_stage_stack.device
        batch_idx_t  = active_batch_idx_t
        last_block_t = active_last_block_t
    else:
        # Legacy path: build the active subset from Python lists.
        if seq_states_list is None or last_block_indices is None or active_mask is None:
            raise ValueError(
                "legacy call needs seq_states_list + last_block_indices + active_mask"
            )
        if not any(active_mask):
            return
        active_idx = [i for i, m in enumerate(active_mask) if m]
        k_stage_stack = torch.stack(
            [seq_states_list[i].k_stage for i in active_idx], dim=0,
        )
        device = k_stage_stack.device
        batch_idx_t = torch.tensor(active_idx, dtype=torch.long, device=device)
        last_block_t = torch.tensor(
            [last_block_indices[i] for i in active_idx],
            dtype=torch.long, device=device,
        )

    # Quantize + pack — identical for both paths.
    buf_f = k_stage_stack.float()                                  # (A, BS, H, D)
    x_max = buf_f.amax(dim=1)                                      # (A, H, D)
    x_min = buf_f.amin(dim=1)                                      # (A, H, D)
    scale = ((x_max - x_min) / 15.0).clamp(min=1e-8)               # (A, H, D)

    q = ((buf_f - x_min.unsqueeze(1)) / scale.unsqueeze(1)) \
        .round().clamp(0, 15).to(torch.uint8)                      # (A, BS, H, D)
    packed = (q[..., 0::2] & 0x0F) | ((q[..., 1::2] & 0x0F) << 4)  # (A, BS, H, half_D)

    # Scatter into view tensors at (batch_idx, last_block_idx) positions.
    n_blocks_max = view["k_int4"].shape[1] // BS
    k_int4_blocked = view["k_int4"].view(-1, n_blocks_max, BS, H, half_D)
    k_int4_blocked[batch_idx_t, last_block_t] = packed
    sidecar_dtype = writer.sidecar_dtype
    view["k_scale"][batch_idx_t, last_block_t] = scale.to(sidecar_dtype)
    view["k_xmin"] [batch_idx_t, last_block_t] = x_min.to(sidecar_dtype)


def _splice_k_partial_tail_batched_unconditional(
    view: Dict[str, Any], writer: Any, *,
    slot_idx_t: "torch.Tensor",            # (B,) long — slot per batch position
    batch_idx_t: "torch.Tensor",           # (B,) long — typically arange(B)
    last_block_indices_t: "torch.Tensor",  # (B,) long — per-seq last block
    active_mask_t: "torch.Tensor",         # (B,) bool — True iff seq has partial tail
) -> None:
    """Phase 6 v2 Option B pre-flight (B-pre-2 + B-pre-3 bundled):
    unconditional splice that processes ALL B sequences uniformly,
    masking inactive writes via torch.where.

    Replaces the prior conditional path that:
      - Filtered to active subset via boolean indexing (3 implicit
        sync points to resolve data-dependent output shapes).
      - Wrapped the entire call in a Python `if any_active:` branch.

    The unconditional version is captured-graph-friendly:
      - Same op chain runs regardless of how many seqs are active.
      - No data-dependent shapes (all tensors stay (B, ...)).
      - No host syncs in the splice region (mask is a device tensor).

    For inactive seqs (no partial tail), the helper READS their current
    k_int4 / k_scale / k_xmin at last_block_indices_t and WRITES IT BACK
    via where(False, new, old) — a deterministic self-write that
    preserves the previously-finalized block contents.

    Cost vs the active-only path: B-A extra seqs go through the
    quantize+pack work (negligible at typical steady-state decode where
    A ≈ B). The win is removing the implicit-sync penalty of the
    bool-indexing path — splice cpu_us drops to pure-dispatch overhead.

    Verified by `verify_phase6_b_pre23_unconditional_splice_equiv.py`.
    """
    BS = writer.BS
    D  = writer.D
    H  = writer.H
    half_D = D // 2

    # Single device gather of all B k_stages from the slot pool.
    k_stage_stack = writer.get_k_stage_by_slots(slot_idx_t)             # (B, BS, H, D)
    B_dim = k_stage_stack.shape[0]

    # Quantize + pack — math identical per-element to the active-only path.
    buf_f = k_stage_stack.float()                                       # (B, BS, H, D)
    x_max = buf_f.amax(dim=1)                                           # (B, H, D)
    x_min = buf_f.amin(dim=1)                                           # (B, H, D)
    scale = ((x_max - x_min) / 15.0).clamp(min=1e-8)                    # (B, H, D)

    q = ((buf_f - x_min.unsqueeze(1)) / scale.unsqueeze(1)) \
        .round().clamp(0, 15).to(torch.uint8)                           # (B, BS, H, D)
    packed = (q[..., 0::2] & 0x0F) | ((q[..., 1::2] & 0x0F) << 4)       # (B, BS, H, half_D)

    n_blocks_max = view["k_int4"].shape[1] // BS
    k_int4_blocked = view["k_int4"].view(-1, n_blocks_max, BS, H, half_D)

    sidecar_dtype = writer.sidecar_dtype
    # Mask broadcasts: keep batch dim aligned with the target shapes.
    mask_packed = active_mask_t.view(B_dim, 1, 1, 1)                    # vs (B, BS, H, half_D)
    mask_meta   = active_mask_t.view(B_dim, 1, 1)                       # vs (B, H, D)

    # Read-modify-write under mask. Each (batch_idx_t[k], last_block_indices_t[k])
    # pair is unique (distinct batch positions per seq), so no scatter race.
    # For inactive seqs the new value equals the old value, so the write is a
    # deterministic no-op preserving the previously-finalized block contents.
    old_k_int4 = k_int4_blocked[batch_idx_t, last_block_indices_t]      # (B, BS, H, half_D)
    new_k_int4 = torch.where(mask_packed, packed, old_k_int4)
    k_int4_blocked[batch_idx_t, last_block_indices_t] = new_k_int4

    scale_sc = scale.to(sidecar_dtype)
    old_k_scale = view["k_scale"][batch_idx_t, last_block_indices_t]    # (B, H, D)
    new_k_scale = torch.where(mask_meta, scale_sc, old_k_scale)
    view["k_scale"][batch_idx_t, last_block_indices_t] = new_k_scale

    xmin_sc = x_min.to(sidecar_dtype)
    old_k_xmin = view["k_xmin"][batch_idx_t, last_block_indices_t]
    new_k_xmin = torch.where(mask_meta, xmin_sc, old_k_xmin)
    view["k_xmin"][batch_idx_t, last_block_indices_t] = new_k_xmin


def _splice_k_partial_tail(
    view: Dict[str, Any], writer: Any, last_block_idx: int,
    *, state: Any = None,
) -> None:
    """Phase 5B.4c.2 hybrid splice. Rewrites the last block of the
    gathered packed-K view with on-the-fly quantization of the in-RAM
    staging buffer.

    Phase 5B.6 step 3: optional `state` parameter selects which sequence's
    staging buffer to splice from. Default (state=None) uses the writer's
    default-seq state (legacy single-seq behavior).

    Mirrors PagedKVWriter._finalize_k_group_from_state's math so the
    kernel sees a self-consistent (scale, xmin, nibbles) triple.
    """
    if state is None:
        state = writer._default_state
    BS = writer.BS
    D  = writer.D
    half_D = D // 2

    buf_f = state.k_stage.float()                  # (BS, H, D)
    x_max = buf_f.amax(dim=0)                       # (H, D)
    x_min = buf_f.amin(dim=0)
    scale = ((x_max - x_min) / 15.0).clamp(min=1e-8)

    q = ((buf_f - x_min.unsqueeze(0)) / scale.unsqueeze(0)) \
        .round().clamp(0, 15).to(torch.uint8)       # (BS, H, D)
    packed = (q[..., 0::2] & 0x0F) | ((q[..., 1::2] & 0x0F) << 4)  # (BS, H, D/2)

    bstart = last_block_idx * BS
    view["k_int4"][0, bstart:bstart + BS] = packed
    view["k_scale"][0, last_block_idx]    = scale.to(writer.sidecar_dtype)
    view["k_xmin"] [0, last_block_idx]    = x_min.to(writer.sidecar_dtype)


def _parse_layer_idx_from_name(name: str) -> Optional[int]:
    """Parse the integer N out of 'model.layers.<N>.self_attn' style names.
    Returns None if the name doesn't match — caller falls back to walk-order."""
    parts = name.split(".")
    for i, part in enumerate(parts):
        if part == "layers" and i + 1 < len(parts):
            try:
                return int(parts[i + 1])
            except ValueError:
                return None
    return None


def _looks_like_attention(module: Any) -> bool:
    cls_name = type(module).__name__
    if not cls_name.endswith("Attention"):
        return False
    if not callable(getattr(module, "forward", None)):
        return False
    for sub in module.modules():
        if sub is module:
            continue
        sub_cls = type(sub).__name__
        if sub_cls.endswith("Attention") and callable(getattr(sub, "forward", None)):
            return False
    return True


# ----------------------------------------------------------------------
# Install — swap each leaf Attention layer's .impl class.
# ----------------------------------------------------------------------

def install_int4_protected_backend(
    model: Any,
) -> Tuple[Int4ProtectedBackendManager, Callable[[], None]]:
    """Swap each leaf Attention layer's `.impl` class from
    `FlashAttentionImpl` to `Int4ProtectedAttentionImpl`.

    Strategy: in-place `__class__` assignment on the existing impl
    instance. This:
      - Preserves all instance state (head_size, scale, num_heads, ...).
      - Changes the dispatch for forward() and any other overrides.
      - Is reversible (teardown restores the original class).

    If the in-place class swap fails (e.g., __slots__ conflict on a
    future vLLM version), the install falls back to a forward-method
    monkey-patch (same pattern as Phase 5A).

    Returns:
      (manager, teardown)
        manager.stats() reports counts of swapped vs skipped layers.
        teardown() restores all swapped __class__ assignments.

    Raises ValueError if zero layers were swappable (likely a vLLM
    version mismatch — Int4ProtectedAttentionImpl assumes
    FlashAttentionImpl as the parent).
    """
    if not _VLLM_FA_AVAILABLE:
        raise RuntimeError(
            "install_int4_protected_backend requires vllm.attention.backends.flash_attn. "
            "Are you running in venv-vllm?"
        )

    manager = Int4ProtectedBackendManager()

    # Track forward-fallback swaps separately (for teardown).
    forward_swaps: List[Tuple[Any, Callable]] = []

    # Phase 5B.4c.1: track sequential layer index for protect-mask slicing.
    # Walk-order matches model.named_modules() iteration, which for vLLM
    # 0.7.3's Qwen impl matches model.layers.0..N self_attn order.
    _next_layer_idx = 0

    for name, sub in model.named_modules():
        if not _looks_like_attention(sub):
            continue
        if not hasattr(sub, "impl"):
            manager._stats["skipped_no_impl_attr"] += 1
            logger.warning("Layer %s has no .impl attribute; skipping", name)
            continue
        impl = sub.impl
        if not isinstance(impl, FlashAttentionImpl):
            manager._stats["skipped_not_FA_impl"] += 1
            logger.warning(
                "Layer %s .impl is %s, not FlashAttentionImpl; skipping",
                name, type(impl).__name__,
            )
            continue

        original_class = impl.__class__
        try:
            impl.__class__ = Int4ProtectedAttentionImpl
            # Phase 5B.4c.1: prefer the integer parsed out of a name like
            # 'model.layers.<N>.self_attn' (matches Phase 5B.0 calibrator
            # ordering). Fall back to walk-order if the name doesn't fit.
            layer_idx = _parse_layer_idx_from_name(name)
            if layer_idx is None:
                layer_idx = _next_layer_idx
            impl._phase5b_layer_idx = layer_idx
            _next_layer_idx += 1
            manager.swapped.append((impl, original_class))
            manager._stats["swapped_impls"] += 1
        except TypeError as e:
            # __class__ swap failed — likely __slots__ or similar.
            # Fall back to monkey-patching forward on this instance.
            logger.warning(
                "Class swap failed on layer %s (%s); falling back to "
                "forward monkey-patch.", name, e,
            )
            original_forward = impl.forward

            def _wrapped_forward(_orig=original_forward):
                def f(*a, **kw):
                    # Pure delegate at this phase.
                    return _orig(*a, **kw)
                return f
            impl.forward = _wrapped_forward()
            forward_swaps.append((impl, original_forward))
            manager._stats["fallback_forward_swap"] += 1

    if (manager._stats["swapped_impls"] == 0
            and manager._stats["fallback_forward_swap"] == 0):
        raise ValueError(
            "install_int4_protected_backend found no swappable Attention "
            f"impls. Stats: {manager.stats()}"
        )

    logger.info(
        "Phase 5B.2 installed: %d class swaps, %d forward fallbacks",
        manager._stats["swapped_impls"],
        manager._stats["fallback_forward_swap"],
    )

    def teardown() -> None:
        # Restore class-swapped impls.
        for impl, original_class in manager.swapped:
            try:
                impl.__class__ = original_class
            except TypeError as e:
                logger.warning("Teardown class restore failed on %s: %s", impl, e)
        manager.swapped.clear()
        # Restore forward-monkey-patched impls.
        for impl, original_forward in forward_swaps:
            impl.forward = original_forward
        forward_swaps.clear()

    return manager, teardown


# ----------------------------------------------------------------------
# Utility — count how many layers currently use our subclass.
# ----------------------------------------------------------------------

def count_int4_protected_impls(model: Any) -> Tuple[int, int]:
    """Returns (int4_protected_count, total_FA_impl_count). Useful for
    verify scripts to assert install / teardown took effect."""
    if not _VLLM_FA_AVAILABLE:
        return (0, 0)
    n_ours = 0
    n_total = 0
    for _, sub in model.named_modules():
        if not _looks_like_attention(sub):
            continue
        if not hasattr(sub, "impl"):
            continue
        impl = sub.impl
        if isinstance(impl, FlashAttentionImpl):
            n_total += 1
            if isinstance(impl, Int4ProtectedAttentionImpl):
                n_ours += 1
    return (n_ours, n_total)


# ----------------------------------------------------------------------
# Phase 5B.3a — init-time install via CacheConfig + backend selector
# monkey-patches. Call BEFORE LLM(...) construction.
# ----------------------------------------------------------------------

# Module-level state so enable/disable is idempotent across calls.
_INSTALLED_PATCHES: Dict[str, Any] = {}


def enable_int4_protected_backend() -> None:
    """Patch vLLM at the module level so kv_cache_dtype="int4_protected"
    is accepted by CacheConfig validation AND routed to our backend
    class at engine init. Idempotent — safe to call multiple times.

    Patches applied:
      1. CacheConfig._verify_cache_dtype: add "int4_protected" to the
         accepted list (alongside "auto" and the fp8 variants).
      2. current_platform.get_attn_backend_cls: when kv_cache_dtype
         == "int4_protected", return our backend's qualname instead
         of vLLM's default FA qualname. resolve_obj_by_qualname then
         imports our class via kv_policy.phase5b_backend_install.
      3. _cached_get_attn_backend.cache_clear() to invalidate any
         stale cache hits from before patching.

    Call BEFORE LLM(...) construction. Once patches are in place, you
    can construct an LLM with kv_cache_dtype="int4_protected" and the
    engine init will route through Int4ProtectedAttentionBackend →
    Int4ProtectedAttentionImpl per attention layer.

    See disable_int4_protected_backend() for teardown (process-level —
    rarely needed since process exit clears the patches).
    """
    if not _VLLM_FA_AVAILABLE:
        raise RuntimeError(
            "enable_int4_protected_backend requires vllm.attention.backends.flash_attn"
        )
    if _INSTALLED_PATCHES.get("phase5b_3a", False):
        return

    # --- 1. CacheConfig._verify_cache_dtype patch ---
    import vllm.config as vllm_config
    original_verify = vllm_config.CacheConfig._verify_cache_dtype
    _INSTALLED_PATCHES["original_verify_cache_dtype"] = original_verify

    def _patched_verify(self):
        # Accept "int4_protected" as a valid dtype. Falls through to the
        # original method for all other values (auto, fp8 variants, etc.).
        if getattr(self, "cache_dtype", None) == "int4_protected":
            logger.info(
                "Using int4_protected kv cache dtype (Phase 5B.3a). "
                "Routes through Int4ProtectedAttentionBackend at init."
            )
            return
        return original_verify(self)

    vllm_config.CacheConfig._verify_cache_dtype = _patched_verify

    # --- 2. current_platform.get_attn_backend_cls patch ---
    from vllm.platforms import current_platform
    original_get_cls = current_platform.get_attn_backend_cls
    _INSTALLED_PATCHES["original_get_attn_backend_cls"] = original_get_cls
    _INSTALLED_PATCHES["platform"] = current_platform

    def _patched_get_cls(*args, **kwargs):
        # The signature is (selected_backend, head_size, dtype,
        # kv_cache_dtype, block_size, use_v1, use_mla) but we accept
        # *args/**kwargs to be robust to minor signature drift.
        # kv_cache_dtype is the 4th positional arg or "kv_cache_dtype" kwarg.
        kv_dtype = kwargs.get("kv_cache_dtype")
        if kv_dtype is None and len(args) >= 4:
            kv_dtype = args[3]
        if kv_dtype == "int4_protected":
            return (
                "kv_policy.phase5b_backend_install."
                "Int4ProtectedAttentionBackend"
            )
        return original_get_cls(*args, **kwargs)

    current_platform.get_attn_backend_cls = _patched_get_cls

    # --- 3. Clear the @cache on _cached_get_attn_backend ---
    from vllm.attention import selector as sel_mod
    cached = getattr(sel_mod, "_cached_get_attn_backend", None)
    if cached is not None and hasattr(cached, "cache_clear"):
        cached.cache_clear()

    # --- 4. Extend STR_DTYPE_TO_TORCH_DTYPE to accept "int4_protected" ---
    # CacheEngine.get_cache_block_size does
    #   STR_DTYPE_TO_TORCH_DTYPE[cache_config.cache_dtype]
    # which KeyErrors on "int4_protected" without this patch.
    #
    # Phase 5B.4b: map "int4_protected" -> torch.uint8 (1 byte/elem),
    # down from bf16 (2 bytes/elem). This halves per-block bytes, which
    # doubles num_blocks at the same gpu_memory_utilization budget.
    # The reserve-line bytes don't shrink (vLLM fills the budget either
    # way), but the per-block sizing is now INT4-aware. Phase 5B.4c
    # adds the matching write/read paths so the smaller storage isn't
    # just garbage.
    import sys as _sys
    patched_dict_ids: set = set()
    patched_dicts: list = []
    for mod_name, mod in list(_sys.modules.items()):
        if mod is None or not isinstance(mod_name, str) or not mod_name.startswith("vllm"):
            continue
        d = getattr(mod, "STR_DTYPE_TO_TORCH_DTYPE", None)
        if isinstance(d, dict) and id(d) not in patched_dict_ids:
            # Always overwrite (in case we changed the mapping between
            # 5B.3a's bf16 and 5B.4b's uint8 across script reloads).
            d["int4_protected"] = torch.uint8
            logger.info(
                "Patched STR_DTYPE_TO_TORCH_DTYPE in %s: "
                "'int4_protected' -> torch.uint8 (5B.4b: half bytes/elem)",
                mod_name,
            )
            patched_dicts.append((d, "int4_protected"))
            patched_dict_ids.add(id(d))
    _INSTALLED_PATCHES["str_dtype_dicts"] = patched_dicts

    _INSTALLED_PATCHES["phase5b_3a"] = True
    logger.info(
        "Phase 5B.3a installed: kv_cache_dtype='int4_protected' accepted; "
        "backend selection patched to return Int4ProtectedAttentionBackend."
    )


def disable_int4_protected_backend() -> None:
    """Undo the patches installed by enable_int4_protected_backend().
    Process-level — clears the module-level state. Mainly useful for
    test cleanup; normal use just relies on process exit."""
    if not _INSTALLED_PATCHES.get("phase5b_3a", False):
        return

    import vllm.config as vllm_config
    vllm_config.CacheConfig._verify_cache_dtype = (
        _INSTALLED_PATCHES["original_verify_cache_dtype"]
    )

    platform = _INSTALLED_PATCHES["platform"]
    platform.get_attn_backend_cls = (
        _INSTALLED_PATCHES["original_get_attn_backend_cls"]
    )

    from vllm.attention import selector as sel_mod
    cached = getattr(sel_mod, "_cached_get_attn_backend", None)
    if cached is not None and hasattr(cached, "cache_clear"):
        cached.cache_clear()

    # Undo STR_DTYPE_TO_TORCH_DTYPE extensions.
    for d, key in _INSTALLED_PATCHES.get("str_dtype_dicts", []):
        d.pop(key, None)

    _INSTALLED_PATCHES.clear()
    logger.info("Phase 5B.3a patches removed.")


def is_int4_protected_enabled() -> bool:
    """True iff enable_int4_protected_backend() has been called and
    not since disabled. Mainly for tests."""
    return _INSTALLED_PATCHES.get("phase5b_3a", False)
