"""CPU shape/correctness tests for the protected-K INT4 KV cache
(``kv_policy.int4_protected_k_cache.ProtectedKINT4Cache``) and the
6c.3A ``fused_v2`` route-A wrapper.

Run on CPU — no GPU, no Triton needed. The fused kernel itself is
GPU-only and is validated by ``Bench/scripts/kernel_6c_gpu_test.py``;
these tests pin the *plumbing*:

* Cache shapes match the kernel's input contract
  (``KERNEL_6C_BLUEPRINT.md`` §3, replicated in
  ``scripts/kernel_6c_gpu_test.py``'s ``_build_inputs``).
* Cache contents are bit-identical to the kernel test's
  per-batch quantize-then-stack path (same quant ops, just
  incremental).
* ``reset()`` clears per-sequence state but keeps buffers.
* ``freeze_protect_mask`` auto-fires on the first ``kernel_inputs``.
* ``mark_poisoned`` blocks further decode bypass.
* The fused_v2 wrapper sidecars prefill K/V into the cache and falls
  back gracefully when Triton/GPU is unavailable.
* ``dequant_fallback`` backend behavior is unaffected by the new
  fused_v2 code (regression).

This is layer-2 of the test pyramid: kernel-input plumbing, NOT the
kernel's numerical contract (that's the GPU test).
"""

from __future__ import annotations

import pytest


pytest.importorskip("torch")


QWEN_NUM_KV_HEADS = 4
QWEN_HEAD_DIM = 128
QWEN_NUM_Q_HEADS = 28


# --------------------------------------------------------------------- #
# Cache class — shape & correctness                                     #
# --------------------------------------------------------------------- #


def test_cache_lazy_alloc_on_first_append():
    """Buffers are not allocated until the first ``append()``."""
    import torch
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    c = ProtectedKINT4Cache(
        max_seq_len=64, k_group_size=1, v_group_size=32, asymmetric=True,
    )
    assert not c.is_allocated
    assert c.k_packed_buf is None
    assert c.num_kv_heads is None and c.head_dim is None
    assert c.seq_len == 0

    k = torch.randn(8, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16)
    v = torch.randn_like(k)
    c.append(k, v)

    assert c.is_allocated
    assert c.num_kv_heads == QWEN_NUM_KV_HEADS
    assert c.head_dim == QWEN_HEAD_DIM
    assert c.seq_len == 8
    # Buffers sized to max_seq_len, not seq_len.
    assert tuple(c.k_packed_buf.shape) == (64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM // 2)
    assert tuple(c.k_scale_buf.shape) == (64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    assert tuple(c.k_offset_buf.shape) == (64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    assert tuple(c.k_fp16_buf.shape) == (64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM)
    assert tuple(c.v_packed_buf.shape) == (64, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM // 2)
    assert tuple(c.v_scale_buf.shape) == (64, QWEN_NUM_KV_HEADS, 4)
    assert tuple(c.v_offset_buf.shape) == (64, QWEN_NUM_KV_HEADS, 4)


def test_cache_accepts_bf16_inputs_casts_to_fp16_internally():
    """Models loaded in BF16 (Qwen2.5, Llama-3) hand K/V in BF16 at
    the attention boundary. The cache must accept BF16 (and FP32) and
    cast to FP16 internally so the kernel's input contract stays pure
    FP16. Regression test for the cell-D BF16 bug surfaced on the pod.
    """
    import torch
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    c = ProtectedKINT4Cache(
        max_seq_len=32, k_group_size=1, v_group_size=32, asymmetric=True,
    )
    # BF16 K/V — the Qwen2.5 case.
    k_bf16 = torch.randn(8, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.bfloat16)
    v_bf16 = torch.randn_like(k_bf16)
    c.append(k_bf16, v_bf16)
    assert c.seq_len == 8
    # Buffers are always FP16 regardless of input.
    assert c.k_fp16_buf.dtype == torch.float16
    assert c.k_scale_buf.dtype == torch.float16

    # kernel_inputs returns FP16 across the board (k_packed/v_packed
    # are uint8; protect_mask is int8).
    inputs = c.kernel_inputs()
    assert inputs["k_fp16"].dtype == torch.float16
    assert inputs["k_scale"].dtype == torch.float16
    assert inputs["v_scale"].dtype == torch.float16

    # FP32 also accepted.
    c2 = ProtectedKINT4Cache(
        max_seq_len=16, k_group_size=1, v_group_size=32, asymmetric=True,
    )
    k_fp32 = torch.randn(4, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float32)
    c2.append(k_fp32, k_fp32.clone())
    assert c2.k_fp16_buf.dtype == torch.float16


def test_cache_rejects_unsupported_dtype():
    """Float8 / int8 K/V are rejected with a clear error (not silently
    cast — those dtypes signal something is wrong at the caller)."""
    import torch
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    c = ProtectedKINT4Cache(
        max_seq_len=16, k_group_size=1, v_group_size=32, asymmetric=True,
    )
    k_i8 = torch.zeros(4, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.int8)
    with pytest.raises(ValueError, match=r"FP16 / BF16 / FP32"):
        c.append(k_i8, k_i8.clone())


def test_cache_symmetric_omits_offset_buffers():
    """Symmetric mode allocates no offset buffers; kernel_inputs returns
    None for k_offset / v_offset."""
    import torch
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    c = ProtectedKINT4Cache(
        max_seq_len=32, k_group_size=1, v_group_size=32, asymmetric=False,
    )
    k = torch.randn(4, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16)
    c.append(k, k.clone())
    assert c.k_offset_buf is None
    assert c.v_offset_buf is None
    inputs = c.kernel_inputs()
    assert inputs["k_offset"] is None
    assert inputs["v_offset"] is None


def test_cache_rejects_non_v1_k_group_size():
    """k_group_size != 1 is refused at __init__ — loud refusal so the
    §20.4 group=32 number can't accidentally ride this code path."""
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    with pytest.raises(ValueError, match=r"k_group_size=1"):
        ProtectedKINT4Cache(
            max_seq_len=32, k_group_size=32, v_group_size=32,
            asymmetric=True,
        )


def test_cache_kernel_inputs_shapes_match_blueprint():
    """The dict returned by kernel_inputs has exactly the layouts the
    kernel reads (KERNEL_6C_BLUEPRINT.md §3, replicated in
    kernel_6c_gpu_test.py's _build_inputs)."""
    import torch
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    c = ProtectedKINT4Cache(
        max_seq_len=256, protect_fraction=0.04,
        k_group_size=1, v_group_size=32, asymmetric=True,
    )
    # Prefill (T=20) + decode (T=1 x 5) → total seq_len = 25.
    k_prefill = torch.randn(20, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16)
    v_prefill = torch.randn_like(k_prefill)
    c.append(k_prefill, v_prefill)
    for _ in range(5):
        k_step = torch.randn(1, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16)
        v_step = torch.randn_like(k_step)
        c.append(k_step, v_step)
    assert c.seq_len == 25

    inputs = c.kernel_inputs()
    S = 25
    H = QWEN_NUM_KV_HEADS
    D = QWEN_HEAD_DIM
    n_grp_v = D // 32

    assert tuple(inputs["k_packed"].shape) == (1, H, S, D // 2)
    assert tuple(inputs["k_scale"].shape) == (1, S, H, D)
    assert tuple(inputs["k_offset"].shape) == (1, S, H, D)
    assert tuple(inputs["k_fp16"].shape) == (1, H, S, D)
    assert tuple(inputs["protect_mask"].shape) == (H, D)
    assert tuple(inputs["v_packed"].shape) == (1, H, S, D // 2)
    assert tuple(inputs["v_scale"].shape) == (1, S, H, n_grp_v)
    assert tuple(inputs["v_offset"].shape) == (1, S, H, n_grp_v)

    # dtypes.
    assert inputs["k_packed"].dtype == torch.uint8
    assert inputs["k_scale"].dtype == torch.float16
    assert inputs["k_offset"].dtype == torch.float16
    assert inputs["k_fp16"].dtype == torch.float16
    assert inputs["protect_mask"].dtype == torch.int8
    assert inputs["v_packed"].dtype == torch.uint8
    assert inputs["v_scale"].dtype == torch.float16
    assert inputs["v_offset"].dtype == torch.float16

    # Contiguity — the three permute-copies must be contiguous.
    assert inputs["k_packed"].is_contiguous()
    assert inputs["k_fp16"].is_contiguous()
    assert inputs["v_packed"].is_contiguous()


def test_cache_contents_match_route_b_per_batch_quantize():
    """The same K/V tensor, fed to (a) a single ``append(T=S)`` call and
    (b) the route-B per-batch quantize-then-stack used by the GPU test's
    ``_build_inputs``, produce element-wise identical kernel inputs.

    This is the cache's numerical contract: the per-call append +
    incremental write produces the same INT4-packed bytes / scales /
    offsets as the kernel test's monolithic per-batch path. A regression
    here breaks the kernel's numerical oracle. (The kernel itself is
    validated by ``kernel_6c_gpu_test.py``; this test pins the cache's
    *production* of those inputs.)
    """
    import torch
    from kv_policy.int4_per_channel_kv import (
        quantize_per_channel_int4, quantize_per_token_int4, pack_int4,
    )
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    # Single-batch Qwen-shape with group_size_k=1 — the 6c.3A v1
    # config.
    H, D, S = QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, 16
    gk, gv = 1, 32
    torch.manual_seed(7)
    k = torch.randn(S, H, D, dtype=torch.float16)
    v = torch.randn(S, H, D, dtype=torch.float16)

    # Route-B style (kernel test's _build_inputs path, adapted to gk=1).
    kq, ks, ko = quantize_per_channel_int4(
        k, group_size=gk, asymmetric=True, bits=4,
    )
    vq, vs, vo = quantize_per_token_int4(
        v, group_size=gv, asymmetric=True, bits=4,
    )
    k_packed_ref = pack_int4(kq)                                       # (S, H, D/2)
    v_packed_ref = pack_int4(vq)
    # Layout to the kernel's input shape: (B, H, S, D/2) etc.
    k_packed_ref_kernel = k_packed_ref.permute(1, 0, 2).contiguous().unsqueeze(0)
    v_packed_ref_kernel = v_packed_ref.permute(1, 0, 2).contiguous().unsqueeze(0)
    k_scale_ref_kernel = ks.to(torch.float16).unsqueeze(0)             # (1, S, H, D)
    k_offset_ref_kernel = ko.to(torch.float16).unsqueeze(0)
    v_scale_ref_kernel = vs.to(torch.float16).unsqueeze(0)             # (1, S, H, n_grp_v)
    v_offset_ref_kernel = vo.to(torch.float16).unsqueeze(0)

    # Cache path: a single ``append(T=S)`` followed by ``kernel_inputs``.
    c = ProtectedKINT4Cache(
        max_seq_len=64, protect_fraction=0.0,
        k_group_size=gk, v_group_size=gv, asymmetric=True,
    )
    c.append(k, v)
    cache_inputs = c.kernel_inputs()

    # Bit-identical: same quant ops underneath, same byte packing.
    assert torch.equal(cache_inputs["k_packed"], k_packed_ref_kernel)
    assert torch.equal(cache_inputs["v_packed"], v_packed_ref_kernel)
    assert torch.equal(cache_inputs["k_scale"], k_scale_ref_kernel)
    assert torch.equal(cache_inputs["v_scale"], v_scale_ref_kernel)
    assert torch.equal(cache_inputs["k_offset"], k_offset_ref_kernel)
    assert torch.equal(cache_inputs["v_offset"], v_offset_ref_kernel)


def test_cache_incremental_appends_match_monolithic():
    """Appending one token at a time (the decode pattern) produces the
    same kernel inputs as one ``append(T=S)`` call. With group_size_k=1
    these MUST match — every token is its own group.
    """
    import torch
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    H, D, S = QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, 12
    torch.manual_seed(11)
    k = torch.randn(S, H, D, dtype=torch.float16)
    v = torch.randn(S, H, D, dtype=torch.float16)

    # Monolithic.
    c_mono = ProtectedKINT4Cache(
        max_seq_len=64, protect_fraction=0.04,
        k_group_size=1, v_group_size=32, asymmetric=True,
    )
    c_mono.append(k, v)
    inp_mono = c_mono.kernel_inputs()

    # Incremental — one token at a time.
    c_inc = ProtectedKINT4Cache(
        max_seq_len=64, protect_fraction=0.04,
        k_group_size=1, v_group_size=32, asymmetric=True,
    )
    for i in range(S):
        c_inc.append(k[i:i+1], v[i:i+1])
    inp_inc = c_inc.kernel_inputs()

    for key in (
        "k_packed", "k_scale", "k_offset", "k_fp16",
        "v_packed", "v_scale", "v_offset", "protect_mask",
    ):
        assert torch.equal(inp_mono[key], inp_inc[key]), (
            f"incremental vs monolithic differ on {key}"
        )


def test_cache_protect_mask_auto_freeze_on_first_kernel_inputs():
    """``kernel_inputs`` auto-freezes the mask on first call; subsequent
    appends don't re-freeze."""
    import torch
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    c = ProtectedKINT4Cache(
        max_seq_len=64, protect_fraction=0.04,
        k_group_size=1, v_group_size=32, asymmetric=True,
    )
    k = torch.randn(10, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16)
    # Force one channel to be a clear outlier so the freeze picks
    # something specific.
    k[:, 0, 0] *= 50.0
    c.append(k, k.clone())
    assert not c.is_frozen

    inp1 = c.kernel_inputs()
    assert c.is_frozen
    mask1 = inp1["protect_mask"].clone()
    # The outlier channel must be protected.
    assert mask1[0, 0].item() == 1

    # Appending a decode token must NOT re-freeze — the mask is
    # supposed to stay the prefill-derived one.
    k_step = torch.randn(1, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16)
    c.append(k_step, k_step.clone())
    inp2 = c.kernel_inputs()
    assert torch.equal(inp2["protect_mask"], mask1)
    assert c.stats["freeze_calls"] == 1   # freeze fired exactly once


def test_cache_protect_fraction_zero_yields_all_zero_mask():
    """``protect_fraction=0`` → no channels protected."""
    import torch
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    c = ProtectedKINT4Cache(
        max_seq_len=16, protect_fraction=0.0,
        k_group_size=1, v_group_size=32, asymmetric=True,
    )
    c.append(
        torch.randn(8, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16),
        torch.randn(8, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16),
    )
    mask = c.kernel_inputs()["protect_mask"]
    assert mask.sum().item() == 0


def test_cache_protect_fraction_one_yields_all_one_mask():
    """``protect_fraction=1.0`` → every channel protected."""
    import torch
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    c = ProtectedKINT4Cache(
        max_seq_len=16, protect_fraction=1.0,
        k_group_size=1, v_group_size=32, asymmetric=True,
    )
    c.append(
        torch.randn(8, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16),
        torch.randn(8, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16),
    )
    mask = c.kernel_inputs()["protect_mask"]
    assert mask.sum().item() == QWEN_NUM_KV_HEADS * QWEN_HEAD_DIM


def test_cache_reset_clears_state_keeps_buffers():
    """``reset()`` zeros s_curr and mask state; keeps allocated buffers."""
    import torch
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    c = ProtectedKINT4Cache(
        max_seq_len=32, protect_fraction=0.04,
        k_group_size=1, v_group_size=32, asymmetric=True,
    )
    c.append(
        torch.randn(8, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16),
        torch.randn(8, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16),
    )
    _ = c.kernel_inputs()
    buf_before = c.k_packed_buf
    assert c.seq_len == 8 and c.is_frozen and c.is_allocated

    c.reset()
    assert c.seq_len == 0
    assert not c.is_frozen
    assert c.is_allocated                   # buffers retained
    assert c.k_packed_buf is buf_before     # exact-same tensor


def test_cache_rejects_overflow():
    """``append`` past ``max_seq_len`` raises."""
    import torch
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    c = ProtectedKINT4Cache(
        max_seq_len=10, k_group_size=1, v_group_size=32, asymmetric=True,
    )
    c.append(
        torch.randn(8, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16),
        torch.randn(8, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16),
    )
    with pytest.raises(ValueError, match=r"max_seq_len"):
        c.append(
            torch.randn(3, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16),
            torch.randn(3, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16),
        )


def test_cache_rejects_mismatched_subsequent_shape():
    """Once allocated for (H_kv, D), further appends with different
    (H_kv, D) raise."""
    import torch
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    c = ProtectedKINT4Cache(
        max_seq_len=32, k_group_size=1, v_group_size=32, asymmetric=True,
    )
    c.append(
        torch.randn(2, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16),
        torch.randn(2, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16),
    )
    with pytest.raises(ValueError, match=r"allocated for"):
        c.append(
            torch.randn(2, QWEN_NUM_KV_HEADS + 1, QWEN_HEAD_DIM, dtype=torch.float16),
            torch.randn(2, QWEN_NUM_KV_HEADS + 1, QWEN_HEAD_DIM, dtype=torch.float16),
        )


def test_cache_mark_poisoned_persists_until_reset():
    """``mark_poisoned`` flips ``is_poisoned`` true; ``reset`` clears it."""
    import torch
    from kv_policy.int4_protected_k_cache import ProtectedKINT4Cache

    c = ProtectedKINT4Cache(
        max_seq_len=16, k_group_size=1, v_group_size=32, asymmetric=True,
    )
    c.append(
        torch.randn(4, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16),
        torch.randn(4, QWEN_NUM_KV_HEADS, QWEN_HEAD_DIM, dtype=torch.float16),
    )
    assert not c.is_poisoned
    c.mark_poisoned("test")
    assert c.is_poisoned
    c.reset()
    assert not c.is_poisoned


# --------------------------------------------------------------------- #
# Fused_v2 wrapper — prefill sidecar + decode fallback                  #
# --------------------------------------------------------------------- #


def _build_fake_vllm_model(num_layers: int = 4):
    """A model with ``num_layers`` attention modules whose forward
    signature matches vLLM's classic ``forward(self, q, k, v,
    kv_cache, attn_metadata)``. The fake Attention records what K/V
    its original forward received — so we can verify the wrapper's
    rewrite (or bypass) behaviour.
    """
    import torch

    class Attention(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.received_k = None
            self.received_v = None
            self.received_q = None
            self.n_calls = 0

        def forward(self, q, k, v, kv_cache=None, attn_metadata=None):
            self.received_q = q
            self.received_k = k
            self.received_v = v
            self.n_calls += 1
            # Pretend output is q.clone() so we can check the wrapper
            # returns whatever original_forward returned in prefill.
            return q.clone()

    class FakeModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.layers = torch.nn.ModuleList()
            for _ in range(num_layers):
                blk = torch.nn.Module()
                blk.attn = Attention()
                self.layers.append(blk)

    return FakeModel()


def _kv_2d(num_tokens, num_kv_heads=QWEN_NUM_KV_HEADS, head_dim=QWEN_HEAD_DIM):
    """Build a (num_tokens, num_kv_heads*head_dim) FP16 tensor — vLLM's layout."""
    import torch
    return torch.randn(
        num_tokens, num_kv_heads * head_dim, dtype=torch.float16,
    )


def _q_2d(num_tokens, num_q_heads=QWEN_NUM_Q_HEADS, head_dim=QWEN_HEAD_DIM):
    import torch
    return torch.randn(
        num_tokens, num_q_heads * head_dim, dtype=torch.float16,
    )


def test_fused_v2_install_creates_per_layer_caches_lazily():
    """Install succeeds; caches dict is empty until a forward fires."""
    from kv_policy.int4_cache_kv_route_a import (
        install_int4_cache_kv_route_a, BACKEND_FUSED_V2,
    )

    model = _build_fake_vllm_model(num_layers=3)
    manager, teardown = install_int4_cache_kv_route_a(
        model=model,
        num_kv_heads=QWEN_NUM_KV_HEADS,
        kernel_backend=BACKEND_FUSED_V2,
        max_seq_len=32,
        protect_fraction=0.04,
        cache_k_group_size=1,
        cache_v_group_size=32,
    )
    assert manager.kernel_backend == BACKEND_FUSED_V2
    assert len(manager.caches) == 0   # lazy
    teardown()


def test_fused_v2_prefill_sidecars_cache_and_runs_original_forward():
    """T > 1 path: cache populated AND original forward called."""
    import torch
    from kv_policy.int4_cache_kv_route_a import (
        install_int4_cache_kv_route_a, BACKEND_FUSED_V2,
    )

    model = _build_fake_vllm_model(num_layers=2)
    manager, teardown = install_int4_cache_kv_route_a(
        model=model,
        num_kv_heads=QWEN_NUM_KV_HEADS,
        kernel_backend=BACKEND_FUSED_V2,
        max_seq_len=64,
        protect_fraction=0.04,
        cache_k_group_size=1,
        cache_v_group_size=32,
    )

    T_prefill = 12
    q = _q_2d(T_prefill)
    k = _kv_2d(T_prefill)
    v = _kv_2d(T_prefill)
    for layer in model.layers:
        out = layer.attn.forward(q, k, v)
        assert out.shape == q.shape
        # Original forward was called (it recorded inputs).
        assert layer.attn.n_calls == 1
        assert layer.attn.received_k is not None
        # Original forward saw the LOSSY K/V (route-A's dequant_fallback
        # rewrite still runs in prefill).
        assert not torch.equal(layer.attn.received_k, k)
        # Cache was sidecarred.
        cache = manager.caches[id(layer.attn)]
        assert cache.seq_len == T_prefill
        assert not cache.is_frozen   # auto-freezes on first kernel_inputs only

    assert manager.stats["fused_v2_prefills_sidecar"] == 2  # 2 layers × 1 prefill
    assert manager.stats["fused_v2_decodes"] == 0
    teardown()
    # After teardown, the forwards are restored.
    for layer in model.layers:
        layer.attn.n_calls = 0
        layer.attn.forward(q, k, v)
        assert layer.attn.n_calls == 1
        # Now without interception, original forward saw the unrewritten K.
        assert torch.equal(layer.attn.received_k, k)


def test_fused_v2_decode_falls_back_when_kernel_unavailable():
    """T == 1 path: cache appends, but if the fused kernel isn't
    available (no Triton or no GPU — this CPU test) it falls back to
    dequant_fallback rather than crashing. The original forward IS
    called via the fallback, with rewritten K/V."""
    import torch
    from kv_policy.int4_cache_kv_route_a import (
        install_int4_cache_kv_route_a, BACKEND_FUSED_V2,
    )

    model = _build_fake_vllm_model(num_layers=1)
    manager, teardown = install_int4_cache_kv_route_a(
        model=model,
        num_kv_heads=QWEN_NUM_KV_HEADS,
        kernel_backend=BACKEND_FUSED_V2,
        max_seq_len=64,
        protect_fraction=0.04,
        cache_k_group_size=1,
        cache_v_group_size=32,
    )

    attn = model.layers[0].attn
    # Prefill first so cache has rows when decode appends.
    T_prefill = 5
    attn.forward(_q_2d(T_prefill), _kv_2d(T_prefill), _kv_2d(T_prefill))
    cache = manager.caches[id(attn)]
    assert cache.seq_len == T_prefill

    # Decode call — kernel call will raise (no GPU/Triton); wrapper
    # must catch and fall back.
    attn.n_calls = 0
    q_d = _q_2d(1)
    k_d = _kv_2d(1)
    v_d = _kv_2d(1)
    out = attn.forward(q_d, k_d, v_d)
    # Cache append still succeeded (it runs before the kernel call).
    assert cache.seq_len == T_prefill + 1
    # Fallback path called the original forward.
    assert attn.n_calls == 1
    # Stats: a decode-exception fallback was recorded.
    fb = manager.stats["fused_v2_fallbacks"]
    assert "decode_exception" in fb and fb["decode_exception"] == 1
    assert manager.stats["fused_v2_decodes"] == 0
    # Output shape preserved (whatever the fallback returned).
    assert out.shape == q_d.shape
    teardown()


def test_fused_v2_poisoned_cache_blocks_decode_bypass():
    """If a cache is marked poisoned during prefill, subsequent decode
    calls do NOT try the fused kernel — they fall back directly."""
    import torch
    from kv_policy.int4_cache_kv_route_a import (
        install_int4_cache_kv_route_a, BACKEND_FUSED_V2,
    )

    model = _build_fake_vllm_model(num_layers=1)
    manager, teardown = install_int4_cache_kv_route_a(
        model=model,
        num_kv_heads=QWEN_NUM_KV_HEADS,
        kernel_backend=BACKEND_FUSED_V2,
        max_seq_len=64,
        protect_fraction=0.04,
        cache_k_group_size=1,
        cache_v_group_size=32,
    )
    attn = model.layers[0].attn
    attn.forward(_q_2d(5), _kv_2d(5), _kv_2d(5))
    cache = manager.caches[id(attn)]
    cache.mark_poisoned("test")

    attn.n_calls = 0
    out = attn.forward(_q_2d(1), _kv_2d(1), _kv_2d(1))
    fb = manager.stats["fused_v2_fallbacks"]
    assert fb.get("poisoned_cache", 0) == 1
    # Poisoned-cache fallback does NOT append (we want the cache to
    # stay at the last consistent state).
    assert cache.seq_len == 5
    assert attn.n_calls == 1
    teardown()


def test_fused_v2_manager_reset_clears_all_caches():
    """``manager.reset()`` calls ``reset`` on every per-layer cache."""
    import torch
    from kv_policy.int4_cache_kv_route_a import (
        install_int4_cache_kv_route_a, BACKEND_FUSED_V2,
    )

    model = _build_fake_vllm_model(num_layers=3)
    manager, teardown = install_int4_cache_kv_route_a(
        model=model,
        num_kv_heads=QWEN_NUM_KV_HEADS,
        kernel_backend=BACKEND_FUSED_V2,
        max_seq_len=32,
        protect_fraction=0.04,
        cache_k_group_size=1,
        cache_v_group_size=32,
    )
    for layer in model.layers:
        layer.attn.forward(_q_2d(4), _kv_2d(4), _kv_2d(4))
    for cache in manager.caches.values():
        assert cache.seq_len == 4
    manager.reset()
    for cache in manager.caches.values():
        assert cache.seq_len == 0
        assert not cache.is_frozen
        assert not cache.is_poisoned
        # Buffers retained.
        assert cache.is_allocated
    teardown()


def test_dequant_fallback_backend_unaffected_by_fused_v2_code():
    """Regression: the existing dequant_fallback backend behaviour is
    untouched by the fused_v2 addition. ``round_trip_kv`` still runs
    and the original forward sees lossy K/V."""
    import torch
    from kv_policy.int4_cache_kv_route_a import (
        install_int4_cache_kv_route_a, BACKEND_DEQUANT_FALLBACK,
    )

    model = _build_fake_vllm_model(num_layers=2)
    manager, teardown = install_int4_cache_kv_route_a(
        model=model,
        num_kv_heads=QWEN_NUM_KV_HEADS,
        kernel_backend=BACKEND_DEQUANT_FALLBACK,
    )
    assert manager.kernel_backend == BACKEND_DEQUANT_FALLBACK
    assert len(manager.caches) == 0   # never populated in dequant_fallback

    k = _kv_2d(8)
    v = _kv_2d(8)
    for layer in model.layers:
        layer.attn.forward(_q_2d(8), k, v)
        assert not torch.equal(layer.attn.received_k, k)   # rewritten

    assert manager.stats["forward_calls"] == 2
    assert manager.stats["fused_v2_decodes"] == 0
    assert len(manager.caches) == 0
    teardown()


def test_fused_v2_requires_max_seq_len():
    """Install with ``fused_v2`` but no ``max_seq_len`` raises."""
    from kv_policy.int4_cache_kv_route_a import (
        install_int4_cache_kv_route_a, BACKEND_FUSED_V2,
    )

    model = _build_fake_vllm_model(num_layers=1)
    with pytest.raises(ValueError, match=r"max_seq_len"):
        install_int4_cache_kv_route_a(
            model=model,
            num_kv_heads=QWEN_NUM_KV_HEADS,
            kernel_backend=BACKEND_FUSED_V2,
            cache_k_group_size=1,
        )


def test_fused_v2_refuses_non_v1_k_group_size():
    """Install with ``fused_v2`` and ``cache_k_group_size != 1`` raises
    — guards against accidentally claiming §20.4's group=32 throughput.
    """
    from kv_policy.int4_cache_kv_route_a import (
        install_int4_cache_kv_route_a, BACKEND_FUSED_V2,
    )

    model = _build_fake_vllm_model(num_layers=1)
    with pytest.raises(ValueError, match=r"cache_k_group_size=1"):
        install_int4_cache_kv_route_a(
            model=model,
            num_kv_heads=QWEN_NUM_KV_HEADS,
            kernel_backend=BACKEND_FUSED_V2,
            max_seq_len=32,
            cache_k_group_size=32,
        )
