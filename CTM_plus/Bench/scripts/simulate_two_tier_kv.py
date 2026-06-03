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
  python CTM_plus/Bench/scripts/simulate_two_tier_kv.py --derive-crf  # Phase 9 Step 0:
      # DERIVE the achievable cold_read_frac from a sink+recent keep-set across
      # sequence lengths (is the 0.15 headline reachable, and at what context?)
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
             bookkeeping: float, cold_read_frac: float = 1.0) -> Dict[str, float]:
    """Predict two-tier throughput + memory vs all-bf16 and all-int4.

    Normalize a bf16 token's decode cost to 1.0. int4 token decode cost is
    higher: if all-int4 runs at `int4_agg_ratio` of bf16 aggregate, an int4
    token costs ~1/int4_agg_ratio bf16-token-equivalents. Cold tokens also pay
    a `bookkeeping` surcharge (demotion/promotion/integration).

    cold_read_frac (THE mechanism knob, 0<f<=1): the fraction of decode steps on
    which a cold token is actually READ/attended.
      * 1.0  = COMPRESSION-demotion: cold tokens are read EVERY step, just stored
               smaller. (The original model — a speed<->density dial, not a win.)
      * <1.0 = EVICTION / READ-SKIP (H2O / StreamingLLM): cold tokens are read
               only `cold_read_frac` of the time, so their per-step decode cost
               drops proportionally. This is the mechanism that can actually move
               the needle — but it carries a QUALITY RISK (a skipped read of a
               token attention needed) that this MODEL DOES NOT quantify.
    Tokens stay STORED in int4 either way, so density is unchanged by
    cold_read_frac; only the decode cost changes.
    """
    int4_agg_ratio = max(1e-3, min(int4_agg_ratio, 1.0))
    cold_read_frac = max(0.0, min(cold_read_frac, 1.0))
    int4_token_cost = 1.0 / int4_agg_ratio                 # >1 (int4 slower/token)
    # A cold token's per-step contribution = its read cost * how often it's read,
    # plus the (always-on) bookkeeping surcharge for being in the cold tier.
    cold_token_cost = int4_token_cost * cold_read_frac * (1.0 + bookkeeping)

    # Per-token weighted decode cost (lower = faster aggregate throughput).
    twotier_cost = hot_frac * 1.0 + (1.0 - hot_frac) * cold_token_cost
    bf16_cost = 1.0
    allint4_cost = int4_token_cost   # all-int4 reads everything every step

    # Throughput ratio vs bf16 (= bf16_cost / this_cost).
    twotier_tps_ratio = bf16_cost / max(twotier_cost, 1e-9)
    allint4_tps_ratio = bf16_cost / allint4_cost

    # Memory per token: bf16=1.0, int4=1/density. Cold tokens are STILL STORED in
    # int4, so density is independent of cold_read_frac.
    int4_mem = 1.0 / density
    twotier_mem = hot_frac * 1.0 + (1.0 - hot_frac) * int4_mem
    twotier_density = 1.0 / twotier_mem
    allint4_density = 1.0 / int4_mem   # == density

    return {
        "hot_frac": hot_frac,
        "cold_read_frac": cold_read_frac,
        "twotier_tps_ratio": round(twotier_tps_ratio, 3),
        "allint4_tps_ratio": round(allint4_tps_ratio, 3),
        "tps_gain_vs_allint4": round(twotier_tps_ratio - allint4_tps_ratio, 3),
        "twotier_density": round(twotier_density, 3),
        "allint4_density": round(allint4_density, 3),
        "density_kept_vs_allint4_pct": round(100.0 * (twotier_density - 1.0) /
                                             (allint4_density - 1.0), 1)
        if allint4_density > 1.0 else 0.0,
    }


def achievable_cold_read_frac(seq_len: int, n_sink: int, n_recent: int,
                              middle_keep_frac: float, hot_frac: float) -> Dict[str, float]:
    """DERIVE cold_read_frac from the StreamingLLM/H2O keep-set, instead of
    treating it as a free dial.

    The headline 1.9x assumes `cold_read_frac=0.15` — but is 0.15 ACHIEVABLE?
    Route-A can't skip everything: an attention-safe skip MUST keep the
    always-read set (the `n_sink` attention sinks + the `n_recent`-token recent
    window), and within the remaining MIDDLE it can keep only `middle_keep_frac`
    of tokens (the heavy hitters). So the realised cold-tier read fraction is a
    STRUCTURAL consequence of (seq_len, keep-set sizes, hot_frac), not a knob.

    Model (token-count accounting at one decode step on a length-`seq_len` seq):
      - always-read set A = min(n_sink + n_recent, seq_len): read every step.
      - the hot (bf16) tier absorbs A first (recent+sink ARE the hot tokens). If
        hot_frac*S < A, the leftover always-read tokens spill into the cold tier
        and are STILL read every step (read prob 1.0).
      - every other cold token is "middle": read at `middle_keep_frac`.
      cold_read_frac = (always_read_in_cold*1.0 + middle_in_cold*middle_keep)
                       / cold_total.

    The structural consequence (the whole point): the floor is `middle_keep_frac`
    (long seq, hot tier covers the always-read set) and it rises toward 1.0 as
    `seq_len` shrinks toward the keep-set size. So the read-skip prize is
    SEQUENCE-LENGTH DEPENDENT — big at long context, ~nil at short context where
    sink+recent already are most of the cache and there is nothing to skip.
    """
    seq_len = max(1, int(seq_len))
    hot_frac = max(0.0, min(hot_frac, 1.0))
    middle_keep_frac = max(0.0, min(middle_keep_frac, 1.0))
    always_read = min(n_sink + n_recent, seq_len)          # A
    hot_tokens = hot_frac * seq_len
    cold_total = max(1e-9, seq_len - hot_tokens)
    # always-read tokens not absorbed by the hot tier spill into cold (still read):
    always_read_in_cold = max(0.0, min(always_read - hot_tokens, cold_total))
    middle_in_cold = max(0.0, cold_total - always_read_in_cold)
    cold_reads = always_read_in_cold * 1.0 + middle_in_cold * middle_keep_frac
    crf = cold_reads / cold_total
    return {
        "seq_len": seq_len,
        "always_read": int(always_read),
        "always_read_in_cold": round(always_read_in_cold, 1),
        "cold_read_frac": round(crf, 4),
        "middle_keep_frac": middle_keep_frac,
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

    # 8. cold_read_frac default == 1.0 (compression): identical to the old model.
    a = simulate(0.25, 0.32, 1.83, 0.05)
    b = simulate(0.25, 0.32, 1.83, 0.05, cold_read_frac=1.0)
    assert a["twotier_tps_ratio"] == b["twotier_tps_ratio"], (a, b)
    print("  cold_read_frac default 1.0 == compression baseline (back-compat): PASS")

    # 9. THE MITIGATION: read-skip (cold_read_frac < 1) breaks the tension.
    # Same low hot_frac (keeps density high) but cold tokens read rarely ->
    # big tps gain that compression CANNOT achieve at the same density.
    compress = simulate(0.10, 0.32, 1.83, 0.05, cold_read_frac=1.0)
    evict    = simulate(0.10, 0.32, 1.83, 0.05, cold_read_frac=0.10)
    # density identical (cold tokens still STORED in int4):
    assert abs(compress["twotier_density"] - evict["twotier_density"]) < 1e-6, (compress, evict)
    # but read-skip is much faster:
    assert evict["twotier_tps_ratio"] > compress["twotier_tps_ratio"] * 1.5, (compress, evict)
    print(f"  read-skip breaks the tension: same density {evict['twotier_density']}x, "
          f"tps {compress['twotier_tps_ratio']}x -> {evict['twotier_tps_ratio']}x: PASS")

    # 10. read-skip can clear the verdict bar where compression could not.
    rows_evict = [simulate(hf, 0.32, 1.83, 0.05, cold_read_frac=0.15)
                  for hf in (0.05, 0.1, 0.25)]
    assert verdict(rows_evict).startswith("WORTH"), verdict(rows_evict)
    print("  read-skip variant clears the verdict bar (compression did not): PASS")

    # 11. DERIVED cold_read_frac floor == middle_keep_frac when the hot tier
    # covers the whole always-read set (long seq). At seq=8192, hot_frac=0.05
    # (=410 hot tokens) covers sink+recent=4+256=260, so cold is ALL middle ->
    # crf collapses to middle_keep.
    d = achievable_cold_read_frac(8192, 4, 256, 0.15, 0.05)
    assert abs(d["cold_read_frac"] - 0.15) < 0.01, d
    print(f"  derived crf floor == middle_keep at long seq (8192 -> "
          f"crf={d['cold_read_frac']}): PASS")

    # 12. SEQUENCE-LENGTH DEPENDENCE: shorter seq -> always-read set dominates
    # the cache -> crf rises toward 1.0 -> less to skip. Monotone in seq_len.
    crfs = [achievable_cold_read_frac(S, 4, 512, 0.15, 0.05)["cold_read_frac"]
            for S in (1024, 4096, 16384)]
    assert crfs[0] > crfs[1] > crfs[2], crfs
    assert crfs[0] > 0.4, ("short seq has little to skip", crfs)   # 1k: crf high
    print(f"  derived crf rises as seq shrinks (16k/4k/1k -> {crfs[::-1]}): PASS")

    # 13. THE STEP-0 GATE: at a DERIVED (not free) crf, the read-skip prize is
    # real ONLY at long context. Plug the derived crf back into the cost model.
    long_crf = achievable_cold_read_frac(16384, 4, 512, 0.15, 0.05)["cold_read_frac"]
    short_crf = achievable_cold_read_frac(1024, 4, 512, 0.15, 0.05)["cold_read_frac"]
    long_gain = simulate(0.05, 0.32, 1.83, 0.05, cold_read_frac=long_crf)["tps_gain_vs_allint4"]
    short_gain = simulate(0.05, 0.32, 1.83, 0.05, cold_read_frac=short_crf)["tps_gain_vs_allint4"]
    assert long_gain >= 0.10, ("long-context prize must clear the 10% bar", long_gain)
    assert short_gain < long_gain, (short_gain, long_gain)
    print(f"  derived prize real at long ctx (+{long_gain}) but shrinks short "
          f"(+{short_gain}): PASS")

    print("\nself-test: 13/13 PASS")
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
    ap.add_argument("--cold-read-frac", type=float, default=None,
                    help="fraction of steps a COLD token is read. 1.0=compression "
                         "(read every step); <1.0=eviction/read-skip (H2O-style). "
                         "If omitted, the run shows BOTH a compression (1.0) and a "
                         "read-skip (0.15) sweep side by side.")
    ap.add_argument("--min-tps-gain", type=float, default=0.10)
    # --- DERIVED cold_read_frac (the keep-set model: sink+recent kept, middle skipped) ---
    ap.add_argument("--derive-crf", action="store_true",
                    help="DERIVE cold_read_frac from a StreamingLLM/H2O keep-set "
                         "(sink+recent always read, middle kept at --middle-keep) "
                         "across --seq-lens, instead of using a free dial. Shows "
                         "whether the headline 0.15 is ACHIEVABLE and at what context.")
    ap.add_argument("--seq-lens", default="1024,4096,8192,16384,32768",
                    help="comma-separated sequence lengths to sweep in --derive-crf mode")
    ap.add_argument("--n-sink", type=int, default=4,
                    help="attention-sink tokens always read (StreamingLLM uses 4)")
    ap.add_argument("--n-recent", type=int, default=512,
                    help="recent-window tokens always read")
    ap.add_argument("--middle-keep", type=float, default=0.15,
                    help="fraction of the MIDDLE (non-sink, non-recent) tokens kept "
                         "(the heavy-hitter retention rate; H2O-style)")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    hot_fracs = [float(x) for x in args.hot_fracs.split(",") if x.strip()]

    def _table(crf: float, label: str):
        rows = [simulate(hf, args.int4_agg_ratio, args.density,
                         args.bookkeeping, cold_read_frac=crf) for hf in hot_fracs]
        print(f"--- {label} (cold_read_frac={crf}) ---")
        print(f"{'hot_frac':>8} | {'tps ratio':>9} | {'vs all-int4':>11} | "
              f"{'density':>8} | {'density kept':>12}")
        print("-" * 62)
        for r in rows:
            print(f"{r['hot_frac']:>8.2f} | {r['twotier_tps_ratio']:>8.3f}x | "
                  f"{r['tps_gain_vs_allint4']:>+10.3f} | {r['twotier_density']:>7.3f}x | "
                  f"{r['density_kept_vs_allint4_pct']:>11.0f}%")
        print("-" * 62)
        print("VERDICT:", verdict(rows, args.min_tps_gain))
        print()
        return rows

    def _derived_table(hot_frac: float):
        """STEP-0 GATE: derive cold_read_frac per sequence length from the
        keep-set, plug it into the cost model, and print whether the prize is
        real at ACHIEVABLE skip rates (not at a hand-set 0.15)."""
        seq_lens = [int(x) for x in args.seq_lens.split(",") if x.strip()]
        print(f"--- DERIVED read-skip prize (keep-set: sink={args.n_sink} + "
              f"recent={args.n_recent} always read, middle kept @ "
              f"{args.middle_keep:.0%}; hot_frac={hot_frac}) ---")
        print(f"{'seq_len':>8} | {'derived crf':>11} | {'tps ratio':>9} | "
              f"{'vs all-int4':>11} | {'density':>8} | {'gain>=10%?':>10}")
        print("-" * 74)
        any_win = False
        for S in seq_lens:
            d = achievable_cold_read_frac(S, args.n_sink, args.n_recent,
                                          args.middle_keep, hot_frac)
            r = simulate(hot_frac, args.int4_agg_ratio, args.density,
                         args.bookkeeping, cold_read_frac=d["cold_read_frac"])
            win = r["tps_gain_vs_allint4"] >= args.min_tps_gain
            any_win = any_win or win
            print(f"{S:>8} | {d['cold_read_frac']:>11.3f} | "
                  f"{r['twotier_tps_ratio']:>8.3f}x | "
                  f"{r['tps_gain_vs_allint4']:>+10.3f} | "
                  f"{r['twotier_density']:>7.3f}x | {'YES' if win else 'no':>10}")
        print("-" * 74)
        if any_win:
            print("VERDICT: PRIZE IS REAL at achievable skip rates — and it GROWS with "
                  "context. The derived crf falls to its floor (=middle-keep 0.15) once "
                  "the cache dwarfs the always-read keep-set, so the headline ~1.9x is "
                  "achievable at long context (>=8k) but the gain is much smaller short "
                  "(the keep-set is then most of the cache, leaving little to skip). The "
                  "0.15 is NOT a free dial — it is earned by length. ➜ the GPU A/B MUST "
                  "use a LONG-context workload; Step 3 still gates on quality + dispatch tax.")
        else:
            print("VERDICT: NO WIN at achievable skip rates for these seq lengths — "
                  "the always-read keep-set (sink+recent) is too large a share of the "
                  "cache to leave anything worth skipping. STOP / lengthen context.")
        print()

    print("=" * 78)
    print("Two-tier KV — PRIZE-SIZING MODEL (predictions, NOT measurements)")
    print("=" * 78)
    print(f"inputs: int4_agg_ratio={args.int4_agg_ratio}  density={args.density}x  "
          f"bookkeeping={args.bookkeeping*100:.0f}%")
    allint4 = simulate(0.0, args.int4_agg_ratio, args.density, args.bookkeeping)
    print(f"baselines: all-bf16 tps=1.000x/density=1.00x | "
          f"all-int4 tps={allint4['allint4_tps_ratio']}x/density={allint4['allint4_density']}x")
    print()

    if args.derive_crf:
        # Derive the skip rate from the keep-set at the most-dense hot_frac in
        # the sweep (lowest hot_frac = highest density = the regime we care about).
        _derived_table(min(hot_fracs))
    elif args.cold_read_frac is not None:
        _table(args.cold_read_frac,
               "COMPRESSION" if args.cold_read_frac >= 0.999 else "EVICTION / READ-SKIP")
    else:
        # Default: show both mechanisms side by side — the whole point.
        _table(1.0, "MECHANISM A: COMPRESSION-demotion (cold read EVERY step)")
        _table(0.15, "MECHANISM B: EVICTION / READ-SKIP (cold read ~15% of steps)")

    print("HOW TO READ THIS:")
    print("  * Compression (cold_read_frac=1.0): density and tps-gain are in DIRECT")
    print("    TENSION -- cold tokens pay the int4 tax EVERY step, so keeping density")
    print("    keeps the cost ~ all-int4. A speed<->density DIAL, not a win. DON'T build.")
    print("  * Read-skip (cold_read_frac<1.0): cold tokens are read RARELY, so their")
    print("    per-step cost drops while density is UNCHANGED (still stored in int4).")
    print("    THIS is the mechanism that breaks the tension -- it can clear the bar at")
    print("    low hot_frac (high density) -- but it is EVICTION (H2O/StreamingLLM):")
    print("    a skipped read of a needed token is a QUALITY risk this model does NOT")
    print("    quantify. The gain is real; the risk must be measured separately.")
    print()
    print("CAVEATS: (1) MODEL ONLY -- no real bookkeeping/promotion/thrash cost beyond")
    print("the knob. (2) read-skip's quality cost is UNMODELED (needs a GPU needle/MMLU")
    print("run at the chosen cold_read_frac). (3) gated on Route-A solving the hot-path")
    print("integration tax (PHASE8 audit) -- the per-step skip decision can't eat -20%.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
