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

# Debug flag to bypass V packing (writer stashes bf16 V in a parallel
# sidecar; read path passes it as v_cache positional). Used to isolate
# V packed-path correctness vs K packed-path correctness.
_BF16_V_ENV = "PHASE5B_4C_BF16_V"


def _bf16_v_mode() -> bool:
    return os.environ.get(_BF16_V_ENV, "").strip() in ("1", "true", "True", "yes")


def _bf16_backing_max_seqlen() -> int:
    raw = os.environ.get(_BF16_BACKING_MAX_SEQLEN_ENV, "").strip()
    if not raw:
        return _DEFAULT_BF16_BACKING_MAX_SEQLEN
    try:
        return int(raw)
    except ValueError:
        return _DEFAULT_BF16_BACKING_MAX_SEQLEN


def _max_active_slots() -> int:
    raw = os.environ.get(_MAX_ACTIVE_SLOTS_ENV, "").strip()
    if not raw:
        return _DEFAULT_MAX_ACTIVE_SLOTS
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_MAX_ACTIVE_SLOTS

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
    def bf16_k_backing(self) -> "torch.Tensor":
        # (1, max_S, H, D) — preserves the historical leading-1 batch
        # dim that callers slice as state.bf16_k_backing[0, :S, ...].
        s = self.slot_idx
        return self._writer._bf16_k_backing_pool[s:s + 1]

    @property
    def bf16_v_backing(self) -> "torch.Tensor":
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
        decode read. Replaces the per-seq Python copy loop in
        `get_bf16_backing_batched` with a single CUDA gather.

        Returns (B, S_padded, H, D), (B, S_padded, H, D) — both bf16.
        """
        if not self._allocated:
            raise RuntimeError("get_bf16_backing_batched_by_slots before _lazy_alloc")
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
        self._bf16_k_backing_pool = torch.zeros(
            (n_slots, max_S, H, D), dtype=torch.bfloat16, device=device,
        )
        self._bf16_v_backing_pool = torch.zeros(
            (n_slots, max_S, H, D), dtype=torch.bfloat16, device=device,
        )
        # Slots are handed out via ensure_seq_state; default seq takes 0.
        self._free_slots = list(range(n_slots))
        self._allocated = True

        # Phase 5B.6 step 1: per-sequence state container. Allocate the
        # default seq right away so legacy single-seq attribute access
        # (self.k_stage, self.bf16_k_backing, etc.) returns a valid
        # tensor immediately. Multi-seq callers call ensure_seq_state
        # on demand for additional seqs.
        default_slot = self._free_slots.pop(0)
        default = SeqState(self, default_slot)
        self._seq_states[self.DEFAULT_SEQ_ID] = default
        self._slot_map[self.DEFAULT_SEQ_ID] = default_slot

        logger.info(
            "PagedKVWriter layer=%d allocated: NB=%d BS=%d H=%d D=%d "
            "n_protect=%d v_n_groups=%d", self.layer_idx, NB, BS, H, D,
            n_protect, v_n_groups,
        )

    def reset_sequence(self, seq_id: Any = None) -> None:
        """Reset streaming state for one sequence (default seq if None)
        or ALL sequences (seq_id='all').

        Per-LAYER sidecar tensors (k_scale_ext etc.) are kept — they're
        large and reusable; positions of dropped sequences will be
        overwritten by future writes.

        Phase 6 v2 Option B pre-flight (B-pre-1): `seq_id='all'` now ALSO
        evicts all non-default sequences (frees their slots back to the
        pool). The DEFAULT_SEQ_ID slot is retained — legacy single-seq
        callers expect the writer.k_stage / .bf16_k_backing proxy
        properties to keep returning valid tensors after reset.

        This change is required to keep the slot pool (default size 8)
        from filling up across long-lived workloads that cycle through
        many seq_ids (e.g., benches that run B=1, 2, 4, 8 back-to-back
        without an explicit evict_sequence pass).
        """
        if seq_id == "all":
            # Evict non-default seqs FIRST so their slots return to the
            # free pool; iterate over a snapshot of keys to avoid mutating
            # during iteration.
            for sid in list(self._seq_states.keys()):
                if sid == self.DEFAULT_SEQ_ID:
                    continue
                self.evict_sequence(sid)
            # Then reset the default seq's streaming state in place.
            default = self._seq_states.get(self.DEFAULT_SEQ_ID)
            if default is not None:
                default.reset()
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
        """
        if seq_id is None:
            seq_id = self.DEFAULT_SEQ_ID
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
