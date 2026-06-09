#!/usr/bin/env python3
# CPU regression for the hybrid bf16/int4_protected KV scheduler cost model
# (Bench/scripts/hybrid_kv_scheduler.py).
#
# Guards the invariants the scheduler relies on:
#   * the "<= bf16 always" guarantee for the guarded hybrid (#4*) and load-switch (#6);
#   * the honest caveat that the NAIVE two-pool (#4) can exceed bf16 when a few
#     sequences sit just above the crossover (it opens the int4 pool, pays the
#     fixed tax, and their small per-seq savings don't cover it);
#   * exact bf16 per-token KV bytes and the crossover-length formula;
#   * the audited ~1.8x net density at saturation.
#
# Pure stdlib (no torch). Run:
#   python CTM_plus/Bench/tests/test_hybrid_kv_scheduler.py
#   (also pytest-collectable)

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import hybrid_kv_scheduler as H  # noqa: E402

GB = H.GB


def test_selftest_gates_pass():
    assert H.selftest() == 0


def test_bf16_per_token_exact():
    # Qwen2.5-7B: 2(K,V) * 28 layers * 4 KV heads * 128 D * 2 bytes
    assert H.PRESETS["qwen2.5-7b"].bf16_kv_bytes_per_token() == 57344
    # Llama-3.1-8B doubles it (8 KV heads)
    assert H.PRESETS["llama-3.1-8b"].bf16_kv_bytes_per_token() == 131072


def test_crossover_formula_and_routing():
    mc, cal = H.PRESETS["qwen2.5-7b"], H.Int4Calib()
    Lstar = H.crossover_length(mc, cal)
    assert 900 < Lstar < 1100  # ~986 tok at the default staging estimate
    # just below -> bf16 cheaper; just above -> int4 cheaper
    below, above = int(Lstar * 0.9), int(Lstar * 1.1) + 1
    assert H.bf16_seq_bytes(mc, below) < H.int4_seq_marginal_bytes(mc, cal, below)
    assert H.int4_seq_marginal_bytes(mc, cal, above) < H.bf16_seq_bytes(mc, above)


def test_guarantee_holds_over_random_workloads():
    mc, cal = H.PRESETS["qwen2.5-7b"], H.Int4Calib()
    import random
    rng = random.Random(7)
    for _ in range(200):
        spec = rng.choice([
            f"unif:8:200:{rng.randint(1,128)}",
            f"unif:40000:60000:{rng.randint(1,64)}",
            f"lognormal:{rng.choice([256,1024,8192])}:0.8:{rng.randint(1,128)}",
            f"mix:{rng.random():.2f}:64:48000:{rng.randint(1,96)}",
        ])
        L = H.make_workload(spec, seed=rng.randint(0, 9999))
        bf16 = H.total_bf16(mc, L)
        assert H.total_hybrid_guarded(mc, cal, L) <= bf16 + 1e-3
        assert H.total_load_switch(mc, cal, L) <= bf16 + 1e-3


def test_naive_two_pool_caveat_is_real():
    mc, cal = H.PRESETS["qwen2.5-7b"], H.Int4Calib()
    Lstar = H.crossover_length(mc, cal)
    few_long = [int(Lstar * 1.5)] * 3
    two, n_i4, _ = H.total_hybrid_two_pool(mc, cal, few_long)
    assert n_i4 == 3 and two > H.total_bf16(mc, few_long) + 1e-3
    # but all-short never opens the int4 pool -> equals bf16
    short = H.make_workload("uniform:64:32", 0)
    two_sh, _, _ = H.total_hybrid_two_pool(mc, cal, short)
    assert abs(two_sh - H.total_bf16(mc, short)) < 1e-3


def test_saturation_density_matches_audit():
    mc, cal = H.PRESETS["qwen2.5-7b"], H.Int4Calib()
    longw = H.make_workload("uniform:32768:64", 0)
    kv_bf16 = H.total_bf16(mc, longw) - mc.weight_gb * GB
    kv_i4 = H.total_int4(mc, cal, longw) - mc.weight_gb * GB
    assert 1.7 <= kv_bf16 / kv_i4 <= 1.9   # ~1.8x audited net density


if __name__ == "__main__":
    rc = H.selftest()
    # also exercise the pytest functions directly when run standalone
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  [PASS] {name}")
    print("\nstandalone run: ALL PASS" if rc == 0 else "\nselftest reported FAIL")
    raise SystemExit(rc)
