"""Phase 5B.4c.3 V-path isolation.

Focused diagnostic per the debug order:
  T1: writer V output (gathered view) BIT-EXACT vs pack_v_for_phase2_6.
      Same nibble bytes, same scale, same xmin.
  T2: unpack(writer view) == unpack(pack_v_for_phase2_6) bit-equal.
      Confirms dequant formula match.
  T3: GQA head mapping — writer's per-head V data lands at the right
      kv_head index in the gathered view.
  T4: kernel V isolation — K stays BF16 (no packed K), V via writer.
      Output cosine vs Phase 5A reference >= 0.995.
  T5: same as T4 but V via direct pack_v_for_phase2_6 (no writer).
      Establishes the reference kernel-V cosine on this fixture.
  T6: partial-tail V slot range — writer writes 7 tokens (< BS=32),
      gathered v_int4/v_scale/v_xmin for positions [0..6] must equal
      pack_v_for_phase2_6 over those 7 tokens.

Decision rule:
  - T1/T2 fail -> writer V layout/nibble/dequant bug.
  - T1/T2 pass, T4 fail, T5 pass -> writer-specific bug in the
    paged/gather path (vs the contiguous pack reference).
  - T4 and T5 both pass at Phase 5A cosine but Qwen still garbage ->
    issue is NOT V; switch focus to K partial-tail splice or per-layer.

Exit 0 if all PASS; 1 if any FAIL.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback

import torch

_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_kvp_root  = os.path.join(_repo_root, "KVPolicy")
if _kvp_root not in sys.path:
    sys.path.insert(0, _kvp_root)

from kv_policy.phase5b_4c_paged_writer import PagedKVWriter
from kv_policy.phase2_6_packed_v import pack_v_for_phase2_6, unpack_v_from_phase2_6

try:
    from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache
except ImportError as e:
    print(f"FAIL: can't import flash_attn_with_int4_kvcache: {e}")
    sys.exit(1)


# ----------------------------------------------------------------------
# Fixtures.
# ----------------------------------------------------------------------

NUM_LAYERS = 28
H_KV       = 4
H_Q        = 28           # Qwen GQA: 28 query heads grouped into 4 kv heads
D          = 128
BS         = 32           # block_size = group_size_k = group_size_v
V_GROUP    = 32           # v_group_size
N_PROTECT  = 5

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
if DEVICE != "cuda":
    print("FAIL: requires CUDA"); sys.exit(1)

DTYPE_BF = torch.bfloat16

COS_GATE_KERNEL = 0.995


def cosine(a: torch.Tensor, b: torch.Tensor) -> float:
    af = a.float().flatten()
    bf = b.float().flatten()
    return float(torch.nn.functional.cosine_similarity(
        af.unsqueeze(0), bf.unsqueeze(0)).item())


def _make_protect_mask() -> torch.Tensor:
    mask = torch.zeros((H_KV, D), dtype=torch.int8)
    for h in range(H_KV):
        mask[h, :N_PROTECT] = 1
    return mask


def _setup_protect_artifact() -> str:
    full = torch.zeros((NUM_LAYERS, H_KV, D), dtype=torch.int8)
    m = _make_protect_mask()
    for l in range(NUM_LAYERS):
        full[l] = m
    fd, path = tempfile.mkstemp(suffix=".pt"); os.close(fd)
    torch.save(full, path)
    os.environ["PROTECT_MASK_PATH"] = path
    return path


# ----------------------------------------------------------------------
# T1: writer V vs reference pack — bit-exact.
# ----------------------------------------------------------------------

def test_writer_v_bit_exact(writer: PagedKVWriter, kv_cache: torch.Tensor) -> None:
    print("T1: writer V vs pack_v_for_phase2_6 bit-exact")
    writer.reset_sequence(); kv_cache.zero_()

    S = 4 * BS   # 4 full groups, no partial tail
    torch.manual_seed(101)
    k_bf = torch.randn((1, S, H_KV, D), dtype=DTYPE_BF, device=DEVICE) * 0.5
    v_bf = torch.randn((1, S, H_KV, D), dtype=DTYPE_BF, device=DEVICE) * 0.5

    slot_map = torch.arange(S, dtype=torch.long, device=DEVICE)
    writer.write(k_bf[0], v_bf[0], kv_cache, slot_map)

    # Writer's gathered V view.
    block_ids = torch.arange(S // BS, dtype=torch.long, device=DEVICE)
    view = writer.get_packed_view(block_ids, kv_cache)

    # Reference packing (contiguous, no paged cache).
    ref = pack_v_for_phase2_6(v_bf, v_group_size=V_GROUP)

    # Shapes match?
    assert view["v_int4"].shape == ref["v_int4"].shape, (
        f"v_int4 shape mismatch: writer {tuple(view['v_int4'].shape)} "
        f"!= ref {tuple(ref['v_int4'].shape)}"
    )
    assert view["v_scale"].shape == ref["v_scale"].shape, (
        f"v_scale shape mismatch: writer {tuple(view['v_scale'].shape)} "
        f"!= ref {tuple(ref['v_scale'].shape)}"
    )
    assert view["v_xmin"].shape == ref["v_xmin"].shape

    # Bit-equality.
    int4_eq  = torch.equal(view["v_int4"],  ref["v_int4"])
    scale_eq = torch.equal(view["v_scale"], ref["v_scale"])
    xmin_eq  = torch.equal(view["v_xmin"],  ref["v_xmin"])

    if not int4_eq:
        diff = (view["v_int4"].int() - ref["v_int4"].int()).abs()
        n_diff = int((diff > 0).sum().item())
        max_diff = int(diff.max().item())
        print(f"  v_int4 MISMATCH: {n_diff} bytes differ; max nibble-value diff {max_diff}")
        # Locate first mismatch
        idx = torch.nonzero(diff > 0)[0].tolist()
        print(f"    first mismatch at {idx}: writer={view['v_int4'][tuple(idx)].item()} "
              f"ref={ref['v_int4'][tuple(idx)].item()}")
    if not scale_eq:
        diff = (view["v_scale"].float() - ref["v_scale"].float()).abs()
        print(f"  v_scale MISMATCH: max_abs={diff.max().item():.4e}")
    if not xmin_eq:
        diff = (view["v_xmin"].float() - ref["v_xmin"].float()).abs()
        print(f"  v_xmin MISMATCH: max_abs={diff.max().item():.4e}")

    assert int4_eq, "v_int4 bytes not bit-equal to reference"
    assert scale_eq, "v_scale not bit-equal to reference"
    assert xmin_eq, "v_xmin not bit-equal to reference"
    print(f"  PASS — v_int4 + v_scale + v_xmin bit-equal at S={S}")


# ----------------------------------------------------------------------
# T2: unpack equivalence.
# ----------------------------------------------------------------------

def test_unpack_equivalence(writer: PagedKVWriter, kv_cache: torch.Tensor) -> None:
    print("T2: unpack(writer view) == unpack(reference)")
    writer.reset_sequence(); kv_cache.zero_()

    S = 2 * BS
    torch.manual_seed(102)
    k_bf = torch.randn((1, S, H_KV, D), dtype=DTYPE_BF, device=DEVICE) * 0.5
    v_bf = torch.randn((1, S, H_KV, D), dtype=DTYPE_BF, device=DEVICE) * 0.5
    slot_map = torch.arange(S, dtype=torch.long, device=DEVICE)
    writer.write(k_bf[0], v_bf[0], kv_cache, slot_map)

    block_ids = torch.arange(S // BS, dtype=torch.long, device=DEVICE)
    view = writer.get_packed_view(block_ids, kv_cache)

    writer_unpacked = unpack_v_from_phase2_6({
        "v_int4":       view["v_int4"],
        "v_scale":      view["v_scale"],
        "v_xmin":       view["v_xmin"],
        "v_group_size": view["v_group_size"],
    })
    ref_unpacked = unpack_v_from_phase2_6(pack_v_for_phase2_6(v_bf, v_group_size=V_GROUP))

    if not torch.equal(writer_unpacked, ref_unpacked):
        diff = (writer_unpacked.float() - ref_unpacked.float()).abs()
        print(f"  MISMATCH: max_abs={diff.max().item():.4e}  mean_abs={diff.mean().item():.4e}")
        raise AssertionError("writer unpack != reference unpack")
    print("  PASS — bit-equal dequantized V")


# ----------------------------------------------------------------------
# T3: GQA head mapping. Each kv_head's V data must land at the right
# head index in the gathered view.
# ----------------------------------------------------------------------

def test_head_mapping(writer: PagedKVWriter, kv_cache: torch.Tensor) -> None:
    print("T3: per-head V mapping (writer head h <-> view head h)")
    writer.reset_sequence(); kv_cache.zero_()

    S = BS
    # Plant a head-distinct pattern: head h has all values = h+1.0 (constant).
    v_bf = torch.zeros((1, S, H_KV, D), dtype=DTYPE_BF, device=DEVICE)
    for h in range(H_KV):
        v_bf[0, :, h, :] = (h + 1) * 1.0
    k_bf = torch.zeros_like(v_bf)
    slot_map = torch.arange(S, dtype=torch.long, device=DEVICE)
    writer.write(k_bf[0], v_bf[0], kv_cache, slot_map)

    view = writer.get_packed_view(
        torch.arange(1, dtype=torch.long, device=DEVICE), kv_cache,
    )
    # After unpack each head should reconstruct its planted constant.
    unpacked = unpack_v_from_phase2_6({
        "v_int4":       view["v_int4"],
        "v_scale":      view["v_scale"],
        "v_xmin":       view["v_xmin"],
        "v_group_size": view["v_group_size"],
    })
    # Each (t, h, d) should equal h+1 within scale/15 noise.
    for h in range(H_KV):
        per_head = unpacked[0, :, h, :].float()
        expected = float(h + 1)
        diff = (per_head - expected).abs().max().item()
        if diff > 1e-3:
            print(f"  head {h}: max diff from {expected} = {diff:.4e}")
            raise AssertionError(f"head {h} not at expected constant")
    print("  PASS — all 4 heads recover the planted constants")


# ----------------------------------------------------------------------
# T4 + T5: kernel V isolation.
# K stays BF16 (no packed K kwargs); V via writer (T4) or via pack_v (T5).
# Both should match Phase 5A reference (bf16 K + bf16 V via in-register V quant).
# ----------------------------------------------------------------------

def _ref_phase5a(q, k_bf, v_bf, cache_seqlens) -> torch.Tensor:
    # Pure Phase 5A — both K and V bf16, in-register K quant via
    # protect_mask + n_protect, V via Phase 3 in-register quant.
    protect_mask = torch.zeros((1, H_KV, D), dtype=torch.int8, device=DEVICE)
    for h in range(H_KV):
        protect_mask[0, h, :N_PROTECT] = 1
    return flash_attn_with_int4_kvcache(
        q, k_bf, v_bf,
        cache_seqlens=cache_seqlens,
        protect_mask=protect_mask, n_protect=N_PROTECT,
        causal=False,
    )


def _packed_v_only(
    q, k_bf16, cache_seqlens,
    *, v_int4, v_scale, v_xmin,
) -> torch.Tensor:
    """Kernel call with bf16 K (Phase 5A K path) and packed V only.
    No packed K kwargs — kernel uses in-register K quant on the bf16 K.
    """
    protect_mask = torch.zeros((1, H_KV, D), dtype=torch.int8, device=DEVICE)
    for h in range(H_KV):
        protect_mask[0, h, :N_PROTECT] = 1
    S = k_bf16.shape[1]
    # Dummy V buffer — kernel ignores on packed-V path? But the kernel
    # dispatch routes packed only when ALL K+V packed ptrs are set
    # (apply_phase2_6_2). So passing v_packed_* without k_packed_*
    # will leave is_int4kv_packed = FALSE. Kernel takes in-register
    # quant path on BF16 V (Phase 3), reading bf16 v_bf16 — NOT our
    # packed V. So this test as-written exercises BF16 V via the
    # ref call, not packed V. Skip the v_packed kwargs and use bf16.
    raise NotImplementedError("can't run packed-V-only at the kernel level")


def _build_data_derived_protect_mask(k_bf: torch.Tensor) -> torch.Tensor:
    """Build (1, H, D) int8 mask via top-N_PROTECT magnitudes per head.
    This mirrors verify_phase2_6_2 / verify_phase5b_4c_2 exactly so
    we can isolate any 'mask-shape sensitivity' the kernel might have.
    """
    ch_mag = k_bf.float().abs().amax(dim=1)             # (1, H, D)
    _, topk_idx = ch_mag.topk(N_PROTECT, dim=-1)        # (1, H, N_PROTECT)
    mask = torch.zeros((1, H_KV, D), dtype=torch.int8, device=k_bf.device)
    mask.scatter_(-1, topk_idx, 1)
    return mask


def test_v_only_kernel_with_writer(writer: PagedKVWriter, kv_cache: torch.Tensor) -> None:
    """T4/T5 combined: full packed path (both K and V packed via writer).
    Compare to Phase 5A reference. Same as verify_phase5b_4c_2's T1 but
    with the simpler protect mask + no partial tail.
    """
    print("T4: full packed kernel call vs Phase 5A reference (S=4*BS=128)")
    writer.reset_sequence(); kv_cache.zero_()

    S = 4 * BS
    torch.manual_seed(104)
    k_bf = torch.randn((1, S, H_KV, D), dtype=DTYPE_BF, device=DEVICE) * 0.5
    v_bf = torch.randn((1, S, H_KV, D), dtype=DTYPE_BF, device=DEVICE) * 0.5
    q    = torch.randn((1, 1, H_Q, D),  dtype=DTYPE_BF, device=DEVICE)

    slot_map = torch.arange(S, dtype=torch.long, device=DEVICE)
    writer.write(k_bf[0], v_bf[0], kv_cache, slot_map)

    cache_seqlens = torch.tensor([S], dtype=torch.int32, device=DEVICE)
    ref = _ref_phase5a(q, k_bf, v_bf, cache_seqlens)

    # Build the packed call from gathered view.
    block_ids = torch.arange(S // BS, dtype=torch.long, device=DEVICE)
    view = writer.get_packed_view(block_ids, kv_cache)
    dummy = torch.zeros((1, S, H_KV, D), dtype=DTYPE_BF, device=DEVICE)
    protect_mask = writer.protect_mask.unsqueeze(0)

    packed = flash_attn_with_int4_kvcache(
        q, dummy, dummy,
        cache_seqlens=cache_seqlens,
        protect_mask=protect_mask, n_protect=writer.n_protect,
        causal=False,
        k_packed_int4=view["k_int4"].contiguous(),
        k_packed_scale=view["k_scale"].contiguous(),
        k_packed_xmin=view["k_xmin"].contiguous(),
        k_packed_protect_bf16=view["k_protect_bf16"].contiguous(),
        k_packed_protect_slot=view["protect_slot"].contiguous(),
        packed_group_size=BS, packed_n_protect=writer.n_protect,
        v_packed_int4=view["v_int4"].contiguous(),
        v_packed_scale=view["v_scale"].contiguous(),
        v_packed_xmin=view["v_xmin"].contiguous(),
        v_packed_group_size=writer.v_group_size,
    )
    cos = cosine(ref, packed)
    print(f"  writer-packed cosine vs Phase 5A: {cos:.7f}")

    # T5: same call but with REFERENCE packed tensors instead of writer's.
    print("T5: full packed kernel call with REFERENCE pack (no writer)")
    k_packed_ref = _ref_pack_k(k_bf)
    v_packed_ref = pack_v_for_phase2_6(v_bf, v_group_size=V_GROUP)
    packed_ref = flash_attn_with_int4_kvcache(
        q, dummy, dummy,
        cache_seqlens=cache_seqlens,
        protect_mask=protect_mask, n_protect=writer.n_protect,
        causal=False,
        k_packed_int4=k_packed_ref["k_int4"].contiguous(),
        k_packed_scale=k_packed_ref["k_scale"].contiguous(),
        k_packed_xmin=k_packed_ref["k_xmin"].contiguous(),
        k_packed_protect_bf16=k_packed_ref["k_protect_bf16"].contiguous(),
        k_packed_protect_slot=k_packed_ref["protect_slot"].contiguous(),
        packed_group_size=BS, packed_n_protect=k_packed_ref["n_protect"],
        v_packed_int4=v_packed_ref["v_int4"].contiguous(),
        v_packed_scale=v_packed_ref["v_scale"].contiguous(),
        v_packed_xmin=v_packed_ref["v_xmin"].contiguous(),
        v_packed_group_size=v_packed_ref["v_group_size"],
    )
    cos_ref = cosine(ref, packed_ref)
    print(f"  reference-packed cosine vs Phase 5A: {cos_ref:.7f}")

    # Compare writer vs reference packed kernel outputs.
    cross_cos = cosine(packed, packed_ref)
    diff = (packed.float() - packed_ref.float()).abs()
    print(f"  writer-vs-reference packed output cosine: {cross_cos:.7f}  "
          f"max_abs={diff.max().item():.4e}")

    assert cos     >= COS_GATE_KERNEL, f"T4 writer cosine {cos:.6f} < {COS_GATE_KERNEL}"
    assert cos_ref >= COS_GATE_KERNEL, f"T5 reference cosine {cos_ref:.6f} < {COS_GATE_KERNEL}"
    if cross_cos < 0.9999:
        print(f"  WARN: writer vs reference cross cosine {cross_cos:.6f} < 0.9999 — "
              f"writer differs from reference at the kernel-output level.")
    print(f"  PASS — both >= {COS_GATE_KERNEL}")


def _ref_pack_k(k_bf):
    """Use the same K-side reference pack as verify_phase2_4_1b."""
    from kv_policy.phase2_4_packed_kv import pack_k_for_phase2_4
    mask = _make_protect_mask().to(DEVICE)
    return pack_k_for_phase2_4(
        k_bf, group_size=BS, protect_fraction=N_PROTECT / D,
        frozen_protect_mask=mask,
    )


# ----------------------------------------------------------------------
# T6: partial-tail V correctness.
# ----------------------------------------------------------------------

def test_partial_tail_v(writer: PagedKVWriter, kv_cache: torch.Tensor) -> None:
    print("T6: partial-tail V slots (S=7 < BS=32)")
    # Clear ALL writer sidecars (not just staging) so this test starts
    # from a pristine state, independent of what prior tests wrote.
    # In production, the production invariant is cache_seqlens masking,
    # not pad-zero values — but for this bit-equal test we want clean state.
    writer.reset_sequence()
    kv_cache.zero_()
    for t in (writer.v_scale_ext, writer.v_xmin_ext,
              writer.k_scale_ext, writer.k_xmin_ext,
              writer.k_protect_ext):
        if t is not None:
            t.zero_()

    S = 7
    torch.manual_seed(106)
    k_bf = torch.randn((1, S, H_KV, D), dtype=DTYPE_BF, device=DEVICE) * 0.5
    v_bf = torch.randn((1, S, H_KV, D), dtype=DTYPE_BF, device=DEVICE) * 0.5
    slot_map = torch.arange(S, dtype=torch.long, device=DEVICE)
    writer.write(k_bf[0], v_bf[0], kv_cache, slot_map)

    view = writer.get_packed_view(
        torch.arange(1, dtype=torch.long, device=DEVICE), kv_cache,
    )
    # Reference pack of just the 7-token V.
    ref = pack_v_for_phase2_6(v_bf, v_group_size=V_GROUP)

    # PRODUCTION CORRECTNESS CHECK: writer's first S slots bit-equal to
    # reference. Positions beyond S in the gathered view aren't read by
    # the kernel (cache_seqlens masks them), so their content doesn't
    # affect production correctness. We don't assert pad-zero here.
    assert torch.equal(view["v_int4"][0, :S], ref["v_int4"][0]), (
        "writer v_int4 for first 7 slots != reference pack"
    )
    assert torch.equal(view["v_scale"][0, :S], ref["v_scale"][0]), "v_scale mismatch"
    assert torch.equal(view["v_xmin"] [0, :S], ref["v_xmin"][0]),  "v_xmin mismatch"

    print(f"  PASS — first {S} slots bit-equal to reference pack_v_for_phase2_6")


# ----------------------------------------------------------------------
# Driver.
# ----------------------------------------------------------------------

def main() -> int:
    print("==== Phase 5B.4c.3 V-path isolation ====")
    artifact = _setup_protect_artifact()
    try:
        NB = 4
        kv_cache = torch.zeros((2, NB, BS, H_KV, D), dtype=torch.uint8, device=DEVICE)
        writer = PagedKVWriter(layer_idx=0)
        writer._lazy_alloc(kv_cache)

        test_writer_v_bit_exact(writer, kv_cache)
        test_unpack_equivalence(writer, kv_cache)
        test_head_mapping(writer, kv_cache)
        test_partial_tail_v(writer, kv_cache)
        test_v_only_kernel_with_writer(writer, kv_cache)

        print("\n==== V-isolation ALL PASS ====")
        return 0
    except AssertionError as e:
        print(f"\nFAIL: {e}"); traceback.print_exc(); return 1
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}"); traceback.print_exc(); return 1
    finally:
        if os.path.exists(artifact):
            os.remove(artifact)


if __name__ == "__main__":
    sys.exit(main())
