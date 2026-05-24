#!/usr/bin/env python3
"""verify_phase2_6_1_streaming.py — Phase 2.6.1 acceptance.

Validates ValueGroupQuantizer against pack_v_for_phase2_6 bit-equivalence.
V's grouping is along HEAD_DIM (no cross-token state), so streaming
must be bit-identical to batch — much simpler than K's Phase 5B.1
verify which had to handle partial groups and flush.

Three sub-tests:

  1. Token-by-token streaming: append T=1 at a time for S tokens,
     compare to a single batch pack of the same V.

  2. Batched chunks: append in varied chunk sizes (3, 17, 32, 1, 12, ...)
     summing to S, compare to batch.

  3. Single-token edge case: append T=1 with S_total=1. Verifies the
     vectorized math handles the degenerate batch case.

ALL three must be bit-equal on v_int4 / v_scale / v_xmin. There's no
cross-token state, so any non-bit-equal result indicates a logic bug
in the append code (e.g., wrong slice indices, dtype drift).
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


def _compare_packed(label: str, candidate: dict, ground_truth: dict, S: int) -> bool:
    """Compare packed dicts on the first S tokens. The streaming quantizer
    output has max_seqlen-sized tensors with zeros past s_curr; we only
    compare the [:S] slice."""
    import torch
    ok = True
    print(f"  [{label}]")
    for key in ("v_int4", "v_scale", "v_xmin"):
        a = candidate[key][:, :S]
        b = ground_truth[key][:, :S]
        if a.shape != b.shape:
            print(f"    FAIL [{key:10s}] shape {tuple(a.shape)} != {tuple(b.shape)}")
            ok = False
            continue
        eq = bool((a == b).all().item())
        print(f"    [{key:10s}] dtype={a.dtype}, shape={tuple(a.shape)}, "
              f"bit-equal={eq}")
        if not eq:
            ok = False
            diff = (a != b).nonzero(as_tuple=False)
            print(f"      first 3 mismatch idx: {diff[:3].tolist()}")
    if candidate["v_group_size"] != ground_truth["v_group_size"]:
        print(f"    FAIL [v_group_size] {candidate['v_group_size']} != "
              f"{ground_truth['v_group_size']}")
        ok = False
    return ok


def test_token_by_token() -> bool:
    import torch
    from kv_policy.phase2_6_packed_v import pack_v_for_phase2_6
    from kv_policy.phase2_6_streaming_v_quantizer import ValueGroupQuantizer

    print()
    print("=" * 70)
    print("Test 1 — token-by-token streaming")
    print("=" * 70)
    device = "cuda"
    H, D, G = 4, 128, 32
    S = 256
    torch.manual_seed(10)
    v = torch.randn(1, S, H, D, device=device, dtype=torch.bfloat16)

    ref = pack_v_for_phase2_6(v, v_group_size=G)

    quant = ValueGroupQuantizer(
        num_kv_heads=H, head_dim=D, max_seqlen=S, v_group_size=G,
    )
    for t in range(S):
        v_t = v[:, t:t+1, :, :].squeeze(0)  # (1, H, D)
        quant.append(v_t)
    candidate = quant.get_packed()
    return _compare_packed("token-by-token vs batch", candidate, ref, S)


def test_batched_chunks() -> bool:
    import torch
    from kv_policy.phase2_6_packed_v import pack_v_for_phase2_6
    from kv_policy.phase2_6_streaming_v_quantizer import ValueGroupQuantizer

    print()
    print("=" * 70)
    print("Test 2 — batched-chunk streaming (varied chunk sizes)")
    print("=" * 70)
    device = "cuda"
    H, D, G = 4, 128, 32
    S = 256
    torch.manual_seed(20)
    v = torch.randn(1, S, H, D, device=device, dtype=torch.bfloat16)

    ref = pack_v_for_phase2_6(v, v_group_size=G)

    # Varied chunk sizes — including 1, exact group_size, larger than group_size.
    chunks = [3, 17, 32, 1, 12, 50, 5, 100, 1, 1, 34]
    assert sum(chunks) == S, f"chunks sum {sum(chunks)} != S={S}"

    quant = ValueGroupQuantizer(
        num_kv_heads=H, head_dim=D, max_seqlen=S, v_group_size=G,
    )
    pos = 0
    for c in chunks:
        chunk = v[0, pos:pos+c, :, :]  # (c, H, D)
        quant.append(chunk)
        pos += c
    candidate = quant.get_packed()
    return _compare_packed("varied chunks vs batch", candidate, ref, S)


def test_single_token() -> bool:
    import torch
    from kv_policy.phase2_6_packed_v import pack_v_for_phase2_6
    from kv_policy.phase2_6_streaming_v_quantizer import ValueGroupQuantizer

    print()
    print("=" * 70)
    print("Test 3 — single-token append (edge case S=1)")
    print("=" * 70)
    device = "cuda"
    H, D, G = 4, 128, 32
    torch.manual_seed(30)
    v = torch.randn(1, 1, H, D, device=device, dtype=torch.bfloat16)

    ref = pack_v_for_phase2_6(v, v_group_size=G)

    quant = ValueGroupQuantizer(
        num_kv_heads=H, head_dim=D, max_seqlen=1, v_group_size=G,
    )
    quant.append(v[0])  # (1, H, D)
    candidate = quant.get_packed()
    return _compare_packed("S=1 edge case", candidate, ref, 1)


def main() -> int:
    try:
        import torch
    except ImportError as e:
        print(f"FAIL: {e}")
        return 1
    if not torch.cuda.is_available():
        print("FAIL: needs CUDA")
        return 1

    print("=" * 70)
    print("Phase 2.6.1 — ValueGroupQuantizer round-trip verify")
    print("=" * 70)

    results = [
        ("token-by-token",   test_token_by_token()),
        ("batched chunks",   test_batched_chunks()),
        ("single-token S=1", test_single_token()),
    ]

    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    all_ok = True
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if not ok:
            all_ok = False
    print()
    if all_ok:
        print("Phase 2.6.1: GREEN")
        print("  - ValueGroupQuantizer streaming == batch (no cross-token state).")
        print("  - Ready for Phase 2.6.2 (kernel V load helper).")
        return 0
    print("Phase 2.6.1: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
