"""Phase 2.6.1 — streaming V quantizer.

V-side equivalent of Phase 5B.1's PartialGroupQuantizer (K side), but
structurally SIMPLER because V quantization has no cross-token state:

  - K's group axis is SEQ. Each group of `group_size` tokens shares one
    scale per channel. Decode tokens accumulate into a partial group
    until it fills, then finalize. Requires a staging buffer.
  - V's group axis is HEAD_DIM. Each token is INDEPENDENTLY quantized
    into n_groups channel-groups, each with its own scale + xmin.
    No staging. No cross-token coupling.

So this class is:

  - No staging buffer.
  - No flush() (nothing partial to finalize).
  - `append(v_new)` is fully vectorized across T tokens — no Python loop
    in the hot path.
  - Splice directly into pre-allocated output tensors at [s_curr:s_curr+T].

Designed for the Phase 5B.4c.1 cache write path: new V tokens arrive
one (or batched) at a time during prefill / decode, get quantized
inline, and land directly in the paged INT4 V cache.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore


_ASYM_DIV    = 15.0
_SCALE_CLAMP = 1e-8


class ValueGroupQuantizer:
    """Streaming V quantizer with per-(token, head, channel_group) scale.

    Designed for the Phase 5B.4c cache write path: new V tokens stream
    in (T may be 1 at decode, > 1 at prefill) and get quantized
    in-place into preallocated output tensors. Output dict matches
    `kv_policy.phase2_6_packed_v.pack_v_for_phase2_6` format.

    API:
      append(v_new)  - add T new V tokens. (T, H, D) bf16/fp16.
      get_packed()   - returns the dict in pack_v_for_phase2_6 format.
      reset()        - clear state for a new sequence (keeps allocations).
    """

    def __init__(
        self,
        num_kv_heads: int,
        head_dim: int,
        max_seqlen: int,
        *,
        v_group_size: int = 32,
        dtype: "torch.dtype" = None,
        device: "torch.device" = None,
    ) -> None:
        if torch is None:
            raise RuntimeError("ValueGroupQuantizer requires torch")
        if head_dim % v_group_size != 0:
            raise ValueError(
                f"head_dim={head_dim} must be divisible by v_group_size={v_group_size}"
            )
        if head_dim % 2 != 0:
            raise ValueError(f"head_dim={head_dim} must be even for nibble packing")
        if dtype is None:
            dtype = torch.bfloat16

        self.H = num_kv_heads
        self.D = head_dim
        self.G = v_group_size
        self.n_groups = head_dim // v_group_size
        self.max_seqlen = max_seqlen
        self.dtype = dtype
        self.device = device

        S = max_seqlen
        H = num_kv_heads
        D = head_dim
        n_groups = self.n_groups
        self.v_int4  = torch.zeros((1, S, H, D // 2),   dtype=torch.uint8, device=device)
        self.v_scale = torch.zeros((1, S, H, n_groups), dtype=dtype,        device=device)
        self.v_xmin  = torch.zeros((1, S, H, n_groups), dtype=dtype,        device=device)

        self.s_curr = 0

    # ------------------------------------------------------------------
    # Streaming API.
    # ------------------------------------------------------------------

    def append(self, v_new: "torch.Tensor") -> None:
        """Append T new V tokens. Shape (T, H, D).

        Vectorized across T — no per-token Python loop. Same numerical
        convention as `pack_v_for_phase2_6` (verified bit-equivalent via
        verify_phase2_6_1_streaming.py).
        """
        if v_new.ndim != 3:
            raise ValueError(f"append expects (T, H, D); got {tuple(v_new.shape)}")
        T, H, D = v_new.shape
        if H != self.H or D != self.D:
            raise ValueError(
                f"append shape ({H}, {D}) != expected ({self.H}, {self.D})"
            )
        if self.s_curr + T > self.max_seqlen:
            raise RuntimeError(
                f"append overflow: s_curr={self.s_curr} + T={T} > "
                f"max_seqlen={self.max_seqlen}"
            )
        if v_new.dtype != self.dtype:
            v_new = v_new.to(self.dtype)

        n_groups = self.n_groups
        G = self.G

        # Group along D axis: (T, H, D) -> (T, H, n_groups, G).
        v_grouped = v_new.float().view(T, H, n_groups, G)
        x_max = v_grouped.amax(dim=-1)         # (T, H, n_groups)
        x_min = v_grouped.amin(dim=-1)
        scale = ((x_max - x_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)

        q = ((v_grouped - x_min.unsqueeze(-1)) / scale.unsqueeze(-1)) \
            .round().clamp(0, 15).to(torch.uint8)   # (T, H, n_groups, G)
        q_flat = q.view(T, H, D)

        even = q_flat[..., 0::2]
        odd  = q_flat[..., 1::2]
        packed = (even & 0x0F) | ((odd & 0x0F) << 4)  # (T, H, D/2)

        # Splice into output tensors at [s_curr:s_curr+T].
        s = self.s_curr
        self.v_int4 [0, s:s+T] = packed
        self.v_scale[0, s:s+T] = scale.to(self.dtype)
        self.v_xmin [0, s:s+T] = x_min.to(self.dtype)
        self.s_curr += T

    def get_packed(self) -> Dict[str, Any]:
        """Return the packed dict in pack_v_for_phase2_6 format.

        WARNING: positions [s_curr, max_seqlen) are zero-init and
        contain no real V data. The caller is responsible for telling
        the kernel which range to attend to (via cache_seqlens).
        """
        return {
            "v_int4":       self.v_int4,
            "v_scale":      self.v_scale,
            "v_xmin":       self.v_xmin,
            "v_group_size": self.G,
        }

    def reset(self) -> None:
        """Clear streaming state for a new sequence. Keeps the
        preallocated output tensors. Next append() will overwrite
        positions [0, ...] of the output tensors."""
        self.s_curr = 0
