#!/usr/bin/env python3
# Phase 6K.13 — int4_protected scorecard (AUDIT-ONLY; no model, no kernel work).
#
# Pulls the clean post-fix measurements into one scorecard: HBM, concurrency,
# throughput, sidecar ranking, quality, memory delta, fidelity-per-GB, and the
# diet options as audit recommendations. CPU-only (no torch/vllm) — runs
# anywhere, instantly.
#
# Precise verdict: protected int4 is QUALITY-POSITIVE (vs naive) but
# CAPACITY-NEGATIVE (vs bf16) in the current implementation — it uses MORE HBM
# than bf16, so it is a quality feature, not a memory feature, today.
#
# Numbers are the measured post-fix values (A100-80GB, gpu_util=0.5); update the
# constants if you re-run the benches. Sources: audit_phase6g_sidecar_overhead,
# bench_phase6_long_context_gpu, bench_phase6_h_high_load_gpu,
# bench_phase6j_quality_gpu, phase6k12_hard_needle.
#
# Usage:  python CTM_plus/Bench/scripts/phase6k13_capacity_demo.py

# ---- measured data (post-fix) -------------------------------------------------
HBM = {  # mml: (bf16_GB, int4prot_GB, bf16_conc, int4_conc)
    8192:  (39.13, 43.82, 55.3, 110.6),
    16384: (38.04, 42.72, 26.4, 52.8),
    32768: (35.85, 40.51, 12.0, 23.9),
}
THROUGHPUT = {  # mml: (bf16_tps, int4_tps) at B=8 (long-context bench)
    8192:  (131.9, 74.4),
    16384: (70.9, 46.3),
    32768: (34.7, 23.1),
}
SIDECARS = [  # (tensor, scaling, GB@32K, pct)
    ("k_protect_ext", "per_token", 0.818, 23.8),
    ("v_scale_ext",   "per_token", 0.654, 19.0),
    ("v_xmin_ext",    "per_token", 0.654, 19.0),
    ("k_scale_ext",   "per_block", 0.654, 19.0),
    ("k_xmin_ext",    "per_block", 0.654, 19.0),
    ("_k_stage_pool", "per_slot",  0.007, 0.2),
]
QUALITY = {  # metric: (naive, protected, bf16)
    "token_agreement_vs_bf16": (0.533, 0.737, 1.000),
    "hard_needle_retrieval@8K": (0.915, 0.964, 1.000),
}
HARD_NEEDLE_MISSES = {"naive": "5 (4 V-bound + 1 K-bound)", "protected": "2 (2 V-bound, 0 K-bound)"}

DIET = [  # (id, desc, save_GB, risk, targets, kernel?)
    ("A", "Halve V quant groups (v_n_groups 4->2)", 0.65, "moderate",
     "v_scale_ext, v_xmin_ext", "yes (V kernel)"),
    ("C", "Quantize sidecars bf16 -> fp8 (e4m3)", 1.72, "high",
     "all scale/xmin + k_protect_ext", "yes (read+write)"),
    ("F", "Reduce protected channels (n_protect 5->3)", 0.33, "moderate",
     "k_protect_ext", "no (recalibration only)"),
    ("D", "Eliminate k_protect_ext (inline into kv_cache)", 0.82, "low semantic / high impl",
     "k_protect_ext", "yes (layout change)"),
]
DIET_STACK_AFC = 3.19   # A+F+C stacked (audit estimate; interactions accounted)


def _bar():
    print("-" * 92)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="int4_protected audit scorecard (CPU-only).")
    ap.add_argument("--mml", type=int, help="(ignored) scorecard covers all measured mml")
    ap.add_argument("--worker", action="store_true", help="(ignored) audit-only, no model")
    args, _unknown = ap.parse_known_args()
    if args.mml is not None or args.worker or _unknown:
        print("[6k13] NOTE: this is the AUDIT-ONLY scorecard (CPU; no model loaded). "
              "CLI args are ignored. The live saturation runner is a separate, "
              "post-diet bench (see [7] RECOMMENDATION).\n")
    print("=" * 92)
    print("PHASE 6K.13 — int4_protected SCORECARD (audit-only, clean post-fix)")
    print("  VERDICT: QUALITY-POSITIVE (vs naive) but CAPACITY-NEGATIVE (vs bf16).")
    print("  Protected int4 is a QUALITY feature, not a memory feature, in the current impl.")
    print("=" * 92)

    print("\n[1] HBM & concurrency (A100-80GB, gpu_util=0.5)")
    print(f"  {'mml':>6} | {'bf16 GB':>8} {'int4 GB':>8} {'ΔHBM':>8} | "
          f"{'bf16 conc':>9} {'int4 conc':>9} {'conc x':>6}")
    _bar()
    for mml, (b, i, bc, ic) in HBM.items():
        print(f"  {mml:>6} | {b:>8.2f} {i:>8.2f} {i-b:>+8.2f} | "
              f"{bc:>9.1f} {ic:>9.1f} {ic/bc:>6.2f}")
    print("  -> int4 uses MORE total HBM (+~4.7 GB sidecar+graph tax); conc ~2x is")
    print("     vLLM bookkeeping within the budget, NOT a footprint reduction.")

    print("\n[2] Decode throughput (B=8; int4/bf16)")
    print(f"  {'mml':>6} | {'bf16 tps':>8} {'int4 tps':>8} {'int4/bf16':>9}")
    _bar()
    for mml, (b, i) in THROUGHPUT.items():
        print(f"  {mml:>6} | {b:>8.1f} {i:>8.1f} {i/b:>9.2f}x")
    print("  -> int4 decode is ~1.5-1.9x SLOWER. 6H high-load was INCONCLUSIVE")
    print("     (short prompts never saturated; bf16 still 1.4-1.9x faster).")

    print("\n[3] Sidecar inventory (mml=32K; fixed 16.4% of KV cache)")
    print(f"  {'tensor':>16} | {'scaling':>10} {'GB':>6} {'% sidecar':>9}")
    _bar()
    for name, sc, gb, pct in SIDECARS:
        print(f"  {name:>16} | {sc:>10} {gb:>6.3f} {pct:>8.1f}%")
    tot = sum(g for _, _, g, _ in SIDECARS)
    print(f"  total sidecars ~= {tot:.2f} GB. No single tensor dominates.")

    print("\n[4] Quality (clean post-fix)")
    print(f"  {'metric':>26} | {'naive':>6} {'protected':>9} {'bf16':>6} {'prot-naive':>10}")
    _bar()
    for k, (n, p, b) in QUALITY.items():
        print(f"  {k:>26} | {n:>6.3f} {p:>9.3f} {b:>6.3f} {p-n:>+10.3f}")
    print(f"  hard-needle genuine misses: naive {HARD_NEEDLE_MISSES['naive']} -> "
          f"protected {HARD_NEEDLE_MISSES['protected']}")
    print("  easy needle saturated (both int4 ~= bf16). Remaining misses V-bound.")

    print("\n[5] Fidelity-per-GB (what the PROTECT sidecar buys)")
    ta_gain = QUALITY["token_agreement_vs_bf16"][1] - QUALITY["token_agreement_vs_bf16"][0]
    kpe = SIDECARS[0][2]   # k_protect_ext GB
    print(f"  protect token-agreement gain = +{ta_gain*100:.1f} pts for k_protect_ext={kpe:.2f} GB")
    print(f"  -> ~{ta_gain*100/kpe:.1f} token-agreement pts per GB of protect sidecar.")
    print("  NOTE: protected vs naive is ~SAME total memory (both allocate sidecars),")
    print("  so PROTECT is near-free fidelity over naive — always prefer protected to naive.")
    print("  The +4.7 GB cost is the int4 PATH vs bf16, and it BUYS 0.737 (< bf16 1.0)")
    print("  fidelity + 2x conc, NOT memory savings.")

    print("\n[6] Diet options (audit recommendation only — NO implementation)")
    print(f"  {'id':>2} | {'save GB':>7} {'risk':>22} | targets / kernel")
    _bar()
    for did, desc, save, risk, targets, kern in DIET:
        print(f"  {did:>2} | {save:>7.2f} {risk:>22} | {targets}  [{kern}]")
        print(f"       {desc}")
    print(f"\n  Stacked A+F+C ~= {DIET_STACK_AFC:.2f} GB  <  ~4.7 GB delta to bf16.")
    print("  => A+F+C ALONE does NOT close the gap. Either add D (eliminate")
    print("     k_protect_ext) too, or accept protected int4 as a QUALITY feature.")

    print("\n[7] RECOMMENDATION")
    print("  Proceed only with sidecar-diet experiments and scorecarding. Do NOT start")
    print("  heavy Phase 6F kernel work until a dieted protected-int4 config demonstrates")
    print("  an HBM advantage (or at least near-parity with bf16) while preserving most")
    print("  of the +20.4 token-agreement gain. Next: pick diet option(s), re-run the")
    print("  6G audit + long-context HBM crossover + a TRUE-saturation high-load test,")
    print("  and re-score fidelity after each diet step.")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
