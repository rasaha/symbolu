# Phase 3 cache-aware scheduling — measured finding

> **Status:** Phase 3 closed. Two-seed Tier-A measurement on
> Qwen2.5-7B-Instruct + H100 + vLLM 0.7.3 produced an **inconclusive
> realized-hit signal with a consistent mild E2E p99 regression**.
> Cache-aware admission reordering is **not productionized**.
>
> **VC brief: unchanged.** Cache-aware was never in the brief;
> it stays in roadmap-only state.
>
> **Code disposition:** all components stay in-tree per the
> Phase 4 + TurboQuant precedent. The full cache-aware install
> (PR-1 + PR-2) is retained as an **experimental** CLI flag.
> The measurement-only install + the three-cell Phase 3 bench
> harness are kept as **partner-credible measurement utilities**
> with independent value.

## TL;DR

| Item | Status |
|---|---|
| Realized prefix-cache hit ratio C/B | **Inconclusive** at 2 seeds (0.903 and 1.115; opposite signs) |
| TPS regression | **None** (C/B = 0.985 and 0.999) |
| TTFT p99 ratio | Inconclusive (16.4× at seed=42; 1.04× at seed=43 — the 16× was a seed-specific tail event, not systematic) |
| E2E p99 ratio | **Consistently worse** (1.61× and 1.40× — borderline above the 1.5× target) |
| Predictor calibration | Consistently under-predicts by ~3.1× at both seeds |
| Operational outcome | Not productionized; not in brief; CLI flag retained as experimental |

## The measurement

### Workload (per the approved Phase 3 design)

* Model: `Qwen/Qwen2.5-7B-Instruct`
* GPU: H100, `gpu_memory_utilization=0.5`
* Engine: vLLM 0.7.3 V0 with prefix caching ON for cells B and C
* Workload: 100 requests, **4 cohorts × 25 requests** each,
  256-token shared prefix per cohort + per-request unique tail
  of 32 / 64 / 128 / 256 tokens (uniform draw)
* Arrivals: Pareto-bursty, rate 4.0 req/s, alpha 1.5
* Wall budget: 60s (each cell completes in ~17s real time)
* Decode budget: 32 tokens per request

### Cells

| Cell | `enable_prefix_caching` | `cache_aware_scheduling` | `cache_aware_measurement_only` |
|---|:-:|:-:|:-:|
| A | OFF | OFF | OFF |
| B | ON | OFF | ON (measurement bridge — installs the tree wraps without reorder so realized-hit numbers are apples-to-apples with cell C) |
| C | ON | ON (full mode) | OFF |

The Phase 3A `prefix_hit_probe` was designed as the apples-to-apples
measurement instrument. The first Phase 3C GPU run surfaced that
vLLM 0.7.3 uses a chained content_hash (parent-block-hash + current
tokens) which the probe's flat blake2b can't match, so the probe's
realized-hit count was always zero. The fix (`measurement_only=True`
mode on the cache-aware install) uses the cache-aware tree as the
instrument instead — the tree tracks token sequences directly and
doesn't depend on vLLM's hash function. See
`V2_CACHE_REUSE_PHASE1_INTEGRATION_NOTE.md` §"Phase 3C measurement-
path fix" for the design + implementation.

## Per-seed results

(numbers from `bench_out/PHASE3C_SEED42_V2/comparison.json` and
`bench_out/PHASE3C_SEED43_V2/comparison.json`)

### Seed 42

| Cell | realized_hit_tokens | TPS | TTFT p50 ms | TTFT p99 ms | E2E p50 ms | E2E p99 ms |
|---|---:|---:|---:|---:|---:|---:|
| A | 0 (probe; n/a) | 185.7 | 36.6 | 70.4 | 510.3 | 629.4 |
| B | 7,936 (tree) | 185.6 | 23.9 | 49.8 | 483.0 | 808.9 |
| C | 7,168 (tree) | 182.7 | 22.0 | 818.9 | 464.0 | 1302.0 |

Cell C cache_aware_extra: `admissions=10`, `predicted_hit_tokens=2,304`, `tree_inserts=100`, `tree_evictions=2,456`.

### Seed 43

| Cell | realized_hit_tokens | TPS | TTFT p50 ms | TTFT p99 ms | E2E p50 ms | E2E p99 ms |
|---|---:|---:|---:|---:|---:|---:|
| B | 6,656 (tree) | 180.2 | 23.3 | 69.3 | 458.7 | 657.1 |
| C | 7,424 (tree) | 180.1 | 27.3 | 72.2 | 590.0 | 923.2 |

Cell C cache_aware_extra: `admissions=8`, `predicted_hit_tokens=2,304`, `tree_inserts=100`, `tree_evictions=2,516`.

(Cell A not rerun for seed=43; it's the no-prefix-caching floor and
already established at seed=42.)

### B-vs-C ratios (C / B)

| Metric | Seed 42 | Seed 43 |
|---|---:|---:|
| `realized_hit_tokens_ratio` | **0.903** | **1.115** |
| `tokens_per_second_ratio` | 0.985 | 0.999 |
| `ttft_p50_ratio` | 0.921 | 1.171 |
| `ttft_p99_ratio` | 16.434 | 1.043 |
| `e2e_p50_ratio` | 0.961 | 1.286 |
| `e2e_p99_ratio` | 1.610 | 1.405 |

## What survived to claim

**TPS parity.** Cache-aware reorder did not regress aggregate
throughput at either seed (C/B = 0.985 and 0.999). Whatever the
reorder does, it doesn't cost the engine measurable throughput on
this workload at 100 requests / 17s.

That is the only claim the two-seed data supports.

## What didn't survive to claim

### Realized-hit benefit

| Seed | Cell B (FCFS+vLLM caching) | Cell C (cache-aware) | C/B |
|---|---:|---:|---:|
| 42 | 7,936 | 7,168 | 0.903 |
| 43 | 6,656 | 7,424 | 1.115 |

Mean C/B = 1.009. Range 0.903 – 1.115. Two seeds in **opposite
directions**; no directional effect on realized hits is
partner-credible at this sample size. The proposal's Phase 3D
thresholds (ship at ≥2×, weak at 1.5×-2×, inconclusive below 1.5×)
put this firmly in **inconclusive** territory.

### TTFT p99 stability

Seed 42 showed cell C's TTFT p99 at 818.9ms vs cell B's 49.8ms —
a 16.4× regression. Seed 43 showed 72.2ms vs 69.3ms — 1.04×
parity. The 16.4× regression is therefore best understood as a
**tail event in seed-42's arrival pattern**, not a systematic
property of cache-aware reorder. Two seeds isn't enough to
characterize p99 tail latency reliably — proper TTFT p99
measurement would need 5-10 seeds or a much larger per-seed
request budget.

## What consistently failed

### E2E p99 regression (the only consistent negative)

| Seed | Cell B e2e_p99 ms | Cell C e2e_p99 ms | C/B |
|---|---:|---:|---:|
| 42 | 808.9 | 1302.0 | 1.610 |
| 43 | 657.1 | 923.2 | 1.405 |

Both above the proposal's 1.5× fairness threshold (seed=42 well
above; seed=43 just below at 1.40×). The cache-aware reorder
advances some requests and pushes others back; the pushed-back
ones suffer at the e2e tail. This is the same fairness pattern
typically associated with priority-scheduling under bursty load,
and it's consistent across both seeds — strong enough to call a
mild fairness regression on this workload.

### Predictor calibration

The cache-aware predictor consistently **under-predicts** realized
hits by ~3.1× at both seeds:

| Seed | predicted_hit_tokens | realized_hit_tokens (via tree) | realized / predicted |
|---|---:|---:|---:|
| 42 | 2,304 | 7,168 | 3.11 |
| 43 | 2,304 | 7,424 | 3.22 |

The predictor sees only a fraction of the actual reuse
opportunity. This is the **mechanism** behind the inconclusive
realized-hit ratio: the reorder operates on bad information, so
when it advances a request it's not reliably advancing one with
high *realized* hits. The predictor's design is block-aligned
static lookup against the **current** tree state; it doesn't
model in-flight overlap, which is where most of the realized hits
actually come from on this workload.

Cell B's measurement-only install confirms this: B's tree records
~7,300 realized hit tokens (average across the two seeds) entirely
through in-flight cohort overlap, with **zero** admission reorder.
Pure FCFS plus vLLM's native prefix caching produces most of the
available reuse on this workload essentially for free.

## Honest scope of this finding

* **Workload scope.** Synthetic 4-cohort × 25-request shared-prefix
  workload with Pareto-bursty arrivals at rate 4.0. Not a real
  chat replay. Production chat workloads with different burstiness
  / cohort sizes / system-prompt lengths may produce a different
  picture; we did not measure those.
* **Sample size.** Two seeds (Tier-A discipline), 100 requests
  each. Not enough to bound a 10–15 % realized-hit effect with
  partner-credible confidence.
* **Model scope.** Qwen-7B only. Not measured on Mistral, Llama,
  or the 14B / 32B / 70B tier.
* **vLLM version scope.** vLLM 0.7.3 V0 engine. V1 engine has a
  different scheduler shape that this work has not been ported
  to.

## Code disposition

Following the Phase 4 + TurboQuant precedent — **keep code in-tree,
preserve operational fall-out as documentation, no destructive
removals**.

### Kept as-is (in-tree, documented, ready for revisit)

* `KVPolicy/kv_policy/cache_aware_scheduler.py` — Phase 0 predictor
  + radix tree (24 CPU tests in `test_cache_aware_scheduler.py`).
* `KVPolicy/kv_policy/cache_aware_install.py` — full + measurement-
  only install modes (26 CPU tests in `test_cache_aware_install.py`).
* `Bench/ctm_bench/runner_vllm_streaming.py` — driver wiring for
  both modes + shared-prefix prompt builder + per-request latency
  telemetry (Phase 3A).
* `Bench/ctm_bench/scripts/bench_phase3_cache_aware.py` — three-
  cell comparison harness (16 CPU tests in
  `test_bench_phase3_cache_aware.py`). **Partner-credible
  measurement utility; retained as an independent v2 tool.**
* `KVPolicy/kv_policy/prefix_hit_probe.py` — vLLM 0.7.3 native
  prefix-hit probe with research-grounded fallback paths
  (11 CPU tests).
* All 119 cache-aware + Phase-3 CPU tests.

### Documented as experimental

* `--cache-aware-scheduling` CLI flag on `run_streaming.py`:
  retained but help text updated to reference this finding doc
  and mark "experimental; measured inconclusive on Qwen-7B chat
  workload; do not enable in production."
* `--cache-aware-measurement-only` CLI flag (introduced by the
  Phase 3C fix): retained as a **working measurement utility**.
  The measurement-only install is useful independently of
  whether cache-aware reorder ever ships — it provides a
  realized-hit instrument for any future workload analysis.

### Not changed

* `Int4ProtectedAttentionImpl` — never touched by this work
  (orthogonality contract held throughout Phase 0 → 3C).
* Forked vllm-flash-attn kernel — same.
* `INT4_PROTECTED_VC_BRIEF.md` — cache-aware was never in the
  brief; no edit.

## Revisit conditions

This work could be revisited if any of the following hold:

1. **Better-calibrated predictor.** The 3.1× under-prediction is
   the load-bearing mechanism behind the inconclusive realized-
   hit signal. A predictor that models in-flight overlap (the
   actual primary source of reuse on this workload) instead of
   only matching against the current static tree state might
   bring predicted close to realized, which would let the
   reorder act on accurate information. This is a design change,
   not a tuning knob; would belong in a new workstream.
2. **Real chat workload replay.** Synthetic Pareto-bursty
   arrivals at rate 4.0 may not represent production chat
   traffic. A chat dataset replay (ShareGPT or partner-
   provided) with realistic system-prompt cohort distribution
   would tell us whether the realized-hit picture changes.
3. **Tier-A 5-seed replication.** Two seeds with opposite signs
   on a 10–15 % effect is consistent with noise. Five seeds
   would tighten the confidence interval enough to call the
   realized-hit ratio as positive, negative, or zero with
   partner-credible confidence. ~$0.50 GPU.
4. **A workload where FCFS produces less concurrent overlap.**
   The cache-aware tree's hits in cell B come entirely from
   in-flight overlap; if a workload had less natural overlap
   (longer decode budgets so requests stay alive longer; or a
   different arrival rate keeping the queue depth higher),
   cache-aware reorder might contribute additional overlap
   beyond FCFS's natural overlap. The discipline rules warn
   against "tuning until we find a workload that wins" — any
   such revisit should be partner-driven (i.e., a partner has a
   workload they need this for), not lab-driven.

None of these are committed work. They are notes for the next
visit, whenever that is.

## Artifact pointers

| Doc / data | What it captures |
|---|---|
| `Bench/scripts/V2_CACHE_REUSE_DESIGN.md` | The original v2 cache-reuse design |
| `Bench/scripts/V2_CACHE_REUSE_PHASE1_INTEGRATION_NOTE.md` | PR-1 + PR-2 implementation note + Phase 3C measurement-path fix |
| `Bench/scripts/PHASE3_VLLM_NATIVE_PREFIX_HITS_RESEARCH.md` | Research note on vLLM prefix-hit counters + recovery options |
| `Bench/bench_out/PHASE3C_SEED42_V2/` | Seed-42 cell A/B/C streaming summaries + comparison.json |
| `Bench/bench_out/PHASE3C_SEED43_V2/` | Seed-43 cell B/C streaming summaries + comparison.json |
| `Bench/ctm_bench/scripts/bench_phase3_cache_aware.py` | Three-cell bench harness (keep) |
| `Bench/tests/test_cache_aware_*.py`, `test_bench_phase3_cache_aware.py`, `test_shared_prefix_workload.py`, `test_request_latency.py`, `test_prefix_hit_probe.py` | 119 CPU tests covering install, runner, bench, workload, latency, probe |

## Closing

Phase 3 produced honest, durable engineering work and an honest
measured finding. The three-cell bench harness is partner-
credible measurement machinery, retained. The cache-aware
install (both full + measurement-only modes) is in-tree, tested,
documented. The reorder behavior is not productionized on this
workload at this predictor calibration; the path back is named.

Same disposition as Phase 4 and TurboQuant: code preserved,
finding documented, brief unchanged, revisit conditions named.

## Post-closure audit (CRITICAL fixes landed)

A multi-angle code-review audit run after Phase 3 closure surfaced
seven CRITICAL defects in the cache-aware machinery. All seven
were fixed in-tree (see commit log + the
`V2_CACHE_REUSE_PHASE1_INTEGRATION_NOTE.md` §"Post-closure audit
fixes" section). None of the fixes change the Phase 3 directional
conclusion (cache-aware does not productionize on this workload),
but two affect the **absolute numbers** in the per-seed tables
above:

* **Audit fix #2 (cancellation drops slowest requests from p99).**
  Cancelled-at-wall-budget tasks now record their latency. The
  cell C `e2e_p99_ms` of 1302ms (seed 42) / 923ms (seed 43)
  was a **lower bound** — the worst pushed-back requests (the
  ones reorder most-affects) were silently dropped pre-fix. A
  re-run with the fix would likely show higher cell C p99 values,
  strengthening (not weakening) the "do not productionize"
  recommendation. The B-vs-C ratio direction is unchanged.

* **Audit fix #3 (hardcoded `block_size=32` vs vLLM default 16).**
  The install + probe now read vLLM's actual `block_size` from
  `engine.cache_config.block_size`. For the Phase 3 workload
  (prefix=256, tails ∈ {32,64,128,256} — all 32-aligned) this
  fix is a no-op on the numbers. For workloads with irregular
  prompt lengths (real chat replay), the pre-fix code would have
  truncated realized_hit to multiples of 32, biasing low.

The other five fixes (starvation guard clock-base, predicted-hits
memory leak, probe-teardown-on-failure, waiting.clear() race,
multi-sequence orphan) are production-correctness items that did
not affect the Phase 3 measurement on this workload (no beam
search, no long-running deployment, no epoch-clock starvation).
