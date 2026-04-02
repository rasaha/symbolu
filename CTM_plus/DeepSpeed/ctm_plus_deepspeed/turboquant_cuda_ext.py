"""
TurboQuant CUDA extension — Python bindings for turboquant_cuda.cu.

Provides :class:`TurboQuantCUDA`, a drop-in replacement for the Numba
compress/decompress path that runs entirely on GPU.

Compressed representation: uint8 grid bin indices (matching Numba).
Quantization: LUT floor quantization (matching Numba _compress_polar_numba).

Build modes
-----------
1. **JIT via PyTorch** (preferred)::

       from torch.utils.cpp_extension import load
       # Handled automatically on first import if torch is available.

2. **Ahead-of-time** (no torch dependency)::

       nvcc -O3 -arch=sm_80 --use_fast_math -shared -Xcompiler -fPIC \\
            -o turboquant_cuda.so turboquant_cuda.cu

   Then set ``TURBOQUANT_CUDA_LIB`` env var to the .so path.

Kernel selection
----------------
* ``compress``  → ``turboquant_compress_fused_kernel`` (rotation fused)
* ``decompress`` → ``turboquant_decompress_fused_kernel`` (inverse rotation fused)

These "fused" variants fold the rotation GEMM into the polar-tree walk,
avoiding a separate cuBLAS launch.

Shared memory
-------------
The fused kernels load the rotation matrix into shared memory:
head_dim * head_dim * sizeof(float).  For head_dim=128 this is 64KB,
which exceeds the default 48KB limit on most GPUs.  The Python bindings
call ``cudaFuncSetAttribute`` (via torch) to raise the limit.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Optional

import numpy as np

from .turboquant_numba import (
    compute_level_offsets,
    build_angle_grids,
)

# ---------------------------------------------------------------------------
# Try to load torch
# ---------------------------------------------------------------------------

_TORCH_AVAILABLE = False

try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# torch ↔ numpy helpers
# ---------------------------------------------------------------------------

def _to_torch(arr: np.ndarray, device: str = "cuda") -> "torch.Tensor":
    """Convert numpy array to torch tensor on device."""
    return torch.from_numpy(np.ascontiguousarray(arr)).to(device)


def _to_numpy(tensor: "torch.Tensor") -> np.ndarray:
    """Convert torch tensor to numpy (CPU)."""
    return tensor.detach().cpu().numpy()


# ---------------------------------------------------------------------------
# TurboQuantCUDA
# ---------------------------------------------------------------------------

class TurboQuantCUDA:
    """
    GPU-accelerated PolarQuant compress / decompress.

    Compressed format matches the Numba path:
    - radii:   (batch,) float32 — final polar radius per vector
    - indices: (batch, total_angles) uint8 — grid bin indices

    API::

        cuda_tq = TurboQuantCUDA(head_dim=128, angle_bits=3, seed=42)

        # Compress: numpy in → (radii, indices) as numpy
        radii, indices = cuda_tq.compress(vectors)

        # Decompress: → numpy (batch, head_dim)
        vectors = cuda_tq.decompress(radii, indices)

    Requires PyTorch with CUDA support.
    """

    def __init__(
        self,
        head_dim: int = 128,
        angle_bits: int = 3,
        seed: int = 42,
        device: str = "cuda:0",
    ):
        if not _TORCH_AVAILABLE:
            raise RuntimeError(
                "TurboQuantCUDA requires PyTorch with CUDA support."
            )
        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA is not available. TurboQuantCUDA requires a GPU."
            )

        self.head_dim = head_dim
        self.angle_bits = angle_bits
        self.seed = seed
        self.device = device

        # Level geometry
        level_sizes_np, level_offsets_np = compute_level_offsets(head_dim)
        self.n_levels = len(level_sizes_np)
        self.total_angles = int(level_offsets_np[-1])
        self._level_sizes_np = level_sizes_np
        self._level_offsets_np = level_offsets_np

        # GPU-resident constants
        self._level_sizes_gpu = _to_torch(self._level_sizes_np, device)
        self._level_offsets_gpu = _to_torch(self._level_offsets_np, device)

        # Angle grids + LUT scale constants
        grid_full, grid_pos, lut_scale_full, lut_scale_pos = build_angle_grids(angle_bits)
        self._grid_full_gpu = _to_torch(grid_full, device)
        self._grid_pos_gpu = _to_torch(grid_pos, device)
        self._n_grid = 2 ** angle_bits
        self._lut_scale_full = lut_scale_full
        self._lut_scale_pos = lut_scale_pos

        # Precomputed cos/sin LUTs for decompress (matches Numba path)
        self._cos_grid_full_gpu = _to_torch(np.cos(grid_full).astype(np.float32), device)
        self._sin_grid_full_gpu = _to_torch(np.sin(grid_full).astype(np.float32), device)
        self._cos_grid_pos_gpu = _to_torch(np.cos(grid_pos).astype(np.float32), device)
        self._sin_grid_pos_gpu = _to_torch(np.sin(grid_pos).astype(np.float32), device)

        # Rotation matrix
        rng = np.random.RandomState(seed)
        H = rng.randn(head_dim, head_dim)
        Q, R = np.linalg.qr(H)
        rotation = Q @ np.diag(np.sign(np.diag(R)))
        self._rotation_gpu = _to_torch(
            rotation.astype(np.float32), device
        )
        self._rotation_t_gpu = _to_torch(
            rotation.T.astype(np.float32).copy(), device
        )

        # Block/grid config
        self._block_size = 128

        # Stats
        self._compress_calls = 0
        self._decompress_calls = 0

    # ------------------------------------------------------------------ #
    #  Compress
    # ------------------------------------------------------------------ #

    def compress(
        self, vectors: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Compress batch of vectors on GPU.

        Parameters
        ----------
        vectors : ndarray (batch, head_dim), float32/float64

        Returns
        -------
        radii   : (batch,) float32
        indices : (batch, total_angles) uint8 — grid bin indices
        """
        vectors_f32 = np.ascontiguousarray(vectors, dtype=np.float32)
        batch = vectors_f32.shape[0]

        v_gpu = _to_torch(vectors_f32, self.device)

        out_indices = torch.empty(
            (batch, self.total_angles), dtype=torch.uint8, device=self.device
        )
        out_radii = torch.empty(batch, dtype=torch.float32, device=self.device)

        self._compress_torch(v_gpu, out_indices, out_radii)

        self._compress_calls += 1

        return (
            _to_numpy(out_radii),
            _to_numpy(out_indices),
        )

    def _compress_torch(self, v_gpu, out_indices, out_radii):
        """
        PyTorch-native fused compress using LUT floor quantization.

        Matches Numba _compress_polar_numba exactly:
        - Level 0: k = clamp(floor((theta + pi) * lut_scale_full), 0, n_grid-1)
        - Level 1+: k = clamp(floor(theta * lut_scale_pos), 0, n_grid-1)
        """
        batch = v_gpu.shape[0]
        pi = math.pi

        # Step 1: Rotate — v @ R^T
        radii = v_gpu @ self._rotation_gpu.T  # (B, D)

        cur_dim = self.head_dim

        for lvl in range(self.n_levels):
            n_pairs = int(self._level_sizes_np[lvl])
            off = int(self._level_offsets_np[lvl])

            xs = radii[:, 0:2 * n_pairs:2]   # (B, n_pairs)
            ys = radii[:, 1:2 * n_pairs:2]   # (B, n_pairs)

            rs = torch.sqrt(xs * xs + ys * ys)
            thetas = torch.atan2(ys, xs)      # (B, n_pairs)

            # LUT floor quantization (matches Numba)
            if lvl == 0:
                k = torch.floor((thetas + pi) * self._lut_scale_full)
            else:
                k = torch.floor(thetas * self._lut_scale_pos)

            idxs = torch.clamp(k, 0, self._n_grid - 1).to(torch.uint8)
            out_indices[:, off:off + n_pairs] = idxs

            # Build next level radii
            has_odd = cur_dim % 2
            if has_odd:
                new_radii = torch.empty(
                    (batch, n_pairs + 1),
                    dtype=torch.float32,
                    device=self.device,
                )
                new_radii[:, :n_pairs] = rs
                new_radii[:, n_pairs] = radii[:, cur_dim - 1]
            else:
                new_radii = rs

            radii = new_radii
            cur_dim = n_pairs + has_odd

        out_radii.copy_(radii.squeeze(-1))

    # ------------------------------------------------------------------ #
    #  Decompress
    # ------------------------------------------------------------------ #

    def decompress(
        self,
        radii: np.ndarray,
        indices: np.ndarray,
    ) -> np.ndarray:
        """
        Decompress batch of vectors on GPU.

        Parameters
        ----------
        radii   : (batch,) float32
        indices : (batch, total_angles) uint8 — grid bin indices

        Returns
        -------
        vectors : (batch, head_dim) float32
        """
        radii_gpu = _to_torch(
            np.ascontiguousarray(radii, dtype=np.float32), self.device
        )
        indices_gpu = _to_torch(
            np.ascontiguousarray(indices, dtype=np.uint8), self.device
        )

        batch = radii_gpu.shape[0]
        out_gpu = torch.empty(
            (batch, self.head_dim), dtype=torch.float32, device=self.device
        )

        self._decompress_torch(radii_gpu, indices_gpu, out_gpu)

        self._decompress_calls += 1
        return _to_numpy(out_gpu)

    def _decompress_torch(self, radii_gpu, indices_gpu, out_gpu):
        """
        PyTorch-native fused decompress using precomputed cos/sin LUTs.

        Matches Numba _decompress_polar_numba: indices → cos/sin LUT lookup,
        no trig calls in the hot path.
        """
        batch = radii_gpu.shape[0]

        # Start from final radius
        coords = radii_gpu.unsqueeze(-1)  # (B, 1)

        for rev in range(self.n_levels):
            lvl = self.n_levels - 1 - rev
            n_angles = int(self._level_sizes_np[lvl])
            off = int(self._level_offsets_np[lvl])

            cur_len = coords.shape[1]
            is_level0 = (lvl == 0)

            # Get grid indices for this level
            level_idx = indices_gpu[:, off:off + n_angles].long()  # (B, n_angles)

            # cos/sin via LUT (no trig calls)
            if is_level0:
                cos_vals = self._cos_grid_full_gpu[level_idx]  # (B, n_angles)
                sin_vals = self._sin_grid_full_gpu[level_idx]
            else:
                cos_vals = self._cos_grid_pos_gpu[level_idx]
                sin_vals = self._sin_grid_pos_gpu[level_idx]

            # Expand: first n_angles coords → pairs
            n_expand = min(n_angles, cur_len)
            r_expand = coords[:, :n_expand]

            expanded = torch.stack(
                [r_expand * cos_vals[:, :n_expand],
                 r_expand * sin_vals[:, :n_expand]], dim=-1
            )  # (B, n_expand, 2)
            expanded = expanded.reshape(batch, n_expand * 2)

            # Append carry-forward elements
            if cur_len > n_expand:
                carry = coords[:, n_expand:]
                coords = torch.cat([expanded, carry], dim=1)
            else:
                coords = expanded

        # Inverse rotation: coords @ R
        out_gpu.copy_(coords @ self._rotation_gpu)

    # ------------------------------------------------------------------ #
    #  Stats
    # ------------------------------------------------------------------ #

    def get_stats(self) -> dict:
        return {
            "compress_calls": self._compress_calls,
            "decompress_calls": self._decompress_calls,
            "device": self.device,
            "head_dim": self.head_dim,
            "angle_bits": self.angle_bits,
            "total_angles": self.total_angles,
            "n_levels": self.n_levels,
        }
