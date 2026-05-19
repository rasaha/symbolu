"""CPU regression tests for the §20.6 Marlin-style fused unpack-attend
kernel sketch (`kv_policy.int4_fused_attention_sketch`).

Pins:

* The fused reference produces output that exactly matches the naive
  "dequant K, dequant V, attention" pipeline (bit-identical within
  FP16 rounding) when fed K/V quantized through the route-B
  `quantize_per_channel_int4` / `quantize_per_token_int4` ops.
  This is the SPEC the CUDA/Triton kernel must match. A kernel
  author who implements the wrong asymmetric formula would fail
  this test.

* GQA broadcasting invariant: query heads in the same GQA group
  (sharing one KV head) produce identical outputs when their query
  vectors are identical. Catches GQA-layout regressions.

* Byte-nibble layout: `_unpack_int4_inline` is bit-identical to
  `int4_per_channel_kv.unpack_int4` on every value in the byte's
  uint8 range. Catches the class of bugs where someone swaps
  low/high nibble or forgets the +8 shift.

* HBM byte counter symmetric and asymmetric paths produce different
  results; asymmetric is correctly larger by the offset overhead.
  This pins the M1 audit fix.

* `speedup_ceiling` at the §18.3 ship config (asymmetric=True) is
  the partner-shareable number; pinned at 3.20× at the documented
  Qwen shape so a future doc-vs-code drift triggers here.
"""

from __future__ import annotations

import pytest


pytest.importorskip("torch")


def _qwen_shape():
    return dict(B=1, H_q=28, H_kv=4, S_q=1, S_kv=64, D=128,
                group_size_k=32, group_size_v=32)


def test_round_trip_matches_naive_pipeline():
    """The fused reference must produce identical output to a naive
    dequant-K + dequant-V + standard-attention pipeline when both
    consume the same quantized representation.

    This is the regression that catches H1 (the audit's
    wrong-asymmetric-formula bug): a kernel that implements
    `(x_int4 + 8) * scale + offset` instead of `x_int4 * scale + offset`
    would land off by +8*scale per element and fail this test.
    """
    import torch
    from kv_policy.int4_fused_attention_sketch import _round_trip_demo
    result = _round_trip_demo()
    # Output shape contract.
    assert result["output_shape"] == (1, 28, 1, 128)
    assert result["output_dtype"] == "torch.float16"
    # Numerical contract: the fused reference and the naive pipeline
    # consume the same quantized data; they must produce numerically
    # equivalent output. FP16 rounding tolerance is small.
    assert result["max_abs_diff_vs_naive"] < 1e-3, (
        f"Fused reference diverges from naive pipeline by "
        f"max_abs={result['max_abs_diff_vs_naive']:.6f}. The wrong-"
        f"asymmetric-formula regression would land here at ~8*scale "
        f"per element."
    )
    assert result["cosine_similarity_vs_naive"] >= 0.9999, (
        f"Fused reference cosine vs naive = "
        f"{result['cosine_similarity_vs_naive']:.6f}; expected ≥ 0.9999."
    )


def test_unpack_int4_inline_matches_pack_unpack_round_trip():
    """`_unpack_int4_inline` in the sketch must produce the same int8
    output as `pack_int4` followed by `unpack_int4` from int4_per_channel_kv.

    Probes every byte value (0-255) to make sure no nibble layout
    regression slips through.
    """
    import torch
    from kv_policy.int4_per_channel_kv import pack_int4, unpack_int4
    from kv_policy.int4_fused_attention_sketch import _unpack_int4_inline

    # Walk every possible nibble pair (both nibbles in [-8, +7]).
    pairs = []
    for low in range(-8, 8):
        for high in range(-8, 8):
            pairs.append((low, high))
    flat = torch.tensor(
        [v for pair in pairs for v in pair], dtype=torch.int8,
    )
    # Pack and unpack via the route-B path.
    packed = pack_int4(flat)
    unpacked_route_b = unpack_int4(packed, target_n=flat.shape[-1])
    # Compare against the sketch's _unpack_int4_inline.
    unpacked_sketch = _unpack_int4_inline(packed, target_n=flat.shape[-1])
    assert torch.equal(unpacked_route_b, unpacked_sketch), (
        "Sketch's _unpack_int4_inline diverges from route-B's "
        "unpack_int4. Either the nibble layout flipped or the +8 "
        "shift is missing on one side."
    )
    # And both must round-trip back to the original.
    assert torch.equal(unpacked_route_b, flat)


def test_gqa_broadcast_groups_share_outputs():
    """GQA invariant: when query heads in the same GQA group are
    identical, their attention outputs must be identical (since they
    all consume the same KV head). Catches GQA layout regressions
    (e.g., a swapped axis in the GQA broadcast reshape).
    """
    import torch
    from kv_policy.int4_fused_attention_sketch import (
        fused_int4_attention_reference, FusedAttentionSpec,
    )

    shape = _qwen_shape()
    B, H_q, H_kv = shape["B"], shape["H_q"], shape["H_kv"]
    S_q, S_kv, D = shape["S_q"], shape["S_kv"], shape["D"]
    gk, gv = shape["group_size_k"], shape["group_size_v"]
    G_q = H_q // H_kv

    torch.manual_seed(42)
    # Make first G_q query heads identical; the rest can vary.
    q = torch.randn(B, H_q, S_q, D, dtype=torch.float16)
    q[:, :G_q, :, :] = q[:, 0:1, :, :].expand(B, G_q, S_q, D)

    n_groups_k = S_kv // gk
    n_groups_v = D // gv
    k_packed = torch.randint(0, 256, (B, H_kv, S_kv, D // 2), dtype=torch.uint8)
    v_packed = torch.randint(0, 256, (B, H_kv, S_kv, D // 2), dtype=torch.uint8)
    k_scale = torch.randn(B, n_groups_k, H_kv, D, dtype=torch.float16).abs() * 0.1
    k_offset = torch.randn(B, n_groups_k, H_kv, D, dtype=torch.float16) * 0.1
    v_scale = torch.randn(B, S_kv, H_kv, n_groups_v, dtype=torch.float16).abs() * 0.1
    v_offset = torch.randn(B, S_kv, H_kv, n_groups_v, dtype=torch.float16) * 0.1

    spec = FusedAttentionSpec(
        B=B, H_q=H_q, H_kv=H_kv, S_q=S_q, S_kv=S_kv, D=D,
        block_size=16, group_size_k=gk, group_size_v=gv, asymmetric=True,
    )
    out = fused_int4_attention_reference(
        q=q, k_packed=k_packed, k_scale=k_scale, k_offset=k_offset,
        v_packed=v_packed, v_scale=v_scale, v_offset=v_offset, spec=spec,
    )
    # First G_q query heads share KV head 0 → outputs must be equal.
    for i in range(1, G_q):
        assert torch.allclose(out[:, i], out[:, 0], atol=1e-3), (
            f"Q head {i} (in GQA group 0) diverges from head 0; GQA "
            f"broadcast or reshape is wrong."
        )


def test_hbm_counter_asymmetric_larger_than_symmetric():
    """Asymmetric quant stores BOTH scale AND offset; the byte counter
    must reflect that. Pinning this prevents the M1 audit regression
    (3.56× was symmetric-only; 3.20× is the §18.3 ship config).
    """
    from kv_policy.int4_fused_attention_sketch import (
        hbm_bytes_for_attention, speedup_ceiling,
    )
    sym = hbm_bytes_for_attention(
        B=1, H_kv=4, S_kv=64, D=128, int4=True, asymmetric=False,
    )
    asym = hbm_bytes_for_attention(
        B=1, H_kv=4, S_kv=64, D=128, int4=True, asymmetric=True,
    )
    # Asymmetric has roughly the same value bytes (32k) + scale + offset
    # vs symmetric's value bytes (32k) + scale only.
    assert asym > sym, (
        f"asymmetric ({asym}) should exceed symmetric ({sym}) by the "
        f"offset-storage overhead"
    )
    # The gap should be roughly the scale-storage size (the offset
    # storage duplicates it).
    scale_only_bytes = sym - 2 * 1 * 4 * 64 * 128 // 2  # subtract values
    extra_for_offset = asym - sym
    assert abs(extra_for_offset - scale_only_bytes) < 100, (
        f"Asymmetric extra ({extra_for_offset}) should be ~equal to "
        f"the scale-storage size ({scale_only_bytes})."
    )


def test_speedup_ceiling_default_is_318_to_322():
    """Pin the §18.3 ship-config (asymmetric=True) speedup ceiling at
    ~3.20× on the documented Qwen shape. If this number drifts the
    partner-shareable claim in PHASE4_GPU_FINDINGS §20.6 needs updating.
    """
    from kv_policy.int4_fused_attention_sketch import speedup_ceiling
    # Default = asymmetric (matches §18.3 ship config).
    ceiling = speedup_ceiling(B=1, H_kv=4, S_kv=64, D=128)
    assert 3.18 <= ceiling <= 3.22, (
        f"Default speedup ceiling = {ceiling:.4f}; expected 3.20 ± 0.02. "
        f"If you intentionally changed group_size or asymmetric defaults, "
        f"update this test AND the §20.6 partner-shareable claim."
    )
    # Symmetric-only is higher (no offset storage).
    sym_ceiling = speedup_ceiling(
        B=1, H_kv=4, S_kv=64, D=128, asymmetric=False,
    )
    assert sym_ceiling > ceiling
    assert 3.55 <= sym_ceiling <= 3.58


def test_speedup_ceiling_protected_k_4pct_near_uniform():
    """§20.4.2 outlier-protected-K (top 4% of K channels FP16) keeps a
    HBM-traffic ceiling close to uniform INT4 — the mixed FP16+INT4 K
    layout does not kill the fused kernel's bandwidth advantage. This
    is the Exp-6 go/no-go input: a kernel for protected-K is worth
    building, ~as much as for uniform INT4.
    """
    from kv_policy.int4_fused_attention_sketch import speedup_ceiling
    uniform = speedup_ceiling(B=1, H_kv=4, S_kv=64, D=128)
    protected = speedup_ceiling(
        B=1, H_kv=4, S_kv=64, D=128, k_protect_fraction=0.04,
    )
    # Protecting 4% of K channels at FP16 costs only a little ceiling.
    assert protected < uniform, "protection must cost some bandwidth"
    assert 2.9 <= protected <= 3.15, (
        f"protected-K 4% ceiling = {protected:.4f}; expected ~3.07. "
        f"If this drifts, update the §20.4.2 / Exp-6 throughput claim."
    )
    # The gap vs uniform must be small — that is the whole point.
    assert (uniform - protected) < 0.25


def test_fused_reference_handles_symmetric_no_offset():
    """The reference must work with `asymmetric=False` (offsets None).
    Pins that the symmetric branch isn't accidentally broken when the
    asymmetric branch is touched.
    """
    import torch
    from kv_policy.int4_fused_attention_sketch import (
        fused_int4_attention_reference, FusedAttentionSpec,
    )
    shape = _qwen_shape()
    B, H_q, H_kv = shape["B"], shape["H_q"], shape["H_kv"]
    S_q, S_kv, D = shape["S_q"], shape["S_kv"], shape["D"]
    gk, gv = shape["group_size_k"], shape["group_size_v"]
    n_groups_k = S_kv // gk
    n_groups_v = D // gv

    torch.manual_seed(0)
    q = torch.randn(B, H_q, S_q, D, dtype=torch.float16)
    k_packed = torch.randint(0, 256, (B, H_kv, S_kv, D // 2), dtype=torch.uint8)
    v_packed = torch.randint(0, 256, (B, H_kv, S_kv, D // 2), dtype=torch.uint8)
    k_scale = torch.randn(B, n_groups_k, H_kv, D, dtype=torch.float16).abs() * 0.1
    v_scale = torch.randn(B, S_kv, H_kv, n_groups_v, dtype=torch.float16).abs() * 0.1

    spec = FusedAttentionSpec(
        B=B, H_q=H_q, H_kv=H_kv, S_q=S_q, S_kv=S_kv, D=D,
        block_size=16, group_size_k=gk, group_size_v=gv, asymmetric=False,
    )
    out = fused_int4_attention_reference(
        q=q, k_packed=k_packed, k_scale=k_scale, k_offset=None,
        v_packed=v_packed, v_scale=v_scale, v_offset=None, spec=spec,
    )
    assert out.shape == (B, H_q, S_q, D)
    assert torch.isfinite(out).all()
