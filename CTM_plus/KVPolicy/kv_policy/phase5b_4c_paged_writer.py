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

# Debug flag to bypass V packing (write V as bf16 into the cache instead).
# Set via PHASE5B_4C_BF16_V=1 to isolate packed-V correctness issues.
_BF16_V_ENV = "PHASE5B_4C_BF16_V"


def _bf16_v_mode() -> bool:
    return os.environ.get(_BF16_V_ENV, "").strip() in ("1", "true", "True", "yes")

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
# PagedKVWriter — per-layer quantizing writer.
# ----------------------------------------------------------------------

class PagedKVWriter:
    """Per-layer streaming KV quantizer that writes to vLLM's paged
    uint8 cache + external sidecar tensors.

    Lazy-allocates sidecars on first `write()` (needs kv_cache shape).
    batch=1 v1: one staging buffer per layer.

    Construction is cheap — no device-bound state. The expensive
    allocations happen in `_lazy_alloc()` on first write.
    """

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

        self.k_scale_ext: Optional[torch.Tensor] = None   # (NB, H, D) bf16
        self.k_xmin_ext:  Optional[torch.Tensor] = None   # (NB, H, D) bf16
        self.k_protect_ext: Optional[torch.Tensor] = None # (NB, BS, H, n_protect) bf16
        self.v_scale_ext: Optional[torch.Tensor] = None   # (NB, BS, H, v_n_groups) bf16
        self.v_xmin_ext:  Optional[torch.Tensor] = None   # (NB, BS, H, v_n_groups) bf16

        self.k_stage: Optional[torch.Tensor] = None       # (BS, H, D) bf16
        self.k_stage_count: int = 0                       # 0..BS-1
        self.k_stage_block_id: int = -1                   # block we're filling

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

        # K staging buffer.
        self.k_stage = torch.zeros((BS, H, D), dtype=dtype, device=device)
        self.k_stage_count = 0
        self.k_stage_block_id = -1

        self.NB, self.BS, self.H, self.D = NB, BS, H, D
        self.n_protect = n_protect
        self.v_n_groups = v_n_groups
        self._allocated = True

        logger.info(
            "PagedKVWriter layer=%d allocated: NB=%d BS=%d H=%d D=%d "
            "n_protect=%d v_n_groups=%d", self.layer_idx, NB, BS, H, D,
            n_protect, v_n_groups,
        )

    def reset_sequence(self) -> None:
        """Clear K staging state for a new sequence. Sidecar tensors
        and protect tables are kept (they're large + reusable)."""
        self.k_stage_count = 0
        self.k_stage_block_id = -1
        if self.k_stage is not None:
            self.k_stage.zero_()

    # ------------------------------------------------------------------
    # Write path.
    # ------------------------------------------------------------------

    def write(
        self,
        key: "torch.Tensor",            # (T, H_kv, D) bf16
        value: "torch.Tensor",          # (T, H_kv, D) bf16
        kv_cache: "torch.Tensor",       # (2, NB, BS, H_kv, D) uint8
        slot_mapping: "torch.Tensor",   # (T,) long
    ) -> None:
        """Quantize T new K/V tokens and write them into the paged cache
        + external sidecars at the slots given by slot_mapping.

        For each token:
          * V: quantize per-(h, group) along D, write nibbles into the
               V slot's first D/2 bytes, write scale/xmin into the V
               externals at (block_id, pos).
          * K: extract protected channels (write to k_protect_ext at
               (block_id, pos)), stage in k_stage. When the staging
               buffer fills a block, finalize the K group: quantize
               all 16 tokens with shared per-(h, d) scale, write nibbles
               into kv_cache[0]'s K slot, write scale/xmin into the K
               externals at block_id.
        """
        if not self._allocated:
            self._lazy_alloc(kv_cache)

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

        # Move slot_mapping to CPU once for the per-token Python loop.
        # (For v1 we accept the per-token cost; vectorize in v2.)
        slot_map_cpu = slot_mapping.to("cpu", dtype=torch.long, non_blocking=False)
        T = key.shape[0]
        dtype = self.sidecar_dtype
        BS = self.BS
        D = self.D
        half_D = D // 2

        # Cast K/V to sidecar dtype if needed (typically already bf16).
        if key.dtype != dtype:
            key = key.to(dtype)
        if value.dtype != dtype:
            value = value.to(dtype)

        for t in range(T):
            slot = int(slot_map_cpu[t].item())
            if slot < 0:
                # vLLM uses -1 for "do not write" padding slots.
                continue
            block_id = slot // BS
            pos = slot % BS

            # =============== V (per-token) ===============
            v_tok = value[t]   # (H, D)
            if _bf16_v_mode():
                # Debug mode: stash bf16 V in an external sidecar instead
                # of packing. Read path will gather from this sidecar and
                # pass directly to the kernel (skipping v_packed_*).
                # Allocate v_bf16_ext lazily on first use.
                if getattr(self, "_v_bf16_ext", None) is None:
                    self._v_bf16_ext = torch.zeros(
                        (self.NB, self.BS, self.H, self.D),
                        dtype=dtype, device=kv_cache.device,
                    )
                self._v_bf16_ext[block_id, pos] = v_tok
            else:
                v_grouped = v_tok.float().view(self.H, self.v_n_groups, self.v_group_size)
                v_max = v_grouped.amax(dim=-1)                          # (H, n_g)
                v_min = v_grouped.amin(dim=-1)
                v_scale_tok = ((v_max - v_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)
                q_v = ((v_grouped - v_min.unsqueeze(-1)) / v_scale_tok.unsqueeze(-1)) \
                    .round().clamp(0, 15).to(torch.uint8)               # (H, n_g, G)
                q_v_flat = q_v.view(self.H, D)
                v_packed = (q_v_flat[..., 0::2] & 0x0F) | ((q_v_flat[..., 1::2] & 0x0F) << 4)
                # v_packed: (H, D/2) uint8

                kv_cache[1, block_id, pos, :, :half_D] = v_packed
                self.v_scale_ext[block_id, pos] = v_scale_tok.to(dtype)
                self.v_xmin_ext [block_id, pos] = v_min.to(dtype)

            # =============== K (staged) ===============
            k_tok = key[t]    # (H, D)

            # Protected-channel extraction to external sidecar.
            gathered = torch.gather(k_tok, dim=1, index=self.protected_d_per_head)
            # gathered: (H, n_protect) bf16
            self.k_protect_ext[block_id, pos] = gathered

            # Detect block boundary crossing. If block_id changes mid-write,
            # we're starting a new group. Reset stage state.
            if block_id != self.k_stage_block_id:
                self.k_stage_block_id = block_id
                # If the previous group had a partial tail, it lives only
                # in our staging buffer at that point — and we just lost it
                # because k_stage is reused. For batch=1 v1 this means:
                # a new sequence (after reset_sequence) or a perfectly
                # block-aligned sequence boundary. Anything else implies a
                # multi-batch race, which v1 explicitly disallows.
                self.k_stage.zero_()
                self.k_stage_count = 0

            # Stage at the slot's intra-block position.
            self.k_stage[pos] = k_tok
            # Track count by max(seen pos) + 1 to be robust to non-monotone
            # writes (shouldn't happen in practice, but safer).
            if pos + 1 > self.k_stage_count:
                self.k_stage_count = pos + 1

            # Finalize on block boundary.
            if self.k_stage_count == BS:
                self._finalize_k_group(kv_cache, block_id)
                self.k_stage_count = 0
                # k_stage_block_id stays so the next token's check is correct;
                # k_stage values are stale until overwritten in the next group.

    def _finalize_k_group(
        self,
        kv_cache: "torch.Tensor",
        block_id: int,
    ) -> None:
        """Quantize the full staging buffer (BS, H, D) and write packed
        nibbles + scale + xmin to the cache + externals for this block."""
        BS = self.BS
        D = self.D
        half_D = D // 2

        buf_f = self.k_stage.float()                    # (BS, H, D)
        x_max = buf_f.amax(dim=0)                       # (H, D)
        x_min = buf_f.amin(dim=0)
        scale = ((x_max - x_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)

        q = ((buf_f - x_min.unsqueeze(0)) / scale.unsqueeze(0)) \
            .round().clamp(0, 15).to(torch.uint8)       # (BS, H, D)
        packed = (q[..., 0::2] & 0x0F) | ((q[..., 1::2] & 0x0F) << 4)  # (BS, H, D/2)

        # Write nibbles to all BS slots of this block.
        kv_cache[0, block_id, :, :, :half_D] = packed
        # Write per-(h, d) scale + xmin to externals.
        self.k_scale_ext[block_id] = scale.to(self.sidecar_dtype)
        self.k_xmin_ext [block_id] = x_min.to(self.sidecar_dtype)

    # ------------------------------------------------------------------
    # Introspection helpers (for verify scripts).
    # ------------------------------------------------------------------

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
