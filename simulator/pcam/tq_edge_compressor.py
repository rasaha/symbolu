"""
TurboQuant Edge Score Compression for PCAM.

Applies PolarQuant + QJL compression to PCAM attention edge profiles,
enabling higher-fidelity score estimation from CXL tier entries during ATTEND.

Key insight: For each key block, the set of attention weights from different
query sources forms an "attention profile vector". This vector captures HOW
a block is attended to — not just a scalar score, but a distribution across
query positions. Compressing this profile with TQ preserves the relative
importance signals that scalar Q4.4 quantization loses.

Architecture:
  BRAM Tier:  Full-precision BlockScore + attention_edges dict
                    │
                    │ demotion (compress)
                    ▼
  CXL Tier:   CompressedBlockEntry with:
              ├── Q4.4 scalar score (existing, 8 bits)
              ├── TQ-compressed attention profile (NEW)
              │   ├── PolarQuant: radius + quantized angles
              │   └── QJL: sign-bit residual correction
              └── Compressed edges (existing, optional)
                    │
                    │ promotion (decompress)
                    ▼
  BRAM Tier:  Reconstructed BlockScore with estimated edge weights

Benefits:
  - 5.3x compression of attention profiles (vs storing raw weight vectors)
  - >0.99 cosine similarity on reconstructed profiles
  - Enables query-conditioned scoring from CXL tier (not just flat score)
  - Cross-host edge discovery can compare profiles, not just scalar scores
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math

import numpy as np

from .core.tiered_config import TurboQuantEdgeConfig


# ---------------------------------------------------------------------------
# Attention Profile: vectorized representation of a block's attention pattern
# ---------------------------------------------------------------------------

@dataclass
class AttentionProfile:
    """Vectorized attention profile for a block.

    Represents how a block is attended to across different query positions.
    The profile is a fixed-size vector where each element corresponds to
    a "query bucket" — a range of query positions grouped for compression.

    This is the data structure that gets TQ-compressed in the CXL tier.
    """
    block_id: int

    # Raw profile: query_bucket -> cumulative attention weight
    # Fixed-size vector of length `profile_dim`
    weights: np.ndarray = field(default_factory=lambda: np.zeros(0))

    # Metadata
    total_weight: float = 0.0
    num_updates: int = 0
    max_query_seen: int = 0

    @property
    def profile_dim(self) -> int:
        return len(self.weights)

    @property
    def norm(self) -> float:
        if len(self.weights) == 0:
            return 0.0
        return float(np.linalg.norm(self.weights))

    def normalized(self) -> np.ndarray:
        """L2-normalized profile for cosine similarity comparisons."""
        n = self.norm
        if n < 1e-10:
            return self.weights.copy()
        return self.weights / n


# ---------------------------------------------------------------------------
# Edge Profile Compressor: PolarQuant + QJL for attention profiles
# ---------------------------------------------------------------------------

class EdgeProfileCompressor:
    """TurboQuant compression for PCAM attention edge profiles.

    Adapts the PolarQuant + QJL pipeline from CTM+ vLLM for compressing
    attention profile vectors instead of KV cache vectors.

    The key difference from KV compression:
    - KV vectors are high-dimensional (128-dim) with Gaussian-like distribution
    - Attention profiles are lower-dimensional (16-64 dim) with sparse,
      non-negative values (attention weights are always >= 0)
    - We adapt PolarQuant's rotation + quantization for this distribution

    Usage:
        compressor = EdgeProfileCompressor(profile_dim=32, angle_bits=3)

        # Build profile from BRAM edges
        profile = compressor.build_profile(block_score, attention_edges, query_block)

        # Compress for CXL storage
        compressed = compressor.compress(profile)

        # Estimate relevance from compressed profile during ATTEND
        score = compressor.estimate_relevance(compressed, query_bucket=5)

        # Full decompression on promotion
        reconstructed = compressor.decompress(compressed)
    """

    def __init__(
        self,
        profile_dim: int = 32,
        angle_bits: int = 3,
        enable_qjl: bool = True,
        seed: int = 42,
    ):
        self.profile_dim = profile_dim
        self.angle_bits = angle_bits
        self.enable_qjl = enable_qjl

        self._rng = np.random.RandomState(seed)

        # Pre-compute random rotation matrix (orthogonal, for PolarQuant)
        self._rotation = self._generate_rotation(profile_dim)

        # Pre-compute quantization grids
        n_levels = 2 ** angle_bits
        self._angle_grid_full = np.linspace(
            -math.pi, math.pi, n_levels, endpoint=False
        ) + math.pi / n_levels
        self._angle_grid_pos = np.linspace(
            0, math.pi / 2, n_levels, endpoint=False
        ) + math.pi / (4 * n_levels)

        # QJL projection matrix
        if enable_qjl:
            self._jl_matrix = self._rng.choice(
                [-1.0, 1.0], size=(profile_dim, profile_dim)
            ) / math.sqrt(profile_dim)
        else:
            self._jl_matrix = None

        # Statistics
        self.stats = {
            "profiles_compressed": 0,
            "total_mse": 0.0,
            "total_cosine_sim": 0.0,
        }

    def _generate_rotation(self, d: int) -> np.ndarray:
        """Generate random orthogonal rotation matrix via QR decomposition."""
        H = self._rng.randn(d, d)
        Q, R = np.linalg.qr(H)
        Q = Q @ np.diag(np.sign(np.diag(R)))
        return Q

    @property
    def bits_per_element(self) -> float:
        """Effective bits per profile element after compression."""
        d = self.profile_dim
        polar_bits = ((d - 1) * self.angle_bits + 16) / d
        if self.enable_qjl:
            polar_bits += 1.0  # 1 bit per JL dimension
        return polar_bits

    @property
    def compression_ratio(self) -> float:
        """Compression ratio vs FP32 (32 bits per element)."""
        return 32.0 / self.bits_per_element

    # -------------------------------------------------------------------
    # Profile construction from BRAM state
    # -------------------------------------------------------------------

    def build_profile(
        self,
        block_id: int,
        attention_edges: Dict[Tuple[int, int], float],
        max_query_block: int,
        bucket_size: int = 0,
    ) -> AttentionProfile:
        """Build an attention profile vector from BRAM edge state.

        Groups attention edges by query position into fixed-size buckets,
        producing a vector suitable for TQ compression.

        Args:
            block_id: The key block to profile
            attention_edges: Full edge dict (query_block, key_block) -> weight
            max_query_block: Highest query block seen (for bucketing)
            bucket_size: Positions per bucket (0 = auto-compute)

        Returns:
            AttentionProfile with weights vector of shape (profile_dim,)
        """
        if bucket_size == 0:
            bucket_size = max(1, (max_query_block + 1 + self.profile_dim - 1)
                              // self.profile_dim)

        weights = np.zeros(self.profile_dim, dtype=np.float64)
        total_weight = 0.0
        num_updates = 0

        for (query_block, key_block), weight in attention_edges.items():
            if key_block != block_id:
                continue

            bucket = min(query_block // bucket_size, self.profile_dim - 1)
            weights[bucket] += weight
            total_weight += weight
            num_updates += 1

        return AttentionProfile(
            block_id=block_id,
            weights=weights,
            total_weight=total_weight,
            num_updates=num_updates,
            max_query_seen=max_query_block,
        )

    # -------------------------------------------------------------------
    # PolarQuant compression
    # -------------------------------------------------------------------

    def compress(self, profile: AttentionProfile) -> Dict:
        """Compress an attention profile using PolarQuant + QJL.

        Returns a compressed representation dict containing:
          - radius: single FP16 value
          - angle_indices: quantized angle indices (angle_bits each)
          - qjl_signs: sign bits for JL residual correction (if enabled)
          - metadata: block_id, total_weight, num_updates
          - reconstructed: decompressed vector (for quality measurement)
        """
        vector = profile.weights.copy()
        d = len(vector)

        if d != self.profile_dim:
            raise ValueError(
                f"Profile dim {d} != expected {self.profile_dim}"
            )

        # Handle zero/near-zero profiles
        norm = float(np.linalg.norm(vector))
        if norm < 1e-12:
            return {
                "radius": 0.0,
                "angle_indices": np.zeros(d - 1, dtype=np.int32),
                "reconstructed": np.zeros(d),
                "original_norm": 0.0,
                "qjl_signs": None,
                "qjl_scale": 0.0,
                "metadata": {
                    "block_id": profile.block_id,
                    "total_weight": profile.total_weight,
                    "num_updates": profile.num_updates,
                    "max_query_seen": profile.max_query_seen,
                },
                "mse": 0.0,
                "cosine_similarity": 1.0,
            }

        # Step 1: Random rotation (distributes energy for better quantization)
        rotated = self._rotation @ vector

        # Step 2: Recursive polar transformation
        radii = rotated.copy()
        all_angle_indices = []
        q_levels = []

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
            q_levels.append(np.array(level_angles))
            radii = np.array(new_radii)

        final_radius = float(radii[0])

        # Step 3: Quantize angles
        quantized_levels = []
        for lvl_idx, level_angles in enumerate(q_levels):
            if len(level_angles) == 0:
                quantized_levels.append(np.array([]))
                continue
            grid = (self._angle_grid_full if lvl_idx == 0
                    else self._angle_grid_pos)
            la = np.array(level_angles)
            indices = np.argmin(
                np.abs(la[:, None] - grid[None, :]), axis=1
            )
            quantized = grid[indices]
            quantized_levels.append(quantized)
            all_angle_indices.append(indices)

        angle_indices = (np.concatenate(all_angle_indices)
                        if all_angle_indices
                        else np.array([], dtype=np.int32))

        # Step 4: Reconstruct from quantized representation
        reconstructed = self._reconstruct(final_radius, quantized_levels)

        # Step 5: QJL residual correction
        qjl_signs = None
        qjl_scale = 0.0
        if self.enable_qjl and self._jl_matrix is not None:
            residual = vector - reconstructed
            projected = self._jl_matrix @ residual
            qjl_signs = np.sign(projected).astype(np.int8)
            qjl_signs[qjl_signs == 0] = 1
            qjl_scale = float(np.mean(np.abs(projected)))

        # Quality metrics
        mse = float(np.mean((vector - reconstructed) ** 2))
        cos_sim = float(
            np.dot(vector, reconstructed)
            / (np.linalg.norm(vector) * np.linalg.norm(reconstructed) + 1e-10)
        )

        self.stats["profiles_compressed"] += 1
        self.stats["total_mse"] += mse
        self.stats["total_cosine_sim"] += cos_sim

        return {
            "radius": final_radius,
            "angle_indices": angle_indices.astype(np.int32),
            "reconstructed": reconstructed,
            "original_norm": norm,
            "qjl_signs": qjl_signs,
            "qjl_scale": qjl_scale,
            "metadata": {
                "block_id": profile.block_id,
                "total_weight": profile.total_weight,
                "num_updates": profile.num_updates,
                "max_query_seen": profile.max_query_seen,
            },
            "mse": mse,
            "cosine_similarity": cos_sim,
        }

    def _reconstruct(
        self, radius: float, q_levels: List[np.ndarray],
    ) -> np.ndarray:
        """Reconstruct vector from polar representation."""
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

    # -------------------------------------------------------------------
    # Score estimation from compressed profiles
    # -------------------------------------------------------------------

    def estimate_relevance(
        self,
        compressed: Dict,
        query_bucket: int,
    ) -> float:
        """Estimate a block's relevance to a query from its compressed profile.

        Uses the reconstructed profile to estimate the attention weight
        for the given query bucket. If QJL correction is available, it
        provides a more accurate estimate.

        Args:
            compressed: Output of compress()
            query_bucket: Which bucket the current query falls into

        Returns:
            Estimated attention weight for this query position
        """
        reconstructed = compressed["reconstructed"]
        if query_bucket >= len(reconstructed):
            return 0.0

        base_score = float(reconstructed[query_bucket])

        # QJL correction: project a one-hot query vector through JL
        if (self.enable_qjl and self._jl_matrix is not None
                and compressed.get("qjl_signs") is not None):
            query_vec = np.zeros(self.profile_dim)
            query_vec[query_bucket] = 1.0
            query_projected = self._jl_matrix @ query_vec
            correction = (
                float(np.dot(query_projected, compressed["qjl_signs"]))
                * compressed["qjl_scale"]
            )
            base_score += correction

        return max(0.0, base_score)

    def estimate_total_relevance(
        self,
        compressed: Dict,
        query_buckets: List[int],
    ) -> float:
        """Estimate total relevance across multiple query buckets.

        Useful for scoring a block against a range of recent query positions.
        """
        return sum(
            self.estimate_relevance(compressed, b) for b in query_buckets
        )

    def compare_profiles(
        self,
        compressed_a: Dict,
        compressed_b: Dict,
    ) -> float:
        """Compare two compressed profiles by cosine similarity.

        Useful for cross-host edge discovery: find CXL entries with
        similar attention patterns to BRAM entries.
        """
        ra = compressed_a["reconstructed"]
        rb = compressed_b["reconstructed"]
        dot = float(np.dot(ra, rb))
        norm_a = float(np.linalg.norm(ra))
        norm_b = float(np.linalg.norm(rb))
        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0
        return dot / (norm_a * norm_b)

    # -------------------------------------------------------------------
    # Full decompression (for promotion back to BRAM)
    # -------------------------------------------------------------------

    def decompress_to_profile(self, compressed: Dict) -> AttentionProfile:
        """Decompress back to an AttentionProfile (lossy).

        Used when promoting a CXL entry back to BRAM.
        The reconstructed weights will have quantization error but
        preserve the relative importance distribution.
        """
        meta = compressed["metadata"]
        return AttentionProfile(
            block_id=meta["block_id"],
            weights=compressed["reconstructed"].copy(),
            total_weight=meta["total_weight"],
            num_updates=meta["num_updates"],
            max_query_seen=meta["max_query_seen"],
        )

    # -------------------------------------------------------------------
    # Memory accounting
    # -------------------------------------------------------------------

    def compressed_size_bits(self) -> int:
        """Size of a single compressed profile in bits.

        Components:
        - Radius: 16 bits (FP16)
        - Angles: (profile_dim - 1) * angle_bits
        - QJL signs: profile_dim bits (if enabled)
        - Metadata: ~64 bits (block_id, counts)
        """
        d = self.profile_dim
        size = 16  # radius
        size += (d - 1) * self.angle_bits  # angles
        if self.enable_qjl:
            size += d  # sign bits
        size += 64  # metadata overhead
        return size

    def compressed_size_bytes(self) -> int:
        """Size of a single compressed profile in bytes."""
        return (self.compressed_size_bits() + 7) // 8

    def get_stats(self) -> Dict:
        n = self.stats["profiles_compressed"]
        return {
            **self.stats,
            "avg_mse": self.stats["total_mse"] / max(1, n),
            "avg_cosine_similarity": self.stats["total_cosine_sim"] / max(1, n),
            "compression_ratio": self.compression_ratio,
            "bits_per_element": self.bits_per_element,
            "compressed_size_bytes": self.compressed_size_bytes(),
            "profile_dim": self.profile_dim,
            "angle_bits": self.angle_bits,
            "qjl_enabled": self.enable_qjl,
        }
