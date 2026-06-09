#!/usr/bin/env python3
# Hybrid bf16 / int4_protected KV scheduler — cost model + policy harness.
#
# WHAT THIS IS
#   A calibrated, CPU-only *decision tool*. Given a model and a workload
#   (sequence-length distribution + concurrency), it computes the HBM footprint
#   of four KV-cache policies and tells you (a) the per-sequence crossover length
#   where int4_protected starts beating bf16, (b) how much a hybrid scheduler
#   actually saves on realistic workloads, and (c) whether the "<= bf16 always"
#   guarantee holds. It answers "is the hybrid worth building, and where do we set
#   the threshold?" BEFORE anyone writes the vLLM mixed-dtype-pool plumbing.
#
# WHAT THIS IS NOT
#   It is NOT the serving implementation (mixed-dtype paged KV pools in vLLM = the
#   weeks-of-engineering part). It is the cost model that justifies/sizes that work.
#
# THE KEY FINDING IT ENCODES (from MEMORY_STORY.md, measured)
#   On the per-sequence axis a scheduler actually uses, int4_protected is ~0.55x
#   bf16 PER TOKEN (the audited ~1.8x net density) -- so it wins on long sequences.
#   The measured "+4.68 GB more at equal gpu_util" is NOT a same-workload penalty;
#   it is the cost of int4 serving ~2x the load in that experiment. The only thing
#   that makes int4 LOSE at short length is the LENGTH-INDEPENDENT overhead:
#       * a fixed CUDA-graph / kernel-workspace tax, and
#       * a per-active-slot PagedKVWriter staging pool.
#   Those set the crossover. The per-slot staging size is the one input that is
#   not yet directly measured -- it is flagged, overridable, and swept.
#
# CALIBRATION SOURCES (all in this repo)
#   * bf16 per-token KV bytes: exact analytical (2 * layers * n_kv_heads * D * 2).
#   * int4 per-token fraction 0.555: MEMORY_STORY.md SS1/SS4 audited net density
#     ~1.8x (range 0.50 = the 2.0x vLLM-bookkeeping number .. 0.555 = net-of-tax).
#   * fixed tax + per-slot staging: MEMORY_STORY.md SS1 ("sidecar + CUDA-graph
#     tax", "per-slot staging pool sized to PHASE6_MAX_ACTIVE_SLOTS"). Magnitudes
#     are ESTIMATES pending a pod measurement -- see measure_stage_pool() TODO.
#
# Run:
#   python CTM_plus/Bench/scripts/hybrid_kv_scheduler.py --crossover
#   python CTM_plus/Bench/scripts/hybrid_kv_scheduler.py --sweep
#   python CTM_plus/Bench/scripts/hybrid_kv_scheduler.py --workload lognormal:7.6:0.9:256
#   python CTM_plus/Bench/scripts/hybrid_kv_scheduler.py --selftest   # invariant gates
#
# Pure stdlib (no torch/numpy) -> runs anywhere, like the other CPU regressions.

from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass, replace

GB = 1024 ** 3
MB = 1024 ** 2
KB = 1024


# --------------------------------------------------------------------------- #
# Model + calibration
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ModelConfig:
    name: str
    layers: int
    n_kv_heads: int          # GQA KV heads (drives KV size, hence everything)
    head_dim: int
    weight_gb: float         # bf16 weights resident (KV quant is weights-bf16).
    # NOTE: weight_gb is a SHARED constant carried once by every policy, so it
    # cancels in all deltas/savings and in the <=bf16 guarantee. It only affects
    # absolute GB totals and "% of total", never a scheduling decision.

    def bf16_kv_bytes_per_token(self) -> int:
        # K and V, every layer, per KV head, head_dim, 2 bytes (bf16).
        return 2 * self.layers * self.n_kv_heads * self.head_dim * 2


PRESETS = {
    # layers, n_kv_heads, head_dim, weight_gb   (the three we benched this quarter)
    "qwen2.5-7b":      ModelConfig("Qwen2.5-7B",      28, 4, 128, 15.2),
    "llama-3.1-8b":    ModelConfig("Llama-3.1-8B",    32, 8, 128, 16.1),
    "mistral-7b-v0.3": ModelConfig("Mistral-7B-v0.3", 32, 8, 128, 14.5),
}


@dataclass(frozen=True)
class Int4Calib:
    # int4_protected per-token KV bytes as a fraction of bf16 (data ~0.25 + sidecar).
    # 0.555 reproduces the AUDITED ~1.8x net density; 0.50 = the 2.0x bookkeeping number.
    per_token_frac: float = 0.555
    # Fixed int4-only HBM tax (CUDA-graph / kernel workspaces), independent of load.
    fixed_tax_gb: float = 0.5
    # Per-active-slot PagedKVWriter staging pool (length-independent). THE crossover
    # driver. ESTIMATE pending pod measurement (see measure_stage_pool()).
    stage_per_slot_mb: float = 24.0

    def __post_init__(self):
        if not (0.0 < self.per_token_frac < 1.0):
            raise ValueError("per_token_frac must be in (0,1)")


# --------------------------------------------------------------------------- #
# Per-sequence cost (the scheduler's decision axis = same workload, not same pool)
# --------------------------------------------------------------------------- #
def bf16_seq_bytes(mc: ModelConfig, length: int) -> float:
    return mc.bf16_kv_bytes_per_token() * length


def int4_seq_marginal_bytes(mc: ModelConfig, cal: Int4Calib, length: int) -> float:
    """Marginal HBM to host ONE sequence in the int4 pool (excludes the pool's
    one-time fixed_tax_gb): per-slot staging + int4 per-token KV."""
    return cal.stage_per_slot_mb * MB + cal.per_token_frac * mc.bf16_kv_bytes_per_token() * length


def crossover_length(mc: ModelConfig, cal: Int4Calib) -> float:
    """L* where int4's marginal per-seq cost == bf16's.
        stage + frac*c*L == c*L  ->  L* = stage / ((1-frac)*c)
    Below L*, bf16 is smaller for that sequence; above, int4 is. Independent of
    batch and of the fixed tax (that is a separate pool-open cost)."""
    c = mc.bf16_kv_bytes_per_token()
    return (cal.stage_per_slot_mb * MB) / ((1.0 - cal.per_token_frac) * c)


# --------------------------------------------------------------------------- #
# Workload policies (totals over a set of resident sequence lengths)
# --------------------------------------------------------------------------- #
def total_bf16(mc: ModelConfig, lengths) -> float:
    return mc.weight_gb * GB + sum(bf16_seq_bytes(mc, L) for L in lengths)


def total_int4(mc: ModelConfig, cal: Int4Calib, lengths) -> float:
    if not lengths:
        return mc.weight_gb * GB
    return (mc.weight_gb * GB + cal.fixed_tax_gb * GB
            + sum(int4_seq_marginal_bytes(mc, cal, L) for L in lengths))


def _partition(mc, cal, lengths):
    """Route each sequence to its cheaper pool: int4 if its marginal int4 cost
    (staging + int4 KV) beats bf16 KV, else bf16. Returns (int4-routed, bf16-routed)."""
    hi, lo = [], []
    for L in lengths:
        (hi if int4_seq_marginal_bytes(mc, cal, L) < bf16_seq_bytes(mc, L) else lo).append(L)
    return hi, lo


def total_hybrid_two_pool(mc: ModelConfig, cal: Int4Calib, lengths):
    """#4 NAIVE: keep both pools open; route each sequence to its cheaper pool.
    Pays fixed_tax once (int4 pool exists). NOT guaranteed <= bf16 -- it loses by
    up to fixed_tax when there is too little long-sequence load to amortize it."""
    routed_int4, routed_bf16 = _partition(mc, cal, lengths)
    total = mc.weight_gb * GB
    total += (cal.fixed_tax_gb * GB) if routed_int4 else 0.0
    total += sum(int4_seq_marginal_bytes(mc, cal, L) for L in routed_int4)
    total += sum(bf16_seq_bytes(mc, L) for L in routed_bf16)
    return total, len(routed_int4), len(routed_bf16)


def total_hybrid_guarded(mc: ModelConfig, cal: Int4Calib, lengths) -> float:
    """#4 SMART: open the int4 pool only if doing so is net-positive. By
    construction = min(bf16_only, two_pool) -> UNCONDITIONALLY <= bf16."""
    two_pool, _, _ = total_hybrid_two_pool(mc, cal, lengths)
    return min(total_bf16(mc, lengths), two_pool)


def total_load_switch(mc: ModelConfig, cal: Int4Calib, lengths) -> float:
    """#6: one pool at a time; whole resident set runs bf16 OR int4, whichever is
    smaller. min(bf16_only, int4_only) -> UNCONDITIONALLY <= bf16, but cannot MIX
    (short seqs pay int4 treatment when the system has flipped)."""
    return min(total_bf16(mc, lengths), total_int4(mc, cal, lengths))


# --------------------------------------------------------------------------- #
# Workload generation
# --------------------------------------------------------------------------- #
def make_workload(spec: str, seed: int = 0):
    """spec forms:
        uniform:L:n                  -> n sequences all length L
        unif:Lo:Hi:n                 -> n ~ U(Lo,Hi)
        lognormal:muLnK:sigma:n      -> n ~ lognormal; median length = e^muLnK *1000? no:
                                        median = exp(mu)*1; we take mu=ln(medianTokens)
        mix:short_frac:Lshort:Llong:n-> bernoulli mixture of two lengths
    Lengths are clamped to >=1 and rounded to int tokens."""
    rng = random.Random(seed)
    parts = spec.split(":")
    kind = parts[0]
    if kind == "uniform":
        L, n = int(parts[1]), int(parts[2])
        return [L] * n
    if kind == "unif":
        lo, hi, n = int(parts[1]), int(parts[2]), int(parts[3])
        return [rng.randint(lo, hi) for _ in range(n)]
    if kind == "lognormal":
        median_tokens, sigma, n = float(parts[1]), float(parts[2]), int(parts[3])
        mu = math.log(median_tokens)
        return [max(1, int(rng.lognormvariate(mu, sigma))) for _ in range(n)]
    if kind == "mix":
        sf, ls, ll, n = float(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
        return [ls if rng.random() < sf else ll for _ in range(n)]
    raise ValueError(f"bad workload spec: {spec}")


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def _fmt_gb(b: float) -> str:
    return f"{b / GB:8.2f}"


def report_workload(mc: ModelConfig, cal: Int4Calib, lengths, label: str):
    bf16 = total_bf16(mc, lengths)
    i4 = total_int4(mc, cal, lengths)
    two, n_i4, n_bf = total_hybrid_two_pool(mc, cal, lengths)
    guarded = total_hybrid_guarded(mc, cal, lengths)
    lsw = total_load_switch(mc, cal, lengths)
    Lstar = crossover_length(mc, cal)
    n = len(lengths)
    mean_L = sum(lengths) / n if n else 0
    print(f"\n=== {label} : {mc.name} | n={n} seqs, mean len={mean_L:,.0f} tok | "
          f"crossover L*={Lstar:,.0f} tok ===")
    print(f"  {'policy':<26}{'total HBM':>11}{'vs bf16':>11}{'saved':>9}   note")
    base = bf16
    def row(name, val, note=""):
        d = val - base
        pct = (-d / base * 100.0) if base else 0.0
        print(f"  {name:<26}{_fmt_gb(val)} GB{_fmt_gb(d):>9} GB{pct:7.1f}%   {note}")
    row("bf16-only", bf16, "baseline")
    row("int4-only", i4, f"{'WIN' if i4 < bf16 else 'LOSS'} at this load")
    row("hybrid two-pool (#4)", two, f"route {n_i4} int4 / {n_bf} bf16  "
        f"{'<=bf16' if two <= bf16 + 1e-6 else 'EXCEEDS bf16!'}")
    row("hybrid guarded (#4*)", guarded, "min(bf16, two-pool) -> <=bf16 always")
    row("load-switch (#6)", lsw, "min(bf16, int4-only) -> <=bf16 always")


def report_crossover(mc: ModelConfig, cal: Int4Calib):
    c = mc.bf16_kv_bytes_per_token()
    print(f"\n=== crossover : {mc.name} ===")
    print(f"  bf16 KV per token      : {c:,} B/token ({c/KB:.1f} KB)  "
          f"[2 * {mc.layers}L * {mc.n_kv_heads}kvH * {mc.head_dim}D * 2B]")
    print(f"  int4 per-token frac    : {cal.per_token_frac:.3f} of bf16  "
          f"(=> {1/cal.per_token_frac:.2f}x net density)")
    print(f"  per-slot staging pool  : {cal.stage_per_slot_mb:.1f} MB/slot   "
          f"<-- ESTIMATE; measure on pod")
    print(f"  fixed int4 tax (pool)  : {cal.fixed_tax_gb:.2f} GB one-time")
    print(f"  => per-seq crossover L*: {crossover_length(mc, cal):,.0f} tokens")
    print(f"     (seqs longer than L* are cheaper in int4; shorter in bf16)")
    print("\n  L* sensitivity to the un-measured staging pool:")
    print(f"  {'stage MB/slot':>14}{'L* (tokens)':>14}")
    for s in (8, 16, 24, 32, 48, 64, 96):
        Lst = crossover_length(mc, replace(cal, stage_per_slot_mb=s))
        print(f"  {s:>14}{Lst:>14,.0f}")


def report_sweep(mc: ModelConfig, cal: Int4Calib, concurrency: int = 64, seed: int = 0):
    print(f"\n=== mean-length sweep : {mc.name} | concurrency={concurrency} | "
          f"L*={crossover_length(mc, cal):,.0f} tok ===")
    print(f"  {'mean len':>9}{'bf16 GB':>10}{'int4 GB':>10}{'guarded GB':>12}"
          f"{'switch GB':>11}{'best saved':>11}")
    for med in (256, 512, 1024, 2048, 4096, 8192, 16384, 32768):
        lengths = make_workload(f"lognormal:{med}:0.6:{concurrency}", seed=seed)
        bf16 = total_bf16(mc, lengths)
        i4 = total_int4(mc, cal, lengths)
        g = total_hybrid_guarded(mc, cal, lengths)
        lsw = total_load_switch(mc, cal, lengths)
        best = min(i4, g, lsw)
        saved = (bf16 - best) / bf16 * 100.0
        print(f"  {med:>9,}{_fmt_gb(bf16):>10}{_fmt_gb(i4):>10}{_fmt_gb(g):>12}"
              f"{_fmt_gb(lsw):>11}{saved:>10.1f}%")


def measure_stage_pool():
    """TODO (pod, venv-vllm): pin stage_per_slot_mb empirically instead of the
    estimate. Procedure: load the int4_protected backend, snapshot
    torch.cuda.memory_allocated(), admit one max-len sequence, snapshot again;
    the delta minus (int4 per-token * len) is the per-slot staging + amortized
    fixed tax. Repeat at two batch sizes to separate fixed_tax from per-slot.
    Then feed --stage-per-slot-mb / --fixed-tax-gb here for an exact crossover."""
    raise NotImplementedError("run on the GPU pod; see docstring")


# --------------------------------------------------------------------------- #
# Self-test (invariant gates) -- the "test harness" part
# --------------------------------------------------------------------------- #
def selftest() -> int:
    mc = PRESETS["qwen2.5-7b"]
    cal = Int4Calib()
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    print("hybrid_kv_scheduler selftest")

    # 1. bf16 per-token analytical value (Qwen2.5-7B): 2*28*4*128*2 = 57,344 B.
    check("bf16 per-token bytes == 57,344 (Qwen2.5-7B)",
          mc.bf16_kv_bytes_per_token() == 57344)

    # 2. Crossover formula consistency: a seq just below L* prefers bf16, just above prefers int4.
    Lstar = crossover_length(mc, cal)
    below, above = int(Lstar * 0.9), int(Lstar * 1.1) + 1
    check("seq < L* cheaper in bf16",
          bf16_seq_bytes(mc, below) < int4_seq_marginal_bytes(mc, cal, below))
    check("seq > L* cheaper in int4",
          int4_seq_marginal_bytes(mc, cal, above) < bf16_seq_bytes(mc, above))

    # 3. THE GUARANTEE: guarded-hybrid and load-switch never exceed bf16, for many
    #    random workloads incl. adversarial all-short and all-long.
    rng = random.Random(1)
    guard_ok = switch_ok = True
    for _ in range(400):
        spec = rng.choice([
            f"unif:8:200:{rng.randint(1,128)}",        # all-short (adversarial for #4)
            f"unif:40000:60000:{rng.randint(1,64)}",   # all-long
            f"lognormal:{rng.choice([256,1024,8192])}:0.8:{rng.randint(1,128)}",
            f"mix:{rng.random():.2f}:64:48000:{rng.randint(1,96)}",
        ])
        lengths = make_workload(spec, seed=rng.randint(0, 9999))
        bf16 = total_bf16(mc, lengths)
        guard_ok &= total_hybrid_guarded(mc, cal, lengths) <= bf16 + 1e-3
        switch_ok &= total_load_switch(mc, cal, lengths) <= bf16 + 1e-3
    check("guarded hybrid (#4*) <= bf16 over 400 random workloads", guard_ok)
    check("load-switch (#6) <= bf16 over 400 random workloads", switch_ok)

    # 4. The HONEST caveat is real: naive two-pool (#4) CAN exceed bf16 when a FEW
    #    sequences sit just above L* -- they route to int4 and open the pool, but
    #    their small per-seq savings don't cover fixed_tax. (All-short load does NOT
    #    trigger it: the router keeps shorts in bf16 and never opens the pool.)
    few_long = [int(Lstar * 1.5)] * 3            # 3 seqs just above the crossover
    two_fl, n_i4, _ = total_hybrid_two_pool(mc, cal, few_long)
    all_short = make_workload("uniform:64:32", seed=0)
    two_sh, _, _ = total_hybrid_two_pool(mc, cal, all_short)
    check("naive two-pool EXCEEDS bf16 with a few seqs just above L* (caveat real)",
          n_i4 == 3 and two_fl > total_bf16(mc, few_long) + 1e-3)
    check("naive two-pool == bf16 on all-short load (router never opens int4 pool)",
          abs(two_sh - total_bf16(mc, all_short)) < 1e-3)

    # 5. Monotonicity: int4-only savings grow as mean length grows.
    def i4_saving(med):
        L = make_workload(f"uniform:{med}:64", 0)
        return total_bf16(mc, L) - total_int4(mc, cal, L)
    check("int4-only saving increases with sequence length",
          i4_saving(256) < i4_saving(4096) < i4_saving(32768))

    # 6. Calibration sanity: on a saturation workload (many long seqs), int4-only net
    #    density ~ 1/per_token_frac (~1.8x) vs bf16 KV (weights excluded).
    longw = make_workload("uniform:32768:64", 0)
    kv_bf16 = total_bf16(mc, longw) - mc.weight_gb * GB
    kv_i4 = total_int4(mc, cal, longw) - mc.weight_gb * GB
    density = kv_bf16 / kv_i4
    check(f"int4 net KV density ~1.8x (got {density:.2f}x)", 1.7 <= density <= 1.9)

    # 7. Selection sanity: a tiny seq routes bf16, a huge seq routes int4.
    hi, lo = _partition(mc, cal, [50, 50000])
    check("router sends short->bf16, long->int4", hi == [50000] and lo == [50])

    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description="Hybrid bf16/int4_protected KV scheduler cost model")
    ap.add_argument("--model", default="qwen2.5-7b", choices=sorted(PRESETS))
    ap.add_argument("--per-token-frac", type=float, default=None,
                    help="int4 per-token KV bytes / bf16 (default 0.555 = ~1.8x net density)")
    ap.add_argument("--stage-per-slot-mb", type=float, default=None,
                    help="per-active-slot staging pool MB (the crossover driver; measure on pod)")
    ap.add_argument("--fixed-tax-gb", type=float, default=None,
                    help="fixed int4-only HBM tax (CUDA-graph/kernel)")
    ap.add_argument("--concurrency", type=int, default=64)
    ap.add_argument("--workload", default=None,
                    help="uniform:L:n | unif:Lo:Hi:n | lognormal:median:sigma:n | mix:sf:Ls:Ll:n")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--crossover", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    mc = PRESETS[args.model]
    cal = Int4Calib()
    over = {}
    if args.per_token_frac is not None:
        over["per_token_frac"] = args.per_token_frac
    if args.stage_per_slot_mb is not None:
        over["stage_per_slot_mb"] = args.stage_per_slot_mb
    if args.fixed_tax_gb is not None:
        over["fixed_tax_gb"] = args.fixed_tax_gb
    if over:
        cal = replace(cal, **over)

    did = False
    if args.crossover:
        report_crossover(mc, cal); did = True
    if args.workload:
        report_workload(mc, cal, make_workload(args.workload, args.seed),
                        f"workload {args.workload}"); did = True
    if args.sweep or not did:
        report_sweep(mc, cal, concurrency=args.concurrency, seed=args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
