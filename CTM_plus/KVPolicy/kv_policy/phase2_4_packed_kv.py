"""Phase 2.4 — packed INT4 K storage helpers (Python side).

These are the Python pack/unpack functions for the Phase 2.4 sidecar.
They mirror the route-B asymmetric INT4 quantization convention used
by Phase 2.3's in-kernel transform (`int4_inline.h`) — so the CUDA
kernel reading the packed layout will produce numerically identical
output to Phase 5A's in-register quant on the same K.

Convention:
    For each group along seq (group_size = 32 by default):
        x_min   = min(K_group_h_d)                            # per (h, d)
        x_max   = max(K_group_h_d)
        scale   = max((x_max - x_min) / 15.0, 1e-8)
        q       = round((x - x_min) / scale).clamp(0, 15)     # uint nibble
        x_hat   = q * scale + x_min                            # exact inverse

    Storage:
        q is packed 2 nibbles per byte: byte[d/2] = q[d_even] | (q[d_odd] << 4)
        scale, x_min stored as bf16 per (group, h, d)

    Protected channels (top-`protect_fraction` magnitude per (h)):
        Stored at full BF16 precision in a compact (S, H, n_protect)
        tensor. protect_slot[(h, d)] is the index into that compact
        tensor (or -1 if d is not protected).
        At read time, the kernel returns the BF16 value directly for
        protected channels, bypassing the dequant path.

V1 SCOPE:
    - V cache is NOT packed in Phase 2.4 — V stays BF16 in the
      sidecar. Phase 2.6 mirrors this file for V.
    - Sidecar tensors are managed as SEPARATE torch tensors (per the
      Phase 2.4 design doc decision). No fat allocation.
    - The accompanying CUDA kernel that reads this packed format is
      Phase 2.4.1 work (not in this commit).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore


# Matches Phase 2.3 in-kernel constants (see int4_inline.h).
_INT4_BITS = 4
_ASYM_DIV  = float((1 << _INT4_BITS) - 1)  # 15
_SCALE_CLAMP = 1e-8
_QMIN_UNSIGNED = 0
_QMAX_UNSIGNED = 15


def _select_protect_mask(
    k_bf16: "torch.Tensor",     # (1, S, H, D)
    protect_fraction: float,
) -> "torch.Tensor":
    """Returns (H, D) int8 mask: 1 if protected, 0 if not.

    Selection rule: top-`protect_fraction` channels by per-channel
    max-abs across the seq dim, per kv_head. Matches the §20.4.3
    static mask convention used in Phase 4 and Phase 5A.
    """
    # k_bf16: (1, S, H, D). Per-channel magnitude:
    ch_mag = k_bf16.float().abs().amax(dim=1).squeeze(0)  # (H, D)
    H, D = ch_mag.shape
    n_protect = max(1, int(round(D * protect_fraction)))
    _, topk_idx = ch_mag.topk(n_protect, dim=-1)          # (H, n_protect)
    mask = torch.zeros((H, D), dtype=torch.int8, device=ch_mag.device)
    mask.scatter_(-1, topk_idx, 1)
    return mask


def _build_protect_slot(
    protect_mask: "torch.Tensor",   # (H, D) int8
) -> "torch.Tensor":
    """Returns (H, D) int8: protected channels get sequential slot
    indices 0..n_protect-1 sorted by d; unprotected get -1.

    The kernel uses protect_slot[h, d] >= 0 as the "is protected"
    check AND as the index into the compact k_protect_bf16 tensor's
    last dim.
    """
    H, D = protect_mask.shape
    slot = torch.full((H, D), -1, dtype=torch.int8, device=protect_mask.device)
    for h in range(H):
        # Indices of protected channels for this head, sorted ascending.
        idx = torch.nonzero(protect_mask[h], as_tuple=True)[0]
        slot[h, idx] = torch.arange(len(idx), dtype=torch.int8,
                                    device=protect_mask.device)
    return slot


def _pack_nibbles(q_unsigned: "torch.Tensor") -> "torch.Tensor":
    """Pack last dim of uint8 nibbles [0,15] into uint8 bytes
    (2 nibbles per byte). Even nibble in low 4 bits, odd in high.

    Input:  (..., D) uint8, values in [0, 15], D must be even.
    Output: (..., D/2) uint8.
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

    target_d must equal packed.shape[-1] * 2 (no odd-D padding handled
    in this v1 — Qwen2.5-7B has D=128 which is even).
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


def pack_k_for_phase2_4(
    k_bf16: "torch.Tensor",           # (1, S, H, D) bf16/fp16
    *,
    group_size: int = 32,
    protect_fraction: float = 0.04,
) -> Dict[str, "torch.Tensor"]:
    """Pack a single layer's K into the Phase 2.4 sidecar format.

    Args:
        k_bf16: (1, S_kv, H_kv, D) bf16 K (full accumulated prefill K,
            from Phase 5A's `cache.k_fp16[:, :S_curr]` slice).
        group_size: along-seq quant group size. v1 locked to 32.
        protect_fraction: fraction of channels per (h) to keep at full
            BF16. v1 default 0.04 per Phase 6.4 GREEN. Use 0.08 for the
            safe-mode config.

    Returns dict with keys:
        k_int4         : (1, S, H, D//2) uint8           — packed nibbles
        k_scale        : (1, S//G, H, D) bf16            — per-group scale
        k_xmin         : (1, S//G, H, D) bf16            — per-group x_min
        k_protect_bf16 : (1, S, H, n_protect) bf16       — protected channels at full precision
        protect_slot   : (H, D) int8                     — protected->slot map (-1 if not)
        n_protect      : int                              — = round(D * protect_fraction)
        group_size     : int                              — = group_size

    Notes:
        - S MUST be divisible by group_size. Caller pads to a multiple
          of group_size BEFORE calling (Phase 2.4.2 will preallocate the
          sidecar to a multiple-of-G max_seqlen).
        - Scale + x_min are computed for ALL channels (including
          protected). The kernel ignores them for protected channels.
          Computing them anyway keeps the code branch-free.
    """
    if k_bf16.ndim != 4 or k_bf16.shape[0] != 1:
        raise ValueError(
            f"pack_k expects (1, S, H, D); got {tuple(k_bf16.shape)}"
        )
    _, S, H, D = k_bf16.shape
    if S % group_size != 0:
        raise ValueError(
            f"S={S} must be divisible by group_size={group_size}; "
            "pad caller-side before pack"
        )
    if D % 2 != 0:
        raise ValueError(f"D={D} must be even for nibble packing")

    device = k_bf16.device
    n_groups = S // group_size

    # ---- Protect mask + slot ----
    protect_mask = _select_protect_mask(k_bf16, protect_fraction)  # (H, D)
    protect_slot = _build_protect_slot(protect_mask)
    n_protect = max(1, int(round(D * protect_fraction)))

    # ---- Compact protect tensor ----
    # k_protect_bf16[token, h, slot] = k_bf16[0, token, h, d] where
    # slot = protect_slot[h, d] (>= 0)
    k_protect_bf16 = torch.zeros(
        (1, S, H, n_protect), dtype=k_bf16.dtype, device=device,
    )
    for h in range(H):
        protected_d = torch.nonzero(protect_mask[h], as_tuple=True)[0]  # (n_protect,)
        # protected_d is sorted ascending, matching slot 0..n_protect-1.
        k_protect_bf16[0, :, h, :len(protected_d)] = k_bf16[0, :, h, protected_d]

    # ---- Per-group scale + x_min on full K ----
    # Reshape (1, S, H, D) -> (1, n_groups, G, H, D), reduce along G.
    k_grouped = k_bf16.float().view(1, n_groups, group_size, H, D)
    x_max = k_grouped.amax(dim=2)  # (1, n_groups, H, D)
    x_min = k_grouped.amin(dim=2)
    scale = ((x_max - x_min) / _ASYM_DIV).clamp(min=_SCALE_CLAMP)
    k_scale = scale.to(k_bf16.dtype)
    k_xmin  = x_min.to(k_bf16.dtype)

    # ---- Quantize per-group ----
    # Broadcast scale/x_min back to (1, n_groups, G, H, D).
    q_unsigned = ((k_grouped - x_min.unsqueeze(2)) / scale.unsqueeze(2)) \
                 .round().clamp(_QMIN_UNSIGNED, _QMAX_UNSIGNED).to(torch.uint8)
    q_unsigned = q_unsigned.view(1, S, H, D)  # back to per-token layout

    # ---- Pack nibbles ----
    k_int4 = _pack_nibbles(q_unsigned)  # (1, S, H, D//2) uint8

    return {
        "k_int4":         k_int4,
        "k_scale":        k_scale,
        "k_xmin":         k_xmin,
        "k_protect_bf16": k_protect_bf16,
        "protect_slot":   protect_slot,
        "n_protect":      n_protect,
        "group_size":     group_size,
    }


def unpack_k_from_phase2_4(packed: Dict[str, Any]) -> "torch.Tensor":
    """Inverse of pack_k_for_phase2_4.

    Round-trips the packed format back to BF16 K. For each (s, h, d):
      - If protect_slot[h, d] >= 0: use k_protect_bf16[0, s, h, slot].
      - Else: dequant via q * scale + x_min.

    Used for testing only; the real consumer is the Phase 2.4.1 CUDA
    kernel which does the same arithmetic in-register.
    """
    k_int4         = packed["k_int4"]
    k_scale        = packed["k_scale"].float()
    k_xmin         = packed["k_xmin"].float()
    k_protect_bf16 = packed["k_protect_bf16"]
    protect_slot   = packed["protect_slot"]
    group_size     = packed["group_size"]

    _, S, H, D_half = k_int4.shape
    D = D_half * 2
    n_groups = k_scale.shape[1]
    assert n_groups * group_size == S, f"n_groups*G {n_groups*group_size} != S {S}"

    # Unpack nibbles -> uint8 in [0, 15].
    q_unsigned = _unpack_nibbles(k_int4, target_d=D).float()  # (1, S, H, D)

    # Dequant per group. Broadcast scale/x_min from (1, n_groups, H, D)
    # to (1, S, H, D).
    q_grouped = q_unsigned.view(1, n_groups, group_size, H, D)
    x_hat_grouped = q_grouped * k_scale.unsqueeze(2) + k_xmin.unsqueeze(2)
    x_hat = x_hat_grouped.view(1, S, H, D).to(k_protect_bf16.dtype)

    # Blend protect: where protect_slot[h, d] >= 0, use k_protect_bf16.
    # Build a (1, S, H, D) tensor of protected values where applicable.
    device = x_hat.device
    out = x_hat.clone()
    for h in range(H):
        slots_for_h = protect_slot[h]                            # (D,) int8
        protected_d = torch.nonzero(slots_for_h >= 0, as_tuple=True)[0]
        if len(protected_d) == 0:
            continue
        # k_protect_bf16[0, :, h, :len(protected_d)] -> overwrite at those d.
        out[0, :, h, protected_d] = k_protect_bf16[0, :, h, :len(protected_d)]

    return out


def round_trip_max_error(
    k_bf16: "torch.Tensor",
    *,
    group_size: int = 32,
    protect_fraction: float = 0.04,
) -> Dict[str, float]:
    """Pack k -> unpack -> compare. Returns per-element error stats.

    The unpack output is NOT bit-equal to input — INT4 quantization
    is lossy. But:
      - Protected channels SHOULD be bit-equal (they bypass quant).
      - Unprotected channels should have per-element error bounded by
        ~scale (per-group LSB).
      - Aggregate stats: max-abs, mean-abs, mean-rel-error.

    Pass criterion (the test below):
      - On protected channels: max-abs error == 0 (bit-equal).
      - On unprotected channels: per-element error <= ~max(scale).
    """
    packed = pack_k_for_phase2_4(
        k_bf16, group_size=group_size, protect_fraction=protect_fraction,
    )
    k_rt = unpack_k_from_phase2_4(packed)

    diff = (k_bf16.float() - k_rt.float()).abs()
    protect_mask_h_d = (packed["protect_slot"] >= 0)             # (H, D) bool
    # Broadcast to (1, S, H, D).
    protect_broadcast = protect_mask_h_d.unsqueeze(0).unsqueeze(0).expand_as(diff)

    diff_protected   = diff[protect_broadcast]
    diff_unprotected = diff[~protect_broadcast]
    return {
        "n_protected":             int(protect_mask_h_d.sum().item()),
        "n_total_channels":        int(protect_mask_h_d.numel()),
        "protected_max_abs":       float(diff_protected.max().item())
                                   if diff_protected.numel() > 0 else 0.0,
        "unprotected_max_abs":     float(diff_unprotected.max().item())
                                   if diff_unprotected.numel() > 0 else 0.0,
        "unprotected_mean_abs":    float(diff_unprotected.mean().item())
                                   if diff_unprotected.numel() > 0 else 0.0,
        "all_max_abs":             float(diff.max().item()),
        "all_mean_abs":            float(diff.mean().item()),
    }


def sidecar_byte_size(
    S: int, H: int, D: int,
    *,
    group_size: int = 32,
    protect_fraction: float = 0.04,
    dtype_bytes: int = 2,  # bf16 == 2 bytes
) -> Dict[str, int]:
    """Sidecar memory accounting per layer at sequence length S.

    Returns dict of per-tensor bytes + total. Used to validate the
    Phase 2.4 design doc's memory math.
    """
    n_groups = (S + group_size - 1) // group_size
    n_protect = max(1, int(round(D * protect_fraction)))
    bytes_k_int4         = S * H * (D // 2)                    # uint8
    bytes_k_scale        = n_groups * H * D * dtype_bytes      # bf16
    bytes_k_xmin         = n_groups * H * D * dtype_bytes      # bf16
    bytes_k_protect_bf16 = S * H * n_protect * dtype_bytes     # bf16
    bytes_protect_slot   = H * D                                # int8
    total = (bytes_k_int4 + bytes_k_scale + bytes_k_xmin
             + bytes_k_protect_bf16 + bytes_protect_slot)
    return {
        "k_int4":         bytes_k_int4,
        "k_scale":        bytes_k_scale,
        "k_xmin":         bytes_k_xmin,
        "k_protect_bf16": bytes_k_protect_bf16,
        "protect_slot":   bytes_protect_slot,
        "total":          total,
        "fp16_baseline":  S * H * D * dtype_bytes,
        "compression":    (S * H * D * dtype_bytes) / total,
        "n_protect":      n_protect,
        "n_groups":       n_groups,
    }
