"""TurboQuant ↔ vLLM KV-cache integration — Tier 1 CPU prototype.

The architecture-doc (``CTM_plus/TURBOQUANT_CTXL_IMPLEMENTATION_OVERVIEW.md``)
projects an 8.8× combined-stack capacity from TurboQuant + CTM+ + CTXL.
CTM+ Phase 4 is partially validated (algorithm-quality result holds; see
``Bench/bench_out/PHASE4_GPU_FINDINGS.md`` §13.3). TurboQuant is
CPU-simulated only (``CTM_plus/DeepSpeed/TURBOQUANT_BENCHMARK.md``); its
integration into vLLM's KV-cache path has never been built. This module
is the first step of closing that gap.

**Tier 1 scope (this module):** a CPU shim that compresses K/V tensors
on the way into a side-store and decompresses on the way out. Round-trip
math reuses the existing ``CTM_plus.DeepSpeed.ctm_plus_deepspeed.turboquant_offload``
implementation (~1900 lines, ICLR 2026 polar-quant + QJL). Latency is
catastrophic by design — CPU transit on every K/V block — so Tier 1
isn't a runtime claim. Deliverables are:

  * Measured compression ratio on real-shape Qwen2.5-7B KV-block
    tensors.
  * Measured cosine similarity on the same.
  * Documented hook point for Tier 2 (the GPU PyTorch-ops port).
  * Per-call CPU latency characterised so Tier 2 has a baseline to
    beat.

**Tier 2 (next session):** re-implement TurboQuant's polar transform in
pure PyTorch ops (``torch.atan2``, ``torch.cos``, ``torch.sin``,
``torch.bucketize`` for bit-packing). Runs on GPU without CUDA. 5–10×
slower than a hand-rolled kernel but real GPU code, deployable shape.

**Tier 3 (future):** Triton / CUDA kernel. Production-ready.

**Hook point in vLLM 0.7.3** (documented here so Tier 2 has the
co-ordinates): ``vllm/attention/backends/flash_attn.py``'s
``cache_kv`` call inside ``FlashAttentionImpl.forward``. The KV cache
layout there is ``[2, num_blocks, block_size, num_kv_heads, head_dim]``
in BF16 or FP16 on GPU. Per-block tensors of shape
``(block_size, num_kv_heads, head_dim)`` are the natural unit of
compression — one independent ``TurboQuantCompressor.compress`` call
per block.

Tier 1 does NOT install a real vLLM hook. The wrapper class is exposed
to be driven by tests (and, when Tier 2 lands, by a real
``cache_kv`` monkey-patch).
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

try:
    import numpy as np  # type: ignore
except ImportError:
    np = None  # type: ignore


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
    """Tier 1 CPU compressed KV-cache side-store.

    One instance owns N compressed blocks, each holding the K and V
    tensors of one (block_size, num_kv_heads, head_dim) slot. Write
    compresses; read decompresses; remove drops.

    The class is deliberately Phase-4-agnostic: it doesn't know about
    CTM+ eviction or vLLM scheduling. It is just the compression
    transport. Wiring into vLLM's ``cache_kv`` is documented at the
    module level (deferred to Tier 2).
    """

    def __init__(
        self,
        *,
        angle_bits: int = 3,
        enable_qjl: bool = True,
        segment_dim: int = 128,
        config_factory: Optional[Any] = None,
    ) -> None:
        if np is None:
            raise ImportError(
                "TurboQuantKVStore requires numpy; install with `pip install numpy`."
            )
        TQC, TQTC, _ = _import_turboquant()
        if TQC is None:
            raise ImportError(
                "TurboQuant compressor not importable. Ensure "
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
        # Two compressors so K/V can be tuned independently in a
        # future Tier-2 ablation (they share the same config today).
        self._compressor_k = TQC(config)
        self._compressor_v = TQC(config)
        # block_id -> (k_buf, v_buf, k_shape, v_shape, original_dtype)
        self._compressed_blocks: Dict[int, Tuple[Any, Any, Tuple[int, ...], Tuple[int, ...], Any]] = {}
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

        ``k_array`` / ``v_array``: numpy arrays of arbitrary shape
        (the compressor flattens internally). Typical vLLM 0.7.3 Qwen
        layout is ``(block_size, num_kv_heads, head_dim)`` per slot.

        Stores the original shape + dtype so ``read_block`` can
        reconstruct the exact source tensor layout (lossy in values,
        lossless in shape/dtype).
        """
        t0 = time.perf_counter()
        original_dtype = k_array.dtype
        # PolarQuant operates on float32 internally; the compress call
        # casts implicitly via ``flatten().astype(np.float32)``. We make
        # it explicit here to make the CPU↔GPU transit cost (when this
        # is wired into vLLM) visible to the caller as part of the
        # ``write_us_sum`` counter.
        k_f32 = k_array.astype(np.float32, copy=False)
        v_f32 = v_array.astype(np.float32, copy=False)
        k_buf = self._compressor_k.compress(k_f32)
        v_buf = self._compressor_v.compress(v_f32)
        self._compressed_blocks[block_id] = (
            k_buf, v_buf, tuple(k_array.shape), tuple(v_array.shape),
            original_dtype,
        )
        self._stats["writes"] += 1
        self._stats["bytes_in"] += int(k_array.nbytes) + int(v_array.nbytes)
        self._stats["bytes_out_theoretical"] += (
            int(k_buf.theoretical_packed_bytes)
            + int(v_buf.theoretical_packed_bytes)
        )
        self._stats["write_us_sum"] += (time.perf_counter() - t0) * 1e6

    def read_block(self, block_id: int) -> Tuple[Any, Any]:
        """Decompress and return ``(K, V)`` numpy arrays, restored to
        the original shape and dtype.

        Raises ``KeyError`` if the block isn't held.
        """
        if block_id not in self._compressed_blocks:
            raise KeyError(f"TurboQuantKVStore: block {block_id} not held")
        t0 = time.perf_counter()
        k_buf, v_buf, k_shape, v_shape, original_dtype = (
            self._compressed_blocks[block_id]
        )
        k = self._compressor_k.decompress(k_buf).reshape(k_shape).astype(
            original_dtype, copy=False,
        )
        v = self._compressor_v.decompress(v_buf).reshape(v_shape).astype(
            original_dtype, copy=False,
        )
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

    def get_stats(self) -> Dict[str, Any]:
        s = dict(self._stats)
        s["compression_ratio"] = self.compression_ratio
        s["blocks_held"] = len(self._compressed_blocks)
        s["avg_write_us"] = self.avg_write_us
        s["avg_read_us"] = self.avg_read_us
        s["config_angle_bits"] = self._config.angle_bits
        s["config_enable_qjl"] = self._config.enable_qjl
        s["config_segment_dim"] = self._config.segment_dim
        return s


def install_turboquant_kvstore(*, model: Any = None, **config) -> TurboQuantKVStore:
    """Tier 1: builds the side-store but does NOT install a real vLLM
    cache_kv hook.

    The intended hook coordinates for Tier 2 are:

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

    For Tier 1 (this implementation), tests drive ``write_block`` /
    ``read_block`` directly with synthetic and real-shape tensors. The
    ``model`` argument is kept in the signature so the Tier 2 PR can
    swap a no-op for a real monkey-patch without a CLI break.

    Returns the constructed store so the caller can read ``.get_stats()``
    at the end of a workload.
    """
    return TurboQuantKVStore(**config)
