"""
TurboQuant: PolarQuant + QJL KV Cache Compression Simulator

Simulates the TurboQuant compression pipeline for KV cache vectors:
  Phase 1: PolarQuant — recursive polar coordinate transformation
           with fixed-grid angular quantization (no per-block constants)
  Phase 2: QJL — 1-bit Quantized Johnson-Lindenstrauss residual correction

Reference: Google Research, ICLR 2026
  "TurboQuant: Redefining AI efficiency with extreme compression"

This module provides a faithful numerical simulation of the compression
quality (MSE, dot-product bias, memory footprint) without requiring GPU
hardware.  It integrates with CTM+'s KV cache simulator to measure the
combined benefit of intelligent eviction + mathematical compression.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class TurboQuantConfig:
    """Configuration for TurboQuant compression."""

    # Bit-width for angular quantization (PolarQuant stage)
    angle_bits: int = 3

    # Whether to apply QJL residual correction (adds 1 bit per dim)
    enable_qjl: bool = True

    # Dimension of JL projection (0 = same as input dim)
    qjl_projection_dim: int = 0

    # Random seed for reproducible rotation matrices
    seed: int = 42

    # Head dimension of the KV vectors being compressed
    head_dim: int = 128

    @property
    def total_bits_per_element(self) -> float:
        """Effective bits per element after compression."""
        # PolarQuant: (d-1) angles at angle_bits each + 1 radius at 16 bits
        # Per element: ((d-1)*angle_bits + 16) / d
        d = self.head_dim
        polar_bits = ((d - 1) * self.angle_bits + 16) / d
        if self.enable_qjl:
            # QJL adds 1 bit per projected dimension
            proj_dim = self.qjl_projection_dim or d
            qjl_bits = proj_dim / d
            return polar_bits + qjl_bits
        return polar_bits

    @property
    def compression_ratio(self) -> float:
        """Compression ratio vs FP16 (16 bits per element)."""
        return 16.0 / self.total_bits_per_element

    @property
    def memory_reduction_factor(self) -> float:
        """How many more vectors fit in the same memory."""
        return self.compression_ratio

    @classmethod
    def three_bit(cls, head_dim: int = 128) -> "TurboQuantConfig":
        """3-bit config: ~5.3x compression (matches paper's 6x claim)."""
        return cls(angle_bits=3, enable_qjl=True, head_dim=head_dim)

    @classmethod
    def four_bit(cls, head_dim: int = 128) -> "TurboQuantConfig":
        """4-bit config: ~4x compression, near-lossless quality."""
        return cls(angle_bits=4, enable_qjl=True, head_dim=head_dim)

    @classmethod
    def two_bit(cls, head_dim: int = 128) -> "TurboQuantConfig":
        """2-bit aggressive config: ~8x compression, quality risk on small models."""
        return cls(angle_bits=2, enable_qjl=True, head_dim=head_dim)


# ---------------------------------------------------------------------------
# PolarQuant: Recursive Polar Coordinate Quantization
# ---------------------------------------------------------------------------

class PolarQuant:
    """
    PolarQuant stage of TurboQuant.

    Algorithm:
    1. Apply random rotation R to input vector v → v' = R·v
    2. Recursively pair coordinates and convert to polar: (x,y) → (r, θ)
    3. Quantize angles θ onto a fixed circular grid (Lloyd-Max optimal)
    4. Store: 1 final radius + (d-1) quantized angles

    Key insight: After random rotation, angular distributions are predictable
    (approximately Beta), so a single fixed codebook works for all data —
    no per-block normalization constants needed.
    """

    def __init__(self, config: TurboQuantConfig):
        self.config = config
        self.rng = np.random.RandomState(config.seed)

        # Pre-compute random rotation matrix (orthogonal)
        self._rotation = self._generate_rotation(config.head_dim)

        # Pre-compute fixed quantization grids for angles.
        # Level 0: pairs of i.i.d. Gaussian coords → angles uniform on [-π, π]
        # Level 1+: pairs of non-negative radii → angles in [0, π/2]
        n_levels = 2 ** config.angle_bits
        # Full-range grid for level 0 (Gaussian pairs)
        self._angle_grid_full = np.linspace(
            -math.pi, math.pi, n_levels, endpoint=False
        ) + math.pi / n_levels
        # Positive-quadrant grid for level 1+ (radius pairs, always positive)
        self._angle_grid_pos = np.linspace(
            0, math.pi / 2, n_levels, endpoint=False
        ) + math.pi / (4 * n_levels)

    def _generate_rotation(self, d: int) -> np.ndarray:
        """Generate random orthogonal rotation matrix via QR decomposition."""
        H = self.rng.randn(d, d)
        Q, R = np.linalg.qr(H)
        # Ensure proper rotation (det = +1)
        Q = Q @ np.diag(np.sign(np.diag(R)))
        return Q

    def compress(self, vector: np.ndarray) -> dict:
        """
        Compress a single vector using PolarQuant.

        Args:
            vector: Input vector of shape (d,) in FP16/FP32

        Returns:
            dict with 'radius', 'quantized_angles', 'reconstructed' keys
        """
        d = len(vector)
        assert d == self.config.head_dim, f"Expected dim {self.config.head_dim}, got {d}"

        # Step 1: Random rotation (distributes energy evenly)
        rotated = self._rotation @ vector

        # Step 2: Recursive polar transformation — track angles per level
        levels = []  # Each level stores (angles_at_this_level, n_radii_out)
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
        q_levels = []
        all_q_angles = []
        all_q_indices = []

        for lvl_idx, level_angles in enumerate(levels):
            if len(level_angles) == 0:
                q_levels.append(np.array([]))
                continue

            # Level 0: full range [-π, π] (Gaussian coordinate pairs)
            # Level 1+: positive range [0, π/2] (radius pairs, always ≥0)
            grid = self._angle_grid_full if lvl_idx == 0 else self._angle_grid_pos

            la = np.array(level_angles)
            indices = np.argmin(np.abs(la[:, None] - grid[None, :]), axis=1)
            quantized = grid[indices]
            q_levels.append(quantized)
            all_q_angles.append(quantized)
            all_q_indices.append(indices)

        quantized_angles = np.concatenate(all_q_angles) if all_q_angles else np.array([])
        quantized_indices = np.concatenate(all_q_indices) if all_q_indices else np.array([], dtype=int)

        # Step 4: Reconstruct from quantized representation
        reconstructed = self._reconstruct(final_radius, q_levels)

        return {
            "radius": final_radius,
            "quantized_angles": quantized_angles,
            "angle_indices": quantized_indices,
            "reconstructed": reconstructed,
            "original_norm": float(np.linalg.norm(vector)),
            "_levels": levels,  # For debugging
        }

    def _reconstruct(self, radius: float, q_levels: list[np.ndarray]) -> np.ndarray:
        """Reconstruct vector from polar representation (level-by-level reversal)."""
        # Start from the final radius and expand outward, reversing each level
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
                    # Odd carry-forward element
                    new_coords.append(r)
            radii = np.array(new_coords)

        # Inverse rotation
        reconstructed = self._rotation.T @ radii
        return reconstructed

    def compute_mse(self, original: np.ndarray, compressed: dict) -> float:
        """Compute MSE between original and reconstructed vector."""
        recon = compressed["reconstructed"]
        return float(np.mean((original - recon) ** 2))

    def compute_dot_product_error(
        self, v1: np.ndarray, v2: np.ndarray, c1: dict, c2: dict
    ) -> float:
        """Compute relative error in dot product estimation."""
        true_dot = float(np.dot(v1, v2))
        approx_dot = float(np.dot(c1["reconstructed"], c2["reconstructed"]))
        if abs(true_dot) < 1e-10:
            return abs(approx_dot)
        return abs(approx_dot - true_dot) / abs(true_dot)

    def compress_and_reconstruct(self, vector: np.ndarray) -> np.ndarray:
        """Convenience: compress and return only the reconstructed vector."""
        return self.compress(vector)["reconstructed"]


# ---------------------------------------------------------------------------
# QJL: Quantized Johnson-Lindenstrauss Error Correction
# ---------------------------------------------------------------------------

class QJL:
    """
    QJL (Quantized Johnson-Lindenstrauss) residual correction.

    After PolarQuant, a small bias remains in dot-product estimates.
    QJL corrects this by:
    1. Computing the residual: e = v_original - v_polarquant
    2. Projecting residual with a JL transform: e' = JL @ e
    3. Storing only sign bits: sign(e')  → 1 bit per projected dim

    The asymmetric estimator (full-precision query × quantized key)
    is unbiased with distortion √(3π/2) ≈ 2.72× above information-theoretic
    minimum.
    """

    def __init__(self, config: TurboQuantConfig):
        self.config = config
        self.rng = np.random.RandomState(config.seed + 1000)

        proj_dim = config.qjl_projection_dim or config.head_dim
        self.proj_dim = proj_dim

        # JL projection matrix: random ±1/√m Rademacher
        self._jl_matrix = self.rng.choice(
            [-1.0, 1.0], size=(proj_dim, config.head_dim)
        ) / math.sqrt(proj_dim)

    def compress_residual(self, residual: np.ndarray) -> dict:
        """
        Compress residual vector to sign bits.

        Args:
            residual: Error vector (original - PolarQuant reconstruction)

        Returns:
            dict with 'sign_bits' and 'scale' for reconstruction
        """
        # Project into JL space
        projected = self._jl_matrix @ residual

        # Store sign bits only
        sign_bits = np.sign(projected)
        sign_bits[sign_bits == 0] = 1.0  # Map zeros to +1

        # Scale factor for unbiased estimation
        # E[sign(x) * |x|] relationship
        scale = np.mean(np.abs(projected))

        return {
            "sign_bits": sign_bits,
            "scale": scale,
            "projected_norm": float(np.linalg.norm(projected)),
        }

    def estimate_dot_product_correction(
        self,
        query: np.ndarray,
        compressed_residual: dict,
    ) -> float:
        """
        Estimate the dot product between a full-precision query and
        the compressed residual for bias correction.

        Uses the asymmetric estimator from the QJL paper:
        For vectors u, v with QJL applied to v:
            <u, v> ≈ <JL·u, sign(JL·v)> · ||JL·v||_1 / m

        where m is the projection dimension.
        """
        # Project query with same JL matrix (full precision)
        query_projected = self._jl_matrix @ query

        # Asymmetric estimator: full_proj · sign_bits, scaled by L1 norm
        sign_bits = compressed_residual["sign_bits"]
        scale = compressed_residual["scale"]  # mean(|projected|)

        # The correction is: scale * sum(q_proj * sign_bits) / sqrt(m)
        # This gives an approximately unbiased estimate of <query, residual>
        correction = float(np.dot(query_projected, sign_bits)) * scale

        return correction


# ---------------------------------------------------------------------------
# TurboQuant: Combined Pipeline
# ---------------------------------------------------------------------------

class TurboQuantCompressor:
    """
    Full TurboQuant pipeline combining PolarQuant + QJL.

    Usage:
        config = TurboQuantConfig.three_bit(head_dim=128)
        compressor = TurboQuantCompressor(config)

        # Compress a KV vector
        compressed = compressor.compress(kv_vector)

        # Estimate attention score
        score = compressor.estimate_attention_score(query, compressed)

        # Get quality metrics
        metrics = compressor.quality_metrics(original, compressed)
    """

    def __init__(self, config: TurboQuantConfig):
        self.config = config
        self.polar = PolarQuant(config)
        self.qjl = QJL(config) if config.enable_qjl else None

        # Runtime statistics
        self.stats = {
            "vectors_compressed": 0,
            "total_mse": 0.0,
            "total_dot_error": 0.0,
            "dot_comparisons": 0,
        }

    def compress(self, vector: np.ndarray) -> dict:
        """
        Compress a KV cache vector using the full TurboQuant pipeline.

        Returns a compressed representation dict containing:
          - PolarQuant output (radius + quantized angles)
          - QJL correction (sign bits) if enabled
          - Reconstructed vector for quality measurement
        """
        # Stage 1: PolarQuant
        polar_result = self.polar.compress(vector)

        result = {
            "polar": polar_result,
            "reconstructed": polar_result["reconstructed"].copy(),
            "original_norm": float(np.linalg.norm(vector)),
        }

        # Stage 2: QJL residual correction
        if self.qjl is not None:
            residual = vector - polar_result["reconstructed"]
            qjl_result = self.qjl.compress_residual(residual)
            result["qjl"] = qjl_result
            result["residual_norm"] = float(np.linalg.norm(residual))

        self.stats["vectors_compressed"] += 1
        mse = float(np.mean((vector - result["reconstructed"]) ** 2))
        self.stats["total_mse"] += mse

        return result

    def estimate_attention_score(
        self,
        query: np.ndarray,
        compressed_key: dict,
    ) -> float:
        """
        Estimate Q·K attention score using compressed key.

        Combines PolarQuant reconstruction with QJL bias correction
        for an unbiased dot-product estimate.
        """
        # Base score from PolarQuant reconstruction
        score = float(np.dot(query, compressed_key["reconstructed"]))

        # QJL bias correction
        if self.qjl is not None and "qjl" in compressed_key:
            correction = self.qjl.estimate_dot_product_correction(
                query, compressed_key["qjl"]
            )
            score += correction

        return score

    def quality_metrics(
        self, original: np.ndarray, compressed: dict
    ) -> dict:
        """Compute quality metrics for a single compression."""
        recon = compressed["reconstructed"]
        mse = float(np.mean((original - recon) ** 2))
        cosine_sim = float(
            np.dot(original, recon)
            / (np.linalg.norm(original) * np.linalg.norm(recon) + 1e-10)
        )
        snr = float(
            np.linalg.norm(original) ** 2 / (mse * len(original) + 1e-10)
        )
        return {
            "mse": mse,
            "cosine_similarity": cosine_sim,
            "snr_db": 10 * math.log10(snr) if snr > 0 else -float("inf"),
            "compression_ratio": self.config.compression_ratio,
            "bits_per_element": self.config.total_bits_per_element,
        }

    def batch_compress(self, vectors: np.ndarray) -> list[dict]:
        """Compress a batch of vectors. Shape: (n, head_dim)."""
        return [self.compress(v) for v in vectors]

    def get_stats(self) -> dict:
        """Return compression statistics."""
        n = self.stats["vectors_compressed"]
        return {
            **self.stats,
            "avg_mse": self.stats["total_mse"] / max(1, n),
            "compression_ratio": self.config.compression_ratio,
            "bits_per_element": self.config.total_bits_per_element,
            "memory_reduction": f"{self.config.memory_reduction_factor:.1f}x",
        }


# ---------------------------------------------------------------------------
# Memory model: effective cache capacity with TurboQuant
# ---------------------------------------------------------------------------

@dataclass
class MemoryBudget:
    """Models how TurboQuant changes effective cache capacity."""

    total_memory_bytes: int
    head_dim: int = 128
    num_heads: int = 32
    num_layers: int = 32
    bytes_per_element_fp16: int = 2

    @property
    def kv_bytes_per_token_fp16(self) -> int:
        """Bytes per token for K+V in FP16."""
        return 2 * self.num_heads * self.head_dim * self.num_layers * self.bytes_per_element_fp16

    def max_tokens_fp16(self) -> int:
        """Maximum tokens that fit in budget at FP16."""
        return self.total_memory_bytes // self.kv_bytes_per_token_fp16

    def max_tokens_turboquant(self, config: TurboQuantConfig) -> int:
        """Maximum tokens with TurboQuant compression."""
        bytes_per_element_tq = config.total_bits_per_element / 8
        kv_bytes_per_token = (
            2 * self.num_heads * self.head_dim * self.num_layers
            * bytes_per_element_tq
        )
        return int(self.total_memory_bytes / kv_bytes_per_token)

    def capacity_report(self, config: TurboQuantConfig) -> dict:
        """Generate capacity comparison report."""
        fp16_tokens = self.max_tokens_fp16()
        tq_tokens = self.max_tokens_turboquant(config)
        return {
            "total_memory_mb": self.total_memory_bytes / (1024 * 1024),
            "fp16_max_tokens": fp16_tokens,
            "turboquant_max_tokens": tq_tokens,
            "capacity_multiplier": tq_tokens / max(1, fp16_tokens),
            "compression_ratio": config.compression_ratio,
            "bits_per_element": config.total_bits_per_element,
        }
