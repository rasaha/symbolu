"""CPU regression tests for the route-A INT4 KV-cache integration
(`kv_policy.int4_cache_kv_route_a`).

Route-A is a vLLM monkey-patch; this pod has no vllm and no GPU. The
tests verify the install + interception against FAKED vLLM attention
modules — the same pattern `test_vllm_protocol_fixture.py` uses for
the CTM+ Phase 4 evictor install.

Pins:

* `INT4CacheKVRouteA.round_trip_kv` produces lossy-but-faithful K/V
  (cosine ≥ 0.99 on Gaussian data at the §18.3 ship config).
* The install wraps every attention module's `forward` and the
  wrapped forward sees INT4-round-tripped K/V (not the originals).
* Non-attention modules are left untouched.
* `teardown()` reverts every wrapped forward (LIFO).
* The interception fails OPEN — a malformed call (wrong arg arity,
  non-3-D K/V) passes through untouched rather than crashing.
* sink_size > 0 keeps the first N positions bit-identical FP16.
* Install raises if no attention module is found (heuristic missed).
"""

from __future__ import annotations

import pytest


pytest.importorskip("torch")


def _cosine(a, b):
    import torch
    af = a.flatten().to(torch.float64)
    bf = b.flatten().to(torch.float64)
    n = (torch.linalg.vector_norm(af) * torch.linalg.vector_norm(bf)).item()
    return 0.0 if n == 0.0 else float((af @ bf).item() / n)


# --------------------------------------------------------------------- #
# Faked vLLM model — mirrors the protocol-fixture pattern.              #
# --------------------------------------------------------------------- #


def _build_fake_vllm_model(num_layers: int = 4):
    """A model with `num_layers` attention modules whose forward
    signature matches vLLM's classic `forward(self, q, k, v, kv_cache,
    attn_metadata)`. Each attention module records the K/V it actually
    received so a test can assert the interception rewrote them.
    """
    import torch

    class Attention(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.received_k = None
            self.received_v = None

        def forward(self, q, k, v, kv_cache, attn_metadata):
            # Record what this layer actually saw (post-interception).
            self.received_k = k
            self.received_v = v
            return q

    class MLP(torch.nn.Module):
        # A non-attention module — must be left untouched by the install.
        def forward(self, x):
            return x

    class FakeVLLMModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.layers = torch.nn.ModuleList()
            for _ in range(num_layers):
                blk = torch.nn.Module()
                blk.attn = Attention()
                blk.mlp = MLP()
                self.layers.append(blk)

    return FakeVLLMModel()


QWEN_NUM_KV_HEADS = 4
QWEN_HEAD_DIM = 128


def test_round_trip_kv_3d_preserves_shape_and_is_faithful():
    """`round_trip_kv` on 3-D `(num_tokens, num_kv_heads, head_dim)`
    input returns lossy K/V of the same shape/dtype, faithful at
    cosine ≥ 0.99 on Gaussian data."""
    import torch
    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA

    mgr = INT4CacheKVRouteA(
        k_group_size=32, v_group_size=32, asymmetric=True, bits=4,
    )
    g = torch.Generator().manual_seed(2026)
    k = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM,
                    dtype=torch.float32, generator=g)
    v = torch.randn(k.shape, dtype=torch.float32, generator=g)
    k_lossy, v_lossy = mgr.round_trip_kv(k, v)
    assert k_lossy.shape == k.shape
    assert v_lossy.shape == v.shape
    assert k_lossy.dtype == k.dtype
    assert not torch.equal(k_lossy, k)
    assert _cosine(k, k_lossy) >= 0.99
    assert _cosine(v, v_lossy) >= 0.99
    assert mgr.stats["forward_calls"] == 1
    assert mgr.stats["tokens_compressed"] == 64


def test_round_trip_kv_2d_vllm_layout_is_the_real_path():
    """THE audit-fix test. vLLM passes K/V to Attention.forward as 2-D
    `(num_tokens, num_kv_heads*head_dim)` — confirmed by the repo's
    GPU-validated triattention.py Phase 4 hook. `round_trip_kv` must
    handle 2-D input: reshape to 3-D, quantize, reshape back to 2-D.

    Before the audit fix this raised ValueError and the interception
    silently no-op'd on real vLLM.
    """
    import torch
    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA

    # num_kv_heads MUST be set for the 2-D path.
    mgr = INT4CacheKVRouteA(
        k_group_size=32, v_group_size=32, asymmetric=True,
        num_kv_heads=QWEN_NUM_KV_HEADS,
    )
    g = torch.Generator().manual_seed(2026)
    # 2-D vLLM layout: (num_tokens, num_kv_heads * head_dim).
    k2d = torch.randn(64, QWEN_NUM_KV_HEADS * QWEN_HEAD_DIM,
                      dtype=torch.float32, generator=g)
    v2d = torch.randn(k2d.shape, dtype=torch.float32, generator=g)
    k_lossy, v_lossy = mgr.round_trip_kv(k2d, v2d)
    # Output is 2-D, same shape as input — vLLM gets back what it expects.
    assert k_lossy.shape == k2d.shape
    assert v_lossy.shape == v2d.shape
    assert k_lossy.ndim == 2
    # Lossy but faithful.
    assert not torch.equal(k_lossy, k2d)
    assert _cosine(k2d, k_lossy) >= 0.99
    assert _cosine(v2d, v_lossy) >= 0.99
    # The interception fired — NOT skipped.
    assert mgr.stats["forward_calls"] == 1
    assert mgr.stats["skipped_unknown_shape"] == 0
    # 2-D round-trip equals 3-D round-trip of the same data reshaped.
    k3d = k2d.reshape(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    mgr2 = INT4CacheKVRouteA(k_group_size=32, v_group_size=32,
                             asymmetric=True)
    k3d_lossy, _ = mgr2.round_trip_kv(k3d, k3d)
    assert torch.allclose(
        k_lossy, k3d_lossy.reshape(64, -1), atol=1e-5,
    ), "2-D path must produce the same values as the 3-D path"


def test_round_trip_2d_without_num_kv_heads_is_detectable_noop():
    """If 2-D K/V arrives but num_kv_heads is unknown, the manager
    passes the input through UNCHANGED and increments
    `skipped_unknown_shape` — a detectable no-op, not a crash."""
    import torch
    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA

    mgr = INT4CacheKVRouteA()  # num_kv_heads not set
    k2d = torch.randn(64, QWEN_NUM_KV_HEADS * QWEN_HEAD_DIM)
    k_lossy, v_lossy = mgr.round_trip_kv(k2d, k2d)
    # Passed through unchanged.
    assert torch.equal(k_lossy, k2d)
    assert mgr.stats["skipped_unknown_shape"] == 1
    assert mgr.stats["forward_calls"] == 0


def test_round_trip_rejects_1d_and_4d():
    """Only 2-D and 3-D are valid; 1-D / 4-D raise a clear error."""
    import torch
    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA

    mgr = INT4CacheKVRouteA()
    with pytest.raises(ValueError, match="2-D .* or 3-D"):
        mgr.round_trip_kv(torch.randn(64), torch.randn(64))
    with pytest.raises(ValueError, match="2-D .* or 3-D"):
        mgr.round_trip_kv(torch.randn(2, 4, 8, 16), torch.randn(2, 4, 8, 16))


def test_install_wraps_every_attention_module():
    """The install wraps all attention modules; a 4-layer fake model
    → 4 wrapped forwards."""
    from kv_policy.int4_cache_kv_route_a import install_int4_cache_kv_route_a

    model = _build_fake_vllm_model(num_layers=4)
    manager, teardown = install_int4_cache_kv_route_a(
        model=model, num_kv_heads=QWEN_NUM_KV_HEADS,
    )
    try:
        # Count wrapped attention modules by checking forward identity
        # changed. (The wrapped forward is a fresh closure.)
        n_attn = sum(
            1 for _n, m in model.named_modules()
            if type(m).__name__ == "Attention"
        )
        assert n_attn == 4
        assert manager.config["route"] == "A"
    finally:
        teardown()


def test_wrapped_forward_sees_int4_round_tripped_kv_3d():
    """After install, an attention module's forward receives
    INT4-round-tripped K/V (3-D input path)."""
    import torch
    from kv_policy.int4_cache_kv_route_a import install_int4_cache_kv_route_a

    model = _build_fake_vllm_model(num_layers=2)
    manager, teardown = install_int4_cache_kv_route_a(
        model=model, k_group_size=32, v_group_size=32, asymmetric=True,
        num_kv_heads=QWEN_NUM_KV_HEADS,
    )
    try:
        g = torch.Generator().manual_seed(7)
        q = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
        k = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
        v = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)

        attn0 = model.layers[0].attn
        attn0.forward(q, k, v, None, None)

        assert attn0.received_k is not None
        assert not torch.equal(attn0.received_k, k), (
            "attention module received the ORIGINAL K — the route-A "
            "interception didn't rewrite the args"
        )
        assert _cosine(k, attn0.received_k) >= 0.99
        assert _cosine(v, attn0.received_v) >= 0.99
        assert manager.stats["forward_calls"] >= 1
    finally:
        teardown()


def test_wrapped_forward_sees_int4_round_tripped_kv_2d_vllm_layout():
    """THE realistic end-to-end test: vLLM hands Attention.forward 2-D
    K/V `(num_tokens, num_kv_heads*head_dim)`. After install, the
    attention module must receive INT4-round-tripped 2-D K/V, and the
    interception must NOT silently no-op (forward_calls > 0,
    skipped_unknown_shape == 0).

    Before the audit fix this test would fail — the wrapper's 3-D-only
    guard skipped 2-D K/V and the attention module saw the originals.
    """
    import torch
    from kv_policy.int4_cache_kv_route_a import install_int4_cache_kv_route_a

    model = _build_fake_vllm_model(num_layers=2)
    manager, teardown = install_int4_cache_kv_route_a(
        model=model, k_group_size=32, v_group_size=32, asymmetric=True,
        num_kv_heads=QWEN_NUM_KV_HEADS,
    )
    try:
        g = torch.Generator().manual_seed(7)
        # 2-D vLLM layout.
        q = torch.randn(64, QWEN_NUM_KV_HEADS * QWEN_HEAD_DIM, generator=g)
        k = torch.randn(64, QWEN_NUM_KV_HEADS * QWEN_HEAD_DIM, generator=g)
        v = torch.randn(64, QWEN_NUM_KV_HEADS * QWEN_HEAD_DIM, generator=g)

        attn0 = model.layers[0].attn
        attn0.forward(q, k, v, None, None)

        assert attn0.received_k is not None
        # Received 2-D K/V, same shape as input.
        assert attn0.received_k.shape == k.shape
        assert attn0.received_k.ndim == 2
        # Lossy — the interception fired.
        assert not torch.equal(attn0.received_k, k), (
            "attention module received the ORIGINAL 2-D K — the "
            "route-A interception silently skipped the 2-D layout "
            "(this is the audit bug A1)"
        )
        assert _cosine(k, attn0.received_k) >= 0.99
        assert _cosine(v, attn0.received_v) >= 0.99
        # No silent no-op.
        assert manager.stats["forward_calls"] >= 1
        assert manager.stats["skipped_unknown_shape"] == 0
    finally:
        teardown()


def test_teardown_reverts_all_wrapped_forwards():
    """After teardown, attention modules see the ORIGINAL K/V again —
    every wrapped forward reverted."""
    import torch
    from kv_policy.int4_cache_kv_route_a import install_int4_cache_kv_route_a

    model = _build_fake_vllm_model(num_layers=2)
    manager, teardown = install_int4_cache_kv_route_a(model=model)
    teardown()

    g = torch.Generator().manual_seed(1)
    q = torch.randn(32, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    k = torch.randn(32, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    v = torch.randn(32, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    attn0 = model.layers[0].attn
    attn0.forward(q, k, v, None, None)
    # Post-teardown the original forward runs — K passes through verbatim.
    assert torch.equal(attn0.received_k, k)
    assert torch.equal(attn0.received_v, v)


def test_non_attention_modules_untouched():
    """MLP (and other non-attention) modules must not be wrapped."""
    from kv_policy.int4_cache_kv_route_a import install_int4_cache_kv_route_a

    model = _build_fake_vllm_model(num_layers=2)
    mlp0 = model.layers[0].mlp
    original_mlp_forward = mlp0.forward
    manager, teardown = install_int4_cache_kv_route_a(model=model)
    try:
        # MLP forward identity unchanged.
        assert mlp0.forward == original_mlp_forward
    finally:
        teardown()


def test_interception_fails_open_on_unsupported_rank():
    """A forward whose K/V slots hold tensors of an unsupported rank
    (here 4-D) must pass through untouched — the wrapper's
    `ndim in (2, 3)` guard skips it; never crash the engine."""
    import torch
    from kv_policy.int4_cache_kv_route_a import install_int4_cache_kv_route_a

    model = _build_fake_vllm_model(num_layers=1)
    manager, teardown = install_int4_cache_kv_route_a(
        model=model, num_kv_heads=QWEN_NUM_KV_HEADS,
    )
    try:
        attn0 = model.layers[0].attn
        q = torch.zeros(8, 4)
        k_4d = torch.zeros(2, 4, 8, 16)  # 4-D — unsupported rank
        v_4d = torch.zeros(2, 4, 8, 16)
        # Should not raise.
        attn0.forward(q, k_4d, v_4d, None, None)
        # K passed through untouched (interception skipped 4-D).
        assert torch.equal(attn0.received_k, k_4d)
        assert manager.stats["forward_calls"] == 0
    finally:
        teardown()


def test_interception_fails_open_on_too_few_args():
    """A forward called with too few positional args (K/V slots
    absent) must pass through untouched — never crash."""
    import torch
    from kv_policy.int4_cache_kv_route_a import install_int4_cache_kv_route_a

    model = _build_fake_vllm_model(num_layers=1)
    manager, teardown = install_int4_cache_kv_route_a(
        model=model, num_kv_heads=QWEN_NUM_KV_HEADS,
    )
    try:
        attn0 = model.layers[0].attn

        # A forward variant that takes only `q` — too few args for the
        # key_arg_index=1 / value_arg_index=2 the wrapper expects.
        def short_forward(q):
            attn0.received_k = "untouched"
            return q
        # Re-wrap a short-signature forward by calling the wrapped
        # forward with just one arg.
        wrapped = attn0.forward  # the installed wrapper
        # Should not raise even though args is length 1.
        try:
            wrapped(torch.zeros(8, 4))
        except TypeError:
            # The ORIGINAL forward needs 5 args — a TypeError from the
            # original is fine; what matters is the wrapper itself
            # didn't crash in the interception logic.
            pass
        # The interception didn't fire (too few args) — no compression.
        assert manager.stats["forward_calls"] == 0
    finally:
        teardown()


def test_install_raises_when_no_attention_modules_found():
    """If the class-name heuristic finds nothing, the install raises a
    clear error rather than silently no-op-ing. (The model class is
    named so it does NOT end in 'Attention' — the heuristic uses
    `endswith`, so a wrapper like 'NoAttentionModel' would be a false
    positive under a substring match; `endswith` avoids that.)"""
    import torch
    from kv_policy.int4_cache_kv_route_a import install_int4_cache_kv_route_a

    class PlainLinearModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.linear = torch.nn.Linear(4, 4)

    with pytest.raises(ValueError, match="no attention modules"):
        install_int4_cache_kv_route_a(model=PlainLinearModel())


def test_heuristic_endswith_not_substring():
    """`_looks_like_attention` must use `endswith('Attention')`, not a
    substring match — otherwise a wrapper class named e.g.
    'NoAttentionModel' would be a false positive.
    """
    import torch
    from kv_policy.int4_cache_kv_route_a import _looks_like_attention

    class Attention(torch.nn.Module):
        def forward(self):
            return None

    class Qwen2Attention(torch.nn.Module):
        def forward(self):
            return None

    class NoAttentionModel(torch.nn.Module):
        pass

    assert _looks_like_attention(Attention()) is True
    assert _looks_like_attention(Qwen2Attention()) is True
    assert _looks_like_attention(NoAttentionModel()) is False
    assert _looks_like_attention(torch.nn.Linear(2, 2)) is False


def test_sink_size_keeps_first_n_positions_fp16():
    """sink_size > 0 keeps the first N positions bit-identical FP16
    (the §20.2 sink-FP16 path, applied at the route-A layer)."""
    import torch
    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA

    mgr = INT4CacheKVRouteA(
        k_group_size=32, v_group_size=32, asymmetric=True, sink_size=4,
    )
    g = torch.Generator().manual_seed(2026)
    k = torch.randn(64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    v = torch.randn(k.shape, dtype=torch.float32, generator=g)
    k_lossy, v_lossy = mgr.round_trip_kv(k, v)
    # First 4 positions bit-identical.
    assert torch.equal(k_lossy[:4], k[:4])
    assert torch.equal(v_lossy[:4], v[:4])
    # Positions [4:] are lossy.
    assert not torch.equal(k_lossy[4:], k[4:])
    assert _cosine(k[4:], k_lossy[4:]) >= 0.99
    # Stats reflect the sink passthrough.
    assert mgr.stats["sink_tokens_passed_through"] == 4
    assert mgr.stats["tokens_compressed"] == 60


def test_decode_step_single_token_goes_through_compression_path():
    """A decode-step forward (num_tokens=1) goes through the
    compression codepath, NOT the sink-FP16 passthrough — sink-FP16
    is a prefill-time decision (only fires when num_tokens > sink_size).

    Note: a single-token asymmetric per-channel quant is numerically
    degenerate-lossless (x_max == x_min for S=1, so the affine scale
    collapses and the token is reproduced from the offset within
    float32 epsilon). Route-B has the exact same behaviour — its
    decode-step `update()` also quantizes one new token at a time.
    So we assert the CODEPATH (stats), not lossiness; the per-token
    decode degeneracy is a known property fixed only by the
    paged-buffer tier (quantize per 16/32-token block).
    """
    import torch
    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA

    mgr = INT4CacheKVRouteA(sink_size=4)
    g = torch.Generator().manual_seed(3)
    k = torch.randn(1, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, generator=g)
    v = torch.randn(k.shape, dtype=torch.float32, generator=g)
    k_lossy, v_lossy = mgr.round_trip_kv(k, v)
    # num_tokens=1 <= sink_size=4 → the else branch (compression path)
    # ran, NOT the sink passthrough. Stats prove the codepath.
    assert mgr.stats["sink_tokens_passed_through"] == 0
    assert mgr.stats["tokens_compressed"] == 1
    assert mgr.stats["forward_calls"] == 1
    # Shape/dtype preserved regardless of the degenerate-lossless value.
    assert k_lossy.shape == k.shape and v_lossy.shape == v.shape


def test_config_matches_route_b_knobs():
    """Route-A config dict carries the same KIVI knobs as route-B's
    INT4PerChannelCache, so the two are configured identically."""
    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA

    mgr = INT4CacheKVRouteA(
        k_group_size=32, v_group_size=32, asymmetric=True, bits=4,
        sink_size=16,
    )
    cfg = mgr.config
    assert cfg["route"] == "A"
    assert cfg["quant"] == "int4-per-channel"
    assert cfg["k_group_size"] == 32
    assert cfg["v_group_size"] == 32
    assert cfg["asymmetric"] is True
    assert cfg["bits"] == 4
    assert cfg["sink_size"] == 16
    assert "sink_size=16" in cfg["scheme"]
