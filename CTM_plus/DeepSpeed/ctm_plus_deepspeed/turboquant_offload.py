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
        """Effective bits per element after compression."""
        d = self.segment_dim
        polar_bits = ((d - 1) * self.angle_bits + 16) / d
        if self.enable_qjl:
            proj_dim = self.qjl_projection_dim or d
            qjl_bits = proj_dim / d
            return polar_bits + qjl_bits
        return polar_bits

    @property
    def compression_ratio(self) -> float:
        """Compression ratio vs FP32 (32 bits per element)."""
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
        all_q_angles: List[np.ndarray] = []

        for lvl_idx, level_angles in enumerate(levels):
            if len(level_angles) == 0:
                q_levels.append(np.array([]))
                continue
            grid = self._angle_grid_full if lvl_idx == 0 else self._angle_grid_pos
            la = np.array(level_angles)
            indices = np.argmin(np.abs(la[:, None] - grid[None, :]), axis=1)
            quantized = grid[indices]
            q_levels.append(quantized)
            all_q_angles.append(quantized)
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


# ---------------------------------------------------------------------------
# CompressedTensorBuffer: per-tensor compressed storage
# ---------------------------------------------------------------------------

@dataclass
class CompressedTensorBuffer:
    """
    Stores the compressed representation of a single tensor on the CPU.

    A tensor is flattened, padded to a multiple of segment_dim, then
    split into n_segments chunks. Each chunk is stored as:
      - one FP32 radius (final magnitude after recursive polar transform)
      - (segment_dim - 1) quantized angle indices (uint8)
      - optionally: proj_dim sign bits (int8) + one FP32 scale for QJL

    Properties
    ----------
    original_shape : tuple
        Shape of the original tensor before flatten/pad.
    original_dtype : str
        NumPy dtype string of the original tensor (e.g. 'float32').
    n_padded_elements : int
        Total elements after padding to multiple of segment_dim.
    segment_dim : int
        Length of each compressed segment.
    segment_radii : List[float]
        Final radius per segment.
    segment_angle_indices : List[np.ndarray]
        Angle indices per segment, dtype uint8, shape (segment_dim-1,).
    segment_qjl_signs : Optional[List[np.ndarray]]
        QJL sign bits per segment, dtype int8. None when QJL disabled.
    segment_qjl_scales : Optional[List[float]]
        QJL scale per segment. None when QJL disabled.
    angle_bits : int
        Bits per angle index (used for byte-size estimation).
    """

    original_shape: tuple
    original_dtype: str
    n_padded_elements: int
    segment_dim: int
    segment_radii: List[float]
    segment_angle_indices: List[np.ndarray]
    segment_qjl_signs: Optional[List[np.ndarray]]
    segment_qjl_scales: Optional[List[float]]
    angle_bits: int

    @property
    def n_segments(self) -> int:
        return len(self.segment_radii)

    @property
    def compressed_bytes(self) -> int:
        """Estimate actual storage bytes."""
        d = self.segment_dim
        # Each segment: 4 bytes (FP32 radius) + ceil((d-1)*angle_bits/8) for angles
        bits_per_seg = 32 + (d - 1) * self.angle_bits
        if self.segment_qjl_signs is not None and self.segment_qjl_signs:
            proj_dim = len(self.segment_qjl_signs[0])
            bits_per_seg += proj_dim + 32  # 1 bit/dim sign + FP32 scale
        return max(1, (bits_per_seg * self.n_segments + 7) // 8)

    @property
    def original_bytes(self) -> int:
        """Bytes in original FP32 tensor."""
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
            "total_compressed_bytes": 0,
        }

    def compress(self, data: np.ndarray) -> CompressedTensorBuffer:
        """
        Compress an arbitrary numpy array.

        Args:
            data: Any shape, any float dtype.

        Returns:
            CompressedTensorBuffer holding all segment data.
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

        radii: List[float] = []
        angle_indices_list: List[np.ndarray] = []
        qjl_signs_list: Optional[List[np.ndarray]] = [] if self.qjl else None
        qjl_scales_list: Optional[List[float]] = [] if self.qjl else None

        for i in range(n_segs):
            seg = flat[i * d: (i + 1) * d]
            polar_result = self.polar.compress(seg)

            radii.append(polar_result["radius"])
            angle_indices_list.append(polar_result["angle_indices"])

            if self.qjl is not None:
                residual = seg - polar_result["reconstructed"]
                qjl_result = self.qjl.compress_residual(residual)
                qjl_signs_list.append(qjl_result["sign_bits"])
                qjl_scales_list.append(qjl_result["scale"])

        buf = CompressedTensorBuffer(
            original_shape=original_shape,
            original_dtype=original_dtype,
            n_padded_elements=n_padded,
            segment_dim=d,
            segment_radii=radii,
            segment_angle_indices=angle_indices_list,
            segment_qjl_signs=qjl_signs_list,
            segment_qjl_scales=qjl_scales_list,
            angle_bits=self.config.angle_bits,
        )

        self.stats["tensors_compressed"] += 1
        self.stats["total_segments"] += n_segs
        self.stats["total_original_bytes"] += data.nbytes
        self.stats["total_compressed_bytes"] += buf.compressed_bytes

        return buf

    def decompress(self, buf: CompressedTensorBuffer) -> np.ndarray:
        """
        Decompress a CompressedTensorBuffer back to a numpy array.

        Returns:
            Array with buf.original_shape and buf.original_dtype.
        """
        d = buf.segment_dim
        n_segs = buf.n_segments
        reconstructed_flat = np.empty(buf.n_padded_elements, dtype=np.float32)

        for i in range(n_segs):
            radius = buf.segment_radii[i]
            angle_indices = buf.segment_angle_indices[i]

            # Rebuild quantized angles from stored indices
            n_levels = 2 ** buf.angle_bits
            angle_grid_full = (
                np.linspace(-math.pi, math.pi, n_levels, endpoint=False)
                + math.pi / n_levels
            )
            angle_grid_pos = (
                np.linspace(0, math.pi / 2, n_levels, endpoint=False)
                + math.pi / (4 * n_levels)
            )

            # Reconstruct level angles: level 0 uses full grid, rest use pos grid
            # Determine level sizes from d:  level k has d >> (k+1) angles
            q_levels: List[np.ndarray] = []
            idx = 0
            cur_len = d
            while cur_len > 1:
                n_pairs = cur_len // 2
                lvl_indices = angle_indices[idx: idx + n_pairs]
                grid = angle_grid_full if len(q_levels) == 0 else angle_grid_pos
                q_levels.append(grid[lvl_indices.astype(int)])
                idx += n_pairs
                cur_len = n_pairs + (cur_len % 2)

            seg_reconstructed = self.polar._reconstruct(radius, q_levels)

            # Apply QJL correction is skipped on decompress path —
            # the reconstruction from PolarQuant alone is used (standard practice).
            # QJL is only used for asymmetric dot-product estimation, not full decode.

            reconstructed_flat[i * d: (i + 1) * d] = seg_reconstructed

        # Unpad and reshape
        n_original = 1
        for s in buf.original_shape:
            n_original *= s
        flat = reconstructed_flat[:n_original]
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
        """Return compression statistics."""
        n_c = self.stats["tensors_compressed"]
        orig = self.stats["total_original_bytes"]
        comp = self.stats["total_compressed_bytes"]
        return {
            **self.stats,
            "effective_compression_ratio": orig / max(1, comp),
            "theoretical_compression_ratio": self.config.compression_ratio,
            "bits_per_element": self.config.total_bits_per_element,
            "memory_reduction": f"{self.config.compression_ratio:.1f}x",
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
        """Return True if this tensor type is eligible for TurboQuant."""
        state = self.ctm.tensors.get(tensor_id)
        if state is None:
            return False
        if state.is_gradient and self.tq_config.compress_gradients:
            return True
        if state.is_optimizer_state and self.tq_config.compress_optimizer_states:
            return True
        return False

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
        for k in ("tensors_compressed", "tensors_decompressed", "total_segments"):
            self.compressor.stats[k] = 0
        self.compressor.stats["total_original_bytes"] = 0
        self.compressor.stats["total_compressed_bytes"] = 0

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
        ctm = CTMOffloadManager(
            gpu_memory_bytes,
            cpu_memory_bytes,
            ctm_config or CTMDeepSpeedConfig.for_training(),
        )
        return cls(ctm, tq_config or TurboQuantTrainingConfig.three_bit())


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
    tq_config = _presets.get(tq_mode, TurboQuantTrainingConfig.three_bit())
    return TurboQuantOffloadManager.create(
        gpu_memory_bytes=int(gpu_memory_gb * 1024 ** 3),
        cpu_memory_bytes=int(cpu_memory_gb * 1024 ** 3),
        ctm_config=ctm_config,
        tq_config=tq_config,
    )
