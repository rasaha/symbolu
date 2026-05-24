"""Phase 5B.4c.2 — read-path verify.

Exercises the paged-cache → contiguous gather → packed-kernel path
end-to-end on synthetic K/V, comparing against Phase 5A's
flash_attn_with_int4_kvcache reference (BF16 K/V with the same
protect_mask + n_protect).

Three tests:
  T1: gather equivalence (no partial tail)
      Write S = 4 * BS = 128 tokens through PagedKVWriter into a paged
      uint8 cache. Gather. Run the packed kernel on the gathered view.
      Compare to Phase 5A reference on the original bf16 K/V.
      Gate: cosine >= 0.995.

  T2: partial-tail splice
      Write S = 2 * BS + 7 = 71 tokens. Splice the in-RAM staging buffer
      into the gathered view's last block. Run packed kernel with
      cache_seqlens=[71]. Compare to Phase 5A reference.
      Gate: cosine >= 0.995.

  T3: protect-mask wiring sanity
      Confirm the writer's per-layer protect mask is the same set of
      channels Phase 5A receives. Important because identical masks
      are required for the apples-to-apples comparison above.

Run on the pod:

  /workspace/venv-vllm/bin/python3 \
      /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase5b_4c_2_read.py
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

try:
    from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache
except ImportError as e:
    print(f"FAIL: can't import flash_attn_with_int4_kvcache: {e}")
    sys.exit(1)


# ----------------------------------------------------------------------
# Fixtures.
# ----------------------------------------------------------------------

QWEN_NUM_LAYERS = 28
QWEN_H_KV       = 4
QWEN_H_Q        = 28
QWEN_D          = 128
BS              = 32          # block_size = group_size = kInt4GroupSize
V_GROUP_SIZE    = 32
N_PROTECT       = 5

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
if DEVICE != "cuda":
    print("FAIL: this verify needs CUDA"); sys.exit(1)

DTYPE_BF = torch.bfloat16

COSINE_GATE = 0.995


def cosine(a: torch.Tensor, b: torch.Tensor) -> float:
    af = a.float().flatten()
    bf = b.float().flatten()
    return float(torch.nn.functional.cosine_similarity(af.unsqueeze(0), bf.unsqueeze(0)).item())


def _make_layer_protect_mask() -> torch.Tensor:
    """Build a deterministic (H_kv, D) int8 mask with the first
    N_PROTECT channels protected per head."""
    mask = torch.zeros((QWEN_H_KV, QWEN_D), dtype=torch.int8)
    for h in range(QWEN_H_KV):
        mask[h, :N_PROTECT] = 1
    return mask


def _make_protect_artifact() -> str:
    """Save (num_layers, H, D) artifact and set $PROTECT_MASK_PATH."""
    full = torch.zeros((QWEN_NUM_LAYERS, QWEN_H_KV, QWEN_D), dtype=torch.int8)
    layer_mask = _make_layer_protect_mask()
    for l in range(QWEN_NUM_LAYERS):
        full[l] = layer_mask
    fd, path = tempfile.mkstemp(suffix=".pt"); os.close(fd)
    torch.save(full, path)
    os.environ["PROTECT_MASK_PATH"] = path
    return path


# ----------------------------------------------------------------------
# Reference: Phase 5A path (BF16 K/V + in-register quant + protect-K).
# ----------------------------------------------------------------------

def _ref_phase5a(q, k_bf16, v_bf16, cache_seqlens, protect_mask_bhd) -> torch.Tensor:
    """Phase 5A reference call. Uses BF16 K/V; kernel quantizes in-register
    with the given protect_mask + n_protect."""
    return flash_attn_with_int4_kvcache(
        q, k_bf16, v_bf16,
        cache_seqlens=cache_seqlens,
        protect_mask=protect_mask_bhd,    # (B, H_kv, D) int8
        n_protect=N_PROTECT,
        causal=False,
    )


# ----------------------------------------------------------------------
# Driver under test: gather + packed-kernel call.
# ----------------------------------------------------------------------

def _packed_via_writer(
    writer: PagedKVWriter,
    kv_cache: torch.Tensor,
    q: torch.Tensor,
    cache_seqlens: torch.Tensor,
    do_splice_tail: bool,
) -> torch.Tensor:
    """Same logic as Int4ProtectedAttentionImpl._read_decode_packed.

    Gather the full sequence's blocks from kv_cache, optionally splice
    the partial K tail from writer.k_stage, and call the packed kernel.
    """
    from kv_policy.phase5b_backend_install import _splice_k_partial_tail

    seqlen = int(cache_seqlens[0].item())
    BS = writer.BS
    n_blocks_used = (seqlen + BS - 1) // BS
    block_ids = torch.arange(n_blocks_used, dtype=torch.long, device=DEVICE)
    S = n_blocks_used * BS

    view = writer.get_packed_view(block_ids, kv_cache)

    if do_splice_tail and (seqlen % BS) != 0:
        _splice_k_partial_tail(view, writer, last_block_idx=n_blocks_used - 1)

    dummy = torch.empty((1, S, writer.H, writer.D), dtype=DTYPE_BF, device=DEVICE)

    return flash_attn_with_int4_kvcache(
        q, dummy, dummy,
        cache_seqlens=cache_seqlens.to(torch.int32),
        softmax_scale=None,                       # default = D^-0.5
        causal=False,
        k_packed_int4=view["k_int4"].contiguous(),
        k_packed_scale=view["k_scale"].contiguous(),
        k_packed_xmin=view["k_xmin"].contiguous(),
        k_packed_protect_bf16=view["k_protect_bf16"].contiguous(),
        k_packed_protect_slot=view["protect_slot"].contiguous(),
        packed_group_size=BS,
        packed_n_protect=writer.n_protect,
        v_packed_int4=view["v_int4"].contiguous(),
        v_packed_scale=view["v_scale"].contiguous(),
        v_packed_xmin=view["v_xmin"].contiguous(),
        v_packed_group_size=writer.v_group_size,
    )


# ----------------------------------------------------------------------
# Tests.
# ----------------------------------------------------------------------

def test_full_groups(writer: PagedKVWriter, kv_cache: torch.Tensor) -> None:
    print("T1: gather equivalence (no partial tail) — S = 4 * BS = 128")
    writer.reset_sequence()
    kv_cache.zero_()

    S = 4 * BS
    torch.manual_seed(42)
    k_bf = torch.randn((1, S, QWEN_H_KV, QWEN_D), dtype=DTYPE_BF, device=DEVICE) * 0.5
    v_bf = torch.randn((1, S, QWEN_H_KV, QWEN_D), dtype=DTYPE_BF, device=DEVICE) * 0.5
    q    = torch.randn((1, 1, QWEN_H_Q, QWEN_D),  dtype=DTYPE_BF, device=DEVICE)

    # Write through PagedKVWriter, sequentially.
    slot_mapping = torch.arange(S, dtype=torch.long, device=DEVICE)
    writer.write(k_bf[0], v_bf[0], kv_cache, slot_mapping)

    # Reference: Phase 5A on original bf16 K/V.
    cache_seqlens = torch.tensor([S], dtype=torch.int32, device=DEVICE)
    # Phase 5A wants (B, H_kv, D) int8 protect_mask.
    protect_mask_bhd = writer.protect_mask.unsqueeze(0).to(DEVICE)  # (1, H, D)
    ref = _ref_phase5a(q, k_bf, v_bf, cache_seqlens, protect_mask_bhd)

    # Packed path through our gather.
    packed = _packed_via_writer(writer, kv_cache, q, cache_seqlens, do_splice_tail=False)

    cos = cosine(ref, packed)
    diff = (ref.float() - packed.float()).abs()
    print(f"  ref shape={tuple(ref.shape)}, packed shape={tuple(packed.shape)}")
    print(f"  cosine={cos:.7f}  max_abs={diff.max().item():.4e}  mean_abs={diff.mean().item():.4e}")
    assert cos >= COSINE_GATE, f"T1 cosine {cos:.6f} < {COSINE_GATE}"
    print(f"  PASS (cosine {cos:.6f} >= {COSINE_GATE})")


def test_partial_tail(writer: PagedKVWriter, kv_cache: torch.Tensor) -> None:
    print("T2: partial-tail splice — S = 2 * BS + 7 = 71")
    writer.reset_sequence()
    kv_cache.zero_()

    S = 2 * BS + 7
    torch.manual_seed(43)
    k_bf = torch.randn((1, S, QWEN_H_KV, QWEN_D), dtype=DTYPE_BF, device=DEVICE) * 0.5
    v_bf = torch.randn((1, S, QWEN_H_KV, QWEN_D), dtype=DTYPE_BF, device=DEVICE) * 0.5
    q    = torch.randn((1, 1, QWEN_H_Q, QWEN_D),  dtype=DTYPE_BF, device=DEVICE)

    slot_mapping = torch.arange(S, dtype=torch.long, device=DEVICE)
    writer.write(k_bf[0], v_bf[0], kv_cache, slot_mapping)

    state = writer.get_state()
    expected_tail = S % BS
    assert state["k_stage_count"] == expected_tail, (
        f"k_stage_count {state['k_stage_count']} != expected {expected_tail}"
    )

    cache_seqlens = torch.tensor([S], dtype=torch.int32, device=DEVICE)
    protect_mask_bhd = writer.protect_mask.unsqueeze(0).to(DEVICE)
    ref = _ref_phase5a(q, k_bf, v_bf, cache_seqlens, protect_mask_bhd)

    packed = _packed_via_writer(writer, kv_cache, q, cache_seqlens, do_splice_tail=True)

    cos = cosine(ref, packed)
    diff = (ref.float() - packed.float()).abs()
    print(f"  cosine={cos:.7f}  max_abs={diff.max().item():.4e}  mean_abs={diff.mean().item():.4e}")
    assert cos >= COSINE_GATE, f"T2 cosine {cos:.6f} < {COSINE_GATE}"
    print(f"  PASS (cosine {cos:.6f} >= {COSINE_GATE})")


def test_protect_mask_wiring(writer: PagedKVWriter) -> None:
    print("T3: protect-mask wiring sanity")
    # writer.protect_mask should equal what we built; n_protect=5; first
    # 5 channels protected per head.
    expected = _make_layer_protect_mask().to(writer.protect_mask.device)
    assert torch.equal(writer.protect_mask, expected), "protect_mask mismatch"
    assert writer.n_protect == N_PROTECT, f"n_protect {writer.n_protect} != {N_PROTECT}"
    for h in range(QWEN_H_KV):
        slots = writer.protect_slot[h]
        for d in range(QWEN_D):
            s_idx = int(slots[d].item())
            if d < N_PROTECT:
                assert s_idx == d, f"slot mismatch at h={h}, d={d}: got {s_idx}"
            else:
                assert s_idx == -1, f"unexpected protect slot at h={h}, d={d}"
    print(f"  PASS — protect_mask + n_protect={N_PROTECT} + protect_slot consistent.")


# ----------------------------------------------------------------------
# Driver.
# ----------------------------------------------------------------------

def main() -> int:
    print("==== Phase 5B.4c.2 read-path verify ====")
    print(f"device={DEVICE}  torch={torch.__version__}")
    print(f"BS={BS}  H_kv={QWEN_H_KV}  D={QWEN_D}  N_PROTECT={N_PROTECT}")

    artifact = _make_protect_artifact()
    try:
        NB = 4  # enough for the largest test (S=128 -> 4 blocks at BS=32)
        kv_cache = torch.zeros(
            (2, NB, BS, QWEN_H_KV, QWEN_D), dtype=torch.uint8, device=DEVICE,
        )
        writer = PagedKVWriter(layer_idx=0)

        # Force lazy-alloc.
        writer._lazy_alloc(kv_cache)

        test_protect_mask_wiring(writer)
        test_full_groups(writer, kv_cache)
        test_partial_tail(writer, kv_cache)

        print("\n==== Phase 5B.4c.2 ALL PASS ====")
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
