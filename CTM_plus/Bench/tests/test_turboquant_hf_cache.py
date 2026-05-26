"""CPU regression tests for ``kv_policy.turboquant_hf_cache``.

Pins the route-B integration contract (HF DynamicCache subclass that
compresses K/V on update). Real-model integration is exercised by
``Bench/ctm_bench/scripts/track_e_quality_eval.py``; these tests cover
the cache-layer mechanics in isolation so the GPU run isn't the first
thing to find a shape/dtype/interface bug.

Skips cleanly when transformers or torch is missing.
"""

from __future__ import annotations

import os

# Retirement guard bypass: TurboQuantKVStore (which TurboQuantCache
# wraps) is retired from the active product path. See
# TURBOQUANT_RETIREMENT.md. Tests remain for archaeology /
# negative-result reproducibility.
os.environ.setdefault("TURBOQUANT_KV_RETIRED_BYPASS", "1")

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


def test_choice_token_ids_returns_lists_per_letter():
    """Bug-1 regression: ``_choice_token_ids`` must return a list of
    candidate token ids per letter (not a single id), to cover both
    'A' and ' A' tokenizer variants. A tokenizer that produces
    different ids for the two variants must be reflected in the
    returned mapping; one that collapses them must produce a list of
    length one.
    """
    from ctm_bench.scripts.track_e_quality_eval import _choice_token_ids

    class _DistinctSpaceTok:
        """Tokenizer where 'A' and ' A' tokenize to different ids."""
        def encode(self, text, add_special_tokens=False, **kwargs):
            # Map "A"/"B"/"C"/"D" → 0/1/2/3; " A"/" B"/... → 100/101/...
            if text.startswith(" "):
                return [100 + (ord(text[-1]) - ord("A"))]
            return [ord(text[-1]) - ord("A")]

    class _MergedSpaceTok:
        """Tokenizer where 'A' and ' A' collapse to the same id."""
        def encode(self, text, add_special_tokens=False, **kwargs):
            return [50 + (ord(text[-1]) - ord("A"))]

    distinct = _choice_token_ids(_DistinctSpaceTok())
    for letter, expected_ids in [("A", {0, 100}), ("B", {1, 101}),
                                  ("C", {2, 102}), ("D", {3, 103})]:
        assert set(distinct[letter]) == expected_ids, (
            f"Distinct-space tokenizer: expected both variants for "
            f"{letter}, got {distinct[letter]}"
        )

    merged = _choice_token_ids(_MergedSpaceTok())
    for letter, expected_id in [("A", 50), ("B", 51), ("C", 52), ("D", 53)]:
        assert merged[letter] == [expected_id], (
            f"Merged-space tokenizer: expected single id for {letter}, "
            f"got {merged[letter]}"
        )


def test_per_channel_scale_round_trip_preserves_shape(torch_module):
    """Per-channel scale (KIVI trick) must preserve shape and dtype on
    round-trip, same as the un-scaled torch backend path."""
    torch = torch_module
    from kv_policy.turboquant_kvstore import TurboQuantKVStore

    store = TurboQuantKVStore(backend="torch", per_channel_scale=True)
    g = torch.Generator().manual_seed(42)
    k = torch.randn(16, 4, 128, generator=g, dtype=torch.float32)
    v = torch.randn(k.shape, generator=g, dtype=torch.float32)
    store.write_block(0, k, v)
    k_back, v_back = store.read_block(0)
    assert tuple(k_back.shape) == tuple(k.shape)
    assert k_back.dtype == k.dtype
    assert tuple(v_back.shape) == tuple(v.shape)


def test_per_channel_scale_rescues_outlier_channel_cosines(torch_module):
    """The whole point of per-channel scale: per-(head, head_dim)
    reconstruction quality. On an outlier-channel tensor (one channel
    100x larger than the rest, mimicking Qwen's RoPE-rotated K
    distribution), per-channel scaling must lift per-channel cosine
    above 0.9 — without scaling, individual channels can flip sign.
    """
    torch = torch_module
    from kv_policy.turboquant_kvstore import TurboQuantKVStore

    g = torch.Generator().manual_seed(42)
    k = torch.randn(16, 4, 128, generator=g, dtype=torch.float32)
    k[:, 0, 7] *= 100.0  # outlier channel
    v = torch.randn(k.shape, generator=g, dtype=torch.float32)

    # Without scaling: per-channel cosine can be terrible
    s_no = TurboQuantKVStore(backend="torch", angle_bits=3, per_channel_scale=False)
    s_no.write_block(0, k, v)
    k_no, _ = s_no.read_block(0)
    per_ch_no = torch.nn.functional.cosine_similarity(k, k_no, dim=0).flatten()
    min_no = per_ch_no.min().item()

    # With per-channel scaling: every channel should reconstruct well
    s_yes = TurboQuantKVStore(backend="torch", angle_bits=3, per_channel_scale=True)
    s_yes.write_block(0, k, v)
    k_yes, _ = s_yes.read_block(0)
    per_ch_yes = torch.nn.functional.cosine_similarity(k, k_yes, dim=0).flatten()
    min_yes = per_ch_yes.min().item()

    assert min_yes > 0.9, (
        f"per-channel scale should keep min per-channel cosine > 0.9; "
        f"got {min_yes:.4f}"
    )
    assert min_yes > min_no, (
        f"per-channel scale should improve the worst per-channel cosine "
        f"(no-scale min {min_no:.4f}, with-scale min {min_yes:.4f})"
    )


def test_per_channel_scale_requires_torch_backend(torch_module):
    """Configuration error: per_channel_scale on numpy backend isn't
    supported (the normalisation is implemented in torch ops)."""
    from kv_policy.turboquant_kvstore import TurboQuantKVStore
    with pytest.raises(ValueError, match="per_channel_scale"):
        TurboQuantKVStore(backend="numpy", per_channel_scale=True)


def test_per_channel_scale_handles_zero_channels(torch_module):
    """Dead channels (all-zero along the seq axis) must not produce
    NaN through the divide-by-scale. A clamp at 1e-8 prevents that.
    """
    torch = torch_module
    from kv_policy.turboquant_kvstore import TurboQuantKVStore

    k = torch.randn(16, 4, 128, dtype=torch.float32)
    k[:, 1, 5] = 0.0   # dead channel
    v = torch.randn(k.shape, dtype=torch.float32)

    store = TurboQuantKVStore(backend="torch", per_channel_scale=True)
    store.write_block(0, k, v)
    k_back, _ = store.read_block(0)
    assert not torch.isnan(k_back).any()
    assert not torch.isinf(k_back).any()


def test_turboquant_cache_per_channel_scale_threads_through(
    torch_module, transformers_module
):
    """The HF cache wrapper must thread the per_channel_scale flag to
    the underlying kvstore so Track E's CLI flag actually changes
    behaviour."""
    torch = torch_module
    from kv_policy.turboquant_hf_cache import TurboQuantCache

    cache = TurboQuantCache(backend="torch", per_channel_scale=True)
    assert cache.turboquant_config["per_channel_scale"] is True
    assert cache._tq_store.per_channel_scale is True


def test_turboquant_cache_sink_size_preserves_first_n_positions_exactly(
    torch_module, transformers_module
):
    """StreamingLLM-style sink-skip: the first ``sink_size`` positions
    of the update's seq axis must come back bit-identical to the input
    (no compression applied), while positions ``[sink_size:]`` go
    through the lossy round-trip.
    """
    torch = torch_module
    from kv_policy.turboquant_hf_cache import TurboQuantCache

    cache = TurboQuantCache(backend="torch", sink_size=4, angle_bits=3)
    g = torch.Generator().manual_seed(42)
    # (B, H, S, D) — prefill of 32 tokens
    k = torch.randn(1, 4, 32, 128, generator=g, dtype=torch.float32)
    v = torch.randn(1, 4, 32, 128, generator=g, dtype=torch.float32)

    k_back, v_back = cache.update(k, v, layer_idx=0)

    # Sink positions (first 4) must be exact.
    assert torch.equal(k_back[:, :, :4, :], k[:, :, :4, :]), (
        "sink positions of K should be passed through unchanged"
    )
    assert torch.equal(v_back[:, :, :4, :], v[:, :, :4, :]), (
        "sink positions of V should be passed through unchanged"
    )
    # Non-sink positions are lossy (cosine < 1 but ≥ 0.95).
    cos_rest = _cosine(k[:, :, 4:, :], k_back[:, :, 4:, :])
    assert 0.95 <= cos_rest < 1.0, (
        f"non-sink positions should be lossy but meet target; cosine {cos_rest:.4f}"
    )


def test_turboquant_cache_sink_size_zero_is_default_behaviour(
    torch_module, transformers_module
):
    """sink_size=0 must compress every position (no passthrough). This
    is the default; pinning so a future refactor doesn't accidentally
    skip position 0."""
    torch = torch_module
    from kv_policy.turboquant_hf_cache import TurboQuantCache

    cache = TurboQuantCache(backend="torch", sink_size=0, angle_bits=3)
    k = torch.randn(1, 4, 32, 128, dtype=torch.float32)
    v = torch.randn(k.shape, dtype=torch.float32)
    k_back, _ = cache.update(k, v, layer_idx=0)
    # Position 0 should be lossy, not bit-identical.
    assert not torch.equal(k_back[:, :, :1, :], k[:, :, :1, :])


def test_turboquant_cache_sink_size_larger_than_input_passes_everything_through(
    torch_module, transformers_module
):
    """Edge case: if the prefill is shorter than sink_size, the
    fallback should compress the whole thing (matches the original
    behaviour). This prevents an empty-slice crash."""
    torch = torch_module
    from kv_policy.turboquant_hf_cache import TurboQuantCache

    cache = TurboQuantCache(backend="torch", sink_size=64, angle_bits=3)
    # Only 16 tokens — less than sink_size=64.
    k = torch.randn(1, 4, 16, 128, dtype=torch.float32)
    v = torch.randn(k.shape, dtype=torch.float32)
    k_back, _ = cache.update(k, v, layer_idx=0)
    # Compresses everything (no separation since shape[2]<=sink_size)
    assert k_back.shape == k.shape
    # Verify it actually went through compression (lossy)
    assert not torch.equal(k_back, k)


def test_turboquant_cache_sink_size_threads_through(torch_module, transformers_module):
    """Config + stats reporting for sink_size."""
    from kv_policy.turboquant_hf_cache import TurboQuantCache

    cache = TurboQuantCache(backend="torch", sink_size=4)
    assert cache.turboquant_config["sink_size"] == 4
    assert cache._sink_size == 4


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
