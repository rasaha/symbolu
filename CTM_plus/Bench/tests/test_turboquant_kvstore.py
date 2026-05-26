"""CPU regression tests for ``kv_policy.turboquant_kvstore``.

Tier 1 of the TurboQuant ↔ vLLM integration (see the module's docstring
and ``Bench/bench_out/PHASE4_GPU_FINDINGS.md`` §14). These tests pin
three contracts:

  1. The round-trip is shape- and dtype-preserving (lossy in values,
     lossless in tensor shape).
  2. Cosine similarity meets the architecture-doc target (≥ 0.95) on
     Qwen2.5-7B-shaped real-tensor data (block_size=16, num_kv_heads=4,
     head_dim=128).
  3. Compression ratio meets the architecture-doc target (≥ 5× at
     3-bit polar, ~7× expected per the existing CPU benchmark in
     ``CTM_plus/DeepSpeed/TURBOQUANT_BENCHMARK.md``).

Skips cleanly if numpy or the cross-package ``ctm_plus_deepspeed``
import fails (lets CI run without DeepSpeed installed). The Tier 2
work-track (PyTorch-ops GPU port) will add a sibling
``test_turboquant_kvstore_gpu.py`` driving the same shapes through the
GPU path; the assertions transfer directly.
"""

from __future__ import annotations

import os

# Retirement guard bypass: TurboQuantKVStore is retired from the
# active product path (TURBOQUANT_RETIREMENT.md). These tests
# remain to reproduce the historical contracts / negative result.
os.environ.setdefault("TURBOQUANT_KV_RETIRED_BYPASS", "1")

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


@pytest.fixture
def turboquant_store():
    """Build a default-config TurboQuantKVStore or skip if either
    numpy or the cross-package TurboQuant import is missing."""
    np = pytest.importorskip("numpy")
    try:
        from kv_policy.turboquant_kvstore import TurboQuantKVStore
    except ImportError as exc:
        pytest.skip(f"kv_policy.turboquant_kvstore import failed: {exc}")
    try:
        store = TurboQuantKVStore()
    except ImportError as exc:
        pytest.skip(
            f"TurboQuant compressor not available "
            f"(install ctm-plus-deepspeed or fix PYTHONPATH): {exc}"
        )
    return store


# ----------------------------------------------------------------- #
# Qwen2.5-7B-Instruct KV layout. Numbers from the vLLM 0.7.3 model
# config: num_hidden_layers=28, num_attention_heads=28,
# num_key_value_heads=4 (GQA), head_dim=128. vLLM block_size default
# is 16. One block holds (block_size, num_kv_heads, head_dim) per K or V.
# ----------------------------------------------------------------- #
QWEN_BLOCK_SIZE = 16
QWEN_NUM_KV_HEADS = 4
QWEN_HEAD_DIM = 128


def _cosine_similarity(a, b):
    import numpy as np
    af = a.flatten().astype(np.float64)
    bf = b.flatten().astype(np.float64)
    denom = float(np.linalg.norm(af)) * float(np.linalg.norm(bf))
    if denom == 0.0:
        return 0.0
    return float(np.dot(af, bf) / denom)


def test_turboquant_kvstore_roundtrip_preserves_shape_and_dtype(turboquant_store):
    """Write a K/V block pair in fp32, read it back, assert shape and
    dtype are bit-identical. (Values are lossy by design.)"""
    import numpy as np
    rng = np.random.default_rng(42)
    k = rng.standard_normal(
        (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    ).astype(np.float32)
    v = rng.standard_normal(k.shape).astype(np.float32)

    turboquant_store.write_block(0, k, v)
    k_back, v_back = turboquant_store.read_block(0)

    assert k_back.shape == k.shape
    assert v_back.shape == v.shape
    assert k_back.dtype == k.dtype
    assert v_back.dtype == v.dtype


def test_turboquant_kvstore_cosine_similarity_meets_architecture_target(turboquant_store):
    """On Qwen-shaped synthetic K/V blocks, the architecture-doc target
    is cosine similarity ≥ 0.95 at 3-bit polar. The existing CPU
    benchmark reports ~0.965 on similar shapes; we set the gate at
    0.95 (the architecture target) and let the CPU run report higher
    in the stats."""
    import numpy as np
    rng = np.random.default_rng(137)

    cosines = []
    for block_id in range(8):
        k = rng.standard_normal(
            (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
        ).astype(np.float32)
        v = rng.standard_normal(k.shape).astype(np.float32)
        turboquant_store.write_block(block_id, k, v)
        k_back, v_back = turboquant_store.read_block(block_id)
        cosines.append(_cosine_similarity(k, k_back))
        cosines.append(_cosine_similarity(v, v_back))

    mean_cos = sum(cosines) / len(cosines)
    min_cos = min(cosines)
    assert mean_cos >= 0.95, (
        f"mean cosine {mean_cos:.4f} below architecture-doc target 0.95"
    )
    assert min_cos >= 0.93, (
        f"min cosine {min_cos:.4f} below per-block floor; "
        f"some block was significantly worse than the rest"
    )


def test_turboquant_kvstore_compression_ratio_meets_architecture_target(turboquant_store):
    """Theoretical compression ratio (source bytes / bit-packed
    compressed bytes) on Qwen-shaped data. Architecture-doc target is
    ≥ 5× at 3-bit polar; the CPU benchmark reports ~7.15× on the same
    config. We gate at 5× and let the run report higher in the stats."""
    import numpy as np
    rng = np.random.default_rng(271)

    for block_id in range(8):
        k = rng.standard_normal(
            (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
        ).astype(np.float32)
        v = rng.standard_normal(k.shape).astype(np.float32)
        turboquant_store.write_block(block_id, k, v)

    ratio = turboquant_store.compression_ratio
    assert ratio >= 5.0, (
        f"compression ratio {ratio:.2f}x below architecture-doc target 5x"
    )
    assert ratio <= 12.0, (
        f"compression ratio {ratio:.2f}x improbably high; "
        "byte-counter accounting may have regressed"
    )


def test_turboquant_kvstore_remove_block_drops_state(turboquant_store):
    """remove_block should free internal state so the store doesn't
    leak memory as vLLM evicts and re-admits blocks."""
    import numpy as np
    rng = np.random.default_rng(311)
    k = rng.standard_normal(
        (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    ).astype(np.float32)
    v = rng.standard_normal(k.shape).astype(np.float32)

    turboquant_store.write_block(42, k, v)
    assert 42 in turboquant_store
    assert len(turboquant_store) == 1

    turboquant_store.remove_block(42)
    assert 42 not in turboquant_store
    assert len(turboquant_store) == 0

    # Read on a removed block raises (avoids silent stale-data reads).
    with pytest.raises(KeyError):
        turboquant_store.read_block(42)


def test_turboquant_kvstore_stats_report_latency_per_operation(turboquant_store):
    """The streaming runner will surface ``avg_write_us`` /
    ``avg_read_us`` so Tier 1's catastrophic-by-design latency is
    visible in the bench_out artefact. Pin the contract."""
    import numpy as np
    rng = np.random.default_rng(0)
    k = rng.standard_normal(
        (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    ).astype(np.float32)
    v = rng.standard_normal(k.shape).astype(np.float32)

    turboquant_store.write_block(0, k, v)
    turboquant_store.read_block(0)

    stats = turboquant_store.get_stats()
    assert stats["writes"] == 1
    assert stats["reads"] == 1
    assert stats["avg_write_us"] > 0.0
    assert stats["avg_read_us"] > 0.0
    assert stats["compression_ratio"] >= 5.0
    assert stats["blocks_held"] == 1
    assert stats["config_angle_bits"] == 3
    assert stats["config_enable_qjl"] is True


def test_turboquant_kvstore_handles_bf16_and_fp16_dtypes(turboquant_store):
    """vLLM 0.7.3 stores KV at BF16 or FP16. The wrapper must round-trip
    those dtypes (compressor works internally on FP32; we cast on the
    way in and restore on the way out)."""
    import numpy as np
    rng = np.random.default_rng(1729)

    # numpy doesn't have native BF16; use FP16 + a separate FP32 test
    # to cover the conversion paths. The vLLM-side BF16 will reach this
    # wrapper as FP16 or FP32 after the .to('cpu') step in Tier 2.
    for dtype in (np.float16, np.float32):
        k = rng.standard_normal(
            (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
        ).astype(dtype)
        v = rng.standard_normal(k.shape).astype(dtype)

        block_id = hash(str(dtype)) & 0xFFFF
        turboquant_store.write_block(block_id, k, v)
        k_back, v_back = turboquant_store.read_block(block_id)
        assert k_back.dtype == dtype
        assert v_back.dtype == dtype
        cos = _cosine_similarity(k, k_back)
        # FP16 round-trip loses a small amount on top of polar
        # quantisation; we keep the per-dtype floor at 0.93.
        assert cos >= 0.93, (
            f"cosine {cos:.4f} on dtype {dtype} below per-dtype floor 0.93"
        )
