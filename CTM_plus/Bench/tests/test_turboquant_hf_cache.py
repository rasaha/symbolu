"""CPU regression tests for ``kv_policy.turboquant_hf_cache``.

Pins the route-B integration contract (HF DynamicCache subclass that
compresses K/V on update). Real-model integration is exercised by
``Bench/ctm_bench/scripts/track_e_quality_eval.py``; these tests cover
the cache-layer mechanics in isolation so the GPU run isn't the first
thing to find a shape/dtype/interface bug.

Skips cleanly when transformers or torch is missing.
"""

from __future__ import annotations

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


@pytest.fixture
def torch_module():
    return pytest.importorskip("torch")


@pytest.fixture
def transformers_module():
    return pytest.importorskip("transformers")


# Qwen2.5-7B GQA-4 layout — same as the existing Tier 1/2 test files.
QWEN_BLOCK_SIZE = 16
QWEN_NUM_KV_HEADS = 4
QWEN_HEAD_DIM = 128


def _make_kv(torch, *, batch=1, seq=QWEN_BLOCK_SIZE, dtype=None, seed=42):
    if dtype is None:
        dtype = torch.float32
    g = torch.Generator().manual_seed(seed)
    k = torch.randn(batch, QWEN_NUM_KV_HEADS, seq, QWEN_HEAD_DIM,
                    generator=g, dtype=torch.float32).to(dtype)
    v = torch.randn(batch, QWEN_NUM_KV_HEADS, seq, QWEN_HEAD_DIM,
                    generator=g, dtype=torch.float32).to(dtype)
    return k, v


def _cosine(a, b):
    import torch
    af = a.flatten().to(torch.float64)
    bf = b.flatten().to(torch.float64)
    n = (torch.linalg.vector_norm(af) * torch.linalg.vector_norm(bf)).item()
    if n == 0.0:
        return 0.0
    return float((af @ bf).item() / n)


def test_compress_decompress_kv_preserves_shape_and_dtype(torch_module, transformers_module):
    """The (B, H, S, D) → vLLM-block-layout → round-trip must come
    back at the input shape and dtype, even for BF16 (numpy can't
    represent BF16, so the torch backend is required for that case)."""
    torch = torch_module
    from kv_policy.turboquant_hf_cache import _compress_decompress_kv
    from kv_policy.turboquant_kvstore import TurboQuantKVStore

    for dtype in (torch.float32, torch.float16, torch.bfloat16):
        store = TurboQuantKVStore(backend="torch")
        k, v = _make_kv(torch, dtype=dtype)
        k2, v2 = _compress_decompress_kv(k, v, store=store)
        assert k2.shape == k.shape, f"K shape mismatch on dtype {dtype}"
        assert v2.shape == v.shape, f"V shape mismatch on dtype {dtype}"
        assert k2.dtype == dtype, f"K dtype mismatch (expected {dtype}, got {k2.dtype})"
        assert v2.dtype == dtype, f"V dtype mismatch (expected {dtype}, got {v2.dtype})"


def test_compress_decompress_kv_meets_cosine_target(torch_module, transformers_module):
    """Round-trip cosine on Qwen-shape Gaussian K/V should clear the
    architecture-doc target ≥ 0.95. Uses fresh kvstore per call (the
    HF-cache integration is throwaway-per-update — see the docstring
    on _compress_decompress_kv)."""
    torch = torch_module
    from kv_policy.turboquant_hf_cache import _compress_decompress_kv
    from kv_policy.turboquant_kvstore import TurboQuantKVStore

    store = TurboQuantKVStore(backend="torch")
    k, v = _make_kv(torch)
    k2, v2 = _compress_decompress_kv(k, v, store=store)
    cos_k = _cosine(k, k2)
    cos_v = _cosine(v, v2)
    assert cos_k >= 0.95, f"K cosine {cos_k:.4f} below architecture target 0.95"
    assert cos_v >= 0.95, f"V cosine {cos_v:.4f} below architecture target 0.95"


def test_compress_decompress_kv_rejects_wrong_rank(torch_module, transformers_module):
    """The cache wrapper assumes (B, H, S, D); bad rank should fail
    loudly so a model misconfiguration is caught at the first update,
    not absorbed into a meaningless logits-comparison."""
    torch = torch_module
    from kv_policy.turboquant_hf_cache import _compress_decompress_kv
    from kv_policy.turboquant_kvstore import TurboQuantKVStore

    store = TurboQuantKVStore(backend="torch")
    bad = torch.randn(QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    with pytest.raises(ValueError, match="4-D"):
        _compress_decompress_kv(bad, bad, store=store)


def test_turboquant_cache_update_returns_lossy_kv(torch_module, transformers_module):
    """End-to-end: TurboQuantCache.update() must return tensors of the
    correct shape, route them through the parent DynamicCache, and
    have observable lossy K/V (cosine < 1.0 vs input but ≥ 0.95)."""
    torch = torch_module
    from kv_policy.turboquant_hf_cache import TurboQuantCache

    cache = TurboQuantCache(backend="torch")
    k, v = _make_kv(torch)
    k_back, v_back = cache.update(k, v, layer_idx=0)
    assert k_back.shape == k.shape
    assert v_back.shape == v.shape
    cos_k = _cosine(k, k_back)
    assert 0.95 <= cos_k < 1.0, (
        f"K cosine {cos_k:.4f} must be lossy (< 1.0) but meet target (≥ 0.95)"
    )


def test_turboquant_cache_seq_length_grows_per_update(torch_module, transformers_module):
    """The parent DynamicCache should see the lossy K/V and grow
    seq_length per update — pin so a bug in the super().update() call
    doesn't silently drop the cache state."""
    torch = torch_module
    from kv_policy.turboquant_hf_cache import TurboQuantCache

    cache = TurboQuantCache(backend="torch")
    k, v = _make_kv(torch, seq=QWEN_BLOCK_SIZE)
    cache.update(k, v, layer_idx=0)
    assert cache.get_seq_length(0) == QWEN_BLOCK_SIZE, (
        f"After 1 update of {QWEN_BLOCK_SIZE} tokens, expected "
        f"seq_length={QWEN_BLOCK_SIZE}, got {cache.get_seq_length(0)}"
    )
    cache.update(k, v, layer_idx=0)
    assert cache.get_seq_length(0) == 2 * QWEN_BLOCK_SIZE, (
        "After 2 updates the seq_length should have doubled — "
        "indicates parent DynamicCache.update() not being called"
    )


def test_turboquant_cache_multilayer_independent(torch_module, transformers_module):
    """Per-layer state must be isolated: updating layer 5 doesn't grow
    layer 0's seq_length, and stats reflect the right total."""
    torch = torch_module
    from kv_policy.turboquant_hf_cache import TurboQuantCache

    cache = TurboQuantCache(backend="torch")
    k, v = _make_kv(torch, seq=QWEN_BLOCK_SIZE)
    cache.update(k, v, layer_idx=0)
    cache.update(k, v, layer_idx=5)
    cache.update(k, v, layer_idx=5)
    assert cache.get_seq_length(0) == QWEN_BLOCK_SIZE
    assert cache.get_seq_length(5) == 2 * QWEN_BLOCK_SIZE
    stats = cache.turboquant_stats
    assert stats["updates"] == 3
    assert stats["compression_ratio"] >= 5.0


def test_turboquant_cache_stats_report_backend_config(torch_module, transformers_module):
    """Stats surface must include backend + algorithm config so a Track
    E artefact tells you exactly which knobs produced the number."""
    torch = torch_module
    from kv_policy.turboquant_hf_cache import TurboQuantCache

    cache = TurboQuantCache(
        backend="torch", angle_bits=3, segment_dim=128, enable_qjl=True,
    )
    k, v = _make_kv(torch)
    cache.update(k, v, layer_idx=0)
    cfg = cache.turboquant_config
    assert cfg["backend"] == "torch"
    assert cfg["angle_bits"] == 3
    assert cfg["segment_dim"] == 128
    assert cfg["enable_qjl"] is True
    stats = cache.turboquant_stats
    assert stats["backend"] == "torch"
    assert stats["config_angle_bits"] == 3
