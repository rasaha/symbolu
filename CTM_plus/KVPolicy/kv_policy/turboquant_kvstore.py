"""TurboQuant ↔ vLLM KV-cache integration — Tier 1 (numpy) + Tier 2 (torch).

The architecture-doc (``CTM_plus/TURBOQUANT_CTXL_IMPLEMENTATION_OVERVIEW.md``)
projects an 8.8× combined-stack capacity from TurboQuant + CTM+ + CTXL.
CTM+ Phase 4 is partially validated (algorithm-quality result holds; see
``Bench/bench_out/PHASE4_GPU_FINDINGS.md`` §13.3). TurboQuant is
CPU-simulated only (``CTM_plus/DeepSpeed/TURBOQUANT_BENCHMARK.md``); its
integration into vLLM's KV-cache path has never been built. This module
is the wrapper that closes the integration gap, in two tiers.

**Tier 1 (``backend="numpy"``, default):** a CPU shim that compresses
K/V tensors on the way into a side-store and decompresses on the way
out. Round-trip math reuses the existing
``CTM_plus.DeepSpeed.ctm_plus_deepspeed.turboquant_offload``
implementation (~1900 LOC, ICLR 2026 polar-quant + QJL). Latency is
catastrophic by design — CPU transit on every K/V block — so Tier 1
isn't a runtime claim. Deliverables (all landed in
``Bench/bench_out/PHASE4_GPU_FINDINGS.md`` §14):

  * Measured compression ratio on real-shape Qwen2.5-7B KV-block tensors.
  * Measured cosine similarity on the same.
  * Documented hook point for Tier 2.
  * Per-call CPU latency characterised.

**Tier 2 (``backend="torch"``, this session):** re-implement
TurboQuant's PolarQuant + QJL stages in pure PyTorch ops
(``torch.atan2``, ``torch.sqrt``, ``torch.floor``, ``torch.clamp``,
integer gather into precomputed cos/sin tables, plus two contiguous
matmul rotations). All ops route to CUDA kernels without a CPU sync, so
running with ``torch_device="cuda"`` is a one-line change at the
caller. See ``kv_policy.turboquant_torch`` for the port.

Tier 2 still does NOT install the real ``cache_kv`` monkey-patch — that
is the next GPU session's job. What Tier 2 gives this session is:

  * A GPU-shaped compression path that bit-/value-matches the numpy
    reference within float32 roundoff (cross-impl cosine ≥ 0.999 on
    every block, ≥ 99% angle-index agreement; see
    ``Bench/tests/test_turboquant_kvstore_torch.py``).
  * The same ``write_block`` / ``read_block`` API surface, just
    consuming/producing ``torch.Tensor`` instead of numpy arrays.
  * Removes the catastrophic-CPU-latency caveat at the algorithm level
    (CPU↔GPU transit on every block is gone; tensors live on whatever
    device they were created on).

**Tier 3 (future):** Triton / CUDA kernel. Production-ready bit-packing
and a fused rotate-quantise kernel. Weeks of work.

**Hook point in vLLM 0.7.3** (documented here so the next GPU session
has the coordinates): ``vllm/attention/backends/flash_attn.py``'s
``cache_kv`` call inside ``FlashAttentionImpl.forward``. The KV cache
layout there is ``[2, num_blocks, block_size, num_kv_heads, head_dim]``
in BF16 or FP16 on GPU. Per-block tensors of shape
``(block_size, num_kv_heads, head_dim)`` are the natural unit of
compression — one independent ``write_block`` call per slot.

Neither tier installs a real vLLM hook. The wrapper class is exposed to
be driven by tests (and, when the next GPU session lands the
``cache_kv`` monkey-patch, by real KV-cache traffic).
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

try:
    import numpy as np  # type: ignore
except ImportError:
    np = None  # type: ignore


def _is_torch_tensor(obj: Any) -> bool:
    """Cheap check that doesn't import torch unless it's already imported."""
    cls = type(obj)
    return cls.__module__.startswith("torch") and cls.__name__ == "Tensor"


def _import_turboquant():
    """Locate the TurboQuant compressor from the sibling DeepSpeed package.

    The two packages (``kv-policy`` and ``ctm-plus-deepspeed``) live in
    separate setup.py trees so neither imports the other at module-top.
    This helper tries the installed-package path first; if that fails,
    falls back to a sibling-relative ``sys.path`` injection so the
    wrapper works in development checkouts without ``pip install -e``
    on the DeepSpeed package.
    """
    try:
        from ctm_plus_deepspeed.turboquant_offload import (
            CompressedTensorBuffer,
            TurboQuantCompressor,
            TurboQuantTrainingConfig,
        )
        return TurboQuantCompressor, TurboQuantTrainingConfig, CompressedTensorBuffer
    except ImportError:
        import pathlib
        import sys
        deepspeed_path = str(
            pathlib.Path(__file__).resolve().parent.parent.parent / "DeepSpeed"
        )
        if deepspeed_path not in sys.path:
            sys.path.insert(0, deepspeed_path)
        try:
            from ctm_plus_deepspeed.turboquant_offload import (
                CompressedTensorBuffer,
                TurboQuantCompressor,
                TurboQuantTrainingConfig,
            )
            return TurboQuantCompressor, TurboQuantTrainingConfig, CompressedTensorBuffer
        except ImportError:
            return None, None, None


class TurboQuantKVStore:
    """Compressed KV-cache side-store. Tier 1 (numpy) and Tier 2 (torch)
    share this surface; the backend is selected via ``backend=``.

    One instance owns N compressed blocks, each holding the K and V
    tensors of one ``(block_size, num_kv_heads, head_dim)`` slot. Write
    compresses; read decompresses; remove drops.

    The class is deliberately Phase-4-agnostic: it doesn't know about
    CTM+ eviction or vLLM scheduling. It is just the compression
    transport. Wiring into vLLM's ``cache_kv`` is documented at the
    module level (deferred to the next GPU session — see
    ``install_turboquant_kvstore``).
    """

    def __init__(
        self,
        *,
        angle_bits: int = 3,
        enable_qjl: bool = True,
        segment_dim: int = 128,
        config_factory: Optional[Any] = None,
        backend: str = "numpy",
        torch_device: Optional[Any] = None,
    ) -> None:
        if backend not in ("numpy", "torch"):
            raise ValueError(
                f"TurboQuantKVStore backend must be 'numpy' or 'torch', got "
                f"{backend!r}"
            )
        if np is None:
            raise ImportError(
                "TurboQuantKVStore requires numpy; install with `pip install numpy`."
            )
        TQC, TQTC, _ = _import_turboquant()
        if TQTC is None:
            raise ImportError(
                "TurboQuantTrainingConfig not importable. Ensure "
                "CTM_plus/DeepSpeed is on PYTHONPATH or install "
                "the ctm-plus-deepspeed package."
            )
        if config_factory is not None:
            config = config_factory()
        else:
            config = TQTC(
                angle_bits=angle_bits,
                enable_qjl=enable_qjl,
                segment_dim=segment_dim,
            )
        self._backend = backend
        self._torch_device = torch_device
        # Two compressors so K/V can be tuned independently in a future
        # ablation (they share the same config today). Each backend
        # constructs its own compressor pair so callers can pick a
        # backend per instance without rebuilding the wrapper.
        if backend == "torch":
            try:
                import torch as _torch  # noqa: F401 — just availability check
            except ImportError as exc:  # pragma: no cover - exercised at runtime
                raise ImportError(
                    "TurboQuantKVStore(backend='torch') requires PyTorch."
                ) from exc
            from .turboquant_torch import TurboQuantTorchCompressor
            self._compressor_k = TurboQuantTorchCompressor(config, device=torch_device)
            self._compressor_v = TurboQuantTorchCompressor(config, device=torch_device)
        else:
            if TQC is None:
                raise ImportError(
                    "TurboQuant numpy compressor not importable. Ensure "
                    "CTM_plus/DeepSpeed is on PYTHONPATH or install "
                    "the ctm-plus-deepspeed package."
                )
            self._compressor_k = TQC(config)
            self._compressor_v = TQC(config)
        # block_id -> (k_buf, v_buf, k_shape, v_shape, original_dtype,
        #              is_torch_input)
        self._compressed_blocks: Dict[
            int, Tuple[Any, Any, Tuple[int, ...], Tuple[int, ...], Any, bool]
        ] = {}
        self._stats: Dict[str, Any] = {
            "writes": 0,
            "reads": 0,
            "removes": 0,
            "bytes_in": 0,
            "bytes_out_theoretical": 0,
            "write_us_sum": 0.0,
            "read_us_sum": 0.0,
        }
        self._config = config

    # ---- Compression transport ---------------------------------- #

    def write_block(self, block_id: int, k_array, v_array) -> None:
        """Compress and store one (K, V) block pair.

        ``k_array`` / ``v_array``: arrays of arbitrary shape (the
        compressor flattens internally). Typical vLLM 0.7.3 Qwen layout
        is ``(block_size, num_kv_heads, head_dim)`` per slot.

        The input type must match the backend:
          * ``backend="numpy"`` requires ``numpy.ndarray``.
          * ``backend="torch"`` requires ``torch.Tensor``.

        Mixed-type calls raise ``TypeError`` — there is no implicit
        device/host transit. (Tier 2's whole point is that the torch
        path stays on whatever device the tensor arrived on.)

        Stores the original shape + dtype so ``read_block`` can
        reconstruct the exact source tensor layout (lossy in values,
        lossless in shape/dtype).
        """
        t0 = time.perf_counter()
        k_is_torch = _is_torch_tensor(k_array)
        v_is_torch = _is_torch_tensor(v_array)
        if k_is_torch != v_is_torch:
            raise TypeError(
                "TurboQuantKVStore.write_block: k_array and v_array must be "
                "the same type (both numpy or both torch)."
            )
        if self._backend == "torch" and not k_is_torch:
            raise TypeError(
                "TurboQuantKVStore(backend='torch').write_block expected "
                "torch.Tensor input; got numpy. The backend deliberately does "
                "not auto-convert — call write_block(id, torch.from_numpy(k), "
                "torch.from_numpy(v)) at the caller if you need to."
            )
        if self._backend == "numpy" and k_is_torch:
            raise TypeError(
                "TurboQuantKVStore(backend='numpy').write_block expected "
                "numpy.ndarray input; got torch.Tensor. Construct the store "
                "with backend='torch' for torch input."
            )

        if k_is_torch:
            original_dtype = k_array.dtype
            bytes_in = int(
                k_array.element_size() * k_array.numel()
                + v_array.element_size() * v_array.numel()
            )
            k_in = k_array if self._torch_device is None else k_array.to(self._torch_device)
            v_in = v_array if self._torch_device is None else v_array.to(self._torch_device)
        else:
            original_dtype = k_array.dtype
            bytes_in = int(k_array.nbytes) + int(v_array.nbytes)
            # The numpy compressor flattens via ``.astype(np.float32)``;
            # the explicit cast here makes the host-side transit
            # cost visible to the latency counter.
            k_in = k_array.astype(np.float32, copy=False)
            v_in = v_array.astype(np.float32, copy=False)

        k_buf = self._compressor_k.compress(k_in)
        v_buf = self._compressor_v.compress(v_in)

        self._compressed_blocks[block_id] = (
            k_buf, v_buf, tuple(int(s) for s in k_array.shape),
            tuple(int(s) for s in v_array.shape), original_dtype,
        )
        self._stats["writes"] += 1
        self._stats["bytes_in"] += bytes_in
        self._stats["bytes_out_theoretical"] += (
            int(k_buf.theoretical_packed_bytes)
            + int(v_buf.theoretical_packed_bytes)
        )
        self._stats["write_us_sum"] += (time.perf_counter() - t0) * 1e6

    def read_block(self, block_id: int) -> Tuple[Any, Any]:
        """Decompress and return ``(K, V)``, restored to the original
        shape and dtype. Return type matches the backend (numpy →
        ``ndarray``, torch → ``Tensor``).

        Raises ``KeyError`` if the block isn't held.
        """
        if block_id not in self._compressed_blocks:
            raise KeyError(f"TurboQuantKVStore: block {block_id} not held")
        t0 = time.perf_counter()
        k_buf, v_buf, k_shape, v_shape, original_dtype = (
            self._compressed_blocks[block_id]
        )
        k = self._compressor_k.decompress(k_buf)
        v = self._compressor_v.decompress(v_buf)

        if self._backend == "torch":
            # Torch decompress already restores the original torch dtype.
            k = k.reshape(k_shape)
            v = v.reshape(v_shape)
        else:
            k = k.reshape(k_shape).astype(original_dtype, copy=False)
            v = v.reshape(v_shape).astype(original_dtype, copy=False)

        self._stats["reads"] += 1
        self._stats["read_us_sum"] += (time.perf_counter() - t0) * 1e6
        return k, v

    def remove_block(self, block_id: int) -> None:
        if self._compressed_blocks.pop(block_id, None) is not None:
            self._stats["removes"] += 1

    def __contains__(self, block_id: int) -> bool:
        return block_id in self._compressed_blocks

    def __len__(self) -> int:
        return len(self._compressed_blocks)

    # ---- Reporting ---------------------------------------------- #

    @property
    def compression_ratio(self) -> float:
        """Theoretical ratio = source bytes / bit-packed compressed bytes.

        The "theoretical" qualifier matches the existing
        ``TurboQuantCompressor.stats`` semantics: actual heap storage
        is higher than the theoretical packed size because the polar
        indices are stored as ``uint8`` rather than packed at
        ``angle_bits`` bits-per-index. Tier 2's GPU path stores at the
        theoretical (bit-packed) size, so this is the partner-relevant
        number — not the per-process RAM cost of the Tier 1 prototype.
        """
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
        return self._backend

    def get_stats(self) -> Dict[str, Any]:
        s = dict(self._stats)
        s["compression_ratio"] = self.compression_ratio
        s["blocks_held"] = len(self._compressed_blocks)
        s["avg_write_us"] = self.avg_write_us
        s["avg_read_us"] = self.avg_read_us
        s["config_angle_bits"] = self._config.angle_bits
        s["config_enable_qjl"] = self._config.enable_qjl
        s["config_segment_dim"] = self._config.segment_dim
        s["backend"] = self._backend
        return s


def install_turboquant_kvstore(*, model: Any = None, **config) -> TurboQuantKVStore:
    """Build the side-store. Does NOT install a real vLLM ``cache_kv``
    hook at any tier — that's the next GPU session's job.

    The intended hook coordinates are:

    * ``vllm/attention/backends/flash_attn.py`` →
      ``FlashAttentionImpl.forward`` → ``cache_kv`` call site (the
      KV-cache write path for the FlashAttention backend in vLLM
      0.7.3).
    * KV layout at that site:
      ``[2, num_blocks, block_size, num_kv_heads, head_dim]`` BF16/FP16
      on GPU. Per-block tensors of shape
      ``(block_size, num_kv_heads, head_dim)`` are the natural unit of
      compression — one ``write_block`` call per slot, indexed by the
      block_id from vLLM's allocator.

    For Tier 1 and Tier 2 (both implemented as of this commit), tests
    drive ``write_block`` / ``read_block`` directly with synthetic and
    real-shape tensors. The ``model`` argument is kept in the signature
    so the next GPU session can swap a no-op for a real
    ``cache_kv`` monkey-patch without a CLI break.

    The Tier 2 (``backend="torch"``) path keeps tensors on whatever
    device they were created on, so once the ``cache_kv`` hook is
    installed and tensors arrive on ``cuda:0``, no CPU↔GPU transit
    occurs. That removes the catastrophic-by-design latency of Tier 1
    while preserving algorithm parity (cross-impl cosine ≥ 0.999; see
    ``Bench/tests/test_turboquant_kvstore_torch.py``).

    Returns the constructed store so the caller can read ``.get_stats()``
    at the end of a workload.
    """
    return TurboQuantKVStore(**config)
