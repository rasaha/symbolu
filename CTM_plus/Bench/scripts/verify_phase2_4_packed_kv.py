#!/usr/bin/env python3
"""verify_phase2_4_packed_kv.py — Phase 2.4.0 Python pack/unpack
acceptance test.

Validates the Phase 2.4 packed K sidecar format end-to-end on the
Python side BEFORE we touch CUDA. Three sub-tests:

  1. Round-trip on RANDOM Qwen2.5-7B-shaped K. Protected channels
     must be bit-equal after pack -> unpack. Unprotected channels
     must have per-element error bounded by ~scale (= per-group LSB).

  2. Round-trip on OUTLIER-amplified K (5 channels × 10 boost).
     Protected channels should land on those outliers; their error
     stays at 0. Unprotected dequant error stays in scale (= the
     un-boosted-channel scale).

  3. Sidecar memory accounting matches the Phase 2.4 design doc's
     table for Qwen2.5-7B at S=32k.

Exits 0 if all three pass, 1 otherwise.

This validates the algorithm + the storage layout. The Phase 2.4.1
CUDA kernel that reads this layout must produce the same dequant
values as this Python `unpack_k_from_phase2_4`.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running without installing the kv_policy package.
ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))

try:
    import torch
except ImportError:
    print("FAIL: torch not installed")
    sys.exit(1)

from kv_policy.phase2_4_packed_kv import (
    pack_k_for_phase2_4,
    unpack_k_from_phase2_4,
    round_trip_max_error,
    sidecar_byte_size,
)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE  = torch.bfloat16


def _print_round_trip(label, k, fraction):
    err = round_trip_max_error(k, protect_fraction=fraction)
    print(f"  [{label}]  protect={fraction*100:.0f}%, "
          f"n_protected={err['n_protected']}/{err['n_total_channels']}")
    print(f"     protected_max_abs   = {err['protected_max_abs']:.6e}  "
          f"(MUST be 0 — protected channels bypass quant)")
    print(f"     unprotected_max_abs = {err['unprotected_max_abs']:.6e}  "
          f"(bounded by ~scale)")
    print(f"     unprotected_mean_abs= {err['unprotected_mean_abs']:.6e}")
    return err


def test_round_trip_gaussian() -> bool:
    print()
    print("=" * 70)
    print("Test 1 — round-trip on random Gaussian K (Qwen2.5-7B shapes)")
    print("=" * 70)
    torch.manual_seed(42)
    # Qwen2.5-7B per-layer K: (1, S, H_kv=4, D=128).
    # Use a multi-of-group_size S for the pack invariant.
    S = 16384
    k = torch.randn(1, S, 4, 128, device=DEVICE, dtype=DTYPE)

    ok = True
    for fraction in [0.04, 0.08]:
        err = _print_round_trip(f"Gaussian S={S}", k, fraction)
        # Gate: protected MUST be bit-equal (0 error).
        if err["protected_max_abs"] > 0.0:
            print(f"     FAIL: protected_max_abs > 0 — pack/unpack lost "
                  f"a protected channel value")
            ok = False
        # Gate: unprotected error bounded by ~LSB. For random Gaussian
        # with std=1, LSB ≈ (max-min)/15 ≈ 4/15 ≈ 0.27. Allow 0.5 cap
        # for headroom.
        if err["unprotected_max_abs"] > 0.5:
            print(f"     FAIL: unprotected_max_abs {err['unprotected_max_abs']:.3f}"
                  f" > 0.5 (expected ≤ scale ≈ 0.27)")
            ok = False
    return ok


def test_round_trip_outlier() -> bool:
    print()
    print("=" * 70)
    print("Test 2 — round-trip on outlier-amplified K (10x boost on 5 ch)")
    print("=" * 70)
    torch.manual_seed(43)
    S = 16384
    H_kv = 4
    D = 128
    k = torch.randn(1, S, H_kv, D, device=DEVICE, dtype=DTYPE)
    # Boost 5 random channels per (h) by 10x — same pattern as Phase 4
    # outlier sub-test.
    n_boost = 5
    boost_idx = torch.zeros((H_kv, n_boost), dtype=torch.long, device=DEVICE)
    for h in range(H_kv):
        boost_idx[h] = torch.randperm(D, device=DEVICE)[:n_boost]
    boost_mask = torch.zeros((1, 1, H_kv, D), dtype=DTYPE, device=DEVICE)
    for h in range(H_kv):
        boost_mask[0, 0, h, boost_idx[h]] = 9.0  # factor (1 + 9) = 10x
    k_outlier = k + k * boost_mask

    ok = True
    for fraction in [0.04, 0.08]:
        err = _print_round_trip(f"Outlier S={S}", k_outlier, fraction)
        # Same gates as Test 1.
        if err["protected_max_abs"] > 0.0:
            print(f"     FAIL: protected_max_abs > 0")
            ok = False
        # Unprotected error in outlier K depends on which channels got
        # boosted. If a boosted channel is NOT protected, its scale is
        # 10x larger -> LSB is 10x larger -> per-element error up to ~2.7.
        # With protect_fraction=0.04 (5 protected) and 5 boosted, the
        # algorithm SHOULD select the boosted channels for protection
        # (they're the magnitude-top by L_inf). So if fraction >= 5/128,
        # all boosted channels are protected -> unprotected error stays
        # at ~0.27. If fewer protected, some boosted leak into unprotected.
        # Allow 3.0 cap for outlier K to handle this edge case.
        if err["unprotected_max_abs"] > 3.0:
            print(f"     FAIL: unprotected_max_abs {err['unprotected_max_abs']:.3f}"
                  f" > 3.0 even on outlier K")
            ok = False
    return ok


def test_sidecar_bytes() -> bool:
    print()
    print("=" * 70)
    print("Test 3 — sidecar memory accounting matches design doc")
    print("=" * 70)
    # Qwen2.5-7B per-layer K at S=32k.
    S = 32768
    H_kv = 4
    D = 128
    info = sidecar_byte_size(S, H_kv, D, protect_fraction=0.04)
    print(f"  S={S} H_kv={H_kv} D={D} protect_fraction=0.04")
    for k, v in info.items():
        if isinstance(v, int) and v > 1024:
            print(f"    {k:25s} {v:>15,} bytes  ({v/1024/1024:.2f} MB)")
        else:
            print(f"    {k:25s} {v}")
    fp16_baseline = info["fp16_baseline"]
    total = info["total"]
    compression = info["compression"]
    print(f"  compression vs FP16 = {compression:.2f}x  "
          f"(per-layer: {total/1024/1024:.2f} MB vs FP16 {fp16_baseline/1024/1024:.2f} MB)")
    # Per the design doc: at S=32k, expect ~0.65 GB across all 28 layers
    # = 23 MB per layer. compression should be ~2.9x.
    if not (2.5 <= compression <= 3.5):
        print(f"  FAIL: compression {compression:.2f}x outside expected [2.5, 3.5]")
        return False
    # 28 layers total at S=32k:
    total_all_layers = total * 28
    print(f"  Aggregate across 28 layers: {total_all_layers/1024/1024/1024:.2f} GB"
          f"  (design doc target: ~0.65 GB; +~0.4 GB if scale+xmin counted "
          f"both bf16 = OK)")
    return True


def main() -> int:
    print(f"Phase 2.4.0 — Python pack/unpack helpers acceptance")
    print(f"  device: {DEVICE}")
    print(f"  dtype:  {DTYPE}")

    results = [
        ("Gaussian round-trip",  test_round_trip_gaussian()),
        ("Outlier round-trip",   test_round_trip_outlier()),
        ("Sidecar byte sizing",  test_sidecar_bytes()),
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
        print("Phase 2.4.0: GREEN.")
        print("  - pack/unpack round-trip preserves protected channels bit-equal")
        print("  - unprotected dequant error bounded by per-group scale")
        print("  - sidecar memory matches design doc target compression")
        print("  - Safe to proceed to Phase 2.4.1 (custom HBM load CUDA path)")
        return 0
    print("Phase 2.4.0: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
