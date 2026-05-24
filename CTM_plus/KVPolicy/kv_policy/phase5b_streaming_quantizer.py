"""Phase 5B.1 — partial-group streaming quantizer.

Accepts K tokens one at a time (or in batches), maintains a partial-group
staging buffer, and finalizes the quantized output when each group fills.
Produces packed tensors in the SAME format as
`kv_policy.phase2_4_packed_kv.pack_k_for_phase2_4` (verified bit-equivalent
via verify_phase5b_1_streaming.py).

Why this exists:
  Phase 2.4.1c v0 does a full O(S) repack on every decode step. Phase 2.4.1d
  does an O(group_size) per-group repack on the cached BF16 K sidecar, but
  STILL holds the full FP16 K sidecar in memory.

  Phase 5B's design (KERNEL_6C3C_PHASE5B5C_DESIGN.md Q3) eliminates the FP16
  K sidecar entirely. New K tokens flow into a SMALL partial-group buffer
  (group_size × H × D bf16, ~4 KB at Qwen target). When the buffer fills,
  quantize-pack-write to the paged INT4 cache, clear buffer, repeat. The
  full BF16 K is never held end-to-end.

  This class is the staging buffer logic, tested standalone before
  integrating with vLLM's BlockManager (Phase 5B.4).

Locked design decisions (from PHASE5B5C_DESIGN.md):
  - group_size = 16 = vLLM block_size. (Q2)
  - Protect mask is FROZEN per-model, supplied at construction. (Q1)
  - Quantize-on-fill (not lazy-on-read). (Q3)

Memory cost per (layer, h_kv) of the staging buffer:
  group_size × D × 2 bytes = 16 × 128 × 2 = 4 KB.
  Across 28 layers × 4 H_kv = 112 buffers × 4 KB = ~448 KB total per model.
  Negligible.

Numerical convention matches `pack_k_for_phase2_4` exactly:
  scale = max((x_max - x_min) / 15.0, 1e-8)
  q     = round((x - x_min) / scale).clamp(0, 15)
  x_hat = q * scale + x_min
  Even d -> low nibble, odd d -> high nibble of byte[d/2].
"""
from __future__ import annotations

from typing import Any, Dict, Optional

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore


# Module-level constants (mirror Phase 2.4.0 conventions).
_ASYM_DIV    = 15.0
_SCALE_CLAMP = 1e-8


class PartialGroupQuantizer:
    """Streaming INT4 quantizer with a partial-group staging buffer.

    Designed for the Phase 5B cache write path: new K tokens arrive
    one (or several) at a time during prefill/decode, get staged in a
    (group_size, H, D) BF16 buffer, and are quantized + packed into
    the output sidecar tensors when the buffer fills.

    The frozen protect_mask is required at construction — protected
    channels are extracted into k_protect_bf16 AS EACH TOKEN ARRIVES
    (without waiting for a full group), because protect values are
    per-token and don't depend on group statistics.

    API:
      append(k_new)  - add one or more K tokens. (T, H, D) bf16.
      flush()        - finalize any partial group (zero-pads to G).
      get_packed()   - returns the dict in pack_k_for_phase2_4 format.
      reset()        - clear state for a new sequence (keeps allocations).
    """

    def __init__(
        self,
        num_kv_heads: int,
        head_dim: int,
        max_seqlen: int,
        *,
        protect_mask: "torch.Tensor",   # (H_kv, D) int8, 1 = protected
        group_size: int = 16,
        dtype: "torch.dtype" = None,    # default bf16
        device: "torch.device" = None,  # default protect_mask's device
    ) -> None:
        if torch is None:
            raise RuntimeError("PartialGroupQuantizer requires torch")
        if protect_mask.ndim != 2:
            raise ValueError(
                f"protect_mask shape (H_kv, D) required; got {tuple(protect_mask.shape)}"
            )
        if protect_mask.shape != (num_kv_heads, head_dim):
            raise ValueError(
                f"protect_mask shape {tuple(protect_mask.shape)} != "
                f"(num_kv_heads={num_kv_heads}, head_dim={head_dim})"
            )
        if head_dim % 2 != 0:
            raise ValueError(f"head_dim={head_dim} must be even for nibble packing")
        if max_seqlen % group_size != 0:
            raise ValueError(
                f"max_seqlen={max_seqlen} must be a multiple of group_size={group_size}"
            )

        self.H = num_kv_heads
        self.D = head_dim
        self.G = group_size
        self.max_seqlen = max_seqlen
        if device is None:
            device = protect_mask.device
        if dtype is None:
            dtype = torch.bfloat16
        self.device = device
        self.dtype = dtype

        # ---- Frozen mask + derived tables ----
        # protect_mask : (H, D) int8, 1 = protected.
        self.protect_mask = protect_mask.to(device=device, dtype=torch.int8)
        # n_protect from per-row max (protect mask should be uniform).
        self.n_protect = max(1, int(self.protect_mask.sum(dim=-1).max().item()))
        # protect_slot : (H, D) int8, slot index or -1 (matches Phase 2.4.0).
        self.protect_slot = self._build_protect_slot()
        # protected_d_per_head : (H, n_protect) long for fast gather.
        self.protected_d_per_head = self._build_protected_d()

        # ---- Output tensors (preallocated for max_seqlen) ----
        S = max_seqlen
        H = num_kv_heads
        D = head_dim
        G = group_size
        n_groups = S // G
        n_protect = self.n_protect
        self.k_int4 = torch.zeros((1, S, H, D // 2), dtype=torch.uint8, device=device)
        self.k_scale = torch.zeros((1, n_groups, H, D), dtype=dtype, device=device)
        self.k_xmin  = torch.zeros((1, n_groups, H, D), dtype=dtype, device=device)
        self.k_protect_bf16 = torch.zeros((1, S, H, n_protect), dtype=dtype, device=device)

        # ---- Streaming state ----
        self.staging_buffer = torch.zeros((G, H, D), dtype=dtype, device=device)
        self.tokens_in_buffer = 0          # 0..G-1
        self.completed_groups = 0          # 0..n_groups
        self.s_curr = 0                    # total tokens appended

    # ------------------------------------------------------------------
    # Setup helpers (run once at __init__).
    # ------------------------------------------------------------------

    def _build_protect_slot(self) -> "torch.Tensor":
        """Build (H, D) int8 slot table from the protect mask.
        protect_slot[h, d] = slot index in [0, n_protect) if protected,
        else -1. Slots are sequential 0..n_protect-1 in ascending order of d.
        """
        H, D = self.protect_mask.shape
        slot = torch.full((H, D), -1, dtype=torch.int8, device=self.device)
        for h in range(H):
            idx = torch.nonzero(self.protect_mask[h] >= 1, as_tuple=True)[0]
            slot[h, idx] = torch.arange(
                len(idx), dtype=torch.int8, device=self.device,
            )
        return slot

    def _build_protected_d(self) -> "torch.Tensor":
        """Build (H, n_protect) long tensor of protected D-indices per head,
        sorted ascending — matches protect_slot ordering."""
        H, D = self.protect_mask.shape
        n = self.n_protect
        protected_d = torch.zeros((H, n), dtype=torch.long, device=self.device)
        for h in range(H):
            idx = torch.nonzero(self.protect_mask[h] >= 1, as_tuple=True)[0]
            protected_d[h, :len(idx)] = idx
        return protected_d

    # ------------------------------------------------------------------
    # Streaming API.
    # ------------------------------------------------------------------

    def append(self, k_new: "torch.Tensor") -> None:
        """Append T new K tokens. Shape (T, H, D).

        For each token:
          1. Extract protected-channel values via gather; write to
             k_protect_bf16[0, s_curr].
          2. Write the full token to the staging buffer slot.
          3. Advance s_curr and tokens_in_buffer.
          4. If tokens_in_buffer == group_size, finalize the group.
        """
        if k_new.ndim != 3:
            raise ValueError(f"append expects (T, H, D); got {tuple(k_new.shape)}")
        T, H, D = k_new.shape
        if H != self.H or D != self.D:
            raise ValueError(
                f"append shape ({H}, {D}) != expected ({self.H}, {self.D})"
            )
        if self.s_curr + T > self.max_seqlen:
            raise RuntimeError(
                f"append overflow: s_curr={self.s_curr} + T={T} > "
                f"max_seqlen={self.max_seqlen}"
            )

        # Cast input to dtype if needed.
        if k_new.dtype != self.dtype:
            k_new = k_new.to(self.dtype)

        # Process tokens one-at-a-time. This is the simple v0 path; a
        # vectorized "append a batch of T tokens" optimization could
        # process all of T at once when (s_curr % G + T) doesn't cross
        # a group boundary, but the per-token loop is correct and easy
        # to verify. Phase 5B.4 / later can optimize.
        for t in range(T):
            tok = k_new[t]   # (H, D)

            # (1) Protected-channel gather + write to compact sidecar.
            gathered = torch.gather(tok, dim=1, index=self.protected_d_per_head)
            # gathered shape: (H, n_protect)
            self.k_protect_bf16[0, self.s_curr] = gathered

            # (2) Stage full token in the partial-group buffer.
            self.staging_buffer[self.tokens_in_buffer] = tok

            # (3) Advance counters.
            self.tokens_in_buffer += 1
            self.s_curr += 1

            # (4) Finalize if group is full.
            if self.tokens_in_buffer == self.G:
                self._finalize_group()

    def flush(self) -> None:
        """Finalize a partial group at end-of-prefill / end-of-sequence.

        Zero-pads remaining slots in the staging buffer and emits the
        last group. Idempotent if the buffer is already empty.
        Numerically equivalent to packing K zero-padded to a multiple
        of group_size (matches the pack_k_for_phase2_4 convention since
        max_seqlen is a multiple of G; zeros in the padded slots stay
        within the typical K range, validated in Phase 2.4.1c).
        """
        if self.tokens_in_buffer == 0:
            return
        # Zero the remaining slots in the staging buffer so the
        # quantization for the partial group uses true zeros for the
        # padding (matches the zero-init of self.k_fp16 in Phase 2.4.1c
        # which is what pack_k_for_phase2_4 was tested against).
        self.staging_buffer[self.tokens_in_buffer:] = 0
        self._finalize_group()

    def _finalize_group(self) -> None:
        """Quantize the current staging buffer's (G, H, D) tokens into
        the output sidecar tensors at the appropriate group slot."""
        g = self.completed_groups
        g_start = g * self.G
        g_end = g_start + self.G

        # Per-group max/min reduction over G. Cast to float for the
        # math to match pack_k_for_phase2_4's numerical convention.
        buf_f = self.staging_buffer.float()                     # (G, H, D)
        x_max = buf_f.amax(dim=0, keepdim=True)                  # (1, H, D)
        x_min = buf_f.amin(dim=0, keepdim=True)
        scale = ((x_max - x_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)

        # Quantize all G tokens with this group's scale.
        q = ((buf_f - x_min) / scale).round().clamp(0, 15).to(torch.uint8)  # (G, H, D)

        # Pack nibbles: even -> low, odd -> high.
        even = q[..., 0::2]
        odd  = q[..., 1::2]
        packed_bytes = (even & 0x0F) | ((odd & 0x0F) << 4)        # (G, H, D/2)

        # Splice into output tensors.
        self.k_int4[0, g_start:g_end] = packed_bytes
        # scale / x_min: (1, H, D) -> (1, H, D) slot in (1, n_groups, H, D).
        self.k_scale[0, g:g+1] = scale.to(self.dtype)
        self.k_xmin [0, g:g+1] = x_min.to(self.dtype)

        # Advance state. tokens_in_buffer reset to 0; staging buffer
        # will be overwritten by the next group's appends.
        self.completed_groups += 1
        self.tokens_in_buffer = 0

    def get_packed(self) -> Dict[str, Any]:
        """Return the packed dict in pack_k_for_phase2_4 format.

        WARNING: positions [s_curr, max_seqlen) are zero-init and
        contain no real data. The caller is responsible for telling
        the kernel which range to attend to (via cache_seqlens).
        """
        return {
            "k_int4":         self.k_int4,
            "k_scale":        self.k_scale,
            "k_xmin":         self.k_xmin,
            "k_protect_bf16": self.k_protect_bf16,
            "protect_slot":   self.protect_slot,
            "n_protect":      self.n_protect,
            "group_size":     self.G,
        }

    def reset(self) -> None:
        """Clear streaming state for a new sequence. Keeps the
        preallocated output tensors AND the frozen protect mask /
        protect_slot / protected_d_per_head (those are model-static)."""
        self.staging_buffer.zero_()
        self.tokens_in_buffer = 0
        self.completed_groups = 0
        self.s_curr = 0
        # NOTE: we do NOT zero the output tensors here. The next
        # append() will overwrite them group-by-group. If the next
        # sequence is shorter than the last, positions [s_curr_new,
        # s_curr_old) retain old data — but cache_seqlens prevents
        # the kernel from reading them.
