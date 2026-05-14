"""PyTorch-ops port of TurboQuant compression (Tier 2 — CPU-correct, GPU-ready).

The numpy reference lives in
``CTM_plus/DeepSpeed/ctm_plus_deepspeed/turboquant_offload.py`` (~1900 LOC).
Tier 1 (see ``turboquant_kvstore.py`` + ``Bench/bench_out/PHASE4_GPU_FINDINGS.md``
§14) wrapped that reference in a vLLM-shaped side-store but ran the math on
CPU via numpy.

This module re-implements the *forward* compression path (PolarQuant +
QJL residual) in pure PyTorch ops. Same algorithm, same constants, same
seeded rotation matrix as the numpy reference — written so each
operation is one that maps to a CUDA kernel without a CPU sync. That
makes the module **GPU-ready** when a ``device='cuda'`` tensor is passed
in, and **CPU-correct** in this session's verification environment.

What's in scope
---------------

* ``PolarQuantTorch``: ``compress_batch`` + ``decompress_batch`` on
  ``(n_segs, segment_dim)`` torch tensors. Uses ``torch.atan2``,
  ``torch.sqrt``, ``torch.floor``, ``torch.clamp``, gather via integer
  indexing into precomputed cos/sin tables, plus two contiguous-matmul
  rotations.
* ``QJLTorch``: residual sign-projection. Pure ``matmul`` +
  ``torch.sign`` + ``torch.mean``.
* ``TurboQuantTorchCompressor``: orchestrates flatten / pad / segment /
  compress / decompress around the two stages above. Returns a
  ``CompressedTensorBufferTorch`` dataclass with the same
  ``theoretical_packed_bytes`` semantics as the numpy
  ``CompressedTensorBuffer`` (the partner-relevant compression-ratio
  number).

What's *not* in scope (deliberate)
----------------------------------

* The ``cache_kv`` monkey-patch in
  ``vllm/attention/backends/flash_attn.py``. Still a documented TODO on
  the kvstore wrapper; landing it requires a GPU pod with vLLM 0.7.3.
* Bit-packing of angle indices into ``angle_bits``-per-index byte
  streams. The numpy path uses ``_pack_angle_indices`` which is a pure
  integer scatter operation; for Tier 2 CPU correctness it is sufficient
  to expose the unpacked ``(n_segs, d-1) uint8`` index tensor and report
  ``theoretical_packed_bytes`` analytically. A Triton or CUDA kernel
  would pack on-device; the Tier 3 work-track.
* Numba parity. The numpy reference has both a numpy and a Numba
  variant of the inner loops (``_compress_polar_numba`` /
  ``_decompress_polar_numba``); they produce bit-identical output. We
  match the numpy variant.
* Real-value (Qwen2.5-7B activation) quality measurement. This module's
  verification gate is bit-/value-equivalence to the numpy reference on
  synthetic Gaussian inputs at Qwen-shape — see
  ``Bench/tests/test_turboquant_kvstore_torch.py``. Real-value cosine
  is deferred to the next GPU session that also runs Track E
  (MMLU/perplexity), per the session decision tree in
  ``Bench/bench_out/PHASE4_GPU_FINDINGS.md`` §14.5.

Determinism
-----------

The rotation matrix and the JL projection matrix are built via
``numpy.random.RandomState(seed)`` — exactly the protocol the numpy
reference uses. We materialise them in numpy and copy into a torch
tensor on the requested device. So for the same ``seed`` and
``segment_dim`` both implementations see the same rotation, and the
torch ``compress_batch`` matches the numpy ``compress_batch`` to within
matmul roundoff (~ULP of float32). On the rare angle-near-bin-boundary
case the two implementations may disagree on the discrete index — the
cross-implementation test (``test_turboquant_kvstore_torch.py``) checks
that the *reconstructed* tensor agrees to ≥ 0.999 cosine and that the
discrete index agreement is ≥ 99% of all indices.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional, Tuple

try:
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover - numpy is a hard dep of every consumer
    np = None  # type: ignore

try:
    import torch  # type: ignore
except ImportError:  # pragma: no cover - guarded at the caller
    torch = None  # type: ignore


# --------------------------------------------------------------------------- #
# Helpers — build the rotation and JL matrices from the same RNG protocol     #
# as the numpy reference, then move to torch                                  #
# --------------------------------------------------------------------------- #


def _build_rotation_np(d: int, seed: int) -> "np.ndarray":
    """Same protocol as ``PolarQuant._generate_rotation``.

    Critical: we use numpy's ``RandomState(seed)`` here, not torch's
    generator. Tier 2's verification gate is "torch path matches numpy
    path on the same input", and that gate only holds if both
    implementations see the same orthogonal rotation. We materialise the
    rotation in numpy and let torch consume it via ``torch.from_numpy``.
    """
    rng = np.random.RandomState(seed)
    H = rng.randn(d, d)
    Q, R = np.linalg.qr(H)
    Q = Q @ np.diag(np.sign(np.diag(R)))
    return np.ascontiguousarray(Q.astype(np.float32))


def _build_jl_np(proj_dim: int, d: int, seed: int) -> "np.ndarray":
    """Same protocol as ``QJL.__init__`` — Rademacher ±1/√m on float32.

    Uses ``seed + 1000`` to match the numpy reference's deliberate
    decoupling of the polar rotation seed from the QJL projection seed.
    """
    rng = np.random.RandomState(seed + 1000)
    raw = rng.choice(np.array([-1.0, 1.0], dtype=np.float32), size=(proj_dim, d))
    return (raw / np.float32(math.sqrt(proj_dim))).astype(np.float32)


# --------------------------------------------------------------------------- #
# PolarQuantTorch                                                             #
# --------------------------------------------------------------------------- #


class PolarQuantTorch:
    """PyTorch-ops port of ``PolarQuant`` (numpy reference at
    ``turboquant_offload.py`` lines 113–432).

    Operates on a 2-D tensor of shape ``(n_segs, segment_dim)``. The
    compress path emits per-segment radii + angle indices; the
    decompress path inverts. Both inner loops are vectorised across the
    ``n_segs`` axis so the kernel-count is ``O(log segment_dim)``
    independent of ``n_segs``, matching the numpy reference's
    ``compress_batch`` shape and asymptotics.
    """

    def __init__(
        self,
        segment_dim: int,
        angle_bits: int,
        seed: int = 42,
        device: Optional[Any] = None,
        dtype: Any = None,
    ) -> None:
        if torch is None:
            raise ImportError("PolarQuantTorch requires PyTorch.")
        if np is None:
            raise ImportError("PolarQuantTorch requires numpy (for RNG parity).")
        self.segment_dim = int(segment_dim)
        self.angle_bits = int(angle_bits)
        self.n_levels = 2 ** self.angle_bits
        self.device = torch.device(device) if device is not None else torch.device("cpu")
        self.dtype = dtype if dtype is not None else torch.float32

        # Quantisation scale constants, identical to the numpy reference.
        self.lut_scale_full = float(self.n_levels / (2.0 * math.pi))
        self.lut_scale_pos = float(2.0 * self.n_levels / math.pi)

        # Rotation matrix — float32 in numpy, then to torch on device.
        rot_np = _build_rotation_np(self.segment_dim, seed)
        rotation = torch.from_numpy(rot_np).to(device=self.device, dtype=self.dtype)
        self.rotation = rotation.contiguous()
        self.rotation_T = rotation.t().contiguous()

        # Precomputed grid mid-points (identical to numpy reference).
        nl = self.n_levels
        # endpoint=False linspace + half-step offset → grid mid-points.
        step_full = (2.0 * math.pi) / nl
        step_pos = (math.pi / 2.0) / nl
        grid_full = torch.arange(nl, device=self.device, dtype=self.dtype) * step_full \
            - math.pi + (math.pi / nl)
        grid_pos = torch.arange(nl, device=self.device, dtype=self.dtype) * step_pos \
            + math.pi / (4 * nl)
        self.cos_grid_full = torch.cos(grid_full).contiguous()
        self.sin_grid_full = torch.sin(grid_full).contiguous()
        self.cos_grid_pos = torch.cos(grid_pos).contiguous()
        self.sin_grid_pos = torch.sin(grid_pos).contiguous()

        # Level structure (level sizes + carry flags) — same as numpy.
        sizes = []
        carries = []
        cur = self.segment_dim
        while cur > 1:
            n_pairs = cur // 2
            sizes.append(n_pairs)
            carries.append(cur % 2 == 1)
            cur = n_pairs + (cur % 2)
        self._level_sizes: Tuple[int, ...] = tuple(sizes)
        self._level_carries: Tuple[bool, ...] = tuple(carries)
        self._n_angle_indices_per_seg = sum(sizes)
        # By construction ``segment_dim - 1`` indices total whenever
        # segment_dim is a power of two; not strictly required to be
        # power-of-two but our default 128 is.

    # --------------------------------------------------------------- #
    # Forward                                                         #
    # --------------------------------------------------------------- #

    def compress_batch(
        self, segs: "torch.Tensor"
    ) -> Tuple["torch.Tensor", "torch.Tensor"]:
        """Compress a batch of segments.

        Args:
            segs: ``(n_segs, segment_dim)`` float tensor on ``self.device``.

        Returns:
            ``(radii, all_indices)``:
              * ``radii``: ``(n_segs,)`` float — final scalar radius per segment.
              * ``all_indices``: ``(n_segs, total_indices) uint8`` — angle
                indices, concatenated in level order (level 0 first).
        """
        if segs.shape[1] != self.segment_dim:
            raise ValueError(
                f"PolarQuantTorch.compress_batch expected segment_dim "
                f"{self.segment_dim}, got {segs.shape[1]}"
            )

        rotated = segs.to(self.dtype) @ self.rotation_T  # (n_segs, d)
        current = rotated
        level_idx = 0
        index_cols = []

        while current.shape[1] > 1:
            n_cur = current.shape[1]
            n_pairs = n_cur // 2
            has_carry = (n_cur % 2 == 1)

            x = current[:, 0:2 * n_pairs:2]
            y = current[:, 1:2 * n_pairs:2]
            r = torch.sqrt(x * x + y * y)
            theta = torch.atan2(y, x)

            if level_idx == 0:
                k = torch.floor((theta + math.pi) * self.lut_scale_full)
            else:
                k = torch.floor(theta * self.lut_scale_pos)
            indices = torch.clamp(k, min=0, max=self.n_levels - 1).to(torch.uint8)
            index_cols.append(indices)

            if has_carry:
                current = torch.cat([r, current[:, -1:]], dim=1)
            else:
                current = r
            level_idx += 1

        final_radii = current[:, 0].contiguous()
        all_indices = torch.cat(index_cols, dim=1).contiguous()
        return final_radii, all_indices

    # --------------------------------------------------------------- #
    # Inverse                                                         #
    # --------------------------------------------------------------- #

    def decompress_batch(
        self, radii: "torch.Tensor", all_indices: "torch.Tensor"
    ) -> "torch.Tensor":
        """Reconstruct segments from radii + angle indices.

        Args:
            radii: ``(n_segs,)`` float on ``self.device``.
            all_indices: ``(n_segs, sum(level_sizes)) uint8`` on ``self.device``.

        Returns:
            ``(n_segs, segment_dim)`` float — the polar reconstruction
            (lossy in values, exact in shape).
        """
        # Split concatenated indices back into per-level slices.
        level_indices = []
        start = 0
        for sz in self._level_sizes:
            level_indices.append(all_indices[:, start:start + sz])
            start += sz

        # Build the reconstruction by walking levels in reverse (deepest
        # → shallowest), exactly as the numpy reference does.
        current = radii.unsqueeze(1).to(self.dtype)  # (n_segs, 1)
        n_levels = len(self._level_sizes)
        for rev_idx in range(n_levels):
            real_level = n_levels - 1 - rev_idx
            q_idx = level_indices[real_level].to(torch.long)
            has_carry = self._level_carries[real_level]

            if real_level == 0:
                cos_vals = self.cos_grid_full[q_idx]
                sin_vals = self.sin_grid_full[q_idx]
            else:
                cos_vals = self.cos_grid_pos[q_idx]
                sin_vals = self.sin_grid_pos[q_idx]

            n_pairs = cos_vals.shape[1]
            r_pairs = current[:, :n_pairs]

            expanded = torch.empty(
                (current.shape[0], 2 * n_pairs),
                dtype=self.dtype,
                device=self.device,
            )
            expanded[:, 0::2] = r_pairs * cos_vals
            expanded[:, 1::2] = r_pairs * sin_vals

            if has_carry:
                current = torch.cat([expanded, current[:, -1:]], dim=1)
            else:
                current = expanded

        # Inverse rotation — same matmul shape as the numpy reference's
        # ``reconstructed @ self._rotation``.
        return (current @ self.rotation).to(self.dtype)


# --------------------------------------------------------------------------- #
# QJLTorch — residual sign-projection                                         #
# --------------------------------------------------------------------------- #


class QJLTorch:
    """PyTorch-ops port of ``QJL`` (numpy reference at lines 438–514)."""

    def __init__(
        self,
        segment_dim: int,
        proj_dim: int,
        seed: int = 42,
        device: Optional[Any] = None,
        dtype: Any = None,
    ) -> None:
        if torch is None:
            raise ImportError("QJLTorch requires PyTorch.")
        if np is None:
            raise ImportError("QJLTorch requires numpy (for RNG parity).")
        self.segment_dim = int(segment_dim)
        self.proj_dim = int(proj_dim)
        self.device = torch.device(device) if device is not None else torch.device("cpu")
        self.dtype = dtype if dtype is not None else torch.float32

        jl_np = _build_jl_np(self.proj_dim, self.segment_dim, seed)
        jl = torch.from_numpy(jl_np).to(device=self.device, dtype=self.dtype)
        self.jl = jl.contiguous()
        self.jl_T = jl.t().contiguous()

    def compress_residuals_batch(
        self, residuals: "torch.Tensor"
    ) -> Tuple["torch.Tensor", "torch.Tensor"]:
        """Project residuals, return ``(signs, scales)``.

        ``signs``: ``(n_segs, proj_dim) int8`` of values ±1 (zeros
        mapped to +1, matching the numpy reference).
        ``scales``: ``(n_segs,) float`` — mean(|projected|).
        """
        projected = residuals.to(self.dtype) @ self.jl_T  # (n_segs, proj_dim)
        signs = torch.sign(projected)
        signs = torch.where(signs == 0, torch.ones_like(signs), signs).to(torch.int8)
        scales = torch.mean(torch.abs(projected), dim=1)
        return signs, scales


# --------------------------------------------------------------------------- #
# Compressed-buffer dataclass + top-level compressor                          #
# --------------------------------------------------------------------------- #


@dataclass
class CompressedTensorBufferTorch:
    """Torch-tensor analogue of the numpy ``CompressedTensorBuffer``.

    Carries the same minimum information: the original shape & dtype
    (so ``decompress`` can restore both losslessly), per-segment radii,
    per-segment angle indices (unpacked; the partner-relevant
    compression ratio still applies via the analytical
    ``theoretical_packed_bytes`` formula), and the optional QJL state.
    """

    original_shape: Tuple[int, ...]
    original_dtype: str
    n_padded_elements: int
    segment_dim: int
    angle_bits: int

    radii: "torch.Tensor"               # (n_segs,) float
    all_indices: "torch.Tensor"         # (n_segs, n_angle_indices_per_seg) uint8

    # QJL state (None when disabled)
    qjl_signs: Optional["torch.Tensor"] = None    # (n_segs, proj_dim) int8
    qjl_scales: Optional["torch.Tensor"] = None   # (n_segs,) float
    qjl_proj_dim: int = 0

    @property
    def n_segments(self) -> int:
        return int(self.radii.shape[0])

    @property
    def theoretical_packed_bytes(self) -> int:
        """Same formula as the numpy ``CompressedTensorBuffer`` so the
        kvstore's ``compression_ratio`` property is backend-agnostic."""
        d = self.segment_dim
        n = self.n_segments
        bits_per_seg = 32 + (d - 1) * self.angle_bits
        if self.qjl_proj_dim:
            bits_per_seg += self.qjl_proj_dim + 32
        return max(1, (bits_per_seg * n + 7) // 8)

    @property
    def original_bytes(self) -> int:
        return self.n_padded_elements * 4


_TORCH_DTYPE_FROM_STR = None  # populated lazily once torch is in scope


def _torch_dtype_from_str(name: str) -> Any:
    global _TORCH_DTYPE_FROM_STR
    if _TORCH_DTYPE_FROM_STR is None:
        _TORCH_DTYPE_FROM_STR = {
            "torch.float16": torch.float16,
            "torch.float32": torch.float32,
            "torch.float64": torch.float64,
            "torch.bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
            "float64": torch.float64,
            "bfloat16": torch.bfloat16,
        }
    if name not in _TORCH_DTYPE_FROM_STR:
        raise KeyError(f"Unsupported torch dtype string: {name!r}")
    return _TORCH_DTYPE_FROM_STR[name]


class TurboQuantTorchCompressor:
    """Torch-tensor analogue of ``TurboQuantCompressor`` (numpy reference
    at lines 740–905).

    Public surface mirrors the numpy class:
      * ``compress(tensor)`` → ``CompressedTensorBufferTorch``
      * ``decompress(buf)``  → torch.Tensor of the original shape and dtype
    """

    def __init__(self, config: Any, device: Optional[Any] = None) -> None:
        if torch is None:
            raise ImportError("TurboQuantTorchCompressor requires PyTorch.")
        self.config = config
        self.device = torch.device(device) if device is not None else torch.device("cpu")
        self.polar = PolarQuantTorch(
            segment_dim=config.segment_dim,
            angle_bits=config.angle_bits,
            seed=config.seed,
            device=self.device,
        )
        proj_dim = config.qjl_projection_dim or config.segment_dim
        self.qjl = (
            QJLTorch(
                segment_dim=config.segment_dim,
                proj_dim=proj_dim,
                seed=config.seed,
                device=self.device,
            )
            if config.enable_qjl
            else None
        )

    def compress(self, data: "torch.Tensor") -> CompressedTensorBufferTorch:
        """Compress an arbitrary-shape torch tensor.

        Mirrors the numpy reference: flatten → pad → segment → compress.
        Returns a ``CompressedTensorBufferTorch`` carrying everything
        required to round-trip.
        """
        if not torch.is_tensor(data):
            raise TypeError(
                f"TurboQuantTorchCompressor.compress expected torch.Tensor, "
                f"got {type(data).__name__}"
            )
        original_shape = tuple(int(s) for s in data.shape)
        original_dtype_str = str(data.dtype)

        flat = data.flatten().to(device=self.device, dtype=torch.float32)
        n = int(flat.shape[0])
        d = self.config.segment_dim
        pad_needed = (-n) % d
        if pad_needed:
            pad = torch.zeros(pad_needed, dtype=torch.float32, device=self.device)
            flat = torch.cat([flat, pad])
        n_padded = int(flat.shape[0])
        n_segs = n_padded // d

        segs = flat.reshape(n_segs, d)
        radii, all_indices = self.polar.compress_batch(segs)

        qjl_signs = None
        qjl_scales = None
        qjl_proj_dim = 0
        if self.qjl is not None:
            recon = self.polar.decompress_batch(radii, all_indices)
            residuals = segs - recon
            qjl_signs, qjl_scales = self.qjl.compress_residuals_batch(residuals)
            qjl_proj_dim = int(qjl_signs.shape[1])

        return CompressedTensorBufferTorch(
            original_shape=original_shape,
            original_dtype=original_dtype_str,
            n_padded_elements=n_padded,
            segment_dim=d,
            angle_bits=self.config.angle_bits,
            radii=radii,
            all_indices=all_indices,
            qjl_signs=qjl_signs,
            qjl_scales=qjl_scales,
            qjl_proj_dim=qjl_proj_dim,
        )

    def decompress(self, buf: CompressedTensorBufferTorch) -> "torch.Tensor":
        """Round-trip ``buf`` back to a torch tensor of the original
        shape and dtype. QJL is intentionally not applied on the
        reconstruction path — see the numpy reference's lines 862–865:
        QJL corrects dot-product bias, not reconstruction error.
        """
        n_segs = buf.n_segments
        d = buf.segment_dim
        reconstructed = self.polar.decompress_batch(buf.radii, buf.all_indices)
        flat = reconstructed.flatten()

        prod = 1
        for s in buf.original_shape:
            prod *= int(s)
        flat = flat[:prod]

        torch_dtype = _torch_dtype_from_str(buf.original_dtype)
        return flat.reshape(buf.original_shape).to(torch_dtype)
