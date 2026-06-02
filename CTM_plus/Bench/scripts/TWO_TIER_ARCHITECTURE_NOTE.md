# Two-Tier KV Cache — forward-looking architecture note (design candidate, NOT built)

> **Status: DESIGN CANDIDATE. No implementation. No GPU work.** Captures the
> concept, why it rescues the dead eviction work, the central (unmeasured)
> hypothesis, and the honest dependency on the Route-A integration shape. Paired
> with a CPU **simulator** (`simulate_two_tier_kv.py`) that *sizes the prize* from
> already-measured numbers — it models, it does not benchmark a real system.

## One-line idea

Split the KV-cache into **hot (bf16, full speed)** and **cold (int4_protected,
4× dense)** tiers. When the hot tier fills, **demote** the lowest-attention blocks
to the int4 tier instead of **deleting** them. Nothing is lost; cold tokens cost
4× less memory; and — the key bet — the int4 *decode tax is paid only on the cold
minority*, so hot tokens keep bf16 speed.

## Why this is a COMPOSITION, not a pivot

int4_protected stays the moat (1.83× density, quality-locked, MMLU-validated).
Two-tier *uses* it as the cold store. It also **rescues the Phase 4/8 eviction
work**, which failed as a standalone throughput play:

| Approach | Question it answers | Outcome (measured) |
|---|---|---|
| Standalone eviction (Phase 4/8) | "which token to **delete**?" | algorithm GREEN (−11% vs LRU) but **−20% net throughput** to vLLM Evictor-ABC dispatch tax → dead end |
| Pure int4_protected | "store **everything** in int4" | max density, but **every** token pays the decode tax (0.22–0.54×) |
| **Two-tier** | "which token to **demote** to int4?" | **hypothesis:** density of int4 on cold tokens + bf16 speed on hot tokens; nothing deleted (no quality loss) |

The shift from *delete* to *demote* turns eviction's fatal flaw (losing
information) into a non-issue — because int4_protected gives a cheap place to put
demoted data instead of the trash.

## ⚠ CPU MODEL RESULT (run before reading further) — the prize is NOT free

`simulate_two_tier_kv.py`, fed the measured anchors (int4 0.32× tps, 1.83×
density), returns **LIKELY NOT WORTH IT**, and exposes a structural reason:

> **Density and throughput-gain are in DIRECT TENSION.** Keeping most of int4's
> density requires a *mostly-cold* cache — but cold tokens are exactly the ones
> paying the int4 decode tax *every decode step*. So the aggregate cost approaches
> all-int4, and the throughput gain that preserves ≥50% density is only ~+0.05.

The model sweep (5% bookkeeping):

| hot_frac | tps ratio | gain vs all-int4 | density | density kept |
|---:|---:|---:|---:|---:|
| 0.10 | 0.328× | +0.008 | 1.69× | 83% |
| 0.25 | 0.369× | +0.049 | 1.52× | 62% |
| 0.50 | 0.467× | +0.147 | 1.29× | 35% |
| 0.75 | 0.637× | +0.317 | 1.13× | 15% |

You only get real speed by giving up most of the density. **So "compression-
demotion" two-tier (where BOTH tiers are fully read each step) is a speed↔density
DIAL, not a free win.**

**The version that WOULD win is different:** true **eviction** (H2O /
StreamingLLM) where cold tokens are *read less often or skipped*, not merely
stored smaller. That changes the cost model (cold tokens stop costing per-step) —
but it's a *drop/skip* mechanism with real quality risk, and it's exactly the
Phase 4/8 eviction work that hit the −20% integration tax. So the honest path
isn't "compress-demote"; it's "**skip cold reads via Route-A**" — and that lands
us right back on the unsolved integration-shape problem.

**Revised recommendation:** two-tier as *compression-demotion* is **not worth
building** (the model says it's a dial, not a gain). Two-tier as *attention-based
skip/eviction* (cold tokens read rarely) is the only version with upside — and it
is gated entirely on Route-A solving the hot-path integration tax. Don't build
either until Route-A is proven; the cold-read-skip variant is the one to model
next (this simulator does NOT yet model skipped reads).

## The central hypothesis (UNMEASURED — this is the whole risk)

> If attention is concentrated (a small fraction of tokens carry most of the
> attention mass — the "sink + recent + few entities" pattern StreamingLLM/H2O
> exploit), then keeping only that hot fraction in bf16 and demoting the cold
> majority to int4 yields **most of int4's density win while paying the int4
> decode tax on only the cold minority** — i.e. better aggregate throughput than
> all-int4, at near-int4 density, with zero deletion/quality loss.

This is plausible (attention IS concentrated in practice) but **completely
unproven for this stack.** It could be eaten by: (a) demotion/promotion
bookkeeping overhead, (b) the same Route-A integration tax, (c) hot/cold
mis-classification thrashing tokens between tiers.

## The honest dependency: it inherits the integration problem

`PHASE8_EVICTION_AUDIT.md` was blunt: the −20% tax is **NOT the algorithm** — it's
vLLM calling our Python policy in hot paths that expect C-speed (a Cython port
recovered 0pp). Two-tier still makes demotion decisions in that hot path, so it
**inherits the same problem.** The audit's answer is **Route-A** — wire the
decision through the `cache_kv` attention hook (`int4_cache_kv_route_a.py`,
Days 1-3 landed on CPU / 12 tests, Days 4-5 GPU verification PENDING) instead of
vLLM's slow Evictor-ABC. **So the first step of two-tier is NOT "build two-tier" —
it's "finish Route-A GPU verification," the unsolved integration shape.**

## Pieces that already exist (the building blocks)

- `attention_evictor.py` — the 4-signal block scorer (attention EMA + importance +
  CMS frequency + recency). This becomes the **demotion-priority** scorer.
- `int4_protected` writer/reader — the **cold tier** store (proven, quality-locked).
- `int4_cache_kv_route_a.py` — the hook surface that would carry attention scores
  to the demotion decision without the Evictor-ABC tax (GPU verification pending).
- `swap_telemetry.py` / TIER5A — byte-clean swap machinery (a precedent for safe
  tier movement).

So two-tier is mostly *wiring existing, individually-validated pieces* through the
Route-A shape — not green-field — which is why it's the most coherent "next big
bet" rather than a moonshot.

## Honest non-goals / risks

- **Not a throughput silver bullet.** Best case it *blunts* the decode tax on hot
  tokens; it does not make int4 attention itself faster (that's 6F, bounded ~0.3×).
- **Promotion path is the hard part.** A demoted token that becomes hot again must
  re-promote to bf16 without a stall or a recompute — easy to get wrong.
- **Quality must stay locked.** Demotion to int4 must use the *protected* path
  (the mml=8192-calibrated mask), or you reintroduce the collapse risk.
- **Closed tracks stay closed** — no int8-V / n_protect↓ / sidecar diet sneaking
  in via the cold tier.

## Recommended sequencing (disciplined, cheapest-first)

1. **Size the prize on CPU first** — `simulate_two_tier_kv.py` (this commit):
   parameterize with measured costs (bf16 decode, int4 tax 0.22–0.54×, hot
   fraction) → does the model predict a worthwhile aggregate gain BEFORE any
   build? If the model says "<10% better than all-int4 even at optimistic hot
   fractions," don't build it.
2. **Route-A GPU verification** (the gating integration shape; already half-landed).
3. **Two-tier prototype** behind a flag, with the byte-eq + COLLAPSE=0 + MMLU
   oracle, only if (1) sizes a real prize and (2) Route-A clears the tax.

## Why write this down now

So the convergence — int4_protected + the dead eviction work + the throughput
weakness — is captured as ONE coherent design candidate, not three orphaned
threads. The theme of the whole 6M/6N/6O session holds here too: **the algorithm
was never the bottleneck; the integration is.** Two-tier is worth it only if
Route-A solves the integration, and only if the CPU model says the prize is real.
