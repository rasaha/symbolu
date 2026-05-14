"""CPU regression tests for ``kv_policy.turboquant_kvstore`` with the
Tier 2 ``backend="torch"`` path.

Tier 2 of the TurboQuant ↔ vLLM integration (see the module's docstring
and ``Bench/bench_out/PHASE4_GPU_FINDINGS.md`` §14). These tests pin
four contracts:

  1. The torch-backend round-trip is shape- and dtype-preserving (lossy
     in values, lossless in tensor shape / dtype), matching the Tier 1
     numpy contract.
  2. Cosine similarity meets the architecture-doc target (≥ 0.95) on
     Qwen2.5-7B-shaped real-shape Gaussian data.
  3. Compression ratio matches the Tier 1 number on FP32 Gaussian
     (≥ 5×, ~7.15× expected per ``§14.2``).
  4. **Cross-implementation agreement**: the torch path agrees with the
     numpy reference on the same input within float32 roundoff. Two
     gates:
       * Reconstructed-tensor cosine ≥ 0.999 on every block.
       * The two implementations may disagree on the discrete angle
         index at points within ULP of a bin boundary; we require at
         least 99% of indices to match exactly.

Real-value (Qwen2.5-7B activation) quality measurement is **deferred to
the next GPU session** that runs Track E (MMLU/perplexity) — the
verification cell that turns the synthetic-Gaussian cosine into a
generation-quality claim. See ``Bench/bench_out/PHASE4_GPU_FINDINGS.md``
§14.5.

Skips cleanly if PyTorch or the cross-package ``ctm_plus_deepspeed``
import is missing.
"""

from __future__ import annotations

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


# Qwen2.5-7B-Instruct KV layout (matches the Tier 1 test file).
QWEN_BLOCK_SIZE = 16
QWEN_NUM_KV_HEADS = 4
QWEN_HEAD_DIM = 128


@pytest.fixture
def torch_module():
    return pytest.importorskip("torch")


@pytest.fixture
def turboquant_store_torch(torch_module):
    """Build a default-config TurboQuantKVStore with backend='torch' or
    skip if either torch or the cross-package TurboQuant import is
    missing."""
    pytest.importorskip("numpy")
    try:
        from kv_policy.turboquant_kvstore import TurboQuantKVStore
    except ImportError as exc:
        pytest.skip(f"kv_policy.turboquant_kvstore import failed: {exc}")
    try:
        store = TurboQuantKVStore(backend="torch")
    except ImportError as exc:
        pytest.skip(
            f"TurboQuant compressor not available "
            f"(install ctm-plus-deepspeed or fix PYTHONPATH): {exc}"
        )
    return store


def _cosine_similarity_torch(a, b):
    """Cosine in float64 to avoid spurious FP32-roundoff failures on the
    ≥0.999 gate."""
    import torch
    af = a.flatten().to(torch.float64)
    bf = b.flatten().to(torch.float64)
    denom = torch.norm(af).item() * torch.norm(bf).item()
    if denom == 0.0:
        return 0.0
    return float(torch.dot(af, bf).item() / denom)


def test_turboquant_kvstore_torch_roundtrip_preserves_shape_and_dtype(
    turboquant_store_torch, torch_module
):
    """Write a K/V block pair on the torch backend, read it back,
    assert shape and dtype are bit-identical to the input torch
    tensors. (Values are lossy by design.)"""
    torch = torch_module
    g = torch.Generator().manual_seed(42)
    k = torch.randn(
        (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM),
        generator=g, dtype=torch.float32,
    )
    v = torch.randn(k.shape, generator=g, dtype=torch.float32)

    turboquant_store_torch.write_block(0, k, v)
    k_back, v_back = turboquant_store_torch.read_block(0)

    assert isinstance(k_back, torch.Tensor)
    assert isinstance(v_back, torch.Tensor)
    assert tuple(k_back.shape) == tuple(k.shape)
    assert tuple(v_back.shape) == tuple(v.shape)
    assert k_back.dtype == k.dtype
    assert v_back.dtype == v.dtype


def test_turboquant_kvstore_torch_cosine_similarity_meets_architecture_target(
    turboquant_store_torch, torch_module
):
    """Same gate as the numpy Tier 1 test: mean cosine ≥ 0.95, per-block
    floor 0.93, on Qwen-shape Gaussian inputs."""
    torch = torch_module
    g = torch.Generator().manual_seed(137)

    cosines = []
    for block_id in range(8):
        k = torch.randn(
            (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM),
            generator=g, dtype=torch.float32,
        )
        v = torch.randn(k.shape, generator=g, dtype=torch.float32)
        turboquant_store_torch.write_block(block_id, k, v)
        k_back, v_back = turboquant_store_torch.read_block(block_id)
        cosines.append(_cosine_similarity_torch(k, k_back))
        cosines.append(_cosine_similarity_torch(v, v_back))

    mean_cos = sum(cosines) / len(cosines)
    min_cos = min(cosines)
    assert mean_cos >= 0.95, (
        f"mean cosine {mean_cos:.4f} below architecture-doc target 0.95"
    )
    assert min_cos >= 0.93, (
        f"min cosine {min_cos:.4f} below per-block floor; "
        f"some block was significantly worse than the rest"
    )


def test_turboquant_kvstore_torch_compression_ratio_meets_architecture_target(
    turboquant_store_torch, torch_module
):
    """Same gate as the numpy Tier 1 test: ≥ 5×, ≤ 12×, on FP32 Gaussian
    Qwen-shape inputs. Torch backend reports through the same
    ``theoretical_packed_bytes`` formula, so the partner-relevant ratio
    is identical between backends modulo input dtype."""
    torch = torch_module
    g = torch.Generator().manual_seed(271)

    for block_id in range(8):
        k = torch.randn(
            (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM),
            generator=g, dtype=torch.float32,
        )
        v = torch.randn(k.shape, generator=g, dtype=torch.float32)
        turboquant_store_torch.write_block(block_id, k, v)

    ratio = turboquant_store_torch.compression_ratio
    assert ratio >= 5.0, (
        f"compression ratio {ratio:.2f}x below architecture-doc target 5x"
    )
    assert ratio <= 12.0, (
        f"compression ratio {ratio:.2f}x improbably high; "
        "byte-counter accounting may have regressed"
    )


def test_turboquant_kvstore_torch_remove_block_drops_state(
    turboquant_store_torch, torch_module
):
    """Mirrors the numpy remove-block lifecycle test."""
    torch = torch_module
    g = torch.Generator().manual_seed(311)
    k = torch.randn(
        (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM),
        generator=g, dtype=torch.float32,
    )
    v = torch.randn(k.shape, generator=g, dtype=torch.float32)

    turboquant_store_torch.write_block(42, k, v)
    assert 42 in turboquant_store_torch
    assert len(turboquant_store_torch) == 1

    turboquant_store_torch.remove_block(42)
    assert 42 not in turboquant_store_torch
    assert len(turboquant_store_torch) == 0

    with pytest.raises(KeyError):
        turboquant_store_torch.read_block(42)


def test_turboquant_kvstore_torch_stats_report_backend_and_latency(
    turboquant_store_torch, torch_module
):
    """Pin the stats contract: the torch backend reports through the
    same surface as numpy and additionally surfaces ``backend='torch'``
    so callers can distinguish in a single artefact."""
    torch = torch_module
    g = torch.Generator().manual_seed(0)
    k = torch.randn(
        (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM),
        generator=g, dtype=torch.float32,
    )
    v = torch.randn(k.shape, generator=g, dtype=torch.float32)

    turboquant_store_torch.write_block(0, k, v)
    turboquant_store_torch.read_block(0)

    stats = turboquant_store_torch.get_stats()
    assert stats["backend"] == "torch"
    assert stats["writes"] == 1
    assert stats["reads"] == 1
    assert stats["avg_write_us"] > 0.0
    assert stats["avg_read_us"] > 0.0
    assert stats["compression_ratio"] >= 5.0
    assert stats["blocks_held"] == 1


def test_turboquant_kvstore_torch_handles_bf16_and_fp16_dtypes(
    turboquant_store_torch, torch_module
):
    """vLLM 0.7.3 stores KV at BF16 or FP16. The torch backend must
    round-trip those dtypes exactly (no host-side numpy fallback —
    numpy can't represent BF16, so a fallback would silently upcast)."""
    torch = torch_module
    g = torch.Generator().manual_seed(1729)

    # FP16 and BF16 — the two dtypes vLLM 0.7.3 supports for KV cache.
    for dtype in (torch.float16, torch.bfloat16):
        k = torch.randn(
            (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM),
            generator=g, dtype=torch.float32,
        ).to(dtype)
        v = torch.randn(k.shape, generator=g, dtype=torch.float32).to(dtype)

        block_id = hash(str(dtype)) & 0xFFFF
        turboquant_store_torch.write_block(block_id, k, v)
        k_back, v_back = turboquant_store_torch.read_block(block_id)
        assert k_back.dtype == dtype, (
            f"expected dtype {dtype}, got {k_back.dtype} — backend likely "
            f"silently upcast through numpy"
        )
        assert v_back.dtype == dtype
        cos = _cosine_similarity_torch(k, k_back)
        assert cos >= 0.93, (
            f"cosine {cos:.4f} on dtype {dtype} below per-dtype floor 0.93"
        )


def test_turboquant_kvstore_torch_rejects_numpy_input(torch_module):
    """The torch backend deliberately does not auto-convert numpy
    input: the whole point of Tier 2 is that tensors stay on whatever
    device they were created on, and a silent ``.cpu().numpy()`` would
    defeat that on a GPU pod. Pin the rejection."""
    torch = torch_module
    np = pytest.importorskip("numpy")
    try:
        from kv_policy.turboquant_kvstore import TurboQuantKVStore
    except ImportError as exc:
        pytest.skip(str(exc))
    try:
        store = TurboQuantKVStore(backend="torch")
    except ImportError as exc:
        pytest.skip(str(exc))

    arr = np.random.default_rng(0).standard_normal(
        (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    ).astype(np.float32)
    with pytest.raises(TypeError, match="torch.Tensor"):
        store.write_block(0, arr, arr)


def test_turboquant_kvstore_numpy_rejects_torch_input(torch_module):
    """Symmetric to the torch-backend rejection: the numpy backend
    refuses torch input rather than silently moving it to CPU."""
    torch = torch_module
    np = pytest.importorskip("numpy")
    try:
        from kv_policy.turboquant_kvstore import TurboQuantKVStore
    except ImportError as exc:
        pytest.skip(str(exc))
    try:
        store = TurboQuantKVStore(backend="numpy")
    except ImportError as exc:
        pytest.skip(str(exc))

    t = torch.randn(
        (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM),
        dtype=torch.float32,
    )
    with pytest.raises(TypeError, match="numpy"):
        store.write_block(0, t, t)


# --------------------------------------------------------------------- #
# Cross-implementation agreement                                        #
# --------------------------------------------------------------------- #


def test_turboquant_torch_matches_numpy_reconstruction(torch_module):
    """The torch port reconstructs each Qwen-shape block to a tensor
    that is value-equivalent to the numpy reference within float32
    matmul roundoff. Gate: cosine(np_recon, torch_recon) ≥ 0.999 on
    every block.

    This is the Tier 2 verification claim: a future GPU session
    swapping ``backend='torch'`` in for ``backend='numpy'`` will see
    the same generation-quality behaviour modulo the float32 drift in
    the two rotation matmuls.
    """
    torch = torch_module
    np = pytest.importorskip("numpy")
    try:
        from kv_policy.turboquant_kvstore import TurboQuantKVStore
    except ImportError as exc:
        pytest.skip(str(exc))
    try:
        store_np = TurboQuantKVStore(backend="numpy")
        store_torch = TurboQuantKVStore(backend="torch")
    except ImportError as exc:
        pytest.skip(str(exc))

    rng = np.random.default_rng(2026)
    cross_cosines = []
    for block_id in range(16):
        k_np_arr = rng.standard_normal(
            (QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
        ).astype(np.float32)
        v_np_arr = rng.standard_normal(k_np_arr.shape).astype(np.float32)
        k_t = torch.from_numpy(k_np_arr)
        v_t = torch.from_numpy(v_np_arr)

        store_np.write_block(block_id, k_np_arr, v_np_arr)
        store_torch.write_block(block_id, k_t, v_t)

        k_np_back, v_np_back = store_np.read_block(block_id)
        k_t_back, v_t_back = store_torch.read_block(block_id)

        # Cosine between the two reconstructions (lossy in absolute
        # value but matmul-equivalent in direction).
        cos_k = _cosine_similarity_torch(k_t_back, torch.from_numpy(k_np_back))
        cos_v = _cosine_similarity_torch(v_t_back, torch.from_numpy(v_np_back))
        cross_cosines.extend([cos_k, cos_v])

    min_cross = min(cross_cosines)
    mean_cross = sum(cross_cosines) / len(cross_cosines)
    assert min_cross >= 0.999, (
        f"cross-impl cosine min {min_cross:.6f} below 0.999 — torch port "
        f"diverges from numpy reference beyond float32 matmul roundoff. "
        f"Mean was {mean_cross:.6f} over {len(cross_cosines)} blocks."
    )


def test_turboquant_torch_angle_indices_match_numpy(torch_module):
    """Discrete agreement: the torch port produces the same quantised
    angle indices as the numpy reference for ≥ 99% of indices. The
    remaining ≤ 1% are angles within float32-ULP of a bin boundary
    where the two matmul paths land on different sides of the floor.

    Operates on PolarQuant directly (one level below ``compress``) so
    the test pinpoints the polar path; the cosine test above covers
    the full pipeline.
    """
    torch = torch_module
    np = pytest.importorskip("numpy")
    try:
        from kv_policy.turboquant_torch import PolarQuantTorch
        from ctm_plus_deepspeed.turboquant_offload import (
            PolarQuant,
            TurboQuantTrainingConfig,
        )
    except ImportError as exc:
        pytest.skip(str(exc))

    cfg = TurboQuantTrainingConfig(angle_bits=3, enable_qjl=True, segment_dim=128)
    polar_np = PolarQuant(cfg)
    polar_t = PolarQuantTorch(
        segment_dim=cfg.segment_dim, angle_bits=cfg.angle_bits, seed=cfg.seed,
    )

    rng = np.random.default_rng(2027)
    # 64 segments of 128 elements — exercises every level in the polar
    # tree across a representative number of segments.
    segs = rng.standard_normal((64, 128)).astype(np.float32)

    radii_np, idx_np = polar_np.compress_batch(segs)
    radii_t, idx_t = polar_t.compress_batch(torch.from_numpy(segs))

    # Radii to within float32 roundoff (this is the same matmul path on
    # both sides plus a sequence of identical sqrt operations).
    radii_t_np = radii_t.detach().cpu().numpy()
    max_radii_diff = float(np.max(np.abs(radii_np - radii_t_np)))
    assert max_radii_diff < 1e-3, (
        f"max radii diff {max_radii_diff:.2e} exceeds 1e-3 — the two "
        f"implementations diverge beyond float32 roundoff"
    )

    # Discrete indices: ≥ 99% must match exactly.
    idx_t_np = idx_t.detach().cpu().numpy()
    agreement = float((idx_np == idx_t_np).mean())
    assert agreement >= 0.99, (
        f"angle-index agreement {agreement:.4f} below 99% — torch port "
        f"diverges from numpy reference in the polar quantisation step"
    )
