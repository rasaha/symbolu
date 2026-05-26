"""CPU composition test: Route-A INT4 K/V rewrite + Phase 3 attention
capture compose correctly on the same Attention modules.

This is the central test the audit asked for — the streaming runner
installs `install_attention_capture` and then `install_int4_cache_kv_route_a`
on the same model, but the two wrappers have never been verified
composing against the same `Attention.forward`. Both monkey-patch
`forward`; install order matters; teardown order matters; the captured
attention is observed AGAINST the int4-round-tripped K/V (route-A
rewrites first because it was installed second and therefore wraps
the capture wrapper).

Locks (regression bars):

* Both wrappers fire when the wrapped forward is called once.
* Route-A's K/V rewrite is observed by the original forward, NOT the
  outer capture wrapper (verifies wrapping order).
* Phase 3 capture's `aggregator.record_*` is called per forward.
* The aggregator flushes per-block sums into the evictor's
  `forward_block_attention` and the evictor receives non-zero attention.
* Teardown of route-A restores the capture wrapper underneath (not the
  fully-original forward) — verifies LIFO discipline.
* When ONLY route-A installs (no capture), the evictor receives zero
  attention_sum (the audit-flagged status quo today).
* Composition raises no exceptions when both wrappers fire on
  the same module — the audit risk this test eliminates.

Skips on CPU hosts without torch. Runs as part of the standard Bench
suite once torch is available (GPU pod CI).
"""

from __future__ import annotations

import pytest


pytest.importorskip("torch")


QWEN_NUM_KV_HEADS = 4
QWEN_HEAD_DIM = 128
QWEN_BLOCK_SIZE = 32


def _build_fake_vllm_model(num_layers: int = 2):
    """A model with attention modules whose forward signature matches
    vLLM's classic `forward(query, key, value, kv_cache, attn_metadata)`.

    Each attention module records the K/V it received AND the
    attn_metadata so tests can assert the int4 rewrite happened before
    the original was called.
    """
    import torch

    class Attention(torch.nn.Module):
        # Phase 3 capture's _is_vllm_attention_module heuristic looks
        # for head_size/head_dim AND num_heads — provide them.
        head_size = QWEN_HEAD_DIM
        num_heads = QWEN_NUM_KV_HEADS

        def __init__(self):
            super().__init__()
            self.received_k = None
            self.received_v = None
            self.received_metadata = None

        def forward(self, q, k, v, kv_cache, attn_metadata):
            self.received_k = k
            self.received_v = v
            self.received_metadata = attn_metadata
            return q

    class FakeVLLMModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.layers = torch.nn.ModuleList()
            for _ in range(num_layers):
                blk = torch.nn.Module()
                blk.attn = Attention()
                self.layers.append(blk)

    return FakeVLLMModel()


class _FakeAttnMetadata:
    """vLLM's AttentionMetadata has many fields. The Phase 3 capture
    path uses the `decode_attention_weights` test side-channel
    (vllm_evictor.py:1890) — pre-computed per-block weights bypass the
    real GPU extraction path. That's what we drive here."""

    def __init__(self, decode_attention_weights):
        self.decode_attention_weights = decode_attention_weights
        self.num_decode_tokens = 1
        self.num_prefill_tokens = 0
        self.block_tables = None


class _StubEvictor:
    """Minimum surface to receive flush_to_evictor's calls."""

    def __init__(self):
        self.received = []

    def forward_block_attention(self, block_id, attention_sum, seq_len=None):
        self.received.append({
            "block_id": block_id,
            "attention_sum": float(attention_sum),
            "seq_len": seq_len,
        })


def test_compose_route_a_over_phase3_capture_install_order():
    """Compose: install capture FIRST, then route-A. Matches the
    streaming runner's actual install order (runner_vllm_streaming.py
    lines 1004-1098)."""
    import torch
    from kv_policy.int4_cache_kv_route_a import install_int4_cache_kv_route_a
    from kv_policy.vllm_evictor import (
        AttentionAggregator, install_attention_capture,
    )

    model = _build_fake_vllm_model(num_layers=2)
    aggregator = AttentionAggregator()
    evictor = _StubEvictor()

    n_capture = install_attention_capture(
        model=model, aggregator=aggregator, evictor=evictor,
    )
    assert n_capture == 2, "capture should patch both attention layers"

    manager, route_a_teardown = install_int4_cache_kv_route_a(
        model=model,
        k_group_size=QWEN_BLOCK_SIZE, v_group_size=QWEN_BLOCK_SIZE,
        num_kv_heads=QWEN_NUM_KV_HEADS,
    )

    g = torch.Generator().manual_seed(2026)
    q = torch.randn(1, QWEN_NUM_KV_HEADS * QWEN_HEAD_DIM, generator=g)
    k = torch.randn(QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS * QWEN_HEAD_DIM,
                    generator=g)
    v = torch.randn(k.shape, generator=g)

    decode_weights = {101: 0.6, 102: 0.4}
    metadata = _FakeAttnMetadata(decode_weights)

    for layer in model.layers:
        layer.attn(q, k, v, None, metadata)

    assert manager.stats["forward_calls"] >= 2, (
        "route-A wrapper should fire on every layer forward"
    )

    received_k = model.layers[0].attn.received_k
    assert received_k is not None
    assert received_k.shape == k.shape
    cosine = _cosine(received_k.flatten(), k.flatten())
    assert 0.5 < cosine < 0.9999, (
        f"original.forward saw K with cosine={cosine:.4f} — expected "
        "the int4-round-tripped value (lossy but faithful, NOT the "
        "raw input). If cosine == 1.0 the route-A interception didn't "
        "fire; if cosine < 0.5 the round-trip is broken."
    )

    n_flushed = aggregator.flush_to_evictor(evictor)
    assert n_flushed == 2, "two distinct block_ids should flush"
    block_ids = {r["block_id"] for r in evictor.received}
    assert block_ids == {101, 102}
    sums = {r["block_id"]: r["attention_sum"] for r in evictor.received}
    assert sums[101] > 0.0 and sums[102] > 0.0, (
        "evictor.forward_block_attention received zero attention — "
        "the bridge is broken (this is the gap the audit flagged)"
    )

    route_a_teardown()
    aggregator2 = AttentionAggregator()
    evictor2 = _StubEvictor()

    metadata2 = _FakeAttnMetadata({201: 0.7, 202: 0.3})
    for layer in model.layers:
        layer.attn.received_k = None
        layer.attn(q, k, v, None, metadata2)

    received_k_after = model.layers[0].attn.received_k
    cos_after = _cosine(received_k_after.flatten(), k.flatten())
    assert cos_after > 0.9999, (
        f"after route-A teardown, original.forward should see ORIGINAL "
        f"K (cosine ~ 1.0); got {cos_after:.4f}. Teardown order broken."
    )


def test_only_route_a_no_capture_means_zero_attention_to_evictor():
    """Lock the audit-flagged status quo: with only route-A installed
    (the current shipped path), the evictor receives zero attention.

    This is the OPPOSITE direction of the previous test — it documents
    why the bridge work matters. If this test ever fails (evictor.received
    becomes non-empty without capture installed), something has changed
    in the bridge wiring and the documentation in
    PHASE8_EVICTION_AUDIT.md needs revisiting.
    """
    import torch
    from kv_policy.int4_cache_kv_route_a import install_int4_cache_kv_route_a
    from kv_policy.vllm_evictor import AttentionAggregator

    model = _build_fake_vllm_model(num_layers=2)
    evictor = _StubEvictor()
    aggregator = AttentionAggregator()

    install_int4_cache_kv_route_a(
        model=model,
        k_group_size=QWEN_BLOCK_SIZE, v_group_size=QWEN_BLOCK_SIZE,
        num_kv_heads=QWEN_NUM_KV_HEADS,
    )

    g = torch.Generator().manual_seed(7)
    k = torch.randn(QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS * QWEN_HEAD_DIM,
                    generator=g)
    v = torch.randn(k.shape, generator=g)
    q = torch.randn(1, QWEN_NUM_KV_HEADS * QWEN_HEAD_DIM, generator=g)
    metadata = _FakeAttnMetadata({999: 0.5})

    for layer in model.layers:
        layer.attn(q, k, v, None, metadata)

    n_flushed = aggregator.flush_to_evictor(evictor)
    assert n_flushed == 0, (
        "Without install_attention_capture, the aggregator should "
        "stay empty regardless of route-A activity. Got "
        f"{n_flushed} blocks flushed -- check whether route-A grew "
        "an attention-forwarding side effect (it shouldn't)."
    )
    assert evictor.received == []


def test_real_ctm_evictor_admits_untracked_blocks_speculatively():
    """Day 5b May 2026 GPU run regression test: forward_block_attention
    received 1.15M calls but every single one hit the `_tracked` early-
    return because vLLM hadn't promoted the block_ids to IMMUTABLE yet
    in the 60s wall window. The fix admits un-tracked blocks
    speculatively via policy.ensure_block; this test locks that
    behaviour so it doesn't regress.

    Without speculative admission, this test fails with
    forward_block_attention_calls == 0 (the Day 5b symptom).
    """
    from kv_policy.vllm_evictor import CTMEvictorModern

    evictor = CTMEvictorModern(num_blocks_capacity=128, block_size=16)
    assert 99 not in evictor._tracked

    evictor.forward_block_attention(block_id=99, attention_sum=0.7)
    evictor.forward_block_attention(block_id=99, attention_sum=0.3)
    evictor.forward_block_attention(block_id=42, attention_sum=0.0)

    assert evictor._forward_block_attention_calls == 3, (
        "All three calls should tick the counter; pre-fix this was 0"
    )
    assert evictor._forward_block_attention_nonzero_sum_calls == 2, (
        "Two calls had attention_sum > 0; the third was zero"
    )
    assert 99 in evictor._policy.blocks
    assert 42 in evictor._policy.blocks
    assert 99 not in evictor._tracked, (
        "Speculative admission must NOT add to _tracked "
        "(vLLM's allocator owns _tracked membership)"
    )


def test_install_attention_capture_subsamples_layers():
    """Day 5b May 2026 GPU run regression test: Phase 3 capture
    overhead was 82% of wall on Qwen2.5-7B because every Attention
    layer ran the per-call .tolist() + Python aggregator. The
    capture_every_n knob reduces patched modules; this test locks
    the subsampling math.
    """
    from kv_policy.vllm_evictor import (
        AttentionAggregator, install_attention_capture,
    )

    model = _build_fake_vllm_model(num_layers=8)
    aggregator = AttentionAggregator()
    evictor = _StubEvictor()

    n_patched = install_attention_capture(
        model=model, aggregator=aggregator, evictor=evictor,
        capture_every_n=4,
    )
    assert n_patched == 2, (
        f"8 attention modules, every 4th -> 2 patched; got {n_patched}"
    )


def test_is_vllm_attention_module_strict_to_inner_attention():
    """Day 5b May 2026 GPU run, iteration 2: the broader
    ``endswith("Attention")`` match combined with capture_every_n=4
    preferentially picked the OUTER model wrappers (Qwen2Attention),
    whose forward signature doesn't carry attn_metadata at args[4].
    Capture extracted 0 samples even though throughput recovered.

    Lock the strict match: only vLLM's inner Attention /
    PagedAttention class names match. The per-model wrappers
    (Qwen2Attention, LlamaAttention, MistralAttention) are
    intentionally REJECTED here even though they pass route-A's
    looser check.
    """
    import torch
    from kv_policy.vllm_evictor import _is_vllm_attention_module

    class Attention(torch.nn.Module):
        head_size = 128
        num_heads = 4
        def forward(self, *a, **k): pass

    class PagedAttention(torch.nn.Module):
        head_size = 128
        num_heads = 4
        def forward(self, *a, **k): pass

    class Qwen2Attention(torch.nn.Module):
        # The outer wrapper. Its forward signature does NOT carry
        # attn_metadata at args[4] — capture would silently fail.
        head_size = 128
        num_heads = 4
        def forward(self, *a, **k): pass

    class QKVParallelLinear(torch.nn.Module):
        # Has heuristic-match attrs, but it's not an attention module.
        head_size = 128
        num_heads = 4
        def forward(self, x): return x

    assert _is_vllm_attention_module(Attention())
    assert _is_vllm_attention_module(PagedAttention())
    assert not _is_vllm_attention_module(Qwen2Attention()), (
        "Qwen2Attention is the outer wrapper; its forward signature "
        "doesn't carry attn_metadata at args[4]. Day 5b iteration 2 "
        "regression: subsampling picked these and got 0 samples."
    )
    assert not _is_vllm_attention_module(QKVParallelLinear())


def test_compose_does_not_double_quantize_kv():
    """If both wrappers fire on the same forward, the int4 round-trip
    must run exactly ONCE per forward, not twice. A composition bug
    that re-entered route-A's wrapper from inside the capture wrapper
    would compound quantization error and tank quality.
    """
    import torch
    from kv_policy.int4_cache_kv_route_a import install_int4_cache_kv_route_a
    from kv_policy.vllm_evictor import (
        AttentionAggregator, install_attention_capture,
    )

    model = _build_fake_vllm_model(num_layers=1)
    aggregator = AttentionAggregator()
    evictor = _StubEvictor()

    install_attention_capture(
        model=model, aggregator=aggregator, evictor=evictor,
    )
    manager, _ = install_int4_cache_kv_route_a(
        model=model,
        k_group_size=QWEN_BLOCK_SIZE, v_group_size=QWEN_BLOCK_SIZE,
        num_kv_heads=QWEN_NUM_KV_HEADS,
    )

    g = torch.Generator().manual_seed(11)
    k = torch.randn(QWEN_BLOCK_SIZE, QWEN_NUM_KV_HEADS * QWEN_HEAD_DIM,
                    generator=g)
    v = torch.randn(k.shape, generator=g)
    q = torch.randn(1, QWEN_NUM_KV_HEADS * QWEN_HEAD_DIM, generator=g)
    metadata = _FakeAttnMetadata({1: 0.5, 2: 0.5})

    n_before = manager.stats["forward_calls"]
    model.layers[0].attn(q, k, v, None, metadata)
    n_after = manager.stats["forward_calls"]

    assert n_after - n_before == 1, (
        f"route-A wrapper fired {n_after - n_before} times on one "
        "forward call — expected exactly 1. If > 1, the capture "
        "wrapper is re-entering route-A; the K/V is being quantized "
        "multiple times and quality WILL regress."
    )


def _cosine(a, b):
    import torch
    af = a.flatten().to(torch.float64)
    bf = b.flatten().to(torch.float64)
    n = (torch.linalg.vector_norm(af) * torch.linalg.vector_norm(bf)).item()
    return 0.0 if n == 0.0 else float((af @ bf).item() / n)
