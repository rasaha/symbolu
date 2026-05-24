#!/usr/bin/env python3
"""verify_phase5b_1_streaming.py — Phase 5B.1 acceptance.

Validates PartialGroupQuantizer against pack_k_for_phase2_4 bit-equivalence
on three scenarios:

  Test 1 — Token-by-token streaming on S = multiple of group_size.
    Stream tokens one-at-a-time, compare to batch pack.
    Gate: bit-equal on k_int4 / protect_slot; cosine ≥ 0.99999 for bf16.

  Test 2 — Batched streaming (multiple tokens per append call).
    Stream in chunks of [3, 17, 32, 1, 12, ...] — varied chunk sizes,
    some crossing group boundaries.
    Gate: same as Test 1; verifies the per-token inner loop is correct
    regardless of how tokens arrive batched.

  Test 3 — Partial-group flush (S NOT a multiple of group_size).
    Stream S = 95 tokens with G = 16. After flush(), the last group
    has 1 real token + 15 zero-pads. Compare to pack_k_for_phase2_4
    of K padded to 96 with zeros.
    Gate: same as Test 1, on the padded K reference.

If all three pass, Phase 5B.1 is GREEN. PartialGroupQuantizer is
verified ready for integration in Phase 5B.4 (block-aware write path).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


def _cosine(a, b) -> float:
    import torch
    af = a.float().flatten()
    bf = b.float().flatten()
    return float(torch.nn.functional.cosine_similarity(
        af.unsqueeze(0), bf.unsqueeze(0)
    ).item())


def _compare_packed(label: str, candidate: dict, ground_truth: dict) -> bool:
    """Compare two packed-dict outputs. Returns True if all match."""
    import torch
    ok = True
    print(f"  [{label}]")
    for key in ("k_int4", "k_scale", "k_xmin", "k_protect_bf16", "protect_slot"):
        a = candidate[key]
        b = ground_truth[key]
        if a.shape != b.shape:
            print(f"    FAIL [{key:18s}] shape {tuple(a.shape)} != {tuple(b.shape)}")
            ok = False
            continue
        if a.dtype in (torch.uint8, torch.int8):
            eq = bool((a == b).all().item())
            print(f"    [{key:18s}] dtype={str(a.dtype):20s} shape={tuple(a.shape)} bit-equal={eq}")
            if not eq:
                ok = False
                diff = (a != b).nonzero(as_tuple=False)
                print(f"      first 3 mismatch idx: {diff[:3].tolist()}")
        else:
            cos = _cosine(a, b)
            maxd = float((a.float() - b.float()).abs().max().item())
            print(f"    [{key:18s}] dtype={str(a.dtype):20s} shape={tuple(a.shape)} "
                  f"cosine={cos:.7f} max-abs={maxd:.4e}")
            if cos < 0.99999 or maxd > 1e-3:
                ok = False
    # Compare scalar metadata
    for key in ("n_protect", "group_size"):
        if candidate[key] != ground_truth[key]:
            print(f"    FAIL [{key}] {candidate[key]} != {ground_truth[key]}")
            ok = False
    return ok


def _build_random_K(B, S, H, D, device, seed=0):
    import torch
    g = torch.Generator(device=device)
    g.manual_seed(seed)
    return torch.randn(B, S, H, D, generator=g, device=device, dtype=torch.bfloat16)


def _build_mask(H, D, n_protect, device, seed=1):
    """Random valid protect mask: top-n_protect channels per head."""
    import torch
    g = torch.Generator(device=device)
    g.manual_seed(seed)
    mag = torch.rand((H, D), generator=g, device=device)
    _, topk_idx = mag.topk(n_protect, dim=-1)
    mask = torch.zeros((H, D), dtype=torch.int8, device=device)
    mask.scatter_(-1, topk_idx, 1)
    return mask


def test_token_by_token() -> bool:
    import torch
    from kv_policy.phase2_4_packed_kv import pack_k_for_phase2_4
    from kv_policy.phase5b_streaming_quantizer import PartialGroupQuantizer

    print()
    print("=" * 70)
    print("Test 1 — token-by-token streaming (S multiple of G)")
    print("=" * 70)
    device = "cuda"
    H, D, G = 4, 128, 16
    S = 256  # 16 groups
    n_protect = 5

    K = _build_random_K(1, S, H, D, device, seed=10)
    mask = _build_mask(H, D, n_protect, device, seed=11)

    # Reference: batch pack.
    ref = pack_k_for_phase2_4(K, group_size=G, frozen_protect_mask=mask)

    # Streaming: append one token at a time.
    quant = PartialGroupQuantizer(
        num_kv_heads=H, head_dim=D, max_seqlen=S,
        protect_mask=mask, group_size=G,
    )
    for t in range(S):
        quant.append(K[:, t:t+1, :, :].squeeze(0))  # (1, H, D)
    # S is a multiple of G, so no flush needed (last group already finalized).
    candidate = quant.get_packed()

    return _compare_packed("token-by-token vs batch", candidate, ref)


def test_batched_appends() -> bool:
    import torch
    from kv_policy.phase2_4_packed_kv import pack_k_for_phase2_4
    from kv_policy.phase5b_streaming_quantizer import PartialGroupQuantizer

    print()
    print("=" * 70)
    print("Test 2 — batched-chunk streaming (varied chunk sizes)")
    print("=" * 70)
    device = "cuda"
    H, D, G = 4, 128, 16
    S = 256
    n_protect = 5

    K = _build_random_K(1, S, H, D, device, seed=20)
    mask = _build_mask(H, D, n_protect, device, seed=21)
    ref = pack_k_for_phase2_4(K, group_size=G, frozen_protect_mask=mask)

    # Varied chunk sizes — some smaller than G, some larger, some
    # exactly G, some crossing multiple group boundaries.
    chunks = [3, 17, 32, 1, 12, 50, 5, 100, 1, 1, S - (3+17+32+1+12+50+5+100+1+1)]
    assert sum(chunks) == S, f"chunk sizes sum to {sum(chunks)} != {S}"

    quant = PartialGroupQuantizer(
        num_kv_heads=H, head_dim=D, max_seqlen=S,
        protect_mask=mask, group_size=G,
    )
    pos = 0
    for c in chunks:
        chunk = K[0, pos:pos+c, :, :]  # (c, H, D)
        quant.append(chunk)
        pos += c
    candidate = quant.get_packed()

    return _compare_packed("varied chunks vs batch", candidate, ref)


def test_partial_group_flush() -> bool:
    """S is NOT a multiple of G: stream S tokens, flush() to finalize
    the partial group (which gets zero-padded). Compare to the batch
    pack of K_padded (where K_padded[S:] is zeros)."""
    import torch
    from kv_policy.phase2_4_packed_kv import pack_k_for_phase2_4
    from kv_policy.phase5b_streaming_quantizer import PartialGroupQuantizer

    print()
    print("=" * 70)
    print("Test 3 — partial-group flush (S not a multiple of G)")
    print("=" * 70)
    device = "cuda"
    H, D, G = 4, 128, 16
    S_real = 95
    S_padded = 96  # next multiple of G
    n_protect = 5

    # Real K of size S_real, plus zero-padding.
    K_real = _build_random_K(1, S_real, H, D, device, seed=30)
    K_padded = torch.cat([
        K_real,
        torch.zeros((1, S_padded - S_real, H, D),
                    dtype=K_real.dtype, device=device),
    ], dim=1)
    mask = _build_mask(H, D, n_protect, device, seed=31)
    # Reference: batch pack of the PADDED K (must use max_seqlen
    # divisible by G).
    ref = pack_k_for_phase2_4(K_padded, group_size=G, frozen_protect_mask=mask)

    # Streaming: append S_real real tokens, then flush.
    quant = PartialGroupQuantizer(
        num_kv_heads=H, head_dim=D, max_seqlen=S_padded,
        protect_mask=mask, group_size=G,
    )
    quant.append(K_real[0])   # (S_real, H, D), all in one batch
    print(f"    s_curr before flush: {quant.s_curr} (real), "
          f"tokens_in_buffer: {quant.tokens_in_buffer} "
          f"(partial group: {S_real % G} of {G})")
    quant.flush()
    print(f"    s_curr after flush:  {quant.s_curr} (unchanged), "
          f"tokens_in_buffer: {quant.tokens_in_buffer} (cleared)")
    candidate = quant.get_packed()

    # IMPORTANT: the streaming quantizer's k_protect_bf16 for positions
    # [S_real, S_padded) is ZERO (we never appended those tokens, the
    # output tensor is zero-init). The reference's k_protect_bf16 for
    # those positions is also ZERO (K_padded is zero there, gather of
    # zeros is zeros). So they match.
    return _compare_packed("partial-flush vs batch (padded)", candidate, ref)


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
    print("Phase 5B.1 — PartialGroupQuantizer round-trip verify")
    print("=" * 70)

    results = [
        ("token-by-token",     test_token_by_token()),
        ("batched chunks",     test_batched_appends()),
        ("partial-group flush", test_partial_group_flush()),
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
        print("Phase 5B.1: GREEN")
        return 0
    print("Phase 5B.1: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
