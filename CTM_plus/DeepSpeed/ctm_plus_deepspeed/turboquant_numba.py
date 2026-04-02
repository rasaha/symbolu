"""
TurboQuant Numba-accelerated kernels for PolarQuant compress / decompress.

Provides JIT-compiled routines for the recursive polar coordinate
transformation used in TurboQuant KV-cache compression.

Architecture decisions
----------------------
* **Decompress** (`_decompress_batch_kernel`): uses ``prange`` over the batch
  dimension — each vector reconstruction is independent, so threading pays off
  for batch sizes ≥ 64.
* **Compress** (`_compress_batch_kernel`): **sequential** compiled loop (no
  ``parallel=True``).  ``prange`` with per-segment slice copies created heap
  allocations that exceeded the benefit of parallelism at typical n_segs = 4608.
  The compiled scalar ``atan2`` / ``sqrt`` path alone is ~2× faster than numpy
  broadcast for compress.
* All kernels operate on **flat 1-D angle buffers** with precomputed level
  offsets to avoid 2-D ragged-array indexing.

Level structure (head_dim = 128)
--------------------------------
Level 0: 64 angles (pairs of rotated Gaussian coords, range [-π, π])
Level 1: 32 angles (radius pairs, range [0, π/2])
Level 2: 16
Level 3:  8
Level 4:  4
Level 5:  2
Level 6:  1
Total:  127 angles + 1 final radius per vector.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# Numba availability
# ---------------------------------------------------------------------------

_NUMBA_AVAILABLE = False

try:
    import numba
    from numba import njit, prange, float64, int64, float32

    _NUMBA_AVAILABLE = True
except ImportError:
    pass


def numba_available() -> bool:
    """Return True if Numba is importable and JIT compilation will work."""
    return _NUMBA_AVAILABLE


# ---------------------------------------------------------------------------
# Level geometry helpers (pure Python — called once at init, not in hot path)
# ---------------------------------------------------------------------------

def compute_level_structure(head_dim: int) -> dict:
    """
    Return the level geometry for a given head dimension.

    Returns
    -------
    dict with keys:
        n_levels      : int            — number of polar tree levels
        level_sizes   : list[int]      — angles per level
        level_offsets : list[int]      — cumulative offset into flat angle buf
        total_angles  : int            — sum(level_sizes) == head_dim - 1
    """
    sizes: list[int] = []
    d = head_dim
    while d > 1:
        n_pairs = d // 2
        sizes.append(n_pairs)
        d = n_pairs + (d % 2)  # carry-forward odd element

    offsets = [0]
    for s in sizes:
        offsets.append(offsets[-1] + s)

    return {
        "n_levels": len(sizes),
        "level_sizes": sizes,
        "level_offsets": offsets,
        "total_angles": offsets[-1],
    }


def build_angle_grids(angle_bits: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Build the fixed quantisation grids.

    Returns
    -------
    grid_full : ndarray, shape (2**angle_bits,)
        Uniform grid on [-π, π] for level-0 (Gaussian pairs).
    grid_pos  : ndarray, shape (2**angle_bits,)
        Uniform grid on [0, π/2] for level 1+ (radius pairs).
    """
    n = 2 ** angle_bits
    grid_full = np.linspace(-math.pi, math.pi, n, endpoint=False) + math.pi / n
    grid_pos = np.linspace(0, math.pi / 2, n, endpoint=False) + math.pi / (4 * n)
    return grid_full.astype(np.float64), grid_pos.astype(np.float64)


# ---------------------------------------------------------------------------
# Numba kernels (guarded behind _NUMBA_AVAILABLE)
# ---------------------------------------------------------------------------

if _NUMBA_AVAILABLE:

    # ------------------------------------------------------------------
    # Compress: sequential JIT — no parallel=True
    # ------------------------------------------------------------------

    @njit(cache=True)
    def _compress_single(
        rotated,        # (head_dim,) float64 — R @ v
        grid_full,      # (n_grid,) float64
        grid_pos,       # (n_grid,) float64
        level_sizes,    # (n_levels,) int64
        level_offsets,  # (n_levels+1,) int64
        n_levels,       # int
        head_dim,       # int
        out_angles,     # (total_angles,) float64  — quantised angles
        out_indices,    # (total_angles,) int64     — grid indices
    ):
        """Compress one vector: recursive polar → quantised angles + radius."""
        # Working buffer — reuse across levels.  Max size == head_dim.
        radii = np.empty(head_dim, dtype=np.float64)
        new_radii = np.empty(head_dim, dtype=np.float64)

        # Initialise radii from rotated vector
        for i in range(head_dim):
            radii[i] = rotated[i]

        cur_len = head_dim

        for lvl in range(n_levels):
            n_pairs = level_sizes[lvl]
            off = level_offsets[lvl]
            nr = 0  # count of new radii this level

            for p in range(n_pairs):
                x = radii[2 * p]
                y = radii[2 * p + 1]
                r = math.sqrt(x * x + y * y)
                theta = math.atan2(y, x)

                # Quantise
                if lvl == 0:
                    grid = grid_full
                else:
                    grid = grid_pos

                best_idx = 0
                best_dist = abs(theta - grid[0])
                for g in range(1, grid.shape[0]):
                    d = abs(theta - grid[g])
                    if d < best_dist:
                        best_dist = d
                        best_idx = g

                out_angles[off + p] = grid[best_idx]
                out_indices[off + p] = best_idx
                new_radii[nr] = r
                nr += 1

            # Carry-forward odd element
            if cur_len % 2 == 1:
                new_radii[nr] = radii[cur_len - 1]
                nr += 1

            # Swap buffers
            for i in range(nr):
                radii[i] = new_radii[i]
            cur_len = nr

        return radii[0]  # final radius

    @njit(cache=True)
    def _compress_batch_kernel(
        rotated_batch,   # (batch, head_dim) float64
        grid_full,
        grid_pos,
        level_sizes,
        level_offsets,
        n_levels,
        head_dim,
        out_angles,      # (batch, total_angles) float64
        out_indices,     # (batch, total_angles) int64
        out_radii,       # (batch,) float64
    ):
        """Compress a batch of vectors (sequential — no prange)."""
        batch = rotated_batch.shape[0]
        for b in range(batch):
            out_radii[b] = _compress_single(
                rotated_batch[b],
                grid_full,
                grid_pos,
                level_sizes,
                level_offsets,
                n_levels,
                head_dim,
                out_angles[b],
                out_indices[b],
            )

    # ------------------------------------------------------------------
    # Decompress: parallel across batch dimension
    # ------------------------------------------------------------------

    @njit(cache=True)
    def _decompress_single(
        radius,          # float64
        q_angles,        # (total_angles,) float64 — quantised angles
        level_sizes,     # (n_levels,) int64
        level_offsets,   # (n_levels+1,) int64
        n_levels,        # int
        head_dim,        # int
        out_coords,      # (head_dim,) float64
    ):
        """Reconstruct one vector from (radius, quantised_angles)."""
        # Working buffers
        radii = np.empty(head_dim, dtype=np.float64)
        new_coords = np.empty(head_dim, dtype=np.float64)

        radii[0] = radius
        cur_len = 1

        # Walk levels in reverse (from root → leaves)
        for rev in range(n_levels):
            lvl = n_levels - 1 - rev
            n_angles = level_sizes[lvl]
            off = level_offsets[lvl]

            nc = 0
            a_idx = 0
            for i in range(cur_len):
                r = radii[i]
                if a_idx < n_angles:
                    theta = q_angles[off + a_idx]
                    a_idx += 1
                    new_coords[nc] = r * math.cos(theta)
                    nc += 1
                    new_coords[nc] = r * math.sin(theta)
                    nc += 1
                else:
                    # Odd carry-forward
                    new_coords[nc] = r
                    nc += 1

            for i in range(nc):
                radii[i] = new_coords[i]
            cur_len = nc

        for i in range(head_dim):
            out_coords[i] = radii[i]

    @njit(parallel=True, cache=True)
    def _decompress_batch_kernel(
        radii,           # (batch,) float64
        q_angles,        # (batch, total_angles) float64
        level_sizes,     # (n_levels,) int64
        level_offsets,   # (n_levels+1,) int64
        n_levels,        # int
        head_dim,        # int
        out_vectors,     # (batch, head_dim) float64
    ):
        """Decompress a batch of vectors — parallel across batch."""
        batch = radii.shape[0]
        for b in prange(batch):
            _decompress_single(
                radii[b],
                q_angles[b],
                level_sizes,
                level_offsets,
                n_levels,
                head_dim,
                out_vectors[b],
            )


# ---------------------------------------------------------------------------
# High-level Python API
# ---------------------------------------------------------------------------

class TurboQuantNumba:
    """
    Numba-accelerated PolarQuant compress / decompress.

    Usage::

        tqn = TurboQuantNumba(head_dim=128, angle_bits=3, seed=42)
        radii, angles, indices = tqn.compress(vectors)   # vectors: (B, 128)
        recon = tqn.decompress(radii, angles)             # (B, 128)

    Falls back to pure-numpy if Numba is not installed.
    """

    def __init__(
        self,
        head_dim: int = 128,
        angle_bits: int = 3,
        seed: int = 42,
    ):
        self.head_dim = head_dim
        self.angle_bits = angle_bits
        self.seed = seed

        # Level geometry
        ls = compute_level_structure(head_dim)
        self.n_levels = ls["n_levels"]
        self.total_angles = ls["total_angles"]
        self._level_sizes = np.array(ls["level_sizes"], dtype=np.int64)
        self._level_offsets = np.array(ls["level_offsets"], dtype=np.int64)

        # Angle grids
        self._grid_full, self._grid_pos = build_angle_grids(angle_bits)

        # Rotation matrix
        rng = np.random.RandomState(seed)
        H = rng.randn(head_dim, head_dim)
        Q, R = np.linalg.qr(H)
        self._rotation = Q @ np.diag(np.sign(np.diag(R)))
        self._rotation_t = self._rotation.T.copy()

        # Warm-up Numba JIT on first call
        self._warmed_up = False

    def _warmup(self) -> None:
        """Trigger JIT compilation with a tiny dummy batch."""
        if self._warmed_up or not _NUMBA_AVAILABLE:
            return
        dummy = np.zeros((1, self.head_dim), dtype=np.float64)
        self.compress(dummy)
        r = np.zeros(1, dtype=np.float64)
        a = np.zeros((1, self.total_angles), dtype=np.float64)
        self.decompress(r, a)
        self._warmed_up = True

    # ------------------------------------------------------------------ #
    #  Compress                                                           #
    # ------------------------------------------------------------------ #

    def compress(
        self, vectors: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compress a batch of vectors.

        Parameters
        ----------
        vectors : ndarray, shape (batch, head_dim), float32/float64

        Returns
        -------
        radii   : (batch,) float64 — final polar radius per vector
        angles  : (batch, total_angles) float64 — quantised angle values
        indices : (batch, total_angles) int64   — grid bin indices
        """
        vectors = np.ascontiguousarray(vectors, dtype=np.float64)
        batch = vectors.shape[0]

        # Rotate
        rotated = vectors @ self._rotation.T  # (B, D)

        # Allocate outputs
        out_angles = np.empty((batch, self.total_angles), dtype=np.float64)
        out_indices = np.empty((batch, self.total_angles), dtype=np.int64)
        out_radii = np.empty(batch, dtype=np.float64)

        if _NUMBA_AVAILABLE:
            _compress_batch_kernel(
                rotated,
                self._grid_full,
                self._grid_pos,
                self._level_sizes,
                self._level_offsets,
                self.n_levels,
                self.head_dim,
                out_angles,
                out_indices,
                out_radii,
            )
        else:
            self._compress_numpy(rotated, out_angles, out_indices, out_radii)

        return out_radii, out_angles, out_indices

    def _compress_numpy(self, rotated, out_angles, out_indices, out_radii):
        """Pure-numpy fallback for compress."""
        batch = rotated.shape[0]
        for b in range(batch):
            radii = rotated[b].copy()
            cur_len = self.head_dim

            for lvl in range(self.n_levels):
                n_pairs = self._level_sizes[lvl]
                off = self._level_offsets[lvl]
                grid = self._grid_full if lvl == 0 else self._grid_pos

                xs = radii[:2 * n_pairs:2]
                ys = radii[1:2 * n_pairs:2]
                rs = np.sqrt(xs * xs + ys * ys)
                thetas = np.arctan2(ys, xs)

                idxs = np.argmin(np.abs(thetas[:, None] - grid[None, :]), axis=1)
                out_angles[b, off:off + n_pairs] = grid[idxs]
                out_indices[b, off:off + n_pairs] = idxs

                new_radii = np.empty(n_pairs + (cur_len % 2), dtype=np.float64)
                new_radii[:n_pairs] = rs
                if cur_len % 2 == 1:
                    new_radii[n_pairs] = radii[cur_len - 1]

                radii = new_radii
                cur_len = len(radii)

            out_radii[b] = radii[0]

    # ------------------------------------------------------------------ #
    #  Decompress                                                         #
    # ------------------------------------------------------------------ #

    def decompress(
        self,
        radii: np.ndarray,
        angles: np.ndarray,
    ) -> np.ndarray:
        """
        Reconstruct vectors from compressed representation.

        Parameters
        ----------
        radii  : (batch,) float64
        angles : (batch, total_angles) float64 — quantised angle values

        Returns
        -------
        vectors : (batch, head_dim) float64
        """
        radii = np.ascontiguousarray(radii, dtype=np.float64)
        angles = np.ascontiguousarray(angles, dtype=np.float64)
        batch = radii.shape[0]

        out = np.empty((batch, self.head_dim), dtype=np.float64)

        if _NUMBA_AVAILABLE:
            _decompress_batch_kernel(
                radii,
                angles,
                self._level_sizes,
                self._level_offsets,
                self.n_levels,
                self.head_dim,
                out,
            )
        else:
            self._decompress_numpy(radii, angles, out)

        # Inverse rotation: v = R^T @ coords
        return out @ self._rotation

    def _decompress_numpy(self, radii, angles, out):
        """Pure-numpy fallback for decompress."""
        batch = radii.shape[0]
        for b in range(batch):
            r_buf = np.array([radii[b]])

            for rev in range(self.n_levels):
                lvl = self.n_levels - 1 - rev
                n_angles = self._level_sizes[lvl]
                off = self._level_offsets[lvl]

                new_coords = []
                a_idx = 0
                for i in range(len(r_buf)):
                    r = r_buf[i]
                    if a_idx < n_angles:
                        theta = angles[b, off + a_idx]
                        a_idx += 1
                        new_coords.append(r * math.cos(theta))
                        new_coords.append(r * math.sin(theta))
                    else:
                        new_coords.append(r)
                r_buf = np.array(new_coords)

            out[b, :] = r_buf[:self.head_dim]
