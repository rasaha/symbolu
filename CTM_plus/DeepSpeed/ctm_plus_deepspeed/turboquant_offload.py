"""
TurboQuant Offload Manager for DeepSpeed.

Integrates TurboQuant (PolarQuant + QJL) compression into DeepSpeed's tensor offload
pipeline. Gradient and optimizer state tensors (Adam momentum/variance) are dense
floating-point vectors — ideally suited for PolarQuant's random-rotation +
angle-quantization scheme.

Key difference from vLLM integration:
  Training tensors are arbitrary shape. We segment them into chunks of `segment_dim`
  elements and compress each chunk independently (PolarQuant requires fixed-dim input).

Compression pipeline:
  Phase 1: PolarQuant — random rotation + recursive polar coordinate quantization
            with fixed angular grids (no per-block normalization constants)
  Phase 2: QJL — 1-bit sign projection for dot-product residual correction

Expected gains (FP32 → compressed):
  3-bit config : ~4-5x compression on gradient/optimizer traffic
  4-bit config : ~3-4x compression, near-lossless quality
  Combined with CTM+ smart eviction: up to 8x effective CPU memory capacity

Reference: Google Research, ICLR 2026
  "TurboQuant: Redefining AI efficiency with extreme compression"
"""

import math
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

from .config import CTMDeepSpeedConfig
from .offload_manager import CTMOffloadManager, TensorLocation


# ---------------------------------------------------------------------------
# TurboQuantTrainingConfig
# ---------------------------------------------------------------------------

@dataclass
class TurboQuantTrainingConfig:
    """
    Configuration for TurboQuant compression of training tensors.

    Attributes:
        angle_bits: Bits for angular quantization in PolarQuant (2/3/4).
        enable_qjl: Whether to apply QJL residual correction.
        qjl_projection_dim: JL projection dimension (0 = same as segment_dim).
        segment_dim: Chunk size for segmenting large tensors.
        compress_gradients: Apply TurboQuant to gradient tensors.
        compress_optimizer_states: Apply TurboQuant to optimizer state tensors.
        min_compress_elements: Skip compression for tensors smaller than this.
        seed: Random seed for reproducible rotation matrices.
    """

    angle_bits: int = 3
    enable_qjl: bool = True
    qjl_projection_dim: int = 0
    segment_dim: int = 128
    compress_gradients: bool = True
    compress_optimizer_states: bool = True
    min_compress_elements: int = 512
    seed: int = 42

    @property
    def total_bits_per_element(self) -> float:
        """Theoretical bits per element assuming bit-packed storage.

        Formula: (1 FP32 radius + (d-1) angle indices) / d + QJL overhead.
        The radius is 32 bits (FP32), matching the training tensor dtype.
        """
        d = self.segment_dim
        polar_bits = ((d - 1) * self.angle_bits + 32) / d  # 32-bit FP32 radius
        if self.enable_qjl:
            proj_dim = self.qjl_projection_dim or d
            qjl_bits = proj_dim / d  # 1 sign bit per projected dim
            return polar_bits + qjl_bits
        return polar_bits

    @property
    def compression_ratio(self) -> float:
        """Theoretical compression ratio vs FP32, assuming bit-packed storage."""
        return 32.0 / self.total_bits_per_element

    @classmethod
    def three_bit(cls) -> "TurboQuantTrainingConfig":
        """3-bit: ~4-5x compression."""
        return cls(angle_bits=3, enable_qjl=True, segment_dim=128)

    @classmethod
    def four_bit(cls) -> "TurboQuantTrainingConfig":
        """4-bit: ~3-4x compression, near-lossless quality."""
        return cls(angle_bits=4, enable_qjl=True, segment_dim=128)

    @classmethod
    def lossless_4bit(cls) -> "TurboQuantTrainingConfig":
        """4-bit with larger segments for better quality on long vectors."""
        return cls(angle_bits=4, enable_qjl=True, segment_dim=256)


# ---------------------------------------------------------------------------
# PolarQuant: Recursive Polar Coordinate Quantization
# ---------------------------------------------------------------------------

class PolarQuant:
    """
    PolarQuant stage of TurboQuant, adapted for training tensors.

    Operates on fixed-size segments of `segment_dim` elements.
    Identical algorithm to the vLLM KV-cache variant — only the
    dimension parameter changes.

    Algorithm:
      1. Apply random rotation R → v' = R·v  (energy spread evenly)
      2. Recursively pair coordinates: (x,y) → (r, θ)
      3. Quantize θ onto a fixed circular grid
      4. Store: 1 final radius + (d-1) quantized angles

    After random rotation the angular distribution is predictable
    (approximately Beta), so a single fixed codebook works for all
    gradient/optimizer-state data — no per-block normalization needed.
    """

    def __init__(self, config: TurboQuantTrainingConfig):
        self.config = config
        d = config.segment_dim
        self.rng = np.random.RandomState(config.seed)
        self._rotation = self._generate_rotation(d)

        n_levels = 2 ** config.angle_bits
        # Level-0 grid: Gaussian coordinate pairs → angles uniform on [-π, π]
        self._angle_grid_full = (
            np.linspace(-math.pi, math.pi, n_levels, endpoint=False)
            + math.pi / n_levels
        )
        # Level-1+ grid: radius pairs (always ≥0) → angles in [0, π/2]
        self._angle_grid_pos = (
            np.linspace(0, math.pi / 2, n_levels, endpoint=False)
            + math.pi / (4 * n_levels)
        )

    def _generate_rotation(self, d: int) -> np.ndarray:
        """Generate random orthogonal rotation matrix via QR decomposition."""
        H = self.rng.randn(d, d)
        Q, R = np.linalg.qr(H)
        # Ensure det = +1 (proper rotation)
        Q = Q @ np.diag(np.sign(np.diag(R)))
        return Q

    def compress(self, vector: np.ndarray) -> dict:
        """
        Compress a single segment vector.

        Args:
            vector: 1-D array of shape (segment_dim,).

        Returns:
            dict with keys: radius, angle_indices, reconstructed, _levels.
        """
        d = len(vector)
        assert d == self.config.segment_dim

        # Step 1: Random rotation
        rotated = self._rotation @ vector

        # Step 2: Recursive polar transformation
        levels: List[np.ndarray] = []
        radii = rotated.copy()

        while len(radii) > 1:
            level_angles = []
            new_radii = []
            for i in range(0, len(radii), 2):
                if i + 1 < len(radii):
                    x, y = radii[i], radii[i + 1]
                    r = math.sqrt(x * x + y * y)
                    theta = math.atan2(y, x)
                    level_angles.append(theta)
                    new_radii.append(r)
                else:
                    new_radii.append(radii[i])
            levels.append(np.array(level_angles))
            radii = np.array(new_radii)

        final_radius = float(radii[0])

        # Step 3: Quantize angles per level using level-appropriate grids
        q_levels: List[np.ndarray] = []
        all_q_indices: List[np.ndarray] = []

        for lvl_idx, level_angles in enumerate(levels):
            if len(level_angles) == 0:
                q_levels.append(np.array([]))
                continue
            grid = self._angle_grid_full if lvl_idx == 0 else self._angle_grid_pos
            la = np.array(level_angles)
            indices = np.argmin(np.abs(la[:, None] - grid[None, :]), axis=1)
            quantized = grid[indices]
            q_levels.append(quantized)
            all_q_indices.append(indices.astype(np.uint8))

        angle_indices = (
            np.concatenate(all_q_indices) if all_q_indices
            else np.array([], dtype=np.uint8)
        )

        reconstructed = self._reconstruct(final_radius, q_levels)

        return {
            "radius": final_radius,
            "angle_indices": angle_indices,
            "reconstructed": reconstructed,
            "_levels": levels,
            "_q_levels": q_levels,
        }

    def _reconstruct(self, radius: float, q_levels: List[np.ndarray]) -> np.ndarray:
        """Reconstruct segment from quantized polar representation."""
        radii = np.array([radius])
        for level_angles in reversed(q_levels):
            new_coords = []
            angle_idx = 0
            for r in radii:
                if angle_idx < len(level_angles):
                    theta = level_angles[angle_idx]
                    angle_idx += 1
                    new_coords.append(r * math.cos(theta))
                    new_coords.append(r * math.sin(theta))
                else:
                    new_coords.append(r)
            radii = np.array(new_coords)
        return self._rotation.T @ radii

    def compress_and_reconstruct(self, vector: np.ndarray) -> np.ndarray:
        """Convenience: compress then return only the reconstructed vector."""
        return self.compress(vector)["reconstructed"]

    # -------------------------------------------------------------------------
    # Vectorised batch API (used by TurboQuantCompressor for production speed)
    # -------------------------------------------------------------------------

    def compress_batch(self, segs: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compress a batch of segments simultaneously using matrix operations.

        Processes all n_segs segments in parallel, eliminating the Python-level
        per-segment loop. The rotation and angular quantization are fully
        vectorised as 2-D numpy ops.

        Args:
            segs: shape (n_segs, segment_dim), float32.

        Returns:
            radii:      (n_segs,) float32 — final scalar radius per segment.
            all_indices:(n_segs, segment_dim-1) uint8 — angle indices, all
                        levels concatenated in compress order.
        """
        n_segs, d = segs.shape

        # Rotate all segments: (n_segs, d) @ R.T
        current = segs @ self._rotation.T   # (n_segs, d)

        level_idx = 0
        all_angle_cols: List[np.ndarray] = []

        while current.shape[1] > 1:
            n_cur = current.shape[1]
            n_pairs = n_cur // 2
            has_carry = (n_cur % 2 == 1)

            x = current[:, 0:2 * n_pairs:2]   # (n_segs, n_pairs)
            y = current[:, 1:2 * n_pairs:2]   # (n_segs, n_pairs)

            r     = np.sqrt(x * x + y * y)    # (n_segs, n_pairs)
            theta = np.arctan2(y, x)           # (n_segs, n_pairs)

            # Quantize: find nearest grid point for each angle
            grid = self._angle_grid_full if level_idx == 0 else self._angle_grid_pos
            # Broadcast: (n_segs, n_pairs, 1) vs (1, 1, n_levels)
            diffs   = np.abs(theta[:, :, None] - grid[None, None, :])
            indices = np.argmin(diffs, axis=2).astype(np.uint8)  # (n_segs, n_pairs)
            all_angle_cols.append(indices)

            if has_carry:
                current = np.concatenate([r, current[:, -1:]], axis=1)
            else:
                current = r

            level_idx += 1

        final_radii = current[:, 0].astype(np.float32)                  # (n_segs,)
        all_indices = np.concatenate(all_angle_cols, axis=1)            # (n_segs, d-1)
        return final_radii, all_indices

    def decompress_batch(
        self,
        radii: np.ndarray,
        all_indices: np.ndarray,
        angle_grid_full: np.ndarray,
        angle_grid_pos: np.ndarray,
    ) -> np.ndarray:
        """
        Reconstruct a batch of segments simultaneously.

        Args:
            radii:           (n_segs,) float32.
            all_indices:     (n_segs, segment_dim-1) uint8.
            angle_grid_full: level-0 quantisation grid.
            angle_grid_pos:  level-1+ quantisation grid.

        Returns:
            (n_segs, segment_dim) float32.
        """
        d = self.config.segment_dim

        # Pre-compute level structure (mirrors compress)
        level_sizes: List[int] = []
        carries: List[bool] = []
        cur = d
        while cur > 1:
            n_pairs = cur // 2
            level_sizes.append(n_pairs)
            carries.append(cur % 2 == 1)
            cur = n_pairs + (cur % 2)

        # Split all_indices into per-level slices
        level_indices: List[np.ndarray] = []
        start = 0
        for sz in level_sizes:
            level_indices.append(all_indices[:, start:start + sz])
            start += sz

        # Reverse through levels
        current = radii[:, None].astype(np.float32)   # (n_segs, 1)

        for rev_idx, (q_idx, has_carry) in enumerate(
                zip(reversed(level_indices), reversed(carries))):
            real_level = len(level_sizes) - 1 - rev_idx
            grid = angle_grid_full if real_level == 0 else angle_grid_pos
            angles = grid[q_idx.astype(np.intp)]   # (n_segs, n_pairs)

            n_pairs = angles.shape[1]
            r_pairs = current[:, :n_pairs]          # (n_segs, n_pairs)

            # Expand: (r, θ) → (r·cos θ, r·sin θ)
            expanded = np.empty((len(radii), 2 * n_pairs), dtype=np.float32)
            expanded[:, 0::2] = r_pairs * np.cos(angles)
            expanded[:, 1::2] = r_pairs * np.sin(angles)

            if has_carry:
                current = np.concatenate([expanded, current[:, -1:]], axis=1)
            else:
                current = expanded

        # Inverse rotation: v_rotated @ R  (equivalent to per-row R.T @ v)
        return (current @ self._rotation).astype(np.float32)


# ---------------------------------------------------------------------------
# QJL: Quantized Johnson-Lindenstrauss Residual Correction
# ---------------------------------------------------------------------------

class QJL:
    """
    QJL residual correction for TurboQuant.

    After PolarQuant a small bias remains in dot-product estimates.
    QJL corrects this using sign-projected residuals:
      1. residual e = v_original - v_polar
      2. Project:   e' = JL @ e   (Rademacher ±1/√m matrix)
      3. Store:     sign(e')      → 1 bit per projected dimension

    The asymmetric estimator (full-precision query × quantized key)
    is unbiased with distortion √(3π/2) ≈ 2.72× above information-
    theoretic minimum.
    """

    def __init__(self, config: TurboQuantTrainingConfig):
        self.config = config
        self.rng = np.random.RandomState(config.seed + 1000)

        proj_dim = config.qjl_projection_dim or config.segment_dim
        self.proj_dim = proj_dim

        # Rademacher ±1/√m JL projection matrix
        self._jl_matrix = self.rng.choice(
            [-1.0, 1.0], size=(proj_dim, config.segment_dim)
        ) / math.sqrt(proj_dim)

    def compress_residual(self, residual: np.ndarray) -> dict:
        """
        Compress residual vector to sign bits.

        Returns:
            dict with 'sign_bits' (int8 array) and 'scale' (float32).
        """
        projected = self._jl_matrix @ residual
        sign_bits = np.sign(projected).astype(np.int8)
        sign_bits[sign_bits == 0] = 1
        scale = float(np.mean(np.abs(projected)))
        return {"sign_bits": sign_bits, "scale": scale}

    def estimate_dot_product_correction(
        self, query: np.ndarray, compressed_residual: dict
    ) -> float:
        """
        Asymmetric estimator for <query, residual> from compressed residual.

        <u, v> ≈ <JL·u, sign(JL·v)> · mean(|JL·v|)
        """
        query_projected = self._jl_matrix @ query
        sign_bits = compressed_residual["sign_bits"].astype(np.float32)
        scale = compressed_residual["scale"]
        return float(np.dot(query_projected, sign_bits)) * scale

    def compress_residuals_batch(
        self, residuals: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Vectorised QJL residual compression for a batch of segments.

        Args:
            residuals: (n_segs, segment_dim) float32.

        Returns:
            sign_bits: (n_segs, proj_dim) int8, values ±1.
            scales:    (n_segs,) float32.
        """
        # Project: (n_segs, d) @ (d, proj_dim) = (n_segs, proj_dim)
        projected = residuals @ self._jl_matrix.T
        signs = np.sign(projected).astype(np.int8)
        signs[signs == 0] = 1
        scales = np.mean(np.abs(projected), axis=1).astype(np.float32)
        return signs, scales


# ---------------------------------------------------------------------------
# Bit-packing helpers
# ---------------------------------------------------------------------------

def _pack_angle_indices(indices: np.ndarray, bits: int) -> np.ndarray:
    """
    Pack a flat uint8 array of angle indices into a bit-packed byte array.

    Each index value is in [0, 2**bits - 1].  Values are packed LSB-first:
    index i occupies bits [i*bits, (i+1)*bits - 1] of the output stream.

    Pure-numpy O(n) implementation using scatter-add on uint32 output buffer.

    Args:
        indices: flat uint8 array, shape (n,).
        bits:    bits per index (2, 3, or 4).

    Returns:
        uint8 byte array of length ceil(n * bits / 8).
    """
    n = len(indices)
    if n == 0:
        return np.array([], dtype=np.uint8)

    total_bytes = (n * bits + 7) // 8
    out = np.zeros(total_bytes + 1, dtype=np.uint32)   # +1 for overflow headroom

    bit_pos   = np.arange(n, dtype=np.uint32) * bits
    byte_idx  = bit_pos >> 3                           # bit_pos // 8
    bit_off   = (bit_pos & 7).astype(np.uint32)        # bit_pos % 8

    vals = indices.astype(np.uint32)

    # Low bits land in byte_idx
    np.add.at(out, byte_idx, vals << bit_off)

    # High bits that overflow into byte_idx + 1
    overflow = bit_off + bits
    spill_mask = overflow > 8
    if spill_mask.any():
        spill_shift = 8 - bit_off[spill_mask]
        np.add.at(out, byte_idx[spill_mask] + 1, vals[spill_mask] >> spill_shift)

    return (out[:total_bytes] & 0xFF).astype(np.uint8)


def _unpack_angle_indices(packed: np.ndarray, bits: int, n: int) -> np.ndarray:
    """
    Reverse of _pack_angle_indices.

    Args:
        packed: uint8 byte array.
        bits:   bits per index.
        n:      number of original indices to extract.

    Returns:
        uint8 array of shape (n,) with values in [0, 2**bits - 1].
    """
    if n == 0:
        return np.array([], dtype=np.uint8)

    mask = np.uint32((1 << bits) - 1)

    bit_pos  = np.arange(n, dtype=np.uint32) * bits
    byte_idx = bit_pos >> 3
    bit_off  = (bit_pos & 7).astype(np.uint32)

    # Extend by one byte so byte_idx+1 is always valid
    packed_ext = np.empty(len(packed) + 1, dtype=np.uint32)
    packed_ext[:len(packed)] = packed
    packed_ext[-1] = 0

    vals = ((packed_ext[byte_idx] | (packed_ext[byte_idx + 1] << 8)) >> bit_off) & mask
    return vals.astype(np.uint8)


# ---------------------------------------------------------------------------
# CompressedTensorBuffer: per-tensor compressed storage
# ---------------------------------------------------------------------------

@dataclass
class CompressedTensorBuffer:
    """
    Stores the compressed representation of a single tensor on the CPU.

    A tensor is flattened, padded to a multiple of segment_dim, then
    all n_segments chunks are compressed together using vectorised batch
    operations.  Angle indices are bit-packed; QJL sign bits are
    packed with np.packbits.

    Fields
    ------
    original_shape : tuple
    original_dtype : str
    n_padded_elements : int
    segment_dim : int
    angle_bits : int
    radii : np.ndarray
        Shape (n_segs,), float32.  Final scalar radius per segment.
    packed_angle_bytes : np.ndarray
        Shape (packed_bytes,), uint8.  All (n_segs × (d-1)) angle indices
        bit-packed into a flat byte array (angle_bits bits per index, LSB-first).
    n_angle_indices : int
        Total number of angle indices = n_segs × (segment_dim - 1).
        Required to correctly unpack packed_angle_bytes.
    qjl_sign_bytes : Optional[np.ndarray]
        Shape (n_segs, ceil(proj_dim/8)), uint8.  QJL sign bits packed
        with np.packbits(bitorder='little').  None when QJL disabled.
    qjl_scales : Optional[np.ndarray]
        Shape (n_segs,), float32.  QJL scale per segment.
    qjl_proj_dim : int
        Projection dimension used for QJL (0 = QJL disabled).
    """

    original_shape: tuple
    original_dtype: str
    n_padded_elements: int
    segment_dim: int
    angle_bits: int

    # Core compressed data (contiguous numpy arrays — no Python lists)
    radii: np.ndarray                          # (n_segs,) float32
    packed_angle_bytes: np.ndarray             # (packed_bytes,) uint8
    n_angle_indices: int                       # n_segs * (segment_dim - 1)

    # QJL (None when disabled)
    qjl_sign_bytes: Optional[np.ndarray]       # (n_segs, ceil(proj_dim/8)) uint8
    qjl_scales: Optional[np.ndarray]           # (n_segs,) float32
    qjl_proj_dim: int = 0                      # 0 → QJL disabled

    @property
    def n_segments(self) -> int:
        return len(self.radii)

    @property
    def actual_stored_bytes(self) -> int:
        """Real heap bytes used by this buffer (bit-packed storage)."""
        b = self.radii.nbytes + self.packed_angle_bytes.nbytes
        if self.qjl_sign_bytes is not None:
            b += self.qjl_sign_bytes.nbytes + self.qjl_scales.nbytes
        return b

    @property
    def theoretical_packed_bytes(self) -> int:
        """Ideal byte count if the FP32 radius were also compressed to fewer bits.

        Currently the radius is stored as-is in float32; this property exists to
        express the algorithm's theoretical ceiling and is identical to
        actual_stored_bytes except for the radius storage.
        """
        d = self.segment_dim
        n = self.n_segments
        bits_per_seg = 32 + (d - 1) * self.angle_bits
        if self.qjl_proj_dim:
            bits_per_seg += self.qjl_proj_dim + 32
        return max(1, (bits_per_seg * n + 7) // 8)

    @property
    def compressed_bytes(self) -> int:
        """Alias for actual_stored_bytes."""
        return self.actual_stored_bytes

    @property
    def original_bytes(self) -> int:
        """Bytes in original FP32 tensor (before padding)."""
        return self.n_padded_elements * 4


# ---------------------------------------------------------------------------
# TurboQuantCompressor: handles arbitrary-shaped tensors via segmentation
# ---------------------------------------------------------------------------

class TurboQuantCompressor:
    """
    Full TurboQuant pipeline (PolarQuant + QJL) for training tensors.

    Handles arbitrary tensor shapes by:
      1. Flatten  → 1-D array
      2. Pad      → multiple of segment_dim (pad with zeros)
      3. Segment  → n_segments chunks of segment_dim each
      4. Compress → PolarQuant + optional QJL per segment
      5. Pack     → CompressedTensorBuffer

    Decompression reverses the steps: decompress → unpad → reshape.
    """

    def __init__(self, config: TurboQuantTrainingConfig):
        self.config = config
        self.polar = PolarQuant(config)
        self.qjl = QJL(config) if config.enable_qjl else None

        self.stats: Dict[str, Any] = {
            "tensors_compressed": 0,
            "tensors_decompressed": 0,
            "total_segments": 0,
            "total_original_bytes": 0,
            "total_actual_stored_bytes": 0,    # real heap usage (no bit-packing)
            "total_theoretical_packed_bytes": 0,  # if bit-packed (the compression goal)
        }

    def compress(self, data: np.ndarray) -> CompressedTensorBuffer:
        """
        Compress an arbitrary numpy array.

        Internally uses fully-vectorised batch operations (no Python loop over
        segments) and bit-packs the angle indices to angle_bits bits per index.

        Args:
            data: Any shape, any float dtype.

        Returns:
            CompressedTensorBuffer with bit-packed storage.
        """
        original_shape = data.shape
        original_dtype = str(data.dtype)
        flat = data.flatten().astype(np.float32)
        n = len(flat)

        d = self.config.segment_dim
        pad_needed = (-n) % d
        if pad_needed:
            flat = np.concatenate([flat, np.zeros(pad_needed, dtype=np.float32)])
        n_padded = len(flat)
        n_segs = n_padded // d

        # Reshape to (n_segs, d) for batch processing
        segs = flat.reshape(n_segs, d)

        # --- Vectorised PolarQuant ---
        radii, all_indices = self.polar.compress_batch(segs)
        # all_indices: (n_segs, d-1) uint8

        # Bit-pack all angle indices into a flat byte array
        flat_indices = all_indices.ravel()   # (n_segs * (d-1),) uint8
        packed_angle_bytes = _pack_angle_indices(flat_indices, self.config.angle_bits)

        # --- Vectorised QJL (optional) ---
        qjl_sign_bytes: Optional[np.ndarray] = None
        qjl_scales: Optional[np.ndarray] = None
        qjl_proj_dim = 0

        if self.qjl is not None:
            # Reconstruct for residual calculation (needed for QJL input)
            # We do a single batch reconstruct here using the already-computed indices
            recon_segs = self.polar.decompress_batch(
                radii, all_indices,
                self.polar._angle_grid_full,
                self.polar._angle_grid_pos,
            )  # (n_segs, d)
            residuals = segs - recon_segs   # (n_segs, d)
            signs, qjl_scales = self.qjl.compress_residuals_batch(residuals)
            # signs: (n_segs, proj_dim) int8, values ±1
            # Pack sign bits: convert ±1 → 0/1, then np.packbits along proj axis
            bool_signs = ((signs + 1) // 2).astype(np.uint8)  # (n_segs, proj_dim)
            qjl_sign_bytes = np.packbits(bool_signs, axis=1, bitorder="little")
            qjl_proj_dim = signs.shape[1]

        buf = CompressedTensorBuffer(
            original_shape=original_shape,
            original_dtype=original_dtype,
            n_padded_elements=n_padded,
            segment_dim=d,
            angle_bits=self.config.angle_bits,
            radii=radii,
            packed_angle_bytes=packed_angle_bytes,
            n_angle_indices=n_segs * (d - 1),
            qjl_sign_bytes=qjl_sign_bytes,
            qjl_scales=qjl_scales,
            qjl_proj_dim=qjl_proj_dim,
        )

        self.stats["tensors_compressed"] += 1
        self.stats["total_segments"] += n_segs
        self.stats["total_original_bytes"] += data.nbytes
        self.stats["total_actual_stored_bytes"] += buf.actual_stored_bytes
        self.stats["total_theoretical_packed_bytes"] += buf.theoretical_packed_bytes

        return buf

    def decompress(self, buf: CompressedTensorBuffer) -> np.ndarray:
        """
        Decompress a CompressedTensorBuffer back to a numpy array.

        Uses fully-vectorised batch reconstruction (no Python loop over segments).

        Returns:
            Array with buf.original_shape and buf.original_dtype.
        """
        d = buf.segment_dim
        n_segs = buf.n_segments

        # Unpack bit-packed angle indices → (n_segs, d-1) uint8
        flat_indices = _unpack_angle_indices(
            buf.packed_angle_bytes, buf.angle_bits, buf.n_angle_indices
        )
        all_indices = flat_indices.reshape(n_segs, d - 1)

        # Angle grids (built once)
        n_levels = 2 ** buf.angle_bits
        angle_grid_full = (
            np.linspace(-math.pi, math.pi, n_levels, endpoint=False)
            + math.pi / n_levels
        )
        angle_grid_pos = (
            np.linspace(0, math.pi / 2, n_levels, endpoint=False)
            + math.pi / (4 * n_levels)
        )

        # Vectorised batch reconstruct → (n_segs, d)
        # QJL correction is skipped on the full-decode path:
        # QJL corrects dot-product estimation bias, not reconstruction error.
        reconstructed = self.polar.decompress_batch(
            buf.radii, all_indices, angle_grid_full, angle_grid_pos
        )

        # Flatten, unpad, reshape
        flat = reconstructed.ravel()[:np.prod(buf.original_shape, dtype=int)]
        result = flat.reshape(buf.original_shape).astype(buf.original_dtype)

        self.stats["tensors_decompressed"] += 1
        return result

    def estimate_compressed_bytes(self, n_elements: int) -> int:
        """Estimate compressed size in bytes for a tensor with n_elements."""
        d = self.config.segment_dim
        n_segs = math.ceil(n_elements / d)
        bits_per_seg = 32 + (d - 1) * self.config.angle_bits
        if self.qjl is not None:
            proj_dim = self.config.qjl_projection_dim or d
            bits_per_seg += proj_dim + 32
        return max(1, (bits_per_seg * n_segs + 7) // 8)

    def get_stats(self) -> dict:
        """Return compression statistics.

        Reports two ratios:
          actual_compression_ratio     — original / actual_stored (real heap savings)
          theoretical_compression_ratio — original / theoretical_packed (bit-pack target)
        """
        orig = self.stats["total_original_bytes"]
        actual = self.stats["total_actual_stored_bytes"]
        packed = self.stats["total_theoretical_packed_bytes"]
        return {
            **self.stats,
            "actual_compression_ratio": orig / max(1, actual),
            "theoretical_compression_ratio": orig / max(1, packed),
            "config_compression_ratio": self.config.compression_ratio,
            "bits_per_element": self.config.total_bits_per_element,
        }


# ---------------------------------------------------------------------------
# TurboQuantOffloadManager: CTM+ eviction + TurboQuant compression
# ---------------------------------------------------------------------------

class TurboQuantOffloadManager:
    """
    Wraps CTMOffloadManager with TurboQuant compression for DeepSpeed.

    CTMOffloadManager decides *which* tensors to offload (smart eviction).
    TurboQuantOffloadManager decides *how* to store them (compressed vs raw).

    Eligible tensors (is_gradient=True or is_optimizer_state=True) are
    compressed with PolarQuant + QJL before being stored in CPU memory.
    All other tensors are stored as-is.

    Usage::

        # Build via factory (recommended)
        manager = TurboQuantOffloadManager.create(
            gpu_memory_bytes=40 * 1024**3,
            cpu_memory_bytes=256 * 1024**3,
        )

        # Register tensors
        manager.register_tensor(
            tensor_id="layer.0.weight.grad",
            name="layer.0.weight.grad",
            size_bytes=grad_tensor.nbytes,
            is_gradient=True,
        )

        # On tensor access (delegates to CTM for eviction decisions)
        needs_fetch, prefetch_list = manager.on_access(tensor_id)

        # When DeepSpeed offloads a tensor to CPU
        stored_bytes = manager.offload(tensor_id, grad_numpy)

        # When DeepSpeed needs the tensor back on GPU
        data = manager.fetch(tensor_id)
    """

    def __init__(
        self,
        ctm_manager: CTMOffloadManager,
        tq_config: Optional[TurboQuantTrainingConfig] = None,
    ):
        """
        Initialize with an existing CTMOffloadManager.

        Args:
            ctm_manager: CTM eviction manager (handles which tensors to move).
            tq_config: TurboQuant config; defaults to 3-bit if None.
        """
        self.ctm = ctm_manager
        self.tq_config = tq_config or TurboQuantTrainingConfig.three_bit()
        self.compressor = TurboQuantCompressor(self.tq_config)

        # CPU-side storage: tensor_id → compressed buffer or raw array
        self._compressed_store: Dict[str, CompressedTensorBuffer] = {}
        self._raw_store: Dict[str, np.ndarray] = {}
        self._is_compressed: Dict[str, bool] = {}

        self._lock = threading.RLock()
        self.stats: Dict[str, int] = {
            "offloads_compressed": 0,
            "offloads_raw": 0,
            "fetches_decompressed": 0,
            "fetches_raw": 0,
            "skipped_too_small": 0,
        }

    # -------------------------------------------------------------------------
    # Registration
    # -------------------------------------------------------------------------

    def register_tensor(
        self,
        tensor_id: str,
        name: str,
        size_bytes: int,
        is_gradient: bool = False,
        is_optimizer_state: bool = False,
        initial_location: TensorLocation = TensorLocation.GPU,
    ) -> None:
        """Register a tensor with the CTM eviction manager."""
        self.ctm.register_tensor(
            tensor_id, name, size_bytes,
            is_gradient, is_optimizer_state, initial_location,
        )

    def unregister_tensor(self, tensor_id: str) -> None:
        """Remove tensor from tracking and free CPU storage."""
        self.ctm.unregister_tensor(tensor_id)
        with self._lock:
            self._compressed_store.pop(tensor_id, None)
            self._raw_store.pop(tensor_id, None)
            self._is_compressed.pop(tensor_id, None)

    # -------------------------------------------------------------------------
    # Access tracking (delegated to CTM)
    # -------------------------------------------------------------------------

    def on_access(
        self,
        tensor_id: str,
        in_compute_graph: bool = False,
    ) -> Tuple[bool, List[str]]:
        """
        Notify CTM of tensor access for eviction scoring.

        Returns:
            (needs_fetch, prefetch_list) from CTM.
        """
        return self.ctm.on_access(tensor_id, in_compute_graph)

    # -------------------------------------------------------------------------
    # Data movement with compression
    # -------------------------------------------------------------------------

    def _should_compress(self, tensor_id: str) -> bool:
        """Return True if this tensor type is eligible for TurboQuant.

        Acquires ctm._lock to safely read TensorState flags that may be
        written concurrently by register_tensor / unregister_tensor.
        """
        with self.ctm._lock:
            state = self.ctm.tensors.get(tensor_id)
            if state is None:
                return False
            return (
                (state.is_gradient and self.tq_config.compress_gradients)
                or (state.is_optimizer_state and self.tq_config.compress_optimizer_states)
            )

    def offload(self, tensor_id: str, data: np.ndarray) -> int:
        """
        Offload tensor data to CPU, compressing if eligible.

        The caller is responsible for converting the PyTorch tensor to numpy
        (e.g. ``tensor.detach().cpu().float().numpy()``).

        Args:
            tensor_id: Must already be registered.
            data: Numpy array of tensor data.

        Returns:
            Actual bytes stored (compressed or raw).
        """
        with self._lock:
            n_elements = data.size

            if (self._should_compress(tensor_id)
                    and n_elements >= self.tq_config.min_compress_elements):
                buf = self.compressor.compress(data)
                self._compressed_store[tensor_id] = buf
                self._is_compressed[tensor_id] = True
                stored_bytes = buf.compressed_bytes
                self.stats["offloads_compressed"] += 1
            else:
                self._raw_store[tensor_id] = data.copy()
                self._is_compressed[tensor_id] = False
                stored_bytes = data.nbytes
                if n_elements < self.tq_config.min_compress_elements:
                    self.stats["skipped_too_small"] += 1
                else:
                    self.stats["offloads_raw"] += 1

            return stored_bytes

    def fetch(self, tensor_id: str) -> Optional[np.ndarray]:
        """
        Fetch and decompress tensor data from CPU storage.

        Args:
            tensor_id: ID of the tensor to retrieve.

        Returns:
            Numpy array in original shape and dtype, or None if not found.
        """
        with self._lock:
            compressed = self._is_compressed.get(tensor_id, False)

            if not compressed:
                data = self._raw_store.pop(tensor_id, None)
                self._is_compressed.pop(tensor_id, None)
                if data is not None:
                    self.stats["fetches_raw"] += 1
                return data

            buf = self._compressed_store.pop(tensor_id, None)
            self._is_compressed.pop(tensor_id, None)
            if buf is None:
                return None

            data = self.compressor.decompress(buf)
            self.stats["fetches_decompressed"] += 1
            return data

    # -------------------------------------------------------------------------
    # Passthrough wrappers for CTM operations
    # -------------------------------------------------------------------------

    def pin_tensor(self, tensor_id: str) -> None:
        """Pin tensor to prevent CTM from selecting it as an eviction victim."""
        self.ctm.pin_tensor(tensor_id)

    def unpin_tensor(self, tensor_id: str) -> None:
        """Unpin tensor to allow CTM eviction."""
        self.ctm.unpin_tensor(tensor_id)

    def set_compute_graph(self, tensor_ids: List[str], in_graph: bool) -> None:
        """Mark tensors as in/out of compute graph (protected from eviction)."""
        self.ctm.set_compute_graph(tensor_ids, in_graph)

    def get_memory_stats(self) -> dict:
        """Return CTM memory usage stats."""
        return self.ctm.get_memory_stats()

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict:
        """
        Combined statistics from CTM eviction + TurboQuant compression.

        The 'turboquant' sub-dict includes:
          - compression_ratio: theoretical ratio from config
          - effective_compression_ratio: measured ratio from actual offloads
          - bits_per_element: effective bit width after PolarQuant + QJL
          - offloads_compressed / offloads_raw: count of each path
        """
        ctm_stats = self.ctm.get_stats()
        tq_stats = self.compressor.get_stats()
        return {
            **ctm_stats,
            "turboquant": {
                **tq_stats,
                **self.stats,
                "compression_ratio": self.tq_config.compression_ratio,
                "bits_per_element": self.tq_config.total_bits_per_element,
                "angle_bits": self.tq_config.angle_bits,
                "qjl_enabled": self.tq_config.enable_qjl,
                "segment_dim": self.tq_config.segment_dim,
            },
        }

    def reset_stats(self) -> None:
        """Reset all statistics."""
        self.ctm.reset_stats()
        for k in self.stats:
            self.stats[k] = 0
        for k in self.compressor.stats:
            self.compressor.stats[k] = 0

    # -------------------------------------------------------------------------
    # Factory
    # -------------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        gpu_memory_bytes: int,
        cpu_memory_bytes: int,
        ctm_config: Optional[CTMDeepSpeedConfig] = None,
        tq_config: Optional[TurboQuantTrainingConfig] = None,
    ) -> "TurboQuantOffloadManager":
        """
        Build a CTMOffloadManager + TurboQuantOffloadManager in one call.

        Args:
            gpu_memory_bytes: Available GPU VRAM in bytes.
            cpu_memory_bytes: Available CPU RAM in bytes.
            ctm_config: CTM eviction config; defaults to for_training() preset.
            tq_config: TurboQuant config; defaults to 3-bit.

        Returns:
            Ready-to-use TurboQuantOffloadManager.

        Example::

            manager = TurboQuantOffloadManager.create(
                gpu_memory_bytes=40 * 1024**3,   # 40 GB GPU
                cpu_memory_bytes=256 * 1024**3,  # 256 GB CPU
            )
        """
        resolved_ctm_config = ctm_config or CTMDeepSpeedConfig.for_training()
        ctm = CTMOffloadManager(gpu_memory_bytes, cpu_memory_bytes, resolved_ctm_config)

        # If tq_config was not explicitly provided, derive it from the ctm_config's
        # turboquant_* fields.  This means setting turboquant_angle_bits=4 on
        # CTMDeepSpeedConfig is sufficient — no need for a separate TQ config object.
        # When enable_turboquant=False, to_turboquant_config() returns None and
        # _should_compress() will always return False (no eligible tensor types).
        resolved_tq_config = (
            tq_config
            if tq_config is not None
            else resolved_ctm_config.to_turboquant_config()
                 or TurboQuantTrainingConfig(
                     compress_gradients=False,
                     compress_optimizer_states=False,
                 )
        )
        return cls(ctm, resolved_tq_config)


# ---------------------------------------------------------------------------
# Module-level factory
# ---------------------------------------------------------------------------

def create_turboquant_offload_manager(
    gpu_memory_gb: float,
    cpu_memory_gb: float,
    tq_mode: str = "3bit",
    ctm_config: Optional[CTMDeepSpeedConfig] = None,
) -> TurboQuantOffloadManager:
    """
    Convenience factory for the most common deployment patterns.

    Args:
        gpu_memory_gb: GPU memory in gigabytes.
        cpu_memory_gb: CPU memory in gigabytes.
        tq_mode: Compression preset — "3bit" | "4bit" | "lossless_4bit".
        ctm_config: Optional CTM eviction config.

    Returns:
        Configured TurboQuantOffloadManager.

    Example::

        manager = create_turboquant_offload_manager(
            gpu_memory_gb=80,
            cpu_memory_gb=512,
            tq_mode="3bit",
        )
    """
    _presets = {
        "3bit": TurboQuantTrainingConfig.three_bit(),
        "4bit": TurboQuantTrainingConfig.four_bit(),
        "lossless_4bit": TurboQuantTrainingConfig.lossless_4bit(),
    }
    # tq_mode takes precedence; if not recognised fall back to ctm_config bridge
    explicit_tq = _presets.get(tq_mode)
    return TurboQuantOffloadManager.create(
        gpu_memory_bytes=int(gpu_memory_gb * 1024 ** 3),
        cpu_memory_bytes=int(cpu_memory_gb * 1024 ** 3),
        ctm_config=ctm_config,
        tq_config=explicit_tq,  # None → bridge from ctm_config
    )
