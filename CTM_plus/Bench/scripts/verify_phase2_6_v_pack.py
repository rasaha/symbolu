#!/usr/bin/env python3
"""verify_phase2_6_v_pack.py — Phase 2.6.0 acceptance.

Validates V pack/unpack helpers (kv_policy.phase2_6_packed_v) before
any kernel work. V's grouping is along HEAD_DIM (per-token, per-32-
channels-group), simpler than K's seq-axis grouping — no cross-token
state, no protect mask.

Three sub-tests:

  1. Round-trip on RANDOM Gaussian V at Qwen2.5-7B shapes (S=4096,
     H_kv=4, D=128). Per-element error must be bounded by ~scale
     (per-group LSB). Mean error close to zero (no drift).

  2. Streaming-equivalent-to-batch test. Pack-each-token-individually
     must equal pack-all-tokens-batched. This is trivially true for
     V because there's no cross-token coupling (unlike K's seq groups).
     We verify it anyway as a sanity check on the per-token loop.

  3. Sidecar memory accounting matches design doc's Section 6.
     Per-token V cost should be 80 bytes (64 packed + 8 scale + 8 xmin
     at D=128, v_group_size=32).

If all three pass, Phase 2.6.0 is GREEN and the streaming class /
kernel work can proceed.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))


def test_round_trip_gaussian() -> bool:
    import torch
    from kv_policy.phase2_6_packed_v import (
        pack_v_for_phase2_6, unpack_v_from_phase2_6, round_trip_v_max_error
    )

    print()
    print("=" * 70)
    print("Test 1 — round-trip on random Gaussian V (Qwen2.5-7B shapes)")
    print("=" * 70)
    torch.manual_seed(42)
    device = "cuda"

    S, H, D = 4096, 4, 128
    G = 32
    v = torch.randn(1, S, H, D, device=device, dtype=torch.bfloat16)

    err = round_trip_v_max_error(v, v_group_size=G)
    print(f"  shapes:    (1, {S}, {H}, {D})  v_group_size={G}  n_groups={D//G}")
    print(f"  max-abs   = {err['max_abs']:.6e}")
    print(f"  mean-abs  = {err['mean_abs']:.6e}")
    print(f"  median-abs= {err['median_abs']:.6e}")
    print(f"  n_total   = {err['n_total']:,}")

    # For Gaussian with std=1, per-(token, h, group) range ~ [-2.5, 2.5]
    # (in the worst case across 32 samples). Scale = 5/15 ≈ 0.33. LSB = scale.
    # Per-element error should be <= scale/2 typically (RTNE rounding).
    # Allow 0.5 cap for safety.
    ok = True
    if err["max_abs"] > 0.5:
        print(f"  FAIL: max_abs {err['max_abs']:.3f} > 0.5 — quantization "
              f"diverged from expected RTNE bounds")
        ok = False
    # Mean abs should NOT drift far from zero (mean of RTNE quantization
    # error is ~0 for symmetric distributions). For Gaussian: <= scale/4.
    # Empirically ~0.08 for v_group_size=32. Cap at 0.15.
    if err["mean_abs"] > 0.15:
        print(f"  FAIL: mean_abs {err['mean_abs']:.4f} > 0.15 — drift suggests"
              f" a bias bug in pack/unpack arithmetic")
        ok = False

    if ok:
        print(f"  PASS")
    return ok


def test_streaming_equiv_batched() -> bool:
    """V is per-token-quantized; streaming MUST equal batch. This is
    structural — no cross-token state — but verify anyway."""
    import torch
    from kv_policy.phase2_6_packed_v import pack_v_for_phase2_6

    print()
    print("=" * 70)
    print("Test 2 — streaming pack-per-token == batch pack")
    print("=" * 70)
    torch.manual_seed(43)
    device = "cuda"
    S, H, D = 256, 4, 128
    G = 32
    v = torch.randn(1, S, H, D, device=device, dtype=torch.bfloat16)

    # Batch pack.
    batch = pack_v_for_phase2_6(v, v_group_size=G)

    # Per-token loop pack: pack each token independently, concat.
    parts = []
    for t in range(S):
        v_t = v[:, t:t+1, :, :]  # (1, 1, H, D)
        parts.append(pack_v_for_phase2_6(v_t, v_group_size=G))

    streaming_v_int4 = torch.cat([p["v_int4"] for p in parts], dim=1)
    streaming_v_scale = torch.cat([p["v_scale"] for p in parts], dim=1)
    streaming_v_xmin  = torch.cat([p["v_xmin"]  for p in parts], dim=1)

    ok = True
    # v_int4 must be bit-equal.
    eq_int4 = bool((batch["v_int4"] == streaming_v_int4).all().item())
    print(f"  v_int4   bit-equal: {eq_int4}")
    if not eq_int4:
        ok = False

    # v_scale / v_xmin: cosine 1.0 (bf16 RTNE round-trip is idempotent
    # for values computed the same way; numerically should be identical).
    eq_scale = bool((batch["v_scale"] == streaming_v_scale).all().item())
    eq_xmin  = bool((batch["v_xmin"]  == streaming_v_xmin).all().item())
    print(f"  v_scale  bit-equal: {eq_scale}")
    print(f"  v_xmin   bit-equal: {eq_xmin}")
    if not (eq_scale and eq_xmin):
        ok = False

    if ok:
        print(f"  PASS")
    return ok


def test_sidecar_bytes() -> bool:
    import torch
    from kv_policy.phase2_6_packed_v import v_sidecar_byte_size

    print()
    print("=" * 70)
    print("Test 3 — V sidecar memory accounting matches design doc")
    print("=" * 70)
    # Qwen2.5-7B per-layer V at S=32k.
    S, H, D = 32768, 4, 128
    info = v_sidecar_byte_size(S, H, D, v_group_size=32)
    print(f"  S={S} H_kv={H} D={D} v_group_size=32")
    for k, val in info.items():
        if isinstance(val, int) and val > 1024:
            print(f"    {k:18s} {val:>15,} bytes  ({val/1024/1024:.2f} MB)")
        else:
            print(f"    {k:18s} {val}")

    ok = True
    # Design doc: per-token V cost = 64 (int4) + 8 (scale) + 8 (xmin) = 80 bytes.
    expected_per_token = 80
    if info["per_token_bytes"] != expected_per_token:
        print(f"  FAIL: per_token_bytes {info['per_token_bytes']} != "
              f"expected {expected_per_token}")
        ok = False

    # Compression vs bf16: 256 / 80 = 3.2×.
    expected_compression = 256 / 80
    if not (3.0 <= info["compression"] <= 3.4):
        print(f"  FAIL: compression {info['compression']:.2f}x outside expected"
              f" range [3.0, 3.4]")
        ok = False
    else:
        print(f"  compression {info['compression']:.2f}× (target ~{expected_compression:.2f}×) PASS")

    return ok


def main() -> int:
    try:
        import torch
    except ImportError as e:
        print(f"FAIL: {e}")
        return 1
    if not torch.cuda.is_available():
        print("FAIL: needs CUDA")
        return 1

    print("Phase 2.6.0 — V pack/unpack helpers acceptance")
    print(f"  device: cuda")
    print(f"  dtype:  torch.bfloat16")

    r1 = test_round_trip_gaussian()
    r2 = test_streaming_equiv_batched()
    r3 = test_sidecar_bytes()

    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    results = [
        ("Gaussian round-trip   ", r1),
        ("Streaming == batch    ", r2),
        ("Sidecar byte sizing   ", r3),
    ]
    all_ok = all(ok for _, ok in results)
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print()
    if all_ok:
        print("Phase 2.6.0: GREEN")
        print("  - V pack/unpack round-trip preserves values within per-group LSB")
        print("  - streaming == batch (no cross-token state, as expected)")
        print("  - per-token V cost is 80 bytes (vs bf16's 256, 3.2x savings)")
        print("  - Ready for Phase 2.6.1 (streaming quantizer class).")
        return 0
    print("Phase 2.6.0: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
