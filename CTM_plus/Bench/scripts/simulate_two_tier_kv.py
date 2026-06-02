"""Two-tier KV cache — CPU PRIZE-SIZING SIMULATOR (models, does NOT measure).

Two-tier doesn't exist yet, so this cannot benchmark a real system. It does the
honest pre-build thing: given ALREADY-MEASURED costs (bf16 decode speed, int4
decode tax, int4 density) + a hot-fraction parameter, it predicts whether a
hot=bf16 / cold=int4_protected split would beat all-int4 enough to justify the
build. If the model says "barely better even at optimistic hot fractions," don't
build it. See TWO_TIER_ARCHITECTURE_NOTE.md.

THIS IS A MODEL. Its outputs are predictions from a simple cost model, NOT
measurements of a running two-tier cache. Every number it emits is "if the model
is right, then ..." — the real system has bookkeeping/promotion/integration costs
this model deliberately bounds but cannot capture. Treat as a go/no-go SCREEN.

Cost model (deliberately simple + conservative):
  - A request has S total KV tokens. A fraction `hot_frac` stay in bf16 (tier 1),
    the rest (1-hot_frac) are demoted to int4_protected (tier 2).
  - Per-token decode cost: bf16 tokens cost `1.0` (normalized); int4 tokens cost
    `1/int4_ratio` MORE (int4 is slower per token: at the measured 0.32x agg, an
    int4 token is ~1/0.32 = 3.1x a bf16 token's decode work).
  - Aggregate decode throughput ∝ S / (weighted per-token cost).
  - Memory: bf16 tokens cost 1.0 unit; int4 tokens cost 1/density (≈1/2) units.
    Two-tier memory = hot_frac*1 + (1-hot_frac)*(1/density).
  - Compared against all-bf16 (speed baseline) and all-int4 (density baseline).

  Plus a `bookkeeping_overhead` knob (default 5%) that taxes the cold-tier path
  to crudely represent demotion/promotion/Route-A cost — so the model isn't
  free-lunch optimistic.

Usage:
  python CTM_plus/Bench/scripts/simulate_two_tier_kv.py                  # default sweep
  python CTM_plus/Bench/scripts/simulate_two_tier_kv.py \
      --int4-agg-ratio 0.32 --density 1.83 --hot-fracs 0.1,0.25,0.5 \
      --bookkeeping 0.05
  python CTM_plus/Bench/scripts/simulate_two_tier_kv.py --selftest
"""
from __future__ import annotations

import argparse
import sys
from typing import Dict, List, Optional

# Measured anchors from this session (defaults).
DEFAULT_INT4_AGG_RATIO = 0.32   # int4 agg throughput / bf16 (gen=512 point; range 0.22-0.54)
DEFAULT_DENSITY = 1.83          # int4 net seq/GB vs bf16 (locked)
DEFAULT_BOOKKEEPING = 0.05      # cold-tier overhead fraction (demotion/promotion/Route-A proxy)


def simulate(hot_frac: float, int4_agg_ratio: float, density: float,
             bookkeeping: float) -> Dict[str, float]:
    """Predict two-tier throughput + memory vs all-bf16 and all-int4.

    Normalize a bf16 token's decode cost to 1.0. int4 token decode cost is
    higher: if all-int4 runs at `int4_agg_ratio` of bf16 aggregate, an int4
    token costs ~1/int4_agg_ratio bf16-token-equivalents. Cold tokens also pay
    a `bookkeeping` surcharge (demotion/promotion/integration).
    """
    int4_agg_ratio = max(1e-3, min(int4_agg_ratio, 1.0))
    int4_token_cost = 1.0 / int4_agg_ratio                 # >1 (int4 slower/token)
    cold_token_cost = int4_token_cost * (1.0 + bookkeeping)

    # Per-token weighted decode cost (lower = faster aggregate throughput).
    twotier_cost = hot_frac * 1.0 + (1.0 - hot_frac) * cold_token_cost
    bf16_cost = 1.0
    allint4_cost = int4_token_cost

    # Throughput ratio vs bf16 (= bf16_cost / this_cost).
    twotier_tps_ratio = bf16_cost / twotier_cost
    allint4_tps_ratio = bf16_cost / allint4_cost

    # Memory per token: bf16=1.0, int4=1/density. Two-tier blends.
    int4_mem = 1.0 / density
    twotier_mem = hot_frac * 1.0 + (1.0 - hot_frac) * int4_mem
    # Density vs bf16 = 1 / mem-per-token.
    twotier_density = 1.0 / twotier_mem
    allint4_density = 1.0 / int4_mem   # == density

    return {
        "hot_frac": hot_frac,
        "twotier_tps_ratio": round(twotier_tps_ratio, 3),
        "allint4_tps_ratio": round(allint4_tps_ratio, 3),
        "tps_gain_vs_allint4": round(twotier_tps_ratio - allint4_tps_ratio, 3),
        "twotier_density": round(twotier_density, 3),
        "allint4_density": round(allint4_density, 3),
        "density_kept_vs_allint4_pct": round(100.0 * (twotier_density - 1.0) /
                                             (allint4_density - 1.0), 1)
        if allint4_density > 1.0 else 0.0,
    }


def verdict(rows: List[Dict[str, float]], min_tps_gain: float = 0.10) -> str:
    """Go/no-go screen: is there a hot_frac where two-tier beats all-int4
    throughput by >= min_tps_gain WHILE keeping a meaningful density share?"""
    best = max(rows, key=lambda r: r["tps_gain_vs_allint4"])
    if best["tps_gain_vs_allint4"] >= min_tps_gain and best["density_kept_vs_allint4_pct"] >= 50.0:
        return (f"WORTH MODELING FURTHER — at hot_frac={best['hot_frac']}, two-tier "
                f"predicts {best['twotier_tps_ratio']}x tps (vs all-int4 "
                f"{best['allint4_tps_ratio']}x, +{best['tps_gain_vs_allint4']}) while "
                f"keeping {best['density_kept_vs_allint4_pct']}% of int4's density gain. "
                f"NOTE: model only — validate the hot-attention-concentration assumption + "
                f"Route-A integration cost before building.")
    return ("LIKELY NOT WORTH IT — no hot_frac gives a >=%.0f%% throughput gain over "
            "all-int4 while keeping >=50%% of the density. The split's overhead/density-loss "
            "outweighs the speed recovered. (Model only; re-check inputs.)" % (min_tps_gain * 100))


def _selftest() -> int:
    # 1. hot_frac=0 -> identical to all-int4 (no bf16 tokens).
    r = simulate(0.0, 0.32, 1.83, 0.0)
    assert abs(r["twotier_tps_ratio"] - r["allint4_tps_ratio"]) < 1e-6, r
    assert abs(r["twotier_density"] - r["allint4_density"]) < 1e-6, r
    print("  hot_frac=0 == all-int4: PASS")

    # 2. hot_frac=1 -> all bf16: tps ratio 1.0, density 1.0 (no compression).
    r = simulate(1.0, 0.32, 1.83, 0.0)
    assert abs(r["twotier_tps_ratio"] - 1.0) < 1e-6, r
    assert abs(r["twotier_density"] - 1.0) < 1e-6, r
    print("  hot_frac=1 == all-bf16 (tps 1.0, density 1.0): PASS")

    # 3. monotonic: more hot -> faster but less dense.
    lo = simulate(0.2, 0.32, 1.83, 0.0)
    hi = simulate(0.6, 0.32, 1.83, 0.0)
    assert hi["twotier_tps_ratio"] > lo["twotier_tps_ratio"], (lo, hi)
    assert hi["twotier_density"] < lo["twotier_density"], (lo, hi)
    print("  more hot -> faster + less dense (monotonic): PASS")

    # 4. two-tier throughput always >= all-int4 (hot tokens are faster).
    for hf in (0.1, 0.3, 0.5, 0.9):
        r = simulate(hf, 0.32, 1.83, 0.0)
        assert r["twotier_tps_ratio"] >= r["allint4_tps_ratio"] - 1e-9, (hf, r)
    print("  two-tier tps >= all-int4 tps for all hot_frac: PASS")

    # 5. bookkeeping overhead reduces the gain (no free lunch).
    no_oh = simulate(0.3, 0.32, 1.83, 0.0)["tps_gain_vs_allint4"]
    with_oh = simulate(0.3, 0.32, 1.83, 0.20)["tps_gain_vs_allint4"]
    assert with_oh < no_oh, (no_oh, with_oh)
    print("  bookkeeping overhead shrinks the gain: PASS")

    # 6. THE STRUCTURAL FINDING: density and throughput-gain are in DIRECT
    # tension under the both-tiers-read model. Keeping >=50% density forces a
    # mostly-cold cache, whose cost ~= all-int4 cost -> tiny tps gain. So at the
    # realistic measured anchors the verdict is NOT-WORTH, AND this holds even
    # for a steep tax + high density (you still can't get both). This is the
    # honest model result: two-tier (compression-demotion, both tiers fully
    # read) is a speed<->density DIAL, not a free win.
    rows_measured = [simulate(hf, 0.32, 1.83, 0.05) for hf in (0.05, 0.1, 0.25, 0.5, 0.75)]
    assert verdict(rows_measured).startswith("LIKELY NOT"), verdict(rows_measured)
    rows_steep = [simulate(hf, 0.10, 4.0, 0.02) for hf in (0.05, 0.1, 0.2)]
    assert verdict(rows_steep).startswith("LIKELY NOT"), (
        "even steep-tax/high-density cannot satisfy BOTH >=10% gain AND >=50% "
        "density -> confirms the tension: " + verdict(rows_steep))
    print("  verdict: NOT-WORTH at measured AND steep anchors (density<->speed tension): PASS")

    # 7. The dial IS real: giving up density (high hot_frac) DOES buy speed.
    fast = simulate(0.75, 0.32, 1.83, 0.05)
    assert fast["twotier_tps_ratio"] > 0.55 and fast["twotier_density"] < 1.2, fast
    print("  the dial works: high hot_frac buys speed at the cost of density: PASS")

    print("\nself-test: 7/7 PASS")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Two-tier KV prize-sizing simulator (MODEL, not measurement)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--int4-agg-ratio", type=float, default=DEFAULT_INT4_AGG_RATIO,
                    help="measured all-int4 aggregate throughput / bf16 (default 0.32; range 0.22-0.54)")
    ap.add_argument("--density", type=float, default=DEFAULT_DENSITY,
                    help="measured int4 net density vs bf16 (default 1.83)")
    ap.add_argument("--bookkeeping", type=float, default=DEFAULT_BOOKKEEPING,
                    help="cold-tier overhead fraction (demotion/promotion/Route-A proxy)")
    ap.add_argument("--hot-fracs", default="0.05,0.1,0.25,0.5,0.75",
                    help="comma-separated hot-tier fractions to sweep")
    ap.add_argument("--min-tps-gain", type=float, default=0.10)
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    hot_fracs = [float(x) for x in args.hot_fracs.split(",") if x.strip()]
    rows = [simulate(hf, args.int4_agg_ratio, args.density, args.bookkeeping)
            for hf in hot_fracs]

    print("=" * 78)
    print("Two-tier KV — PRIZE-SIZING MODEL (predictions, NOT measurements)")
    print("=" * 78)
    print(f"inputs: int4_agg_ratio={args.int4_agg_ratio}  density={args.density}x  "
          f"bookkeeping={args.bookkeeping*100:.0f}%")
    print(f"baselines: all-bf16 tps=1.000x/density=1.00x | "
          f"all-int4 tps={rows[0]['allint4_tps_ratio']}x/density={rows[0]['allint4_density']}x")
    print()
    print(f"{'hot_frac':>8} | {'tps ratio':>9} | {'vs all-int4':>11} | {'density':>8} | {'density kept':>12}")
    print("-" * 62)
    for r in rows:
        print(f"{r['hot_frac']:>8.2f} | {r['twotier_tps_ratio']:>8.3f}x | "
              f"{r['tps_gain_vs_allint4']:>+10.3f} | {r['twotier_density']:>7.3f}x | "
              f"{r['density_kept_vs_allint4_pct']:>11.0f}%")
    print("-" * 62)
    print()
    print("VERDICT:", verdict(rows, args.min_tps_gain))
    print()
    print("THE STRUCTURAL FINDING (important): under this model, density and")
    print("throughput-gain are in DIRECT TENSION. Keeping most of int4's density")
    print("requires a mostly-COLD cache, but cold tokens are exactly the ones paying")
    print("the int4 decode tax every step -> the cost approaches all-int4 -> small gain.")
    print("So COMPRESSION-demotion two-tier (both tiers fully read each step) is a")
    print("speed<->density DIAL, NOT a free win. The version that WOULD win is true")
    print("EVICTION (H2O/StreamingLLM): cold tokens read LESS OFTEN, not just smaller.")
    print("That is a different mechanism (drop/skip), with its own quality risk.")
    print()
    print("CAVEATS: (1) MODEL ONLY. (2) assumes both tiers fully read; an eviction")
    print("variant (skip cold reads) is NOT modeled here. (3) gated on Route-A integration.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
