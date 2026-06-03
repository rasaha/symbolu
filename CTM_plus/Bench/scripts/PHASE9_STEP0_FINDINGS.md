# Phase 9 Step 0 — CPU model of the Route-A read-skip prize (the pre-pod gate)

> **Status: MODEL RESULT, $0, CPU-only. Go/no-go screen for booking a GPU pod.**
> Companion to `simulate_two_tier_kv.py` (extended this step) and
> `TWO_TIER_ARCHITECTURE_NOTE.md`. This step answers the *only* question that
> gates GPU spend: **is the read-skip prize real at an _achievable_ skip rate,
> or only at a hand-picked `cold_read_frac=0.15` dial?**

## What Step 0 had to decide

Per `PHASE9_ROUTE_A_READSKIP_NEXT_SESSION.md`:

> STEP 0 — model it (CPU, $0). Extend `simulate_two_tier_kv.py` so
> `cold_read_frac` reflects what Route-A can REALLY skip (sink+recent kept,
> middle skipped). **If the prize is <10% gain at achievable skip rates → STOP,
> don't book a pod.**

The prior model treated `cold_read_frac` as a **free dial** — set it to 0.15 and
read off ~1.9×. That is circular: it assumes the answer. The real question is
whether 0.15 is *achievable* under an attention-safe keep-set.

## The extension: derive `cold_read_frac` from the keep-set (not a dial)

Added `achievable_cold_read_frac(seq_len, n_sink, n_recent, middle_keep_frac,
hot_frac)` + a `--derive-crf` mode. An attention-safe Route-A skip MUST keep:

- the `n_sink` attention sinks (StreamingLLM uses 4),
- the `n_recent`-token recent window,

and within the remaining **middle** it can keep only `middle_keep_frac` (the
heavy hitters; H2O premise). The realised cold-tier read fraction is then a
**structural consequence** of `(seq_len, keep-set sizes, hot_frac)`:

```
cold_read_frac = (always_read_in_cold·1.0 + middle_in_cold·middle_keep) / cold_total
```

The hot (bf16) tier absorbs the always-read set first; whatever spills into the
cold tier is still read every step. **Floor = `middle_keep_frac`** (long seq);
it rises toward **1.0** as `seq_len` shrinks toward the keep-set size.

## The result (defaults: sink=4, recent=512, middle-keep=0.15, hot_frac=0.05)

`python CTM_plus/Bench/scripts/simulate_two_tier_kv.py --derive-crf`

| seq_len | derived crf | tps ratio | gain vs all-int4 | density | clears +10%? |
|---:|---:|---:|---:|---:|:--:|
| 1 024  | 0.556 | 0.561× | +0.241 | 1.76× | yes (modest) |
| 4 096  | 0.218 | 1.371× | +1.051 | 1.76× | yes |
| 8 192  | 0.162 | 1.806× | +1.486 | 1.76× | yes |
| 16 384 | 0.150 | 1.932× | +1.612 | 1.76× | **yes (headline)** |
| 32 768 | 0.150 | 1.932× | +1.612 | 1.76× | **yes (headline)** |

**The headline 0.15 is real — but EARNED BY LENGTH, not assumed.** It is the
floor the derived crf reaches once the cache dwarfs the sink+recent keep-set
(≥8k). All densities stay at 1.76× (91% of int4's gain) because cold tokens are
still *stored* in int4 regardless of how often they are read.

### Robustness checks

- **Sequence-length floor.** At `seq_len ≤ keep-set` (256/512 with recent=512)
  the derived crf pins to **1.0** → no skip, no win (−0.004, i.e. = compression).
  The prize genuinely vanishes at short context; nothing to skip.
- **Pessimistic keep fraction (2×).** At `--middle-keep 0.30` (double the heavy
  hitters retained — a hedge against attention being less concentrated than H2O
  assumes), read-skip *still* clears the bar at long context: ≈**1.0× tps vs
  all-int4's 0.32×** (+0.70 gain). So the verdict is not knife-edge on the 0.15
  assumption — there is ~2× of slack in the achievable keep fraction.

## Verdict: **PROCEED to Step 1 (GPU smoke). Do NOT stop.**

The prize clears the +10% bar comfortably at the long-context regime — the model
predicts ~1.9× tps at 91% density when `seq_len ≥ 8k`, and still wins at 2× the
keep fraction. This is **not** a "<10% gain at achievable skip rates" — so the
go/no-go screen says **book the pod.**

Two constraints Step 0 hands to the GPU experiment:

1. **The A/B MUST use a long-context workload (≥8k, ideally the 32k chat /
   needle setup).** At short context there is structurally nothing to skip, so a
   short-context A/B would *falsely* show read-skip ≈ all-int4 and bury a real
   long-context win.
2. **Step 0 prices only throughput. It does NOT model the two real risks** — the
   GPU run still must measure both (these are Steps 2–3, unchanged):
   - **Quality (H2O risk):** does needle + MMLU survive the skip at the achieved
     crf on the mml=8192 mask? A faster-but-wrong skip is a FAILURE.
   - **Integration/dispatch tax:** the per-step skip decision is the same
     hot-path call that cost Phase 8 −20%. If the gain is eaten in Python
     dispatch → that is the empirical case FOR PCAM hardware (Step 3).

## Reproduce

```
python CTM_plus/Bench/scripts/simulate_two_tier_kv.py --selftest        # 13/13
python CTM_plus/Bench/scripts/simulate_two_tier_kv.py --derive-crf       # the table above
python CTM_plus/Bench/scripts/simulate_two_tier_kv.py --derive-crf --middle-keep 0.30   # pessimistic
python CTM_plus/Bench/scripts/simulate_two_tier_kv.py --derive-crf --seq-lens 256,512,768  # the floor
```
