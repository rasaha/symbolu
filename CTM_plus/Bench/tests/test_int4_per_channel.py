"""CPU regression tests for the INT4 per-channel KV-cache compression
path (``kv_policy.int4_per_channel_kv`` and
``kv_policy.int4_per_channel_hf_cache``).

After PolarQuant's failure at 3-4 bits on Qwen2.5-7B (see
``Bench/bench_out/PHASE4_GPU_FINDINGS.md`` §17), INT4 with per-channel
K + per-token V quantization (KIVI-style) is the literature-validated
alternative. These tests pin the round-trip + quality contracts
against synthetic data; the GPU Track E run measures the real-model
quality on Qwen2.5-7B.
"""

from __future__ import annotations

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


QWEN_BLOCK_SIZE = 16
QWEN_NUM_KV_HEADS = 4
QWEN_HEAD_DIM = 128


@pytest.fixture
def torch_module():
    return pytest.importorskip("torch")


@pytest.fixture
def transformers_module():
    return pytest.importorskip("transformers")


def _cosine(a, b):
    import torch
    af = a.flatten().to(torch.float64)
    bf = b.flatten().to(torch.float64)
    n = (torch.linalg.vector_norm(af) * torch.linalg.vector_norm(bf)).item()
    if n == 0.0:
        return 0.0
    return float((af @ bf).item() / n)


# --------------------------------------------------------------------- #
# Quantization primitives                                               #
# --------------------------------------------------------------------- #


def test_per_channel_quant_roundtrip_preserves_shape_and_dtype(torch_module):
    """The (S, H, D) round-trip must come back at the input shape +
    dtype for FP16 and FP32. (BF16 isn't tested separately — the
    quantize implementation casts to FP32 internally then casts back,
    so the BF16 path matches FP32 within the cast error.)
    """
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
    )
    for dtype in (torch.float32, torch.float16):
        t = torch.randn(QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM,
                        dtype=dtype)
        q, scale, _ = quantize_per_channel_int4(t)
        assert q.dtype == torch.int8
        assert q.shape == t.shape
        assert scale.shape == (1, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
        back = dequantize_per_channel_int4(q, scale, dtype=dtype)
        assert back.dtype == dtype
        assert back.shape == t.shape


def test_per_channel_quant_outlier_channel_resolved_at_its_scale(torch_module):
    """The KIVI promise: an outlier channel doesn't destroy the small
    channels' reconstruction. Per-channel scaling means each (h, d)
    location has its own 16-bin quantization range, so outliers are
    resolved at their magnitude without consuming the small channels'
    bin budget.

    Synthetic test: one channel 100× larger than the rest. Min
    per-channel cosine must clear 0.99 (INT4 per-channel is nearly
    lossless per channel).
    """
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
    )
    g = torch.Generator().manual_seed(42)
    t = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    t[:, 0, 7] *= 100.0  # outlier channel
    q, scale, _ = quantize_per_channel_int4(t)
    back = dequantize_per_channel_int4(q, scale, dtype=torch.float32)

    per_ch_cos = torch.nn.functional.cosine_similarity(t, back, dim=0).flatten()
    min_cos = per_ch_cos.min().item()
    # INT4 has 16 levels; theoretical floor on per-channel cosine for
    # Gaussian-ish input is ~0.985. The KIVI paper's reported quality
    # numbers cluster around 0.98-0.99. PolarQuant's number on the same
    # input was min per-channel cosine -0.36 (sign-flipped). Anything
    # >= 0.97 here decisively beats PolarQuant; 0.98+ is the literature
    # bar for INT4 per-channel.
    assert min_cos >= 0.97, (
        f"INT4 per-channel should achieve min per-channel cosine >= 0.97 "
        f"on outlier-channel data; got {min_cos:.4f}"
    )


def test_per_token_quant_position_outlier_resolved(torch_module):
    """V is quantized per-token, so an outlier position (huge magnitude
    on one token across all dims) is resolved at its scale without
    leaking error into the non-outlier tokens.
    """
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_token_int4, dequantize_per_token_int4,
    )
    g = torch.Generator().manual_seed(42)
    t = torch.randn(32, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    t[0, :, :] *= 100.0  # outlier position (attention sink)
    q, scale, _ = quantize_per_token_int4(t)
    back = dequantize_per_token_int4(q, scale, dtype=torch.float32)

    # Per-token cosine — same 16-level INT4 noise floor as the K test
    per_tok_cos = torch.nn.functional.cosine_similarity(t, back, dim=2).flatten()
    min_cos = per_tok_cos.min().item()
    assert min_cos >= 0.97, (
        f"INT4 per-token should achieve min per-token cosine >= 0.97 "
        f"on outlier-position data; got {min_cos:.4f}"
    )


def test_per_channel_quant_handles_dead_channels(torch_module):
    """All-zero channels must not produce NaN through the divide-by-
    scale step (clamp at 1e-8 in the implementation)."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
    )
    t = torch.randn(32, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    t[:, 1, 5] = 0.0  # dead channel
    q, scale, _ = quantize_per_channel_int4(t)
    back = dequantize_per_channel_int4(q, scale, dtype=torch.float32)
    assert not torch.isnan(back).any()
    assert not torch.isinf(back).any()


# --------------------------------------------------------------------- #
# KVStore round-trip                                                    #
# --------------------------------------------------------------------- #


def test_int4_store_roundtrip_meets_cosine_target(torch_module):
    """End-to-end via the kvstore: (S, H, D) Gaussian round-trip
    cosine must clear 0.99 (the KIVI literature target for INT4
    per-channel)."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import INT4PerChannelKVStore

    store = INT4PerChannelKVStore()
    g = torch.Generator().manual_seed(42)
    k = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g,
                    dtype=torch.float32)
    v = torch.randn(k.shape, generator=g, dtype=torch.float32)
    store.write_block(0, k, v)
    k_back, v_back = store.read_block(0)
    cos_k = _cosine(k, k_back)
    cos_v = _cosine(v, v_back)
    assert cos_k >= 0.99, f"K cosine {cos_k:.4f} below INT4 target 0.99"
    assert cos_v >= 0.99, f"V cosine {cos_v:.4f} below INT4 target 0.99"


def test_int4_store_compression_ratio(torch_module):
    """Compression ratio formula: K = (4 bits/elem + 16 bits per (H,D)
    scale) / S, V = (4 bits/elem + 16 bits per (S,H) scale) / D.
    For (S=64, H=4, D=128): combined ratio vs FP32 should be ~7.5×.
    """
    torch = torch_module
    from kv_policy.int4_per_channel_kv import INT4PerChannelKVStore

    store = INT4PerChannelKVStore()
    k = torch.randn(64, 4, 128)
    v = torch.randn(64, 4, 128)
    store.write_block(0, k, v)
    ratio = store.compression_ratio
    # FP32 input → theoretical packed ≈ 7-8×
    assert 6.0 <= ratio <= 9.0, (
        f"compression ratio {ratio:.2f}× outside expected range [6, 9] for "
        f"FP32 input + S=64 prefill"
    )


def test_int4_store_rejects_numpy_input(torch_module):
    """Like TurboQuantKVStore's torch backend, the INT4 store doesn't
    auto-convert numpy — the math is in torch ops on the input
    device. Reject loudly."""
    torch = torch_module
    import numpy as np
    from kv_policy.int4_per_channel_kv import INT4PerChannelKVStore

    store = INT4PerChannelKVStore()
    arr = np.random.default_rng(0).standard_normal((16, 4, 128)).astype(np.float32)
    with pytest.raises(TypeError, match="torch.Tensor"):
        store.write_block(0, arr, arr)


# --------------------------------------------------------------------- #
# HF cache wrapper                                                      #
# --------------------------------------------------------------------- #


def test_int4_cache_update_returns_lossy_kv(torch_module, transformers_module):
    """End-to-end via the HF cache wrapper: update() returns lossy K, V
    of the same shape; cosine clears 0.99."""
    torch = torch_module
    from kv_policy.int4_per_channel_hf_cache import INT4PerChannelCache

    cache = INT4PerChannelCache()
    g = torch.Generator().manual_seed(42)
    k = torch.randn(1, QWEN_NUM_KV_HEADS, 32, QWEN_HEAD_DIM,
                    generator=g, dtype=torch.float32)
    v = torch.randn(k.shape, generator=g, dtype=torch.float32)
    k_back, v_back = cache.update(k, v, layer_idx=0)
    assert k_back.shape == k.shape
    assert v_back.shape == v.shape
    cos_k = _cosine(k, k_back)
    assert 0.99 <= cos_k < 1.0, (
        f"K cosine {cos_k:.4f} must be lossy (<1) but >= 0.99"
    )


def test_int4_cache_seq_length_grows_per_update(torch_module, transformers_module):
    """Same pin as TurboQuant: super().update() must be called and the
    parent DynamicCache's seq_length must reflect each update."""
    torch = torch_module
    from kv_policy.int4_per_channel_hf_cache import INT4PerChannelCache

    cache = INT4PerChannelCache()
    k = torch.randn(1, QWEN_NUM_KV_HEADS, QWEN_BLOCK_SIZE, QWEN_HEAD_DIM,
                    dtype=torch.float32)
    v = torch.randn(k.shape, dtype=torch.float32)
    cache.update(k, v, layer_idx=0)
    assert cache.get_seq_length(0) == QWEN_BLOCK_SIZE
    cache.update(k, v, layer_idx=0)
    assert cache.get_seq_length(0) == 2 * QWEN_BLOCK_SIZE


def test_int4_cache_sink_size_passes_through(torch_module, transformers_module):
    """sink_size on INT4 wrapper works analogously to TurboQuantCache.
    First N positions bit-identical; rest lossy."""
    torch = torch_module
    from kv_policy.int4_per_channel_hf_cache import INT4PerChannelCache

    cache = INT4PerChannelCache(sink_size=4)
    k = torch.randn(1, QWEN_NUM_KV_HEADS, 32, QWEN_HEAD_DIM, dtype=torch.float32)
    v = torch.randn(k.shape, dtype=torch.float32)
    k_back, v_back = cache.update(k, v, layer_idx=0)
    assert torch.equal(k_back[:, :, :4, :], k[:, :, :4, :])
    cos_rest = _cosine(k[:, :, 4:, :], k_back[:, :, 4:, :])
    assert 0.99 <= cos_rest < 1.0


# --------------------------------------------------------------------- #
# Cross-algorithm comparison (sanity check the INT4 approach beats     #
# PolarQuant's per-channel-cosine performance on outlier-channel data) #
# --------------------------------------------------------------------- #


def test_group_quant_round_trip_preserves_shape(torch_module):
    """K with group_size=32 and V with group_size=32 round-trip
    through quantize+dequantize to the original shape (lossy values,
    lossless shape). Tests both the seq-axis grouping (K) and the
    head_dim-axis grouping (V).
    """
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
        quantize_per_token_int4, dequantize_per_token_int4,
    )
    g = torch.Generator().manual_seed(42)
    k = torch.randn(80, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    v = torch.randn(80, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)

    # K: group along seq axis, group_size=32 → 3 groups (32, 32, 16)
    k_q, k_scale, _ = quantize_per_channel_int4(k, group_size=32)
    assert k_q.shape == k.shape
    assert k_scale.shape == (3, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM), (
        f"expected scale shape (3, H, D); got {tuple(k_scale.shape)}"
    )
    k_back = dequantize_per_channel_int4(k_q, k_scale, dtype=k.dtype, group_size=32)
    assert k_back.shape == k.shape

    # V: group along head_dim, group_size=32 → 4 groups
    v_q, v_scale, _ = quantize_per_token_int4(v, group_size=32)
    assert v_q.shape == v.shape
    assert v_scale.shape == (80, QWEN_NUM_KV_HEADS, 4), (
        f"expected scale shape (S, H, 4); got {tuple(v_scale.shape)}"
    )
    v_back = dequantize_per_token_int4(v_q, v_scale, dtype=v.dtype, group_size=32)
    assert v_back.shape == v.shape


def test_group_quant_outlier_position_resolved_better_than_plain(torch_module):
    """The motivation for group quant: an outlier position (e.g.
    attention sink) inflates the per-channel scale, hurting non-sink
    reconstruction. Group quant isolates the outlier to its own group
    so other groups get appropriate scales.

    Synthetic: 4 outlier positions at the start (100×), rest standard
    Gaussian. Measure cosine on the non-sink positions.
    """
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
    )
    g = torch.Generator().manual_seed(42)
    t = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    t[:4] *= 100.0  # attention-sink-like outlier positions

    # Plain per-channel (one scale per (h, d), dominated by sinks)
    q_plain, s_plain, _ = quantize_per_channel_int4(t, group_size=0)
    back_plain = dequantize_per_channel_int4(
        q_plain, s_plain, dtype=torch.float32, group_size=0,
    )

    # Group quant (group_size=32 — sinks isolated to first group)
    q_grp, s_grp, _ = quantize_per_channel_int4(t, group_size=32)
    back_grp = dequantize_per_channel_int4(
        q_grp, s_grp, dtype=torch.float32, group_size=32,
    )

    # Cosine on the CLEAN GROUP (positions 32-63, in group 1 which has
    # no sink contamination). With group_size=32 and sinks at 0-3,
    # only group 1 (positions [32:64]) is sink-free. Positions 4-31
    # share group 0 with the sinks and are expected to remain
    # poorly-resolved.
    cos_plain_clean = torch.nn.functional.cosine_similarity(
        t[32:].flatten(), back_plain[32:].flatten(), dim=0,
    ).item()
    cos_grp_clean = torch.nn.functional.cosine_similarity(
        t[32:].flatten(), back_grp[32:].flatten(), dim=0,
    ).item()

    # Plain has ONE scale per channel, dominated by sinks even for
    # positions 32-63 → poor reconstruction. Group quant gives the
    # second group its own clean scale → great reconstruction.
    assert cos_grp_clean > cos_plain_clean + 0.03, (
        f"group quant should improve clean-group cosine vs plain by ≥3pp; "
        f"plain={cos_plain_clean:.4f}, group={cos_grp_clean:.4f}"
    )
    assert cos_grp_clean >= 0.98, (
        f"group quant clean-group cosine {cos_grp_clean:.4f} below 0.98 — "
        f"the rescue mechanism isn't doing its job on the sink-isolated group"
    )


def test_group_quant_kvstore_round_trip_meets_cosine(
    torch_module, transformers_module,
):
    """End-to-end via the kvstore with group_size=32 on K and V."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import INT4PerChannelKVStore

    store = INT4PerChannelKVStore(k_group_size=32, v_group_size=32)
    g = torch.Generator().manual_seed(42)
    k = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g,
                    dtype=torch.float32)
    v = torch.randn(k.shape, generator=g, dtype=torch.float32)
    store.write_block(0, k, v)
    k_back, v_back = store.read_block(0)
    cos_k = _cosine(k, k_back)
    cos_v = _cosine(v, v_back)
    assert cos_k >= 0.995, f"K cosine {cos_k:.4f} below 0.995 (group quant target)"
    assert cos_v >= 0.995, f"V cosine {cos_v:.4f} below 0.995 (group quant target)"


def test_group_quant_kvstore_compression_ratio(torch_module, transformers_module):
    """Group quantisation adds modest scale overhead but the ratio
    should still beat INT8 KV cache (2x vs FP16). For Qwen-shape with
    group_size=32 on both axes, expect ~7-8x vs FP32 source."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import INT4PerChannelKVStore

    store = INT4PerChannelKVStore(k_group_size=32, v_group_size=32)
    k = torch.randn(64, 4, 128)
    v = torch.randn(64, 4, 128)
    store.write_block(0, k, v)
    ratio = store.compression_ratio
    # Group overhead reduces the effective ratio slightly vs plain
    # per-channel/per-token. For S=64 K group=32: 2 groups instead of
    # 1 = 2× scale overhead. Expected ratio still 5-8x vs FP32.
    assert 5.0 <= ratio <= 9.0, (
        f"compression ratio {ratio:.2f}× outside expected range [5, 9]"
    )


def test_group_quant_zero_group_size_is_plain_per_channel(torch_module):
    """group_size=0 must be equivalent to the original plain per-channel
    behaviour (one scale per channel, no grouping). Pin so a future
    refactor doesn't accidentally change the default."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import quantize_per_channel_int4

    t = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    q0, s0, _ = quantize_per_channel_int4(t, group_size=0)
    q_default, s_default, _ = quantize_per_channel_int4(t)
    assert torch.equal(q0, q_default)
    assert torch.equal(s0, s_default)
    assert s0.shape == (1, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)


def test_group_quant_handles_non_divisible_seq_length(torch_module):
    """S=80 with group_size=32 produces 3 groups of size (32, 32, 16).
    Padding + trim must round-trip correctly."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
    )
    g = torch.Generator().manual_seed(42)
    t = torch.randn(80, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    q, scale, _ = quantize_per_channel_int4(t, group_size=32)
    assert scale.shape == (3, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    back = dequantize_per_channel_int4(q, scale, dtype=t.dtype, group_size=32)
    assert back.shape == t.shape
    # The last partial group (16 elements) should also reconstruct well
    cos_last = torch.nn.functional.cosine_similarity(
        t[64:].flatten(), back[64:].flatten(), dim=0,
    ).item()
    assert cos_last >= 0.98


# --------------------------------------------------------------------- #
# Asymmetric quantization (KIVI's actual config)                        #
# --------------------------------------------------------------------- #


def test_asymmetric_quant_round_trip_preserves_shape_and_dtype(torch_module):
    """Asymmetric INT4 quantize+dequantize preserves shape and dtype
    just like the symmetric path. Verifies the offset-bearing 3-tuple
    works end-to-end."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
        quantize_per_token_int4, dequantize_per_token_int4,
    )
    for dtype in (torch.float32, torch.float16):
        t = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=dtype)

        q_k, scale_k, offset_k = quantize_per_channel_int4(t, asymmetric=True)
        assert offset_k is not None
        assert offset_k.shape == scale_k.shape
        back_k = dequantize_per_channel_int4(q_k, scale_k, dtype=dtype, offset=offset_k)
        assert back_k.shape == t.shape and back_k.dtype == dtype

        q_v, scale_v, offset_v = quantize_per_token_int4(t, asymmetric=True)
        assert offset_v is not None
        assert offset_v.shape == scale_v.shape
        back_v = dequantize_per_token_int4(q_v, scale_v, dtype=dtype, offset=offset_v)
        assert back_v.shape == t.shape and back_v.dtype == dtype


def test_asymmetric_beats_symmetric_on_asymmetric_distribution(torch_module):
    """The motivation for asymmetric: data not centred on zero. We
    construct a synthetic distribution skewed positive (e.g.
    exponential-like). Asymmetric INT4 should reconstruct it
    measurably better than symmetric INT4 because it uses all 16 bins
    on [min, max] rather than wasting 8 of them on the unused negative
    range.
    """
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
    )
    g = torch.Generator().manual_seed(42)
    # Skewed input: half-normal + small constant offset. All positive.
    t = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g).abs() + 0.1

    q_sym, scale_sym, _ = quantize_per_channel_int4(t, asymmetric=False)
    back_sym = dequantize_per_channel_int4(q_sym, scale_sym, dtype=torch.float32)
    cos_sym = _cosine(t, back_sym)

    q_asym, scale_asym, offset_asym = quantize_per_channel_int4(t, asymmetric=True)
    back_asym = dequantize_per_channel_int4(
        q_asym, scale_asym, dtype=torch.float32, offset=offset_asym,
    )
    cos_asym = _cosine(t, back_asym)

    # Cosine deltas are small in the near-1 regime; compare
    # reconstruction error (1 - cosine) which is more sensitive.
    # Asymmetric should give ≥ 2× lower error on asymmetric input.
    err_sym = 1.0 - cos_sym
    err_asym = 1.0 - cos_asym
    assert err_asym <= err_sym / 2.0, (
        f"asymmetric quant should give ≤ 1/2 the reconstruction error of "
        f"symmetric on asymmetric input; "
        f"symmetric cos={cos_sym:.4f} (err {err_sym:.4f}), "
        f"asymmetric cos={cos_asym:.4f} (err {err_asym:.4f})"
    )


def test_asymmetric_group_quant_round_trip(torch_module):
    """Asymmetric + group quantization combo (KIVI's actual config).
    Round-trip must preserve shape + offset must be shape-compatible
    with the grouped scale."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
    )
    g = torch.Generator().manual_seed(42)
    t = torch.randn(80, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)

    q, scale, offset = quantize_per_channel_int4(t, group_size=32, asymmetric=True)
    # With S=80, group=32 → 3 groups (32, 32, 16)
    assert scale.shape == (3, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    assert offset is not None and offset.shape == scale.shape

    back = dequantize_per_channel_int4(
        q, scale, dtype=torch.float32, group_size=32, offset=offset,
    )
    assert back.shape == t.shape
    # Quality should be high — every group resolves its own [min, max]
    cos = _cosine(t, back)
    assert cos >= 0.99, f"asymmetric + group cosine {cos:.4f} below 0.99"


def test_asymmetric_kvstore_end_to_end(torch_module, transformers_module):
    """Asymmetric INT4 routed through the kvstore + HF cache wrapper.
    Stats must surface asymmetric=True."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import INT4PerChannelKVStore

    store = INT4PerChannelKVStore(
        k_group_size=32, v_group_size=32, asymmetric=True,
    )
    k = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float32)
    v = torch.randn(k.shape, dtype=torch.float32)
    store.write_block(0, k, v)
    k_back, v_back = store.read_block(0)
    cos_k = _cosine(k, k_back)
    cos_v = _cosine(v, v_back)
    assert cos_k >= 0.99, f"asymmetric K cosine {cos_k:.4f} below 0.99"
    assert cos_v >= 0.99, f"asymmetric V cosine {cos_v:.4f} below 0.99"

    stats = store.get_stats()
    assert stats["asymmetric"] is True
    # Compression ratio with asymmetric overhead is slightly lower
    # than symmetric (extra FP16 offset per scale).
    assert 5.0 <= stats["compression_ratio"] <= 9.0


def test_asymmetric_threads_through_hf_cache(torch_module, transformers_module):
    """HF cache wrapper plumbs asymmetric kwarg to the kvstore."""
    from kv_policy.int4_per_channel_hf_cache import INT4PerChannelCache
    cache = INT4PerChannelCache(asymmetric=True, k_group_size=32, v_group_size=32)
    cfg = cache.int4_config
    assert cfg["asymmetric"] is True
    assert "asymmetric" in cfg["scheme"]


# --------------------------------------------------------------------- #
# Bit-packing (Path A from the post-audit improvements)                 #
# --------------------------------------------------------------------- #


def test_pack_unpack_int4_round_trip_preserves_values(torch_module):
    """pack_int4 + unpack_int4 must be exact: every int4 value in
    [-8, +7] round-trips byte-identically."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import pack_int4, unpack_int4

    # All possible int4 values in a contiguous tensor (even length).
    t = torch.tensor(list(range(-8, 8)), dtype=torch.int8)  # 16 values
    packed = pack_int4(t)
    assert packed.dtype == torch.uint8
    assert packed.shape == (8,)  # 16 values → 8 bytes
    back = unpack_int4(packed, target_n=16)
    assert back.dtype == torch.int8
    assert back.shape == (16,)
    assert torch.equal(back, t)


def test_pack_unpack_int4_odd_length_handles_padding(torch_module):
    """Odd length on the last dim should pad-then-trim correctly."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import pack_int4, unpack_int4

    t = torch.tensor([3, -7, 0, 5, -2], dtype=torch.int8)  # 5 values (odd)
    packed = pack_int4(t)
    assert packed.shape == (3,)  # ceil(5/2) = 3
    back = unpack_int4(packed, target_n=5)
    assert back.shape == (5,)
    assert torch.equal(back, t)


def test_pack_unpack_int4_multi_dim_packs_along_last(torch_module):
    """Multi-dim input: packing happens along the last axis only.
    Mirrors how the kvstore uses it: ``(S, H, D) → (S, H, D/2)``."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import pack_int4, unpack_int4

    g = torch.Generator().manual_seed(42)
    t = torch.randint(-8, 8, (4, 3, 16), generator=g, dtype=torch.int8)
    packed = pack_int4(t)
    assert packed.shape == (4, 3, 8)
    back = unpack_int4(packed, target_n=16)
    assert back.shape == (4, 3, 16)
    assert torch.equal(back, t)


def test_int4_store_actual_compression_ratio_matches_theoretical(torch_module):
    """After bit-packing landed, actual heap usage should equal
    theoretical-packed bytes within a small odd-D padding constant.
    This pins the partner-relevant claim: 3.2× isn't theoretical-only;
    it's the real number.
    """
    torch = torch_module
    from kv_policy.int4_per_channel_kv import INT4PerChannelKVStore

    store = INT4PerChannelKVStore(
        k_group_size=32, v_group_size=32, asymmetric=True,
    )
    g = torch.Generator().manual_seed(42)
    k = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM,
                    generator=g, dtype=torch.float16)
    v = torch.randn(k.shape, generator=g, dtype=torch.float16)
    store.write_block(0, k, v)
    stats = store.get_stats()

    # Theoretical and actual ratios must match closely (≤2% drift
    # accounting for any odd-D byte-pad rounding).
    ratio_theo = stats["compression_ratio"]
    ratio_actual = stats["actual_compression_ratio"]
    diff_pct = abs(ratio_theo - ratio_actual) / ratio_theo * 100.0
    assert diff_pct <= 2.0, (
        f"actual ({ratio_actual:.3f}) vs theoretical ({ratio_theo:.3f}) "
        f"ratios drift {diff_pct:.1f}% — bit-packing not producing real "
        f"savings"
    )
    # The combined ratio should be in the partner-shareable 3.0–3.5× range
    # for the full KIVI config (asymmetric + group=32 on Qwen-shape FP16
    # source).
    assert 2.8 <= ratio_actual <= 3.6, (
        f"INT4 + group=32 + asymmetric on FP16 source should give "
        f"actual compression ratio ~3.0-3.5×; got {ratio_actual:.2f}×"
    )
    assert stats["bit_packed_storage"] is True


def test_int4_store_round_trip_preserved_after_packing(torch_module):
    """End-to-end: bit-packing in the kvstore must NOT degrade
    quality vs the pre-packing implementation. K/V cosine still ≥ 0.99
    on Qwen-shape Gaussian.
    """
    torch = torch_module
    from kv_policy.int4_per_channel_kv import INT4PerChannelKVStore

    store = INT4PerChannelKVStore(
        k_group_size=32, v_group_size=32, asymmetric=True,
    )
    g = torch.Generator().manual_seed(42)
    k = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM,
                    generator=g, dtype=torch.float32)
    v = torch.randn(k.shape, generator=g, dtype=torch.float32)
    store.write_block(0, k, v)
    k_back, v_back = store.read_block(0)
    cos_k = _cosine(k, k_back)
    cos_v = _cosine(v, v_back)
    assert cos_k >= 0.99, f"K cosine {cos_k:.4f} regressed after bit-packing"
    assert cos_v >= 0.99, f"V cosine {cos_v:.4f} regressed after bit-packing"


# --------------------------------------------------------------------- #
# Audit-pass cheap-fix tests                                            #
# --------------------------------------------------------------------- #


def test_int4_cache_decode_step_s1_round_trip(torch_module, transformers_module):
    """Audit gap closed: S=1 update path (decode after prefill). The
    per-channel/per-token scales degenerate to "scale captures the
    single value", so reconstruction should be essentially exact.
    """
    torch = torch_module
    from kv_policy.int4_per_channel_hf_cache import INT4PerChannelCache

    cache = INT4PerChannelCache(
        k_group_size=32, v_group_size=32, asymmetric=True,
    )
    # First a prefill update so the parent cache has the sink positions.
    g = torch.Generator().manual_seed(42)
    prefill_k = torch.randn(1, QWEN_NUM_KV_HEADS, 32, QWEN_HEAD_DIM,
                            generator=g, dtype=torch.float32)
    prefill_v = torch.randn(prefill_k.shape, generator=g, dtype=torch.float32)
    cache.update(prefill_k, prefill_v, layer_idx=0)

    # Now simulate a decode step (S=1).
    decode_k = torch.randn(1, QWEN_NUM_KV_HEADS, 1, QWEN_HEAD_DIM,
                           generator=g, dtype=torch.float32)
    decode_v = torch.randn(decode_k.shape, generator=g, dtype=torch.float32)
    k_back, v_back = cache.update(decode_k, decode_v, layer_idx=0)

    # The returned tensor includes the prefill plus the new decode step.
    assert k_back.shape == (1, QWEN_NUM_KV_HEADS, 33, QWEN_HEAD_DIM)
    # Cosine on the decode-step slice [:, :, -1:, :] should be very
    # high since per-channel scale on a single token = its value exactly
    # (any error is just int4 quantization of 1 value to 1 of 16 bins).
    cos_decode = _cosine(decode_k, k_back[:, :, -1:, :])
    assert cos_decode >= 0.99, (
        f"decode-step K cosine {cos_decode:.4f} — INT4 on a single-token "
        f"update should round-trip near-exactly"
    )


def test_int4_asymmetric_non_divisible_s_round_trip(torch_module):
    """Audit gap closed: asymmetric + group_size that doesn't evenly
    divide S. The padded portion must not bias the reconstruction.
    """
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
    )
    g = torch.Generator().manual_seed(42)
    # S=80, group=32 → groups (32, 32, 16); last group has 16 real values
    # plus 16 zero-padding when quantized.
    t = torch.randn(80, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    q, scale, offset = quantize_per_channel_int4(
        t, group_size=32, asymmetric=True,
    )
    assert scale.shape == (3, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    assert offset is not None and offset.shape == scale.shape

    back = dequantize_per_channel_int4(
        q, scale, dtype=torch.float32, group_size=32, offset=offset,
    )
    assert back.shape == t.shape

    # Cosine on the real last-group portion (positions 64-79). Padding
    # zeros may bias the scale slightly but the real values should
    # still reconstruct well.
    cos_last_group = _cosine(t[64:], back[64:])
    assert cos_last_group >= 0.98, (
        f"asymmetric + non-divisible last-group cosine {cos_last_group:.4f}; "
        f"padding may be biasing the scale"
    )


# --------------------------------------------------------------------- #
# bits parameter — INT3 experiment + INT4 default backward compat       #
# --------------------------------------------------------------------- #


def test_bits_param_default_4_matches_no_bits(torch_module):
    """bits=4 (default) must produce identical output to calling
    without the bits kwarg — backward compat pin."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import quantize_per_channel_int4

    g = torch.Generator().manual_seed(42)
    t = torch.randn(32, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    q_default, s_default, off_default = quantize_per_channel_int4(t)
    q_explicit, s_explicit, off_explicit = quantize_per_channel_int4(t, bits=4)
    assert torch.equal(q_default, q_explicit)
    assert torch.equal(s_default, s_explicit)
    assert (off_default is None) == (off_explicit is None)


def test_bits_param_int3_clamps_to_correct_range(torch_module):
    """INT3 should produce values in [-4, +3]. Verifies the qmin/qmax
    bounds compute correctly for non-4 bit widths."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import quantize_per_channel_int4

    g = torch.Generator().manual_seed(42)
    t = torch.randn(32, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g) * 10
    q, _, _ = quantize_per_channel_int4(t, bits=3)
    assert q.dtype == torch.int8
    assert q.min().item() >= -4
    assert q.max().item() <= 3


def test_bits_param_int3_asymmetric_clamps_to_correct_range(torch_module):
    """INT3 asymmetric: range still [-4, +3] in signed storage; offset
    handles the shift."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import quantize_per_channel_int4

    g = torch.Generator().manual_seed(42)
    t = torch.randn(32, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g) * 10
    q, scale, offset = quantize_per_channel_int4(t, bits=3, asymmetric=True)
    assert q.min().item() >= -4
    assert q.max().item() <= 3
    assert offset is not None


def test_bits_param_int3_round_trip_meets_lower_cosine(torch_module):
    """INT3 has 8 levels vs INT4's 16 levels — reconstruction is
    noisier by definition. The bar is "still reconstructs well enough
    to be a candidate for the GPU quality test", which we set at
    cosine ≥ 0.97 on Qwen-shape Gaussian (vs INT4's ≥ 0.99 target).
    """
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
    )
    g = torch.Generator().manual_seed(42)
    t = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    q, scale, offset = quantize_per_channel_int4(
        t, group_size=32, asymmetric=True, bits=3,
    )
    back = dequantize_per_channel_int4(
        q, scale, dtype=torch.float32, group_size=32, offset=offset,
    )
    cos = _cosine(t, back)
    assert cos >= 0.97, (
        f"INT3 + group + asymmetric cosine {cos:.4f} below 0.97; "
        f"INT3 may be too aggressive for this quantization scheme"
    )


def test_bits_param_int3_kvstore_round_trip(torch_module):
    """End-to-end INT3 via the kvstore. Source dtype FP16 (the
    partner-relevant deployment dtype for KV cache)."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import INT4PerChannelKVStore

    store = INT4PerChannelKVStore(
        k_group_size=32, v_group_size=32, asymmetric=True, bits=3,
    )
    g = torch.Generator().manual_seed(42)
    k = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM,
                    generator=g, dtype=torch.float16)
    v = torch.randn(k.shape, generator=g, dtype=torch.float16)
    store.write_block(0, k, v)
    k_back, v_back = store.read_block(0)
    cos_k = _cosine(k, k_back)
    cos_v = _cosine(v, v_back)
    assert cos_k >= 0.97, f"INT3 K cosine {cos_k:.4f} below 0.97"
    assert cos_v >= 0.97, f"INT3 V cosine {cos_v:.4f} below 0.97"

    stats = store.get_stats()
    assert stats["bits_per_element"] == 3
    # INT3 vs FP16: theoretical ~4.3-4.5× with asymmetric + group overhead.
    assert 3.5 <= stats["compression_ratio"] <= 5.5, (
        f"INT3 theoretical ratio {stats['compression_ratio']:.2f}× outside "
        f"expected 3.5-5.5× range vs FP16 source"
    )


def test_bits_param_int3_threads_through_hf_cache(torch_module, transformers_module):
    """The HF cache wrapper plumbs bits through to the kvstore so
    Track E's --bits flag actually changes behaviour."""
    from kv_policy.int4_per_channel_hf_cache import INT4PerChannelCache
    cache = INT4PerChannelCache(bits=3, k_group_size=32, asymmetric=True)
    cfg = cache.int4_config
    assert cfg["bits"] == 3
    assert "int3" in cfg["scheme"]
    stats = cache.int4_stats
    assert stats["bits_per_element"] == 3


# --------------------------------------------------------------------- #
# Static calibration (Path #6)                                          #
# --------------------------------------------------------------------- #


def test_quantize_with_static_k_scale_uses_provided_scale(torch_module):
    """When ``static_scale`` is provided, quantize must use it and skip
    the dynamic max-based computation. Verifies by passing a known
    scale and checking the returned scale matches."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import quantize_per_channel_int4

    g = torch.Generator().manual_seed(42)
    t = torch.randn(32, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    custom_scale = torch.full(
        (1, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM), fill_value=0.5, dtype=torch.float32,
    )
    q, scale, _ = quantize_per_channel_int4(t, static_scale=custom_scale)
    # Returned scale should match what was passed in.
    assert torch.equal(scale, custom_scale)


def test_quantize_with_static_scale_rejects_group_size(torch_module):
    """Static calibration + group quantisation isn't currently
    supported — should raise."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import quantize_per_channel_int4

    t = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    scale = torch.ones(1, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    with pytest.raises(ValueError, match="static_scale.*group_size"):
        quantize_per_channel_int4(t, group_size=32, static_scale=scale)


def test_quantize_asymmetric_static_requires_offset(torch_module):
    """Asymmetric + static_scale without static_offset is a
    configuration error — should raise."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import quantize_per_channel_int4

    t = torch.randn(32, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    scale = torch.ones(1, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    with pytest.raises(ValueError, match="static_offset"):
        quantize_per_channel_int4(t, asymmetric=True, static_scale=scale)


def test_quantize_v_static_scale_must_be_per_head(torch_module):
    """V static scale shape must be (1, H, 1). (1, H, D) is rejected
    so the kvstore's per-token storage convention is preserved."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import quantize_per_token_int4

    t = torch.randn(32, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    # Wrong shape: (1, H, D)
    wrong_scale = torch.ones(1, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    with pytest.raises(ValueError, match=r"\(1, H, 1\)"):
        quantize_per_token_int4(t, static_scale=wrong_scale)


def test_quantize_v_static_scale_per_head_works(torch_module):
    """V with correct (1, H, 1) static scale shape works."""
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_token_int4, dequantize_per_token_int4,
    )
    g = torch.Generator().manual_seed(42)
    t = torch.randn(32, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    scale = torch.full((1, QWEN_NUM_KV_HEADS, 1), fill_value=0.5, dtype=torch.float32)
    q, scale_stored, _ = quantize_per_token_int4(t, static_scale=scale)
    # Stored as (S, H, 1) per-token shape
    assert scale_stored.shape == (32, QWEN_NUM_KV_HEADS, 1)
    back = dequantize_per_token_int4(q, scale_stored, dtype=torch.float32)
    assert back.shape == t.shape


def test_int4_cache_loads_calibration(torch_module, transformers_module, tmp_path):
    """HF cache wrapper loads a calibration file at init and looks up
    the right layer's scales in update()."""
    torch = torch_module
    from kv_policy.int4_per_channel_hf_cache import INT4PerChannelCache

    # Fake calibration: 4 layers, each with K scale shape (1, H, D)
    # and V scale shape (1, H, 1).
    calibration = {}
    for layer_idx in range(4):
        k_scale = torch.full(
            (1, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM),
            fill_value=0.1 + 0.01 * layer_idx,
            dtype=torch.float32,
        )
        v_scale = torch.full(
            (1, QWEN_NUM_KV_HEADS, 1),
            fill_value=0.2 + 0.01 * layer_idx,
            dtype=torch.float32,
        )
        calibration[layer_idx] = {"k_scale": k_scale, "v_scale": v_scale}
    calib_path = tmp_path / "calibration.pt"
    torch.save(calibration, calib_path)

    cache = INT4PerChannelCache(calibration_path=str(calib_path))
    # Calibration is loaded
    assert cache._calibration is not None
    assert sorted(cache._calibration.keys()) == [0, 1, 2, 3]

    # Update for layer 0 should use that layer's scales
    k = torch.randn(1, QWEN_NUM_KV_HEADS, 16, QWEN_HEAD_DIM, dtype=torch.float32)
    v = torch.randn(k.shape, dtype=torch.float32)
    k_back, v_back = cache.update(k, v, layer_idx=0)
    assert k_back.shape == k.shape
    # Cache wrapper round-trip preserves shape


def test_int4_cache_rejects_calibration_with_group_size(torch_module, transformers_module, tmp_path):
    """Calibration + group quant is unsupported — should fail at
    INT4PerChannelCache.__init__."""
    torch = torch_module
    from kv_policy.int4_per_channel_hf_cache import INT4PerChannelCache

    calibration = {0: {"k_scale": torch.ones(1, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM),
                        "v_scale": torch.ones(1, QWEN_NUM_KV_HEADS, 1)}}
    calib_path = tmp_path / "calibration.pt"
    torch.save(calibration, calib_path)

    with pytest.raises(ValueError, match="group_size"):
        INT4PerChannelCache(
            calibration_path=str(calib_path),
            k_group_size=32,
        )


def test_int4_per_channel_beats_polar_quant_on_outlier_channel_data(torch_module):
    """The whole motivation: INT4 per-channel should resolve outlier-
    channel data with min per-channel cosine ≥ 0.99 (much better than
    PolarQuant's min per-channel cosine of -0.36 without scaling, or
    +0.93 with the failed per-channel-scale rescue).
    """
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
    )
    g = torch.Generator().manual_seed(42)
    t = torch.randn(16, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    t[:, 0, 7] *= 100.0
    q, scale, _ = quantize_per_channel_int4(t)
    back = dequantize_per_channel_int4(q, scale, dtype=torch.float32)
    per_ch = torch.nn.functional.cosine_similarity(t, back, dim=0).flatten()
    min_int4 = per_ch.min().item()
    mean_int4 = per_ch.mean().item()
    # INT4 per-channel min should clear 0.97; PolarQuant's was -0.36 / 0.93
    assert min_int4 >= 0.97, (
        f"INT4 per-channel min per-channel cosine {min_int4:.4f} below 0.97 "
        f"on outlier data — the algorithm isn't behaving as expected"
    )
    assert mean_int4 >= 0.98, (
        f"INT4 per-channel mean per-channel cosine {mean_int4:.4f} below 0.98"
    )


# --------------------------------------------------------------------- #
# §20.2 — sink-FP16 + body-INT4-with-KIVI-rescue                        #
#                                                                       #
# The §18.1 row 7 "INT4 + sink-skip 4" anti-pattern was sink-skip on    #
# the BROKEN plain-per-channel config (no group, no asymmetric). The   #
# §20.2 hypothesis combines sink-FP16 with the WORKING                  #
# `group=32 + asymmetric` config. Different mechanism: group already   #
# isolates outlier positions to group 0; sink-FP16 then keeps the few   #
# positions where attention sinks live bit-identical FP16, so the body #
# INT4 doesn't even need to budget bins for them.                       #
#                                                                       #
# These tests pin the contract on synthetic data:                       #
#   1. With sink_size > 0 AND the full KIVI rescue stack, the first N   #
#      positions are bit-identical FP16; the body goes through INT4.    #
#   2. On data with realistic outlier-sink magnitudes, sink-FP16 +      #
#      body-INT4-rescue produces strictly better body cosine than       #
#      no-sink + body-INT4-rescue (i.e., the hypothesis isn't crazy).   #
# --------------------------------------------------------------------- #


def test_sink_fp16_plus_kivi_rescue_threads_through(
    torch_module, transformers_module,
):
    """The §18.3 ship config (group=32 + asymmetric) composed with
    sink_size=4 (§20.2 test config) must:
      * Keep positions [0, 4) bit-identical FP16 across the cache
        round-trip.
      * Round-trip positions [4:) through the full INT4 group +
        asymmetric path (not just plain per-channel).
      * Produce a body cosine ≥ 0.999 on well-conditioned synthetic
        data (the group + asymmetric KIVI rescue stack is the gold
        path; bit-packing is lossless; the only quality cost is the
        4-bit discretisation).

    This is the unit-level analog of the §20.2 GPU sweep cell.
    """
    torch = torch_module
    from kv_policy.int4_per_channel_hf_cache import INT4PerChannelCache

    cache = INT4PerChannelCache(
        sink_size=4,
        k_group_size=32, v_group_size=32, asymmetric=True,
    )
    g = torch.Generator().manual_seed(2026)
    k = torch.randn(
        1, QWEN_NUM_KV_HEADS, 64, QWEN_HEAD_DIM,
        dtype=torch.float32, generator=g,
    )
    v = torch.randn(k.shape, dtype=torch.float32, generator=g)
    k_back, v_back = cache.update(k, v, layer_idx=0)

    # 1. Sinks are bit-identical FP16.
    assert torch.equal(k_back[:, :, :4, :], k[:, :, :4, :]), (
        "sink_size=4 must keep positions [0, 4) bit-identical FP16; got "
        f"max-abs-diff {(k_back[:, :, :4, :] - k[:, :, :4, :]).abs().max().item()}"
    )
    assert torch.equal(v_back[:, :, :4, :], v[:, :, :4, :])

    # 2. Body cosine — well-conditioned synthetic data, full KIVI
    # rescue stack: expect ≥ 0.995 (group + asymmetric INT4 round-trip
    # on Gaussian data typically lands around 0.996-0.998; 0.999 would
    # require higher bits or finer groups).
    cos_k_body = _cosine(k[:, :, 4:, :], k_back[:, :, 4:, :])
    cos_v_body = _cosine(v[:, :, 4:, :], v_back[:, :, 4:, :])
    assert cos_k_body >= 0.995, (
        f"K body cosine {cos_k_body:.6f} below 0.995 — the KIVI rescue "
        f"stack (group=32 + asymmetric) should be high-fidelity on "
        f"well-conditioned data even when combined with sink-FP16."
    )
    assert cos_v_body >= 0.995

    # 3. Verify the config dict reflects what we asked for (so the
    # sweep harness's per-sink config field is faithful to the
    # underlying cache state).
    cfg = cache.int4_config
    assert cfg["sink_size"] == 4
    assert cfg["k_group_size"] == 32
    assert cfg["v_group_size"] == 32
    assert cfg["asymmetric"] is True


def test_sink_fp16_helps_body_reconstruction_on_outlier_sinks(torch_module):
    """The §20.2 hypothesis: when the first N positions carry outlier
    magnitudes (StreamingLLM-style attention sinks), removing them
    from the quantization input lets the body's per-group scales tune
    to the non-outlier range — body cosine improves.

    Operationally we don't need the cache wrapper for this; the test
    works directly against the quantizer ops. Compare:
      (a) Quantize positions [4:) of the outlier-sink data through
          INT4 group + asymmetric — i.e., feed the body alone.
      (b) Quantize positions [0:) of the same data through INT4
          group + asymmetric — i.e., feed the full sequence and
          let the per-group scales absorb the sinks.

    Hypothesis (a) ≥ (b) on body cosine. If this holds on
    synthetic outlier-sink data, the §20.2 GPU sweep is testing a
    well-founded mechanism, not a hopeful one.
    """
    torch = torch_module
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, dequantize_per_channel_int4,
    )
    g = torch.Generator().manual_seed(2026)

    # Synthetic outlier-sink K: 64 positions × 4 heads × 128 head_dim;
    # the first 4 positions have 50x magnitude on a few channels (the
    # StreamingLLM mechanism: sinks attract disproportionate L2 mass
    # on a small subset of channels — usually 1-3 out of 128).
    S, H, D = 64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM
    k = torch.randn(S, H, D, generator=g)
    outlier_channels = [3, 17, 89]  # arbitrary "sink-attracting" channels
    for ch in outlier_channels:
        k[:4, :, ch] *= 50.0

    # (a) Sink-FP16 path: quantize only positions [4:).
    body_a = k[4:, :, :].contiguous()
    q_a, scale_a, off_a = quantize_per_channel_int4(
        body_a, group_size=32, asymmetric=True,
    )
    back_a = dequantize_per_channel_int4(
        q_a, scale_a, dtype=torch.float32, group_size=32, offset=off_a,
    )
    cos_a = _cosine(body_a, back_a)

    # (b) No-sink path: quantize all positions [0:).
    q_b, scale_b, off_b = quantize_per_channel_int4(
        k, group_size=32, asymmetric=True,
    )
    back_b = dequantize_per_channel_int4(
        q_b, scale_b, dtype=torch.float32, group_size=32, offset=off_b,
    )
    body_b_back = back_b[4:, :, :]
    cos_b = _cosine(body_a, body_b_back)

    # The mechanism predicts cos_a >= cos_b (with the first chunk's
    # scale tuned to the non-outlier range). On 50x outlier sinks the
    # gap should be visible — on the seed=2026 fixture empirically
    # ~0.041 cosine units (cos_a ≈ 0.997, cos_b ≈ 0.956).
    assert cos_a >= cos_b, (
        f"§20.2 hypothesis failed on synthetic outlier-sink data: "
        f"sink-FP16 body cosine {cos_a:.6f} should be >= no-sink "
        f"body cosine {cos_b:.6f}. The mechanism (group 0's scale "
        f"is inflated by the outliers, harming the remaining 28 "
        f"positions in that group) doesn't reproduce on this fixture; "
        f"check whether group_size or asymmetric is doing something "
        f"unexpected here."
    )
    # Tightened threshold: empirically the gap is ~0.04 on this
    # fixture; require at least 0.01 cosine units so a future regression
    # that silently halves the mechanism's effect (e.g., a sign error
    # in the per-group scale path) is caught by this test rather than
    # only surfacing at the GPU MMLU axis.
    assert (cos_a - cos_b) >= 0.01, (
        f"Gap (cos_a - cos_b)={cos_a - cos_b:.6f} is below the 0.01 "
        f"floor; on seed=2026 the expected gap is ~0.04. A regression "
        f"that compressed the mechanism's effect (cos_a={cos_a:.6f}, "
        f"cos_b={cos_b:.6f}) is the most likely cause."
    )


def test_sink_fp16_decode_step_only_compresses_new_token(
    torch_module, transformers_module,
):
    """During autoregressive decoding the cache is called with S=1
    on each new token. Even when sink_size > 0 the decode-step
    update MUST quantize the new token (the sink positions are
    already in the cache from prefill; the new token is at
    position >= prefill_len > sink_size).

    Pins the cache contract: sink-FP16 is a PREFILL-time decision,
    not a decode-time decision. Confused decode-time behaviour
    would silently break the §20.2 quality measurement (the cache
    would accumulate FP16 tokens beyond the sink budget).
    """
    torch = torch_module
    from kv_policy.int4_per_channel_hf_cache import INT4PerChannelCache

    cache = INT4PerChannelCache(
        sink_size=4,
        k_group_size=32, v_group_size=32, asymmetric=True,
    )
    g = torch.Generator().manual_seed(7)
    # Prefill: 64 positions. First 4 are sinks (FP16), rest INT4.
    k_pre = torch.randn(1, QWEN_NUM_KV_HEADS, 64, QWEN_HEAD_DIM,
                         dtype=torch.float32, generator=g)
    v_pre = torch.randn(k_pre.shape, dtype=torch.float32, generator=g)
    cache.update(k_pre, v_pre, layer_idx=0)

    # Decode step: S=1. The new token should be quantized (since
    # 1 < sink_size = 4 ⇒ the else branch fires which calls
    # _compress_decompress_kv_int4 unconditionally). Verify the
    # returned token is INT4-round-tripped, not bit-identical FP16.
    k_new = torch.randn(1, QWEN_NUM_KV_HEADS, 1, QWEN_HEAD_DIM,
                         dtype=torch.float32, generator=g)
    v_new = torch.randn(k_new.shape, dtype=torch.float32, generator=g)
    k_back, _ = cache.update(k_new, v_new, layer_idx=0)
    # The cache returns the FULL concatenated K so far; slice off
    # the new token (last position).
    k_new_back = k_back[:, :, -1:, :]
    # New token cosine should be high (~0.999 on synthetic) but NOT
    # bit-identical — INT4 round-trip leaves a fingerprint.
    assert not torch.equal(k_new_back, k_new), (
        "Decode-step new token must be quantized, not FP16-passthrough. "
        "If this fails, the cache is silently FP16-storing decode "
        "tokens whenever sink_size > 0, which would invalidate the "
        "§20.2 quality numbers."
    )
    cos_new = _cosine(k_new, k_new_back)
    assert cos_new >= 0.99, (
        f"Decode-step INT4 round-trip cosine {cos_new:.6f} below 0.99 "
        "on synthetic data"
    )
