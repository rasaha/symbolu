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
# Quantization primitives                                                     #
# --------------------------------------------------------------------------- #


def quantize_per_channel_int4(
    tensor: "torch.Tensor", *, group_size: int = 0,
) -> "Tuple[torch.Tensor, torch.Tensor]":
    """Per-channel symmetric INT4 quantization, optionally with
    group-wise scaling along the seq axis.

    Args:
        tensor: ``(S, H, D)`` — seq × num_kv_heads × head_dim. The seq
            axis is the one being aggregated over.
        group_size: when > 0, split the seq axis into chunks of
            ``group_size`` and compute a separate scale for each chunk.
            ``0`` (the default) means "one scale per channel covering
            all S positions" — equivalent to plain per-channel. KIVI's
            published quality numbers on Qwen-family use group_size=32
            or 128; smaller groups improve outlier-position resolution
            at a cost of more scale storage.

    Returns:
        ``(quantized, scale)``:
          * ``quantized``: ``(S, H, D) int8`` with values in [−8, +7].
          * ``scale``: ``(n_groups, H, D) float32`` where
            ``n_groups == ceil(S / max(group_size, S))`` — i.e., 1 for
            plain per-channel, ``ceil(S / group_size)`` when grouped.
            ``quantized * scale[group_idx_per_position] ≈ tensor``.
    """
    if tensor.ndim != 3:
        raise ValueError(
            f"quantize_per_channel_int4 expected 3-D (S, H, D) tensor; "
            f"got shape {tuple(tensor.shape)}"
        )
    s, h, d = tensor.shape
    if group_size <= 0 or group_size >= s:
        # Plain per-channel (one scale per (h, d) covering all S positions)
        t_f32 = tensor.to(torch.float32)
        max_abs = t_f32.abs().amax(dim=0, keepdim=True)  # (1, H, D)
        scale = (max_abs / 7.0).clamp(min=1e-8)
        quantized = (t_f32 / scale).round().clamp(min=-8, max=7).to(torch.int8)
        return quantized, scale

    # Group-wise: pad S to a multiple of group_size, reshape, scale per
    # group, quantize, then trim back to (S, H, D).
    pad = (-s) % group_size
    if pad:
        zeros = torch.zeros(pad, h, d, dtype=tensor.dtype, device=tensor.device)
        tensor_padded = torch.cat([tensor, zeros], dim=0)
    else:
        tensor_padded = tensor
    s_padded = tensor_padded.shape[0]
    n_groups = s_padded // group_size

    # Reshape to (n_groups, group_size, H, D)
    t_f32 = tensor_padded.to(torch.float32).view(n_groups, group_size, h, d)
    # Per-group scale: max(|x|) over the group_size axis
    max_abs = t_f32.abs().amax(dim=1, keepdim=True)  # (n_groups, 1, H, D)
    scale = (max_abs / 7.0).clamp(min=1e-8)
    quantized_grouped = (t_f32 / scale).round().clamp(min=-8, max=7).to(torch.int8)
    # Flatten back to (S_padded, H, D), trim padding
    quantized_flat = quantized_grouped.view(s_padded, h, d)[:s].contiguous()
    return quantized_flat, scale.squeeze(1)  # (n_groups, H, D)


def dequantize_per_channel_int4(
    quantized: "torch.Tensor",
    scale: "torch.Tensor",
    *,
    dtype: Any,
    group_size: int = 0,
) -> "torch.Tensor":
    """Inverse of ``quantize_per_channel_int4``.

    ``scale`` shape is ``(1, H, D)`` for plain per-channel or
    ``(n_groups, H, D)`` when grouped. The ``group_size`` argument
    must match what was passed at quantization time so the per-group
    scale broadcast back to per-position is correct.

    Returns a tensor of shape ``(S, H, D)`` and dtype ``dtype``.
    """
    n_groups = scale.shape[0]
    if n_groups == 1:
        # Plain per-channel — scale broadcasts directly over seq axis.
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
    # scale: (n_groups, H, D); unsqueeze(1) → (n_groups, 1, H, D) broadcasts over group_size
    dequant_grouped = grouped.to(scale.dtype) * scale.unsqueeze(1)
    flat = dequant_grouped.view(n_groups * group_size, h, d)[:s].contiguous()
    return flat.to(dtype)


def quantize_per_token_int4(
    tensor: "torch.Tensor", *, group_size: int = 0,
) -> "Tuple[torch.Tensor, torch.Tensor]":
    """Per-token symmetric INT4 quantization, optionally with
    group-wise scaling along the head_dim axis.

    Aggregates over the head_dim (last) axis. KIVI's V choice; with
    group_size > 0 each (seq, head) pair gets ``ceil(D/group_size)``
    scales instead of one.

    Args:
        tensor: ``(S, H, D)``.
        group_size: 0 = one scale per (S, H) covering all D dims
            (plain per-token). > 0 = scale per group of head_dim
            elements within each (S, H).

    Returns:
        ``(quantized (S, H, D) int8, scale (S, H, n_groups) float32)``.
    """
    if tensor.ndim != 3:
        raise ValueError(
            f"quantize_per_token_int4 expected 3-D (S, H, D) tensor; "
            f"got shape {tuple(tensor.shape)}"
        )
    s, h, d = tensor.shape
    if group_size <= 0 or group_size >= d:
        t_f32 = tensor.to(torch.float32)
        max_abs = t_f32.abs().amax(dim=2, keepdim=True)  # (S, H, 1)
        scale = (max_abs / 7.0).clamp(min=1e-8)
        quantized = (t_f32 / scale).round().clamp(min=-8, max=7).to(torch.int8)
        return quantized, scale

    pad = (-d) % group_size
    if pad:
        zeros = torch.zeros(s, h, pad, dtype=tensor.dtype, device=tensor.device)
        tensor_padded = torch.cat([tensor, zeros], dim=2)
    else:
        tensor_padded = tensor
    d_padded = tensor_padded.shape[2]
    n_groups = d_padded // group_size

    t_f32 = tensor_padded.to(torch.float32).view(s, h, n_groups, group_size)
    max_abs = t_f32.abs().amax(dim=3, keepdim=True)  # (S, H, n_groups, 1)
    scale = (max_abs / 7.0).clamp(min=1e-8)
    quantized_grouped = (t_f32 / scale).round().clamp(min=-8, max=7).to(torch.int8)
    quantized_flat = quantized_grouped.view(s, h, d_padded)[:, :, :d].contiguous()
    return quantized_flat, scale.squeeze(3)  # (S, H, n_groups)


def dequantize_per_token_int4(
    quantized: "torch.Tensor",
    scale: "torch.Tensor",
    *,
    dtype: Any,
    group_size: int = 0,
) -> "torch.Tensor":
    n_groups = scale.shape[2]
    if n_groups == 1:
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
    dequant_grouped = grouped.to(scale.dtype) * scale.unsqueeze(3)
    flat = dequant_grouped.view(s, h, n_groups * group_size)[:, :, :d].contiguous()
    return flat.to(dtype)


# --------------------------------------------------------------------------- #
# Compressed buffer + store                                                   #
# --------------------------------------------------------------------------- #


@dataclass
class INT4Block:
    """Per-block compressed state. Mirrors the partner-shareable
    ``theoretical_packed_bytes`` metric used by the TurboQuant kvstore
    so the same Track E artefact format works for either."""

    k_quantized: "torch.Tensor"   # (S, H, D) int8
    k_scale: "torch.Tensor"        # (n_groups_s, H, D) float32; n_groups_s=1 for plain per-channel
    v_quantized: "torch.Tensor"   # (S, H, D) int8
    v_scale: "torch.Tensor"        # (S, H, n_groups_d) float32; n_groups_d=1 for plain per-token
    original_shape: Tuple[int, ...]
    original_dtype: Any
    k_group_size: int = 0          # 0 means plain per-channel
    v_group_size: int = 0          # 0 means plain per-token

    @property
    def theoretical_packed_bytes(self) -> int:
        """Theoretical bit-packed storage:
          * K: 4 bits/elem * S*H*D + 16 bits * n_groups_s * H*D
          * V: 4 bits/elem * S*H*D + 16 bits * S*H * n_groups_d
        Identical formula shape to PolarQuant's metric so the kvstore's
        ``compression_ratio`` is backend-agnostic.
        """
        s, h, d = self.original_shape
        n_groups_s = int(self.k_scale.shape[0])
        n_groups_d = int(self.v_scale.shape[2])
        k_bits = 4 * s * h * d + 16 * n_groups_s * h * d
        v_bits = 4 * s * h * d + 16 * s * h * n_groups_d
        return max(1, (k_bits + v_bits + 7) // 8)


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
    ) -> None:
        if torch is None:
            raise ImportError("INT4PerChannelKVStore requires PyTorch.")
        if k_group_size < 0 or v_group_size < 0:
            raise ValueError(
                f"group sizes must be >= 0; got k={k_group_size}, v={v_group_size}"
            )
        self._torch_device = torch_device
        self._k_group_size = int(k_group_size)
        self._v_group_size = int(v_group_size)
        self._blocks: Dict[int, INT4Block] = {}
        self._stats: Dict[str, Any] = {
            "writes": 0,
            "reads": 0,
            "removes": 0,
            "bytes_in": 0,
            "bytes_out_theoretical": 0,
            "write_us_sum": 0.0,
            "read_us_sum": 0.0,
        }

    def write_block(self, block_id: int, k_array, v_array) -> None:
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

        k_q, k_scale = quantize_per_channel_int4(
            k_in, group_size=self._k_group_size,
        )
        v_q, v_scale = quantize_per_token_int4(
            v_in, group_size=self._v_group_size,
        )

        block = INT4Block(
            k_quantized=k_q,
            k_scale=k_scale,
            v_quantized=v_q,
            v_scale=v_scale,
            original_shape=tuple(int(s) for s in k_array.shape),
            original_dtype=original_dtype,
            k_group_size=self._k_group_size,
            v_group_size=self._v_group_size,
        )
        self._blocks[block_id] = block
        self._stats["writes"] += 1
        self._stats["bytes_in"] += bytes_in
        self._stats["bytes_out_theoretical"] += int(block.theoretical_packed_bytes)
        self._stats["write_us_sum"] += (time.perf_counter() - t0) * 1e6

    def read_block(self, block_id: int) -> "Tuple[torch.Tensor, torch.Tensor]":
        if block_id not in self._blocks:
            raise KeyError(f"INT4PerChannelKVStore: block {block_id} not held")
        t0 = time.perf_counter()
        b = self._blocks[block_id]
        k = dequantize_per_channel_int4(
            b.k_quantized, b.k_scale, dtype=b.original_dtype,
            group_size=b.k_group_size,
        )
        v = dequantize_per_token_int4(
            b.v_quantized, b.v_scale, dtype=b.original_dtype,
            group_size=b.v_group_size,
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
        out = self._stats["bytes_out_theoretical"]
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
        s["blocks_held"] = len(self._blocks)
        s["avg_write_us"] = self.avg_write_us
        s["avg_read_us"] = self.avg_read_us
        s["backend"] = self.backend
        s["k_quantization"] = "per_channel"
        s["v_quantization"] = "per_token"
        s["k_group_size"] = self._k_group_size
        s["v_group_size"] = self._v_group_size
        s["bits_per_element"] = 4
        return s
