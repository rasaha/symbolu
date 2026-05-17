"""INT4 per-channel K + per-token V KV-cache quantization (KIVI-style).

After PolarQuant's two-track failure on Qwen2.5-7B (3-bit + QJL: 3052×
perplexity blow-up; 4-bit + QJL: 301×; per-channel scale rescue: made
things worse, see PHASE4_GPU_FINDINGS.md §17), this module implements
the *literature-validated* alternative: INT4 quantization with per-
channel scales for K and per-token scales for V.

This is the asymmetric scheme published in:
  Liu et al., "KIVI: A Tuning-Free Asymmetric 2bit Quantization for KV
  Cache" (ICML 2024). The asymmetry matters:

  * K is read by ``softmax(Q · K^T)`` — outlier *channels* in K (after
    RoPE, certain head_dim indices carry disproportionate L2 mass)
    dominate the dot product. Per-channel quantization gives each
    channel its own scale, so outliers are resolved at their true
    magnitude while small channels keep their relative precision.

  * V is read by ``attention_weights · V`` — outlier *tokens* in V
    (the high-mass positions) dominate. Per-token quantization gives
    each (token, head) pair its own scale.

Crucially, **no rotation step**. Each channel (or token) keeps its
identity through the quantization, so the rescue trick (per-channel
scaling) is intrinsic to the algorithm rather than bolted on top.
This is what makes KIVI-style approaches preserve quality where
PolarQuant fails.

Compression math (Qwen2.5-7B GQA-4 KV layout, block_size=16):
  K per-channel scale:  16 bits per (H=4, D=128) location, shared over
                         S=16 tokens → 16/16 = 1.0 bit/element overhead
                         on top of 4 bits/element quantized value.
                         Total: 5.0 bits/elem → 3.2× vs FP16.
  V per-token scale:    16 bits per (S=16, H=4) location, shared over
                         D=128 → 16/128 = 0.125 bits/elem overhead.
                         Total: 4.125 bits/elem → 3.88× vs FP16.

For longer blocks (prefill of 64-256 tokens, as Track E uses):
  K scale overhead: 16/64 = 0.25 bit/elem → total 4.25 bits → 3.76× vs FP16
  K scale overhead: 16/256 = 0.0625 bit/elem → total ~4.0625 bits → ~3.94× vs FP16

Asymptotic per-element compression: 4× vs FP16, 8× vs FP32.

The actual stored bytes use uint8 (8 bits/elem) for the quantized
indices — we don't bit-pack to 4 bits in this CPU-correct
implementation. ``theoretical_packed_bytes`` reports the bit-packed
number for fair comparison to PolarQuant's §14.2 number.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

try:
    import torch  # type: ignore
except ImportError:  # pragma: no cover - guarded at the caller
    torch = None  # type: ignore


# --------------------------------------------------------------------------- #
# Bit packing / unpacking — pack two INT4 values per byte                     #
# --------------------------------------------------------------------------- #


def pack_int4(t_int8: "torch.Tensor") -> "torch.Tensor":
    """Pack a signed-INT4 tensor (stored as int8 with values in [−8, +7])
    into half as many uint8 bytes.

    Packs along the *last* dimension. Two consecutive INT4 values share
    one byte: lower nibble = first, upper nibble = second. Internal
    representation shifts the signed range [−8, +7] to unsigned [0, 15]
    so a byte simply holds two 4-bit unsigned ints.

    If the last dimension is odd, the input is zero-padded by one
    element before packing. ``unpack_int4`` requires knowing the
    original last-dim size to trim that padding back.

    Args:
        t_int8: ``(..., N) int8`` tensor with all values in [−8, +7].

    Returns:
        ``(..., ceil(N / 2)) uint8`` tensor.
    """
    if t_int8.dtype != torch.int8:
        raise TypeError(
            f"pack_int4 expects int8 input; got dtype {t_int8.dtype}"
        )
    n = t_int8.shape[-1]
    # Pad to even length on the last dim.
    if n % 2 == 1:
        pad_shape = t_int8.shape[:-1] + (1,)
        zeros = torch.zeros(pad_shape, dtype=torch.int8, device=t_int8.device)
        t_int8 = torch.cat([t_int8, zeros], dim=-1)
    # Reshape to (..., n_pairs, 2)
    n_pairs = t_int8.shape[-1] // 2
    prefix_shape = t_int8.shape[:-1]
    pairs = t_int8.view(*prefix_shape, n_pairs, 2)
    # Shift signed [−8, +7] → unsigned [0, 15], pack two per byte.
    pairs_unsigned = (pairs + 8).to(torch.uint8)
    packed = pairs_unsigned[..., 0] | (pairs_unsigned[..., 1] << 4)
    return packed  # (..., n_pairs) uint8


def unpack_int4(packed: "torch.Tensor", target_n: int) -> "torch.Tensor":
    """Inverse of ``pack_int4``.

    Args:
        packed: ``(..., m) uint8`` where m == ceil(target_n / 2).
        target_n: original last-dim size before packing. Used to trim
            the padding byte if the original was odd-length.

    Returns:
        ``(..., target_n) int8`` with values restored to [−8, +7].
    """
    if packed.dtype != torch.uint8:
        raise TypeError(f"unpack_int4 expects uint8 input; got dtype {packed.dtype}")
    low = (packed & 0x0F).to(torch.int8) - 8
    high = ((packed >> 4) & 0x0F).to(torch.int8) - 8
    # Interleave low/high pairs: out[2i] = low[i], out[2i+1] = high[i].
    stacked = torch.stack([low, high], dim=-1)
    prefix_shape = packed.shape[:-1]
    m = packed.shape[-1]
    flat = stacked.view(*prefix_shape, m * 2)
    return flat[..., :target_n].contiguous()


# --------------------------------------------------------------------------- #
# Quantization primitives                                                     #
# --------------------------------------------------------------------------- #


def quantize_per_channel_int4(
    tensor: "torch.Tensor",
    *,
    group_size: int = 0,
    asymmetric: bool = False,
    bits: int = 4,
    static_scale: Optional["torch.Tensor"] = None,
    static_offset: Optional["torch.Tensor"] = None,
) -> "Tuple[torch.Tensor, torch.Tensor, Optional[torch.Tensor]]":
    """Per-channel signed-INTb quantization along the seq axis.

    Despite the historical "int4" in the function name, ``bits`` is
    parametric. INT3 values still fit in the INT4 storage slot (range
    ⊂ [−8, +7]) so the bit-packing layer doesn't change — only the
    quantization math and the theoretical bit-rate change.

    Args:
        tensor: ``(S, H, D)``.
        group_size: 0 = plain per-channel (one scale per (h, d) covering
            all S positions). > 0 = split seq axis into groups.
        asymmetric: if True, use affine quantization (scale + offset
            mapping [x_min, x_max] → signed range).
        bits: bit width per value. Must be 2..8. ``4`` (the default)
            is the validated KIVI config. ``3`` is experimental.
        static_scale: optional pre-computed scale tensor of shape
            ``(1, H, D)``. When provided, the dynamic max-based scale
            computation is SKIPPED and this scale is used directly.
            Use for GPTQ/AWQ-style static calibration where scales
            are pre-optimized offline on a calibration set. Currently
            only supported with ``group_size == 0`` (no group quant).
        static_offset: optional pre-computed offset tensor, same shape
            as ``static_scale``. Required for asymmetric mode when
            ``static_scale`` is provided. Ignored in symmetric mode.

    Returns ``(quantized, scale, offset)`` where ``quantized`` is in
    the symmetric signed range ``[-(2**(bits-1)), +(2**(bits-1)-1)]``.
    """
    if tensor.ndim != 3:
        raise ValueError(
            f"quantize_per_channel_int4 expected 3-D (S, H, D) tensor; "
            f"got shape {tuple(tensor.shape)}"
        )
    if not (2 <= bits <= 8):
        raise ValueError(f"bits must be in [2, 8]; got {bits}")
    if static_scale is not None and (group_size > 0 and group_size < tensor.shape[0]):
        raise ValueError(
            f"static_scale only supported with group_size <= 0 (no group "
            f"quantisation); got group_size={group_size}"
        )
    if asymmetric and static_scale is not None and static_offset is None:
        raise ValueError(
            "static_scale provided in asymmetric mode requires static_offset"
        )
    qmin = -(1 << (bits - 1))         # e.g., -8 for INT4, -4 for INT3
    qmax = (1 << (bits - 1)) - 1      # e.g., +7 for INT4, +3 for INT3
    sym_div = float(qmax)             # 7 for INT4, 3 for INT3
    asym_div = float((1 << bits) - 1)  # 15 for INT4, 7 for INT3
    sym_zero_shift = -qmin            # 8 for INT4, 4 for INT3

    s, h, d = tensor.shape
    t_f32 = tensor.to(torch.float32)

    if group_size <= 0 or group_size >= s:
        # Plain per-channel.
        if asymmetric:
            if static_scale is not None:
                # GPTQ/AWQ-style static calibration: scales were
                # pre-computed on a calibration set offline. Just
                # quantize against them.
                scale = static_scale.to(t_f32.device)
                offset = static_offset.to(t_f32.device)
                # Reverse-engineer x_min from the (scale, offset)
                # calibration so we can apply the same affine map:
                # offset = x_min + sym_zero_shift * scale → x_min = offset - sym_zero_shift*scale
                x_min = offset - sym_zero_shift * scale
                q_unsigned = ((t_f32 - x_min) / scale).round().clamp(min=0, max=int(asym_div))
                quantized = (q_unsigned - sym_zero_shift).to(torch.int8)
                return quantized, scale, offset
            x_max = t_f32.amax(dim=0, keepdim=True)  # (1, H, D)
            x_min = t_f32.amin(dim=0, keepdim=True)
            scale = ((x_max - x_min) / asym_div).clamp(min=1e-8)
            q_unsigned = ((t_f32 - x_min) / scale).round().clamp(min=0, max=int(asym_div))
            quantized = (q_unsigned - sym_zero_shift).to(torch.int8)
            offset = x_min + sym_zero_shift * scale
            return quantized, scale, offset
        else:
            if static_scale is not None:
                scale = static_scale.to(t_f32.device)
                quantized = (t_f32 / scale).round().clamp(min=qmin, max=qmax).to(torch.int8)
                return quantized, scale, None
            max_abs = t_f32.abs().amax(dim=0, keepdim=True)
            scale = (max_abs / sym_div).clamp(min=1e-8)
            quantized = (t_f32 / scale).round().clamp(min=qmin, max=qmax).to(torch.int8)
            return quantized, scale, None

    # Group-wise.
    pad = (-s) % group_size
    if pad:
        zeros = torch.zeros(pad, h, d, dtype=tensor.dtype, device=tensor.device)
        tensor_padded = torch.cat([tensor, zeros], dim=0)
        t_f32_padded = tensor_padded.to(torch.float32)
    else:
        t_f32_padded = t_f32
    s_padded = t_f32_padded.shape[0]
    n_groups = s_padded // group_size

    t_grouped = t_f32_padded.view(n_groups, group_size, h, d)
    if asymmetric:
        x_max = t_grouped.amax(dim=1, keepdim=True)  # (n_groups, 1, H, D)
        x_min = t_grouped.amin(dim=1, keepdim=True)
        scale = ((x_max - x_min) / asym_div).clamp(min=1e-8)
        q_unsigned = ((t_grouped - x_min) / scale).round().clamp(min=0, max=int(asym_div))
        quantized_grouped = (q_unsigned - sym_zero_shift).to(torch.int8)
        offset = x_min + sym_zero_shift * scale
        offset_out = offset.squeeze(1)
    else:
        max_abs = t_grouped.abs().amax(dim=1, keepdim=True)
        scale = (max_abs / sym_div).clamp(min=1e-8)
        quantized_grouped = (t_grouped / scale).round().clamp(min=qmin, max=qmax).to(torch.int8)
        offset_out = None

    quantized_flat = quantized_grouped.view(s_padded, h, d)[:s].contiguous()
    return quantized_flat, scale.squeeze(1), offset_out


def dequantize_per_channel_int4(
    quantized: "torch.Tensor",
    scale: "torch.Tensor",
    *,
    dtype: Any,
    group_size: int = 0,
    offset: Optional["torch.Tensor"] = None,
) -> "torch.Tensor":
    """Inverse of ``quantize_per_channel_int4``.

    When ``offset`` is provided (asymmetric mode), reconstruction is
    ``q * scale + offset``. When ``None`` (symmetric mode), it is
    ``q * scale``.
    """
    n_groups = scale.shape[0]
    if n_groups == 1:
        if offset is not None:
            return (quantized.to(scale.dtype) * scale + offset).to(dtype)
        return (quantized.to(scale.dtype) * scale).to(dtype)

    if group_size <= 0:
        raise ValueError(
            "group_size must be > 0 when scale has >1 group rows "
            f"(scale.shape={tuple(scale.shape)}, group_size={group_size})"
        )

    s, h, d = quantized.shape
    pad = n_groups * group_size - s
    if pad < 0:
        raise ValueError(
            f"n_groups*group_size={n_groups * group_size} < S={s}; "
            "scale doesn't cover the full seq axis"
        )
    if pad:
        zeros = torch.zeros(pad, h, d, dtype=quantized.dtype, device=quantized.device)
        quantized_padded = torch.cat([quantized, zeros], dim=0)
    else:
        quantized_padded = quantized
    grouped = quantized_padded.view(n_groups, group_size, h, d)
    if offset is not None:
        # offset: (n_groups, H, D), unsqueeze(1) → (n_groups, 1, H, D)
        dequant_grouped = grouped.to(scale.dtype) * scale.unsqueeze(1) + offset.unsqueeze(1)
    else:
        dequant_grouped = grouped.to(scale.dtype) * scale.unsqueeze(1)
    flat = dequant_grouped.view(n_groups * group_size, h, d)[:s].contiguous()
    return flat.to(dtype)


def quantize_per_token_int4(
    tensor: "torch.Tensor",
    *,
    group_size: int = 0,
    asymmetric: bool = False,
    bits: int = 4,
    static_scale: Optional["torch.Tensor"] = None,
    static_offset: Optional["torch.Tensor"] = None,
) -> "Tuple[torch.Tensor, torch.Tensor, Optional[torch.Tensor]]":
    """Per-token signed-INTb quantization along the head_dim axis.

    Mirrors ``quantize_per_channel_int4`` parametrically including
    optional static-scale calibration support (see that function's
    docstring for semantics).

    For V the calibration shape is ``(1, H, D)`` matching the K
    convention — calibrating per-token-position would require
    knowing seq length up front, which static calibration doesn't.
    Static V calibration uses per-(head, head_dim) scales averaged
    over both the calibration tokens AND the calibration positions.
    """
    if tensor.ndim != 3:
        raise ValueError(
            f"quantize_per_token_int4 expected 3-D (S, H, D) tensor; "
            f"got shape {tuple(tensor.shape)}"
        )
    if not (2 <= bits <= 8):
        raise ValueError(f"bits must be in [2, 8]; got {bits}")
    if static_scale is not None and (group_size > 0 and group_size < tensor.shape[2]):
        raise ValueError(
            f"static_scale only supported with group_size <= 0 (no group "
            f"quantisation); got group_size={group_size}"
        )
    if asymmetric and static_scale is not None and static_offset is None:
        raise ValueError(
            "static_scale provided in asymmetric mode requires static_offset"
        )
    qmin = -(1 << (bits - 1))
    qmax = (1 << (bits - 1)) - 1
    sym_div = float(qmax)
    asym_div = float((1 << bits) - 1)
    sym_zero_shift = -qmin

    s, h, d = tensor.shape
    t_f32 = tensor.to(torch.float32)

    if group_size <= 0 or group_size >= d:
        if asymmetric:
            if static_scale is not None:
                # Static V calibration: expected shape (1, H, 1) — one
                # scale per head, applied uniformly across (S, D). This
                # is coarser than the dynamic per-token scale (which is
                # per-(S, H, 1)) but matches the storage convention
                # exactly. AWQ-KV style: calibrate K aggressively,
                # leave V at simpler per-head scaling.
                if tuple(static_scale.shape) != (1, h, 1):
                    raise ValueError(
                        f"V static_scale must have shape (1, H, 1) = (1, {h}, 1); "
                        f"got {tuple(static_scale.shape)}"
                    )
                scale = static_scale.to(t_f32.device)
                offset = static_offset.to(t_f32.device)
                x_min = offset - sym_zero_shift * scale
                q_unsigned = ((t_f32 - x_min) / scale).round().clamp(min=0, max=int(asym_div))
                quantized = (q_unsigned - sym_zero_shift).to(torch.int8)
                # Tile the (1, H, 1) scale up to (S, H, 1) for the
                # per-token storage convention.
                scale_stored = scale.expand(s, h, 1).contiguous()
                offset_stored = offset.expand(s, h, 1).contiguous()
                return quantized, scale_stored, offset_stored
            x_max = t_f32.amax(dim=2, keepdim=True)  # (S, H, 1)
            x_min = t_f32.amin(dim=2, keepdim=True)
            scale = ((x_max - x_min) / asym_div).clamp(min=1e-8)
            q_unsigned = ((t_f32 - x_min) / scale).round().clamp(min=0, max=int(asym_div))
            quantized = (q_unsigned - sym_zero_shift).to(torch.int8)
            offset = x_min + sym_zero_shift * scale
            return quantized, scale, offset
        if static_scale is not None:
            if tuple(static_scale.shape) != (1, h, 1):
                raise ValueError(
                    f"V static_scale must have shape (1, H, 1) = (1, {h}, 1); "
                    f"got {tuple(static_scale.shape)}"
                )
            scale = static_scale.to(t_f32.device)
            quantized = (t_f32 / scale).round().clamp(min=qmin, max=qmax).to(torch.int8)
            scale_stored = scale.expand(s, h, 1).contiguous()
            return quantized, scale_stored, None
        max_abs = t_f32.abs().amax(dim=2, keepdim=True)
        scale = (max_abs / sym_div).clamp(min=1e-8)
        quantized = (t_f32 / scale).round().clamp(min=qmin, max=qmax).to(torch.int8)
        return quantized, scale, None

    pad = (-d) % group_size
    if pad:
        zeros = torch.zeros(s, h, pad, dtype=tensor.dtype, device=tensor.device)
        tensor_padded = torch.cat([tensor, zeros], dim=2)
        t_f32_padded = tensor_padded.to(torch.float32)
    else:
        t_f32_padded = t_f32
    d_padded = t_f32_padded.shape[2]
    n_groups = d_padded // group_size

    t_grouped = t_f32_padded.view(s, h, n_groups, group_size)
    if asymmetric:
        x_max = t_grouped.amax(dim=3, keepdim=True)  # (S, H, n_groups, 1)
        x_min = t_grouped.amin(dim=3, keepdim=True)
        scale = ((x_max - x_min) / asym_div).clamp(min=1e-8)
        q_unsigned = ((t_grouped - x_min) / scale).round().clamp(min=0, max=int(asym_div))
        quantized_grouped = (q_unsigned - sym_zero_shift).to(torch.int8)
        offset = x_min + sym_zero_shift * scale
        offset_out = offset.squeeze(3)
    else:
        max_abs = t_grouped.abs().amax(dim=3, keepdim=True)
        scale = (max_abs / sym_div).clamp(min=1e-8)
        quantized_grouped = (t_grouped / scale).round().clamp(min=qmin, max=qmax).to(torch.int8)
        offset_out = None

    quantized_flat = quantized_grouped.view(s, h, d_padded)[:, :, :d].contiguous()
    return quantized_flat, scale.squeeze(3), offset_out


def dequantize_per_token_int4(
    quantized: "torch.Tensor",
    scale: "torch.Tensor",
    *,
    dtype: Any,
    group_size: int = 0,
    offset: Optional["torch.Tensor"] = None,
) -> "torch.Tensor":
    n_groups = scale.shape[2]
    if n_groups == 1:
        if offset is not None:
            return (quantized.to(scale.dtype) * scale + offset).to(dtype)
        return (quantized.to(scale.dtype) * scale).to(dtype)

    if group_size <= 0:
        raise ValueError(
            "group_size must be > 0 when scale has >1 group columns "
            f"(scale.shape={tuple(scale.shape)}, group_size={group_size})"
        )

    s, h, d = quantized.shape
    pad = n_groups * group_size - d
    if pad < 0:
        raise ValueError(
            f"n_groups*group_size={n_groups * group_size} < D={d}; "
            "scale doesn't cover the full head_dim axis"
        )
    if pad:
        zeros = torch.zeros(s, h, pad, dtype=quantized.dtype, device=quantized.device)
        quantized_padded = torch.cat([quantized, zeros], dim=2)
    else:
        quantized_padded = quantized
    grouped = quantized_padded.view(s, h, n_groups, group_size)
    if offset is not None:
        dequant_grouped = grouped.to(scale.dtype) * scale.unsqueeze(3) + offset.unsqueeze(3)
    else:
        dequant_grouped = grouped.to(scale.dtype) * scale.unsqueeze(3)
    flat = dequant_grouped.view(s, h, n_groups * group_size)[:, :, :d].contiguous()
    return flat.to(dtype)


# --------------------------------------------------------------------------- #
# Compressed buffer + store                                                   #
# --------------------------------------------------------------------------- #


@dataclass
class INT4Block:
    """Per-block compressed state.

    Storage layout (bit-packed):
      * K quantized values: ``k_packed`` uint8, two 4-bit values per
        byte along the head_dim axis. Shape ``(S, H, ceil(D/2)) uint8``
        when the head_dim is the packing axis (the default).
      * V quantized values: ``v_packed`` uint8, same packing along
        head_dim.
      * Scales / offsets stored as float16 (16 bits each) rather than
        float32, so the partner-shareable ``compression_ratio`` =
        ``original_bytes / actual_stored_bytes`` matches the
        bit-packed theoretical number rather than being 2× off due to
        int8 + fp32 working storage.

    The ``original_d`` field carries the unpadded head_dim so
    ``unpack_int4`` can trim the pad byte (if D is odd).
    """

    k_packed: "torch.Tensor"       # (S, H, ceil(D/2)) uint8 — packed K
    k_scale: "torch.Tensor"        # (n_groups_s, H, D) float16
    v_packed: "torch.Tensor"       # (S, H, ceil(D/2)) uint8 — packed V
    v_scale: "torch.Tensor"        # (S, H, n_groups_d) float16
    original_shape: Tuple[int, ...]
    original_dtype: Any
    k_group_size: int = 0          # 0 means plain per-channel
    v_group_size: int = 0          # 0 means plain per-token
    # Asymmetric quantization offsets (None for symmetric mode).
    # Same shapes as k_scale / v_scale respectively, float16.
    k_offset: Optional["torch.Tensor"] = None
    v_offset: Optional["torch.Tensor"] = None
    # Per-channel effective bit widths. K and V quantize independently so
    # an adaptive-precision config (e.g. K at INT8, V at INT4 — the
    # §20.4.1 long-context recommendation) is representable.
    k_bits: int = 4
    v_bits: int = 4
    # Whether each channel's quantized tensor is nibble-packed. pack_int4
    # only represents 4-bit values ([-8, +7]); at > 4 bits the channel is
    # stored as a raw int8 tensor (8 bits/elem heap) and k/v_bit_packed
    # records which path was taken so read_block can invert correctly.
    k_bit_packed: bool = True
    v_bit_packed: bool = True

    @property
    def theoretical_packed_bytes(self) -> int:
        """Theoretical bit-packed storage (independent of actual heap):
          * K: ``bits`` * S*H*D + 16 * n_groups_s * H*D × (2 if asymmetric else 1)
          * V: ``bits`` * S*H*D + 16 * S*H * n_groups_d × (2 if asymmetric else 1)

        At bits=4 (default KIVI), this is ≈ ``actual_stored_bytes``.
        At bits=3 (experimental), the theoretical bit-rate is lower
        but actual heap stays at 4-bit packing until proper INT3
        packing is implemented.
        """
        s, h, d = self.original_shape
        n_groups_s = int(self.k_scale.shape[0])
        n_groups_d = int(self.v_scale.shape[2])
        k_scale_factor = 2 if self.k_offset is not None else 1
        v_scale_factor = 2 if self.v_offset is not None else 1
        k_total = self.k_bits * s * h * d + 16 * n_groups_s * h * d * k_scale_factor
        v_total = self.v_bits * s * h * d + 16 * s * h * n_groups_d * v_scale_factor
        return max(1, (k_total + v_total + 7) // 8)

    @property
    def actual_stored_bytes(self) -> int:
        """Real heap bytes consumed by this block's tensors.

        After bit-packing landed:
          * ``k_packed`` / ``v_packed`` are uint8 (1 byte per packed pair).
          * Scales / offsets are float16 (2 bytes each).

        Should match ``theoretical_packed_bytes`` within a small
        constant (any pad byte from odd D); partner-shareable
        compression-ratio claims can use either number now.
        """
        b = (
            int(self.k_packed.element_size() * self.k_packed.numel())
            + int(self.k_scale.element_size() * self.k_scale.numel())
            + int(self.v_packed.element_size() * self.v_packed.numel())
            + int(self.v_scale.element_size() * self.v_scale.numel())
        )
        if self.k_offset is not None:
            b += int(self.k_offset.element_size() * self.k_offset.numel())
        if self.v_offset is not None:
            b += int(self.v_offset.element_size() * self.v_offset.numel())
        return b


def _is_torch_tensor(obj: Any) -> bool:
    cls = type(obj)
    return cls.__module__.startswith("torch") and cls.__name__ == "Tensor"


class INT4PerChannelKVStore:
    """KIVI-style INT4 KV cache side-store: K per-channel, V per-token.

    Public surface mirrors ``TurboQuantKVStore`` so the route-B HF cache
    wrapper can swap one for the other:

    * ``write_block(block_id, k, v)``
    * ``read_block(block_id) -> (k, v)``
    * ``remove_block(block_id)``
    * ``compression_ratio`` property
    * ``get_stats()``

    Torch-only (the math is implemented in torch ops; on GPU the
    quantization runs on the input tensor's device).
    """

    def __init__(
        self,
        *,
        torch_device: Optional[Any] = None,
        k_group_size: int = 0,
        v_group_size: int = 0,
        asymmetric: bool = False,
        bits: int = 4,
        k_bits: Optional[int] = None,
        v_bits: Optional[int] = None,
    ) -> None:
        if torch is None:
            raise ImportError("INT4PerChannelKVStore requires PyTorch.")
        if k_group_size < 0 or v_group_size < 0:
            raise ValueError(
                f"group sizes must be >= 0; got k={k_group_size}, v={v_group_size}"
            )
        # ``bits`` sets both channels; ``k_bits`` / ``v_bits`` override it
        # per channel for adaptive precision (e.g. K=8, V=4 — §20.4.1).
        self._k_bits = int(k_bits if k_bits is not None else bits)
        self._v_bits = int(v_bits if v_bits is not None else bits)
        for _label, _b in (("k_bits", self._k_bits), ("v_bits", self._v_bits)):
            if not (2 <= _b <= 8):
                raise ValueError(f"{_label} must be in [2, 8]; got {_b}")
        self._torch_device = torch_device
        self._k_group_size = int(k_group_size)
        self._v_group_size = int(v_group_size)
        self._asymmetric = bool(asymmetric)
        self._blocks: Dict[int, INT4Block] = {}
        self._stats: Dict[str, Any] = {
            "writes": 0,
            "reads": 0,
            "removes": 0,
            "bytes_in": 0,
            "bytes_out_theoretical": 0,
            # bytes_out_actual was added with bit-packing. After
            # packing, theoretical and actual converge — the partner-
            # shareable compression ratio is real.
            "bytes_out_actual": 0,
            "write_us_sum": 0.0,
            "read_us_sum": 0.0,
        }

    def write_block(
        self, block_id: int, k_array, v_array,
        *,
        static_k_scale: "Optional[torch.Tensor]" = None,
        static_k_offset: "Optional[torch.Tensor]" = None,
        static_v_scale: "Optional[torch.Tensor]" = None,
        static_v_offset: "Optional[torch.Tensor]" = None,
    ) -> None:
        if not _is_torch_tensor(k_array) or not _is_torch_tensor(v_array):
            raise TypeError(
                "INT4PerChannelKVStore.write_block requires torch.Tensor "
                "inputs (no numpy backend in this implementation)."
            )
        if k_array.ndim != 3 or v_array.ndim != 3:
            raise ValueError(
                f"INT4PerChannelKVStore.write_block expects (S, H, D) "
                f"tensors; got K {tuple(k_array.shape)}, V "
                f"{tuple(v_array.shape)}"
            )
        t0 = time.perf_counter()
        original_dtype = k_array.dtype
        bytes_in = int(
            k_array.element_size() * k_array.numel()
            + v_array.element_size() * v_array.numel()
        )

        k_in = k_array if self._torch_device is None else k_array.to(self._torch_device)
        v_in = v_array if self._torch_device is None else v_array.to(self._torch_device)

        k_q, k_scale, k_offset = quantize_per_channel_int4(
            k_in, group_size=self._k_group_size, asymmetric=self._asymmetric,
            bits=self._k_bits,
            static_scale=static_k_scale, static_offset=static_k_offset,
        )
        v_q, v_scale, v_offset = quantize_per_token_int4(
            v_in, group_size=self._v_group_size, asymmetric=self._asymmetric,
            bits=self._v_bits,
            static_scale=static_v_scale, static_offset=static_v_offset,
        )

        # Bit-pack the int8 quantized tensors (two 4-bit values per byte)
        # and downcast scales/offsets to float16 for storage. This is what
        # turns the *theoretical* compression ratio into *actual* heap
        # savings — without packing, int8 storage uses 8 bits/element
        # while the algorithm only carries 4 bits of information.
        #
        # pack_int4 only represents 4-bit values ([-8, +7]). At > 4 bits
        # the quantized range overflows the nibble, so that channel is
        # stored as a raw int8 tensor (8 bits/elem heap) until a wider
        # sub-byte packer lands. This is what makes INT5+ and adaptive
        # K=8/V=4 configs correct rather than corrupt.
        if self._k_bits <= 4:
            k_packed, k_bit_packed = pack_int4(k_q), True
        else:
            k_packed, k_bit_packed = k_q.contiguous(), False
        if self._v_bits <= 4:
            v_packed, v_bit_packed = pack_int4(v_q), True
        else:
            v_packed, v_bit_packed = v_q.contiguous(), False
        k_scale_fp16 = k_scale.to(torch.float16)
        v_scale_fp16 = v_scale.to(torch.float16)
        k_offset_fp16 = k_offset.to(torch.float16) if k_offset is not None else None
        v_offset_fp16 = v_offset.to(torch.float16) if v_offset is not None else None

        block = INT4Block(
            k_packed=k_packed,
            k_scale=k_scale_fp16,
            v_packed=v_packed,
            v_scale=v_scale_fp16,
            original_shape=tuple(int(s) for s in k_array.shape),
            original_dtype=original_dtype,
            k_group_size=self._k_group_size,
            v_group_size=self._v_group_size,
            k_offset=k_offset_fp16,
            v_offset=v_offset_fp16,
            k_bits=self._k_bits,
            v_bits=self._v_bits,
            k_bit_packed=k_bit_packed,
            v_bit_packed=v_bit_packed,
        )
        self._blocks[block_id] = block
        self._stats["writes"] += 1
        self._stats["bytes_in"] += bytes_in
        self._stats["bytes_out_theoretical"] += int(block.theoretical_packed_bytes)
        self._stats["bytes_out_actual"] += int(block.actual_stored_bytes)
        self._stats["write_us_sum"] += (time.perf_counter() - t0) * 1e6

    def read_block(self, block_id: int) -> "Tuple[torch.Tensor, torch.Tensor]":
        if block_id not in self._blocks:
            raise KeyError(f"INT4PerChannelKVStore: block {block_id} not held")
        t0 = time.perf_counter()
        b = self._blocks[block_id]
        # Unpack the int4 storage back to int8 for dequantize. The
        # scales/offsets are fp16 on disk; the dequantize math runs in
        # fp32 internally (cast happens inside dequantize) and casts
        # back to original_dtype at the end.
        s, h, d = b.original_shape
        # Invert the per-channel storage path: nibble-unpack 4-bit
        # channels, take the raw int8 tensor for > 4-bit channels.
        k_int8 = unpack_int4(b.k_packed, target_n=d) if b.k_bit_packed else b.k_packed
        v_int8 = unpack_int4(b.v_packed, target_n=d) if b.v_bit_packed else b.v_packed
        k_scale_fp32 = b.k_scale.to(torch.float32)
        v_scale_fp32 = b.v_scale.to(torch.float32)
        k_offset_fp32 = b.k_offset.to(torch.float32) if b.k_offset is not None else None
        v_offset_fp32 = b.v_offset.to(torch.float32) if b.v_offset is not None else None
        k = dequantize_per_channel_int4(
            k_int8, k_scale_fp32, dtype=b.original_dtype,
            group_size=b.k_group_size, offset=k_offset_fp32,
        )
        v = dequantize_per_token_int4(
            v_int8, v_scale_fp32, dtype=b.original_dtype,
            group_size=b.v_group_size, offset=v_offset_fp32,
        )
        self._stats["reads"] += 1
        self._stats["read_us_sum"] += (time.perf_counter() - t0) * 1e6
        return k, v

    def remove_block(self, block_id: int) -> None:
        if self._blocks.pop(block_id, None) is not None:
            self._stats["removes"] += 1

    def __contains__(self, block_id: int) -> bool:
        return block_id in self._blocks

    def __len__(self) -> int:
        return len(self._blocks)

    @property
    def compression_ratio(self) -> float:
        """Theoretical bit-packed compression ratio (source / bit-packed).
        With actual bit-packing landed, this matches ``actual_compression_ratio``
        within rounding."""
        out = self._stats["bytes_out_theoretical"]
        if out == 0:
            return 0.0
        return float(self._stats["bytes_in"]) / float(out)

    @property
    def actual_compression_ratio(self) -> float:
        """Actual heap-storage compression ratio (source / real bytes used).
        Reports the true memory savings after pack_int4 / fp16 scales.
        Should match ``compression_ratio`` within a tiny constant from
        any odd-D padding byte."""
        out = self._stats["bytes_out_actual"]
        if out == 0:
            return 0.0
        return float(self._stats["bytes_in"]) / float(out)

    @property
    def avg_write_us(self) -> float:
        w = self._stats["writes"]
        return 0.0 if w == 0 else self._stats["write_us_sum"] / w

    @property
    def avg_read_us(self) -> float:
        r = self._stats["reads"]
        return 0.0 if r == 0 else self._stats["read_us_sum"] / r

    @property
    def backend(self) -> str:
        return "int4_per_channel"

    def get_stats(self) -> Dict[str, Any]:
        s = dict(self._stats)
        s["compression_ratio"] = self.compression_ratio
        s["actual_compression_ratio"] = self.actual_compression_ratio
        s["blocks_held"] = len(self._blocks)
        s["avg_write_us"] = self.avg_write_us
        s["avg_read_us"] = self.avg_read_us
        s["backend"] = self.backend
        s["k_quantization"] = "per_channel"
        s["v_quantization"] = "per_token"
        s["k_group_size"] = self._k_group_size
        s["v_group_size"] = self._v_group_size
        s["asymmetric"] = self._asymmetric
        s["k_bits"] = self._k_bits
        s["v_bits"] = self._v_bits
        # bits_per_element is the single-value report kept for backward
        # compatibility; it is None when K and V use different widths.
        s["bits_per_element"] = (
            self._k_bits if self._k_bits == self._v_bits else None
        )
        s["bit_packed_storage"] = True
        s["bit_packed_at_full_bit_width"] = (
            self._k_bits == 4 and self._v_bits == 4
        )
        return s
