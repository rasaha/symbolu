"""Phase 2.6.0 — packed INT4 V storage helpers (Python side).

V-side mirror of phase2_4_packed_kv.py (Phase 2.4.0). Key differences
from the K-side helper, locked in KERNEL_6C3C_PHASE2_6_V_PACK_DESIGN.md:

  - Group axis: HEAD_DIM (v_group_size=32 channels per group).
    Each token's V is independently quantized. D=128 channels split
    into 4 groups of 32 each.
  - NO protect-V sidecar (V doesn't exhibit the outlier-channel
    concentration K does, per KIVI + §20.4.3).
  - Per-token scale/xmin: 4 entries each (n_groups = D / v_group_size).

Convention:
    For each (token, head, group_of_channels) (group_size = 32 channels):
        x_min   = min(V_token_h_group)
        x_max   = max(V_token_h_group)
        scale   = max((x_max - x_min) / 15.0, 1e-8)
        q       = round((x - x_min) / scale).clamp(0, 15)     # uint nibble
        x_hat   = q * scale + x_min                            # exact inverse

    Storage:
        q is packed 2 nibbles per byte along D axis:
          byte[d/2] = q[d_even] | (q[d_odd] << 4)
        scale, x_min stored as bf16 per (token, head, group_idx).

V1 SCOPE:
    - No protect-V mask. V outliers not concentrated like K's.
    - Sidecar tensors as SEPARATE torch tensors (matches Phase 2.4.0
      decision).
    - The accompanying CUDA kernel that reads this format is Phase 2.6.2
      work (not in this module).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore


# Matches Phase 2.4.0 / Phase 2.3 in-kernel constants exactly.
_INT4_BITS = 4
_ASYM_DIV  = float((1 << _INT4_BITS) - 1)  # 15
_SCALE_CLAMP = 1e-8
_QMIN_UNSIGNED = 0
_QMAX_UNSIGNED = 15


def _pack_nibbles(q_unsigned: "torch.Tensor") -> "torch.Tensor":
    """Pack last dim of uint8 nibbles [0,15] into uint8 bytes
    (2 nibbles per byte). Even nibble in low 4 bits, odd in high.

    Input:  (..., D) uint8, values in [0, 15], D must be even.
    Output: (..., D/2) uint8.

    Matches phase2_4_packed_kv._pack_nibbles byte-for-byte (the nibble
    packing convention is shared K and V).
    """
    if q_unsigned.shape[-1] % 2 != 0:
        raise ValueError(
            f"pack_nibbles requires even last dim; got {q_unsigned.shape[-1]}"
        )
    even = q_unsigned[..., 0::2]
    odd  = q_unsigned[..., 1::2]
    return (even & 0x0F) | ((odd & 0x0F) << 4)


def _unpack_nibbles(packed: "torch.Tensor", target_d: int) -> "torch.Tensor":
    """Inverse of _pack_nibbles. Returns (..., target_d) uint8.

    target_d must equal packed.shape[-1] * 2.
    """
    if target_d != packed.shape[-1] * 2:
        raise ValueError(
            f"unpack target_d {target_d} != packed.shape[-1]*2 "
            f"{packed.shape[-1] * 2}"
        )
    low  = packed & 0x0F
    high = (packed >> 4) & 0x0F
    out = torch.stack([low, high], dim=-1)
    return out.reshape(*packed.shape[:-1], target_d)


def pack_v_for_phase2_6(
    v_bf16: "torch.Tensor",           # (1, S, H_kv, D) bf16/fp16
    *,
    v_group_size: int = 32,
) -> Dict[str, "torch.Tensor"]:
    """Pack a single layer's V into the Phase 2.6 sidecar format.

    Args:
        v_bf16: (1, S_kv, H_kv, D) bf16 V.
        v_group_size: along-head_dim quant group size. v1 locked to 32.

    Returns dict with keys:
        v_int4       : (1, S, H_kv, D//2)                uint8
                       — packed nibbles, two channels per byte
        v_scale      : (1, S, H_kv, D//v_group_size)     bf16
                       — per-(token, head, channel_group) scale
        v_xmin       : (1, S, H_kv, D//v_group_size)     bf16
                       — per-(token, head, channel_group) x_min
        v_group_size : int                                — = v_group_size

    Notes:
        - D MUST be divisible by v_group_size AND by 2.
        - No S divisibility requirement (V is per-token; no cross-token
          grouping).
        - No protect mask. V doesn't need K's outlier protection.
    """
    if v_bf16.ndim != 4 or v_bf16.shape[0] != 1:
        raise ValueError(
            f"pack_v expects (1, S, H, D); got {tuple(v_bf16.shape)}"
        )
    _, S, H, D = v_bf16.shape
    if D % v_group_size != 0:
        raise ValueError(
            f"D={D} must be divisible by v_group_size={v_group_size}"
        )
    if D % 2 != 0:
        raise ValueError(f"D={D} must be even for nibble packing")

    n_groups = D // v_group_size

    # ---- Per-(token, head, channel_group) scale + x_min ----
    # Reshape (1, S, H, D) -> (1, S, H, n_groups, v_group_size), reduce over last dim.
    v_grouped = v_bf16.float().view(1, S, H, n_groups, v_group_size)
    x_max = v_grouped.amax(dim=-1)  # (1, S, H, n_groups)
    x_min = v_grouped.amin(dim=-1)
    scale = ((x_max - x_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)

    # Quantize per group. Broadcast scale/x_min over the channel_group axis.
    q = ((v_grouped - x_min.unsqueeze(-1)) / scale.unsqueeze(-1)) \
        .round().clamp(_QMIN_UNSIGNED, _QMAX_UNSIGNED).to(torch.uint8)
    # Flatten the channel_group dim back into D for packing.
    q_flat = q.view(1, S, H, D)

    # ---- Pack nibbles along the D axis ----
    v_int4 = _pack_nibbles(q_flat)  # (1, S, H, D//2) uint8

    v_scale = scale.to(v_bf16.dtype)
    v_xmin  = x_min.to(v_bf16.dtype)

    return {
        "v_int4":       v_int4,
        "v_scale":      v_scale,
        "v_xmin":       v_xmin,
        "v_group_size": v_group_size,
    }


def unpack_v_from_phase2_6(packed: Dict[str, Any]) -> "torch.Tensor":
    """Inverse of pack_v_for_phase2_6.

    For each (token, h, channel_group): dequant via q * scale + x_min.
    No protect path (V has no protect mask in v1).
    """
    v_int4       = packed["v_int4"]
    v_scale      = packed["v_scale"].float()
    v_xmin       = packed["v_xmin"].float()
    v_group_size = packed["v_group_size"]

    _, S, H, D_half = v_int4.shape
    D = D_half * 2
    n_groups = v_scale.shape[-1]
    if n_groups * v_group_size != D:
        raise ValueError(
            f"n_groups*v_group_size {n_groups*v_group_size} != D {D}"
        )

    # Unpack nibbles -> uint8 in [0, 15].
    q = _unpack_nibbles(v_int4, target_d=D).float()    # (1, S, H, D)

    # Reshape to (1, S, H, n_groups, v_group_size) for per-group dequant.
    q_grouped = q.view(1, S, H, n_groups, v_group_size)
    v_hat_grouped = q_grouped * v_scale.unsqueeze(-1) + v_xmin.unsqueeze(-1)
    out_dtype = packed["v_scale"].dtype
    return v_hat_grouped.view(1, S, H, D).to(out_dtype)


def round_trip_v_max_error(
    v_bf16: "torch.Tensor",
    *,
    v_group_size: int = 32,
) -> Dict[str, float]:
    """Pack v -> unpack -> compare. Returns per-element error stats.

    The unpack output is NOT bit-equal to input — INT4 quantization
    is lossy. Per-channel-group error bounded by ~scale (per-group LSB).

    Pass criterion (the test below):
      - Per-element error <= ~max(scale) over the corpus.
      - No mean drift (mean error close to 0; only spread matters).
    """
    packed = pack_v_for_phase2_6(v_bf16, v_group_size=v_group_size)
    v_rt = unpack_v_from_phase2_6(packed)

    diff = (v_bf16.float() - v_rt.float()).abs()
    return {
        "max_abs":      float(diff.max().item()),
        "mean_abs":     float(diff.mean().item()),
        "median_abs":   float(diff.flatten().median().item()),
        "n_total":      int(diff.numel()),
    }


def v_sidecar_byte_size(
    S: int, H: int, D: int,
    *,
    v_group_size: int = 32,
    dtype_bytes: int = 2,  # bf16 == 2 bytes
) -> Dict[str, int]:
    """V sidecar memory accounting per layer at sequence length S.

    Returns dict of per-tensor bytes + total. Used to validate the
    Phase 2.6 design doc's memory math.
    """
    n_groups = D // v_group_size
    bytes_v_int4  = S * H * (D // 2)               # uint8
    bytes_v_scale = S * H * n_groups * dtype_bytes # bf16
    bytes_v_xmin  = S * H * n_groups * dtype_bytes # bf16
    total = bytes_v_int4 + bytes_v_scale + bytes_v_xmin
    return {
        "v_int4":       bytes_v_int4,
        "v_scale":      bytes_v_scale,
        "v_xmin":       bytes_v_xmin,
        "total":        total,
        "bf16_baseline": S * H * D * dtype_bytes,
        "compression":  (S * H * D * dtype_bytes) / total,
        "n_groups":     n_groups,
        "per_token_bytes": total // S,
    }
