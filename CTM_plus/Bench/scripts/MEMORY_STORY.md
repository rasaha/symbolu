# int4_protected — memory / capacity / fidelity scorecard (clean, post-fix)

> **Read this first.** This is **not** a "saves memory" story — the clean data
> contradicts that. At equal `gpu_memory_utilization`, int4_protected uses
> **~4.7 GB *more* total HBM than bf16** (sidecar + CUDA-graph tax). What's real
> and sellable is: **near-bf16 quality at int4 KV *density* (≈2× concurrency per
> fixed budget), at ~1.7× slower decode** — a quality/capacity/throughput
> tradeoff. The protect sidecar buys **fidelity (+20.4 pt)**, and it *costs*
> memory. All numbers below are clean post-collapse-fix (6K.7/6K.9/6K.10);
> pre-fix benches measured garbage decode.

## 1. Memory & capacity (A100-80GB, gpu_util=0.5)

| mml | bf16 HBM | int4 HBM | **Δ HBM** | bf16 max-conc | int4 max-conc | conc ratio |
|---|---|---|---|---|---|---|
| 8192 | 39.1 GB | 43.8 GB | **+4.68** | 55.3 | 110.6 | 2.00× |
| 16384 | 38.0 GB | 42.7 GB | **+4.68** | 26.4 | 52.8 | 2.00× |
| 32768 | 35.9 GB | 40.5 GB | **+4.66** | 12.0 | 23.9 | 1.99× |

* **max-concurrency ≈ 2×** — int4 packs ~4× tokens/block, so the *same* KV
  budget holds ~2× the full-context sequences. **But this is vLLM bookkeeping**
  (`num_blocks × block_size / mml`); see §4 for the net-win caveat.
* **Total HBM is +4.7 GB higher** for int4 (it does **not** shrink the
  footprint at equal util). The win is *density within the budget*, not a
  smaller budget.

### Sidecar tax (6G audit, mml=32K; fixed 16.4% of KV cache)

| tensor | scaling | GB | share |
|---|---|---|---|
| k_protect_ext | per_token | 0.82 | 23.8% |
| v_scale_ext / v_xmin_ext | per_token | 0.65 ea | 19.0% ea |
| k_scale_ext / k_xmin_ext | per_block | 0.65 ea | 19.0% ea |
| _k_stage_pool + counters | per_slot | <0.01 | <0.2% |

Diet options (audit recommendation only — **no implementation**):

| id | save | risk | targets | kernel? |
|---|---|---|---|---|
| A | ~0.65 GB | moderate | v_scale_ext, v_xmin_ext (V groups 4→2) | yes (V kernel) |
| C | ~1.72 GB | high | all scale/xmin + k_protect_ext (bf16→fp8 e4m3) | yes (read+write) |
| F | ~0.33 GB | moderate | k_protect_ext (n_protect 5→3) | no (recalibration) |
| D | ~0.82 GB | low semantic / high impl | k_protect_ext (inline into kv_cache) | yes (layout change) |

**A+F+C stacked ≈ 3.19 GB < the ~4.7 GB delta** → diet alone likely can't reach
HBM parity; either add **D** too, or accept protected int4 as a quality feature.
No single tensor dominates.

## 2. Throughput (median agg_tps, long-context bench)

| mml | bf16 | int4 | int4/bf16 |
|---|---|---|---|
| 8192 (B=8) | 131.9 | 74.4 | 0.56× |
| 16384 (B=8) | 70.9 | 46.3 | 0.65× |
| 32768 (B=8) | 34.7 | 23.1 | 0.67× |

int4 decode is **~1.5–1.9× slower** (extra dequant + protect blend work). A real
cost to disclose.

## 3. Fidelity — the actual win (clean post-fix)

| metric | naive int4 | protected int4 | bf16 |
|---|---|---|---|
| token-agreement vs bf16 | 0.533 | **0.737** (**+0.204**) | 1.000 |
| easy needle (8–32K) | 0.96–1.00 | 0.96–1.00 | 1.00 |
| hard needle, retrieval (60 items) | 0.915 | **0.964** (**+0.049**) | 1.000 |
| hard needle genuine misses | 5 (4 V + 1 K) | **2 (2 V, 0 K)** | 0 |

**Protect's value is fidelity, not memory:** +20.4 pt token-agreement (large,
robust) and a modest stressed-retrieval gain. Easy needle is saturated (naive
already ≈ bf16). Remaining hard-needle misses are V-bound → int8-V/protect-V is
the next quality lever if needed.

## 4. The one open number: is the 2× concurrency a NET win?

The 2× is **audited (bookkeeping)**, not demonstrated. The long-context bench
scored `NOT_JUSTIFIED` on **total HBM** (the wrong axis) and 6H was
`INCONCLUSIVE` (short prompts never saturated the KV budget). So we do **not yet
know** whether int4 actually serves ~2× concurrent long-context requests before
saturating, given its +4.7 GB overhead.

**Settling it requires a true-saturation re-run** — fill prompts to ≈mml and
ramp B until a cell saturates (preempt/OOM). If protected sustains a clean
~2×-higher B than bf16 → real capacity story; if it saturates near bf16's B →
bookkeeping, drop the capacity claim. This is a **post-diet** step (see §5
recommendation): not worth running until a dieted config first reaches HBM
parity. `phase6k13_capacity_demo.py` is the audit **scorecard** (this page);
the live saturation runner is a separate future bench.

## 5. Recommendation matrix

| pick | when |
|---|---|
| **bf16** | latency- or quality-critical; HBM not the constraint |
| **naive int4** | you want raw KV density and can accept ~0.53 bf16 fidelity |
| **protected int4** | you want **most of bf16's fidelity (0.74 agreement)** at int4 KV density, and can pay ~1.7× decode latency + ~4.7 GB sidecar overhead |

## 6. Honest verdict

**Precise verdict: protected int4 is QUALITY-POSITIVE (vs naive) but
CAPACITY-NEGATIVE (vs bf16) in the current implementation** — a **quality
feature, not a memory feature**. Keep it; don't pitch memory savings.
- ✅ **Quality-positive:** +20.4 pt token-agreement over naive, modest
  hard-retrieval gain (misses 5→2), decode now correct in both modes. Protect is
  ~free over naive (same sidecars), so always prefer protected to naive.
- ❌ **Capacity-negative:** +4.7 GB HBM vs bf16 (sidecars dominate, overwhelming
  the int4 KV savings) and ~1.5–1.9× slower. The ~2× concurrency is bookkeeping.
- ❌ **Concurrency cap (6K.13 live demo):** the writer keeps a per-slot staging
  pool sized to `PHASE6_MAX_ACTIVE_SLOTS` (default **8**); at B≥9 without
  bumping it the protected cell errored `PagedKVWriter slot pool exhausted`
  (bf16 ran B=128 clean). Bumping it costs *more* memory on top of +4.7 GB, and
  `evict_sequence` was **not wired to sequence completion** → slots leaked in a
  long server.
- 🔧 **Slot lifecycle FIXED (6K.14):** both pieces are now wired —
  (1) `PHASE6_MAX_ACTIVE_SLOTS` **auto-bumps** to vLLM `max_num_seqs` when unset
  (explicit env still wins; `PHASE6K14_AUTOBUMP_SLOTS=0` reverts), and
  (2) `gc_completed_slots()` runs each pure-decode step (precapture hook + eager
  path) to free slots of finished/recompute-preempted sequences
  (`PHASE6K14_EVICT_ON_DECODE=0` reverts). CPU regression
  `test_phase6k14_slot_gc.py` reproduces the wave-leak and proves the fix.
- ✅ **6K.14 Run 1 (mml=8192, gen=8): fix validated on GPU.** protected ran
  B=48→128 with `slots`=B, **zero slot-exhaustion / OOM / preempt** (vs the
  pre-fix B≥9 crash). The bookkeeping bug is gone.
- 🔁 **Capacity NOT yet demonstrated — Runs 1–3 didn't saturate.** gen=8/256/512
  all queue-drain to the sweep ceiling. **Why:** offline `generate([prompt]*B)`
  admits only what fits and drains the rest in waves, always completing — B is
  *submitted*, not *resident*, so B-ramp can't cliff. (Compounded by prompts
  under-filling and a preempt counter that read 0 always.) The harness correctly
  flags CEILING-NOT-REACHED and refuses the bogus 1.0×.
  **Estimated** signals only: (a) concurrency density (vLLM `max_conc` ÷ total
  HBM) = bf16 1.31 vs protected 2.38 → **~1.8× concurrent max-len seqs per GB**
  net of the +4.4 GB tax; (b) protected agg_tps **78–115 vs bf16 51–87** at
  mid/high B (gen 256–512) — a throughput *reversal* (gen=8's "0.8×" was
  prefill-dominated). Both **soften** the "capacity-negative" call (wrong axis:
  absolute footprint), but neither is *demonstrated sustained*.
- 🧪 **Pivot to direct observation (`--resident-pressure`).** New per-step probe
  records peak LIVE resident seqs + peak KV-block utilization;
  `saturation_observed = peak_util≥0.90 OR preempt OR oom`. Demonstrated max live
  concurrency = `peak_live` at saturation; `live_ratio` (protected/bf16) is the
  real number, `live_demonstrated=True` only when BOTH cells hit the block limit.
  Run 4: `--resident-pressure --max-tokens 2048 --prompt-frac 0.98
  --b-list 32,…,192`. Expect bf16 `peak_live≈55`, protected `≈110` → ~2×.
- ⚠️ **Diet ceiling A+F+C ≈ 3.19 GB < 4.7 GB delta** → diet alone likely can't
  reach HBM parity without option D (or accept it as a quality feature).

**Recommendation (Phase 6F gate):** *Proceed only with sidecar-diet experiments
and scorecarding. Do NOT start heavy Phase 6F kernel work until a dieted
protected-int4 config demonstrates an HBM advantage — or at least near-parity
with bf16 — while preserving most of the +20.4 token-agreement gain.* Price it as
**fidelity-per-GB** (+~25 token-agreement pts per GB of protect sidecar) with a
perplexity / small downstream check after each diet step.

## Sources
`audit_phase6g_sidecar_overhead.py`, `bench_phase6_long_context_gpu.py`,
`bench_phase6_h_high_load_gpu.py`, `bench_phase6j_quality_gpu.py`,
`phase6k11_needle_failuremode.py`, `phase6k12_hard_needle.py`,
`phase6k13_capacity_demo.py`, `phase6k14_saturation.py` (pending GPU run); verdict
context in `PHASE_6J_CORRECTED_VERDICT_FINDINGS.md`,
`PHASE_6K7_INT4_DISPATCH_FIX_FINDINGS.md` +
`PHASE_6K14_SLOT_LIFECYCLE_FINDINGS.md`.
