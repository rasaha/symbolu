"""
Numba JIT kernels for the TurboQuant polar transform.

Replaces the numpy-level polar transform loop (arctan2 + sqrt across 7
levels) with a single compiled CPU kernel:

  - _compress_polar_numba:   fuses all 7 levels in one sequential loop
                              (no parallel=True — prange with per-segment
                              .copy() caused heap allocations exceeding the
                              benefit of parallelism at n_segs=4608)
  - _decompress_polar_numba: all levels fused, cos/sin from precomputed
                              lookup tables, parallel via prange

Expected speedup vs numpy inner loop: 2–5× depending on CPU / tensor size.
The rotation matmul (segs @ R.T) is left to BLAS — it is already optimal.

Quantization scheme: LUT floor quantization.  Level-0 angles are in
[-π, π], quantized as k = floor((θ+π) × n_grid_bins/(2π)); level-1+
angles are in [0, π/2], quantized as k = floor(θ × 2·n_grid_bins/π).
This is faster than argmin and produces identical results for uniform grids.

When Numba is unavailable the module exports numpy fallbacks with identical
signatures so callers need no conditional logic.
"""

from __future__ import annotations

import math
import numpy as np

try:
    from numba import njit, prange
    _NUMBA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NUMBA_AVAILABLE = False


def is_numba_available() -> bool:
    return _NUMBA_AVAILABLE


# ---------------------------------------------------------------------------
# Compress kernel
# ---------------------------------------------------------------------------

if _NUMBA_AVAILABLE:

    @njit(cache=True, fastmath=True)
    def _compress_polar_numba(
        rotated: np.ndarray,       # (n_segs, d) float32 — already rotated
        n_grid_bins: int,          # 2**angle_bits — number of quantization grid bins
        lut_scale_full: float,     # n_grid_bins / (2π)   — level-0 quantizer
        lut_scale_pos: float,      # 2*n_grid_bins / π    — level-1+ quantizer
    ):
        """
        Recursive polar transform + quantization for all segments, compiled.

        All 7 levels are fused into a single sequential loop.  No parallel=True:
        prange with per-segment .copy() creates heap allocations that exceed
        the benefit of parallelism at typical batch sizes (n_segs=4608).
        The compiled scalar atan2/sqrt path alone is ~2× faster than numpy.

        In-place radius packing: after processing level k, the n_pairs radii
        are written into buf[0..n_pairs-1], overwriting the consumed pairs.
        This is safe because the write index i < read indices 2i / 2i+1.

        Args:
            rotated:        (n_segs, d) float32, already rotated by R.
            n_grid_bins:    2**angle_bits, number of quantization grid bins.
            lut_scale_full: n_grid_bins / (2π), LUT scale for level-0.
            lut_scale_pos:  2 * n_grid_bins / π, LUT scale for level-1+.

        Returns:
            radii:   (n_segs,) float32
            indices: (n_segs, d-1) uint8  — grid bin indices, all levels concatenated
        """
        n_segs, d = rotated.shape
        radii_out   = np.empty(n_segs, dtype=np.float32)
        indices_out = np.empty((n_segs, d - 1), dtype=np.uint8)
        pi = math.pi

        for seg in range(n_segs):
            # Local buffer: copy current segment row (avoids aliasing issues)
            buf = rotated[seg].copy()
            cur_len = d
            idx_pos = 0
            level   = 0

            while cur_len > 1:
                n_pairs   = cur_len >> 1          # cur_len // 2
                has_carry = (cur_len & 1) == 1    # cur_len % 2

                for i in range(n_pairs):
                    x = buf[2 * i]
                    y = buf[2 * i + 1]

                    r     = math.sqrt(x * x + y * y)
                    theta = math.atan2(y, x)

                    if level == 0:
                        k = int(math.floor((theta + pi) * lut_scale_full))
                    else:
                        k = int(math.floor(theta * lut_scale_pos))

                    # Clamp to [0, n_grid_bins-1]
                    if k < 0:              k = 0
                    if k >= n_grid_bins:   k = n_grid_bins - 1

                    indices_out[seg, idx_pos] = k
                    idx_pos += 1
                    buf[i]  = r   # pack radius in-place (safe: i < 2i)

                if has_carry:
                    buf[n_pairs] = buf[cur_len - 1]
                    cur_len = n_pairs + 1
                else:
                    cur_len = n_pairs

                level += 1

            radii_out[seg] = buf[0]

        return radii_out, indices_out

else:  # numpy fallback

    def _compress_polar_numba(rotated, n_grid_bins, lut_scale_full, lut_scale_pos):  # type: ignore[misc]
        """Numpy fallback — same signature as the Numba version."""
        n_segs, d = rotated.shape
        radii_out   = np.empty(n_segs, dtype=np.float32)
        indices_out = np.empty((n_segs, d - 1), dtype=np.uint8)
        pi = math.pi

        for seg in range(n_segs):
            buf     = rotated[seg].copy()
            cur_len = d
            idx_pos = 0
            level   = 0

            while cur_len > 1:
                n_pairs   = cur_len >> 1
                has_carry = (cur_len & 1) == 1

                for i in range(n_pairs):
                    x = float(buf[2 * i])
                    y = float(buf[2 * i + 1])
                    r = math.sqrt(x * x + y * y)
                    theta = math.atan2(y, x)
                    if level == 0:
                        k = int(math.floor((theta + pi) * lut_scale_full))
                    else:
                        k = int(math.floor(theta * lut_scale_pos))
                    k = max(0, min(k, n_grid_bins - 1))
                    indices_out[seg, idx_pos] = k
                    idx_pos += 1
                    buf[i] = r

                if has_carry:
                    buf[n_pairs] = buf[cur_len - 1]
                    cur_len = n_pairs + 1
                else:
                    cur_len = n_pairs
                level += 1

            radii_out[seg] = buf[0]

        return radii_out, indices_out


# ---------------------------------------------------------------------------
# Decompress kernel
# ---------------------------------------------------------------------------

if _NUMBA_AVAILABLE:

    @njit(parallel=True, cache=True, fastmath=True)
    def _decompress_polar_numba(
        radii: np.ndarray,           # (n_segs,) float32
        indices: np.ndarray,         # (n_segs, d-1) uint8
        level_pairs: np.ndarray,     # (n_levels_count,) int32 — n_pairs per level
        level_carries: np.ndarray,   # (n_levels_count,) bool
        cos_grid_full: np.ndarray,   # (n_levels,) float32
        sin_grid_full: np.ndarray,   # (n_levels,) float32
        cos_grid_pos: np.ndarray,    # (n_levels,) float32
        sin_grid_pos: np.ndarray,    # (n_levels,) float32
    ) -> np.ndarray:
        """
        Reverse polar transform for all segments, compiled.

        Reconstructs coordinates level by level in reverse order.
        Uses precomputed cos/sin tables (size n_levels) — no transcendental
        calls in the hot path, only integer index lookups.

        In-place expansion: for each level, expand n_pairs radii to 2*n_pairs
        coordinates by iterating in DESCENDING index order to avoid overwriting
        values before they are read (write index 2i >= read index i).

        Returns:
            (n_segs, d) float32
        """
        n_segs     = radii.shape[0]
        n_levels_k = level_pairs.shape[0]
        d          = 1
        for k in range(n_levels_k):
            d += level_pairs[k]   # sum of all n_pairs = d - 1, plus initial 1

        out = np.empty((n_segs, d), dtype=np.float32)

        for seg in prange(n_segs):
            buf     = np.empty(d, dtype=np.float32)
            buf[0]  = radii[seg]
            cur_len = 1
            idx_pos = indices.shape[1]  # start at end, walk backwards

            # Reverse through levels (last level first)
            for rev in range(n_levels_k):
                k        = n_levels_k - 1 - rev
                n_pairs  = level_pairs[k]
                has_carry = level_carries[k]
                is_level0 = (k == 0)
                idx_pos  -= n_pairs

                if has_carry:
                    # Move carry element out of the way before in-place expansion
                    buf[2 * n_pairs] = buf[n_pairs]

                # Expand in descending order: buf[i] → (buf[2i], buf[2i+1])
                for i in range(n_pairs - 1, -1, -1):
                    r   = buf[i]
                    idx = int(indices[seg, idx_pos + i])
                    if is_level0:
                        cos_v = cos_grid_full[idx]
                        sin_v = sin_grid_full[idx]
                    else:
                        cos_v = cos_grid_pos[idx]
                        sin_v = sin_grid_pos[idx]
                    buf[2 * i]     = r * cos_v
                    buf[2 * i + 1] = r * sin_v

                if has_carry:
                    cur_len = 2 * n_pairs + 1
                else:
                    cur_len = 2 * n_pairs

            for j in range(d):
                out[seg, j] = buf[j]

        return out

else:  # numpy fallback

    def _decompress_polar_numba(  # type: ignore[misc]
        radii, indices, level_pairs, level_carries,
        cos_grid_full, sin_grid_full, cos_grid_pos, sin_grid_pos,
    ):
        """Numpy fallback — same signature."""
        n_segs     = radii.shape[0]
        n_levels_k = level_pairs.shape[0]
        d          = 1 + int(np.sum(level_pairs))

        out = np.empty((n_segs, d), dtype=np.float32)

        for seg in range(n_segs):
            buf    = np.empty(d, dtype=np.float32)
            buf[0] = radii[seg]
            idx_pos = indices.shape[1]

            for rev in range(n_levels_k):
                k         = n_levels_k - 1 - rev
                n_pairs   = int(level_pairs[k])
                has_carry = bool(level_carries[k])
                is_lv0    = (k == 0)
                idx_pos  -= n_pairs

                if has_carry:
                    buf[2 * n_pairs] = buf[n_pairs]

                for i in range(n_pairs - 1, -1, -1):
                    r   = float(buf[i])
                    idx = int(indices[seg, idx_pos + i])
                    cv  = float(cos_grid_full[idx] if is_lv0 else cos_grid_pos[idx])
                    sv  = float(sin_grid_full[idx] if is_lv0 else sin_grid_pos[idx])
                    buf[2 * i]     = r * cv
                    buf[2 * i + 1] = r * sv

            out[seg] = buf

        return out


# ---------------------------------------------------------------------------
# Precompute level structure (shared between compress and decompress callers)
# ---------------------------------------------------------------------------

def build_level_structure(segment_dim: int):
    """
    Returns (level_pairs, level_carries) arrays for use with
    _compress_polar_numba and _decompress_polar_numba.

    level_pairs[k]   = number of (x,y) pairs processed at level k
    level_carries[k] = True if level k has an odd number of elements
                       (the last element is carried to the next level)
    """
    pairs_list  = []
    carries_list = []
    cur = segment_dim
    while cur > 1:
        n_pairs = cur >> 1
        pairs_list.append(n_pairs)
        carries_list.append((cur & 1) == 1)
        cur = n_pairs + (cur & 1)
    return (
        np.array(pairs_list,   dtype=np.int32),
        np.array(carries_list, dtype=np.bool_),
    )


# ---------------------------------------------------------------------------
# CUDA-compatible helpers (used by turboquant_cuda_ext.py)
# ---------------------------------------------------------------------------

def compute_level_offsets(segment_dim: int):
    """
    Returns (level_sizes, level_offsets) as int32 arrays for CUDA kernels.

    level_sizes[k]   = number of angle pairs at level k
    level_offsets[k]  = cumulative offset into flat angle buffer
    """
    pairs, _ = build_level_structure(segment_dim)
    offsets = np.zeros(len(pairs) + 1, dtype=np.int32)
    for i, p in enumerate(pairs):
        offsets[i + 1] = offsets[i] + p
    return pairs, offsets


def build_angle_grids(angle_bits: int):
    """
    Build fixed quantisation grids and LUT scale constants.

    The grids are uniform midpoint grids.  The LUT scales implement the
    same quantization as floor(theta * scale) — which is equivalent to
    argmin on a uniform grid but O(1) instead of O(n_grid).

    Returns
    -------
    grid_full : (n_grid,) float32  — level 0, midpoints on [-π, π]
    grid_pos  : (n_grid,) float32  — level 1+, midpoints on [0, π/2]
    lut_scale_full : float  — n_grid / (2π), for floor((θ+π) * scale)
    lut_scale_pos  : float  — 2*n_grid / π, for floor(θ * scale)
    """
    n = 2 ** angle_bits
    grid_full = np.linspace(-math.pi, math.pi, n, endpoint=False) + math.pi / n
    grid_pos = np.linspace(0, math.pi / 2, n, endpoint=False) + math.pi / (4 * n)
    lut_scale_full = n / (2.0 * math.pi)
    lut_scale_pos = 2.0 * n / math.pi
    return (
        grid_full.astype(np.float32),
        grid_pos.astype(np.float32),
        lut_scale_full,
        lut_scale_pos,
    )
