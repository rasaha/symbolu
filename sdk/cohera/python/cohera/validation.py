"""
COHERA validation utilities.

Reference implementations used by the P4 test matrix to check that the
device-side kernels agree with the well-known reference semantics:

  - GQA broadcast matches ``torch.repeat_interleave`` along the KV-head axis.
  - RoPE output matches the Llama / Mistral complex-rotation formula.
  - BF16 coherence computed via IEEE bf16 round-trip stays within the
    relative-error budget of the FP32 reference.
  - Causal + sliding-window masks prevent future tokens from ever entering
    an aggregation at position i.

All helpers are pure Python (lists / math) so they run in the SDK test
sandbox without torch / numpy. Callers that already have those libraries
can of course feed in arrays — the helpers accept any 1-D / nested
sequence-like input.
"""

from __future__ import annotations

import math
import struct
from typing import Iterable, List, Sequence, Tuple


# ---------------------------------------------------------------------------
# GQA
# ---------------------------------------------------------------------------

def gqa_broadcast_reference(
    kv: Sequence[Sequence[Sequence[float]]],
    num_heads: int,
) -> List[List[List[float]]]:
    """
    Reference for ``cohera_gqa_broadcast`` / the GQA dispatch inside the
    phase-attention kernel.

    Input ``kv`` shape:   [seq, num_kv_heads, head_dim]
    Output shape:         [seq, num_heads,    head_dim]

    Each KV head is repeated ``num_heads // num_kv_heads`` times — matches
    ``torch.repeat_interleave(kv, repeats=group_size, dim=-2)``.
    """
    if not kv or not kv[0]:
        return []
    num_kv_heads = len(kv[0])
    if num_kv_heads <= 0 or num_heads % num_kv_heads != 0:
        raise ValueError(
            f"num_heads ({num_heads}) must be divisible by "
            f"num_kv_heads ({num_kv_heads})"
        )
    group = num_heads // num_kv_heads
    out: List[List[List[float]]] = []
    for tok in kv:
        row: List[List[float]] = []
        for kv_h in tok:
            for _ in range(group):
                row.append(list(kv_h))
        out.append(row)
    return out


def gqa_broadcast_parity(
    device_output: Sequence[Sequence[Sequence[float]]],
    kv: Sequence[Sequence[Sequence[float]]],
    num_heads: int,
    atol: float = 0.0,
) -> bool:
    """Assert that ``device_output`` is bit-equal to the reference (within atol)."""
    ref = gqa_broadcast_reference(kv, num_heads)
    if len(ref) != len(device_output):
        return False
    for ref_tok, dev_tok in zip(ref, device_output):
        if len(ref_tok) != len(dev_tok):
            return False
        for ref_head, dev_head in zip(ref_tok, dev_tok):
            if len(ref_head) != len(dev_head):
                return False
            for r, d in zip(ref_head, dev_head):
                if abs(float(r) - float(d)) > atol:
                    return False
    return True


# ---------------------------------------------------------------------------
# RoPE
# ---------------------------------------------------------------------------

def rope_inv_freqs(rope_dim: int, base: float = 10000.0) -> List[float]:
    """HF-standard RoPE inverse frequencies: 1 / base^(2i / rope_dim)."""
    if rope_dim <= 0 or rope_dim % 2 != 0:
        return []
    return [1.0 / (base ** (2.0 * i / rope_dim)) for i in range(rope_dim // 2)]


def apply_rope_reference(
    x: Sequence[float],
    position: int,
    rope_dim: int,
    inv_freqs: Sequence[float],
) -> List[float]:
    """
    Apply RoPE to a single head_dim vector.

    Rotates ``x[0:rope_dim]`` in consecutive (2k, 2k+1) pairs; elements
    above ``rope_dim`` are passed through unchanged. Matches
    ``cohera_apply_rope`` / ``mistral_phase_attention.apply_rope``.
    """
    if len(x) < rope_dim:
        raise ValueError("x is shorter than rope_dim")
    if len(inv_freqs) < rope_dim // 2:
        raise ValueError("inv_freqs must have rope_dim/2 entries")

    out = list(x)
    for k in range(rope_dim // 2):
        theta = position * inv_freqs[k]
        c, s = math.cos(theta), math.sin(theta)
        x0, x1 = out[2 * k], out[2 * k + 1]
        out[2 * k]     = x0 * c - x1 * s
        out[2 * k + 1] = x0 * s + x1 * c
    return out


def rope_match_reference(
    device_output: Sequence[float],
    x: Sequence[float],
    position: int,
    rope_dim: int,
    inv_freqs: Sequence[float],
    atol: float = 1e-6,
) -> bool:
    """True iff ``device_output`` matches the reference RoPE within atol."""
    ref = apply_rope_reference(x, position, rope_dim, inv_freqs)
    if len(ref) != len(device_output):
        return False
    return all(abs(float(r) - float(d)) <= atol for r, d in zip(ref, device_output))


# ---------------------------------------------------------------------------
# BF16 coherence
# ---------------------------------------------------------------------------

def _f32_to_bf16_f32(x: float) -> float:
    """
    Round-trip a float32 through the BF16 representation and return the
    resulting float32. Emulates the lossy conversion the kernel does when
    ``dtype == BF16``.
    """
    bits = struct.unpack("<I", struct.pack("<f", float(x)))[0]
    # Round-to-nearest-even on the dropped low 16 bits
    rounded = (bits + 0x7FFF + ((bits >> 16) & 1)) & 0xFFFF0000
    return struct.unpack("<f", struct.pack("<I", rounded))[0]


def coherence_fp32(phases: Iterable[float]) -> float:
    """|sum exp(i * phi)| / N over the full sequence (FP32 reference)."""
    sin_sum = cos_sum = 0.0
    count = 0
    for phi in phases:
        sin_sum += math.sin(phi)
        cos_sum += math.cos(phi)
        count += 1
    if count == 0:
        return 0.0
    return math.sqrt(sin_sum * sin_sum + cos_sum * cos_sum) / count


def coherence_bf16_emulated(phases: Iterable[float]) -> float:
    """
    Coherence computed with each sin/cos partial cast through BF16.
    Matches the kernel's BF16 store/load round trip on the reductions.
    """
    sin_sum = cos_sum = 0.0
    count = 0
    for phi in phases:
        sin_sum += _f32_to_bf16_f32(math.sin(phi))
        cos_sum += _f32_to_bf16_f32(math.cos(phi))
        count += 1
    if count == 0:
        return 0.0
    # Final magnitude / divide stays in FP32 in the kernel
    return math.sqrt(sin_sum * sin_sum + cos_sum * cos_sum) / count


def bf16_coherence_rel_error(
    phases: Iterable[float],
) -> Tuple[float, float, float]:
    """
    Returns (fp32_coherence, bf16_coherence, relative_error).

    Budget from the P1 audit: BF16 coherence must stay within 1% relative
    error of the FP32 reference.
    """
    phases = list(phases)
    fp32 = coherence_fp32(phases)
    bf16 = coherence_bf16_emulated(phases)
    if fp32 == 0.0:
        rel = 0.0 if bf16 == 0.0 else float("inf")
    else:
        rel = abs(fp32 - bf16) / abs(fp32)
    return fp32, bf16, rel


# ---------------------------------------------------------------------------
# Causal / sliding-window mask leak detection
# ---------------------------------------------------------------------------

def attention_mask_leak_positions(
    attn_weights: Sequence[Sequence[float]],
    causal: bool = True,
    window_size: int = -1,
    atol: float = 0.0,
) -> List[Tuple[int, int]]:
    """
    Returns a list of (i, j) positions where ``attn_weights[i][j]`` is
    non-zero but should have been masked out given the causal /
    sliding-window contract.

    An empty list means the mask is honoured.
    """
    leaks: List[Tuple[int, int]] = []
    seq_len = len(attn_weights)
    for i in range(seq_len):
        row = attn_weights[i]
        if len(row) != seq_len:
            raise ValueError(f"row {i} has length {len(row)}, expected {seq_len}")
        for j in range(seq_len):
            if causal and j > i:
                if abs(float(row[j])) > atol:
                    leaks.append((i, j))
                continue
            if window_size > 0:
                if j < i - window_size + 1:
                    if abs(float(row[j])) > atol:
                        leaks.append((i, j))
    return leaks


def assert_no_mask_leak(
    attn_weights: Sequence[Sequence[float]],
    causal: bool = True,
    window_size: int = -1,
    atol: float = 0.0,
) -> None:
    """Raise ``AssertionError`` listing every position that violates the mask."""
    leaks = attention_mask_leak_positions(
        attn_weights, causal=causal, window_size=window_size, atol=atol,
    )
    if leaks:
        sample = leaks[:10]
        raise AssertionError(
            f"attention mask leak: {len(leaks)} violations; first ones: {sample}"
        )
